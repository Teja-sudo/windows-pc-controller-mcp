"""Structured JSON audit logger for all tool calls."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLogger:
    """Logs every tool call to a JSON-lines file."""

    def __init__(self, log_path: str | None = None, enabled: bool = True):
        self._enabled = enabled
        self._log_path = Path(log_path) if log_path else None

    def log_tool_call(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        result: Any,
        allowed: bool,
        deny_reason: str | None = None,
    ) -> None:
        if not self._enabled or self._log_path is None:
            return

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": tool_name,
            "parameters": parameters,
            "allowed": allowed,
        }
        if deny_reason is not None:
            entry["deny_reason"] = deny_reason
        if allowed and result is not None:
            entry["result_summary"] = str(result)[:200]

        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
