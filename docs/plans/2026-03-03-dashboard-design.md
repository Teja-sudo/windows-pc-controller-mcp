# Settings Dashboard — Design Document

**Date:** 2026-03-03
**Status:** Approved

## Overview

Web-based settings dashboard for the Windows PC Controller MCP server. Provides a visual interface for configuration management, security controls, and audit log analytics.

## Architecture

```
python -m src.dashboard   (or: mcp-dashboard)
        │
        ▼
┌─────────────────────────────────┐
│   FastAPI (uvicorn :8765)       │
│                                 │
│  GET  /              → HTML UI  │
│  GET  /api/config    → read     │
│  PUT  /api/config    → save     │
│  POST /api/config/reset → reset │
│  GET  /api/audit     → logs     │
│  GET  /api/audit/stats → stats  │
└────────┬────────────────────────┘
         │ reads/writes
         ▼
  config/default.yaml  (read-only base)
  config/config.yaml   (user overrides)
  logs/audit.log       (read-only, JSON-lines)
```

### Key Files

| File | Purpose |
|------|---------|
| `src/dashboard/__init__.py` | FastAPI app, API routes, static file serving |
| `src/dashboard/__main__.py` | CLI entry point (`python -m src.dashboard`) |
| `src/dashboard/static/index.html` | Single self-contained HTML with inline CSS/JS |

### Launch Method

- **CLI command:** `mcp-dashboard` (from anywhere, via pyproject.toml console_scripts)
- **Module:** `python -m src.dashboard`
- Starts uvicorn on `localhost:8765`, auto-opens browser

### Config Change Model

- Dashboard saves changes to `config/config.yaml`
- Shows banner: "Restart MCP server to apply changes"
- No hot-reload / IPC to running MCP server

## Frontend Stack (CDN)

| Library | Version | Purpose | CDN Size |
|---------|---------|---------|----------|
| Shoelace | 2.x | Web components (toggles, tabs, sliders, dialogs, tooltips) | ~65KB lazy |
| Chart.js | 4.x | Line charts, bar charts for audit analytics | ~60KB |
| Tippy.js | 6.x | Rich contextual help popovers | ~30KB |

All loaded via CDN — zero build step, zero node_modules.

### Why Shoelace

- Highest UX quality rating (8.8/10) among CDN options evaluated
- Beautiful dark theme built-in (`sl-theme-dark`)
- Web Components standard — framework-agnostic, future-proof
- Lazy autoloader — only loads components actually used
- Excellent accessibility (WCAG compliant, ARIA built-in)

## UI Design

### Theme

- Dark theme matching existing CustomTkinter popup aesthetic
- Shoelace dark theme (`sl-theme-dark`) as base
- Custom CSS variables for accent colors

### 4-Tab Layout

#### Tab 1: Tools

Toggle each of the 26 tools on/off, grouped by category:
- Screen (5): capture_screenshot, ocr_extract_text, find_on_screen, get_pixel_color, list_windows
- Mouse (5): mouse_move, mouse_click, mouse_drag, mouse_scroll, mouse_position
- Keyboard (3): keyboard_type, keyboard_hotkey, keyboard_press
- Gamepad (3): gamepad_connect, gamepad_input, gamepad_disconnect
- ADB (4): adb_tap, adb_swipe, adb_key_event, adb_shell
- System (4): launch_app, focus_window, close_window, get_system_info
- Clipboard (2): clipboard_read, clipboard_write

Each category has:
- Collapsible card with category name and tool count
- Individual `<sl-switch>` toggle per tool
- Info icon with Tippy.js popover for each tool
- Category-level "Enable All / Disable All" buttons

#### Tab 2: Security

All security settings organized in cards:

**General Security**
- Master security toggle (`security.enabled`)
- Confirm dangerous actions toggle + timeout slider
- Audit logging toggle

**Screen Masking**
- Masking toggle
- Password field masking toggle
- Blocked apps list editor (add/remove chips)
- Blocked regions editor

**Keyboard Security**
- Blocked hotkeys chip editor
- Max type length slider
- Block password fields toggle

**App Execution**
- Mode selector (allowlist/blocklist)
- Allowed/blocked apps list editor

