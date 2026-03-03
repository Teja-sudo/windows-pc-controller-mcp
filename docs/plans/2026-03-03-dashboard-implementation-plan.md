# Settings Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a web-based settings dashboard with FastAPI backend, Shoelace Web Components UI, and rich audit log analytics.

**Architecture:** FastAPI serves REST API endpoints (config CRUD + audit read) and a single self-contained HTML file. The HTML uses Shoelace (CDN) for UI components, Chart.js for analytics, and Tippy.js for contextual help popovers. Launched via `mcp-dashboard` CLI command or `python -m src.dashboard`.

**Tech Stack:** Python 3.12, FastAPI, uvicorn (already in deps), Shoelace 2.x (CDN), Chart.js 4.x (CDN), Tippy.js 6.x (CDN)

**Design Doc:** `docs/plans/2026-03-03-dashboard-design.md`

---

### Task 1: Setup — Dependencies, Directory Structure, Entry Point

**Files:**
- Modify: `pyproject.toml`
- Create: `src/dashboard/__init__.py`
- Create: `src/dashboard/__main__.py`
- Test: `tests/test_dashboard.py`

**Step 1: Update pyproject.toml**

Add `fastapi` to dependencies and `mcp-dashboard` to console_scripts:

```toml
# In [project] dependencies, add:
"fastapi>=0.115.0",

# In [project.scripts], add:
mcp-dashboard = "src.dashboard:main"
```

**Step 2: Create directory structure**

```
src/dashboard/
  __init__.py     # FastAPI app factory + routes
  __main__.py     # CLI entry point
  static/
    index.html    # Dashboard UI (created in later tasks)
```

**Step 3: Write minimal FastAPI app in `src/dashboard/__init__.py`**

```python
"""Settings Dashboard — FastAPI backend for config management and audit viewing."""
from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from src.config import load_config, _deep_merge

STATIC_DIR = Path(__file__).parent / "static"
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
LOG_DIR = Path(__file__).parent.parent.parent / "logs"

DEFAULT_YAML = CONFIG_DIR / "default.yaml"
USER_YAML = CONFIG_DIR / "config.yaml"
AUDIT_LOG = LOG_DIR / "audit.log"


def create_app() -> FastAPI:
    """Create the FastAPI dashboard application."""
    app = FastAPI(title="MCP Dashboard", version="0.1.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        html_path = STATIC_DIR / "index.html"
        if not html_path.exists():
            return HTMLResponse("<h1>Dashboard UI not found</h1>", status_code=404)
        return HTMLResponse(html_path.read_text(encoding="utf-8"))

    return app


def main():
    """Entry point for the dashboard CLI."""
    app = create_app()
    webbrowser.open("http://localhost:8765")
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
```

**Step 4: Write `src/dashboard/__main__.py`**

```python
"""Allow running as: python -m src.dashboard"""
from src.dashboard import main

if __name__ == "__main__":
    main()
```

**Step 5: Create placeholder `src/dashboard/static/index.html`**

```html
<!DOCTYPE html>
<html><body><h1>MCP Dashboard — Loading...</h1></body></html>
```

**Step 6: Write tests in `tests/test_dashboard.py`**

```python
"""Tests for the dashboard FastAPI backend."""
import sys
import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


class TestCreateApp:
    def test_app_creates_successfully(self):
        from src.dashboard import create_app
        app = create_app()
        assert app.title == "MCP Dashboard"

    def test_index_route_registered(self):
        from src.dashboard import create_app
        app = create_app()
        routes = [r.path for r in app.routes]
        assert "/" in routes

    def test_main_function_exists(self):
        from src.dashboard import main
        assert callable(main)
```

**Step 7: Install deps and run tests**

```bash
cd "C:/Users/sanik_unwtxkj/MyProjects/MCP servers/windows-pc-controller-mcp"
.venv/Scripts/pip install fastapi
.venv/Scripts/python -m pytest tests/test_dashboard.py -v
```
Expected: 3 PASS

**Step 8: Commit**

