#!/bin/bash
# Build Complete Cloppy AI Test Suite - Autonomous Overnight Build
# This uses the new autonomous build_feature workflow that:
# 1. Creates Archon project
# 2. Breaks feature into tasks
# 3. Executes ALL tasks with Scribe → Runner → Medic loop
# 4. Auto-fixes failures up to 3 attempts per test
# 5. Reports comprehensive completion status

set -e

echo "🌙 OVERNIGHT BUILD: Complete Cloppy AI Test Suite"
echo "=================================================="
echo ""
echo "This will autonomously build ALL VisionFlow tests with:"
echo "  • Scribe generates test (Sonnet 4.5)"
echo "  • Runner validates execution"
echo "  • Medic auto-fixes failures (up to 3 attempts)"
echo "  • Archon tracks all task progress"
echo ""
echo "Expected duration: 2-4 hours for complete suite"
echo "Cost estimate: $5-10 total"
echo ""
read -p "Start autonomous build? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

echo ""
echo "🚀 Starting autonomous build..."
echo ""

# Feature 1: Board Management (4 tests)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎨 Building: Board Management Feature"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose -f config/docker-compose.yml exec -T superagent \
  python agent_system/cli.py kaya "build me board management: create board using create-board-btn and board-title-input, edit board name, delete board, verify board persistence across page reload. Use data-testid selectors from visionflow_context.md"

# Feature 2: Node Operations (4 tests)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔷 Building: Node Operations Feature"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose -f config/docker-compose.yml exec -T superagent \
  python agent_system/cli.py kaya "build me node operations: click node-create-btn to add node, edit node content, connect nodes with arrows, delete node, verify node state persistence"

# Feature 3: Export Functionality (3 tests)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📤 Building: Export Feature"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose -f config/docker-compose.yml exec -T superagent \
  python agent_system/cli.py kaya "build me export functionality: click export-pdf-btn and verify PDF download, click export-markdown-btn and verify markdown download, test export with empty board"

# Feature 4: Search & Filters (3 tests)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Building: Search & Filter Feature"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose -f config/docker-compose.yml exec -T superagent \
  python agent_system/cli.py kaya "build me search and filters: enter text in search-input, apply search-filter-type dropdown, apply search-filter-date range, verify search-results accuracy"

# Feature 5: Group Management (4 tests)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Building: Group Management Feature"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose -f config/docker-compose.yml exec -T superagent \
  python agent_system/cli.py kaya "build me group management: click group-create-btn, rename with group-title-input, resize using group-resize-handle, add nodes to group by drag-drop, delete group"

# Feature 6: AI Chat Integration (3 tests)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🤖 Building: AI Chat Feature"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose -f config/docker-compose.yml exec -T superagent \
  python agent_system/cli.py kaya "build me AI chat: enter message in ai-chat-input, click ai-chat-send, verify AI response appears, test chat with grouped nodes context, test chat error handling"

# Feature 7: Media Upload (3 tests)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🖼️  Building: Media Upload Feature"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose -f config/docker-compose.yml exec -T superagent \
  python agent_system/cli.py kaya "build me media upload: upload image file to node, upload video file to node, verify media preview renders, test invalid file format handling"

# Feature 8: Canvas Navigation (3 tests)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🗺️  Building: Canvas Navigation Feature"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose -f config/docker-compose.yml exec -T superagent \
  python agent_system/cli.py kaya "build me canvas navigation: pan canvas by dragging board-canvas, zoom in/out with mouse wheel, reset view to center, verify performance with 100+ nodes"

# Feature 9: Real-time Collaboration (3 tests)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "👥 Building: Collaboration Feature"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose -f config/docker-compose.yml exec -T superagent \
  python agent_system/cli.py kaya "build me real-time collaboration: verify cursor tracking for other users, verify live node updates appear instantly, test conflict resolution when two users edit same node"

# Feature 10: RAG Training (3 tests)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧠 Building: RAG Training Feature"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose -f config/docker-compose.yml exec -T superagent \
  python agent_system/cli.py kaya "build me RAG training: upload document for training, verify vector embeddings created, test semantic search finds relevant content, verify training on large document sets"

# Feature 11: Authentication & Users (4 tests)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔐 Building: Authentication Feature"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose -f config/docker-compose.yml exec -T superagent \
  python agent_system/cli.py kaya "build me authentication: user login with email/password, user registration flow, password reset flow, OAuth social login"

# Feature 12: Billing & Pricing (3 tests)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💳 Building: Billing Feature"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose -f config/docker-compose.yml exec -T superagent \
  python agent_system/cli.py kaya "build me billing: view pricing plans, upgrade to paid plan with payment, view usage metrics, test payment failure handling"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ AUTONOMOUS BUILD COMPLETE!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Summary of test generation:"
echo "  • Board Management: 4 tests"
echo "  • Node Operations: 4 tests"
echo "  • Export: 3 tests"
echo "  • Search & Filters: 3 tests"
echo "  • Group Management: 4 tests"
echo "  • AI Chat: 3 tests"
echo "  • Media Upload: 3 tests"
echo "  • Canvas Navigation: 3 tests"
echo "  • Collaboration: 3 tests"
echo "  • RAG Training: 3 tests"
echo "  • Authentication: 4 tests"
echo "  • Billing: 3 tests"
echo ""
echo "Total: 40 comprehensive tests with auto-validation and fixing"
echo ""
echo "Check logs for:"
echo "  ✅ Completed tasks"
echo "  ❌ Failed tasks (marked for review)"
echo "  🏥 Medic fix attempts"
echo ""
echo "All tests saved in: tests/"
echo ""
