"""Settings Dashboard — FastAPI backend for config management and audit viewing."""
from __future__ import annotations

import json
import webbrowser
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import uvicorn
import yaml
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from src.config import load_config, _deep_merge

STATIC_DIR = Path(__file__).parent / "static"
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
LOG_DIR = Path(__file__).parent.parent.parent / "logs"

DEFAULT_YAML = CONFIG_DIR / "default.yaml"
USER_YAML = CONFIG_DIR / "config.yaml"
AUDIT_LOG = LOG_DIR / "audit.log"


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


def create_app() -> FastAPI:
    """Create the FastAPI dashboard application."""
    app = FastAPI(title="MCP Dashboard", version="0.1.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        html_path = STATIC_DIR / "index.html"
        if not html_path.exists():
            return HTMLResponse("<h1>Dashboard UI not found</h1>", status_code=404)
        return HTMLResponse(html_path.read_text(encoding="utf-8"))

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
        denial_counts = Counter(
            e.get("tool", "unknown") for e in recent if not e.get("allowed")
        )

        most_used = tool_counts.most_common(1)[0][0] if tool_counts else None
        most_denied = denial_counts.most_common(1)[0][0] if denial_counts else None

        # Build hourly timeline
        timeline: dict[str, dict] = {}
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

    return app


def main():
    """Entry point for the dashboard CLI."""
    app = create_app()
    webbrowser.open("http://localhost:8765")
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
