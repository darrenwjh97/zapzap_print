#!/bin/bash

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}$1${RESET}"; }
warn() { echo -e "${YELLOW}$1${RESET}"; }

if [ ! -f ".pids" ]; then
    warn "No .pids file found — bots may not be running."
    exit 0
fi

while IFS='=' read -r name pid; do
    [ -z "$name" ] && continue
    pid=$(echo "$pid" | tr -d '\r\n ')
    if kill -0 "$pid" 2>/dev/null; then
        kill -TERM "$pid" 2>/dev/null
        # Wait up to 5 seconds for clean exit
        for i in 1 2 3 4 5; do
            if ! kill -0 "$pid" 2>/dev/null; then
                break
            fi
            sleep 1
        done
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null
        fi
        ok "${name} stopped (PID ${pid})"
    else
        warn "${name} was not running (PID ${pid})"
    fi
done < .pids

rm -f .pids
ok "All bots stopped."
