#!/bin/bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}$1${RESET}"; }
warn() { echo -e "${YELLOW}$1${RESET}"; }
err()  { echo -e "${RED}$1${RESET}"; }

# --- Step 1: Check macOS ---
echo "Checking macOS..."
if [ "$(uname)" != "Darwin" ]; then
    err "This script must be run on macOS (detected: $(uname))."
    exit 1
fi
ok "macOS detected."
echo

# --- Step 2: Check Python 3 ---
echo "Checking Python 3..."
if ! command -v python3 >/dev/null 2>&1; then
    err "Python 3 not found."
    echo "Install it from https://www.python.org/downloads/ then re-run setup.sh"
    exit 1
fi
PY_VERSION=$(python3 --version 2>&1)
ok "${PY_VERSION} found."
echo

# --- Step 3: Create virtual environment ---
echo "Setting up virtual environment..."
if [ -d ".venv" ]; then
    ok "Virtual environment already exists, skipping."
else
    python3 -m venv .venv
    ok "Virtual environment created."
fi
echo

# --- Step 4: Install dependencies ---
echo "Installing dependencies..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
ok "Dependencies installed."
echo "Installed package versions:"
.venv/bin/pip list --format=columns | grep -iE "pillow|python-telegram-bot|python-dotenv" || true
echo

# --- Step 5: Check printer ---
echo "Checking printer..."
PRINTER_OUTPUT=$(lpstat -p 2>/dev/null || true)
if echo "$PRINTER_OUTPUT" | grep -qi "MITSUBISHI"; then
    ok "Mitsubishi printer detected:"
    echo "$PRINTER_OUTPUT" | grep -i "MITSUBISHI"
    DETECTED_NAME=$(echo "$PRINTER_OUTPUT" | grep -i "MITSUBISHI" | head -1 | awk '{print $2}')
    if [ -n "$DETECTED_NAME" ]; then
        echo "Set PRINTER_NAME=${DETECTED_NAME} in your .env file"
    fi
else
    warn "Mitsubishi printer not detected in lpstat output."
    echo "Make sure the printer is connected and the CP-D90DW driver is installed."
    echo "Driver download: https://www.mitsubishielectric.com/printer"
    echo "You can continue setup — connect the printer before running the bots."
    if [ -n "$PRINTER_OUTPUT" ]; then
        echo "Detected printers:"
        echo "$PRINTER_OUTPUT"
    fi
fi
echo

# --- Step 6: Create .env from template ---
echo "Setting up .env..."
if [ -f ".env" ]; then
    ok ".env already exists, skipping. Edit it manually if needed."
elif [ -f ".env.example" ]; then
    cp .env.example .env
    ok ".env created from .env.example"
    echo "Open .env and fill in your Telegram bot tokens and password."
else
    cat > .env <<'EOF'
BOT_TOKEN=YOUR_PRINT_BOT_TOKEN
MONITOR_BOT_TOKEN=YOUR_MONITOR_BOT_TOKEN
GALLERY_BOT_TOKEN=YOUR_GALLERY_BOT_TOKEN
PRINT_BOT_TOKEN=YOUR_PRINT_BOT_TOKEN
GALLERY_CHANNEL_ID=YOUR_CHANNEL_ID
MONITOR_PASSWORD=changeme
PRINTER_NAME=MITSUBISHI_CPD90D
RIBBON_CAPACITY=700
INK_ALERT_THRESHOLD=100
MAX_COPIES=20
MAX_FILE_SIZE_MB=20
MIN_PRINT_PX=1200
PRINT_TIME_PER_COPY_SECONDS=12
LOG_FILE=print_log.jsonl
GALLERY_LOG_FILE=gallery_log.jsonl
QUEUE_FILE=queue.jsonl
LOG_ARCHIVE_DIR=logs
EOF
    ok ".env created. Open it and fill in your bot tokens and password."
fi
echo

# --- Step 7: Create logs directory ---
echo "Creating logs directory..."
mkdir -p logs
ok "logs/ directory ready."
echo

# --- Step 8: Make scripts executable ---
echo "Making scripts executable..."
chmod +x run.sh stop.sh status.sh 2>/dev/null || true
ok "Scripts are executable."
echo

# --- Step 9: Syntax check all bot files ---
echo "Syntax-checking bot files..."
for f in bot.py monitor.py gallery.py; do
    if [ ! -f "$f" ]; then
        warn "$f not found, skipping."
        continue
    fi
    if ERR_OUTPUT=$(.venv/bin/python -m py_compile "$f" 2>&1); then
        ok "$f OK"
    else
        err "$f FAILED"
        echo "$ERR_OUTPUT"
    fi
done
echo

# --- Final summary ---
echo "╔══════════════════════════════════════════╗"
echo "║           Setup complete!                ║"
echo "╚══════════════════════════════════════════╝"
echo
echo "Next steps:"
echo "  1. Open .env and fill in:"
echo "     - BOT_TOKEN (print bot, from @BotFather)"
echo "     - MONITOR_BOT_TOKEN (monitor bot, from @BotFather)"
echo "     - GALLERY_BOT_TOKEN (gallery bot, from @BotFather)"
echo "     - GALLERY_CHANNEL_ID (from @userinfobot)"
echo "     - MONITOR_PASSWORD (choose any password)"
echo "     - PRINTER_NAME (from lpstat -p)"
echo "  2. Install the CP-D90DW driver if not already installed"
echo "  3. Run: ./run.sh to start all bots"
echo "  4. Run: ./status.sh to verify all bots are running"
