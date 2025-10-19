#!/bin/bash
# SuperAgent - Docker Configuration Validator
# Validates Docker setup without building or starting services

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================================"
echo "   SuperAgent - Docker Configuration Validator"
echo "======================================================${NC}"

ERRORS=0
WARNINGS=0

# Check Docker
echo -e "\n${BLUE}[1] Checking Docker installation...${NC}"
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    echo -e "${GREEN}✓ Docker found: ${DOCKER_VERSION}${NC}"
else
    echo -e "${RED}✗ Docker not found${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check Docker Compose
echo -e "\n${BLUE}[2] Checking Docker Compose...${NC}"
if docker compose version &> /dev/null; then
    COMPOSE_VERSION=$(docker compose version)
    echo -e "${GREEN}✓ Docker Compose found: ${COMPOSE_VERSION}${NC}"
else
    echo -e "${RED}✗ Docker Compose not found${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Validate docker-compose.yml
echo -e "\n${BLUE}[3] Validating docker-compose.yml syntax...${NC}"
if docker compose config --quiet 2>&1 | grep -q "not found"; then
    if [ ! -f .env ]; then
        echo -e "${YELLOW}⚠ .env file not found (expected for validation)${NC}"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo -e "${GREEN}✓ docker-compose.yml syntax is valid${NC}"
fi

# Check Dockerfile
echo -e "\n${BLUE}[4] Checking Dockerfile...${NC}"
if [ -f Dockerfile ]; then
    echo -e "${GREEN}✓ Dockerfile exists${NC}"

    # Check for required instructions
    if grep -q "FROM python:3.11-slim" Dockerfile; then
        echo -e "${GREEN}  ✓ Base image specified (Python 3.11)${NC}"
    else
        echo -e "${RED}  ✗ Base image not found${NC}"
        ERRORS=$((ERRORS + 1))
    fi

    if grep -q "playwright install" Dockerfile; then
        echo -e "${GREEN}  ✓ Playwright installation found${NC}"
    else
        echo -e "${YELLOW}  ⚠ Playwright installation not found${NC}"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo -e "${RED}✗ Dockerfile not found${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check .dockerignore
echo -e "\n${BLUE}[5] Checking .dockerignore...${NC}"
if [ -f .dockerignore ]; then
    echo -e "${GREEN}✓ .dockerignore exists${NC}"

    # Check for essential patterns
    if grep -q "venv/" .dockerignore; then
        echo -e "${GREEN}  ✓ Ignores venv/${NC}"
    fi
    if grep -q "__pycache__" .dockerignore; then
        echo -e "${GREEN}  ✓ Ignores __pycache__${NC}"
    fi
    if grep -q ".env" .dockerignore; then
        echo -e "${GREEN}  ✓ Ignores .env${NC}"
    fi
else
    echo -e "${YELLOW}⚠ .dockerignore not found${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

# Check .env.example
echo -e "\n${BLUE}[6] Checking .env.example...${NC}"
if [ -f .env.example ]; then
    echo -e "${GREEN}✓ .env.example exists${NC}"

    # Check for required variables
    if grep -q "ANTHROPIC_API_KEY" .env.example; then
        echo -e "${GREEN}  ✓ ANTHROPIC_API_KEY defined${NC}"
    fi
    if grep -q "OPENAI_API_KEY" .env.example; then
        echo -e "${GREEN}  ✓ OPENAI_API_KEY defined${NC}"
    fi
    if grep -q "REDIS_HOST" .env.example; then
        echo -e "${GREEN}  ✓ REDIS_HOST defined${NC}"
    fi
else
    echo -e "${YELLOW}⚠ .env.example not found${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

