# HITL Dashboard UI Screenshots & Visual Guide

This document describes the visual appearance and layout of the HITL Dashboard UI.

## Main Dashboard View

### Header Section
```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  HITL Dashboard                                                 │
│  Human-in-the-Loop Queue Management                            │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │    12    │  │     8    │  │     5    │  │   0.68   │      │
│  │  Active  │  │ Resolved │  │High Prior│  │Avg Prior │      │
│  │  Tasks   │  │          │  │          │  │          │      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Stats Cards Display**:
- Active Tasks: Total unresolved tasks in queue
- Resolved: Total resolved tasks (24h window)
- High Priority: Tasks with priority > 0.7
- Avg Priority: Average priority score (0.0-1.0)

### Controls Bar
```
┌─────────────────────────────────────────────────────────────────┐
│  [Refresh Queue]  ☐ Show Resolved Tasks                        │
└─────────────────────────────────────────────────────────────────┘
```

**Controls**:
- Blue "Refresh Queue" button to reload data
- Checkbox to toggle visibility of resolved tasks

### Task Queue List

#### High Priority Task Card (Red Badge)
```
┌─────────────────────────────────────────────────────────────────┐
│  User Authentication - Login Flow            [HIGH]  [PENDING]  │
│  task_001                                                        │
│                                                                  │
│  Attempts: 3  |  Created: 2 hours ago  |  Reason: max_retries  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Error: Selector 'button[data-testid="login-submit"]' not...││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Task Card Elements**:
- **Title**: Feature name (bold, 18px)
- **Task ID**: Small gray monospace text
- **Priority Badge**: Color-coded (red=high, yellow=medium, blue=low)
- **Status Badge**: "Pending" or "Resolved"
- **Meta Info**: Attempts, timestamp, escalation reason
- **Error Preview**: Truncated error in red box (100px max height)

#### Medium Priority Task Card (Yellow Badge)
```
┌─────────────────────────────────────────────────────────────────┐
│  Shopping Cart - Add Item                 [MEDIUM]  [PENDING]  │
│  task_003                                                        │
│                                                                  │
│  Attempts: 2  |  Created: 45 minutes ago  |  Reason: low_conf  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ AssertionError: Expected 1 but received 0                  ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Resolved Task Card (Grayed Out)
```
┌─────────────────────────────────────────────────────────────────┐
│  Profile Settings - Update Email           [LOW]  [RESOLVED]   │
│  task_004                                 (opacity: 0.6)        │
│                                                                  │
│  Attempts: 1  |  Created: 15 minutes ago  |  Reason: regression│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Resolved Tasks**:
- Lighter background (gray)
- 60% opacity
- Green "Resolved" badge
- No hover effect

### Empty State
```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│                                                                  │
│                    No tasks in queue                            │
│                                                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Task Detail Modal

Clicking any task card opens a modal with full details:

### Modal Header
```
┌────────────────────────────────────────────────────────────── × ┐
│                                                                  │
│  User Authentication - Login Flow                               │
│                                                                  │
```

**Modal Structure**:
- Close button (×) in top-right
- Scrollable content
- 90% width, max 1000px
- Centered on screen

### Task Information Section
```
│  ────────────────────────────────────────────────────────────  │
│  Task Information                                               │
│  ────────────────────────────────────────────────────────────  │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Task ID      │  │ Priority     │  │ Attempts     │         │
│  │ task_001     │  │ 0.75 (High)  │  │ 3            │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Severity     │  │ Created At   │  │ Escalation   │         │
│  │ high         │  │ 2hrs ago     │  │ max_retries  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                  │
```

**Detail Items**:
- Light gray background boxes
- Grid layout (3 columns)
- Label in uppercase (small, gray)
- Value in normal text (14px)

### Test Information Section
```
│  ────────────────────────────────────────────────────────────  │
│  Test Information                                               │
│  ────────────────────────────────────────────────────────────  │
│                                                                  │
│  ┌──────────────────────────────┐  ┌──────────────────────┐  │
│  │ Test File                    │  │ Logs                 │  │
│  │ tests/auth/login.spec.ts     │  │ logs/login_test.log  │  │
│  └──────────────────────────────┘  └──────────────────────┘  │
│                                                                  │
```

### Error Message Section
```
│  ────────────────────────────────────────────────────────────  │
│  Error Message                                                  │
│  ────────────────────────────────────────────────────────────  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ Error: Selector 'button[data-testid="login-submit"]'       ││
│  │ not found                                                   ││
│  │   at Page.click (playwright/lib/page.js:1234)              ││
│  │   at test (login.spec.ts:45:18)                            ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                  │
```

**Code Block Style**:
- Dark background (#1e1e1e)
- Light text (#d4d4d4)
- Monospace font (Courier New)
- Scrollable (max 300px height)

### AI Diagnosis Section
```
│  ────────────────────────────────────────────────────────────  │
│  AI Diagnosis                                                   │
│  ────────────────────────────────────────────────────────────  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ The login button selector has changed. The data-testid     ││
│  │ attribute may have been modified in the latest deploy.     ││
│  │                                                             ││
│  │ Confidence: 0.65                                           ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                  │
```

### Code Changes Section
```
│  ────────────────────────────────────────────────────────────  │
│  Code Changes                                                   │
│  ────────────────────────────────────────────────────────────  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ - await page.click('button.login-btn');                    ││
│  │ + await page.click('button[data-testid="login-submit"]');  ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                  │
```

### Screenshots Section
```
│  ────────────────────────────────────────────────────────────  │
│  Screenshots                                                    │
│  ────────────────────────────────────────────────────────────  │
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │
│  │                │  │                │  │                │  │
│  │  [Screenshot]  │  │  [Screenshot]  │  │  [Screenshot]  │  │
│  │                │  │                │  │                │  │
│  ├────────────────┤  ├────────────────┤  ├────────────────┤  │
│  │ artifacts/...  │  │ artifacts/...  │  │ artifacts/...  │  │
│  └────────────────┘  └────────────────┘  └────────────────┘  │
│                                                                  │
```

**Screenshot Grid**:
- Grid layout (auto-fill, min 200px)
- Placeholder for image display
- File path shown below each
- Border and padding

### Attempt History Section
```
│  ────────────────────────────────────────────────────────────  │
│  Attempt History                                                │
│  ────────────────────────────────────────────────────────────  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ Attempt 1                                                   ││
│  │ 2025-10-14 10:00:00                                        ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ Attempt 2                                                   ││
│  │ 2025-10-14 10:30:00                                        ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ Attempt 3                                                   ││
│  │ 2025-10-14 11:00:00                                        ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                  │
```

**Attempt Items**:
- Light gray boxes
- Blue left border (3px)
- Attempt number in bold
- Timestamp in small gray text

## Annotation Form (For Unresolved Tasks)

### Form Section
```
│  ────────────────────────────────────────────────────────────  │
│  Resolve Task                                                   │
│  ────────────────────────────────────────────────────────────  │
│                                                                  │
│  Root Cause Category *                                          │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ Selector Flaky                                        ▼    ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Fix Strategy *                                                 │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ Update Selectors                                      ▼    ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Severity *                                                     │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ Medium                                                ▼    ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Human Notes *                                                  │
│  ┌────────────────────────────────────────────────────────────┐│
│  │                                                             ││
│  │ The login button selector changed in recent deploy.        ││
│  │ Updated test to use data-testid attribute instead of       ││
│  │ CSS class selector for better stability.                   ││
│  │                                                             ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Patch/Diff (Optional)                                          │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ - await page.click('.login-btn');                          ││
│  │ + await page.click('[data-testid="login-submit"]');        ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                  │
│                            [Cancel]  [Resolve Task]             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Form Elements**:
- Dropdown selects for categories
- Large textarea for notes (min 100px)
- Optional patch/diff textarea
- Cancel and Resolve buttons aligned right
- Green "Resolve Task" button

