# SuperAgent - Voice-Controlled Multi-Agent Testing System
# Multi-stage production-ready Dockerfile with Python 3.11, Playwright, and Node.js 18
# Architecture: 6 specialized agents (Kaya, Scribe, Runner, Medic, Critic, Gemini)

# ==============================================================================
# Stage 1: Builder - Install Python dependencies
# ==============================================================================
FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --user -r requirements.txt


# ==============================================================================
# Stage 2: Node.js Builder - Voice integration dependencies
# ==============================================================================
FROM node:18-slim AS node-builder

WORKDIR /build/voice

# Copy voice integration package files
COPY agent_system/voice/package*.json ./
RUN npm ci --only=production && npm cache clean --force

# Copy TypeScript source and build
COPY agent_system/voice/tsconfig.json ./
COPY agent_system/voice/*.ts ./
RUN if [ -f tsconfig.json ]; then npm install typescript && npm run build; fi


# ==============================================================================
# Stage 3: Runtime - Production image
# ==============================================================================
FROM python:3.11-slim-bookworm AS production

# Metadata
LABEL maintainer="SuperAgent Team"
LABEL description="Voice-Controlled Multi-Agent Testing System for Playwright test automation"
LABEL version="0.1.0"
LABEL architecture="multi-agent"

# Environment variables for Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/root/.local/bin:$PATH"

# Environment variables for Playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0 \
    PLAYWRIGHT_HEADLESS=true \
    PLAYWRIGHT_TIMEOUT=45000

# Environment variables for application
ENV TESTS_DIR=/app/tests \
    ARTIFACTS_DIR=/app/artifacts \
    VECTOR_DB_PATH=/app/vector_db \
    LOGS_DIR=/app/logs \
    DEBUG_MODE=false \
    LOG_LEVEL=INFO

WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Node.js and npm (for Playwright and voice integration)
    curl \
    ca-certificates \
    gnupg \
    # Playwright browser dependencies (Chromium optimized)
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    libxshmfence1 \
    # Video recording support
    ffmpeg \
    # Networking and debugging tools
    redis-tools \
    iputils-ping \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 18 LTS
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy Node.js dependencies from node-builder
COPY --from=node-builder /build/voice/node_modules /app/agent_system/voice/node_modules
COPY --from=node-builder /build/voice/dist /app/agent_system/voice/dist

# Copy application code
COPY . .

# Install Playwright browsers (Chromium only for production)
RUN npx playwright install --with-deps chromium

# Create directory structure with proper permissions
RUN mkdir -p \
    /app/tests \
    /app/artifacts/screenshots \
    /app/artifacts/videos \
    /app/artifacts/traces \
    /app/logs \
    /app/vector_db \
    /app/test-results \
    /app/playwright-report \
    /app/hitl_dashboard/static \
    && chmod -R 755 /app

# Install package in editable mode
RUN pip install --no-cache-dir -e .

# Health check - verify Redis connectivity and CLI functionality
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import sys; \
    try: \
        from agent_system.cli import main; \
        from agent_system.state.redis_client import RedisClient; \
        client = RedisClient(); \
        client.ping(); \
        print('OK'); \
        sys.exit(0); \
    except Exception as e: \
        print(f'Health check failed: {e}'); \
        sys.exit(1);" || exit 1

# Expose ports
# 8000: Observability dashboard (WebSocket events)
# 8001: HITL dashboard (human-in-the-loop UI)
# 8002: Metrics and monitoring endpoint
EXPOSE 8000 8001 8002

# Security: Create non-root user (commented out for flexibility)
# Uncomment for production deployments with strict security requirements
# RUN useradd -m -u 1000 superagent && \
#     chown -R superagent:superagent /app
# USER superagent

# Default entrypoint and command
ENTRYPOINT ["python", "-m", "agent_system.cli"]
CMD ["status"]


# ==============================================================================
# Stage 4: Development - Extended image with dev tools
# ==============================================================================
FROM production AS development

# Install development dependencies
RUN pip install --no-cache-dir \
    black==23.12.1 \
    flake8==7.0.0 \
    mypy==1.8.0 \
    pytest-cov==4.1.0 \
    pytest-mock==3.12.0 \
    ipython==8.18.1 \
    ipdb==0.13.13

# Install all Playwright browsers for comprehensive testing
RUN npx playwright install --with-deps firefox webkit

# Override environment for development
ENV DEBUG_MODE=true \
    LOG_LEVEL=DEBUG \
    PLAYWRIGHT_HEADLESS=false

# Override command for interactive development
CMD ["status"]

# ==============================================================================
# Usage Examples:
# ==============================================================================
# Build:
#   docker build -t superagent:latest .
#
# Run CLI:
#   docker run --rm superagent:latest status
#   docker run --rm superagent:latest route write_test "Create login test"
#
# Interactive shell:
#   docker run -it --rm superagent:latest /bin/bash
#
# With environment variables:
#   docker run --rm --env-file .env superagent:latest kaya "create test for checkout"
#
# With volume mounts (persist data):
#   docker run --rm \
#     -v $(pwd)/tests:/app/tests \
#     -v $(pwd)/artifacts:/app/tests/artifacts \
#     superagent:latest run tests/auth.spec.ts
# ==============================================================================
