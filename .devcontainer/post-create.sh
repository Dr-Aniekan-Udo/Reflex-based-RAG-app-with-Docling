#!/bin/bash
set -e

echo "=== Setting up Reflex RAG App ==="

# Install Python dependencies
echo "Running uv sync..."
uv sync

# Initialize reflex frontend (this creates the .web directory)
echo "Running reflex init..."
uv run reflex init

echo "=== Setup complete ==="
echo "To start the app, run: uv run reflex run"
echo "Remember to create a .env file with GOOGLE_API_KEY"
