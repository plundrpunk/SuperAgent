#!/bin/bash
# SuperAgent - Kaya Standalone Runner
# Simple script to run Kaya without Docker

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 SuperAgent - Kaya Runner${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "agent_system/cli.py" ]; then
    echo -e "${RED}❌ Error: Must run from SuperAgent root directory${NC}"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    echo "Create .env file with:"
    echo "  ANTHROPIC_API_KEY=your-key-here"
    exit 1
fi

# Check if venv exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found, creating...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import anthropic" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Installing dependencies...${NC}"
    pip install -q -e .
fi

# Check if Redis is running (optional)
if ! redis-cli ping &>/dev/null; then
    echo -e "${YELLOW}⚠️  Redis not running (optional for basic usage)${NC}"
fi

# Set up environment
export PYTHONPATH=$PWD
export REDIS_HOST=localhost

# Parse command - if no args, show usage
if [ $# -eq 0 ]; then
    echo -e "${YELLOW}Usage:${NC}"
    echo "  ./run_kaya.sh status"
    echo "  ./run_kaya.sh \"fix all test failures\""
    echo "  ./run_kaya.sh \"write a test for user login\""
    echo "  ./run_kaya.sh \"execute the mission\""
    echo ""
    echo -e "${GREEN}Available commands:${NC}"
    python agent_system/cli.py --help
    exit 0
fi

# Run Kaya with all arguments
echo -e "${GREEN}🤖 Running Kaya...${NC}"
echo ""

python agent_system/cli.py kaya "$@"

echo ""
echo -e "${GREEN}✅ Done!${NC}"
