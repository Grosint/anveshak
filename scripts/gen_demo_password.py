#!/usr/bin/env python3
"""Generate a bcrypt hash for the Anveshak demo password.

Usage:
    uv run python scripts/gen_demo_password.py
    uv run python scripts/gen_demo_password.py --password "YourNewPassword"

The output hash goes into scripts/seed_demo.sql (hashed_password column).
"""

from __future__ import annotations

import argparse
import sys

DEFAULT_PASSWORD = "AnveshakDemo2024!"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate bcrypt hash for demo user")
    parser.add_argument(
        "--password",
        default=DEFAULT_PASSWORD,
        help=f"Password to hash (default: {DEFAULT_PASSWORD})",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=12,
        help="bcrypt cost factor (default: 12)",
    )
    args = parser.parse_args()

    try:
        import bcrypt
    except ImportError:
        print("ERROR: bcrypt not installed. Run: uv add bcrypt", file=sys.stderr)
        sys.exit(1)

    hashed = bcrypt.hashpw(args.password.encode(), bcrypt.gensalt(rounds=args.rounds)).decode()
    print(f"\nPassword : {args.password}")
    print(f"Hash     : {hashed}")
    print()
    print("Paste this hash into scripts/seed_demo.sql hashed_password column.")
    print("Then run: make seed-demo")


if __name__ == "__main__":
    main()
