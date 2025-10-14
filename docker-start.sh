#!/bin/bash
# SuperAgent - Docker Quick Start Script
# This script sets up and starts SuperAgent with Docker Compose

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Banner
echo -e "${BLUE}"
echo "======================================================"
echo "   SuperAgent - Docker Quick Start"
echo "   Voice-Controlled Multi-Agent Testing System"
echo "======================================================"
echo -e "${NC}"

# Check prerequisites
echo -e "${BLUE}[1/5] Checking prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed.${NC}"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not available.${NC}"
    echo "Please install Docker Compose v2: https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}✓ Docker and Docker Compose are installed${NC}"

# Check if .env file exists
echo -e "\n${BLUE}[2/5] Checking environment configuration...${NC}"

if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo "Creating .env from .env.example..."

    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${GREEN}✓ Created .env file${NC}"
        echo -e "${YELLOW}⚠ Please edit .env and add your API keys:${NC}"
        echo "  - ANTHROPIC_API_KEY"
        echo "  - OPENAI_API_KEY"
        echo "  - GEMINI_API_KEY"
        echo ""
        read -p "Press Enter to continue after updating .env, or Ctrl+C to exit..."
    else
        echo -e "${RED}Error: .env.example not found${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ .env file exists${NC}"
fi

# Create necessary directories
echo -e "\n${BLUE}[3/5] Creating directories...${NC}"

mkdir -p tests/artifacts
mkdir -p logs
mkdir -p test-results
mkdir -p playwright-report
mkdir -p backups

chmod -R 755 tests logs test-results playwright-report backups

echo -e "${GREEN}✓ Directories created${NC}"

# Build Docker images
echo -e "\n${BLUE}[4/5] Building Docker images...${NC}"
echo "This may take 5-10 minutes on first run..."

if docker compose build; then
    echo -e "${GREEN}✓ Docker images built successfully${NC}"
else
    echo -e "${RED}Error: Failed to build Docker images${NC}"
    exit 1
fi

# Start services
echo -e "\n${BLUE}[5/5] Starting services...${NC}"

if docker compose up -d; then
    echo -e "${GREEN}✓ Services started successfully${NC}"
else
    echo -e "${RED}Error: Failed to start services${NC}"
    exit 1
fi

# Wait for services to be healthy
echo -e "\n${BLUE}Waiting for services to be healthy...${NC}"
echo "This may take 30-60 seconds..."

# Wait for Redis to be healthy
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Redis is healthy${NC}"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -n "."
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "\n${RED}Error: Redis failed to become healthy${NC}"
    docker compose logs redis
    exit 1
fi

# Wait for SuperAgent to be healthy
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker compose exec -T superagent python -c "import sys; sys.exit(0)" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ SuperAgent container is ready${NC}"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -n "."
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "\n${RED}Error: SuperAgent failed to become healthy${NC}"
    docker compose logs superagent
    exit 1
fi

# Check service status
echo -e "\n${BLUE}Service Status:${NC}"
docker compose ps

# Verify SuperAgent CLI
echo -e "\n${BLUE}Verifying SuperAgent CLI...${NC}"
if docker compose exec -T superagent python agent_system/cli.py status > /dev/null 2>&1; then
    echo -e "${GREEN}✓ SuperAgent CLI is working${NC}"
else
    echo -e "${YELLOW}⚠ SuperAgent CLI verification failed (might need more time to start)${NC}"
fi

# Verify Redis connectivity from SuperAgent
echo -e "\n${BLUE}Verifying Redis connectivity...${NC}"
if docker compose exec -T superagent python -c "from agent_system.state.redis_client import RedisClient; RedisClient().ping(); print('OK')" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Redis connectivity verified${NC}"
else
    echo -e "${YELLOW}⚠ Redis connectivity check failed${NC}"
fi

# Display usage instructions
echo -e "\n${GREEN}======================================================"
echo "   SuperAgent is running!"
echo "======================================================${NC}"
echo ""
echo "Quick Commands:"
echo ""
echo "  ${BLUE}# View logs${NC}"
echo "  docker compose logs -f"
echo ""
echo "  ${BLUE}# Check system status${NC}"
echo "  docker compose exec superagent python agent_system/cli.py status"
echo ""
echo "  ${BLUE}# Route a task${NC}"
echo "  docker compose exec superagent python agent_system/cli.py route write_test \"Create login test\""
echo ""
echo "  ${BLUE}# Run Kaya orchestrator${NC}"
echo "  docker compose exec superagent python agent_system/cli.py kaya \"create test for checkout\""
echo ""
echo "  ${BLUE}# Interactive shell${NC}"
echo "  docker compose exec superagent /bin/bash"
echo ""
echo "  ${BLUE}# Stop services${NC}"
echo "  docker compose down"
echo ""
echo "  ${BLUE}# View this help again${NC}"
echo "  cat docker-start.sh | grep -A 20 'Quick Commands:'"
echo ""
echo "For more information, see DOCKER_DEPLOYMENT.md"
echo ""
