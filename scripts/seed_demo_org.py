#!/usr/bin/env python3
"""Seed the demonstration organisation and its accounts - issue #41.

A demonstration needs an organisation, an analyst who belongs to it, an
organisation administrator, and a platform-wide super-admin able to create
further organisations. This script is the only place those rows are written,
so the repository carries no password and no password hash.

Every credential comes from the environment and none has a default:

    ANVESHAK_DEMO_ANALYST_USERNAME  (default: demo@anveshak.local)
    ANVESHAK_DEMO_ANALYST_PASSWORD  required
    ANVESHAK_DEMO_ADMIN_USERNAME    (default: admin@anveshak.local)
    ANVESHAK_DEMO_ADMIN_PASSWORD    required
    ANVESHAK_DEMO_SUPERADMIN_USERNAME (default: superadmin@anveshak.local)
    ANVESHAK_DEMO_SUPERADMIN_PASSWORD required

A missing password stops the run. Pydantic-style silent defaulting would seed
an account with a password nobody knows, which fails later at the login screen
where the cause is invisible.

Identifiers are derived from the slug and the usernames, so a rerun on a fresh
database reproduces the same organisation and the same accounts. User rows
converge on the environment: rotating a password in .env and rerunning updates
the hash rather than failing on the duplicate username.

Run:
    uv run python scripts/seed_demo_org.py
    make seed-demo
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from typing import Mapping
from urllib.parse import quote

import asyncpg
import bcrypt
import structlog

log = structlog.get_logger(__name__)

# No DSN default: a fallback with a guessable password would silently seed
# whatever database happens to answer on it.
POSTGRES_URL_VAR = "POSTGRES_URL"

# Host-side defaults matching the compose port mapping in infra/compose.yml.
DEFAULT_DB_USER = "anveshak"
DEFAULT_DB_HOST = "localhost"
DEFAULT_DB_PORT = "5433"
DEFAULT_DB_NAME = "anveshak"

# Seeding a production deployment with demonstration accounts, one of them
# platform-wide, needs to be a decision rather than a side effect of `make
# setup`. Same shape as ANVESHAK_ALLOW_LIVE.
ALLOW_IN_PRODUCTION_VAR = "ANVESHAK_ALLOW_DEMO_SEED"

# A password shipped in .env.example is published, so it is not a password.
PLACEHOLDER_PREFIX = "change-me"

# Written into every seeded user's labels, so a rerun can find its own rows.
SEEDED_BY = "seed_demo_org"

# bcrypt hashes the first 72 bytes only, and bcrypt>=4 raises rather than
# truncating. Refuse here so the failure names the variable.
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LENGTH = 12
BCRYPT_ROUNDS = 12

# A user id that is stable across machines and reruns. uuid5 over the username
# means the analyst keeps their id when the corpus around them is rebuilt.
USER_ID_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")  # uuid.NAMESPACE_URL

# The organisation is fixed rather than configurable: scripts/seed_demo.sql
# writes its topics, sources and content against this id, and a slug the SQL
# did not know about produced an analyst logged into an empty workbench.
# Further organisations are created through POST /api/v1/organizations, which
# is what the seeded super-admin is for.
ORG_NAME = "Anshul"
ORG_SLUG = "anshul"
ORG_ID = f"org-{ORG_SLUG}"

# slot -> (role, username env var, username default, password env var)
ACCOUNT_SLOTS: tuple[tuple[str, str, str, str], ...] = (
    (
        "analyst",
        "ANVESHAK_DEMO_ANALYST_USERNAME",
        "demo@anveshak.local",
        "ANVESHAK_DEMO_ANALYST_PASSWORD",
    ),
    (
        "admin",
        "ANVESHAK_DEMO_ADMIN_USERNAME",
        "admin@anveshak.local",
        "ANVESHAK_DEMO_ADMIN_PASSWORD",
    ),
    (
        "super-admin",
        "ANVESHAK_DEMO_SUPERADMIN_USERNAME",
        "superadmin@anveshak.local",
        "ANVESHAK_DEMO_SUPERADMIN_PASSWORD",
    ),
)

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

# The organisation is looked up by slug before it is written, because id, name
# and slug are all UNIQUE: an org created through the API carries an id this
# script would never derive, and inserting over it raises a unique violation on
# the slug rather than conflicting on the id.
SQL_FIND_ORG_BY_SLUG = "SELECT id FROM organizations WHERE slug = $1"

# name is UNIQUE as well, so a second organisation reusing the display name
# of an existing one fails on insert. Say which variable to change.
SQL_FIND_ORG_BY_NAME = "SELECT id, slug FROM organizations WHERE name = $1"

# is_active is deliberately absent from the update: a deactivated organisation
# stays deactivated until an operator says otherwise.
SQL_UPSERT_ORG = """
    INSERT INTO organizations (id, name, slug, is_active, created_at, updated_at, labels)
    VALUES ($1, $2, $3, TRUE, NOW(), NOW(), $4::jsonb)
    ON CONFLICT (id) DO UPDATE
        SET name = EXCLUDED.name,
            updated_at = NOW()
