#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-3005}"
HOST="${HOST:-127.0.0.1}"
LOG_FILE="${LOG_FILE:-.dev-3005.log}"

cd "$(dirname "$0")/.."

nohup npm run dev -- -H "$HOST" -p "$PORT" >"$LOG_FILE" 2>&1 &
echo "Dev server starting (PID=$!)"
echo "Log: $LOG_FILE"
echo "URL: http://$HOST:$PORT"
