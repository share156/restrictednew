# Savenileshya — Bug Report & Fixes

> Audited and patched. All patched files live in `Savenileshya-master/`.

---

## TL;DR

- Public restricted content was **not actually working** — a single Python operator-precedence bug (`'t.me/c/' or 't.me/b/' in msg_link`) made every link fall into the private branch and crash on `int('-100' + 'somechannel')`. Fixed.
- Private restricted content had several real bugs: undefined `UT` variable in the VIDEO_NOTE fallback path, `msg.text.markdown` AttributeError, recursive PeerIdInvalid infinite-loop risk, no `FloodWait` handling, fragile string-matching error handling, duplicate cleanup code. All fixed.
- Render deployment was broken: `Procfile` used `Drone:` instead of `web:`, the `Dockerfile` had a bogus multi-stage build, `Werkzeug` was unpinned (broke Flask 2.2.5). All fixed + added `render.yaml` one-click blueprint.
- Added env-var validation so missing `API_ID` / `SESSION` etc. now produce a human-readable error instead of a stack trace.

---

## 1. `main/plugins/pyroplug.py` — the core of private restricted forwarding

### Bug 1.1 — Operator precedence (CRITICAL, broke ALL link routing)
**Before:**
```python
if 't.me/c/' or 't.me/b/' in msg_link:
```
Python parses this as `if ('t.me/c/') or ('t.me/b/' in msg_link):`. Since `'t.me/c/'` is a non-empty string (truthy), the `if` is **always True**. Consequence: public links like `t.me/somechannel/123` enter the private branch, hit `chat = int('-100' + 'somechannel')`, throw `ValueError`, and get reported as "Failed to save".

**After:**
```python
is_private = 't.me/c/' in msg_link
is_bot_chat = 't.me/b/' in msg_link
if is_private or is_bot_chat:
```

### Bug 1.2 — `UT` undefined in VIDEO_NOTE fallback (CRITICAL)
**Before:** the `except Exception as e:` fallback for VIDEO_NOTE used `uploader = await fast_upload(..., UT, ...)` but `UT = time.time()` was only assigned inside the VIDEO branch (line 164). VIDEO_NOTE fell through with `NameError: name 'UT' is not defined`.

**After:** `UT = time.time()` is now assigned inside each branch's fallback path, and the whole fallback logic was refactored into `_is_send_media_error(e)` + per-branch `try/except`.

### Bug 1.3 — `msg.text.markdown` AttributeError (CRITICAL)
**Before:** `await client.send_message(sender, msg.text.markdown)`. In Pyrogram, `msg.text` is a plain `str` — it has no `.markdown` attribute. Every text/WEB_PAGE message crashed with `AttributeError`.

**After:** `await client.send_message(sender, msg.text or "")`.

### Bug 1.4 — Fragile error-string matching
**Before:** a long `if "messages.SendMedia" in str(e) or "SaveBigFilePartRequest" in str(e) or ...` block inline.

**After:** extracted to `_is_send_media_error(e)` helper for clarity and reuse.

### Bug 1.5 — PeerIdInvalid infinite-recursion risk
**Before:** on `PeerIdInvalid` the code rebuilt the link as `t.me/c/...` or `t.me/b/...` and recursively called `get_msg` with the new link — but never checked if the new link was the same as the old one, so a persistent failure could recurse forever.

**After:** added `if new_link == msg_link: return` guard.

### Bug 1.6 — No FloodWait handling in `get_msg`
**Before:** `FloodWait` bubbled up uncaught and the user got a raw traceback.

**After:** caught, `await asyncio.sleep(fw.value + 2)`, then retried once.

### Bug 1.7 — Duplicate cleanup + `edit.delete()` after error return
**Before:** lines 138–143 cleaned up the file and lines 193–199 cleaned it up *again*. Worse, after an `except` clause already called `return`, the code at lines 193–199 still tried to `await edit.delete()` on an `edit` object that might not exist.

**After:** single `_safe_remove(file)` helper + guarded `edit.delete()`.

