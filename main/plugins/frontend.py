#Github.com/Vasusen-code

import time, os

from .. import bot as Drone
from .. import userbot, Bot
from .. import FORCESUB as fs
from main.plugins.pyroplug import get_msg
from main.plugins.helpers import get_link, join

from telethon import events
from pyrogram.errors import FloodWait

from ethon.telefunc import force_sub

# FIX: original code did `f"...@{fs}..."` at module import time. If FORCESUB
# was None (env var not set) this raised TypeError and crashed the whole bot
# before any plugin could load. We build the message lazily and tolerate None.
def _forcesub_msg():
    if fs:
        return f"To use this bot you've to join @{fs}."
    return "To use this bot you've to join the required channel."

message = "Send me the message link you want to start saving from, as a reply to this message."

@Drone.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def clone(event):
    if event.is_reply:
        reply = await event.get_reply_message()
        # FIX: reply.text can be None when the replied message is media-only.
        # Comparing None == message is safe (returns False), but the original
        # intent was to skip when the reply is our own "send me link" prompt.
        if reply and reply.text == message:
            return
    try:
        link = get_link(event.text)
        if not link:
            return
    except TypeError:
        return

    # FIX: only enforce force-sub if FORCESUB is actually configured.
    if fs:
        s, r = await force_sub(event.client, fs, event.sender_id, _forcesub_msg())
        if s == True:
            await event.reply(r)
            return

    edit = await event.reply("Processing!")
    try:
        # FIX: original only matched `t.me/+`. Telegram also still supports the
        # legacy `t.me/joinchat/` invite format. We handle both.
        if 't.me/+' in link or 't.me/joinchat/' in link:
            q = await join(userbot, link)
            await edit.edit(q)
            return
        if 't.me/' in link:
            await get_msg(userbot, Bot, Drone, event.sender_id, edit.id, link, 0)
    except FloodWait as fw:
        # FIX: Pyrogram FloodWait exposes `.value`, not `.x`. The old code
        # raised AttributeError here.
        return await Drone.send_message(
            event.sender_id,
            f'Try again after {fw.value} seconds due to floodwait from telegram.'
        )
    except Exception as e:
        print(f"[clone] error: {e}")
        await Drone.send_message(
            event.sender_id,
            f"An error occurred during cloning of `{link}`\n\n**Error:** {str(e)}"
        )
