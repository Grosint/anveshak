#!/usr/bin/env python3
"""Bootstrap Telegram session string for Anveshak Social service (criteria 3.7).

Run this ONCE on a machine with keyboard access to complete Telegram's 2FA login.
The output session string is stateless — copy it to .env as TELEGRAM_SESSION_STRING.
It will be valid until you explicitly terminate the session in Telegram settings.

Usage:
    uv run python scripts/bootstrap_telegram_session.py

You will need:
    - TELEGRAM_API_ID and TELEGRAM_API_HASH from https://my.telegram.org
    - Your Telegram phone number
    - The OTP sent to your Telegram app

Output:
    TELEGRAM_SESSION_STRING=<long base64 string>

Copy the output line into your .env file. Never commit it to git.
"""

import asyncio
import os
import sys


async def bootstrap() -> None:
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError:
        print("ERROR: telethon not installed. Run: uv add telethon", file=sys.stderr)
        sys.exit(1)

    api_id_str = os.environ.get("TELEGRAM_API_ID") or input("Enter TELEGRAM_API_ID: ").strip()
    api_hash = os.environ.get("TELEGRAM_API_HASH") or input("Enter TELEGRAM_API_HASH: ").strip()

    try:
        api_id = int(api_id_str)
    except ValueError:
        print("ERROR: TELEGRAM_API_ID must be an integer", file=sys.stderr)
        sys.exit(1)

    print("\nStarting Telegram authentication...")
    print("You will receive an OTP in your Telegram app.\n")

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.start()  # interactive: prompts for phone + OTP

    session_string = client.session.save()
    await client.disconnect()

    print("\n" + "=" * 70)
    print("SUCCESS — copy this line into your .env file:")
    print("=" * 70)
    print(f"TELEGRAM_SESSION_STRING={session_string}")
    print("=" * 70)
    print("\nWARNING: This string is equivalent to your Telegram login.")
    print("Never commit it to git. Store it only in .env (which is gitignored).")


if __name__ == "__main__":
    asyncio.run(bootstrap())
