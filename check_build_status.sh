#!/bin/bash
# Check Autonomous Build Status
# Shows current build progress, completed tasks, and any failures

echo "🔍 Autonomous Build Status Check"
echo "=================================="
echo ""

# Check if Docker is running
if ! docker compose -f config/docker-compose.yml ps | grep -q "superagent"; then
    echo "❌ SuperAgent container not running"
    echo ""
    echo "Start with:"
    echo "  docker compose -f config/docker-compose.yml up -d"
    exit 1
fi

echo "✅ SuperAgent container: Running"
echo ""

# Show recent logs with task progress
echo "📊 Recent Activity (last 50 lines):"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose -f config/docker-compose.yml logs --tail=50 superagent | \
  grep -E "🏗️|📋|📝|✅|❌|🏥|🚀|Task|Building|Scribe|Runner|Medic|completed|failed" | \
  tail -20

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Count generated tests
test_count=$(find tests -name "*.spec.ts" -type f | wc -l | tr -d ' ')
echo "📁 Generated Tests: $test_count files in tests/"
echo ""

# Show most recent test files
echo "🆕 Most Recent Tests (last 5):"
find tests -name "*.spec.ts" -type f -print0 | \
  xargs -0 ls -lt | head -5 | \
  awk '{print "  •", $9, "(" $6, $7, $8 ")"}'

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Commands:"
echo "  Full logs:    docker compose -f config/docker-compose.yml logs -f superagent"
echo "  Stop build:   docker compose -f config/docker-compose.yml stop"
echo "  View tests:   ls -lh tests/*.spec.ts"
echo ""
