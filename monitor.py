import os
import json
import asyncio
import subprocess
import shutil
import logging
from datetime import datetime, timezone, timedelta
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update, Bot
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

load_dotenv()

MONITOR_BOT_TOKEN = os.getenv("MONITOR_BOT_TOKEN", "")
PRINT_BOT_TOKEN = os.getenv("PRINT_BOT_TOKEN", "")
MONITOR_PASSWORD = os.getenv("MONITOR_PASSWORD", "changeme")
RIBBON_CAPACITY = int(os.getenv("RIBBON_CAPACITY", "700"))
INK_ALERT_THRESHOLD = int(os.getenv("INK_ALERT_THRESHOLD", "100"))
LOG_FILE = os.getenv("LOG_FILE", "print_log.jsonl")
LOG_ARCHIVE_DIR = os.getenv("LOG_ARCHIVE_DIR", "logs")
SESSIONS_FILE = ".sessions"
INK_ALERT_FLAG = ".ink_alerted"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

authenticated_sessions: set[int] = set()
prompted_sessions: set[int] = set()


def load_sessions() -> None:
    global authenticated_sessions
    if os.path.exists(SESSIONS_FILE):
        with open(SESSIONS_FILE) as f:
            authenticated_sessions = set(json.load(f))


def save_sessions() -> None:
    with open(SESSIONS_FILE, "w") as f:
        json.dump(list(authenticated_sessions), f)


def is_authenticated(chat_id: int) -> bool:
    return chat_id in authenticated_sessions


# ---------------------------------------------------------------------------
# Log helpers
# ---------------------------------------------------------------------------

