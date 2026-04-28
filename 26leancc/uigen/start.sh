#!/bin/bash

# UIGen Development Server Startup Script
# Usage: ./start.sh [--background]

PORT=3000
LOG_FILE="dev-server.log"

cd "$(dirname "$0")"

# Kill any existing process on the port
echo "Checking for existing processes on port $PORT..."
lsof -ti:$PORT | xargs kill -9 2>/dev/null && echo "Killed existing process on port $PORT" || echo "No existing process on port $PORT"

if [ "$1" = "--background" ]; then
    # Background mode
    echo "Starting Next.js development server in background..."
    echo "Logs will be written to $LOG_FILE"
    nohup npx next dev --turbopack --port $PORT --hostname 0.0.0.0 > "$LOG_FILE" 2>&1 &
    SERVER_PID=$!
    sleep 3
    if ps -p $SERVER_PID > /dev/null 2>&1; then
        echo "Server started with PID: $SERVER_PID"
        echo "Access the app at http://localhost:$PORT or http://127.0.0.1:$PORT"
        echo ""
        echo "To view logs: tail -f $LOG_FILE"
        echo "To stop: kill $SERVER_PID or lsof -ti:$PORT | xargs kill -9"
    else
        echo "Server failed to start. Check $LOG_FILE for details."
        cat "$LOG_FILE"
    fi
else
    # Foreground mode (recommended)
    echo "Starting Next.js development server..."
    echo "Access the app at http://localhost:$PORT or http://127.0.0.1:$PORT"
    echo "Press Ctrl+C to stop"
    echo ""
    npx next dev --turbopack --port $PORT --hostname 0.0.0.0
fi