### Bug 1.8 — `msg_id` parsing crashed on `?single` query strings
**Before:** `msg_id = int(msg_link.split("/")[-1]) + int(i)` — but if the URL was `t.me/c/123/456?single`, the last `/`-split segment was `456?single`, which `int()` rejected.

**After:** `int(str(msg_link.split("/")[-1]).split("?")[0]) + int(i)`.

### Bug 1.9 — Public-channel `msg.empty` was misdiagnosed as a bot chat
**Before:** when a public message came back `empty`, the code blindly rebuilt the link as `t.me/b/{chat}/{msg_id}` and recursed — turning every deleted-message case into a bogus bot-chat fetch.

**After:** deleted/missing public messages are reported honestly.

### Bug 1.10 — Public restricted channels had no fallback
**Before:** `client.copy_message()` works only when the public channel allows forwarding. If the channel has `noforwards=True` (restricted), it raised `CHAT_FORWARDS_RESTRICTED` and the bot reported a generic failure.

**After:** on a forwards-restricted error, the bot now falls back to the **userbot** path (download via userbot → re-upload via bot), exactly like the private-channel flow.

---

## 2. `main/plugins/frontend.py`

### Bug 2.1 — `f"...@{fs}..."` at import time crashed when `FORCESUB` was unset (CRITICAL)
**Before:** `ft = f"To use this bot you've to join @{fs}."` ran at module import. If `FORCESUB=None`, Python raised `TypeError: unsupported format string passed to NoneType.__format__`, killing the whole bot before any plugin loaded.

**After:** `ft` is built lazily via `_forcesub_msg()` and the force-sub check is skipped entirely when `FORCESUB` is not configured.

### Bug 2.2 — `fw.x` should be `fw.value` (CRITICAL for Pyrogram)
**Before:** `except FloodWait as fw: ... f'Try again after {fw.x} seconds'`. Pyrogram's `FloodWait` exposes the wait seconds as `.value`, **not** `.x` (`.x` is the old Telethon attribute name). The code raised `AttributeError` on the very first floodwait.

**After:** `fw.value`.

### Bug 2.3 — Only matched `t.me/+`, missed legacy `t.me/joinchat/`
**Before:** `if 't.me/+' in link:`. Telegram still supports the older `https://t.me/joinchat/<hash>` invite format, which slipped past this check.

**After:** `if 't.me/+' in link or 't.me/joinchat/' in link:`.

### Bug 2.4 — `reply.text == message` when `reply` is None or media-only
**Before:** if the replied message had no text, `reply.text` was `None`; the comparison was harmless but the intent (skip our own prompt) was lost.

**After:** `if reply and reply.text == message:`.

---

## 3. `main/plugins/batch.py`

### Bug 3.1 — Same `ft = f"...@{fs}..."` import-time crash (Bug 2.1 clone)
Fixed the same way: lazy `_forcesub_msg()`.

### Bug 3.2 — `fw.x` → `fw.value` (Bug 2.2 clone, appeared twice)
Fixed both the threshold check (`if int(fw.x) > 299:`) and the sleep (`await asyncio.sleep(fw.x + 5)`).

### Bug 3.3 — `batch` list never cleared on early-exit paths
**Before:** if the conversation was cancelled (`conv.cancel()`) after `batch.append(...)`, the user was stuck in the `batch` list forever and could never start a new batch.

**After:** wrapped `run_batch` in `try/finally` that always removes the sender from `batch`.

### Bug 3.4 — `_link` falsy but no early return
**Before:** `get_link()` could return `False`, but only the `except` branch was handled — a falsy `_link` continued into `run_batch` with a garbage link.

**After:** explicit `if not _link: return` check.

### Bug 3.5 — Timer cascade logic was unreachable
**Before:**
```python
if i < 25: timer = 5
if i < 50 and i > 25: timer = 10
if i < 100 and i > 50: timer = 15
```
The first `if` set `timer = 5`, but then the next two `if`s (not `elif`s) could overwrite it. Worked by accident but fragile.