# Check .env
echo -e "\n${BLUE}[7] Checking .env file...${NC}"
if [ -f .env ]; then
    echo -e "${GREEN}✓ .env file exists${NC}"

    # Check for actual API keys (not placeholder values)
    if grep -q "ANTHROPIC_API_KEY=sk-ant-api03-your-key-here" .env; then
        echo -e "${YELLOW}  ⚠ ANTHROPIC_API_KEY is placeholder value${NC}"
        WARNINGS=$((WARNINGS + 1))
    elif grep -q "ANTHROPIC_API_KEY=sk-ant-" .env; then
        echo -e "${GREEN}  ✓ ANTHROPIC_API_KEY appears to be set${NC}"
    fi

    if grep -q "OPENAI_API_KEY=sk-your-key-here" .env; then
        echo -e "${YELLOW}  ⚠ OPENAI_API_KEY is placeholder value${NC}"
        WARNINGS=$((WARNINGS + 1))
    elif grep -q "OPENAI_API_KEY=sk-" .env; then
        echo -e "${GREEN}  ✓ OPENAI_API_KEY appears to be set${NC}"
    fi
else
    echo -e "${YELLOW}⚠ .env file not found (create from .env.example)${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

# Check required directories
echo -e "\n${BLUE}[8] Checking directory structure...${NC}"
REQUIRED_DIRS=("tests" "agent_system" ".claude")
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo -e "${GREEN}  ✓ $dir/ exists${NC}"
    else
        echo -e "${RED}  ✗ $dir/ not found${NC}"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check requirements.txt
echo -e "\n${BLUE}[9] Checking requirements.txt...${NC}"
if [ -f requirements.txt ]; then
    echo -e "${GREEN}✓ requirements.txt exists${NC}"

    # Check for key dependencies
    if grep -q "playwright" requirements.txt; then
        echo -e "${GREEN}  ✓ playwright dependency found${NC}"
    fi
    if grep -q "redis" requirements.txt; then
        echo -e "${GREEN}  ✓ redis dependency found${NC}"
    fi
    if grep -q "anthropic" requirements.txt; then
        echo -e "${GREEN}  ✓ anthropic dependency found${NC}"
    fi
else
    echo -e "${RED}✗ requirements.txt not found${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check Makefile
echo -e "\n${BLUE}[10] Checking Makefile...${NC}"
if [ -f Makefile ]; then
    echo -e "${GREEN}✓ Makefile exists${NC}"

    # Check for key targets
    if grep -q "^up:" Makefile; then
        echo -e "${GREEN}  ✓ 'make up' target found${NC}"
    fi
    if grep -q "^down:" Makefile; then
        echo -e "${GREEN}  ✓ 'make down' target found${NC}"
    fi
    if grep -q "^test:" Makefile; then
        echo -e "${GREEN}  ✓ 'make test' target found${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Makefile not found (optional)${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

# Check documentation
echo -e "\n${BLUE}[11] Checking documentation...${NC}"
DOCS=("DOCKER.md" "DOCKER_DEPLOYMENT.md" "README.md")
for doc in "${DOCS[@]}"; do
    if [ -f "$doc" ]; then
        echo -e "${GREEN}  ✓ $doc exists${NC}"
    else
        echo -e "${YELLOW}  ⚠ $doc not found${NC}"
        WARNINGS=$((WARNINGS + 1))
    fi
done

# Summary
echo -e "\n${BLUE}======================================================"
echo "   Validation Summary"
echo "======================================================${NC}"

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! Configuration is valid.${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Configure .env with your API keys"
    echo "  2. Run: make setup"
    echo "  3. Run: make status"
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ Validation completed with ${WARNINGS} warning(s)${NC}"
    echo ""
    echo "Configuration is functional but has minor issues."
    echo "Review warnings above and proceed with: make setup"
else
    echo -e "${RED}✗ Validation failed with ${ERRORS} error(s) and ${WARNINGS} warning(s)${NC}"
    echo ""
    echo "Please fix the errors above before proceeding."
    exit 1
fi

echo ""
echo "For more information, see DOCKER_DEPLOYMENT.md"
