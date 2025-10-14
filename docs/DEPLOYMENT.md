# SuperAgent - Deployment Guide

Complete guide for deploying SuperAgent in development, staging, and production environments.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [API Key Configuration](#api-key-configuration)
4. [Redis Setup](#redis-setup)
5. [Vector Database Setup](#vector-database-setup)
6. [Docker Deployment](#docker-deployment)
7. [Production Deployment](#production-deployment)
8. [Monitoring and Observability](#monitoring-and-observability)
9. [Backup and Restore](#backup-and-restore)
10. [Security Considerations](#security-considerations)
11. [Performance Tuning](#performance-tuning)

---

## Prerequisites

### System Requirements

**Minimum**:
- CPU: 2 cores
- Memory: 4 GB RAM
- Disk: 10 GB available space
- OS: Linux (Ubuntu 20.04+), macOS (10.15+), or Windows with WSL2

**Recommended**:
- CPU: 4 cores
- Memory: 8 GB RAM
- Disk: 20 GB SSD
- OS: Linux (Ubuntu 22.04+) or macOS (12+)

### Software Dependencies

#### Python
```bash
# Check Python version (3.10+ required, 3.11+ recommended)
python3 --version

# Install Python 3.11 (Ubuntu/Debian)
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev

# Install Python 3.11 (macOS)
brew install python@3.11

# Install Python 3.11 (Windows/WSL2)
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.11 python3.11-venv
```

#### Node.js
```bash
# Check Node.js version (16+ required, 18+ recommended)
node --version
npm --version

# Install Node.js 18 (Ubuntu/Debian)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install Node.js 18 (macOS)
brew install node@18

# Install Node.js 18 (Windows/WSL2)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install 18
nvm use 18
```

#### Docker (Optional but Recommended)
```bash
# Check Docker version
docker --version
docker compose version

# Install Docker Desktop (macOS/Windows)
# Download from: https://www.docker.com/products/docker-desktop

# Install Docker Engine (Ubuntu/Debian)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Verify installation
docker run hello-world
```

#### Git
```bash
# Check Git version
git --version

# Install Git (Ubuntu/Debian)
sudo apt install git

# Install Git (macOS)
brew install git
```

---

## Environment Setup

### 1. Clone Repository

```bash
# Clone the repository
git clone https://github.com/your-org/SuperAgent.git
cd SuperAgent

# Verify directory structure
ls -la
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# OR
.\venv\Scripts\activate  # Windows

# Verify activation (should show venv path)
which python
```

### 3. Install Python Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install project dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep -E "anthropic|openai|google-generativeai|redis|chromadb"
```

### 4. Install Playwright Browsers

```bash
# Install Playwright browsers (Chromium only for production)
npx playwright install chromium

# Install all browsers (development)
npx playwright install

# Verify installation
npx playwright --version
```

### 5. Environment Variables

```bash
# Copy environment template
cp .env.example .env

# Edit with your preferred editor
nano .env
# OR
vim .env
# OR
code .env  # VS Code
```

See [API Key Configuration](#api-key-configuration) for detailed setup.

---

## API Key Configuration

### Required API Keys

SuperAgent requires API keys from three providers:

1. **Anthropic Claude** (Kaya, Scribe, Medic, Critic agents)
2. **OpenAI** (Voice integration, embeddings)
3. **Google Gemini** (Validation agent)

### 1. Anthropic Claude API Key

**Get your key**: [https://console.anthropic.com/](https://console.anthropic.com/)

**Pricing** (as of January 2025):
- Claude Haiku: $0.25 / 1M input tokens, $1.25 / 1M output tokens
- Claude Sonnet 4.5: $3 / 1M input tokens, $15 / 1M output tokens

**Setup**:
```bash
# In .env file
ANTHROPIC_API_KEY=sk-ant-api03-your-actual-key-here
```

**Verify**:
```bash
python3 -c "from anthropic import Anthropic; client = Anthropic(); print('Anthropic OK')"
```

**Cost Management**:
- SuperAgent targets $0.50 per feature ($2-3 for critical paths)
- Uses Haiku for 70% of operations (routing, execution, pre-validation)
- Uses Sonnet 4.5 only for complex tasks (test writing, bug fixing)

### 2. OpenAI API Key

**Get your key**: [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)

**Pricing** (as of January 2025):
- GPT-4o: $2.50 / 1M input tokens, $10 / 1M output tokens
- Text Embedding 3 Small: $0.02 / 1M tokens
- Realtime API: $0.06 / minute audio

**Setup**:
```bash
# In .env file
OPENAI_API_KEY=sk-your-actual-key-here
```

**Verify**:
```bash
python3 -c "from openai import OpenAI; client = OpenAI(); print('OpenAI OK')"
```

**Usage**:
- Voice transcription (Realtime API)
- Vector embeddings (for RAG)
- Intent parsing (voice commands)

### 3. Google Gemini API Key

**Get your key**: [https://makersuite.google.com/app/apikey](https://makersuite.google.com/app/apikey)

**Pricing** (as of January 2025):
- Gemini 2.5 Pro: $1.25 / 1M input tokens, $5 / 1M output tokens
- Free tier: 60 requests per minute

**Setup**:
```bash
# In .env file
GEMINI_API_KEY=your-actual-key-here
```

**Verify**:
```bash
python3 -c "import google.generativeai as genai; genai.configure(api_key='your-key'); print('Gemini OK')"
```

**Usage**:
- Final validation with browser automation
- Screenshot-based test verification
- Used sparingly to minimize costs

### Optional API Keys

#### Redis Cloud (Production)

For managed Redis in production:

```bash
# Get credentials from Redis Cloud dashboard
REDIS_HOST=redis-12345.redislabs.com
REDIS_PORT=12345
REDIS_PASSWORD=your-secure-password
REDIS_TLS=true
```

**Providers**:
- [Redis Cloud](https://redis.com/try-free/) - 30 MB free tier
- [AWS ElastiCache](https://aws.amazon.com/elasticache/) - Managed Redis on AWS
- [Google Cloud Memorystore](https://cloud.google.com/memorystore) - Managed Redis on GCP

### Complete .env Configuration

```env
# ==============================================================================
# API Keys (Required)
# ==============================================================================
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
OPENAI_API_KEY=sk-your-key-here
GEMINI_API_KEY=your-gemini-key-here

# ==============================================================================
# Redis Configuration
# ==============================================================================
REDIS_HOST=localhost          # Use 'redis' for docker-compose
REDIS_PORT=6379
REDIS_PASSWORD=                # Optional
REDIS_DB=0
REDIS_TLS=false               # Set to true for Redis Cloud

# ==============================================================================
# Vector Database
# ==============================================================================
VECTOR_DB_PATH=./vector_db
VECTOR_DB_COLLECTION=superagent_rag

# ==============================================================================
# Application Configuration
# ==============================================================================
BASE_URL=http://localhost:3000    # Your test target
LOG_LEVEL=INFO
TESTS_DIR=./tests
ARTIFACTS_DIR=./artifacts

# ==============================================================================
# Cost Management
# ==============================================================================
MAX_COST_PER_FEATURE=0.50
CRITICAL_PATH_MAX_COST=3.00
DAILY_BUDGET_LIMIT=50.00

# ==============================================================================
# Agent Configuration
# ==============================================================================
KAYA_DEFAULT_MODEL=haiku
SCRIBE_DEFAULT_MODEL=sonnet
MEDIC_DEFAULT_MODEL=sonnet
COMPLEXITY_THRESHOLD=5

# ==============================================================================
# Playwright Configuration
# ==============================================================================
PLAYWRIGHT_TIMEOUT=45000
PLAYWRIGHT_HEADLESS=true
PLAYWRIGHT_SCREENSHOT=on
PLAYWRIGHT_VIDEO=retain-on-failure
PLAYWRIGHT_TRACE=retain-on-failure

# ==============================================================================
# HITL Configuration
# ==============================================================================
MAX_RETRY_ATTEMPTS=3
HITL_PRIORITY_THRESHOLD=0.7
HITL_QUEUE_TIMEOUT_HOURS=24

# ==============================================================================
# Observability
# ==============================================================================
OBSERVABILITY_PORT=8000
ENABLE_TELEMETRY=true
METRICS_EXPORT_INTERVAL=60

# ==============================================================================
# Voice Integration (Optional)
# ==============================================================================
ENABLE_VOICE=false
VOICE_MODEL=gpt-4o-realtime-preview
VOICE_LANGUAGE=en-US

# ==============================================================================
# Security
# ==============================================================================
ENABLE_SANDBOX=false
ALLOWED_TEST_DIRS=./tests,./e2e
MAX_TEST_EXECUTION_TIME=60000

# ==============================================================================
# Development
# ==============================================================================
DEBUG_MODE=false
DRY_RUN=false
ENABLE_CACHING=true
CACHE_TTL=3600
```

---

## Redis Setup

Redis is used for hot state management (session data, task queue, transcripts) with 1-hour TTL.

### Option 1: Local Redis (Development)

#### macOS (Homebrew)
```bash
# Install Redis
brew install redis

# Start Redis
brew services start redis

# Verify
redis-cli ping  # Should return "PONG"
```

#### Ubuntu/Debian
```bash
# Install Redis
sudo apt update
sudo apt install redis-server

# Configure Redis
sudo nano /etc/redis/redis.conf
# Set: supervised systemd

# Start Redis
sudo systemctl start redis
sudo systemctl enable redis

# Verify
redis-cli ping  # Should return "PONG"
```

#### Windows (WSL2)
```bash
# Install Redis
curl -fsSL https://packages.redis.io/gpg | sudo gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/redis.list
sudo apt-get update
sudo apt-get install redis

# Start Redis
sudo service redis-server start

# Verify
redis-cli ping
```

### Option 2: Docker Redis (Development/Staging)

```bash
# Start Redis container
docker run -d \
  --name superagent-redis \
  -p 6379:6379 \
  -v redis_data:/data \
  redis:7-alpine \
  redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru

# Verify
docker exec superagent-redis redis-cli ping

# View logs
docker logs superagent-redis

# Stop Redis
docker stop superagent-redis

# Remove container
docker rm superagent-redis
```

### Option 3: Redis Cloud (Production)

**Setup**:
1. Create account at [Redis Cloud](https://redis.com/try-free/)
2. Create new database (30 MB free tier)
3. Get connection details from dashboard
4. Update `.env`:

```env
REDIS_HOST=redis-12345.redislabs.com
REDIS_PORT=12345
REDIS_PASSWORD=your-secure-password
REDIS_TLS=true
```

**Test connection**:
```bash
redis-cli -h redis-12345.redislabs.com -p 12345 -a your-password --tls ping
```

### Redis Configuration

#### Persistence
```bash
# In redis.conf or docker command
appendonly yes              # Enable AOF persistence
appendfsync everysec        # Sync every second
save 900 1                  # Save after 900 seconds if 1 key changed
save 300 10                 # Save after 300 seconds if 10 keys changed
save 60 10000               # Save after 60 seconds if 10000 keys changed
```

#### Memory Management
```bash
maxmemory 256mb             # Limit memory usage
maxmemory-policy allkeys-lru  # Evict least recently used keys
```

#### TTL Strategy
SuperAgent uses 1-hour TTL for hot state:
- Session data: `session:{session_id}` (1h)
- Task queue: `task:{task_id}` (1h)
- Voice transcripts: `voice:transcript:{id}` (1h)
- Metrics: `metrics:hourly:{timestamp}` (7 days)
- Metrics: `metrics:daily:{date}` (30 days)

### Verify Redis Setup

```python
# Test Redis connection
python3 << 'EOF'
from agent_system.state.redis_client import RedisClient

redis = RedisClient()
print("✓ Redis connected")

# Test set/get
redis.set("test_key", {"hello": "world"}, ttl=60)
value = redis.get("test_key")
print(f"✓ Set/Get working: {value}")

# Test cleanup
redis.delete("test_key")
print("✓ Redis setup complete")
EOF
```

---

## Vector Database Setup

ChromaDB is used for cold storage (permanent) of test patterns, bug fixes, and HITL annotations.

### Installation

ChromaDB is included in `requirements.txt`:
```bash
pip install chromadb
```

### Directory Setup

```bash
# Create vector database directory
mkdir -p vector_db

# Set permissions
chmod 755 vector_db

# Verify in .env
echo "VECTOR_DB_PATH=./vector_db" >> .env
echo "VECTOR_DB_COLLECTION=superagent_rag" >> .env
```

### Initialize Vector Database

```python
# Initialize and test vector database
python3 << 'EOF'
from agent_system.state.vector_client import VectorClient

vector = VectorClient()
print("✓ Vector database initialized")

# Test store/retrieve
vector.store_test_pattern(
    test_id="test_001",
    feature="login",
    pattern_type="success",
    code="test code here",
    metadata={"model": "sonnet", "cost": 0.12}
)
print("✓ Test pattern stored")

# Search
results = vector.search_similar_tests("login authentication")
print(f"✓ Search working: {len(results)} results")
print("✓ Vector database setup complete")
EOF
```

### Data Schema

Vector database stores:

1. **Test Patterns** (`test_patterns` collection)
   - Successful test code
   - Feature descriptions
   - Complexity scores
   - Cost data
   - Embeddings

2. **Bug Fixes** (`bug_fixes` collection)
   - Error signatures
   - Fix strategies
   - Code diffs
   - Success rates
   - Embeddings

3. **HITL Annotations** (`hitl_annotations` collection)
   - Human feedback
   - Root cause analysis
   - Fix recommendations
   - Priority scores
   - Embeddings

### Backup Vector Database

```bash
# Backup entire vector_db directory
tar -czf vector_db_backup_$(date +%Y%m%d_%H%M%S).tar.gz vector_db/

# Move to backup location
mv vector_db_backup_*.tar.gz /path/to/backups/
```

### Restore Vector Database

```bash
# Stop SuperAgent
# Extract backup
tar -xzf vector_db_backup_20250114_120000.tar.gz

# Verify
ls -la vector_db/
```

---

## Docker Deployment

Complete containerized deployment using Docker and Docker Compose.

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 4 GB RAM available
- 10 GB disk space

### Quick Start

```bash
# 1. Navigate to project directory
cd /path/to/SuperAgent

# 2. Copy environment file
cp .env.example .env

# 3. Edit .env with your API keys
nano .env

# 4. Build and start services
docker compose up -d

# 5. Verify deployment
docker compose ps
docker compose logs -f
```

### Using Makefile

```bash
# Setup (first time)
make setup

# Start services
make up

# Check status
make status

# View logs
make logs

# Stop services
make down

# Rebuild
make rebuild
```

### Docker Compose Services

**superagent** (Main application):
- Python 3.11 + Node.js 18
- Playwright browsers (Chromium)
- All agents (Kaya, Scribe, Runner, Medic, Critic, Gemini)
- Resources: 2-4 GB RAM, 1-2 CPU cores

**redis** (State management):
- Redis 7 Alpine
- Max memory: 256 MB
- Persistence: RDB + AOF
- Resources: 128-256 MB RAM, 0.25-0.5 CPU cores

### CLI Usage

```bash
# System status
docker compose exec superagent python agent_system/cli.py status

# Run Kaya orchestrator
docker compose exec superagent python agent_system/cli.py kaya "create test for login"

# Route a task
docker compose exec superagent python agent_system/cli.py route write_test "Create checkout test"

# Execute a test
docker compose exec superagent python agent_system/cli.py run tests/auth.spec.ts

# Review with Critic
docker compose exec superagent python agent_system/cli.py review tests/auth.spec.ts

# Interactive shell
docker compose exec superagent /bin/bash
```

### Makefile Commands

```bash
# Service management
make up              # Start all services
make down            # Stop all services
make restart         # Restart services
make logs            # View logs (follow mode)
make logs-app        # SuperAgent logs only
make logs-redis      # Redis logs only
make status          # Service health check

# SuperAgent CLI
make cli-status      # System status
make cli-kaya CMD="..." # Run Kaya
make cli-route TASK=... DESC="..." # Route task
make cli-run TEST=... # Execute test
make cli-review TEST=... # Review test
make shell           # Interactive shell
make python          # Python REPL
make redis-cli       # Redis CLI

# Testing
make test            # Run all tests
make test-unit       # Unit tests only
make test-integration # Integration tests only
make test-cov        # Tests with coverage

# Data management
make backup          # Backup volumes
make restore-vector FILE=... # Restore vector DB
make restore-redis FILE=... # Restore Redis
make clean-artifacts # Clean test artifacts

# Maintenance
make rebuild         # Rebuild without cache
make update          # Pull + rebuild + restart
make pull            # Pull latest images
make clean           # Remove stopped containers
make clean-all       # Remove everything (DANGER)
```

### Volume Management

**Persistent volumes**:
- `redis_data` - Redis data (survives `docker compose down`)
- `vector_db_data` - Vector database (survives `docker compose down`)

**Host-mounted directories**:
- `./tests` → `/app/tests` - Test files
- `./artifacts` → `/app/tests/artifacts` - Screenshots, videos, traces
- `./logs` → `/app/logs` - Application logs
- `./test-results` → `/app/test-results` - Playwright results
- `./playwright-report` → `/app/playwright-report` - HTML reports

### Backup Docker Volumes

```bash
# Backup vector database
docker run --rm \
  -v superagent-vector-db:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/vector_db_$(date +%Y%m%d_%H%M%S).tar.gz /data

# Backup Redis
docker run --rm \
  -v superagent-redis-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/redis_$(date +%Y%m%d_%H%M%S).tar.gz /data
```

### Restore Docker Volumes

```bash
# Stop services
docker compose down

# Restore vector database
docker run --rm \
  -v superagent-vector-db:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/vector_db_20250114_120000.tar.gz -C /

# Restore Redis
docker run --rm \
  -v superagent-redis-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/redis_20250114_120000.tar.gz -C /

# Restart services
docker compose up -d
```

---

## Production Deployment

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Load Balancer (Nginx)                │
│                    (SSL/TLS Termination)                 │
└───────────────────────┬─────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
┌───────▼───────┐ ┌────▼────┐ ┌────────▼────────┐
│  SuperAgent   │ │SuperAgent│ │   SuperAgent    │
│  Instance 1   │ │Instance 2│ │   Instance 3    │
└───────┬───────┘ └────┬─────┘ └────────┬────────┘
        │              │                 │
        └──────────────┼─────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
┌───────▼──────┐ ┌────▼────┐ ┌───────▼────────┐
│ Redis Cloud  │ │ Vector  │ │  Observability │
│  (Managed)   │ │   DB    │ │   Dashboard    │
└──────────────┘ └─────────┘ └────────────────┘
```

### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y \
  git \
  curl \
  build-essential \
  python3.11 \
  python3.11-venv \
  python3.11-dev \
  nginx \
  certbot \
  python3-certbot-nginx

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Verify
docker --version
python3.11 --version
nginx -v
```

### 2. Clone and Configure

```bash
# Create application directory
sudo mkdir -p /opt/superagent
sudo chown $USER:$USER /opt/superagent
cd /opt/superagent

# Clone repository
git clone https://github.com/your-org/SuperAgent.git .

# Create .env file
cp .env.example .env
nano .env  # Add production API keys
```

### 3. SSL/TLS Certificate

```bash
# Using Let's Encrypt (recommended)
sudo certbot certonly --nginx -d superagent.yourdomain.com

# Or generate self-signed (development only)
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/superagent.key \
  -out /etc/ssl/certs/superagent.crt
```

### 4. Nginx Configuration

Create `/etc/nginx/sites-available/superagent`:

```nginx
upstream superagent_backend {
    least_conn;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
}

# HTTP redirect to HTTPS
server {
    listen 80;
    server_name superagent.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name superagent.yourdomain.com;

    # SSL configuration
    ssl_certificate /etc/letsencrypt/live/superagent.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/superagent.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/superagent-access.log;
    error_log /var/log/nginx/superagent-error.log;

    # Proxy settings
    location / {
        proxy_pass http://superagent_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Static files
    location /static {
        alias /opt/superagent/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Health check endpoint
    location /health {
        access_log off;
        return 200 "OK\n";
        add_header Content-Type text/plain;
    }
}
```

Enable configuration:
```bash
sudo ln -s /etc/nginx/sites-available/superagent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 5. Systemd Service

Create `/etc/systemd/system/superagent.service`:

```ini
[Unit]
Description=SuperAgent Multi-Agent Testing System
After=network.target redis.target

[Service]
Type=simple
User=superagent
Group=superagent
WorkingDirectory=/opt/superagent
Environment="PATH=/opt/superagent/venv/bin"
ExecStart=/opt/superagent/venv/bin/gunicorn \
    --workers 3 \
    --bind 0.0.0.0:8001 \
    --timeout 120 \
    --access-logfile /var/log/superagent/access.log \
    --error-logfile /var/log/superagent/error.log \
    --log-level info \
    agent_system.wsgi:application

Restart=always
RestartSec=10

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/superagent/logs /opt/superagent/artifacts /opt/superagent/vector_db

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
# Create user
sudo useradd -r -s /bin/false superagent
sudo chown -R superagent:superagent /opt/superagent

# Create log directory
sudo mkdir -p /var/log/superagent
sudo chown superagent:superagent /var/log/superagent

# Enable service
sudo systemctl daemon-reload
sudo systemctl enable superagent
sudo systemctl start superagent

# Check status
sudo systemctl status superagent
```

### 6. External Redis

Use managed Redis for production:

```bash
# Update .env with Redis Cloud credentials
REDIS_HOST=redis-12345.redislabs.com
REDIS_PORT=12345
REDIS_PASSWORD=your-secure-password
REDIS_TLS=true
```

Test connection:
```bash
redis-cli -h redis-12345.redislabs.com -p 12345 -a your-password --tls ping
```

### 7. Monitoring

#### Prometheus + Grafana

```bash
# Install Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.40.0/prometheus-2.40.0.linux-amd64.tar.gz
tar xvfz prometheus-*.tar.gz
cd prometheus-*

# Configure prometheus.yml
cat > prometheus.yml << 'EOF'
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'superagent'
    static_configs:
      - targets: ['localhost:8001']
EOF

# Start Prometheus
./prometheus --config.file=prometheus.yml

# Install Grafana
sudo apt install -y grafana
sudo systemctl start grafana-server
sudo systemctl enable grafana-server

# Access Grafana at http://localhost:3000
# Default credentials: admin/admin
```

### 8. Log Aggregation

```bash
# Install filebeat for log shipping to ELK stack
curl -L -O https://artifacts.elastic.co/downloads/beats/filebeat/filebeat-8.10.0-amd64.deb
sudo dpkg -i filebeat-8.10.0-amd64.deb

# Configure filebeat
sudo nano /etc/filebeat/filebeat.yml
# Add log paths: /var/log/superagent/*.log

# Start filebeat
sudo systemctl start filebeat
sudo systemctl enable filebeat
```

---

## Monitoring and Observability

### Observability Dashboard

SuperAgent includes a built-in WebSocket-based observability system.

#### Setup

```bash
# 1. Ensure Redis is running
redis-cli ping

# 2. Start observability server (development)
python3 -m agent_system.observability.event_stream

# 3. Open dashboard in browser
open agent_system/observability/dashboard.html

# 4. Click "Connect" to start receiving events
```

#### Events Tracked

1. **task_queued** - Task enters queue
2. **agent_started** - Agent begins work
3. **agent_completed** - Agent finishes work
4. **validation_complete** - Gemini validation results
5. **hitl_escalated** - Human-in-the-loop escalation
6. **budget_warning** - 80% budget threshold
7. **budget_exceeded** - Budget limit exceeded

#### Metrics

- **agent_utilization** - % of time agents are active
- **cost_per_feature** - Average cost per completed feature
- **average_retry_count** - Average retries per task
- **critic_rejection_rate** - % of tests rejected by Critic
- **validation_pass_rate** - % of validations that pass
- **time_to_completion** - Average queue-to-completion time

#### View Logs

```bash
# Console output (real-time)
tail -f logs/agent-events.jsonl | jq

# Filter by event type
grep "task_queued" logs/agent-events.jsonl | jq

# Count events
cat logs/agent-events.jsonl | jq -r '.event_type' | sort | uniq -c

# Last 10 events
tail -n 10 logs/agent-events.jsonl | jq
```

#### Programmatic Access

```python
from agent_system.observability import get_emitter

emitter = get_emitter()
metrics = emitter.get_metrics()

print(f"Agent utilization: {metrics['agent_utilization']:.2%}")
print(f"Cost per feature: ${metrics['cost_per_feature']:.2f}")
print(f"Validation pass rate: {metrics['validation_pass_rate']:.2%}")
```

---

## Backup and Restore

### Automated Backup Script

Create `/opt/superagent/backup.sh`:

```bash
#!/bin/bash
set -e

BACKUP_DIR="/backups/superagent"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup Redis
docker run --rm \
  -v superagent-redis-data:/data \
  -v $BACKUP_DIR:/backup \
  alpine tar czf /backup/redis_$DATE.tar.gz /data

# Backup Vector DB
docker run --rm \
  -v superagent-vector-db:/data \
  -v $BACKUP_DIR:/backup \
  alpine tar czf /backup/vector_db_$DATE.tar.gz /data

# Backup test files
tar -czf $BACKUP_DIR/tests_$DATE.tar.gz tests/

# Backup artifacts
tar -czf $BACKUP_DIR/artifacts_$DATE.tar.gz artifacts/

# Backup logs
tar -czf $BACKUP_DIR/logs_$DATE.tar.gz logs/

# Delete backups older than 30 days
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

Make executable:
```bash
chmod +x /opt/superagent/backup.sh
```

Schedule with cron:
```bash
crontab -e

# Add line (daily at 2 AM)
0 2 * * * /opt/superagent/backup.sh >> /var/log/superagent-backup.log 2>&1
```

### Restore Procedure

```bash
# 1. Stop services
docker compose down
# OR
sudo systemctl stop superagent

# 2. Restore Redis
docker run --rm \
  -v superagent-redis-data:/data \
  -v /backups/superagent:/backup \
  alpine tar xzf /backup/redis_20250114_120000.tar.gz -C /

# 3. Restore Vector DB
docker run --rm \
  -v superagent-vector-db:/data \
  -v /backups/superagent:/backup \
  alpine tar xzf /backup/vector_db_20250114_120000.tar.gz -C /

# 4. Restore test files
tar -xzf /backups/superagent/tests_20250114_120000.tar.gz

# 5. Restart services
docker compose up -d
# OR
sudo systemctl start superagent

# 6. Verify
docker compose ps
# OR
sudo systemctl status superagent
```

---

## Security Considerations

### 1. API Key Security

**Never commit API keys**:
```bash
# Ensure .env is in .gitignore
echo ".env" >> .gitignore

# Use environment variables in CI/CD
# GitHub Actions example:
# - name: Deploy
#   env:
#     ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

**Rotate keys regularly**:
- Anthropic: [https://console.anthropic.com/](https://console.anthropic.com/)
- OpenAI: [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- Gemini: [https://makersuite.google.com/app/apikey](https://makersuite.google.com/app/apikey)

### 2. Network Security

**Firewall rules**:
```bash
# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Deny Redis access from external
sudo ufw deny 6379/tcp

# Enable firewall
sudo ufw enable
```

**Redis authentication**:
```bash
# In redis.conf
requirepass your-strong-password

# Or in docker-compose.yml
command: redis-server --requirepass your-strong-password
```

### 3. Sandboxing

Enable sandbox mode to restrict file system access:

```env
# In .env
ENABLE_SANDBOX=true
ALLOWED_TEST_DIRS=./tests,./e2e
MAX_TEST_EXECUTION_TIME=60000
```

### 4. Rate Limiting

**Nginx rate limiting**:
```nginx
# In nginx.conf
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

server {
    location / {
        limit_req zone=api burst=20 nodelay;
        # ...
    }
}
```

### 5. Audit Logging

All agent actions are logged:
```bash
# View audit log
tail -f logs/agent-events.jsonl | jq 'select(.event_type | contains("agent"))'

# Search for specific task
grep "t_123" logs/agent-events.jsonl | jq
```

---

## Performance Tuning

### 1. Playwright Optimization

**Headless mode** (faster):
```env
PLAYWRIGHT_HEADLESS=true
```

**Disable unnecessary features**:
```typescript
// In test template
test.use({
  screenshot: 'only-on-failure',  // Not 'on'
  video: 'retain-on-failure',     // Not 'on'
  trace: 'retain-on-failure',     // Not 'on'
});
```

**Browser context reuse**:
```python
# Reuse browser context across tests
browser_context = await playwright.chromium.launch_persistent_context()
```

### 2. Redis Optimization

**Memory settings**:
```bash
# In redis.conf or docker command
maxmemory 512mb
maxmemory-policy allkeys-lru
```

**Persistence settings**:
```bash
# Less frequent saves for better performance
save 900 1
save 300 10
save 60 10000
appendfsync everysec  # Not "always"
```

### 3. Agent Optimization

**Model selection**:
- Use Haiku for simple tasks (70% of operations)
- Use Sonnet 4.5 only for complex tasks (30%)
- Use Gemini only for final validation

**Parallel execution**:
```python
# Run multiple agents in parallel
import asyncio

results = await asyncio.gather(
    scribe.write_test(task1),
    scribe.write_test(task2),
    scribe.write_test(task3)
)
```

### 4. Vector Database Optimization

**Batch operations**:
```python
# Store multiple patterns at once
vector.batch_store_patterns([pattern1, pattern2, pattern3])
```

**Limit search results**:
```python
# Retrieve only top 5 results
results = vector.search_similar_tests("login", limit=5)
```

---

## Health Checks

### Manual Health Check

```bash
# Check all components
python3 << 'EOF'
import sys

# Check Redis
try:
    from agent_system.state.redis_client import RedisClient
    redis = RedisClient()
    redis.redis.ping()
    print("✓ Redis: OK")
except Exception as e:
    print(f"✗ Redis: FAIL - {e}")
    sys.exit(1)

# Check Vector DB
try:
    from agent_system.state.vector_client import VectorClient
    vector = VectorClient()
    print("✓ Vector DB: OK")
except Exception as e:
    print(f"✗ Vector DB: FAIL - {e}")
    sys.exit(1)

# Check Playwright
try:
    import subprocess
    result = subprocess.run(["npx", "playwright", "--version"], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✓ Playwright: OK ({result.stdout.strip()})")
    else:
        raise Exception("Command failed")
except Exception as e:
    print(f"✗ Playwright: FAIL - {e}")
    sys.exit(1)

print("\n✓ All systems operational")
EOF
```

### Automated Health Check

Create `/opt/superagent/health_check.sh`:

```bash
#!/bin/bash

# Check Redis
redis-cli ping > /dev/null 2>&1 || exit 1

# Check SuperAgent service
systemctl is-active superagent > /dev/null 2>&1 || exit 1

# Check Nginx
systemctl is-active nginx > /dev/null 2>&1 || exit 1

echo "OK"
exit 0
```

Add to monitoring:
```bash
# Run every 5 minutes
*/5 * * * * /opt/superagent/health_check.sh || /usr/bin/alert-admin.sh
```

---

## Troubleshooting

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for detailed troubleshooting guide.

Quick checks:

```bash
# 1. Check logs
tail -f logs/agent-events.jsonl

# 2. Check service status
docker compose ps
# OR
sudo systemctl status superagent

# 3. Check Redis connection
redis-cli ping

# 4. Check disk space
df -h

# 5. Check memory
free -h

# 6. Verify API keys
python3 -c "from anthropic import Anthropic; client = Anthropic(); print('OK')"
```

---

## Next Steps

1. **Development**: Follow [Quick Start](#environment-setup) for local development
2. **Docker**: Use [Docker Deployment](#docker-deployment) for containerized deployment
3. **Production**: Follow [Production Deployment](#production-deployment) for full production setup
4. **Monitoring**: Set up [Observability Dashboard](#monitoring-and-observability)
5. **Backup**: Configure [Automated Backups](#backup-and-restore)

---

## Support

- **Documentation**: [README.md](../README.md), [ARCHITECTURE.md](./ARCHITECTURE.md)
- **Troubleshooting**: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- **Docker**: [DOCKER.md](../DOCKER.md), [DOCKER_DEPLOYMENT.md](../DOCKER_DEPLOYMENT.md)
- **Architecture**: [CLAUDE.md](../CLAUDE.md)

---

**Version**: 1.0.0
**Last Updated**: January 2025
**Maintainer**: SuperAgent Team
