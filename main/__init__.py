#Github.com/Vasusen-code

import logging
import sys
import time

from pyrogram import Client
from pyrogram.errors import FloodWait as PyrogramFloodWait

from telethon.sessions import StringSession
from telethon.sync import TelegramClient
from telethon.errors import FloodWaitError

from decouple import config

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                    level=logging.WARNING)

# variables
API_ID = config("API_ID", default=None, cast=int)
API_HASH = config("API_HASH", default=None)
BOT_TOKEN = config("BOT_TOKEN", default=None)
SESSION = config("SESSION", default=None)
FORCESUB = config("FORCESUB", default=None)
AUTH = config("AUTH", default=None, cast=int)

# FIX: validate required env vars up front so we get a clean, human-readable
# error instead of a cryptic Telethon/Pyrogram traceback on Render.
_missing = []
if not API_ID:
    _missing.append("API_ID")
if not API_HASH:
    _missing.append("API_HASH")
if not BOT_TOKEN:
    _missing.append("BOT_TOKEN")
if not SESSION:
    _missing.append("SESSION")
if _missing:
    print("Missing required environment variables: " + ", ".join(_missing))
    print("Set them in the Render dashboard under Environment.")
    sys.exit(1)


def _retry_on_floodwait(fn, label):
    """Call fn() and retry on FloodWait ONLY. Other errors propagate up.

    Without this, the bot would crash on FloodWait -> Render would restart
    the container -> the .session file would be lost (ephemeral FS) ->
    the bot would re-import its auth key -> Telegram would extend the
    FloodWait -> exponential death loop.

    By sleeping through the FloodWait in-process, we keep the container
    alive (gunicorn is still serving /) and let the wait expire naturally.
    """
    while True:
        try:
            return fn()
        except FloodWaitError as e:
            wait = int(e.seconds) + 10
            print(
                f"[{label}] Telethon FloodWait: sleeping {wait}s before retry. "
                f"DO NOT restart the container — this is normal and will resolve itself."
            )
            time.sleep(wait)
        except PyrogramFloodWait as e:
            wait = int(e.value) + 10
            print(
                f"[{label}] Pyrogram FloodWait: sleeping {wait}s before retry. "
                f"DO NOT restart the container — this is normal and will resolve itself."
            )
            time.sleep(wait)


def _start_telethon_bot():
    client = TelegramClient('bot', API_ID, API_HASH)
    return client.start(bot_token=BOT_TOKEN)


# --- Start all three clients (sleep through any floodwait) ---
print("Starting Telethon bot...")
bot = _retry_on_floodwait(_start_telethon_bot, "Telethon bot")

print("Starting Pyrogram userbot...")
userbot = Client("saverestricted", session_string=SESSION, api_hash=API_HASH, api_id=API_ID)
try:
    _retry_on_floodwait(lambda: userbot.start(), "userbot")
except Exception as e:
    print(f"Userbot Error: {e}\nHave you added a valid SESSION while deploying?")
    sys.exit(1)

print("Starting Pyrogram bot...")
Bot = Client(
    "SaveRestricted",
    bot_token=BOT_TOKEN,
    api_id=int(API_ID),
    api_hash=API_HASH
)
try:
    _retry_on_floodwait(lambda: Bot.start(), "Pyrogram bot")
except Exception as e:
    print(f"Bot start error: {e}")
    sys.exit(1)

print("All clients started successfully!")