"""

SQL_RENAME_ORG = "UPDATE organizations SET name = $2, updated_at = NOW() WHERE id = $1"

# Accounts this script wrote under an earlier username. Rotating a username is
# the natural response to a leaked account, and the old row would otherwise
# stay active with its old password.
SQL_STALE_SEEDED_USERS = """
    SELECT username FROM users
    WHERE labels->>'seeded_by' = $1
      AND NOT (username = ANY($2::text[]))
"""

# Conflict on username rather than id: the id is derived from the username, so
# the two can never disagree, and username is what an operator changes.
SQL_UPSERT_USER = """
    INSERT INTO users (id, username, password_hash, role, org_id, created_at, updated_at, labels)
    VALUES ($1, $2, $3, $4, $5, NOW(), NOW(), $6::jsonb)
    ON CONFLICT (username) DO UPDATE
        SET password_hash = EXCLUDED.password_hash,
            role = EXCLUDED.role,
            org_id = EXCLUDED.org_id,
            updated_at = NOW()
"""


class SeedConfigError(RuntimeError):
    """The environment does not describe a seedable organisation."""


@dataclass(frozen=True)
class SeedAccount:
    """One account to seed.

    `password` is excluded from the repr, so a structured log line or a pytest
    assertion that prints a plan cannot leak it. Comments do not enforce that;
    `field(repr=False)` does.
    """

    user_id: str
    username: str
    password: str = field(repr=False)
    role: str
    org_id: str | None


@dataclass(frozen=True)
class SeedPlan:
    org_id: str
    org_name: str
    org_slug: str
    accounts: tuple[SeedAccount, ...]


def user_id_for(username: str) -> str:
    """Return the stable user id for a username."""
    return str(uuid.uuid5(USER_ID_NAMESPACE, f"anveshak:user:{username}"))


def _password_problem(var: str, value: str | None) -> str | None:
    """Return why this password is unusable, or None. Never quotes the value."""
    if not value:
        return f"{var} is not set"
    if len(value) < MIN_PASSWORD_LENGTH:
        return f"{var} is shorter than {MIN_PASSWORD_LENGTH} characters"
    if len(value.encode()) > MAX_PASSWORD_BYTES:
        return f"{var} is longer than {MAX_PASSWORD_BYTES} bytes, which bcrypt cannot hash"
    if value.startswith(PLACEHOLDER_PREFIX):
        # Length is a poor proxy for secrecy: the .env.example placeholders are
        # 20-plus characters and every clone of the repository holds them.
        return f"{var} is still the .env.example placeholder"
    return None


def build_plan(env: Mapping[str, str]) -> SeedPlan:
    """Turn the environment into a seed plan, or raise SeedConfigError.

    Every problem is collected before raising, so an operator setting up a
    fresh box learns about all three passwords in one run.
    """
    org_name, org_slug, org_id = ORG_NAME, ORG_SLUG, ORG_ID

    problems: list[str] = []
    accounts: list[SeedAccount] = []

    for role, username_var, username_default, password_var in ACCOUNT_SLOTS:
        username = env.get(username_var) or username_default
        password = env.get(password_var)
        problem = _password_problem(password_var, password)
        if problem is not None or password is None:
            problems.append(problem or f"{password_var} is not set")
            continue
        accounts.append(
            SeedAccount(
                user_id=user_id_for(username),
                username=username,
                password=password,
                # A platform-wide account scoped to one organisation would be
                # filtered by every org-scoped query it runs.
                org_id=None if role == "super-admin" else org_id,
                role=role,
            )
        )

    if problems:
        raise SeedConfigError(
            "cannot seed the demonstration organisation: "
            + "; ".join(problems)
            + ". Set them in .env - see .env.example."
        )

    return SeedPlan(
        org_id=org_id,
        org_name=org_name,
        org_slug=org_slug,
        accounts=tuple(accounts),
    )


def _org_labels(slug: str) -> str:
    return json.dumps({"classification": "OPEN", "domain": "osint", "owner_org": slug})


def _user_labels(slug: str, org_id: str | None) -> str:
    return json.dumps(
        {
            "classification": "OPEN",
            "domain": "osint",
            "owner_org": slug if org_id else "anveshak",
            # Marks the row as this script's, so a rerun can report accounts it
            # wrote under a username the environment no longer names.
            "seeded_by": SEEDED_BY,
        }
    )


def hash_password(password: str) -> str:
    """bcrypt hash, matching the API's verifier (rounds=12)."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


