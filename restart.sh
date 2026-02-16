#!/usr/bin/env bash
# Restart the Linear Hub server on port 8888.
# Usage: ./restart.sh [port]

set -euo pipefail
PORT="${1:-8888}"

echo "Stopping hub server on port $PORT..."
lsof -ti:"$PORT" | xargs kill 2>/dev/null || true
sleep 1

echo "Pulling latest code..."
git pull origin main 2>/dev/null || true

echo "Starting hub server on port $PORT..."
nohup python3 -m hub.server --port "$PORT" > /tmp/hub-server.log 2>&1 &
sleep 2

if curl -sf "http://localhost:$PORT/health" > /dev/null 2>&1; then
    echo "Server running at http://localhost:$PORT"
    echo "Logs: /tmp/hub-server.log"
else
    echo "ERROR: Server failed to start. Check /tmp/hub-server.log"
    exit 1
fi
