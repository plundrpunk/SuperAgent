#!/bin/bash

# HITL Dashboard Startup Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "HITL Dashboard Startup"
echo "=========================================="
echo ""

# Check for .env file
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "Warning: .env file not found at $PROJECT_ROOT/.env"
    echo "Using .env.example as template..."
    if [ -f "$PROJECT_ROOT/.env.example" ]; then
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
        echo "Created .env file. Please configure Redis settings."
    fi
fi

# Check if Redis is running
echo "Checking Redis connection..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "Error: Redis is not running or not accessible"
    echo "Please start Redis with: redis-server"
    exit 1
fi
echo "✓ Redis is running"
echo ""

# Check Python dependencies
echo "Checking Python dependencies..."
if ! python -c "import flask" 2>/dev/null; then
    echo "Installing required Python packages..."
    pip install -r "$SCRIPT_DIR/requirements.txt"
fi
echo "✓ Dependencies installed"
echo ""

# Start the server
echo "Starting HITL Dashboard server..."
echo ""
cd "$SCRIPT_DIR"
python server.py
