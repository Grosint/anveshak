"""The demonstration organisation seeder, checked without a database - issue #41.

Three properties matter and none of them need PostgreSQL:

  - Credentials come from the environment. A missing or weak password stops the
    seed rather than quietly seeding an account nobody can defend.
  - The seed is reproducible. The same environment produces the same identifiers
    on a fresh database and on a rerun, so a demonstration can be rebuilt.
  - The writes are idempotent. Rerunning after a password rotation converges on
    the new password instead of failing on a duplicate username.

Whether the seeded analyst can actually log in and see only their own
organisation is an API question, and is asserted in
tests/integration/test_demo_org_api_seam.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.seed_demo_org import (
    MIN_PASSWORD_LENGTH,
    ORG_ID,
    ORG_NAME,
    ORG_SLUG,
    SEEDED_BY,
    SQL_STALE_SEEDED_USERS,
    SQL_UPSERT_ORG,
    SQL_UPSERT_USER,
    SeedConfigError,
    build_plan,
    check_environment_allows_seeding,
    database_url,
    resolve_org_id,
    user_id_for,
    warn_about_stale_accounts,
)

pytestmark = pytest.mark.unit


def _env(**overrides: str) -> dict[str, str]:
    env = {
        "ANVESHAK_DEMO_ANALYST_PASSWORD": "analyst-password-1",
        "ANVESHAK_DEMO_ADMIN_PASSWORD": "admin-password-1",
        "ANVESHAK_DEMO_SUPERADMIN_PASSWORD": "superadmin-password-1",
    }
    env.update(overrides)
    return env


# ---------------------------------------------------------------------------
# Credentials come from the environment
# ---------------------------------------------------------------------------


class TestCredentialsFromEnvironment:
    def test_missing_password_refuses_to_seed(self) -> None:
        env = _env()
        del env["ANVESHAK_DEMO_ANALYST_PASSWORD"]
        with pytest.raises(SeedConfigError) as exc:
            build_plan(env)
        assert "ANVESHAK_DEMO_ANALYST_PASSWORD" in str(exc.value)

    def test_every_missing_password_is_named_at_once(self) -> None:
        # An operator setting up a fresh box should learn all three in one run
        # rather than one per attempt.
        with pytest.raises(SeedConfigError) as exc:
            build_plan({})
        message = str(exc.value)
        for var in (
            "ANVESHAK_DEMO_ANALYST_PASSWORD",
            "ANVESHAK_DEMO_ADMIN_PASSWORD",
            "ANVESHAK_DEMO_SUPERADMIN_PASSWORD",
        ):
            assert var in message

    def test_empty_password_counts_as_missing(self) -> None:
        with pytest.raises(SeedConfigError):
            build_plan(_env(ANVESHAK_DEMO_ANALYST_PASSWORD=""))

    def test_short_password_is_refused(self) -> None:
        short = "x" * (MIN_PASSWORD_LENGTH - 1)
        with pytest.raises(SeedConfigError) as exc:
            build_plan(_env(ANVESHAK_DEMO_ANALYST_PASSWORD=short))
        assert str(MIN_PASSWORD_LENGTH) in str(exc.value)

    def test_password_beyond_the_bcrypt_limit_is_refused(self) -> None:
        # bcrypt takes 72 bytes. Beyond that the tail is not part of the hash,
        # so a rejected login would be indistinguishable from a typo.
        with pytest.raises(SeedConfigError) as exc:
            build_plan(_env(ANVESHAK_DEMO_ANALYST_PASSWORD="p" * 73))
        assert "72" in str(exc.value)

    def test_the_env_example_placeholder_is_refused(self) -> None:
        # Length is not secrecy: the placeholders ship in the repository, so a
        # box seeded from an unedited .env would hand out a published
        # super-admin password.
        with pytest.raises(SeedConfigError) as exc:
            build_plan(_env(ANVESHAK_DEMO_SUPERADMIN_PASSWORD="change-me-demo-superadmin"))
        assert "placeholder" in str(exc.value)

    def test_every_env_example_placeholder_is_refused(self) -> None:
        example = (Path(__file__).resolve().parents[2] / ".env.example").read_text()
        for line in example.splitlines():
            if line.startswith("ANVESHAK_DEMO_") and "PASSWORD=" in line:
                var, value = line.split("=", 1)
                with pytest.raises(SeedConfigError):
                    build_plan(_env(**{var: value}))

    def test_no_password_appears_in_the_error(self) -> None:
        secret = "s3cret-do-not-print"
        with pytest.raises(SeedConfigError) as exc:
            build_plan(
                _env(
                    ANVESHAK_DEMO_ANALYST_PASSWORD=secret,
                    ANVESHAK_DEMO_ADMIN_PASSWORD="",
                )
            )
        assert secret not in str(exc.value)


# ---------------------------------------------------------------------------
# The plan itself
# ---------------------------------------------------------------------------


class TestPlan:
    def test_the_organisation_and_accounts(self) -> None:
        plan = build_plan(_env())
        assert (plan.org_id, plan.org_name, plan.org_slug) == (ORG_ID, ORG_NAME, ORG_SLUG)
        assert {a.role for a in plan.accounts} == {"analyst", "admin", "super-admin"}

    def test_the_organisation_is_the_one_the_sql_corpus_uses(self) -> None:
        # scripts/seed_demo.sql writes its topics, sources and content against
        # this id. A configurable slug put the analyst in an empty workbench.
        seed = (Path(__file__).resolve().parents[2] / "scripts" / "seed_demo.sql").read_text()
        assert f"'{ORG_ID}'" in seed

    def test_the_organisation_is_not_environment_configurable(self) -> None:
        plan = build_plan(_env(ANVESHAK_DEMO_ORG_SLUG="ib-demo", ANVESHAK_DEMO_ORG_NAME="IB Demo"))
        assert plan.org_id == ORG_ID

    def test_analyst_belongs_to_the_organisation(self) -> None:
        plan = build_plan(_env())
        analyst = next(a for a in plan.accounts if a.role == "analyst")
        assert analyst.org_id == plan.org_id

    def test_super_admin_belongs_to_no_organisation(self) -> None:
        # A platform-wide account with an org_id would be scoped by every
        # org-filtered query it runs, which is the opposite of its purpose.
        plan = build_plan(_env())
        superadmin = next(a for a in plan.accounts if a.role == "super-admin")
        assert superadmin.org_id is None

    def test_usernames_are_overridable(self) -> None:
        plan = build_plan(_env(ANVESHAK_DEMO_ANALYST_USERNAME="officer@ib.gov.in"))
        analyst = next(a for a in plan.accounts if a.role == "analyst")
        assert analyst.username == "officer@ib.gov.in"

    def test_role_is_one_the_check_constraint_allows(self) -> None:
        allowed = {"super-admin", "admin", "analyst", "viewer"}
        for account in build_plan(_env()).accounts:
            assert account.role in allowed


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


class TestReproducibleIdentifiers:
    def test_same_username_gives_the_same_id(self) -> None:
        assert user_id_for("demo@anveshak.local") == user_id_for("demo@anveshak.local")

    def test_different_usernames_give_different_ids(self) -> None:
        assert user_id_for("demo@anveshak.local") != user_id_for("admin@anveshak.local")

    def test_id_is_a_uuid(self) -> None:
        import uuid

        uuid.UUID(user_id_for("demo@anveshak.local"))

    def test_plan_ids_are_derived_from_usernames(self) -> None:
        for account in build_plan(_env()).accounts:
            assert account.user_id == user_id_for(account.username)


# ---------------------------------------------------------------------------
# Idempotent writes
# ---------------------------------------------------------------------------


class TestSql:
    def test_org_insert_tolerates_a_rerun(self) -> None:
        assert "on conflict" in SQL_UPSERT_ORG.lower()

    def test_user_insert_converges_on_the_new_password(self) -> None:
        sql = SQL_UPSERT_USER.lower()
        assert "on conflict (username) do update" in sql
        assert "password_hash = excluded.password_hash" in sql

    def test_user_insert_carries_labels(self) -> None:
        # Rule 2: every persisted row carries its classification.
        assert "labels" in SQL_UPSERT_USER.lower()


# ---------------------------------------------------------------------------
# The password never leaves the plan
# ---------------------------------------------------------------------------


class TestPasswordIsNotPrintable:
    def test_account_repr_hides_the_password(self) -> None:
        # A structured log line or a failing assertion that prints a plan must
        # not be the way a demonstration password escapes.
        secret = "repr-should-not-show-this"
        plan = build_plan(_env(ANVESHAK_DEMO_ANALYST_PASSWORD=secret))
        assert secret not in repr(plan)
        assert secret not in repr(plan.accounts[0])

    def test_account_still_carries_the_password(self) -> None:
        secret = "still-needs-hashing"
        plan = build_plan(_env(ANVESHAK_DEMO_ANALYST_PASSWORD=secret))
        assert plan.accounts[0].password == secret


# ---------------------------------------------------------------------------
# Where the seed refuses to run
# ---------------------------------------------------------------------------


class TestDatabaseUrl:
    def test_no_url_and_no_password_is_refused(self) -> None:
        # A default DSN would carry a committed password and quietly seed
        # whichever database answered on it.
        with pytest.raises(SeedConfigError) as exc:
            database_url({})
        assert "POSTGRES_URL" in str(exc.value)

    def test_url_is_returned_as_given(self) -> None:
        dsn = "postgresql://user:pw@host:5432/db"
        assert database_url({"POSTGRES_URL": dsn}) == dsn

    def test_dsn_is_assembled_from_parts(self) -> None:
        dsn = database_url({"POSTGRES_PASSWORD": "simple"})
        assert dsn == "postgresql://anveshak:simple@localhost:5433/anveshak"

    def test_password_punctuation_is_encoded(self) -> None:
        # An unencoded @ or / reparses the DSN into a different host or
        # database rather than failing.
        dsn = database_url({"POSTGRES_PASSWORD": "p@ss/w:rd#1"})
        assert "@localhost:5433/anveshak" in dsn
        assert "p%40ss%2Fw%3Ard%231" in dsn


class TestProductionGuard:
    def test_development_seeds_without_a_flag(self) -> None:
        check_environment_allows_seeding({"ENVIRONMENT": "development"})

    def test_unset_environment_seeds_without_a_flag(self) -> None:
        check_environment_allows_seeding({})

    def test_production_is_refused(self) -> None:
        with pytest.raises(SeedConfigError) as exc:
            check_environment_allows_seeding({"ENVIRONMENT": "production"})
        assert "ANVESHAK_ALLOW_DEMO_SEED" in str(exc.value)

    def test_production_seeds_with_an_explicit_flag(self) -> None:
        check_environment_allows_seeding(
            {"ENVIRONMENT": "production", "ANVESHAK_ALLOW_DEMO_SEED": "1"}
        )


class TestStaleAccountQuery:
    def test_query_finds_rows_this_script_wrote(self) -> None:
        sql = SQL_STALE_SEEDED_USERS.lower()
        assert "seeded_by" in sql
        assert "not (username = any" in sql


# ---------------------------------------------------------------------------
# Reruns against a database that has moved on
#
# A stub connection keeps these deterministic: the rows they need are exactly
# the rows the seeder is deciding about, and PostgreSQL adds nothing to that.
# ---------------------------------------------------------------------------


class _StubConnection:
    def __init__(
        self,
        org_by_slug: str | None = None,
        org_by_name: dict | None = None,
        stale: list[str] | None = None,
    ) -> None:
        self._org_by_slug = org_by_slug
        self._org_by_name = org_by_name
        self._stale = stale or []
        self.executed: list[tuple] = []

    async def fetchval(self, sql: str, *args):
        return self._org_by_slug

    async def fetchrow(self, sql: str, *args):
        return self._org_by_name

    async def fetch(self, sql: str, *args):
        return [{"username": name} for name in self._stale]

    async def execute(self, sql: str, *args) -> None:
        self.executed.append((sql, args))


class TestResolveOrgId:
    async def test_a_fresh_database_uses_the_plans_id(self) -> None:
        plan = build_plan(_env())
        assert await resolve_org_id(_StubConnection(), plan) == plan.org_id

    async def test_an_existing_slug_keeps_its_own_id(self) -> None:
        # POST /api/v1/organizations mints a uuid. Inserting the derived id
        # over it collides on the UNIQUE slug, so adopt the existing id.
        plan = build_plan(_env())
        api_made = "3f1d9a1e-0000-0000-0000-000000000001"
        assert await resolve_org_id(_StubConnection(org_by_slug=api_made), plan) == api_made

    async def test_a_name_another_organisation_holds_is_refused(self) -> None:
        # organizations.name is UNIQUE. Left to PostgreSQL this surfaces as a
        # raw unique violation on a column the caller never chose.
        plan = build_plan(_env())
        conn = _StubConnection(org_by_name={"id": "org-other", "slug": "other"})
        with pytest.raises(SeedConfigError) as exc:
            await resolve_org_id(conn, plan)
        assert "other" in str(exc.value)


class TestStaleAccounts:
    async def test_an_account_seeded_under_an_old_username_is_reported(self) -> None:
        # Renaming an account in .env creates the new one and leaves the old
        # one logging in with its old password.
        plan = build_plan(_env())
        conn = _StubConnection(stale=["demo@anveshak.local"])
        assert await warn_about_stale_accounts(conn, plan) == ["demo@anveshak.local"]

    async def test_nothing_is_reported_when_nothing_is_stale(self) -> None:
        plan = build_plan(_env())
        assert await warn_about_stale_accounts(_StubConnection(), plan) == []

    def test_seeded_rows_are_marked_so_they_can_be_found(self) -> None:
        assert SEEDED_BY in SQL_STALE_SEEDED_USERS or "seeded_by" in SQL_STALE_SEEDED_USERS
