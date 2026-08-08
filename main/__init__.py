#Github.com/Vasusen-code

from pyrogram import Client

from telethon.sessions import StringSession
from telethon.sync import TelegramClient

from decouple import config
import logging, time, sys

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

bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

userbot = Client("saverestricted", session_string=SESSION, api_hash=API_HASH, api_id=API_ID)

try:
    userbot.start()
except BaseException as e:
    print(f"Userbot Error: {e}\nHave you added a valid SESSION while deploying?")
    sys.exit(1)

Bot = Client(
    "SaveRestricted",
    bot_token=BOT_TOKEN,
    api_id=int(API_ID),
    api_hash=API_HASH
)

try:
    Bot.start()
except Exception as e:
    print(f"Bot start error: {e}")
    sys.exit(1)
