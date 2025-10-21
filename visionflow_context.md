# VisionFlow Application Context for Test Generation

## Application Overview
VisionFlow (Cloppy_AI) is a visual canvas application with nodes, boards, AI chat, and real-time collaboration.

## IMPORTANT: Selector Strategy
**This app does NOT use data-testid attributes.** Use CSS class selectors and semantic locators instead.

## Common Selectors (use these in tests)

### Login Page
- `input[type="email"]` - Email input on login page
- `input[type="password"]` - Password input on login page
- `button[type="submit"]` - Login submit button

### Dashboard / Boards
- `.vf-board-canvas` - Main canvas area
- `.vf-board-glow-button` - Button to create new board (has text "Create New Board")
- `input#boardName` - Input for board name in create modal
- `.vf-toolbar-row button` - Toolbar buttons for adding nodes
- `.vf-dashboard-card` - Board cards in dashboard list
- `.vf-dashboard-grid` - Grid container for boards
- Button containing "Export" text - Export buttons
- Input with placeholder containing "search" - Search input

## Key Pages & Routes
- `/` or `/boards` - Dashboard with board list (requires login)
- `/board/:id` - Individual board canvas view
- `/dashboard/usage` - Usage dashboard
- `/mcp-store` - MCP store

## User Flows

### Board Creation Flow
1. Start at `/` or `/boards` page
2. Click button with class `.vf-board-glow-button` (text: "Create New Board")
3. Wait for modal to appear
4. Enter name in `input#boardName`
5. Click submit button (gradient purple/blue button)
6. Wait for navigation to `/board/:id`
7. Verify `.vf-board-canvas` is visible

### Node Creation Flow (on board page)
1. Be on `/board/:id` page
2. Click one of the node type buttons in `.vf-toolbar-row`
3. Node types: TEXT, IMAGE, VIDEO, PDF, AUDIO, WEBSITE, AI_CHAT, FOLDER, COMPUTER_USE
4. Verify node appears on canvas

### Export Flow
1. Have content in board
2. Look for button containing "Export" text
3. Click and wait for download
4. Verify file was downloaded

## Authentication
- App requires login - ALWAYS handle auth first in tests
- Test credentials: `process.env.TEST_EMAIL` / `process.env.TEST_PASSWORD`
- Login flow:
  1. Navigate to BASE_URL (will redirect to login if not authenticated)
  2. Fill email input with `process.env.TEST_EMAIL`
  3. Fill password input with `process.env.TEST_PASSWORD`
  4. Click submit/login button
  5. Wait for redirect to dashboard/boards page
- After login, you can access boards and canvas

## Environment
- BASE_URL: http://host.docker.internal:5175
- Backend: http://localhost:3010
- Database: PostgreSQL with vector search
- Redis: For real-time features

## Test Requirements
- Use CSS class selectors (`.vf-*` classes) or semantic Playwright locators
- Use `page.getByRole()`, `page.getByText()` for buttons/labels
- Take screenshots after major actions
- Test both happy path and error cases
- Handle authentication if needed
- Wait for network idle on page loads
