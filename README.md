# Telegram Photobooth Print Bot

A three-bot system for a photobooth setup. Users send photos to the **print bot** via Telegram and they print automatically on a **Mitsubishi CP-D90DW** on 10×15 cm (4×6 in) photo paper. Albums of multiple photos are supported with per-photo copy counts. A **monitor bot** gives the operator real-time stats and alerts, and a **gallery bot** lets authorised users search and browse every printed photo.

---

## Requirements

- macOS (uses `lpr` for printing)
- Python 3.11+
- Mitsubishi CP-D90DW connected and configured in CUPS
- Three Telegram bots created via [@BotFather](https://t.me/BotFather)
- One private Telegram channel (for the live gallery feed)

---

## File structure

```
.
├── bot.py                        # Public print bot
├── monitor.py                    # Private admin monitor bot
├── gallery.py                    # Private gallery query bot
├── .env                          # Secrets and config (never commit)
├── .env.example                  # Template — safe to commit
├── requirements.txt
├── print_log.jsonl               # Created at runtime, one JSON line per print job
├── gallery_log.jsonl             # Created at runtime, one JSON line per successful print
├── logs/                         # Monthly archived print logs
│   └── print_log_YYYY_MM.jsonl
├── .sessions                     # Persisted monitor bot auth sessions
├── .gallery_sessions             # Persisted gallery bot auth sessions
└── .ink_alerted                  # Low-ink alert flag (runtime)
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Create three Telegram bots

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. `/newbot` → follow prompts → copy the token → **PRINT_BOT_TOKEN**
3. `/newbot` again → **MONITOR_BOT_TOKEN**
4. `/newbot` again → **GALLERY_BOT_TOKEN**

### 3. Create the gallery channel

1. In Telegram: New Channel → Private → give it a name (e.g. "Photobooth Gallery")
2. Add the gallery bot as Administrator with **Post Messages** permission
3. Forward any channel message to [@userinfobot](https://t.me/userinfobot) to get the `chat_id` (negative number, e.g. `-1001234567890`) → this is your **GALLERY_CHANNEL_ID**

### 4. Verify your printer name

```bash
lpstat -p
```

Use the name shown after `printer` — e.g. `MITSUBISHI_CPD90D`. Update `PRINTER_NAME` in `bot.py` if it differs.

### 5. Configure `.env`

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```env
PRINT_BOT_TOKEN=your_print_bot_token_here
MONITOR_BOT_TOKEN=your_monitor_bot_token_here
MONITOR_PASSWORD=choose_a_strong_password
RIBBON_CAPACITY=400
INK_ALERT_THRESHOLD=50
LOG_FILE=print_log.jsonl
LOG_ARCHIVE_DIR=logs
GALLERY_BOT_TOKEN=your_gallery_bot_token_here
GALLERY_CHANNEL_ID=-1001234567890
GALLERY_LOG_FILE=gallery_log.jsonl
```

Also open `bot.py` and update `BOT_TOKEN` at the top to match your `PRINT_BOT_TOKEN`.

### 6. Add to `.gitignore`

```
.env
.sessions
.gallery_sessions
.ink_alerted
print_log.jsonl
gallery_log.jsonl
logs/
__pycache__/
```

### 7. Run

**Foreground (development / testing):**

```bash
python bot.py       # Terminal 1 — print bot
python monitor.py   # Terminal 2 — monitor bot
python gallery.py   # Terminal 3 — gallery bot
```

**Background (event / production):**

```bash
python bot.py >> /tmp/print-bot.log 2>&1 & python monitor.py >> /tmp/monitor-bot.log 2>&1 & python gallery.py >> /tmp/gallery-bot.log 2>&1 &
```

Stop all:

```bash
pkill -f "python bot.py" && pkill -f "python monitor.py" && pkill -f "python gallery.py"
```

Tail logs:

```bash
tail -f /tmp/print-bot.log
tail -f /tmp/monitor-bot.log
tail -f /tmp/gallery-bot.log
```

---

## Run on macOS startup (launchd)

Create `~/Library/LaunchAgents/com.local.telegram-print-bot.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.local.telegram-print-bot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/path/to/autoprint/bot.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/autoprint</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/telegram-print-bot.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/telegram-print-bot.err</string>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.local.telegram-print-bot.plist
launchctl unload ~/Library/LaunchAgents/com.local.telegram-print-bot.plist
```

---

## Print bot

Users send photos to the bot in Telegram. It downloads, corrects rotation, scales and centre-crops to fill 10×15 cm at 300 DPI (no white borders), then prints via `lpr -o media=ME_10x15`. Every job is logged to `print_log.jsonl` and successful prints are also posted to the gallery channel and logged to `gallery_log.jsonl`.

**Single photo** — add a caption to set copies:

| Caption | Copies |
|---|---|
| *(none)* | 1 |
| `3` or `3x` or `x3` | 3 |

**Album (multiple photos sent together):**

| Caption | Result |
|---|---|
| *(none)* | 1 copy each |
| `3` | 3 copies each |
| `3,5,1` | photo 1 = 3, photo 2 = 5, photo 3 = 1 |

The number of comma-separated values must match the number of photos. If they don't match, the bot replies with an error and nothing prints.

Maximum: **20 copies** per photo.

---

## Monitor bot

Password-protected. Send the password to authenticate. Sessions survive bot restarts.

| Command | What it returns |
|---|---|
| `/stats` | All-time total jobs, copies, success rate |
| `/today` | Today's jobs and copies, broken down by user |
| `/users` | All-time leaderboard by copies printed |
| `/history [N]` | Last N jobs — name, copies, timestamp, status (default 10) |
| `/lastphoto` | Resends the last successfully printed photo |
| `/ink` | `[████████░░] 350 / 400 remaining` progress bar |
| `/queue` | Live print queue output (`lpstat -o`) |
| `/logout` | End your session |
| `/help` | List all commands |

**Auto-alerts** pushed to all authenticated sessions:
- Print failure → immediate alert with error message
- Ribbon below threshold → single alert per ribbon roll (won't repeat until log rotation)

---

## Gallery bot

Password-protected (same password as monitor bot). Send the password to authenticate.

| Command | What it returns |
|---|---|
| `/latest [N]` | Last N photos resent (default 10, max 20) |
| `/gallery [date]` | All photos on a date, or a list of all dates with counts |
| `/photos [name]` | All photos by a person, or full leaderboard |
| `/count` | Total photos, top 5 users, this vs last month |
| `/more` | Continue paginated results (batches of 20) |
| `/logout` | End your session |
| `/help` | List all commands |

Date formats accepted: `25Apr` `25Apr2026` `25 Apr` `25 Apr 2026`

---

## Maintenance

### New ribbon roll

Log rotation happens automatically at midnight when the month changes. To reset manually mid-month after fitting a new ribbon:

```bash
cp print_log.jsonl logs/print_log_$(date +%Y_%m)_manual.jsonl
> print_log.jsonl
rm -f .ink_alerted
```

### Configuration reference

| Variable | Default | Purpose |
|---|---|---|
| `PRINT_BOT_TOKEN` | — | Token for bot.py |
| `MONITOR_BOT_TOKEN` | — | Token for monitor.py |
| `GALLERY_BOT_TOKEN` | — | Token for gallery.py and channel posting |
| `MONITOR_PASSWORD` | `changeme` | Shared password for monitor and gallery bots |
| `GALLERY_CHANNEL_ID` | — | Telegram channel chat_id (negative number) |
| `RIBBON_CAPACITY` | `400` | Total prints per ribbon roll |
| `INK_ALERT_THRESHOLD` | `50` | Alert when remaining prints fall below this |
| `LOG_FILE` | `print_log.jsonl` | Active print log path |
| `LOG_ARCHIVE_DIR` | `logs` | Archive directory for rotated logs |
| `GALLERY_LOG_FILE` | `gallery_log.jsonl` | Gallery log path |
