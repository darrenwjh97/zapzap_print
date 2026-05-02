# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A three-bot Telegram photobooth print system running on macOS:

- **`bot.py`** — the public-facing print bot. Receives single photos and multi-photo albums from users, prints on a Mitsubishi CP-D90DW via `lpr` on 10×15 cm (ME_10x15) paper. Posts every successful print to a private Telegram channel and logs to both `print_log.jsonl` and `gallery_log.jsonl`.
- **`monitor.py`** — a private admin bot. Password-protected. Polls `print_log.jsonl` every 10 s, provides stats/alerts/ink tracking/queue visibility.
- **`gallery.py`** — a private gallery query bot. Password-protected. Reads `gallery_log.jsonl` to answer search queries (`/latest`, `/gallery`, `/photos`, `/count`) and resends photos.

Dependencies: `python-telegram-bot==21.6`, `pillow>=10.0`, `python-dotenv>=1.0`.

## File structure

```
.
├── bot.py                        # Print bot
├── monitor.py                    # Admin monitor bot
├── gallery.py                    # Gallery query bot
├── .env                          # Secrets and config (never commit)
├── .env.example                  # Safe-to-commit template
├── requirements.txt
├── print_log.jsonl               # One JSON line per print attempt (success + failure)
├── gallery_log.jsonl             # One JSON line per successful print (gallery bot's file_ids)
├── logs/
│   └── print_log_YYYY_MM.jsonl   # Monthly archives of print_log
├── .sessions                     # Persisted monitor bot auth sessions
├── .gallery_sessions             # Persisted gallery bot auth sessions
└── .ink_alerted                  # Flag: low-ink alert sent for this ribbon roll
```

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run individual bots
python bot.py
python monitor.py
python gallery.py

# Run all three in the background (single command)
python bot.py >> /tmp/print-bot.log 2>&1 & python monitor.py >> /tmp/monitor-bot.log 2>&1 & python gallery.py >> /tmp/gallery-bot.log 2>&1 &

# Stop all background bots
pkill -f "python bot.py" && pkill -f "python monitor.py" && pkill -f "python gallery.py"

# Tail logs
tail -f /tmp/print-bot.log
tail -f /tmp/monitor-bot.log
tail -f /tmp/gallery-bot.log

# Find available printer names
lpstat -p

# Run as a persistent background service (macOS launchd)
launchctl load ~/Library/LaunchAgents/com.local.telegram-print-bot.plist
launchctl unload ~/Library/LaunchAgents/com.local.telegram-print-bot.plist
```

## Configuration

All runtime config lives in `.env`. Copy `.env.example` to `.env` and fill in values.

| Variable | Default | Purpose |
|---|---|---|
| `PRINT_BOT_TOKEN` | — | Token for bot.py from @BotFather |
| `MONITOR_BOT_TOKEN` | — | Token for monitor.py from @BotFather |
| `GALLERY_BOT_TOKEN` | — | Token for gallery.py and channel posting |
| `MONITOR_PASSWORD` | `changeme` | Shared password for monitor and gallery bots |
| `GALLERY_CHANNEL_ID` | — | Private channel chat_id (negative, e.g. -1001234567890) |
| `RIBBON_CAPACITY` | `400` | Total prints per ribbon roll |
| `INK_ALERT_THRESHOLD` | `50` | Alert when remaining prints fall below this |
| `LOG_FILE` | `print_log.jsonl` | Active print log path |
| `LOG_ARCHIVE_DIR` | `logs` | Directory for monthly archived logs |
| `GALLERY_LOG_FILE` | `gallery_log.jsonl` | Gallery log path |

`bot.py` also has hardcoded values at the top (not in .env):

| Variable | Value | Purpose |
|---|---|---|
| `BOT_TOKEN` | `os.getenv("PRINT_BOT_TOKEN")` | Print bot token — loaded from `.env` |
| `PRINTER_NAME` | `MITSUBISHI_CPD90D` | Target printer (`None` = system default) |
| `PAPER_W_PX` / `PAPER_H_PX` | `1772` / `1181` | Canvas at 300 DPI for 10×15 cm |
| `MAX_COPIES` | `20` | Cap on copies per photo |

## Architecture

### bot.py — routing and image pipeline

**Entry point**: `handle_image(update, context)`
- `message.document` → `process_single_photo` immediately
- `message.photo` with no `media_group_id` → `process_single_photo` immediately
- `message.photo` with `media_group_id` → buffered in `album_buffer`, timer reset to 1.5 s, fires `process_album` after last photo arrives

**`process_single_photo(update, context)`**
Handles one photo or document: download → `fix_exif_rotation` → `fit_to_paper` → save temp JPEG at 300 DPI → `send_to_printer` → `append_print_log` → `post_to_gallery_channel`.

**`process_album(media_group_id, context)`**
Fires after 1.5 s timer. Finds caption from any message in group, calls `parse_copy_list(caption, photo_count)` to get per-photo copy list. If mismatch → replies with error, aborts. Otherwise loops through each photo with `process_single_photo`-equivalent logic.

**`fit_to_paper(img)`**: picks landscape or portrait canvas by aspect ratio, scales to **fill** (centre-crop, no white borders), LANCZOS resize.

**`send_to_printer(jpeg_path, copies)`**: `lpr -# <copies> -o media=ME_10x15 -o fit-to-page -P MITSUBISHI_CPD90D <file>`. Raises `RuntimeError` on non-zero exit.

