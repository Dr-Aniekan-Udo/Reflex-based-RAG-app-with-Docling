#!/bin/bash
# Unified launcher: Redis + Celery (foreground logs) + Reflex
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

# ─── 6. Start Celery Worker (background, but logs visible) ───
echo ""
echo "Starting Celery worker..."
mkdir -p logs

# Kill any existing worker
if [ -f "logs/celery.pid" ]; then
    OLD_PID=$(cat logs/celery.pid)
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Stopping existing worker (PID: $OLD_PID)..."
        kill "$OLD_PID" || true
        sleep 1
    fi
fi

# Start Celery worker in background, redirect output to log file
uv run celery -A RAG_app.core.celery_app worker \
    --loglevel=info \
    --pool=prefork \
    --max-tasks-per-child=1 \
    --hostname=rag-worker@%h \
    --queues=celery \
    --events \
    --logfile=logs/celery.log \
    --pidfile=logs/celery.pid &

CELERY_PID=$!
sleep 2

if ps -p "$CELERY_PID" > /dev/null 2>&1; then
    echo "Celery worker started (PID: $CELERY_PID)"
else
    echo "ERROR: Celery worker failed to start. Check logs/celery.log"
    exit 1
fi

# Start tailing Celery logs in background so user sees real-time output
echo ""
echo "--- Celery Worker Logs (tail -f logs/celery.log) ---"
tail -f logs/celery.log &
TAIL_PID=$!

# ─── 7. Start Reflex App (foreground) ───
echo ""
echo "=================================="
echo "Starting Reflex Application..."
echo ""
echo "Frontend:  http://localhost:3001"
echo "Backend:   http://localhost:8002"
echo "Redis:     redis://localhost:6379"
echo "Celery:    logs/celery.log (live output below)"
echo ""
if [ "$IS_CODESPACE" = "1" ]; then
    echo "Codespaces URLs:"
    echo "Frontend:  https://${CODESPACE_NAME}-3001.app.github.dev"
    echo "Backend:   https://${CODESPACE_NAME}-8002.app.github.dev"
fi
echo "=================================="
echo ""
echo "Press Ctrl+C to stop the app (Celery will also stop)"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    
    # Stop the tail process
    if ps -p "$TAIL_PID" > /dev/null 2>&1; then
        kill "$TAIL_PID" 2>/dev/null || true
    fi
    
    # Stop Celery worker
    if [ -f "logs/celery.pid" ]; then
        WORKER_PID=$(cat logs/celery.pid)
        if ps -p "$WORKER_PID" > /dev/null 2>&1; then
            echo "Stopping Celery worker (PID: $WORKER_PID)..."
            kill "$WORKER_PID" 2>/dev/null || true
        fi
    fi
    
    # Also kill by PID if file missing
    if ps -p "$CELERY_PID" > /dev/null 2>&1; then
        kill "$CELERY_PID" 2>/dev/null || true
    fi
    
    echo "Shutdown complete."
    exit 0
}

# Set trap to cleanup on Ctrl+C or script exit
trap cleanup INT TERM EXIT

# Start Reflex (this blocks)
uv run reflex run "$@"
