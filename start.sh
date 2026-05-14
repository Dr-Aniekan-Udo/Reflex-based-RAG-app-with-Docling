#!/bin/bash
# Wrapper script to start Reflex with proper Codespaces configuration

set -e

if [ -n "$CODESPACE_NAME" ]; then
    echo "=== Codespaces Detected ==="
    echo "Codespace: $CODESPACE_NAME"
    
    # Ensure port 8002 is public (GitHub sometimes resets this)
    echo "Ensuring port 8002 is public..."
    gh codespace ports visibility 8002:public || true
    
    echo "Backend URL: https://${CODESPACE_NAME}-8002.app.github.dev"
    echo "Frontend URL: https://${CODESPACE_NAME}-3001.app.github.dev"
    echo ""
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found. Create one with:"
    echo "   echo 'GOOGLE_API_KEY=your-key' > .env"
    echo ""
fi

echo "Starting Reflex..."
uv run reflex run "$@"
