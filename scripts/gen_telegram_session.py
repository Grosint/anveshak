from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = input("Enter API ID: ")
api_hash = input("Enter API Hash: ")

with TelegramClient(StringSession(), int(api_id), api_hash) as client:
    session = client.session.save()
    print("\n=== SESSION STRING ===")
    print(session)
    print("\nAdd this to your .env as TELEGRAM_SESSION_STRING=<value>")