```bash
git add pyproject.toml src/dashboard/ tests/test_dashboard.py
git commit -m "feat: add dashboard scaffolding with FastAPI app and CLI entry point"
```

---

### Task 2: Config API Endpoints

**Files:**
- Modify: `src/dashboard/__init__.py`
- Test: `tests/test_dashboard.py`

**Context:** The config API reads/writes YAML files. `GET /api/config` returns the merged config. `PUT /api/config` deep-merges into user config.yaml. `POST /api/config/reset` deletes user config.yaml.

**Step 1: Add tests for config endpoints**

Add to `tests/test_dashboard.py`:

```python
from unittest.mock import patch, mock_open
import json
import yaml


class TestConfigAPI:
    def _get_client(self):
        from src.dashboard import create_app
        from fastapi.testclient import TestClient
        return TestClient(create_app())

    def test_get_config_returns_merged(self):
        client = self._get_client()
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "security" in data
        assert "tools" in data

    def test_get_config_includes_metadata(self):
        client = self._get_client()
        resp = client.get("/api/config")
        data = resp.json()
        assert "_has_user_config" in data

    def test_put_config_saves_partial(self, tmp_path):
        """PUT /api/config with partial data should merge into user config."""
        import src.dashboard as dashboard
        original_user = dashboard.USER_YAML
        dashboard.USER_YAML = tmp_path / "config.yaml"
        try:
            client = self._get_client()
            resp = client.put("/api/config", json={
                "tools": {"clipboard_read": {"enabled": True}}
            })
            assert resp.status_code == 200
            # Verify file was written
            saved = yaml.safe_load(dashboard.USER_YAML.read_text())
            assert saved["tools"]["clipboard_read"]["enabled"] is True
        finally:
            dashboard.USER_YAML = original_user

    def test_post_config_reset_returns_defaults(self, tmp_path):
        import src.dashboard as dashboard
        original_user = dashboard.USER_YAML
        dashboard.USER_YAML = tmp_path / "config.yaml"
        dashboard.USER_YAML.write_text("tools:\n  clipboard_read:\n    enabled: true\n")
        try:
            client = self._get_client()
            resp = client.post("/api/config/reset")
            assert resp.status_code == 200
            assert not dashboard.USER_YAML.exists()
        finally:
            dashboard.USER_YAML = original_user
```

**Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_dashboard.py::TestConfigAPI -v
```
Expected: FAIL (endpoints don't exist yet)

**Step 3: Implement config endpoints in `src/dashboard/__init__.py`**

Add these routes inside `create_app()`:

```python
import yaml

@app.get("/api/config")
async def get_config():
    config = load_config(
        default_path=str(DEFAULT_YAML),
        user_path=str(USER_YAML) if USER_YAML.exists() else None,
    )
    data = config.model_dump()
    data["_has_user_config"] = USER_YAML.exists()
    data["_user_config_path"] = str(USER_YAML)
    return data

@app.put("/api/config")
async def put_config(body: dict[str, Any]):
    # Load existing user config or empty
    existing: dict[str, Any] = {}
    if USER_YAML.exists():
        with open(USER_YAML) as f:
            existing = yaml.safe_load(f) or {}
    # Deep merge new values on top
    merged = _deep_merge(existing, body)
    # Save
    USER_YAML.parent.mkdir(parents=True, exist_ok=True)
    with open(USER_YAML, "w") as f:
        yaml.dump(merged, f, default_flow_style=False, sort_keys=False)
    # Return full merged config
    config = load_config(
        default_path=str(DEFAULT_YAML),
        user_path=str(USER_YAML),
    )
    result = config.model_dump()
    result["_has_user_config"] = True
    return result

@app.post("/api/config/reset")
async def reset_config():
    if USER_YAML.exists():
        USER_YAML.unlink()
    config = load_config(default_path=str(DEFAULT_YAML))
    result = config.model_dump()
    result["_has_user_config"] = False
    return result
