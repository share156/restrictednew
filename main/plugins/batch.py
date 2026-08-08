#Tg:MaheshChauhan/DroneBots
#Github.com/Vasusen-code

"""
Plugin for both public & private channels!
"""

import time, os, asyncio

from .. import bot as Drone
from .. import userbot, Bot, AUTH
from .. import FORCESUB as fs
from main.plugins.pyroplug import get_bulk_msg
from main.plugins.helpers import get_link, screenshot

from telethon import events, Button, errors
from telethon.tl.types import DocumentAttributeVideo

from pyrogram import Client
from pyrogram.errors import FloodWait

from ethon.pyfunc import video_metadata
from ethon.telefunc import force_sub


def _forcesub_msg():
    if fs:
        return f"To use this bot you've to join @{fs}."
    return "To use this bot you've to join the required channel."


ft = _forcesub_msg()

batch = []

@Drone.on(events.NewMessage(incoming=True, from_users=AUTH, pattern='/cancel'))
async def cancel(event):
    if not event.sender_id in batch:
        return await event.reply("No batch active.")
    batch.clear()
    await event.reply("Done.")

@Drone.on(events.NewMessage(incoming=True, from_users=AUTH, pattern='/batch'))
async def _batch(event):
    if not event.is_private:
        return
    if fs:
        s, r = await force_sub(event.client, fs, event.sender_id, ft)
        if s == True:
            await event.reply(r)
            return
    if event.sender_id in batch:
        return await event.reply(
            "You've already started one batch, wait for it to complete you dumbfuck owner!"
        )
    async with Drone.conversation(event.chat_id) as conv:
        await conv.send_message(
            "Send me the message link you want to start saving from, as a reply to this message.",
            buttons=Button.force_reply()
        )
        try:
            link = await conv.get_reply()
            try:
                _link = get_link(link.text)
            except Exception:
                await conv.send_message("No link found.")
                conv.cancel()
                return
            if not _link:
                await conv.send_message("No link found.")
                conv.cancel()
                return
        except Exception as e:
            print(e)
            await conv.send_message("Cannot wait more longer for your response!")
            conv.cancel()
            return
        await conv.send_message(
            "Send me the number of files/range you want to save from the given message, as a reply to this message.",
            buttons=Button.force_reply()
        )
        try:
            _range = await conv.get_reply()
        except Exception as e:
            print(e)
            await conv.send_message("Cannot wait more longer for your response!")
            conv.cancel()
            return
        try:
            value = int(_range.text)
            if value > 100:
                await conv.send_message("You can only get upto 100 files in a single batch.")
                conv.cancel()
                return
        except (ValueError, TypeError):
            await conv.send_message("Range must be an integer!")
            conv.cancel()
            return
        batch.append(event.sender_id)
        try:
            await run_batch(userbot, Bot, event.sender_id, _link, value)
        except Exception as e:
            print(f"[batch] run_batch error: {e}")
        finally:
            conv.cancel()
            if event.sender_id in batch:
                batch.remove(event.sender_id)


async def run_batch(userbot, client, sender, link, _range):
    for i in range(_range):
        timer = 60
        if i < 25:
            timer = 5
        elif i < 50:
            timer = 10
        elif i < 100:
            timer = 15
        # Public links need shorter delays
        if 't.me/c/' not in link:
            timer = 2 if i < 25 else 3
        try:
            if sender not in batch:
                await client.send_message(sender, "Batch completed.")
                break
        except Exception as e:
            print(e)
            await client.send_message(sender, "Batch completed.")
            break
        try:
            await get_bulk_msg(userbot, client, sender, link, i)
        except FloodWait as fw:
            # FIX: Pyrogram FloodWait uses `.value`, not `.x`.
            if int(fw.value) > 299:
                await client.send_message(
                    sender,
                    "Cancelling batch since you have floodwait more than 5 minutes."
                )
                break
            await asyncio.sleep(fw.value + 5)
            try:
                await get_bulk_msg(userbot, client, sender, link, i)
            except Exception as e:
                print(f"[run_batch retry] error: {e}")
        protection = await client.send_message(
            sender,
            f"Sleeping for `{timer}` seconds to avoid Floodwaits and Protect account!"
        )
        await asyncio.sleep(timer)
        try:
            await protection.delete()
        except Exception:
            pass