def read_entries(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


def read_all_entries() -> list[dict]:
    """Current log + all archived logs, sorted by timestamp."""
    entries = []
    archive_dir = Path(LOG_ARCHIVE_DIR)
    if archive_dir.exists():
        for archive_file in sorted(archive_dir.glob("print_log_*.jsonl")):
            entries.extend(read_entries(str(archive_file)))
    entries.extend(read_entries(LOG_FILE))
    return entries


# ---------------------------------------------------------------------------
# Monthly log rotation
# ---------------------------------------------------------------------------

def rotate_log_if_needed() -> None:
    entries = read_entries(LOG_FILE)
    if not entries:
        return
    try:
        first_ts = datetime.fromisoformat(entries[0]["timestamp"])
    except (KeyError, ValueError):
        return
    first_month = first_ts.strftime("%Y_%m")
    current_month = datetime.now(timezone.utc).strftime("%Y_%m")
    if first_month == current_month:
        return
    archive_dir = Path(LOG_ARCHIVE_DIR)
    archive_dir.mkdir(exist_ok=True)
    archive_path = archive_dir / f"print_log_{first_month}.jsonl"
    shutil.copy(LOG_FILE, archive_path)
    open(LOG_FILE, "w").close()
    if os.path.exists(INK_ALERT_FLAG):
        os.remove(INK_ALERT_FLAG)
    print(f"Rotated log for {first_month.replace('_', '-')}")


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

async def require_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat_id = update.effective_chat.id
    if not is_authenticated(chat_id):
        await update.effective_message.reply_text(
            "This bot is password protected. Send the password to continue."
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_auth(update, context):
        return
    entries = read_all_entries()
    total_jobs = len(entries)
    total_copies = sum(e.get("copies", 0) for e in entries)
    success = sum(1 for e in entries if e.get("status") == "success")
    rate = (success / total_jobs * 100) if total_jobs else 0
    await update.effective_message.reply_text(
        f"📊 *Stats (all time)*\n"
        f"Total print jobs: {total_jobs}\n"
        f"Total copies: {total_copies}\n"
        f"Success rate: {rate:.1f}%",
        parse_mode="Markdown",
    )


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_auth(update, context):
        return
    today = datetime.now(timezone.utc).date().isoformat()
    entries = [e for e in read_entries(LOG_FILE) if e.get("timestamp", "").startswith(today)]
    total_copies = sum(e.get("copies", 0) for e in entries)
    user_copies: dict[str, int] = {}
    for e in entries:
        name = e.get("user_name", "Unknown")
        user_copies[name] = user_copies.get(name, 0) + e.get("copies", 0)
    lines = [f"📅 *Today ({today})*", f"Jobs: {len(entries)}, Copies: {total_copies}"]
    if user_copies:
        lines.append("")
        for name, copies in sorted(user_copies.items(), key=lambda x: -x[1]):
            lines.append(f"• {name}: {copies} {'copy' if copies == 1 else 'copies'}")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_auth(update, context):
        return
    entries = read_all_entries()
    user_copies: dict[str, int] = {}
    for e in entries:
        name = e.get("user_name", "Unknown")
        user_copies[name] = user_copies.get(name, 0) + e.get("copies", 0)
    if not user_copies:
        await update.effective_message.reply_text("No print history yet.")
        return
    lines = ["🏆 *All-time leaderboard*"]
    for i, (name, copies) in enumerate(
        sorted(user_copies.items(), key=lambda x: -x[1]), start=1
    ):
        lines.append(f"{i}. {name}: {copies} copies")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_auth(update, context):
        return
    n = 10
    if context.args:
        try:
            n = int(context.args[0])
        except ValueError:
            pass
    entries = read_entries(LOG_FILE)
    recent = list(reversed(entries[-n:]))
    if not recent:
        await update.effective_message.reply_text("No print history yet.")
        return
    lines = [f"📋 *Last {len(recent)} jobs*"]
    for e in recent:
        try:
            ts = datetime.fromisoformat(e["timestamp"]).astimezone()
            ts_str = ts.strftime("%-d %b %Y %H:%M")
        except Exception:
            ts_str = e.get("timestamp", "?")
        icon = "✅" if e.get("status") == "success" else "❌"
        c = e.get("copies", 1)
        lines.append(
            f"{icon} {e.get('user_name', '?')} — {c} {'copy' if c == 1 else 'copies'} — {ts_str}"
        )
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_lastphoto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_auth(update, context):
        return
    all_entries = read_all_entries()
    for entry in reversed(all_entries):
        if entry.get("status") == "success" and entry.get("photo_file_id"):
            file_id = entry["photo_file_id"]
            try:
                print_bot = Bot(token=PRINT_BOT_TOKEN)
                tg_file = await print_bot.get_file(file_id)
                buf = BytesIO()
                await tg_file.download_to_memory(buf)
                buf.seek(0)
                try:
                    ts = datetime.fromisoformat(entry["timestamp"]).astimezone()
                    ts_str = ts.strftime("%-d %b %Y %H:%M")
                except Exception:
                    ts_str = entry.get("timestamp", "?")
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=buf,
                    caption=f"Last print by {entry.get('user_name', '?')} at {ts_str}",
                )
            except Exception as exc:
                await update.effective_message.reply_text(f"Could not fetch photo: {exc}")
            return
    await update.effective_message.reply_text("No successful prints found.")


async def cmd_ink(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_auth(update, context):
        return
    entries = read_entries(LOG_FILE)
    used = sum(1 for e in entries if e.get("status") == "success")
    remaining = max(0, RIBBON_CAPACITY - used)
    filled = round((remaining / RIBBON_CAPACITY) * 10)
    bar = "█" * filled + "░" * (10 - filled)
    msg = f"🖨️ *Ink Ribbon Status*\n[{bar}] {remaining} / {RIBBON_CAPACITY} remaining"
    if remaining < INK_ALERT_THRESHOLD:
        msg += f"\n⚠️ Low ink — fewer than {INK_ALERT_THRESHOLD} prints remaining."
    await update.effective_message.reply_text(msg, parse_mode="Markdown")


async def cmd_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_auth(update, context):
        return
    result = subprocess.run(["lpstat", "-o"], capture_output=True, text=True)
    output = result.stdout.strip()
    if output:
        await update.effective_message.reply_text(
            f"🖨️ *Print queue:*\n```\n{output}\n```", parse_mode="Markdown"
        )
    else:
        await update.effective_message.reply_text("Queue is empty.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_auth(update, context):
        return
    text = (
        "*Monitor Bot Commands*\n"
        "/stats — total prints, copies, success rate (all time)\n"
        "/today — today's jobs and copies, per user\n"
        "/users — all-time leaderboard by copies\n"
        "/history \\[N\\] — last N jobs (default 10)\n"
        "/lastphoto — resend the last successfully printed photo\n"
        "/ink — ribbon remaining with progress bar\n"
        "/queue — current print queue\n"
        "/logout — end your session\n"
        "/help — show this message"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")


async def cmd_logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if chat_id not in authenticated_sessions:
        await update.effective_message.reply_text("You are not logged in.")
        return
    authenticated_sessions.discard(chat_id)
    save_sessions()
    await update.effective_message.reply_text("Logged out.")


# ---------------------------------------------------------------------------
# Auth message handler
# ---------------------------------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    text = (update.effective_message.text or "").strip()

    if is_authenticated(chat_id):
        return

    if text == MONITOR_PASSWORD:
        authenticated_sessions.add(chat_id)
        prompted_sessions.discard(chat_id)
        save_sessions()
        await update.effective_message.reply_text("Access granted.")
    elif chat_id not in prompted_sessions:
        prompted_sessions.add(chat_id)
        await update.effective_message.reply_text(
            "This bot is password protected. Send the password to continue."
        )
    else:
        await update.effective_message.reply_text("Incorrect password.")


# ---------------------------------------------------------------------------
# Alert helpers
# ---------------------------------------------------------------------------

async def send_alert(app: Application, text: str) -> None:
    for chat_id in list(authenticated_sessions):
        try:
            await app.bot.send_message(chat_id=chat_id, text=text)
        except Exception as exc:
            logger.warning("Alert to %s failed: %s", chat_id, exc)


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------

last_line_count: int = 0


async def poll_log(app: Application) -> None:
    global last_line_count
    while True:
        await asyncio.sleep(10)
        if not os.path.exists(LOG_FILE):
            continue
        lines = []
        with open(LOG_FILE) as f:
            lines = [line.strip() for line in f if line.strip()]
        new_lines = lines[last_line_count:]
        last_line_count = len(lines)
        for line in new_lines:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("status") == "failed":
                await send_alert(
                    app,
                    f"⚠️ Print failed for {entry.get('user_name', '?')}: "
                    f"{entry.get('error', 'unknown error')}",
                )
            elif entry.get("status") == "success":
                current_entries = read_entries(LOG_FILE)
                total_success = sum(1 for e in current_entries if e.get("status") == "success")
                if total_success == 0 and os.path.exists(INK_ALERT_FLAG):
                    os.remove(INK_ALERT_FLAG)
                remaining = max(0, RIBBON_CAPACITY - total_success)
                if remaining < INK_ALERT_THRESHOLD and not os.path.exists(INK_ALERT_FLAG):
                    open(INK_ALERT_FLAG, "w").close()
                    await send_alert(
                        app,
                        f"🪫 Low ink! Estimated {remaining} prints remaining "
                        f"(threshold: {INK_ALERT_THRESHOLD}).",
                    )


async def daily_rotation_task() -> None:
    while True:
        now = datetime.now()
        tomorrow = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        await asyncio.sleep((tomorrow - now).total_seconds())
        rotate_log_if_needed()


# ---------------------------------------------------------------------------
# Startup hook
# ---------------------------------------------------------------------------

async def post_init(app: Application) -> None:
    global last_line_count
    load_sessions()
    rotate_log_if_needed()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            last_line_count = sum(1 for line in f if line.strip())
    asyncio.create_task(poll_log(app))
    asyncio.create_task(daily_rotation_task())
    logger.info("Monitor bot started. Authenticated sessions: %d", len(authenticated_sessions))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not MONITOR_BOT_TOKEN:
        raise SystemExit("Set MONITOR_BOT_TOKEN in .env before running.")

    app = ApplicationBuilder().token(MONITOR_BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", cmd_help))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("users", cmd_users))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("lastphoto", cmd_lastphoto))
    app.add_handler(CommandHandler("ink", cmd_ink))
    app.add_handler(CommandHandler("queue", cmd_queue))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("logout", cmd_logout))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()


if __name__ == "__main__":
    main()