**ADB Security**
- Allowed devices list editor
- Allowed commands list editor

**Clipboard**
- Read toggle
- Write toggle

#### Tab 3: Rate Limits

Visual rate limit controls:
- `<sl-range>` slider for each category
- Shows calls/minute value
- Categories: mouse, keyboard, screenshot, adb, gamepad
- Visual bar showing relative limits

#### Tab 4: Audit Log

Rich analytics + log viewer:

**Stats Bar**
- Total calls, allowed count, denied count, deny rate %
- Most-used tool, most-denied tool

**Charts**
- Calls over time (line chart, 24h/7d toggle)
- Denials by tool (bar chart)

**Filterable Table**
- Columns: Time, Tool, Parameters (truncated), Status (badge), Reason
- Filters: tool name dropdown, status filter, text search, time range
- Pagination

**Actions**
- Export CSV button
- Live tail toggle (auto-refresh every 5s)
- Clear filters button

## Contextual Help System

Every setting gets an info icon (`sl-icon name="info-circle"`) with a Tippy.js popover containing:

1. **What it does** — plain English explanation
2. **Why it matters** — security/UX impact, risk level
3. **Default value** — what ships out of the box
4. **Config path** — exact YAML key path
5. **Example** — real YAML config snippet

Help content is defined as a JS object in the HTML file, keyed by config path.

Example popover for `security.clipboard.read_enabled`:
```
Clipboard Read

What: Allows Claude to read your clipboard contents.

Risk: HIGH — clipboard may contain passwords, credit cards,
or sensitive text you recently copied.

Default: Disabled
Config: security.clipboard.read_enabled

Example:
  security:
    clipboard:
      read_enabled: true
```

## API Endpoints

| Method | Path | Query Params | Response |
|--------|------|-------------|----------|
| `GET` | `/` | — | `index.html` |
| `GET` | `/api/config` | — | Full merged config as JSON |
| `PUT` | `/api/config` | — | Body: partial config JSON → saves to config.yaml, returns merged |
| `POST` | `/api/config/reset` | — | Deletes config.yaml, returns defaults |
| `GET` | `/api/audit` | `limit`, `offset`, `tool`, `status`, `search`, `start`, `end` | Paginated audit entries |
| `GET` | `/api/audit/stats` | `hours` (default 24) | Summary stats + time-series data |

### Config API Details

**GET /api/config** returns the full merged config (default + user overrides):
```json
{
  "security": { ... },
  "tools": { ... },
  "_has_user_config": true,
  "_user_config_path": "config/config.yaml"
}
```

**PUT /api/config** accepts partial config and deep-merges into existing user config:
```json
{
  "tools": {
    "clipboard_read": { "enabled": true }
  }
}
```

**POST /api/config/reset** removes user config file, returns defaults.

### Audit API Details

**GET /api/audit** reads `logs/audit.log` (JSON-lines), applies filters, returns paginated:
```json
{
  "entries": [...],
  "total": 1234,
  "limit": 100,
  "offset": 0
}
```

**GET /api/audit/stats** computes aggregates:
```json
{
  "total_calls": 1234,
  "allowed": 1100,
  "denied": 134,
  "deny_rate": 10.9,
  "most_used_tool": "capture_screenshot",
  "most_denied_tool": "launch_app",
  "timeline": [
    { "hour": "2026-03-03T10:00", "allowed": 45, "denied": 3 },
    ...
  ],
  "denials_by_tool": {
    "launch_app": 50,
    "keyboard_hotkey": 30,
    ...
  }
}
```

## Dependencies

Add to `pyproject.toml`:
```toml
"fastapi>=0.115.0",
```

Note: `uvicorn` is already available via `mcp[cli]` dependency.

Add console_scripts entry:
```toml
[project.scripts]
windows-pc-controller-mcp = "src.server:main"
mcp-dashboard = "src.dashboard:main"
```

## No Changes to Existing Code

The dashboard is fully additive:
- Reads existing `config/default.yaml` and `config/config.yaml`
- Reads existing `logs/audit.log`
- Uses existing `src/config.py` load_config() for config parsing
- No modifications to MCP server, security middleware, or tools
