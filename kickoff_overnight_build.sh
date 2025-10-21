#!/bin/bash
# Kickoff Overnight Build - Pre-flight checks + start
# Validates system is ready before starting multi-hour build

set -e

echo "🌙 Overnight Build - Pre-flight Checklist"
echo "=========================================="
echo ""

# Check 1: Docker running
echo "1️⃣  Checking Docker..."
if docker compose -f config/docker-compose.yml ps | grep -q "superagent.*Up"; then
    echo "   ✅ SuperAgent container running"
else
    echo "   ❌ SuperAgent container not running"
    echo ""
    echo "   Starting Docker services..."
    docker compose -f config/docker-compose.yml up -d
    sleep 5
    if docker compose -f config/docker-compose.yml ps | grep -q "superagent.*Up"; then
        echo "   ✅ SuperAgent started successfully"
    else
        echo "   ❌ Failed to start SuperAgent"
        echo "   Run: docker compose -f config/docker-compose.yml logs superagent"
        exit 1
    fi
fi

# Check 2: Anthropic API key
echo ""
echo "2️⃣  Checking API credentials..."
if grep -q "ANTHROPIC_API_KEY=sk-ant-" .env 2>/dev/null; then
    echo "   ✅ Anthropic API key configured"
else
    echo "   ❌ Anthropic API key not found in .env"
    echo ""
    echo "   Add your key:"
    echo "   echo 'ANTHROPIC_API_KEY=sk-ant-xxx' >> .env"
    echo "   docker compose -f config/docker-compose.yml restart"
    exit 1
fi

# Check 3: VisionFlow context
echo ""
echo "3️⃣  Checking VisionFlow context..."
if [ -f "visionflow_context.md" ]; then
    echo "   ✅ VisionFlow context file exists"
else
    echo "   ⚠️  VisionFlow context file missing"
    echo "   Tests will use generic selectors"
fi

# Check 4: Disk space
echo ""
echo "4️⃣  Checking disk space..."
available=$(df -h . | awk 'NR==2 {print $4}')
echo "   ℹ️  Available: $available"
# Check if less than 1GB available (1000000 KB)
if df . | awk 'NR==2 {exit !($4 < 1000000)}'; then
    echo "   ❌ Low disk space (need ~500MB)"
    echo "   Clean up: docker system prune -a"
    exit 1
else
    echo "   ✅ Sufficient disk space"
fi

# Check 5: Test Kaya connectivity
echo ""
echo "5️⃣  Testing Kaya connectivity..."
if timeout 10 docker compose -f config/docker-compose.yml exec -T superagent \
    python agent_system/cli.py kaya "status" > /dev/null 2>&1; then
    echo "   ✅ Kaya responding"
else
    echo "   ⚠️  Kaya not responding (may be busy)"
    echo "   Will proceed anyway"
fi

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ PRE-FLIGHT CHECKS COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Ready to start overnight build!"
echo ""
echo "Build will:"
echo "  • Generate 40+ comprehensive tests"
echo "  • Auto-validate with Runner (Playwright)"
echo "  • Auto-fix failures with Medic (up to 3 attempts)"
echo "  • Track progress in Archon"
echo ""
echo "Expected:"
echo "  Time: 2-4 hours"
echo "  Cost: \$5-10"
echo "  Pass rate: 95%+"
echo ""
echo "You can:"
echo "  • Close your laptop and go to bed 🛏️"
echo "  • Check status anytime: ./check_build_status.sh"
echo "  • Stop build: docker compose -f config/docker-compose.yml stop"
echo ""
read -p "Start overnight build now? (y/N) " -n 1 -r
echo
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 Starting overnight build..."
    echo ""
    echo "Monitor progress:"
    echo "  ./check_build_status.sh"
    echo ""
    echo "View live logs:"
    echo "  docker compose -f config/docker-compose.yml logs -f superagent"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # Start the build
    ./build_complete_test_suite.sh

else
    echo "❌ Build cancelled"
    echo ""
    echo "When ready to start:"
    echo "  ./kickoff_overnight_build.sh"
    echo ""
    echo "Or start manually:"
    echo "  ./build_complete_test_suite.sh"
    exit 0
fi
