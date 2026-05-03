# Telegram Photobooth Print Bot

A three-bot system for a photobooth setup. Users send photos to the **print bot** via Telegram and they print automatically on a **Mitsubishi CP-D90DW** on 10×15 cm (4×6 in) photo paper. Albums of multiple photos are supported with per-photo copy counts. A **monitor bot** gives the operator real-time stats and alerts, and a **gallery bot** lets authorised users search and browse every printed photo.

---

## Requirements

- macOS
- Python 3.9–3.13 (3.12 recommended; **not 3.14** — `python-telegram-bot 21.6` is incompatible)
- Mitsubishi CP-D90DW connected via USB and added in **System Settings → Printers & Scanners**
- Three Telegram bots created via [@BotFather](https://t.me/BotFather)
- One private Telegram channel for the live gallery feed

---

## Quick deploy

For a brand-new Mac, see [DEPLOY.md](DEPLOY.md) for the full step-by-step guide. Short version:

```bash
git clone https://github.com/darrenwjh97/zapzap_print.git
cd zapzap_print
chmod +x *.sh
./setup.sh                    # creates .venv, installs deps, checks printer, creates .env
# edit .env with your tokens, password, channel ID
./run.sh                      # start all three bots
./status.sh                   # confirm RUNNING
./install-autostart.sh        # (production) auto-start at login + restart on crash
```

---

## File structure

```
.
├── bot.py                        # Print bot
├── monitor.py                    # Admin monitor bot
├── gallery.py                    # Gallery query bot
├── requirements.txt
├── .env                          # Secrets and config (never commit)
├── .env.example                  # Template — safe to commit
│
├── setup.sh                      # One-time setup on a new Mac
├── run.sh                        # Start all three bots
├── stop.sh                       # Stop all three bots
├── status.sh                     # Check which bots are running
├── install-autostart.sh          # Register launchd agents (auto-start at login)
├── uninstall-autostart.sh        # Remove launchd agents
│
├── DEPLOY.md                     # Step-by-step new-Mac deployment guide
├── USER_GUIDE.md                 # End-user instructions for sending photos
│
├── logs/                         # Bot logs + monthly archived print logs
│   ├── bot.log
│   ├── monitor.log
│   ├── gallery.log
│   └── print_log_YYYY_MM.jsonl
├── print_log.jsonl               # One JSON line per print attempt
├── gallery_log.jsonl             # One JSON line per successful print
├── .pids                         # PIDs from ./run.sh (auto-managed)
├── .sessions                     # Persisted monitor bot auth sessions
├── .gallery_sessions             # Persisted gallery bot auth sessions
└── .ink_alerted                  # Low-ink alert flag (runtime)
```

---

## Initial setup (one-time per Mac)

### 1. Create three Telegram bots

Message [@BotFather](https://t.me/BotFather) → `/newbot` three times. Save the three tokens:
- `PRINT_BOT_TOKEN` — public-facing photo bot
- `MONITOR_BOT_TOKEN` — admin/stats bot
- `GALLERY_BOT_TOKEN` — gallery query bot (also posts to the gallery channel)

### 2. Create the gallery channel

1. Telegram → New Channel → **Private** → name it (e.g. "Photobooth Gallery")
2. Manage Channel → Administrators → Add Admin → choose the gallery bot → grant **Post Messages**
3. Send a test message → forward it to [@userinfobot](https://t.me/userinfobot) → it returns the channel ID (negative number, e.g. `-1001234567890`) → this is your `GALLERY_CHANNEL_ID`

### 3. Connect the printer

1. Plug the CP-D90DW into the Mac via USB.
2. **System Settings → Printers & Scanners → Add Printer** → select the Mitsubishi → Add. macOS will install the driver.
3. Verify: `lpstat -p` should show a line containing `MITSUBISHI`.

### 4. Run setup

```bash
./setup.sh
```

This script:
- Verifies macOS and a compatible Python (3.9–3.13)
- Creates `.venv/` and installs `requirements.txt`
- Checks that the Mitsubishi printer is detected
- Creates `.env` from `.env.example`
- Syntax-checks the three bot files

### 5. Fill in `.env`

Open `.env` and set the values shown empty in the template. Only change `PRINTER_NAME` if `lpstat -p` shows a different name than `MITSUBISHI_CPD90D` — otherwise the default works.

> Note: `PRINTER_NAME` is currently hardcoded in `bot.py` to `MITSUBISHI_CPD90D`. If your printer has a different name, edit line 20 of `bot.py`.

### 6. Prevent the Mac from sleeping (production photobooth)

When the Mac sleeps, the bots stop polling Telegram. For an always-on photobooth:
- System Settings → Lock Screen → **Start Screen Saver when inactive**: Never
- System Settings → Battery → Options → **Prevent automatic sleeping when the display is off**: On

### 7. Start the bots

For a one-off / event use:
```bash
./run.sh
./status.sh
```

For permanent install (auto-start at login, auto-restart on crash):
```bash
./install-autostart.sh
```

---

## Day-to-day commands

| Action | Command |
|---|---|
| Start bots manually | `./run.sh` |
| Stop bots | `./stop.sh` |
| Health check | `./status.sh` |
| Install auto-start | `./install-autostart.sh` |
| Remove auto-start | `./uninstall-autostart.sh` |
| Tail print bot log | `tail -f logs/bot.log` |
| Tail monitor log | `tail -f logs/monitor.log` |
| Tail gallery log | `tail -f logs/gallery.log` |
| Check print queue | `lpstat -o` |
| List printers | `lpstat -p` |

> Don't mix manual (`./run.sh`) and auto-start (`./install-autostart.sh`) — pick one. Running both creates duplicate bot instances and triggers Telegram's "Conflict: terminated by other getUpdates request" error.

---

## Print bot

Users send photos to the bot in Telegram. It downloads, corrects rotation, scales and centre-crops to fill 10×15 cm at 300 DPI (no white borders), then prints via `lpr -o media=ME_10x15`. Every job is logged to `print_log.jsonl` and successful prints are also posted to the gallery channel and logged to `gallery_log.jsonl`.

**Single photo** — caption controls copies:

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

End-user-facing instructions live in [USER_GUIDE.md](USER_GUIDE.md).

---

## Monitor bot

Password-protected. Send the password (from `MONITOR_PASSWORD`) to authenticate. Sessions persist to `.sessions` and survive bot restarts.

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

Password-protected (same password as monitor bot). Reads `gallery_log.jsonl` (current ribbon only — does not look at archived logs).

| Command | What it returns |
|---|---|
| `/latest [N]` | Last N photos resent (default 10, max 20) |
| `/gallery [date]` | All photos on a date, or a list of all dates with counts |
| `/photos [name]` | All photos by a person, or full leaderboard |
| `/count` | Total photos, top 5 users, this vs last month |
| `/more` | Continue paginated results (batches of 20) |
| `/logout` | End your session |
| `/help` | List all commands |

Date formats: `25Apr` `25Apr2026` `25 Apr` `25 Apr 2026`

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

| Variable | Default | Where it's used |
|---|---|---|
| `PRINT_BOT_TOKEN` | — | `bot.py` |
| `MONITOR_BOT_TOKEN` | — | `monitor.py` |
| `GALLERY_BOT_TOKEN` | — | `gallery.py` (also bot.py for posting to channel) |
| `MONITOR_PASSWORD` | `changeme` | `monitor.py`, `gallery.py` |
| `GALLERY_CHANNEL_ID` | — | `bot.py` |
| `RIBBON_CAPACITY` | `700` | `monitor.py` |
| `INK_ALERT_THRESHOLD` | `100` | `monitor.py` |
| `LOG_FILE` | `print_log.jsonl` | `bot.py`, `monitor.py` |
| `LOG_ARCHIVE_DIR` | `logs` | `monitor.py` |
| `GALLERY_LOG_FILE` | `gallery_log.jsonl` | `bot.py`, `gallery.py` |

Hardcoded in `bot.py` (edit the file to change):

| Constant | Default | Purpose |
|---|---|---|
| `PRINTER_NAME` | `MITSUBISHI_CPD90D` | Target CUPS printer name |
| `MAX_COPIES` | `20` | Cap on copies per photo |
| `PAPER_W_PX` / `PAPER_H_PX` | `1772` / `1181` | Canvas at 300 DPI for 10×15 cm |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Conflict: terminated by other getUpdates request` | Two instances of the same bot are running — stop one. Check both manual (`./run.sh`) and launchd (`launchctl list \| grep zapzap`). |
| `lpr failed: printer or class does not exist` | Check `lpstat -p` matches the `PRINTER_NAME` in `bot.py` line 20 |
| `No such file or directory: 'lpr'` | Install / re-add the printer in System Settings |
| Bot crashes immediately on Python 3.14 | Recreate the venv with Python 3.12: `rm -rf .venv && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt` |
| `./status.sh` shows STOPPED right after `./run.sh` | Bots crashed — check `tail logs/bot.log` for the actual error |
| Photos don't print but bot replies "Done!" | `lpstat -o` to see the print queue; check the printer is online and has paper |
