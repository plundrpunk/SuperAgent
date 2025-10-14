# SuperAgent - Troubleshooting Guide

Complete guide for diagnosing and resolving common issues in SuperAgent.

---

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [Redis Connection Issues](#redis-connection-issues)
3. [API Key Errors](#api-key-errors)
4. [Agent Failures](#agent-failures)
5. [Docker Issues](#docker-issues)
6. [Playwright Issues](#playwright-issues)
7. [Performance Problems](#performance-problems)
8. [Network Issues](#network-issues)
9. [Database Issues](#database-issues)
10. [Observability Issues](#observability-issues)

---

## Quick Diagnostics

### System Health Check

Run this comprehensive health check first:

```bash
#!/bin/bash
echo "=== SuperAgent Health Check ==="
echo

# Check Python version
echo "Python version:"
python3 --version || echo "ERROR: Python not found"
echo

# Check Node.js version
echo "Node.js version:"
node --version || echo "ERROR: Node.js not found"
echo

# Check Docker
echo "Docker:"
docker --version || echo "WARNING: Docker not available"
echo

# Check Redis connection
echo "Redis:"
redis-cli ping 2>/dev/null && echo "✓ Connected" || echo "✗ Not connected"
echo

# Check disk space
echo "Disk space:"
df -h . | tail -1
echo

# Check memory
echo "Memory:"
free -h | grep Mem || echo "WARNING: free command not available"
echo

# Check API keys (without revealing them)
echo "API Keys:"
python3 << 'EOF'
import os
keys = {
    'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY'),
    'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
    'GEMINI_API_KEY': os.getenv('GEMINI_API_KEY')
}
for key, value in keys.items():
    if value and len(value) > 10:
        print(f"✓ {key}: Set ({len(value)} chars)")
    else:
        print(f"✗ {key}: Not set")
EOF
echo

# Check Playwright
echo "Playwright:"
npx playwright --version 2>/dev/null && echo "✓ Installed" || echo "✗ Not installed"
echo

# Check services (Docker)
if command -v docker &> /dev/null; then
    echo "Docker Services:"
    docker compose ps 2>/dev/null || echo "No Docker Compose services running"
    echo
fi

# Check services (Systemd)
if command -v systemctl &> /dev/null; then
    echo "Systemd Services:"
    systemctl is-active superagent 2>/dev/null && echo "✓ SuperAgent running" || echo "✗ SuperAgent not running"
    echo
fi

echo "=== Health Check Complete ==="
```

Save as `health_check.sh`, make executable, and run:
```bash
chmod +x health_check.sh
./health_check.sh
```

### Log Analysis

```bash
# View recent errors
tail -100 logs/agent-events.jsonl | grep -i "error\|fail" | jq

# View agent activity
tail -50 logs/agent-events.jsonl | jq 'select(.event_type | contains("agent"))'

# Check for budget issues
grep "budget" logs/agent-events.jsonl | jq

# View HITL escalations
grep "hitl_escalated" logs/agent-events.jsonl | jq
```

---

## Redis Connection Issues

### Problem: "Connection refused" or "Could not connect to Redis"

**Symptoms**:
```
redis.exceptions.ConnectionError: Error connecting to localhost:6379
```

**Diagnosis**:
```bash
# Check if Redis is running
redis-cli ping

# Check Redis process
ps aux | grep redis

# Check Redis port
netstat -tuln | grep 6379
# OR
lsof -i :6379
```

**Solutions**:

#### Solution 1: Start Redis (Local)

**macOS**:
```bash
# Start Redis
brew services start redis

# Verify
redis-cli ping  # Should return "PONG"
```

**Linux**:
```bash
# Start Redis
sudo systemctl start redis
# OR
sudo service redis-server start

# Enable on boot
sudo systemctl enable redis

# Verify
redis-cli ping
```

**Docker**:
```bash
# Start Redis container
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Verify
docker exec redis redis-cli ping
```

#### Solution 2: Check .env Configuration

```bash
# Verify .env settings
cat .env | grep REDIS

# Should show:
# REDIS_HOST=localhost  (or 'redis' for Docker Compose)
# REDIS_PORT=6379
```

If using Docker Compose:
```env
REDIS_HOST=redis  # Container name, not localhost
REDIS_PORT=6379
```

#### Solution 3: Check Firewall

```bash
# Check if firewall is blocking
sudo ufw status | grep 6379

# Allow Redis (if needed for remote connections)
sudo ufw allow 6379/tcp

# Restart firewall
sudo ufw reload
```

### Problem: Authentication failed

**Symptoms**:
```
redis.exceptions.AuthenticationError: Authentication required
```

**Solution**:
```bash
# Set password in .env
echo "REDIS_PASSWORD=your-password" >> .env

# Test connection with password
redis-cli -a your-password ping

# Or use AUTH command
redis-cli
> AUTH your-password
> PING
```

### Problem: Redis memory full

**Symptoms**:
```
redis.exceptions.ResponseError: OOM command not allowed when used memory > 'maxmemory'
```

**Diagnosis**:
```bash
# Check memory usage
redis-cli info memory | grep used_memory_human

# Check maxmemory setting
redis-cli config get maxmemory
```

**Solution**:
```bash
# Increase maxmemory (to 512MB)
redis-cli config set maxmemory 536870912

# Or in redis.conf
echo "maxmemory 512mb" >> /etc/redis/redis.conf
echo "maxmemory-policy allkeys-lru" >> /etc/redis/redis.conf

# Restart Redis
sudo systemctl restart redis
```

### Problem: Redis persistence issues

**Symptoms**:
```
Can't save in background: fork: Cannot allocate memory
```

**Solution**:
```bash
# Disable save (use AOF instead)
redis-cli config set save ""
redis-cli config set appendonly yes

# Or in redis.conf
appendonly yes
appendfsync everysec
```

---

## API Key Errors

### Problem: "Invalid API key" or "Authentication failed"

**Symptoms**:
```
anthropic.AuthenticationError: Invalid API key
openai.AuthenticationError: Incorrect API key provided
google.api_core.exceptions.Unauthenticated: Request had invalid authentication
```

**Diagnosis**:
```bash
# Check if API keys are set
python3 << 'EOF'
import os
keys = ['ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY']
for key in keys:
    value = os.getenv(key)
    if value:
        print(f"✓ {key}: {value[:10]}... ({len(value)} chars)")
    else:
        print(f"✗ {key}: NOT SET")
EOF
```

**Solutions**:

#### Solution 1: Verify API Keys

**Anthropic**:
```bash
# Test Anthropic API key
python3 << 'EOF'
import os
from anthropic import Anthropic

try:
    client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    message = client.messages.create(
        model="claude-haiku-20240307",
        max_tokens=10,
        messages=[{"role": "user", "content": "Hi"}]
    )
    print("✓ Anthropic API key valid")
except Exception as e:
    print(f"✗ Anthropic API key invalid: {e}")
EOF
```

**OpenAI**:
```bash
# Test OpenAI API key
python3 << 'EOF'
import os
from openai import OpenAI

try:
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=10,
        messages=[{"role": "user", "content": "Hi"}]
    )
    print("✓ OpenAI API key valid")
except Exception as e:
    print(f"✗ OpenAI API key invalid: {e}")
EOF
```

**Gemini**:
```bash
# Test Gemini API key
python3 << 'EOF'
import os
import google.generativeai as genai

try:
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel('gemini-2.5-pro')
    response = model.generate_content("Hi", generation_config={"max_output_tokens": 10})
    print("✓ Gemini API key valid")
except Exception as e:
    print(f"✗ Gemini API key invalid: {e}")
EOF
```

#### Solution 2: Update .env File

```bash
# Backup existing .env
cp .env .env.backup

# Update API keys
nano .env

# Keys should look like:
# ANTHROPIC_API_KEY=sk-ant-api03-...
# OPENAI_API_KEY=sk-...
# GEMINI_API_KEY=...

# Reload environment (if using docker-compose)
docker compose down
docker compose up -d
```

#### Solution 3: Check API Key Format

**Common mistakes**:
- Extra spaces: `ANTHROPIC_API_KEY= sk-ant-...` (space after =)
- Quotes: `ANTHROPIC_API_KEY="sk-ant-..."` (unnecessary quotes)
- Newlines: Key split across multiple lines
- Comments: `ANTHROPIC_API_KEY=sk-ant-... # My key` (comment in value)

**Correct format**:
```env
ANTHROPIC_API_KEY=sk-ant-api03-yourkey
OPENAI_API_KEY=sk-yourkey
GEMINI_API_KEY=yourkey
```

### Problem: Rate limit exceeded

**Symptoms**:
```
anthropic.RateLimitError: Rate limit exceeded
openai.RateLimitError: Rate limit reached
```

**Solution**:
```bash
# Check current usage
# Anthropic: https://console.anthropic.com/
# OpenAI: https://platform.openai.com/usage
# Gemini: https://makersuite.google.com/

# Add retry logic in code
# Or reduce concurrent requests
# Or upgrade to higher tier
```

### Problem: Insufficient credits

**Symptoms**:
```
anthropic.PermissionError: Your credit balance is too low
```

**Solution**:
```bash
# Add credits to your account
# Anthropic: https://console.anthropic.com/settings/billing
# OpenAI: https://platform.openai.com/account/billing
# Gemini: Free tier has 60 requests/minute limit
```

---

## Agent Failures

### Problem: Kaya (Router) not routing correctly

**Symptoms**:
- Tasks routed to wrong agent
- Cost estimates incorrect
- Complexity scoring off

**Diagnosis**:
```bash
# Test complexity estimation
python3 << 'EOF'
from agent_system.complexity_estimator import estimate_complexity

tests = [
    "Create simple login test",
    "Create OAuth login with 2FA and session management",
    "Test payment flow with Stripe integration"
]

for desc in tests:
    score = estimate_complexity(desc)
    model = "sonnet" if score >= 5 else "haiku"
    print(f"{desc}: {score} → {model}")
EOF
```

**Solution**:
```bash
# Check router configuration
cat .claude/router_policy.yaml

# Verify complexity thresholds
grep COMPLEXITY_THRESHOLD .env

# Test routing
python agent_system/cli.py route write_test "Create login test" --dry-run
```

### Problem: Scribe (Test Writer) generates invalid tests

**Symptoms**:
- Syntax errors in generated code
- Missing imports
- Invalid selectors
- No assertions

**Diagnosis**:
```bash
# Check generated test
cat tests/latest_test.spec.ts

# Try to compile
npx tsc tests/latest_test.spec.ts --noEmit
```

**Solution**:
```bash
# 1. Check RAG patterns
python3 << 'EOF'
from agent_system.state.vector_client import VectorClient

vector = VectorClient()
patterns = vector.search_similar_tests("login", limit=3)
print(f"Found {len(patterns)} patterns")
for p in patterns:
    print(f"- {p.get('feature')}: {p.get('pattern_type')}")
EOF

# 2. Store successful patterns
python3 << 'EOF'
from agent_system.state.vector_client import VectorClient

vector = VectorClient()
vector.store_test_pattern(
    test_id="example_login",
    feature="login",
    pattern_type="success",
    code="""
import { test, expect } from '@playwright/test';

test('login', async ({ page }) => {
  await page.goto(process.env.BASE_URL!);
  await page.fill('[data-testid="email"]', 'test@example.com');
  await page.fill('[data-testid="password"]', 'password');
  await page.click('[data-testid="login-button"]');
  await expect(page.locator('[data-testid="dashboard"]')).toBeVisible();
});
""",
    metadata={"model": "sonnet", "cost": 0.12}
)
print("✓ Pattern stored")
EOF

# 3. Verify template exists
cat tests/templates/playwright.template.ts
```

### Problem: Runner (Executor) can't find tests

**Symptoms**:
```
Error: Test file not found: tests/auth.spec.ts
```

**Solution**:
```bash
# Check test exists
ls -la tests/*.spec.ts

# Check working directory
pwd

# Use absolute path
python agent_system/cli.py run /Users/rutledge/Documents/DevFolder/SuperAgent/tests/auth.spec.ts
```

### Problem: Critic (Pre-Validator) rejects all tests

**Symptoms**:
- 100% rejection rate
- Valid tests being rejected

**Diagnosis**:
```bash
# Check rejection reasons
grep "critic" logs/agent-events.jsonl | jq '.payload.rejection_reason'

# Test critic manually
python agent_system/cli.py review tests/auth.spec.ts
```

**Solution**:
```bash
# Adjust rejection criteria in critic.py
# Check for:
# - nth() selectors (should reject)
# - CSS class selectors (should reject)
# - waitForTimeout (should reject)
# - Missing expect (should reject)
# - data-testid selectors (should approve)

# Verify test quality
cat tests/auth.spec.ts | grep -E "nth\(|\.css-|waitForTimeout|expect"
```

### Problem: Medic (Bug Fixer) can't fix issues

**Symptoms**:
- Multiple failed fix attempts
- HITL escalation
- Regression test failures

**Diagnosis**:
```bash
# Check fix history
grep "medic" logs/agent-events.jsonl | jq

# View fix attempts
python agent_system/cli.py hitl list
```

**Solution**:
```bash
# 1. Check error clarity
# Errors should be specific, not generic

# 2. Store fix patterns
python3 << 'EOF'
from agent_system.state.vector_client import VectorClient

vector = VectorClient()
vector.store_bug_fix(
    error_signature="selector timeout: [data-testid='submit-button']",
    fix_strategy="wait_for_selector",
    code_diff="""
-await page.click('[data-testid="submit-button"]');
+await page.waitForSelector('[data-testid="submit-button"]', { state: 'visible' });
+await page.click('[data-testid="submit-button"]');
""",
    success_rate=0.95,
    metadata={"error_type": "timeout", "fix_type": "wait"}
)
print("✓ Fix pattern stored")
EOF

# 3. Run regression tests
pytest tests/unit/ -v
```

### Problem: Gemini (Validator) fails to validate

**Symptoms**:
```
BrowserNotLaunchedException: Could not launch browser
TimeoutError: Validation timeout
```

**Solution**:
```bash
# 1. Check Playwright installation
npx playwright install chromium

# 2. Test browser launch
python3 << 'EOF'
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    print("✓ Browser launched")
    browser.close()
EOF

# 3. Check timeout settings
grep PLAYWRIGHT_TIMEOUT .env

# 4. Increase timeout if needed
echo "PLAYWRIGHT_TIMEOUT=60000" >> .env
```

---

## Docker Issues

### Problem: Container won't start

**Symptoms**:
```
Error response from daemon: Container ... is not running
```

**Diagnosis**:
```bash
# Check container status
docker compose ps

# Check logs
docker compose logs superagent

# Check events
docker events --since 1h | grep superagent
```

**Solution**:
```bash
# 1. Rebuild container
docker compose down
docker compose build --no-cache
docker compose up -d

# 2. Check .env file
cat .env | grep -v "^#" | grep -v "^$"

# 3. Check docker-compose.yml
docker compose config

# 4. Check disk space
docker system df
docker system prune -a
```

### Problem: Port already in use

**Symptoms**:
```
Error starting userland proxy: listen tcp 0.0.0.0:8000: bind: address already in use
```

**Diagnosis**:
```bash
# Find process using port
lsof -i :8000
# OR
netstat -tuln | grep 8000
```

**Solution**:
```bash
# Option 1: Kill process
kill -9 $(lsof -ti:8000)

# Option 2: Change port in docker-compose.yml
ports:
  - "8001:8000"  # Host:Container

# Option 3: Stop conflicting container
docker ps | grep 8000
docker stop <container_id>
```

### Problem: Volume mount errors

**Symptoms**:
```
Error: failed to mount local volume: mount ... permission denied
```

**Solution**:
```bash
# Fix permissions
chmod -R 755 tests artifacts logs vector_db

# Or use named volumes instead of bind mounts
# In docker-compose.yml:
volumes:
  - tests_data:/app/tests
  - artifacts_data:/app/artifacts
```

### Problem: Out of disk space

**Symptoms**:
```
no space left on device
```

**Diagnosis**:
```bash
# Check disk usage
df -h

# Check Docker disk usage
docker system df
```

**Solution**:
```bash
# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Remove build cache
docker builder prune

# Full cleanup (careful!)
docker system prune -a --volumes
```

### Problem: Network connectivity between containers

**Symptoms**:
```
redis.exceptions.ConnectionError: Error connecting to redis:6379
```

**Solution**:
```bash
# Check network
docker network ls
docker network inspect superagent-network

# Verify container names
docker compose ps

# Use container name, not localhost
# In .env:
REDIS_HOST=redis  # Not localhost

# Recreate network
docker compose down
docker network prune
docker compose up -d
```

---

## Playwright Issues

### Problem: Browsers not installed

**Symptoms**:
```
browserType.launch: Executable doesn't exist at /root/.cache/ms-playwright/chromium-1097/chrome-linux/chrome
```

**Solution**:
```bash
# Install browsers
npx playwright install

# Install specific browser
npx playwright install chromium

# Install with dependencies (Linux)
npx playwright install --with-deps chromium

# Verify installation
npx playwright --version
ls ~/.cache/ms-playwright/
```

### Problem: Timeout errors

**Symptoms**:
```
TimeoutError: page.goto: Timeout 30000ms exceeded
```

**Solution**:
```bash
# Increase timeout in .env
echo "PLAYWRIGHT_TIMEOUT=60000" >> .env

# Or in test file
test.setTimeout(60000);

# Or per action
await page.goto(url, { timeout: 60000 });
```

### Problem: Selector not found

**Symptoms**:
```
Error: page.click: Timeout 30000ms exceeded waiting for selector "[data-testid='button']"
```

**Diagnosis**:
```bash
# Take screenshot to see page state
python3 << 'EOF'
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto('http://localhost:3000')
    page.screenshot(path='debug.png')
    print("✓ Screenshot saved to debug.png")
    browser.close()
EOF

# Check if element exists
python3 << 'EOF'
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto('http://localhost:3000')
    element = page.query_selector('[data-testid="button"]')
    if element:
        print("✓ Element found")
    else:
        print("✗ Element not found")
        print("Available data-testids:")
        for el in page.query_selector_all('[data-testid]'):
            print(f"  - {el.get_attribute('data-testid')}")
    browser.close()
EOF
```

**Solution**:
```bash
# Wait for element before interacting
await page.waitForSelector('[data-testid="button"]', { state: 'visible' });
await page.click('[data-testid="button"]');

# Use more robust selectors
# Good: [data-testid="submit-button"]
# Bad: .css-1234abc, button:nth-child(3)
```

### Problem: Headless mode issues

**Symptoms**:
- Test passes in headed mode
- Test fails in headless mode

**Solution**:
```bash
# Disable headless for debugging
echo "PLAYWRIGHT_HEADLESS=false" >> .env

# Add slowMo for debugging
const browser = await chromium.launch({
  headless: false,
  slowMo: 50
});

# Use visible state
await page.waitForSelector('[data-testid="element"]', {
  state: 'visible'
});
```

### Problem: Screenshots not captured

**Symptoms**:
- No screenshots in artifacts/
- Empty screenshot files

**Solution**:
```bash
# Ensure artifacts directory exists
mkdir -p artifacts

# Check permissions
chmod 755 artifacts

# Verify screenshot setting
grep PLAYWRIGHT_SCREENSHOT .env

# Take manual screenshot
await page.screenshot({
  path: 'artifacts/debug.png',
  fullPage: true
});
```

---

## Performance Problems

### Problem: Slow test execution

**Diagnosis**:
```bash
# Profile test execution
npx playwright test --reporter=html

# Check resource usage
docker stats superagent-app
# OR
top
```

**Solutions**:

#### Solution 1: Enable parallel execution
```bash
# In playwright.config.ts
workers: 4  # Run 4 tests in parallel
```

#### Solution 2: Optimize selectors
```typescript
// Fast: Use data-testid
await page.click('[data-testid="button"]');

// Slow: Use complex CSS
await page.click('div.container > ul > li:nth-child(2) > button');
```

#### Solution 3: Reduce wait times
```typescript
// Don't use fixed waits
// Bad:
await page.waitForTimeout(5000);

// Good:
await page.waitForSelector('[data-testid="loaded"]');
```

#### Solution 4: Disable unnecessary features
```env
PLAYWRIGHT_SCREENSHOT=only-on-failure
PLAYWRIGHT_VIDEO=retain-on-failure
PLAYWRIGHT_TRACE=retain-on-failure
```

### Problem: High memory usage

**Diagnosis**:
```bash
# Check memory usage
free -h
docker stats superagent-app

# Check Redis memory
redis-cli info memory | grep used_memory_human
```

**Solutions**:
```bash
# Limit Redis memory
redis-cli config set maxmemory 256mb

# Limit Docker container memory
# In docker-compose.yml:
services:
  superagent:
    deploy:
      resources:
        limits:
          memory: 4G

# Clean up artifacts
find artifacts/ -type f -mtime +7 -delete
```

### Problem: High API costs

**Diagnosis**:
```bash
# Check cost metrics
python3 << 'EOF'
from agent_system.observability import get_emitter

emitter = get_emitter()
metrics = emitter.get_metrics()
print(f"Cost per feature: ${metrics['cost_per_feature']:.2f}")
print(f"Daily spend: ${metrics.get('daily_cost', 0):.2f}")
EOF

# View cost events
grep "cost" logs/agent-events.jsonl | jq '.payload.cost_usd' | awk '{sum+=$1} END {print "Total: $"sum}'
```

**Solutions**:
```bash
# 1. Lower cost limits
echo "MAX_COST_PER_FEATURE=0.25" >> .env

# 2. Use Haiku more
echo "COMPLEXITY_THRESHOLD=8" >> .env  # Higher threshold = more Haiku

# 3. Reduce validation frequency
# Only validate critical tests with Gemini

# 4. Cache agent results
echo "ENABLE_CACHING=true" >> .env
echo "CACHE_TTL=7200" >> .env  # 2 hours
```

---

## Network Issues

### Problem: Cannot reach BASE_URL

**Symptoms**:
```
Error: page.goto: net::ERR_CONNECTION_REFUSED
```

**Diagnosis**:
```bash
# Check if target is reachable
curl -I http://localhost:3000

# Check from Docker container
docker compose exec superagent curl -I http://host.docker.internal:3000
```

**Solution**:
```bash
# For Docker, use host.docker.internal
echo "BASE_URL=http://host.docker.internal:3000" >> .env

# Or use docker network
# In docker-compose.yml:
services:
  superagent:
    extra_hosts:
      - "myapp.local:host-gateway"

# Then:
echo "BASE_URL=http://myapp.local:3000" >> .env
```

### Problem: DNS resolution failed

**Symptoms**:
```
Error: getaddrinfo ENOTFOUND redis
```

**Solution**:
```bash
# Check DNS in container
docker compose exec superagent cat /etc/resolv.conf
docker compose exec superagent nslookup redis

# Add to docker-compose.yml:
services:
  superagent:
    dns:
      - 8.8.8.8
      - 8.8.4.4
```

---

## Database Issues

### Problem: Vector database corrupted

**Symptoms**:
```
chromadb.errors.InvalidDimensionException: Dimension mismatch
```

**Solution**:
```bash
# Backup existing database
mv vector_db vector_db.backup

# Recreate database
mkdir -p vector_db

# Reinitialize
python3 << 'EOF'
from agent_system.state.vector_client import VectorClient
vector = VectorClient()
print("✓ Vector database reinitialized")
EOF

# Restore from backup if needed
# (see docs/DEPLOYMENT.md for restore procedure)
```

### Problem: Redis data loss

**Symptoms**:
- Session data missing
- Task queue empty after restart

**Solution**:
```bash
# Enable persistence
redis-cli config set appendonly yes

# Or in redis.conf:
appendonly yes
appendfsync everysec

# Check persistence status
redis-cli info persistence
```

---

## Observability Issues

### Problem: Events not appearing in dashboard

**Symptoms**:
- Dashboard shows "Disconnected"
- No events in console

**Diagnosis**:
```bash
# Check if WebSocket server is running
lsof -i :3010
# OR
netstat -tuln | grep 3010

# Check logs
tail -f logs/agent-events.jsonl
```

**Solution**:
```bash
# Start event stream server
python3 -m agent_system.observability.event_stream

# In separate terminal, emit test event
python3 << 'EOF'
from agent_system.observability import emit_event
import time

emit_event('task_queued', {
    'task_id': 't_test',
    'feature': 'test',
    'est_cost': 0.01,
    'timestamp': time.time()
})
print("✓ Event emitted")
EOF

# Open dashboard
open agent_system/observability/dashboard.html
```

### Problem: Metrics not updating

**Diagnosis**:
```bash
# Check Redis connection
redis-cli ping

# Check metrics storage
redis-cli keys "metrics:*"

# Get current metrics
python3 << 'EOF'
from agent_system.observability import get_emitter

emitter = get_emitter()
metrics = emitter.get_metrics()
for key, value in metrics.items():
    print(f"{key}: {value}")
EOF
```

**Solution**:
```bash
# Ensure Redis is running
brew services start redis  # macOS
# OR
sudo systemctl start redis  # Linux

# Verify emitter is initialized
python3 << 'EOF'
from agent_system.observability import get_emitter

emitter = get_emitter()
print(f"Console enabled: {emitter.console_enabled}")
print(f"File enabled: {emitter.file_enabled}")
print(f"WebSocket enabled: {emitter.websocket_enabled}")
EOF
```

---

## Advanced Debugging

### Enable Debug Mode

```bash
# In .env
DEBUG_MODE=true
LOG_LEVEL=DEBUG

# Restart services
docker compose restart superagent
# OR
sudo systemctl restart superagent
```

### Capture Full Logs

```bash
# Enable verbose logging for all components
export DEBUG="*"
python agent_system/cli.py status 2>&1 | tee debug.log

# Capture Docker logs
docker compose logs --no-log-prefix > docker-debug.log

# Capture system info
./health_check.sh > system-info.txt
```

### Remote Debugging

```bash
# Enable remote debugging in Python
# Add to agent code:
import debugpy
debugpy.listen(5678)
print("Waiting for debugger...")
debugpy.wait_for_client()

# Connect with VS Code
# .vscode/launch.json:
{
  "type": "python",
  "request": "attach",
  "name": "Python: Remote Attach",
  "connect": {
    "host": "localhost",
    "port": 5678
  }
}
```

---

## Getting Help

### Collect Diagnostic Information

Before opening an issue, collect:

```bash
#!/bin/bash
# Save as collect-diagnostics.sh

echo "Collecting diagnostic information..."

# System info
echo "=== System Info ===" > diagnostics.txt
uname -a >> diagnostics.txt
python3 --version >> diagnostics.txt
node --version >> diagnostics.txt
docker --version >> diagnostics.txt

# Service status
echo -e "\n=== Service Status ===" >> diagnostics.txt
docker compose ps >> diagnostics.txt 2>&1

# Recent logs
echo -e "\n=== Recent Logs ===" >> diagnostics.txt
tail -100 logs/agent-events.jsonl >> diagnostics.txt 2>&1

# Environment (without secrets)
echo -e "\n=== Environment ===" >> diagnostics.txt
cat .env | grep -v "API_KEY\|PASSWORD" >> diagnostics.txt

# Health check
echo -e "\n=== Health Check ===" >> diagnostics.txt
./health_check.sh >> diagnostics.txt 2>&1

echo "Diagnostics saved to diagnostics.txt"
```

### Contact Support

Include in your issue:
1. Diagnostics output
2. Error message (full stack trace)
3. Steps to reproduce
4. Expected vs actual behavior
5. SuperAgent version

---

## Preventive Measures

### Regular Maintenance

```bash
# Weekly
- Backup Redis and Vector DB
- Review logs for errors
- Check disk space
- Update dependencies

# Monthly
- Rotate API keys
- Review cost metrics
- Clean old artifacts
- Update documentation

# Quarterly
- Security audit
- Performance review
- Dependency updates
- System upgrades
```

### Monitoring Alerts

Set up alerts for:
- High API costs (>$10/day)
- Low disk space (<10%)
- High error rate (>10%)
- Redis memory (>80%)
- Service downtime (>5 min)

---

## Related Documentation

- [Deployment Guide](./DEPLOYMENT.md) - Full deployment instructions
- [Architecture Guide](./ARCHITECTURE.md) - System architecture
- [Docker Guide](../DOCKER.md) - Docker quick start
- [README](../README.md) - Project overview

---

**Version**: 1.0.0
**Last Updated**: January 2025
**Maintainer**: SuperAgent Team
