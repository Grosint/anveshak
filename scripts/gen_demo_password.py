#!/usr/bin/env python3
"""Generate demonstration account passwords for .env - issue #41.

Passwords are no longer pasted into a seed file as bcrypt hashes.
scripts/seed_demo_org.py reads them from the environment and hashes them at
seed time, so what this script produces is .env lines rather than SQL.

Usage:
    uv run python scripts/gen_demo_password.py          # all three accounts
    uv run python scripts/gen_demo_password.py --length 32
"""

from __future__ import annotations

import argparse
import secrets

PASSWORD_VARS = (
    "ANVESHAK_DEMO_ANALYST_PASSWORD",
    "ANVESHAK_DEMO_ADMIN_PASSWORD",
    "ANVESHAK_DEMO_SUPERADMIN_PASSWORD",
)

# bcrypt hashes the first 72 bytes only, so a longer password is partly
# decorative. Stay well inside that.
MAX_LENGTH = 64


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate demonstration account passwords")
    parser.add_argument(
        "--length",
        type=int,
        default=24,
        help="password length in characters (default: 24)",
    )
    args = parser.parse_args()

    if not 12 <= args.length <= MAX_LENGTH:
        print(f"ERROR: --length must be between 12 and {MAX_LENGTH}")
        return 1

    print("Add these to .env, then run: make seed-demo\n")
    for var in PASSWORD_VARS:
        # token_urlsafe returns roughly 1.3 characters per byte.
        password = secrets.token_urlsafe(args.length)[: args.length]
        print(f"{var}={password}")
    print("\nRerunning the seed after changing a password updates the account.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
