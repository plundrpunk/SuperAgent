# Recommended MCPs for SuperAgent & Daily Development

**MCP (Model Context Protocol)** servers extend Claude's capabilities with tools and data sources. Here are the best MCPs for your workflow:

---

## 🎯 Already Integrated

### ✅ Archon MCP (Task Management)
**Status**: Integrated into SuperAgent
**Purpose**: Persistent project and task tracking across all sessions

**What It Provides**:
- `mcp__archon__manage_project` - Create/update projects
- `mcp__archon__manage_task` - Create/update tasks
- `mcp__archon__find_tasks` - Search and filter tasks
- `mcp__archon__find_projects` - Search projects

**Why It's Essential**:
- Remembers ALL work across sessions
- Tracks agent performance metrics
- Builds knowledge base over time
- Enables weekly/monthly reviews

**Usage in SuperAgent**:
```python
from agent_system.mcp_integration import get_mcp_client

mcp = get_mcp_client()
project = mcp.create_project(name="Cloppy_AI", description="Testing & Fixes")
task = mcp.create_task(project_id=project['id'], title="Fix audio node tests")
```

---

## 🔍 Highly Recommended - Add These Next

### 1. Filesystem MCP
**Install**: Part of Claude Desktop by default
**Purpose**: Read/write files, search directories

**What It Provides**:
- `read_file` - Read any file
- `write_file` - Write/create files
- `list_directory` - Browse directories
- `search_files` - Grep-like search

**Why You Need It**:
For Kaya to **autonomously** fix Cloppy_AI issues without your intervention

**Example**:
```
You: "Kaya, add data-testid to all buttons in the app"
Kaya: [Uses filesystem MCP to find all .tsx files, adds attributes, saves]
```

### 2. GitHub MCP
**Install**: `npm install -g @modelcontextprotocol/server-github`
**Purpose**: Interact with GitHub repos, issues, PRs

**What It Provides**:
- `create_or_update_file` - Commit changes directly
- `create_pull_request` - Open PRs from command line
- `create_issue` - File issues automatically
- `search_code` - Search across repos
- `get_file_contents` - Read files from any repo

**Why You Need It**:
Kaya can **commit fixes**, create PRs, and manage issues automatically

**Example**:
```
You: "Kaya, commit today's fixes and create PR"
Kaya: [Uses GitHub MCP to commit, push, and open PR with description]
```

### 3. Brave Search MCP (Already Available!)
**Status**: You already have this configured!
**Tools**: `mcp__server-brave-search__brave_web_search`, `mcp__server-brave-search__brave_local_search`

**What It Provides**:
- Web search for latest docs, Stack Overflow, etc.
- Local business search

**Why You Need It**:
When Kaya encounters unknown errors, she can **search for solutions**

**Example**:
```
Test fails with "WebSocket connection refused"
Kaya: [Searches Brave for "Playwright WebSocket connection refused fix"]
```

### 4. Postgres MCP
**Install**: `npm install -g @modelcontextprotocol/server-postgres`
**Purpose**: Query and manage PostgreSQL databases

**What It Provides**:
- `query` - Run SQL queries
- `list_tables` - Show database schema
- `describe_table` - Get table details

**Why You Need It**:
If Cloppy_AI has database tests, Kaya can validate data integrity

**Example**:
```
You: "Kaya, check if user registration is saving to database"
Kaya: [Queries users table to verify]
```

### 5. Memory MCP
**Install**: `npm install -g @modelcontextprotocol/server-memory`
**Purpose**: Long-term memory storage across conversations

**What It Provides**:
- `store_memory` - Save facts/preferences
- `retrieve_memory` - Recall past context
- `search_memory` - Find related memories

**Why You Need It**:
Kaya remembers your preferences, coding style, and past decisions

**Example**:
```
You: "I prefer functional components over class components"
[Memory stored]

Later:
Kaya: [Generates functional components automatically]
```

---

## 💼 Specialized MCPs for Your Workflow

### 6. Puppeteer MCP
**Install**: `npm install -g @modelcontextprotocol/server-puppeteer`
**Purpose**: Browser automation (alternative to Playwright)

**What It Provides**:
- `navigate` - Go to URL
- `screenshot` - Capture page state
- `click` - Interact with elements
- `evaluate` - Run JavaScript in browser

**Why Consider It**:
Cross-validation with Gemini - run tests in **both** Playwright and Puppeteer

### 7. Slack MCP
**Install**: `npm install -g @modelcontextprotocol/server-slack`
**Purpose**: Send messages, read channels, manage workspace

**What It Provides**:
- `send_message` - Post to channels
- `list_channels` - Browse workspace
- `read_thread` - Get conversation history

**Why You Need It**:
Kaya can **notify you** when tests pass/fail, even when you're not at computer

**Example**:
```
Test run completes:
Kaya: [Sends Slack message] "✅ All 207 P0 tests passing!"
```

### 8. Google Drive MCP
**Install**: `npm install -g @modelcontextprotocol/server-gdrive`
**Purpose**: Read/write Google Docs, Sheets, Drive files

**What It Provides**:
- `read_file` - Read docs/sheets
- `write_file` - Create/update files
- `list_files` - Browse Drive
- `search_files` - Find files

**Why Consider It**:
Export test reports to Google Sheets for stakeholders

---

## 🚀 Advanced MCPs (Later)

### 9. Sequential Thinking MCP
**Install**: `npm install -g @modelcontextprotocol/server-sequential-thinking`
**Purpose**: Extended reasoning for complex problems

