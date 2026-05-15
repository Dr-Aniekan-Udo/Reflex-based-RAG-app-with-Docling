#!/bin/bash
# Unified launcher: Redis + Reflex + Celery Worker
# Usage: bash start.sh

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║         RAG App - Unified Launcher                         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# ─── 1. Environment Check ───
if [ -n "$CODESPACE_NAME" ]; then
    echo "📦 GitHub Codespaces detected: $CODESPACE_NAME"
    IS_CODESPACE=1
else
    echo "💻 Local development mode"
    IS_CODESPACE=0
fi

# ─── 2. Start Redis ───
echo ""
echo "🔍 Checking Redis..."
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is already running"
else
    echo "🚀 Starting Redis server..."
    redis-server --daemonize yes --bind 127.0.0.1 --port 6379
    sleep 1
    if redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis started successfully"
    else
        echo "❌ Failed to start Redis. Install with: sudo apt-get install redis-server"
        exit 1
    fi
fi

# ─── 3. Codespaces Port Configuration ───
if [ "$IS_CODESPACE" = "1" ]; then
    echo ""
    echo "🌐 Configuring Codespaces ports..."
    gh codespace ports visibility 8002:public -c "$CODESPACE_NAME" || true
    gh codespace ports visibility 3001:public -c "$CODESPACE_NAME" || true
    echo "✅ Ports configured"
fi

# ─── 4. Ensure .env exists ───
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  .env file not found!"
    echo "   Create one with: echo 'GOOGLE_API_KEY=your-key' > .env"
    echo "   Starting anyway..."
fi

# ─── 5. Ensure frontend is built with polling transport ───
echo ""
echo "📁 Checking frontend build..."
if [ ! -d ".web" ] || [ ! -f ".web/env.json" ]; then
    echo "   Frontend not found. Running reflex init..."
    uv run reflex init
fi

# Force polling transport in env.json (Codespaces WebSocket proxy issues)
BACKEND_URL="http://localhost:8002"
if [ "$IS_CODESPACE" = "1" ]; then
    BACKEND_URL="https://${CODESPACE_NAME}-8002.app.github.dev"
fi

echo "   Configuring frontend for HTTP polling..."
cat > .web/env.json << EOF
{
  "PING": "${BACKEND_URL}/ping",
  "EVENT": "${BACKEND_URL}/_event",
  "UPLOAD": "${BACKEND_URL}/_upload",
  "AUTH_CODESPACE": "${BACKEND_URL}/auth-codespace",
  "HEALTH": "${BACKEND_URL}/_health",
  "ALL_ROUTES": "${BACKEND_URL}/_all_routes",
  "TRANSPORT": "polling",
  "TEST_MODE": false
}
EOF
echo "   ✅ Frontend configured for polling transport"

# ─── 6. Start Celery Worker (background) ───
echo ""
echo "🧑‍🌾 Starting Celery worker..."
uv run celery -A RAG_app.core.celery_app worker \
    --loglevel=info \
    --pool=prefork \
    --max-tasks-per-child=1 \
    --hostname=rag-worker@%h \
    --queues=celery \
    --events \
    --detach \
    --logfile=logs/celery.log \
    --pidfile=logs/celery.pid

if [ -f "logs/celery.pid" ]; then
    echo "✅ Celery worker started (PID: $(cat logs/celery.pid))"
else
    echo "⚠️  Celery worker may not have started. Check logs/celery.log"
fi

# ─── 7. Start Reflex App (foreground) ───
echo ""
echo "════════════════════════════════════════════════════════════"
echo "🚀 Starting Reflex Application..."
echo ""
echo "   Frontend:  http://localhost:3001"
echo "   Backend:   http://localhost:8002"
echo "   Redis:     redis://localhost:6379"
echo ""
if [ "$IS_CODESPACE" = "1" ]; then
    echo "   Codespaces URLs:"
    echo "   Frontend:  https://${CODESPACE_NAME}-3001.app.github.dev"
    echo "   Backend:   https://${CODESPACE_NAME}-8002.app.github.dev"
fi
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Press Ctrl+C to stop the app (Celery worker runs separately)"
echo ""

uv run reflex run "$@"
