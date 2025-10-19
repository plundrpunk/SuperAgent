#!/bin/bash
set -e

echo "🚀 Starting SuperAgent System"
echo "=============================="
echo ""

# Navigate to project directory
cd /Users/rutledge/Documents/DevFolder/SuperAgent

# Activate venv
source venv/bin/activate

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Kill any existing processes
echo "🧹 Cleaning up existing processes..."
lsof -ti:8080 | xargs kill -9 2>/dev/null || true
lsof -ti:3010 | xargs kill -9 2>/dev/null || true
pkill -f "text_chat.js" 2>/dev/null || true
pkill -f "voice_chat.js" 2>/dev/null || true
pkill -f "dashboard_server.py" 2>/dev/null || true
sleep 1

echo ""
echo "✅ Cleanup complete"
echo ""

# Start HTTP dashboard server
echo -e "${BLUE}📊 Starting Dashboard Server...${NC}"
python3 dashboard_server.py &
DASHBOARD_PID=$!
sleep 2

# Start WebSocket event stream
echo -e "${BLUE}🌐 Starting WebSocket Event Stream...${NC}"
cd /Users/rutledge/Documents/DevFolder/SuperAgent
PYTHONPATH=/Users/rutledge/Documents/DevFolder/SuperAgent venv/bin/python start_event_stream.py &
WEBSOCKET_PID=$!
sleep 3

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           SuperAgent is Ready!                                ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}📊 Dashboard:${NC}    http://localhost:8080"
echo -e "${YELLOW}🌐 WebSocket:${NC}    ws://localhost:3010/agent-events"
echo ""
echo -e "${YELLOW}Process IDs:${NC}"
echo "   Dashboard Server: $DASHBOARD_PID"
echo "   WebSocket Server: $WEBSOCKET_PID"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  HOW TO USE KAYA${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Option 1: Text Chat (Recommended for Testing)${NC}"
echo "   cd agent_system/voice"
echo "   REDIS_HOST=localhost node dist/text_chat.js"
echo ""
echo -e "${YELLOW}Option 2: Direct CLI${NC}"
echo "   python agent_system/cli.py kaya \"write a test for board creation\""
echo "   python agent_system/cli.py kaya \"check test coverage\""
echo ""
echo -e "${YELLOW}Option 3: Voice Chat (Requires Microphone)${NC}"
echo "   cd agent_system/voice"
echo "   REDIS_HOST=localhost node dist/voice_chat.js"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  EXAMPLE COMMANDS${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  • \"write a test for Cloppy AI authentication\""
echo "  • \"check test coverage\""
echo "  • \"run tests/auth.spec.ts\""
echo "  • \"validate tests/board.spec.ts\""
echo "  • \"what's the status?\""
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Wait for interrupt
trap "echo '\n\n👋 Shutting down SuperAgent...\n'; kill $DASHBOARD_PID $WEBSOCKET_PID 2>/dev/null; exit 0" INT TERM

# Keep script running
wait