```

**Step 4: Run tests**

```bash
.venv/Scripts/python -m pytest tests/test_dashboard.py -v
```
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/dashboard/__init__.py tests/test_dashboard.py
git commit -m "feat: add config API endpoints (GET/PUT/POST reset)"
```

---

### Task 3: Audit API Endpoints

**Files:**
- Modify: `src/dashboard/__init__.py`
- Test: `tests/test_dashboard.py`

**Context:** The audit log is a JSON-lines file at `logs/audit.log`. Each line is a JSON object with fields: `timestamp`, `tool`, `parameters`, `allowed`, `deny_reason` (optional), `result_summary` (optional). The API needs filtering, pagination, and stats aggregation.

**Step 1: Add tests for audit endpoints**

```python
class TestAuditAPI:
    SAMPLE_ENTRIES = [
        '{"timestamp":"2026-03-03T10:00:00+00:00","tool":"mouse_click","parameters":{"x":100,"y":200},"allowed":true}',
        '{"timestamp":"2026-03-03T10:01:00+00:00","tool":"launch_app","parameters":{"app":"notepad"},"allowed":false,"deny_reason":"Not in allowlist"}',
        '{"timestamp":"2026-03-03T10:02:00+00:00","tool":"capture_screenshot","parameters":{"monitor":0},"allowed":true}',
        '{"timestamp":"2026-03-03T10:03:00+00:00","tool":"keyboard_hotkey","parameters":{"keys":"alt+f4"},"allowed":false,"deny_reason":"Blocked hotkey"}',
        '{"timestamp":"2026-03-03T10:04:00+00:00","tool":"mouse_click","parameters":{"x":300,"y":400},"allowed":true}',
    ]

    def _get_client_with_log(self, tmp_path):
        import src.dashboard as dashboard
        original_log = dashboard.AUDIT_LOG
        dashboard.AUDIT_LOG = tmp_path / "audit.log"
        dashboard.AUDIT_LOG.write_text("\n".join(self.SAMPLE_ENTRIES) + "\n")
        from src.dashboard import create_app
        from fastapi.testclient import TestClient
        return TestClient(create_app()), original_log

    def test_get_audit_returns_entries(self, tmp_path):
        client, orig = self._get_client_with_log(tmp_path)
        import src.dashboard as dashboard
        try:
            resp = client.get("/api/audit")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 5
            assert len(data["entries"]) == 5
        finally:
            dashboard.AUDIT_LOG = orig

    def test_get_audit_filter_by_tool(self, tmp_path):
        client, orig = self._get_client_with_log(tmp_path)
        import src.dashboard as dashboard
        try:
            resp = client.get("/api/audit?tool=mouse_click")
            data = resp.json()
            assert data["total"] == 2
        finally:
            dashboard.AUDIT_LOG = orig

    def test_get_audit_filter_by_status(self, tmp_path):
        client, orig = self._get_client_with_log(tmp_path)
        import src.dashboard as dashboard
        try:
            resp = client.get("/api/audit?status=denied")
            data = resp.json()
            assert data["total"] == 2
        finally:
            dashboard.AUDIT_LOG = orig

    def test_get_audit_pagination(self, tmp_path):
        client, orig = self._get_client_with_log(tmp_path)
        import src.dashboard as dashboard
        try:
            resp = client.get("/api/audit?limit=2&offset=0")
            data = resp.json()
            assert len(data["entries"]) == 2
            assert data["total"] == 5
        finally:
            dashboard.AUDIT_LOG = orig

    def test_get_audit_stats(self, tmp_path):
        client, orig = self._get_client_with_log(tmp_path)
        import src.dashboard as dashboard
        try:
            resp = client.get("/api/audit/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_calls"] == 5
            assert data["allowed"] == 3
            assert data["denied"] == 2
        finally:
            dashboard.AUDIT_LOG = orig

    def test_get_audit_empty_log(self, tmp_path):
        import src.dashboard as dashboard
        original_log = dashboard.AUDIT_LOG
        dashboard.AUDIT_LOG = tmp_path / "nonexistent.log"
        from src.dashboard import create_app
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        try:
            resp = client.get("/api/audit")
            data = resp.json()
            assert data["total"] == 0
            assert data["entries"] == []
        finally:
            dashboard.AUDIT_LOG = original_log
```

**Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_dashboard.py::TestAuditAPI -v
```
Expected: FAIL

**Step 3: Implement audit endpoints**

Add to `src/dashboard/__init__.py`:

```python
import json
from datetime import datetime, timezone, timedelta
from collections import Counter

def _read_audit_entries() -> list[dict]:
    """Read all entries from the audit log file."""
    if not AUDIT_LOG.exists():
        return []
    entries = []
    for line in AUDIT_LOG.read_text(encoding="utf-8").strip().split("\n"):
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries

# Inside create_app():

@app.get("/api/audit")
async def get_audit(
    limit: int = 100,
    offset: int = 0,
    tool: str | None = None,
    status: str | None = None,
    search: str | None = None,
):
    entries = _read_audit_entries()
    # Newest first
    entries.reverse()
    # Filter
    if tool:
        entries = [e for e in entries if e.get("tool") == tool]
    if status == "allowed":
        entries = [e for e in entries if e.get("allowed") is True]
    elif status == "denied":
        entries = [e for e in entries if e.get("allowed") is False]
    if search:
        search_lower = search.lower()
        entries = [e for e in entries if search_lower in json.dumps(e).lower()]
    total = len(entries)
    page = entries[offset:offset + limit]
    return {"entries": page, "total": total, "limit": limit, "offset": offset}

@app.get("/api/audit/stats")
async def get_audit_stats(hours: int = 24):
    entries = _read_audit_entries()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    # Filter by time window
    recent = []
    for e in entries:
        try:
            ts = datetime.fromisoformat(e["timestamp"])
            if ts >= cutoff:
                recent.append(e)
        except (KeyError, ValueError):
            continue

    total = len(recent)
    allowed = sum(1 for e in recent if e.get("allowed"))
    denied = total - allowed
    deny_rate = round((denied / total * 100), 1) if total > 0 else 0

    tool_counts = Counter(e.get("tool", "unknown") for e in recent)
    denial_counts = Counter(e.get("tool", "unknown") for e in recent if not e.get("allowed"))

    most_used = tool_counts.most_common(1)[0][0] if tool_counts else None
    most_denied = denial_counts.most_common(1)[0][0] if denial_counts else None

    # Build hourly timeline
    timeline = {}
    for e in recent:
        try:
            ts = datetime.fromisoformat(e["timestamp"])
            hour_key = ts.strftime("%Y-%m-%dT%H:00")
            if hour_key not in timeline:
                timeline[hour_key] = {"hour": hour_key, "allowed": 0, "denied": 0}
            if e.get("allowed"):
                timeline[hour_key]["allowed"] += 1
            else:
                timeline[hour_key]["denied"] += 1
        except (KeyError, ValueError):
            continue

    return {
        "total_calls": total,
        "allowed": allowed,
        "denied": denied,
        "deny_rate": deny_rate,
        "most_used_tool": most_used,
        "most_denied_tool": most_denied,
        "timeline": sorted(timeline.values(), key=lambda x: x["hour"]),
        "denials_by_tool": dict(denial_counts.most_common()),
        "tool_counts": dict(tool_counts.most_common()),
    }
```

**Step 4: Run tests**

```bash
.venv/Scripts/python -m pytest tests/test_dashboard.py -v
```
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/dashboard/__init__.py tests/test_dashboard.py
git commit -m "feat: add audit API endpoints with filtering, pagination, and stats"
```

---

### Task 4: Dashboard HTML — Shell, Navigation, and CSS

**Files:**
- Create: `src/dashboard/static/index.html`

**Context:** Single self-contained HTML file. CDN imports for Shoelace, Chart.js, Tippy.js. Dark theme. 4-tab layout. This task builds the shell — subsequent tasks fill in each tab's content.

**Step 1: Write the HTML shell**