### Form Field Styling
- Labels: Bold, 13px, uppercase
- Inputs: White background, 1px border
- Focus: Blue border, subtle shadow
- Required fields marked with *

## Resolved Task View

For already resolved tasks, form is replaced with:

```
│  ────────────────────────────────────────────────────────────  │
│  Resolution Details                                             │
│  ────────────────────────────────────────────────────────────  │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Root Cause   │  │ Fix Strategy │  │ Severity     │         │
│  │ selector_... │  │ update_sel...│  │ medium       │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                  │
│  ┌──────────────┐                                               │
│  │ Resolved At  │                                               │
│  │ 1hr ago      │                                               │
│  └──────────────┘                                               │
│                                                                  │
│  Human Notes                                                    │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ The login button selector changed in recent deploy...      ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Applied Patch                                                  │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ - await page.click('.login-btn');                          ││
│  │ + await page.click('[data-testid="login-submit"]');        ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Color Scheme

### Primary Colors
- **Primary Blue**: #4a90e2 (buttons, links, highlights)
- **Success Green**: #52c41a (success messages, resolved)
- **Warning Yellow**: #faad14 (medium priority, warnings)
- **Danger Red**: #f5222d (high priority, errors)

### Neutral Colors
- **Text Primary**: #2c3e50 (main text)
- **Text Secondary**: #7f8c8d (labels, meta info)
- **Background Light**: #f5f7fa (page background)
- **Background White**: #ffffff (cards, modal)
- **Border**: #e1e8ed (card borders, dividers)

### Priority Badge Colors
- **High Priority**: Red background (#fee), red text (#f5222d)
- **Medium Priority**: Yellow background (#ffeaa7), orange text (#d97706)
- **Low Priority**: Blue background (#e3f2fd), blue text (#4a90e2)

## Responsive Design

### Desktop (> 768px)
- Stats: 4 columns
- Task cards: Full width with detailed meta
- Modal: 90% width, max 1000px
- Detail grid: 3 columns

### Tablet (768px)
- Stats: 2 columns
- Task meta: Vertical layout
- Detail grid: 2 columns

### Mobile (< 768px)
- Stats: 2 columns
- Controls: Vertical stack
- Task meta: Vertical layout
- Modal: 95% width
- Detail grid: 1 column

## Interaction States

### Hover Effects
- **Task Card**: Elevation shadow, blue border
- **Button**: Darker shade, subtle shadow
- **Close Button**: Darker text

### Focus States
- **Form Inputs**: Blue border, light blue shadow
- **Buttons**: Outline for accessibility

### Loading State
```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│                          ⟳                                      │
│                    Loading tasks...                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Spinner**: Rotating circle animation, blue accent

## Accessibility Features

- Semantic HTML elements
- Proper heading hierarchy
- Form labels associated with inputs
- Keyboard navigation support
- Focus indicators
- Color contrast compliance (WCAG AA)

## Typography

- **Font Family**: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto
- **Base Size**: 14px
- **Line Height**: 1.6
- **Headings**: 600 weight
- **Code**: 'Courier New', monospace

## Summary

The HITL Dashboard features:
- Clean, modern design with card-based layout
- Priority-based color coding
- Comprehensive task detail modal
- User-friendly annotation form
- Responsive for various screen sizes
- Professional color scheme
- Accessible and keyboard-friendly

All UI elements are designed for clarity and efficiency in reviewing and resolving escalated test failures.