async def resolve_org_id(conn: asyncpg.Connection, plan: SeedPlan) -> str:
    """Return the id the organisation with this slug already has, or the plan's.

    An organisation created through POST /api/v1/organizations carries a uuid
    the plan would never derive. Inserting the plan's id over it collides on
    the UNIQUE slug rather than on the id, so the ON CONFLICT clause never
    fires and asyncpg raises.
    """
    existing = await conn.fetchval(SQL_FIND_ORG_BY_SLUG, plan.org_slug)
    if existing:
        return str(existing)

    clash = await conn.fetchrow(SQL_FIND_ORG_BY_NAME, plan.org_name)
    if clash is not None:
        # organizations.name is UNIQUE. Inserting over it would surface as a
        # raw unique violation on a column the caller never chose.
        raise SeedConfigError(
            f"organisation name {plan.org_name!r} already belongs to slug "
            f"{clash['slug']!r} rather than {plan.org_slug!r}: rename that "
            "organisation before seeding"
        )
    return plan.org_id


async def apply_plan(conn: asyncpg.Connection, plan: SeedPlan) -> None:
    """Write the organisation and its accounts. Safe to rerun."""
    org_id = await resolve_org_id(conn, plan)
    if org_id != plan.org_id:
        await conn.execute(SQL_RENAME_ORG, org_id, plan.org_name)
        log.info("seed.org_exists", org_id=org_id, slug=plan.org_slug)
    else:
        await conn.execute(
            SQL_UPSERT_ORG,
            plan.org_id,
            plan.org_name,
            plan.org_slug,
            _org_labels(plan.org_slug),
        )
        log.info("seed.org", org_id=plan.org_id, slug=plan.org_slug)

    for account in plan.accounts:
        await conn.execute(
            SQL_UPSERT_USER,
            account.user_id,
            account.username,
            hash_password(account.password),
            account.role,
            None if account.org_id is None else org_id,
            _user_labels(plan.org_slug, account.org_id),
        )
        log.info(
            "seed.user",
            username=account.username,
            role=account.role,
            org_id=account.org_id,
        )

    await warn_about_stale_accounts(conn, plan)


