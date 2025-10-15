# SuperAgent - Standalone Usage Guide

Get Kaya working independently in < 5 minutes!

## Quick Start (3 steps)

```bash
# 1. Navigate to SuperAgent directory
cd /Users/rutledge/Documents/DevFolder/SuperAgent

# 2. Make sure .env file has your API key
cat .env  # Should show ANTHROPIC_API_KEY=sk-ant-...

# 3. Run Kaya!
./run_kaya.sh "fix all test failures"
```

## Common Commands

### Fix Test Failures
```bash
./run_kaya.sh "fix all test failures"
```

### Check Status
```bash
./run_kaya.sh status
```

### Write a Test
```bash
./run_kaya.sh "write a test for user login"
```

### Execute Mission
```bash
./run_kaya.sh "execute the mission"
```

### Run Tests
```bash
./run_kaya.sh "run tests in /path/to/tests"
```

## What It Does

The `run_kaya.sh` script:
- ✅ Checks for .env file with API key
- ✅ Creates virtual environment if needed
- ✅ Installs dependencies automatically
- ✅ Sets up PYTHONPATH correctly
- ✅ Runs Kaya with your command
- ✅ Shows helpful error messages

## Requirements

Only 3 things needed:
1. **Python 3.10+** - Already installed ✓
2. **API Key** - In `.env` file ✓
3. **Dependencies** - Auto-installed by script ✓

## Without the Script (Manual)

If you prefer to run manually:

```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent
source venv/bin/activate
export PYTHONPATH=$PWD
python agent_system/cli.py kaya "your command here"
```

## Working with Cloppy_AI Tests

To fix Cloppy_AI test failures:

```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent
./run_kaya.sh "fix all test failures in /Users/rutledge/Documents/DevFolder/Cloppy_Ai"
```

## Optional: Redis for Advanced Features

Redis is optional but enables:
- Event streaming dashboard
- Voice integration
- Task queue

Start Redis:
```bash
brew services start redis
# OR
redis-server
```

## Troubleshooting

### "Virtual environment not found"
Script will create it automatically, or:
```bash
python3 -m venv venv
```

### "ANTHROPIC_API_KEY not found"
Check your `.env` file:
```bash
cat .env
```

Should contain:
```
ANTHROPIC_API_KEY=sk-ant-...
```

### "Permission denied"
Make script executable:
```bash
chmod +x run_kaya.sh
```

### "Module not found"
Install dependencies:
```bash
source venv/bin/activate
pip install -e .
```

## Cost Tracking

Each run costs approximately:
- **Status check**: $0.001 (Haiku)
- **Fix test failures**: $0.10-0.50 (mostly Sonnet)
- **Write test**: $0.05-0.20 (depends on complexity)

## Advanced: GUI Quick Access

Use the GUI for one-click access:

```bash
python3 kaya_quick_access.py
```

Keyboard shortcut: **Ctrl+Shift+E**

## Next Steps

1. Try the script: `./run_kaya.sh status`
2. Fix your tests: `./run_kaya.sh "fix all test failures"`
3. Build features: `./run_kaya.sh "write a test for X"`

You're now independent! 🎉
