# SuperAgent Utility Scripts

This directory contains utility scripts for testing, validation, and development. These are not required for normal operation of SuperAgent.

## Main Operational Scripts (In Root Directory)

For normal SuperAgent operations, use these scripts in the root directory:

- **[../start_superagent.sh](../start_superagent.sh)** - Start all SuperAgent services (dashboard, WebSocket, etc.)
- **[../run_kaya.sh](../run_kaya.sh)** - Run Kaya commands directly
- **[../dashboard_server.py](../dashboard_server.py)** - HTTP dashboard server (port 8080)
- **[../websocket_server.py](../websocket_server.py)** - WebSocket event streaming (port 3010)
- **[../kaya_quick_access.py](../kaya_quick_access.py)** - GUI interface for Kaya commands

## Validation Scripts

Scripts to validate system configuration and setup:

- **[validate-docker.sh](./validate-docker.sh)** - Validate Docker configuration without starting services
  ```bash
  ./scripts/validate-docker.sh
  ```

- **[validate_gemini_setup.py](./validate_gemini_setup.py)** - Verify Gemini agent configuration and API access
  ```bash
  python scripts/validate_gemini_setup.py
  ```

- **[validate_metrics.py](./validate_metrics.py)** - Verify metrics collection and aggregation
  ```bash
  python scripts/validate_metrics.py
  ```

- **[validate_yamls.py](./validate_yamls.py)** - Validate YAML configuration files syntax
  ```bash
  python scripts/validate_yamls.py
  ```

## Test Scripts

Scripts to test specific features and functionality:

- **[test_new_features.sh](./test_new_features.sh)** - Test visible browsers, screenshot streaming, coverage analysis
  ```bash
  ./scripts/test_new_features.sh
  ```

- **[test_kaya_voice.sh](./test_kaya_voice.sh)** - Test Kaya voice integration
  ```bash
  ./scripts/test_kaya_voice.sh
  ```

- **[TEST_VOICE_NOW.sh](./TEST_VOICE_NOW.sh)** - Quick voice integration test
  ```bash
  ./scripts/TEST_VOICE_NOW.sh
  ```

- **[test_lifecycle_demo.py](./test_lifecycle_demo.py)** - Demo lifecycle management features
  ```bash
  python scripts/test_lifecycle_demo.py
  ```

## Development/Demo Scripts

Scripts for development, demos, and specialized use cases:

- **[docker-start.sh](./docker-start.sh)** - Alternative Docker startup script with custom options
  ```bash
  ./scripts/docker-start.sh
  ```

- **[start_event_stream.py](./start_event_stream.py)** - Start event stream server standalone
  ```bash
  python scripts/start_event_stream.py
  ```

- **[talk_to_kaya.py](./talk_to_kaya.py)** - Simple CLI interface for talking to Kaya
  ```bash
  python scripts/talk_to_kaya.py
  ```

- **[run_documentation_summary.sh](./run_documentation_summary.sh)** - Generate documentation summaries
  ```bash
  ./scripts/run_documentation_summary.sh
  ```

## Cloppy AI Test Scripts

Scripts specific to the Cloppy AI test suite generation:

- **[generate_cloppy_tests.py](./generate_cloppy_tests.py)** - Generate tests for Cloppy AI features
  ```bash
  python scripts/generate_cloppy_tests.py
  ```

- **[run_cloppy_tests.py](./run_cloppy_tests.py)** - Run Cloppy AI test suite
  ```bash
  python scripts/run_cloppy_tests.py
  ```

## Usage Guidelines

### For Normal Operations
Use the scripts in the root directory:
```bash
# Start SuperAgent system
./start_superagent.sh

# Run Kaya commands
./run_kaya.sh "write a test for user login"
./run_kaya.sh "status"
```

### For Validation/Testing
Use scripts in this directory:
```bash
# Validate Docker setup
./scripts/validate-docker.sh

# Test new features
./scripts/test_new_features.sh

# Verify metrics
python scripts/validate_metrics.py
```

### Development
Scripts in this directory are useful for:
- Validating configuration before deployment
- Testing specific features in isolation
- Debugging issues
- Development and experimentation

## Environment Requirements

Most scripts assume:
- You're running from the SuperAgent root directory
- Python virtual environment is available (`venv/`)
- Required dependencies are installed (`requirements.txt`)
- Environment variables are configured (`.env`)

## Related Documentation

- [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md) - Deployment guide
- [docs/TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md) - Troubleshooting
- [QUICK_START.md](../QUICK_START.md) - Quick start guide
- [README.md](../README.md) - Project overview

---

**Last Updated**: October 19, 2025
