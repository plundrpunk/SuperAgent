#!/bin/bash
# Test Autonomous Loop - Quick validation of Scribe → Runner → Medic workflow
# This tests the full autonomous execution with a simple feature

set -e

echo "🧪 Testing Autonomous Build Loop"
echo "================================"
echo ""
echo "This will test the complete autonomous workflow:"
echo "  1. Kaya creates Archon project"
echo "  2. Breaks feature into tasks"
echo "  3. For each task:"
echo "     • Scribe generates test (Sonnet 4.5)"
echo "     • Runner validates execution"
echo "     • Medic auto-fixes if needed (up to 3 attempts)"
echo "     • Archon updates task status"
echo "  4. Reports completion summary"
echo ""
echo "Test feature: Simple board creation"
echo "Expected: 2-3 tasks, ~2-5 minutes"
echo "Cost: ~$0.30-0.50"
echo ""

docker compose -f config/docker-compose.yml exec -T superagent \
  python agent_system/cli.py kaya "build me a simple test for board creation with create button and title input"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Autonomous loop test complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Check output above for:"
echo "  • Project created"
echo "  • Tasks breakdown"
echo "  • Scribe generation"
echo "  • Runner validation"
echo "  • Medic fixes (if any)"
echo "  • Final completion summary"
echo ""
