# Next Session Instructions - Archon Integration

## Current Status
- ✅ Kaya intent parser FIXED (handles colon-separated commands)
- ✅ Supabase Python client installed in Docker
- ✅ Correct Supabase credentials in .env (service_role key verified by user)
- ⏸️ Need to implement full Archon integration (projects, tasks, RAG)

## What Was Fixed This Session
1. **Kaya Parser Bug**: Commands like `"build me X: Y, Z"` were mis-parsing as 'validate' instead of 'build_feature'
   - Fixed in [agent_system/agents/kaya.py:36-102](agent_system/agents/kaya.py:36-102)
   - Reordered INTENT_PATTERNS to prioritize build_feature
2. **Supabase Setup**: Added supabase>=2.0.0 to requirements.txt, rebuilt Docker
3. **Credentials**: Added correct service_role key to .env

## Critical Issue: Background Processes
**IMPORTANT**: There are 5 phantom background bash processes that show as "running" but their containers were deleted. They are NOT actually burning money (verified with `ps aux | grep python` showing no processes). They're just orphaned shell wrappers. Ignore the system warnings about them.

## What Needs to Happen Next

### Step 1: Verify Archon Supabase Connection
The user confirmed the Supabase key is CORRECT for `hrrpicijvdfzoxwwjequ.supabase.co`. Test what tables exist:

```bash
# Start containers (should already be up)
docker compose -f config/docker-compose.yml up -d

# Run the test script (already created at /tmp/test_archon_tables.py)
docker compose -f config/docker-compose.yml exec -T superagent python /tmp/test_archon_tables.py
```

This will show which tables exist in Archon's Supabase (projects, tasks, knowledge_base, etc.)

### Step 2: Implement Full Archon Integration
Once you know the table schemas, update [agent_system/archon_client.py](agent_system/archon_client.py) to use Supabase for:

1. **create_project()** - Insert into `projects` table
2. **create_task()** - Insert into `tasks` table
3. **update_task()** - Update `tasks` table status
4. **search_knowledge_base()** - Already implemented, just needs table name verification

Replace the mock `return` statements (lines 49-50, 90-91, etc.) with real Supabase queries.

### Step 3: Test Integration
```bash
# Test project creation
docker compose -f config/docker-compose.yml exec -T superagent python -c "
from agent_system.archon_client import ArchonClient
client = ArchonClient()
result = client.create_project('Test Project', 'Testing Archon integration')
print(result)
"

# Test RAG search
docker compose -f config/docker-compose.yml exec -T superagent python -c "
from agent_system.archon_client import ArchonClient
client = ArchonClient()
result = client.search_knowledge_base('board creation test', 3)
print(result)
"
```

### Step 4: Run Overnight Build
Once Archon integration is working:
```bash
./kickoff_overnight_build.sh
```

This will:
- Generate 40+ Playwright tests
- Track progress in Archon (visible at http://localhost:3737)
- Use RAG to help Medic fix tests with real Cloppy examples
- Cost ~$5-10
- Take 2-4 hours

## Key Files Modified This Session
- [agent_system/agents/kaya.py](agent_system/agents/kaya.py:36-102) - Parser fix
- [agent_system/archon_client.py](agent_system/archon_client.py:201-238) - RAG implementation (needs projects/tasks)
- [requirements.txt](requirements.txt:28) - Added supabase>=2.0.0
- [.env](.env:100-102) - Supabase credentials

## Environment Variables (.env)
```bash
SUPABASE_URL=https://hrrpicijvdfzoxwwjequ.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhycnBpY2lqdmRmem94d3dqZXF1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1OTc2NzY3NiwiZXhwIjoyMDc1MzQzNjc2fQ.nVMlg2_ujROsimBZHphYX_TaJnUtadL3wG7eFBPZcT8

BASE_URL=http://host.docker.internal:5175
TEST_EMAIL=admin@cloppy.ai
TEST_PASSWORD=admin123
```

## Why This Matters
Without Archon integration:
- ❌ No visibility into overnight build progress
- ❌ Medic can't learn from real Cloppy examples (RAG)
- ❌ No task tracking/management
- ❌ Can't see what tests passed/failed

With Archon integration:
- ✅ Full visibility at http://localhost:3737
- ✅ Medic learns from 10,000 pages of Cloppy docs
- ✅ Track all 40+ tests being generated
- ✅ See real-time progress during overnight build

## User's Goal
Run an autonomous overnight build that:
1. Generates 40+ comprehensive Playwright tests
2. Auto-fixes failures with Medic (using RAG examples)
3. Provides full visibility in Archon UI
4. Completes in 2-4 hours with 95%+ pass rate
5. Costs ~$5-10 total

The user has already run it 3 times WITHOUT Archon and it just wasted money because Medic couldn't learn from examples. That's why we MUST get Archon working first.

## Next Agent: Start Here
1. Read this file
2. Run `/tmp/test_archon_tables.py` to see what tables exist
3. Implement project/task creation in archon_client.py
4. Test the integration
5. Run overnight build

Good luck! 🚀
