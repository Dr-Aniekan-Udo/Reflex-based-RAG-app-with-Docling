#!/bin/bash
set -e

echo "=== Setting up Reflex RAG App ==="

# Detect Codespaces and set API URL if needed
if [ -n "$CODESPACE_NAME" ]; then
    echo "Detected GitHub Codespaces environment"
    
    # Make backend port public so frontend WebSocket can connect
    echo "Making port 8002 public..."
    gh codespace ports visibility 8002:public -c "$CODESPACE_NAME" || true
    
    export CODESPACE_BACKEND_URL="https://${CODESPACE_NAME}-8002.app.github.dev"
    echo "Backend will be available at: $CODESPACE_BACKEND_URL"
fi

# Start Redis server in background
echo "Starting Redis server..."
redis-server --daemonize yes --bind 127.0.0.1 --port 6379

echo "Redis is running on port 6379"

# Install Python dependencies
echo "Running uv sync..."
uv sync

# Initialize reflex frontend
echo "Running reflex init..."
uv run reflex init

echo "=== Setup complete ==="
echo ""
echo "To start the app:"
echo "  Terminal 1: uv run reflex run"
echo "  Terminal 2: bash start_worker.sh"
echo ""
echo "Remember to create a .env file with GOOGLE_API_KEY"