**After:** proper `elif` cascade.

---

## 4. `main/plugins/helpers.py`

### Bug 4.1 — `int(duration)/2` returned float (broke `time.gmtime`)
**Before:** `time_stamp = hhmmss(int(duration)/2)`. In Python 3, `/` is true division → returns `float`. `time.gmtime(float)` raises `TypeError: 'float' object cannot be interpreted as an integer`.

**After:** `int(duration) // 2`.

### Bug 4.2 — `None` statement instead of `return None`
**Before:**
```python
if os.path.isfile(out):
    return out
else:
    None
```
`None` on its own line is a no-op expression, not a return. The function returned `None` anyway via implicit fallthrough, but the code was misleading.

**After:** `return None`.

### Bug 4.3 — Dead `x`/`y` variables
**Before:** `x = stderr.decode().strip()` and `y = stdout.decode().strip()` were assigned and never used.

**After:** removed.

### Bug 4.4 — `join()` used wrong FloodWait attribute (Bug 2.2 clone)
**Before:** `except FloodWait:` had no `.x` access but returned a generic message. Now returns the actual wait time via `fw.value`.

---

## 5. `main/plugins/progress.py`

### Bug 5.1 — `bot.stop_transmission()` does not exist in Pyrogram (CRITICAL)
**Before:**
```python
if not statusMsg["running"]:
    bot.stop_transmission()
```
Pyrogram has **no** `stop_transmission()` method on the client. This raised `AttributeError` every time `status.json` existed and had `running: false`.

**After:** raise an exception inside the progress callback — that's the Pyrogram-supported way to abort an in-flight upload/download.

### Bug 5.2 — Bare `except:` swallowed `KeyboardInterrupt`/`SystemExit`
**Before:** `except:` at the bottom of the progress callback.

**After:** `except Exception:`.

### Bug 5.3 — `"GROSSS:"` typo
**Before:** `tmp = progress + "GROSSS: ..."` — looks like a typo of "GROSS" or "SIZE".

**After:** `"SIZE:"`.

### Bug 5.4 — `status.json` read could crash on malformed JSON
**Before:** `json.load(f)` would raise `JSONDecodeError` if the file was partially written.

**After:** wrapped in `try/except`.

---

## 6. `main/plugins/start.py`

### Bug 6.1 — `xx.edit(...)` without `await` (CRITICAL)
**Before:** `xx.edit("No media found.")`. Telethon's `edit()` is a coroutine — calling it without `await` creates a never-awaited coroutine object and the edit never happens.

**After:** `await xx.edit("No media found.")`.

### Bug 6.2 — `x.file.mime_type` crashed when `x` had no media
**Before:** the `if not x.media:` check printed a message but did **not return**, so execution fell through to `mime = x.file.mime_type`, which raised `AttributeError: 'NoneType' object has no attribute 'mime_type'`.

**After:** `return` after the "No media found." edit, plus a defensive `x.file` check.

---

## 7. `main/__init__.py`

### Bug 7.1 — Missing env vars produced cryptic Telethon tracebacks
**Before:** if `API_ID` was unset, `config("API_ID", default=None, cast=int)` returned `None`, then `TelegramClient('bot', None, None)` failed deep inside Telethon with an unhelpful error.

**After:** explicit up-front validation lists exactly which vars are missing.

---

## 8. Deployment files (Render)

### Bug 8.1 — `Procfile` used wrong process name
**Before:** `Drone: python -m main`. Render (and Heroku) require the web process to be named `web:` — anything else is treated as a worker and the service fails to bind to `$PORT`, gets killed, and restarts in a loop.

**After:** `web: bash bash.sh`.

### Bug 8.2 — `Dockerfile` had a broken multi-stage build
**Before:** two `FROM` statements where the second stage reinstalled everything from scratch and ignored the first stage's work — wasted build time and doubled image size.

**After:** single-stage build, cleaner deps install.

