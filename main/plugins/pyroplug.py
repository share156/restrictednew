#Github.com-Vasusen-code
#Fixed by Savenileshya bug-fix pass

import asyncio, time, os

from .. import bot as Drone
from main.plugins.progress import progress_for_pyrogram
from main.plugins.helpers import screenshot

from pyrogram import Client, filters
from pyrogram.errors import (
    ChannelBanned, ChannelInvalid, ChannelPrivate,
    ChatIdInvalid, ChatInvalid, PeerIdInvalid, FloodWait
)
from pyrogram.enums import MessageMediaType
from ethon.pyfunc import video_metadata
from ethon.telefunc import fast_upload
from telethon.tl.types import DocumentAttributeVideo
from telethon import events


def thumbnail(sender):
    if os.path.exists(f'{sender}.jpg'):
        return f'{sender}.jpg'
    else:
        return None


async def get_msg(userbot, client, bot, sender, edit_id, msg_link, i):
    """
    userbot:  Pyrogram userbot client (used to fetch restricted media)
    client:  Pyrogram bot client (used to send/upload media back to user)
    bot:     Telethon bot client (used for fallback Telethon uploads)
    """

    edit = ""
    chat = ""
    round_message = False
    # Strip the "?single" suffix used by Telegram for individual media in albums
    if "?single" in msg_link:
        msg_link = msg_link.split("?single")[0]

    # Defensive: make sure msg_id is an int (some links carry extra query params)
    try:
        msg_id = int(str(msg_link.split("/")[-1]).split("?")[0]) + int(i)
    except ValueError:
        await client.edit_message_text(sender, edit_id, f"Invalid message link: `{msg_link}`")
        return

    height, width, duration, thumb_path = 90, 90, 0, None

    # FIX: original code was `if 't.me/c/' or 't.me/b/' in msg_link:` which due
    # to Python operator precedence is ALWAYS True (non-empty string is truthy).
    # That meant public links like `t.me/somechannel/123` fell into the private
    # branch and then crashed on `int('-100' + 'somechannel')`. We now test
    # each substring explicitly.
    is_private = 't.me/c/' in msg_link
    is_bot_chat = 't.me/b/' in msg_link

    if is_private or is_bot_chat:
        # --- Private channel / chat with bot ---
        if is_bot_chat:
            chat = str(msg_link.split("/")[-2])
        else:
            chat = int('-100' + str(msg_link.split("/")[-2]))

        file = ""
        try:
            msg = await userbot.get_messages(chat, msg_id)

            # Handle WEB_PAGE media (link previews) - just forward the text
            if msg.media:
                if msg.media == MessageMediaType.WEB_PAGE:
                    edit = await client.edit_message_text(sender, edit_id, "Cloning.")
                    # FIX: Pyrogram msg.text is a plain string, not an object
                    # with `.markdown` attribute. Old code used `msg.text.markdown`
                    # which raised AttributeError.
                    await client.send_message(sender, msg.text or "")
                    await edit.delete()
                    return

            # Handle text-only messages
            if not msg.media:
                if msg.text:
                    edit = await client.edit_message_text(sender, edit_id, "Cloning.")
                    # FIX: same `.markdown` AttributeError bug.
                    await client.send_message(sender, msg.text or "")
                    await edit.delete()
                    return

            edit = await client.edit_message_text(sender, edit_id, "Trying to Download.")
            file = await userbot.download_media(
                msg,
                progress=progress_for_pyrogram,
                progress_args=(
                    client,
                    "**DOWNLOADING:**\n",
                    edit,
                    time.time()
                )
            )

            if not file:
                # download_media returns None when there's nothing to download
                await client.edit_message_text(
                    sender, edit_id, f"Failed to download media from: `{msg_link}`"
                )
                return

            await edit.edit('Preparing to Upload!')
            caption = msg.caption if msg.caption is not None else None

            # --- Video note (round video message) ---
            if msg.media == MessageMediaType.VIDEO_NOTE:
                round_message = True
                print("Trying to get metadata")
                data = video_metadata(file)
                height, width, duration = data["height"], data["width"], data["duration"]
                print(f'd: {duration}, w: {width}, h:{height}')
                try:
                    thumb_path = await screenshot(file, duration, sender)
                except Exception:
                    thumb_path = None
                try:
                    await client.send_video_note(
                        chat_id=sender,
                        video_note=file,
                        length=height, duration=duration,
                        thumb=thumb_path,
                        progress=progress_for_pyrogram,
                        progress_args=(
                            client,
                            '**UPLOADING:**\n',
                            edit,
                            time.time()
                        )
                    )
                except Exception as e:
                    # FIX: original VIDEO_NOTE branch referenced `UT` before
                    # assignment when it fell into the fast_upload fallback.
                    # We now define UT here so the fallback path works.
                    if _is_send_media_error(e):
                        UT = time.time()
                        uploader = await fast_upload(f'{file}', f'{file}', UT, bot, edit, '**UPLOADING:**')
                        attributes = [DocumentAttributeVideo(
                            duration=duration, w=width, h=height,
                            round_message=round_message, supports_streaming=True
                        )]
                        await bot.send_file(
                            sender, uploader, caption=caption,
                            thumb=thumb_path, attributes=attributes, force_document=False
                        )
                    else:
                        raise

            # --- Regular video (mp4 / mkv) ---
            elif msg.media == MessageMediaType.VIDEO and \
                    msg.video.mime_type in ["video/mp4", "video/x-matroska"]:
                print("Trying to get metadata")
                data = video_metadata(file)
                height, width, duration = data["height"], data["width"], data["duration"]
                print(f'd: {duration}, w: {width}, h:{height}')
                try:
                    thumb_path = await screenshot(file, duration, sender)
                except Exception:
                    thumb_path = None
                try:
                    await client.send_video(
                        chat_id=sender,
                        video=file,
                        caption=caption,
                        supports_streaming=True,
                        height=height, width=width, duration=duration,
                        thumb=thumb_path,
                        progress=progress_for_pyrogram,
                        progress_args=(
                            client,
                            '**UPLOADING:**\n',
                            edit,
                            time.time()
                        )
                    )
                except Exception as e:
                    # Fall back to Telethon fast_upload for big-file errors
                    if _is_send_media_error(e):
                        UT = time.time()
                        uploader = await fast_upload(f'{file}', f'{file}', UT, bot, edit, '**UPLOADING:**')
                        attributes = [DocumentAttributeVideo(
                            duration=duration, w=width, h=height,
                            round_message=round_message, supports_streaming=True
                        )]
                        await bot.send_file(
                            sender, uploader, caption=caption,
                            thumb=thumb_path, attributes=attributes, force_document=False
                        )
                    else:
                        raise

            # --- Photo ---
            elif msg.media == MessageMediaType.PHOTO:
                await edit.edit("Uploading photo.")
                # FIX: original used `bot.send_file` (Telethon) which is fine
                # but inconsistent with the rest. Keep bot.send_file for photos
                # because Pyrogram sometimes re-encodes; Telethon passes through.
                await bot.send_file(sender, file, caption=caption)

            # --- Any other document / animation / audio ---
            else:
                thumb_path = thumbnail(sender)
                try:
                    await client.send_document(
                        sender,
                        file,
                        caption=caption,
                        thumb=thumb_path,
                        progress=progress_for_pyrogram,
                        progress_args=(
                            client,
                            '**UPLOADING:**\n',
                            edit,
                            time.time()
                        )
                    )
                except Exception as e:
                    if _is_send_media_error(e):
                        UT = time.time()
                        uploader = await fast_upload(f'{file}', f'{file}', UT, bot, edit, '**UPLOADING:**')
                        await bot.send_file(
                            sender, uploader, caption=caption,
                            thumb=thumb_path, force_document=True
                        )
                    else:
                        raise

            # Cleanup downloaded file
            _safe_remove(file)
            try:
                await edit.delete()
            except Exception:
                pass

        except (ChannelBanned, ChannelInvalid, ChannelPrivate, ChatIdInvalid, ChatInvalid):
            await client.edit_message_text(
                sender, edit_id,
                "Have you joined the channel? I can't access this private chat."
            )
            return
        except PeerIdInvalid:
            # Try to recover by reconstructing the link in the other format
            chat_part = msg_link.split("/")[-3]
            try:
                int(chat_part)
                new_link = f"t.me/c/{chat_part}/{msg_id}"
            except Exception:
                new_link = f"t.me/b/{chat_part}/{msg_id}"
            # Guard against infinite recursion
            if new_link == msg_link:
                await client.edit_message_text(
                    sender, edit_id, f"Failed to save: `{msg_link}`\n\nError: PeerIdInvalid"
                )
                return
            return await get_msg(userbot, client, bot, sender, edit_id, new_link, i)
        except FloodWait as fw:
            # FIX: Pyrogram FloodWait exposes `.value`, not `.x`
            await asyncio.sleep(fw.value + 2)
            return await get_msg(userbot, client, bot, sender, edit_id, msg_link, i)
        except Exception as e:
            print(f"[get_msg] error: {e}")
            await client.edit_message_text(
                sender, edit_id,
                f'Failed to save: `{msg_link}`\n\nError: {str(e)}'
            )
            _safe_remove(file)
            return

    else:
        # --- Public channel / chat ---
        edit = await client.edit_message_text(sender, edit_id, "Cloning.")
        try:
            chat = msg_link.split("t.me")[1].split("/")[1]
        except Exception as e:
            await client.edit_message_text(
                sender, edit_id, f"Invalid public link: `{msg_link}`\n\nError: {str(e)}"
            )
            return
        try:
            msg = await client.get_messages(chat, msg_id)
            if msg.empty:
                # FIX: original assumed the link was actually a bot chat and
                # blindly rebuilt it as `t.me/b/...`. That's wrong for public
                # channels. We just report that the message wasn't found.
                await client.edit_message_text(
                    sender, edit_id,
                    f"Message not found in `{chat}`. It may have been deleted."
                )
                return
            # Try to copy directly (works when forwarding isn't restricted)
            await client.copy_message(sender, chat, msg_id)
        except Exception as e:
            err_str = str(e)
            # If the public channel restricts forwarding/saving, fall back to
            # using the userbot to download + re-upload (same as private path).
            if "forwards restricted" in err_str.lower() or "CHAT_FORWARDS_RESTRICTED" in err_str:
                try:
                    pub_msg = await userbot.get_messages(chat, msg_id)
                    # Re-use private-style processing by faking a t.me/c/ link
                    # is NOT possible (different chat id), so we replicate the
                    # download+upload flow inline here.
                    file = await userbot.download_media(pub_msg)
                    if file:
                        if pub_msg.media == MessageMediaType.PHOTO:
                            await bot.send_file(sender, file, caption=pub_msg.caption)
                        elif pub_msg.media == MessageMediaType.VIDEO and \
                                pub_msg.video.mime_type in ["video/mp4", "video/x-matroska"]:
                            data = video_metadata(file)
                            h, w, d = data["height"], data["width"], data["duration"]
                            try:
                                thumb_path = await screenshot(file, d, sender)
                            except Exception:
                                thumb_path = None
                            await client.send_video(
                                chat_id=sender, video=file, caption=pub_msg.caption,
                                supports_streaming=True, height=h, width=w, duration=d,
                                thumb=thumb_path,
                            )
                        else:
                            await client.send_document(
                                sender, file, caption=pub_msg.caption,
                                thumb=thumbnail(sender),
                            )
                        _safe_remove(file)
                    elif pub_msg.text:
                        await client.send_message(sender, pub_msg.text)
                    else:
                        await client.edit_message_text(
                            sender, edit_id,
                            f"Could not retrieve content from: `{msg_link}`"
                        )
                        return
                except Exception as e2:
                    print(f"[get_msg public fallback] error: {e2}")
                    await client.edit_message_text(
                        sender, edit_id,
                        f'Failed to save: `{msg_link}`\n\nError: {str(e2)}'
                    )
                    return
            else:
                print(f"[get_msg public] error: {e}")
                await client.edit_message_text(
                    sender, edit_id,
                    f'Failed to save: `{msg_link}`\n\nError: {err_str}'
                )
                return
        try:
            await edit.delete()
        except Exception:
            pass


async def get_bulk_msg(userbot, client, sender, msg_link, i):
    x = await client.send_message(sender, "Processing!")
    await get_msg(userbot, client, Drone, sender, x.id, msg_link, i)


def _is_send_media_error(e):
    """Return True if the error looks like a Pyrogram/Telethon send-media failure
    that we can retry via Telethon fast_upload (e.g. big file, zero-size file)."""
    s = str(e)
    return (
        "messages.SendMedia" in s
        or "SaveBigFilePartRequest" in s
        or "SendMediaRequest" in s
        or s == "File size equals to 0 B"
    )


def _safe_remove(path):
    """Remove a file if it exists, ignoring errors."""
    if not path:
        return
    try:
        if os.path.isfile(path):
            os.remove(path)
    except Exception:
        pass