**Caption parsing**:
- `parse_copy_list(caption, photo_count) -> list[int] | str` — handles `None`, single number, comma-separated. Returns error string on mismatch.
- `parse_copies(caption) -> int` — single-photo wrapper, delegates to `parse_copy_list(caption, 1)[0]`.

**Gallery posting**: `post_to_channel(file_bytes, user_name, copies)` uploads raw bytes (not file_id — file IDs are bot-specific) via gallery bot to the channel. Returns the gallery bot's `file_id` from the sent message.

**Helpers**:
- `append_print_log(user, file_id, copies, status, error)` — wraps `write_log_entry`
- `post_to_gallery_channel(file_bytes, user, copies)` — wraps `post_to_channel` + `write_gallery_log_entry`

### monitor.py — background tasks

- **`poll_log`**: every 10 s, reads new lines from `print_log.jsonl`. `failed` → alert all sessions. `success` → check ink, alert if below threshold (guarded by `.ink_alerted`).
- **`daily_rotation_task`**: at midnight, if first entry is from a prior month → archive to `logs/print_log_YYYY_MM.jsonl`, truncate, delete `.ink_alerted`.
- **Session auth**: password-based, persisted to `.sessions`.

### gallery.py — query bot

- Reads `gallery_log.jsonl` only (no archived logs — gallery is current ribbon only).
- Resends photos using `GALLERY_BOT_TOKEN` + stored `file_id` (gallery bot's own IDs, always reusable).
- Pagination: batches of 20, `/more` continues. State in memory per chat_id, reset on new command.

### Log formats

**`print_log.jsonl`** — one entry per print attempt:
```json
{
  "timestamp": "2026-04-25T06:32:11.123456+00:00",
  "user_id": 123456789,
  "user_name": "Alice",
  "username": "alice_tg",
  "copies": 2,
  "status": "success",
  "error": null,
  "photo_file_id": "AgACAgIAAxk..."
}
```

**`gallery_log.jsonl`** — one entry per successful print (gallery bot's file_id):
```json
{
  "timestamp": "2026-04-25T06:32:11.123456+00:00",
  "user_id": 123456789,
  "user_name": "Alice",
  "username": "alice_tg",
  "photo_file_id": "AgACAgIAAxk...",
  "copies": 2
}
```

monitor.py `/stats` and `/users` read current + all archived print logs. `/today` and `/history` read current only. `/ink` counts current log only (resets on rotation).
