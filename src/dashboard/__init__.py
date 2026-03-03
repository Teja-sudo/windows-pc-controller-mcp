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