Create `src/dashboard/static/index.html` with:
- DOCTYPE, meta viewport, CDN imports (Shoelace dark theme CSS + autoloader, Chart.js, Tippy.js + Popper.js)
- CSS custom properties for dark theme colors
- Header with title + status indicator
- 4-tab navigation using `<sl-tab-group>`: Tools, Security, Rate Limits, Audit Log
- Save Config button bar at bottom with "restart required" banner (hidden by default)
- JS module with: `state` object, `loadConfig()` fetch, `saveConfig()` fetch, tab switching
- API base URL constant (`const API = ''`)

CDN URLs to use:
```html
<!-- Shoelace -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/themes/dark.css" />
<script type="module" src="https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.20.1/cdn/shoelace-autoloader.js"></script>

<!-- Chart.js -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>

<!-- Tippy.js + Popper -->
<script src="https://unpkg.com/@popperjs/core@2"></script>
<script src="https://unpkg.com/tippy.js@6"></script>
<link rel="stylesheet" href="https://unpkg.com/tippy.js@6/themes/material.css" />
```

Color palette:
- Background: `#0f172a` (slate-900)
- Card bg: `#1e293b` (slate-800)
- Accent: `#3b82f6` (blue-500)
- Success: `#22c55e` (green-500)
- Danger: `#ef4444` (red-500)
- Text: `#e2e8f0` (slate-200)

The shell should render an empty but styled dashboard with working tab navigation. Tabs show placeholder text like "Tools tab content..." etc.

**Step 2: Verify manually**

```bash
.venv/Scripts/python -m src.dashboard
```
Expected: Browser opens to `http://localhost:8765`, dark-themed dashboard with 4 tabs visible, tab switching works.

**Step 3: Commit**

```bash
git add src/dashboard/static/index.html
git commit -m "feat: add dashboard HTML shell with dark theme and tab navigation"
```

---

### Task 5: Dashboard HTML — Tools Tab

**Files:**
- Modify: `src/dashboard/static/index.html`

**Context:** The Tools tab shows all 26 tools grouped into 7 categories. Each tool has a toggle switch and an info icon. Categories are collapsible cards with "Enable All / Disable All" buttons.

**Step 1: Build the Tools tab content**

In the Tools tab panel, add:

1. **Category cards** — one per group (Screen, Mouse, Keyboard, Gamepad, ADB, System, Clipboard)
2. Each card has:
   - `<sl-details>` for collapsible behavior with category name and count badge
   - Header with "Enable All" / "Disable All" `<sl-button>` pair
   - List of tools, each as a row with:
     - `<sl-switch>` bound to `state.config.tools[toolName].enabled`
     - Tool name label
     - `<sl-icon name="info-circle">` with Tippy popover (content from HELP_DATA)
3. On toggle change: mark config as dirty, show save banner

**Tool categories to render (exact names from config):**

```javascript
const TOOL_CATEGORIES = {
    "Screen": ["capture_screenshot", "ocr_extract_text", "find_on_screen", "get_pixel_color", "list_windows"],
    "Mouse": ["mouse_move", "mouse_click", "mouse_drag", "mouse_scroll", "mouse_position"],
    "Keyboard": ["keyboard_type", "keyboard_hotkey", "keyboard_press"],
    "Gamepad": ["gamepad_connect", "gamepad_input", "gamepad_disconnect"],
    "ADB": ["adb_tap", "adb_swipe", "adb_key_event", "adb_shell"],
    "System": ["launch_app", "focus_window", "close_window", "get_system_info"],
    "Clipboard": ["clipboard_read", "clipboard_write"],
};
```

**Step 2: Verify manually**

Load dashboard, toggle some tools, verify Enable All / Disable All work per category.

**Step 3: Commit**

```bash
git add src/dashboard/static/index.html
git commit -m "feat: add Tools tab with category cards and toggle switches"
```

---

### Task 6: Dashboard HTML — Security Tab

**Files:**
- Modify: `src/dashboard/static/index.html`

