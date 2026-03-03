"""Standardized error codes and response helpers for all tools."""
from __future__ import annotations

from typing import Any

# ── Error code constants ──────────────────────────────────────
NOT_FOUND = "NOT_FOUND"
BLOCKED = "BLOCKED"
RATE_LIMITED = "RATE_LIMITED"
TIMEOUT = "TIMEOUT"
INVALID_PARAMS = "INVALID_PARAMS"
DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
OS_ERROR = "OS_ERROR"


def tool_error(
    error: str,
    code: str = OS_ERROR,
    suggestion: str = "",
    **extra: Any,
) -> dict[str, Any]:
    """Build a standardized error response dict.

    Every error includes an ``error_code`` so agents can branch
    programmatically instead of parsing English error strings.
    """
    result: dict[str, Any] = {
        "success": False,
        "error": error,
        "error_code": code,
    }
    if suggestion:
        result["suggestion"] = suggestion
    result.update(extra)
    return result


def tool_success(message: str = "", **extra: Any) -> dict[str, Any]:
    """Build a standardized success response dict."""
    result: dict[str, Any] = {"success": True}
    if message:
        result["message"] = message
    result.update(extra)
    return result
