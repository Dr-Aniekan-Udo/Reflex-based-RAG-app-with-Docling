#!/bin/bash
# Start Celery worker for document processing

echo "=== Starting RAG Document Worker ==="
echo "Redis: redis://localhost:6379/0"
echo ""

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️  Redis is not running. Starting it now..."
    redis-server --daemonize yes --bind 127.0.0.1 --port 6379
    sleep 1
fi

# Check Redis connection
if redis-cli ping | grep -q "PONG"; then
    echo "✅ Redis is ready"
else
    echo "❌ Failed to connect to Redis"
    exit 1
fi

echo ""
echo "Starting Celery worker..."
echo "  Pool: prefork"
echo "  Max tasks per child: 1 (memory isolation)"
echo "  Log level: info"
echo ""

# Use uv run to ensure we're in the virtualenv
uv run celery -A RAG_app.core.celery_app worker \
    --loglevel=info \
    --pool=prefork \
    --max-tasks-per-child=1 \
    --hostname=rag-worker@%h \
    --queues=celery \
    --events
