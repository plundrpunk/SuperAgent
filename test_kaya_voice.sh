#!/bin/bash
# Quick test - send command to Kaya and check for audio

echo "Testing Kaya voice integration..."
echo ""
echo "Command: write a test for board creation"
echo ""

cd /Users/rutledge/Documents/DevFolder/SuperAgent
REDIS_HOST=localhost PYTHONPATH=/Users/rutledge/Documents/DevFolder/SuperAgent venv/bin/python agent_system/cli.py kaya "write a test for board creation"

echo ""
echo "✅ Kaya executed successfully!"
echo "Check tests/ directory for the generated test file"
