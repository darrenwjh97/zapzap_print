#!/bin/bash

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}$1${RESET}"; }
warn() { echo -e "${YELLOW}$1${RESET}"; }
err()  { echo -e "${RED}$1${RESET}"; }

# --- Bot status ---
echo "=== Bot Status ==="
declare -A LOG_FILES
LOG_FILES[print_bot]="logs/bot.log"
LOG_FILES[monitor_bot]="logs/monitor.log"
LOG_FILES[gallery_bot]="logs/gallery.log"

check_bot() {
    local name=$1
    local pid=$2
    local logfile=${LOG_FILES[$name]}

    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        ok "${name} RUNNING (PID ${pid})"
        if [ -f "$logfile" ]; then
            echo "  Last 3 log lines:"
            tail -3 "$logfile" | sed 's/^/    /'
        fi
    else
        err "${name} STOPPED"
    fi
    echo
}

if [ -f ".pids" ]; then
    PRINT_PID=$(grep "^print_bot=" .pids 2>/dev/null | cut -d= -f2 | tr -d '\r\n ')
    MONITOR_PID=$(grep "^monitor_bot=" .pids 2>/dev/null | cut -d= -f2 | tr -d '\r\n ')
    GALLERY_PID=$(grep "^gallery_bot=" .pids 2>/dev/null | cut -d= -f2 | tr -d '\r\n ')
else
    PRINT_PID=""
    MONITOR_PID=""
    GALLERY_PID=""
fi

check_bot print_bot "$PRINT_PID"
check_bot monitor_bot "$MONITOR_PID"
check_bot gallery_bot "$GALLERY_PID"

# --- Printer status ---
echo "=== Printer Status ==="
PRINTER_LINE=$(lpstat -p 2>/dev/null | grep -i "MITSUBISHI" | head -1)
if [ -n "$PRINTER_LINE" ]; then
    PRINTER_NAME=$(echo "$PRINTER_LINE" | awk '{print $2}')
    ok "Printer ONLINE: ${PRINTER_NAME}"
else
    err "Printer NOT DETECTED"
fi
echo

# --- Queue status ---
echo "=== Queue ==="
if [ -f "queue.jsonl" ]; then
    PENDING=$(grep -c '"status":[ ]*"pending"' queue.jsonl 2>/dev/null || echo 0)
    echo "Queue: ${PENDING} jobs pending"
else
    echo "Queue: empty"
fi
echo

# --- Log sizes ---
echo "=== Log Sizes ==="
for f in print_log.jsonl gallery_log.jsonl queue.jsonl; do
    if [ -f "$f" ]; then
        ls -lh "$f" | awk '{print $9, $5}'
    else
        echo "$f not yet created"
    fi
done
echo

# --- Uptime ---
echo "=== Uptime ==="
if [ -f ".pids" ]; then
    STARTED=$(stat -f "%Sm" -t "%d %b %Y %H:%M" .pids 2>/dev/null)
    echo "Bots started: ${STARTED}"
else
    echo "Bots not currently running."
fi
