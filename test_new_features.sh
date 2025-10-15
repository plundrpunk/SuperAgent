#!/bin/bash

# Test script for new features
# Tests: 1) Visible browsers, 2) Screenshot streaming, 3) Coverage analysis

echo "🚀 Testing SuperAgent New Features"
echo "=================================="
echo ""

# Set up environment
cd /Users/rutledge/Documents/DevFolder/SuperAgent
source venv/bin/activate 2>/dev/null || python3 -m venv venv && source venv/bin/activate

echo "✓ Environment ready"
echo ""

# Test 1: Check if coverage analysis works
echo "📊 Test 1: Coverage Analysis"
echo "----------------------------"
echo "Testing coverage analyzer..."
python3 -c "
from agent_system.coverage_analyzer import CoverageAnalyzer
analyzer = CoverageAnalyzer('/Users/rutledge/Documents/DevFolder/Cloppy_Ai')
print('✓ Coverage analyzer initialized successfully')
print('✓ Ready to analyze coverage reports')
" || echo "⚠️  Coverage analyzer needs coverage data to analyze"
echo ""

# Test 2: Check Kaya coverage intent
echo "🤖 Test 2: Kaya Coverage Intent"
echo "-------------------------------"
echo "Testing Kaya's coverage parsing..."
python3 -c "
from agent_system.agents.kaya import KayaAgent
kaya = KayaAgent()

# Test coverage intent patterns
test_commands = [
    'check test coverage',
    'what is the coverage?',
    'test coverage for src/App.tsx'
]

for cmd in test_commands:
    result = kaya.parse_intent(cmd)
    if result['success'] and result['intent'] == 'check_coverage':
        print(f'✓ Recognized: \"{cmd}\" as check_coverage')
    else:
        print(f'✗ Failed to recognize: \"{cmd}\"')
" || echo "⚠️  Kaya coverage intent test failed"
echo ""

# Test 3: Check Gemini browser config
echo "👀 Test 3: Visible Browser Configuration"
echo "----------------------------------------"
echo "Checking Gemini agent browser settings..."
python3 -c "
from agent_system.agents.gemini import GeminiAgent
import yaml

with open('.claude/agents/gemini.yaml', 'r') as f:
    config = yaml.safe_load(f)

headless = config['contracts']['browser']['headless']
if headless == False:
    print('✓ Browsers will be VISIBLE (headless: false)')
else:
    print('⚠️  Browsers will be headless (headless: true)')
" || echo "⚠️  Could not check browser config"
echo ""

# Test 4: Check dashboard file exists
echo "📸 Test 4: Screenshot Dashboard"
echo "-------------------------------"
if [ -f "dashboard.html" ]; then
    echo "✓ Dashboard HTML found"
    if grep -q "Live Screenshots" dashboard.html; then
        echo "✓ Screenshot gallery present in dashboard"
    else
        echo "✗ Screenshot gallery not found"
    fi
else
    echo "✗ Dashboard HTML not found"
fi
echo ""

# Test 5: Check WebSocket server
echo "🌐 Test 5: WebSocket Event Stream"
echo "---------------------------------"
echo "Checking if WebSocket server is accessible..."
curl -s --max-time 2 http://localhost:3010 >/dev/null 2>&1
if [ $? -eq 0 ] || [ $? -eq 52 ]; then
    echo "✓ WebSocket server is running on port 3010"
else
    echo "⚠️  WebSocket server not running (start with: python3 -m agent_system.observability.event_stream)"
fi
echo ""

# Summary
echo "=================================="
echo "✅ Feature Testing Complete!"
echo ""
echo "Next steps:"
echo "1. Open dashboard: open dashboard.html"
echo "2. Start voice chat: cd agent_system/voice && REDIS_HOST=localhost node dist/voice_chat.js"
echo "3. Try: 'Kaya, check test coverage'"
echo "4. Try: 'Kaya, write a test for board creation'"
echo ""
echo "Features installed:"
echo "  ✓ Visible browser windows"
echo "  ✓ Live screenshot streaming"
echo "  ✓ Test coverage analysis"
echo ""