**Context:** The Security tab has 6 card sections. Each maps to fields in `state.config.security`. Uses `<sl-switch>` for toggles, `<sl-input>` for text, `<sl-range>` for sliders, and custom chip editors for lists.

**Step 1: Build Security tab content**

6 cards:

**Card 1: General Security**
- `<sl-switch>` for `security.enabled` (master toggle)
- `<sl-switch>` for `security.confirm_dangerous_actions`
- `<sl-range>` for `security.confirmation_timeout_seconds` (10-300, step 5)
- `<sl-switch>` for `security.audit_logging`
- Each with info icon + help popover

**Card 2: Screen Masking**
- `<sl-switch>` for `security.masking.enabled`
- `<sl-switch>` for `security.masking.mask_password_fields`
- Chip editor for `security.masking.blocked_apps` — list of `<sl-tag>` with remove button + `<sl-input>` to add
- Info icons

**Card 3: Keyboard Security**
- Chip editor for `security.keyboard.blocked_hotkeys`
- `<sl-range>` for `security.keyboard.max_type_length` (50-2000, step 50)
- `<sl-switch>` for `security.keyboard.block_password_fields`

**Card 4: App Execution**
- `<sl-radio-group>` for `security.apps.mode` (allowlist / blocklist)
- Chip editor for `security.apps.allowed`

**Card 5: ADB Security**
- Chip editor for `security.adb.allowed_devices`
- Chip editor for `security.adb.allowed_commands`

**Card 6: Clipboard**
- `<sl-switch>` for `security.clipboard.read_enabled`
- `<sl-switch>` for `security.clipboard.write_enabled`

**Chip editor pattern (reusable):**
```html
<div class="chip-editor" data-path="security.masking.blocked_apps">
  <div class="chips">
    <!-- Rendered dynamically: <sl-tag removable>1Password</sl-tag> -->
  </div>
  <sl-input placeholder="Add item..." size="small">
    <sl-icon name="plus-circle" slot="suffix"></sl-icon>
  </sl-input>
</div>
```

**Step 2: Verify manually**

Toggle switches, add/remove chips, adjust sliders, verify changes reflected in state.

**Step 3: Commit**

```bash
git add src/dashboard/static/index.html
git commit -m "feat: add Security tab with all settings and chip editors"
```

---

### Task 7: Dashboard HTML — Rate Limits Tab

**Files:**
- Modify: `src/dashboard/static/index.html`

**Context:** Simple tab with 5 `<sl-range>` sliders, one per rate limit category. Shows current value as calls/minute.

**Step 1: Build Rate Limits tab content**

- One card with 5 rows
- Each row: category label, `<sl-range>` (min=1, max=500, step=5), value display
- Categories: mouse (60), keyboard (120), screenshot (10), adb (30), gamepad (120)
- Value updates in real-time as slider moves
- Info icon on each explaining what the rate limit controls

**Step 2: Verify manually and commit**

```bash
git add src/dashboard/static/index.html
git commit -m "feat: add Rate Limits tab with slider controls"
```

---

### Task 8: Dashboard HTML — Audit Log Tab (Stats, Charts, Table)

**Files:**
- Modify: `src/dashboard/static/index.html`

**Context:** The richest tab — stats bar, two charts, filterable table with pagination. Fetches data from `/api/audit` and `/api/audit/stats`.

**Step 1: Build the stats bar**

Row of 6 stat cards:
- Total Calls (number)
- Allowed (number, green)
- Denied (number, red)
- Deny Rate (percentage)
- Most Used Tool (name)
- Most Denied Tool (name)

**Step 2: Build charts**

Two `<canvas>` elements side by side:

1. **Calls Over Time** (line chart) — x-axis: hours, two lines: allowed (green), denied (red)
   - `<sl-radio-group>` toggle: 24h / 7d
   - Chart.js Line chart with dark theme colors

2. **Denials by Tool** (bar chart) — horizontal bars, one per tool
   - Chart.js Bar chart, red bars, tool names on y-axis

**Step 3: Build the filterable table**