**Why Consider It**:
When Kaya faces very complex architectural decisions

### 10. EverArt MCP
**Install**: `npm install -g @modelcontextprotocol/server-everart`
**Purpose**: Generate images with AI

**Why Consider It**:
Generate placeholder images, design mockups for UI

### 11. AWS KB Retrieval MCP
**Install**: `npm install -g @modelcontextprotocol/server-aws-kb-retrieval`
**Purpose**: Query AWS Knowledge Base

**Why Consider It**:
If you build a knowledge base of your codebase patterns

---

## 📦 Installation & Setup

### Quick Install (Top 5 Essentials)

```bash
# 1. Filesystem (usually pre-installed with Claude Desktop)
# Check if available: look for "read_file" in Claude's tools

# 2. GitHub MCP
npm install -g @modelcontextprotocol/server-github

# Configure in claude_desktop_config.json:
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "your_token_here"
      }
    }
  }
}

# 3. Brave Search (already configured!)

# 4. Memory MCP
npm install -g @modelcontextprotocol/server-memory

# Configure:
{
  "memory": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-memory"]
  }
}

# 5. Slack (optional but useful)
npm install -g @modelcontextprotocol/server-slack

# Configure:
{
  "slack": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-slack"],
    "env": {
      "SLACK_BOT_TOKEN": "xoxb-your-token",
      "SLACK_TEAM_ID": "your-team-id"
    }
  }
}
```

### Configuration File Location
**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux**: `~/.config/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

---

## 🎯 Recommended Priority for SuperAgent

### Phase 1: Core Functionality (Do Now)
1. ✅ **Archon MCP** - Already integrated
2. ✅ **Brave Search MCP** - Already configured
3. 🔜 **Filesystem MCP** - Enable Kaya to fix files autonomously
4. 🔜 **GitHub MCP** - Let Kaya commit and create PRs

### Phase 2: Enhanced Workflow (This Week)
5. **Memory MCP** - Remember preferences and patterns
6. **Slack MCP** - Get notified of test results

### Phase 3: Advanced Features (Later)
7. **Puppeteer MCP** - Cross-browser validation
8. **Google Drive MCP** - Share reports with stakeholders

---

## 💡 How MCPs Transform Your Workflow

### Before MCPs:
```
You: "Kaya, fix the audio node tests"
Kaya: "Here's what needs to be done: [lists steps]"
You: [Manually make changes]
You: "Kaya, commit these changes"
Kaya: "Here's the commit message: [suggests text]"
You: [Manually git commit]
```

### After MCPs (Filesystem + GitHub):
```
You: "Kaya, fix the audio node tests and commit"
Kaya: [Uses Filesystem MCP to read files, make changes, save]
Kaya: [Uses GitHub MCP to commit and push]
Kaya: "✅ Fixed audio node tests. Committed as: 'fix: add data-testid to audio nodes'"
```

### With Full Stack (+ Slack + Memory):
```
You: "Kaya, work on Cloppy_AI until all tests pass. Notify me on Slack."
[You go to lunch]

Kaya: [Runs tests, identifies failures, searches Brave for solutions]
Kaya: [Uses Filesystem to fix issues, commits via GitHub]
Kaya: [Re-runs tests, validates fixes]
Kaya: [Sends Slack message] "🎉 Fixed 47 test failures. Pass rate now 85%!"

You: [Returns from lunch] "Holy shit, it works!"
```

---

## 🛠️ Troubleshooting MCPs

### MCP Not Showing Up
1. Check `claude_desktop_config.json` is valid JSON
2. Restart Claude Desktop completely (quit + reopen)
3. Check logs: `~/Library/Logs/Claude/mcp*.log`

### MCP Tool Not Working
1. Verify environment variables are set correctly
2. Check API tokens haven't expired
3. Test the MCP server manually: `npx @modelcontextprotocol/server-github`

### Too Many MCPs Slowing Down Claude
- Only enable MCPs you actively use
- Disable unused MCPs by commenting out in config
- MCPs are loaded on-demand, so having many is OK

---

## 📊 MCP Performance Impact

| MCP | Startup Time | Per-Call Latency | Cost Impact |
|-----|--------------|------------------|-------------|
| Archon | ~50ms | ~100ms | None (local) |
| Brave Search | ~100ms | ~200ms | None (free) |
| Filesystem | ~10ms | ~50ms | None (local) |
| GitHub | ~200ms | ~300ms | None (API free tier) |
| Memory | ~50ms | ~100ms | None (local) |
| Slack | ~150ms | ~250ms | None (free tier) |

**Net Impact**: Negligible - MCPs make Kaya **faster** by reducing back-and-forth

---

## 🎉 Next Steps

1. **Today**: Enable Filesystem MCP for autonomous fixes
2. **This Week**: Add GitHub MCP for auto-commits
3. **This Month**: Add Memory MCP for long-term learning
4. **Future**: Explore specialized MCPs as needs arise

With these MCPs, Kaya becomes a **true autonomous agent** that can:
- Fix bugs without supervision
- Commit and push code
- Search for solutions
- Remember your preferences
- Notify you of progress
- Build institutional knowledge

**You'll literally be able to say "Kaya, fix Cloppy_AI" and go get coffee.** ☕

---

**Last Updated**: October 14, 2025
**See Also**: DAILY_AGENT_SETUP.md, MCP_INTEGRATION_GUIDE.md
