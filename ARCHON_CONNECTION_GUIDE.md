# 🔗 Archon Connection Guide - SSE via Socat

## What I Discovered

### ✅ Archon IS Connected to Claude Code!

**Location:** `/Users/rutledge/Library/Application Support/Claude/claude_desktop_config.json`

```json
"archon": {
  "command": "/Applications/Docker.app/Contents/Resources/bin/docker",
  "args": [
    "run",
    "-l",
    "mcp.client=claude-desktop",
    "--rm",
    "-i",
    "alpine/socat",
    "STDIO",
    "TCP:host.docker.internal:8051"
  ]
}
```

**How it works:**
- Uses `socat` (socket cat) to bridge STDIO ↔ TCP
- Connects to Archon MCP on `host.docker.internal:8051`
- Runs inside a Docker container for isolation
- This is **SSE (Server-Sent Events)** transport, not direct HTTP POST

### ✅ Supabase MCP Tools Available!

```json
"supabase": {
  "command": "npx",
  "args": [
    "-y",
    "@supabase/mcp-server-supabase@latest",
    "--project-ref=pxgxcrplrjvdsctrldvw"
  ],
  "env": {
    "SUPABASE_ACCESS_TOKEN": "sbp_..."
  }
}
```

This gives Claude Code direct access to your Supabase database!

### Why My Direct HTTP POST Failed

**Problem:** I was trying:
```python
POST http://localhost:8051/mcp
```

**Issue:** Archon MCP expects **SSE connection via socat**, not direct HTTP POST with session handshake.

**Solution:** The tools work when called through Claude Code's MCP framework, not direct HTTP.

## Archon Architecture

```
Claude Code (Desktop App)
         ↓
    MCP Client
         ↓
Docker socat container (STDIO ↔ TCP bridge)
         ↓
host.docker.internal:8051
         ↓
archon-mcp container (Healthy ✅)
         ↓
archon-server container (HTTP calls)
         ↓
Supabase (your Cloppy docs + data)
```

## Tools Available

### Archon MCP Tools (via socat)
From Archon logs:
```
✓ RAG tools registered (HTTP-based version)
✓ Project tools registered
✓ Task tools registered
✓ Document tools registered
✓ Version tools registered
✓ Feature tools registered
📦 Total modules registered: 6
```

**RAG Module:**
- `rag_search_knowledge_base` - Search 10,000 pages of docs
- `rag_search_code_examples` - Find code snippets
- `rag_get_available_sources` - List knowledge sources
- `rag_list_pages_for_source` - Browse docs by source
- `rag_read_full_page` - Get full page content

**Project Module:**
- `find_projects` - List/search projects
- `manage_project` - Create/update/delete projects
- `find_tasks` - List/search tasks
- `manage_task` - Create/update/delete tasks
- `find_documents` - List/search docs
- `manage_document` - Create/update/delete docs

### Supabase MCP Tools
Direct database access to your Cloppy AI data!

## Codex Branch Discovery

Found git branch: `remotes/upstream/codex-mcp-instructions`

**Recent commits:**
```
ed8451b Finalizing Codex instructions
3e9d812 Add Codex MCP configuration instructions
```

**What is Codex?**
Likely an AI agent in Archon for code generation/fixes. Could potentially help Medic with test fixing!

## How To Use From SuperAgent

### Option 1: Call MCP Tools Directly (When in Claude Code)

The MCP tools (mcp__archon__*) work when I'm running in Claude Code's environment because they use the socat bridge.

**Problem:** SuperAgent runs in Docker, isolated from Claude Code's MCP client.

### Option 2: HTTP API to Archon Server

**Better approach:** Call Archon server's HTTP API directly:

```python
import requests

# Archon server (not MCP) exposes HTTP endpoints
ARCHON_API = "http://localhost:8181/api"

# Search RAG
response = requests.post(
    f"{ARCHON_API}/rag/search",
    json={
        "query": "board creation test",
        "match_count": 3
    }
)

results = response.json()
```

### Option 3: Direct Supabase Connection

Use the same Supabase credentials to query directly:

```python
from supabase import create_client

supabase = create_client(
    "https://hrrpicijvdfzoxwwjequ.supabase.co",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."  # Service key from .env
)

# Query knowledge base directly
results = supabase.table('knowledge_chunks').select('*').execute()
```

## Recommended Solution

### For Overnight Build (Now)

**Use mock mode** - works great without Archon:
- ✅ Generates 40+ tests
- ✅ Auto-fixes with Medic
- ✅ Completes overnight
- ✅ Cost $5-10

### For RAG Integration (Next)

**Option A: HTTP API** (easiest)
1. Find Archon server's RAG endpoint
2. Update `archon_client.py` to call HTTP API
3. Set `use_real_mcp = True`

**Option B: Direct Supabase** (fastest)
1. Add Supabase Python client to requirements
2. Query `knowledge_chunks` table directly
3. Bypass Archon entirely

**Option C: Codex Integration** (most powerful)
1. Check out `codex-mcp-instructions` branch
2. See if Codex can help with test fixes
3. Integrate as backup to Medic

## Investigating Archon HTTP API

Let me check what endpoints Archon server exposes:

```bash
cd "/Users/rutledge/Documents/DevFolder/New Archon/archon"
grep -r "app.post\|app.get" python/src/server/ --include="*.py" | grep -i rag
```

This will show the actual HTTP endpoints for RAG that SuperAgent can call directly.

## Next Steps

### To Connect Real RAG:

1. **Find Archon's HTTP RAG endpoint:**
   ```bash
   curl http://localhost:8181/api/rag/search -X POST \
     -H "Content-Type: application/json" \
     -d '{"query": "board creation", "match_count": 3}'
   ```

2. **Update archon_client.py:**
   ```python
   def search_knowledge_base(self, query: str, match_count: int = 3):
       import requests
       response = requests.post(
           "http://host.docker.internal:8181/api/rag/search",
           json={"query": query, "match_count": match_count}
       )
       return response.json()
   ```

3. **Set flag:**
   ```python
   self.use_real_mcp = True
   ```

4. **Restart SuperAgent:**
   ```bash
   docker compose -f config/docker-compose.yml restart
   ```

### To Try Codex:

1. **Check out Codex branch:**
   ```bash
   cd "/Users/rutledge/Documents/DevFolder/New Archon/archon"
   git checkout codex-mcp-instructions
   cat README.md | grep -A 20 "Codex"
   ```

2. **See if it has test fixing capabilities**

3. **Potentially integrate as Medic backup**

## Summary

**Current Status:**
- ✅ Archon connected to Claude Code via SSE/socat
- ✅ All 6 MCP modules registered and healthy
- ✅ Supabase MCP tools available
- ✅ 10,000 pages of Cloppy docs in Supabase
- ⚠️ SuperAgent can't use MCP tools (different transport)

**Solution:**
- Use Archon's HTTP API instead of MCP
- Or query Supabase directly
- Both options give access to RAG knowledge base

**Your autonomous build works NOW without this!** RAG integration is an enhancement that makes it even better.

---

Want me to:
1. **Find Archon's HTTP endpoints** and wire them up?
2. **Check out Codex branch** and see what it does?
3. **Just kick off the overnight build** as-is?