- Filter row: `<sl-select>` for tool name (populated from data), `<sl-select>` for status (All/Allowed/Denied), `<sl-input>` for text search
- Table with columns: Time, Tool, Parameters, Status (badge), Reason
- Parameters column: truncated to 50 chars with tooltip showing full
- Status column: `<sl-badge variant="success">` for allowed, `<sl-badge variant="danger">` for denied
- Pagination: Previous / Next buttons + "Showing 1-100 of 1234"
- Export CSV button
- Live Tail toggle (`<sl-switch>`) — when on, auto-refresh every 5 seconds

**Step 4: Wire up JS**

```javascript
async function loadAudit() {
    const params = new URLSearchParams({
        limit: state.auditLimit,
        offset: state.auditOffset,
    });
    if (state.auditToolFilter) params.set('tool', state.auditToolFilter);
    if (state.auditStatusFilter) params.set('status', state.auditStatusFilter);
    if (state.auditSearch) params.set('search', state.auditSearch);

    const [entries, stats] = await Promise.all([
        fetch(`/api/audit?${params}`).then(r => r.json()),
        fetch(`/api/audit/stats?hours=${state.auditHours}`).then(r => r.json()),
    ]);
    renderStats(stats);
    renderCharts(stats);
    renderTable(entries);
}
```

**Step 5: Verify manually and commit**

```bash
git add src/dashboard/static/index.html
git commit -m "feat: add Audit Log tab with stats, charts, and filterable table"
```

---

### Task 9: Contextual Help System

**Files:**
- Modify: `src/dashboard/static/index.html`

**Context:** Every setting needs a rich help popover. Define a JS object `HELP_DATA` keyed by config path, containing: what, risk, default, config path, and YAML example. Attach Tippy.js popovers to all info icons.

**Step 1: Define HELP_DATA object**

Comprehensive help data for every setting. Example structure:

```javascript
const HELP_DATA = {
    // Tools
    "tools.capture_screenshot": {
        title: "Capture Screenshot",
        what: "Takes a screenshot of your entire screen, a specific monitor, or a defined region. Returns the image as base64 PNG.",
        risk: "MEDIUM — Screenshots may capture sensitive content visible on screen (passwords, private messages, financial data).",
        default: "Enabled",
        config: "tools:\n  capture_screenshot:\n    enabled: true",
    },
    // ... all 26 tools ...

    // Security settings
    "security.enabled": {
        title: "Master Security Toggle",
        what: "When disabled, ALL security checks are bypassed — no permission checks, no rate limits, no audit logging, no confirmations. Every tool call is allowed unconditionally.",
        risk: "CRITICAL — Disabling this removes all safety guardrails. Only disable for debugging.",
        default: "Enabled",
        config: "security:\n  enabled: true",
    },
    // ... all security settings ...

    // Rate limits
    "rate_limits.mouse": {
        title: "Mouse Rate Limit",
        what: "Maximum number of mouse actions (move, click, drag, scroll, position) allowed per minute. Prevents runaway automation loops.",
        risk: "LOW — Rate limits protect against accidental infinite loops, not security threats.",
        default: "60 calls/min",
        config: "security:\n  rate_limits:\n    mouse: 60",
    },
    // ... all rate limits ...
};
```

Must include help entries for ALL of:
- 26 tool toggles (what the tool does, risk level, when to enable/disable)
- `security.enabled`, `security.confirm_dangerous_actions`, `security.confirmation_timeout_seconds`, `security.audit_logging`
- `security.masking.enabled`, `security.masking.mask_password_fields`, `security.masking.blocked_apps`
- `security.keyboard.blocked_hotkeys`, `security.keyboard.max_type_length`, `security.keyboard.block_password_fields`
- `security.apps.mode`, `security.apps.allowed`
- `security.adb.allowed_devices`, `security.adb.allowed_commands`
- `security.clipboard.read_enabled`, `security.clipboard.write_enabled`
- 5 rate limit categories

**Step 2: Initialize Tippy popovers**

