#!/bin/bash
# ATLAS Startup Script - Always runs in screen for persistence

SCREEN_NAME="atlas-gateway"

# Check if already running in this screen
if screen -ls | grep -q "$SCREEN_NAME"; then
    echo "Gateway already running in screen $SCREEN_NAME"
    echo "To attach: screen -r $SCREEN_NAME"
    exit 0
fi

# Kill any existing gateway processes not in screen
pkill -f "openclaw-gateway" 2>/dev/null

# Start in a new screen session
echo "Starting OpenClaw gateway in screen session '$SCREEN_NAME'..."
screen -dmS "$SCREEN_NAME" bash -c "cd /workspace/Jarvis && pnpm openclaw gateway"

sleep 2

if screen -ls | grep -q "$SCREEN_NAME"; then
    echo "✅ Gateway started successfully in screen"
    echo "To attach: screen -r $SCREEN_NAME"
    echo "To detach: Ctrl+A, D"
else
    echo "❌ Failed to start gateway"
    exit 1
fi
