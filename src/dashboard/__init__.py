"""Settings Dashboard — FastAPI backend for config management and audit viewing."""
from __future__ import annotations

import webbrowser
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

    return app


def main():
    """Entry point for the dashboard CLI."""
    app = create_app()
    webbrowser.open("http://localhost:8765")
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