async def warn_about_stale_accounts(conn: asyncpg.Connection, plan: SeedPlan) -> list[str]:
    """Report accounts this script seeded under a username no longer in use.

    Renaming an account in .env creates the new one and leaves the old one
    logging in with its old password. Deleting it here would be this script
    deciding to remove a user, so it says so loudly instead.
    """
    rows = await conn.fetch(SQL_STALE_SEEDED_USERS, SEEDED_BY, [a.username for a in plan.accounts])
    stale = [row["username"] for row in rows]
    for username in stale:
        log.warning(
            "seed.stale_account",
            username=username,
            reason="seeded under an earlier ANVESHAK_DEMO_*_USERNAME and still active",
            action="delete it, or restore the username in .env",
        )
    return stale


def database_url(env: Mapping[str, str]) -> str:
    """Return the DSN to seed, or raise SeedConfigError.

    POSTGRES_URL wins when it is set. Otherwise the DSN is assembled from the
    same parts compose uses, with the password percent-encoded: an unencoded
    `@` or `/` reparses the DSN into a different host or database rather than
    failing, which is the worst way to learn a password has punctuation in it.

    There is no fallback password. A default would point this script at
    whichever database answered on the guessed host.
    """
    url = env.get(POSTGRES_URL_VAR)
    if url:
        return url

    password = env.get("POSTGRES_PASSWORD")
    if not password:
        raise SeedConfigError(f"neither {POSTGRES_URL_VAR} nor POSTGRES_PASSWORD is set")

    user = env.get("POSTGRES_USER", DEFAULT_DB_USER)
    host = env.get("POSTGRES_HOST", DEFAULT_DB_HOST)
    port = env.get("POSTGRES_PORT", DEFAULT_DB_PORT)
    database = env.get("POSTGRES_DB", DEFAULT_DB_NAME)
    return (
        f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}"
        f"@{host}:{port}/{database}"
    )


def check_environment_allows_seeding(env: Mapping[str, str]) -> None:
    """Refuse a production deployment unless it opts in explicitly."""
    if env.get("ENVIRONMENT", "development").lower() != "production":
        return
    if env.get(ALLOW_IN_PRODUCTION_VAR, "").lower() in ("1", "true", "yes"):
        log.info(
            "seed.production_allowed",
            reason=f"{ALLOW_IN_PRODUCTION_VAR} is set",
        )
        return
    raise SeedConfigError(
        "ENVIRONMENT=production: demonstration accounts, one of them "
        f"platform-wide, are not seeded here unless {ALLOW_IN_PRODUCTION_VAR}=1"
    )


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the demonstration organisation")
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the environment and exit, without touching the database",
    )
    args = parser.parse_args(argv)

    try:
        check_environment_allows_seeding(os.environ)
        plan = build_plan(os.environ)
        dsn = database_url(os.environ)
    except SeedConfigError as exc:
        log.error("seed.refused", reason=str(exc))
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.check:
        print(f"OK: {len(plan.accounts)} accounts configured for {plan.org_id}.")
        return 0

    try:
        conn = await asyncpg.connect(dsn)
    except (OSError, asyncpg.PostgresError) as exc:
        # Never echo the DSN: it carries the database password.
        log.error("seed.connect_failed", error=type(exc).__name__)
        print(f"ERROR: cannot connect to the database ({type(exc).__name__})", file=sys.stderr)
        return 1
    try:
        async with conn.transaction():
            await apply_plan(conn, plan)
    except SeedConfigError as exc:
        log.error("seed.refused", reason=str(exc))
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except asyncpg.PostgresError as exc:
        log.error("seed.write_failed", error=type(exc).__name__, detail=str(exc))
        print(f"ERROR: seed failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await conn.close()

    print(f"Seeded organisation {plan.org_id} with {len(plan.accounts)} accounts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
