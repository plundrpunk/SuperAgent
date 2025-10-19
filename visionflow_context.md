# VisionFlow Application Context for Test Generation

## Application Overview
VisionFlow (Cloppy_AI) is a visual canvas application with nodes, boards, AI chat, and real-time collaboration.

## Common Data Test IDs (use these in tests)
- `board-canvas` - Main canvas area
- `create-board-btn` - Button to create new board
- `board-title-input` - Input for board name
- `node-create-btn` - Button to add new node
- `export-pdf-btn` - Export to PDF button
- `export-markdown-btn` - Export to Markdown button
- `search-input` - Global search input
- `search-filter-type` - Node type filter dropdown
- `search-filter-date` - Date range filter
- `search-results` - Search results container
- `group-create-btn` - Create group button
- `group-resize-handle` - Group resize handle
- `group-title-input` - Group name input
- `ai-chat-input` - AI chat message input
- `ai-chat-send` - Send AI chat button
- `node-{id}` - Individual node (replace {id} with actual ID)
- `group-{id}` - Individual group (replace {id} with actual ID)

## User Flows

### Board Creation Flow
1. Click `create-board-btn`
2. Enter name in `board-title-input`
3. Click save/submit
4. Verify board appears in canvas

### Export Flow
1. Have content in board
2. Click `export-pdf-btn` or `export-markdown-btn`
3. Wait for download
4. Verify file was downloaded

### Search Flow
1. Enter text in `search-input`
2. Apply filters via `search-filter-type`, `search-filter-date`
3. Verify results in `search-results`
4. Click result to navigate

### Group Management Flow
1. Click `group-create-btn`
2. Draw/define group area on canvas
3. Rename via `group-title-input`
4. Resize via `group-resize-handle`
5. Add nodes to group by drag/drop
6. Connect to AI chat for context

## Environment
- BASE_URL: Set in .env file (typically http://localhost:3000)
- Login: May require authentication first
- Database: PostgreSQL with vector search
- Redis: For real-time features

## Test Requirements
- Always use data-testid selectors
- Take screenshots after major actions
- Test both happy path and error cases
- Verify API responses when relevant
- Test real-time updates if applicable
