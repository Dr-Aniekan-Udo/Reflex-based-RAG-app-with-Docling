#!/bin/bash
# Unified launcher: Redis + Reflex
# Usage: bash start.sh

set -e

echo "=================================="
echo "       RAG App - Launcher         "
echo "=================================="
echo ""

# ─── 1. Environment Check ───
if [ -n "$CODESPACE_NAME" ]; then
    echo "GitHub Codespaces detected: $CODESPACE_NAME"
    IS_CODESPACE=1
else
    echo "Local development mode"
    IS_CODESPACE=0
fi

# ─── 2. Start Redis ───
echo ""
echo "Checking Redis..."
if redis-cli ping > /dev/null 2>&1; then
    echo "Redis is already running"
else
    echo "Starting Redis server..."
    redis-server --daemonize yes --bind 127.0.0.1 --port 6379
    sleep 1
    if redis-cli ping > /dev/null 2>&1; then
        echo "Redis started successfully"
    else
        echo "Failed to start Redis. Install with: sudo apt-get install redis-server"
        exit 1
    fi
fi

# ─── 3. Ensure .env exists ───
if [ ! -f ".env" ]; then
    echo ""
    echo "Warning: .env file not found!"
    echo "Create one with: echo 'GOOGLE_API_KEY=your-key' > .env"
    echo "Starting anyway..."
fi

# ─── 4. Apply Reflex Polling Patch ───
echo ""
echo "Applying Reflex polling transport patch..."
uv run python patch_reflex_event.py

# ─── 5. Ensure frontend is built ───
echo ""
echo "Checking frontend build..."
if [ ! -d ".web" ] || [ ! -f ".web/env.json" ]; then
    echo "Frontend not found. Running reflex init..."
    uv run reflex init
fi

# Verify the patch worked
if [ -f ".web/env.json" ]; then
    EVENT_URL=$(cat .web/env.json | grep -o '"EVENT": "[^"]*"' | head -1)
    echo "EVENT endpoint: $EVENT_URL"
    if echo "$EVENT_URL" | grep -q "wss://"; then
        echo "WARNING: EVENT URL still uses wss://. The patch may not have applied correctly."
    else
        echo "EVENT URL uses https:// (polling mode)"
    fi
fi

# ─── 6. Start Reflex App (foreground) ───
echo ""
echo "=================================="
echo "Starting Reflex Application..."
echo ""
echo "Frontend:  http://localhost:3001"
echo "Backend:   http://localhost:8002"
echo "Redis:     redis://localhost:6379"
echo ""
if [ "$IS_CODESPACE" = "1" ]; then
    echo "Codespaces URLs:"
    echo "Frontend:  https://${CODESPACE_NAME}-3001.app.github.dev"
    echo "Backend:   https://${CODESPACE_NAME}-8002.app.github.dev"
fi
echo "=================================="
echo ""
echo "Press Ctrl+C to stop the app"
echo ""

uv run reflex run "$@"