```javascript
function initHelp() {
    document.querySelectorAll('[data-help]').forEach(el => {
        const key = el.dataset.help;
        const help = HELP_DATA[key];
        if (!help) return;
        tippy(el, {
            content: `<div class="help-popover">
                <h4>${help.title}</h4>
                <p><strong>What:</strong> ${help.what}</p>
                <p><strong>Risk:</strong> ${help.risk}</p>
                <p><strong>Default:</strong> ${help.default}</p>
                <pre><code>${help.config}</code></pre>
            </div>`,
            allowHTML: true,
            theme: 'material',
            placement: 'right',
            interactive: true,
            maxWidth: 400,
        });
    });
}
```

**Step 3: Style the help popovers**

```css
.help-popover h4 { margin: 0 0 8px; color: #3b82f6; }
.help-popover p { margin: 4px 0; font-size: 13px; line-height: 1.4; }
.help-popover pre { background: #0f172a; padding: 8px; border-radius: 4px; font-size: 12px; margin-top: 8px; overflow-x: auto; }
.help-popover code { color: #22c55e; }
[data-help] { cursor: help; opacity: 0.6; transition: opacity 0.2s; }
[data-help]:hover { opacity: 1; }
```

**Step 4: Verify all popovers render correctly and commit**

```bash
git add src/dashboard/static/index.html
git commit -m "feat: add contextual help system with Tippy.js popovers for every setting"
```

---

### Task 10: Save/Reset Flow and Polish

**Files:**
- Modify: `src/dashboard/static/index.html`
- Modify: `src/dashboard/__init__.py` (if needed)

**Context:** Wire up the Save and Reset buttons. Show success/error feedback. Add restart banner. Polish overall UX.

**Step 1: Implement Save flow**

- "Save Config" button calls `PUT /api/config` with the full state diff
- On success: show `<sl-alert variant="success">` banner: "Config saved! Restart MCP server to apply changes."
- On error: show `<sl-alert variant="danger">` with error message
- Disable Save button when no changes (dirty tracking)

**Step 2: Implement Reset flow**

- "Reset to Defaults" button shows `<sl-dialog>` confirmation: "This will delete your config.yaml and revert all settings to defaults. Continue?"
- On confirm: calls `POST /api/config/reset`
- On success: reload config into UI, show success alert

**Step 3: Polish**

- Loading spinner while fetching initial config
- Error state if API is unreachable
- Smooth transitions on tab switch
- Responsive layout (works on different window sizes)
- Favicon (inline SVG data URI)

**Step 4: Run full test suite**

```bash
.venv/Scripts/python -m pytest tests/ -v
```
Expected: ALL PASS (existing 152 + new dashboard tests)

**Step 5: Manual end-to-end verification**

1. `python -m src.dashboard` — opens browser
2. Toggle tools — verify switches reflect config
3. Modify security settings — verify chip editors work
4. Adjust rate limits — verify sliders work
5. View audit log — verify stats, charts, table render
6. Click Save — verify config.yaml written, banner shown
7. Click Reset — verify config.yaml deleted, defaults restored
8. Hover info icons — verify help popovers appear with correct content

**Step 6: Commit**

```bash
git add src/dashboard/ tests/
git commit -m "feat: complete dashboard with save/reset flow and UX polish"
```

---

### Task 11: Final Integration & README Update

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml` (verify)

**Step 1: Install and verify CLI command works**

```bash
.venv/Scripts/pip install -e .
mcp-dashboard
```
Expected: Browser opens, dashboard loads, all features work.

**Step 2: Update README**

Add a "Dashboard" section to README.md:
- How to launch (`mcp-dashboard` or `python -m src.dashboard`)
- Screenshot placeholder
- What each tab does
- How config changes are applied (restart required)

**Step 3: Run full test suite one final time**

```bash
.venv/Scripts/python -m pytest tests/ -v
```
Expected: ALL PASS

**Step 4: Final commit**

```bash
git add -A
git commit -m "docs: add dashboard section to README"
```