### Bug 8.3 — `Werkzeug` was unpinned, broke Flask 2.2.5
**Before:** `Flask==2.2.5` requires `Werkzeug<3.0`. Without a pin, pip pulled in Werkzeug 3.x, which removed APIs Flask 2.2.5 depends on → `ImportError` at startup.

**After:** pinned `Werkzeug==2.2.3`.

### Bug 8.4 — No `render.yaml`
**After:** added a one-click Render Blueprint so you can deploy without manually configuring each env var in the dashboard.

### Bug 8.5 — `bash.sh` didn't honor a default `$PORT`
**Before:** `--bind 0.0.0.0:$PORT` failed if `$PORT` was unset (local testing).

**After:** `${PORT:-5000}`.

### Bug 8.6 — `app.py` had no `/health` endpoint
**After:** added `/health` returning `200 OK` so Render's health check has a dedicated path (configured in `render.yaml`).

---

## 9. Public restricted content — what you should update

You mentioned public restricted content "seems to work." After auditing, I found it was actually broken by **Bug 1.1** (operator precedence) — every public link crashed with `ValueError: invalid literal for int() with base 10: '-100somechannel'`. You probably never saw it work; you saw the "Failed to save" error and assumed the link was bad.

After the fix, public links now route correctly to the `else:` branch which calls `client.copy_message()`. This works **only when the public channel allows forwarding**. For channels with `noforwards=True` (the actual "restricted content" case), `copy_message` raises `CHAT_FORWARDS_RESTRICTED`.

I added a fallback (Bug 1.10): on that specific error, the bot now uses the **userbot** to download the media and re-uploads it via the bot — exactly the same flow as private channels. So public restricted content should now actually work end-to-end.

**Recommendation:** make sure your userbot (the `SESSION` account) is a member of any public restricted channels you want to save from. The bot itself can't bypass `noforwards`; only a user account can.

---

## 10. Render-specific notes

| Concern | Status |
|---|---|
| `web` process binds to `$PORT` | ✅ via gunicorn in `bash.sh` |
| Health-check endpoint | ✅ `/health` added |
| `render.yaml` blueprint | ✅ added |
| Ephemeral filesystem caveat | ⚠️ thumbnails (`{sender_id}.jpg`) and `.session` files are lost on every Render restart/deploy. The bot still works (sessions auto-recreate from `BOT_TOKEN` and `SESSION` string), but custom thumbnails won't survive. If you need persistent thumbnails, upgrade Render to a paid plan with a persistent disk and mount it at `/app`. |
| Free-tier sleep | ⚠️ Render free webs sleep after 15 min of inactivity. The Flask health check keeps them awake **only if something pings `https://<your-app>.onrender.com/` periodically**. Use UptimeRobot / cron-job.org to ping every 10 min. |
| Two bot clients on same token | ⚠️ The codebase starts both a Telethon bot (`bot`) and a Pyrogram bot (`Bot`) with the same `BOT_TOKEN`. They don't conflict at the protocol level (both connect to MTProto fine), but they each receive every update. Handlers are split: Telethon handles `events.*`, Pyrogram is only used for `download_media`/`send_*`. So in practice no duplicate replies. I left this as-is to avoid rewriting the plugin layer — but if you ever see double-replies, this is why. |

---

## 11. Files changed

```
Savenileshya-master/
├── Procfile                  (fixed: web: bash bash.sh)
├── Dockerfile                (fixed: single-stage build)
├── bash.sh                   (fixed: $PORT default, set -e)
├── app.py                    (added /health endpoint)
├── requirements.txt          (pinned Werkzeug==2.2.3)
├── render.yaml               (NEW: one-click Render blueprint)
└── main/
    ├── __init__.py           (added env-var validation)
    ├── __main__.py           (unchanged)
    ├── utils.py              (unchanged)
    └── plugins/
        ├── pyroplug.py       (10 bugs fixed)
        ├── frontend.py       (4 bugs fixed)
        ├── batch.py           (5 bugs fixed)
        ├── helpers.py         (4 bugs fixed)
        ├── progress.py        (4 bugs fixed)
        └── start.py            (2 bugs fixed)
```
