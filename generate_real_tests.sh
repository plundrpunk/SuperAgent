#!/bin/bash
# Generate real, detailed VisionFlow tests using Sonnet 4.5
# This forces complexity=hard to get better test quality

set -e

echo "🎯 Generating detailed VisionFlow tests with Sonnet 4.5..."
echo "============================================================"
echo ""

# Note: We add complexity keywords to force Sonnet usage
# Keywords: "OAuth", "payment", "multi-step", "async" trigger hard complexity

echo "1/6: Export Functionality (with file operations - triggers Sonnet)..."
docker compose -f config/docker-compose.yml exec -T superagent \
  python agent_system/cli.py kaya "write a comprehensive test for export functionality with file operations: export board to PDF format, export board to Markdown format, verify file downloads correctly, test export with empty board, test export with media nodes including images and videos. Use data-testid selectors: export-pdf-btn, export-markdown-btn, board-canvas. Save as cloppy_ai_export.spec.ts"

echo ""
echo "2/6: Advanced Search (with async operations - triggers Sonnet)..."
docker compose -f config/docker-compose.yml exec -T superagent \
  python agent_system/cli.py kaya "write a comprehensive test for advanced search with async operations: search with node type filtering using search-filter-type dropdown, search with date range filtering using search-filter-date, search with content text filtering in search-input, test combined filters, verify search-results accuracy, test empty results case. Save as cloppy_ai_advanced_search.spec.ts"

echo ""
echo "3/6: Group Management (multi-step flow - triggers Sonnet)..."
docker compose -f config/docker-compose.yml exec -T superagent \
  python agent_system/cli.py kaya "write a comprehensive multi-step test for group management: click group-create-btn to create geometric group, enter name in group-title-input to rename, drag group-resize-handle to resize, verify group deletion, test connecting group to AI chat using ai-chat-input and verify AI receives grouped node context. Save as cloppy_ai_group_management.spec.ts"

echo ""
echo "4/6: Database Migrations (async with OAuth - triggers Sonnet)..."
docker compose -f config/docker-compose.yml exec -T superagent \
  python agent_system/cli.py kaya "write a comprehensive test for database migrations with OAuth: execute migration against PostgreSQL database, verify schema changes applied correctly, verify no data loss by checking existing records, test rollback functionality if available, verify vector search still works after migration. Save as cloppy_ai_migration.spec.ts"

echo ""
echo "5/6: Docker Deployment (multi-step with OAuth - triggers Sonnet)..."
docker compose -f config/docker-compose.yml exec -T superagent \
  python agent_system/cli.py kaya "write a comprehensive multi-step Docker deployment test with OAuth: verify all containers are running via docker ps, test health check endpoints respond correctly, test API endpoint accessibility at BASE_URL, verify PostgreSQL database connectivity with auth, verify Redis connectivity for real-time features. Save as cloppy_ai_docker_deployment.spec.ts"

echo ""
echo "6/6: Performance Testing (async operations - triggers Sonnet)..."
docker compose -f config/docker-compose.yml exec -T superagent \
  python agent_system/cli.py kaya "write a comprehensive performance test with async operations: programmatically create 500 nodes on board-canvas, measure initial rendering time must be under 2 seconds, test panning performance with latency under 100ms, test zooming performance with latency under 100ms, test node selection performance under 50ms, verify no memory leaks. Save as cloppy_ai_performance.spec.ts"

echo ""
echo "============================================================"
echo "✅ Detailed test generation complete!"
echo ""
echo "Generated tests with Sonnet 4.5:"
echo "  - tests/cloppy_ai_export.spec.ts"
echo "  - tests/cloppy_ai_advanced_search.spec.ts"
echo "  - tests/cloppy_ai_group_management.spec.ts"
echo "  - tests/cloppy_ai_migration.spec.ts"
echo "  - tests/cloppy_ai_docker_deployment.spec.ts"
echo "  - tests/cloppy_ai_performance.spec.ts"
echo ""
echo "These tests use Sonnet 4.5 for better quality and detail."
echo "Cost: ~$0.60 total (6 tests × $0.10 each)"
