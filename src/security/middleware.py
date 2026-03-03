"""Central security middleware — all tool calls pass through here."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.config import AppConfig
from src.security.audit import AuditLogger
from src.security.permissions import PermissionChecker, PermissionResult
from src.security.rate_limiter import RateLimiter


# Map tool names to rate limit categories
# System and clipboard tools are not rate-limited by default (no config entry),
# but are mapped here for completeness. Add rate limits in config if needed.
TOOL_CATEGORY = {
    "mouse_move": "mouse", "mouse_click": "mouse", "mouse_drag": "mouse",
    "mouse_scroll": "mouse", "mouse_position": "mouse",
    "keyboard_type": "keyboard", "keyboard_hotkey": "keyboard", "keyboard_press": "keyboard",
    "capture_screenshot": "screenshot", "ocr_extract_text": "screenshot",
    "find_on_screen": "screenshot", "get_pixel_color": "screenshot", "list_windows": "screenshot",
    "adb_tap": "adb", "adb_swipe": "adb", "adb_key_event": "adb", "adb_shell": "adb",
    "gamepad_connect": "gamepad", "gamepad_input": "gamepad", "gamepad_disconnect": "gamepad",
    "launch_app": "system", "focus_window": "system", "close_window": "system",
    "get_system_info": "system",
    "clipboard_read": "clipboard", "clipboard_write": "clipboard",
}


@dataclass
class MiddlewareResult:
    allowed: bool
    reason: str = ""
    requires_confirmation: bool = False


class SecurityMiddleware:
    """Central security gate. Every tool call must pass through pre_check()."""

    def __init__(self, config: AppConfig, log_dir: str | None = None):
        self._config = config
        sec = config.security

        tool_configs = {name: cfg.model_dump() for name, cfg in config.tools.items()}
        self._perm_checker = PermissionChecker(
            tool_configs=tool_configs,
            security_config=sec.model_dump(),
        )

        self._rate_limiter = RateLimiter(
            limits=sec.rate_limits.model_dump(),
        )

        if log_dir is None:
            log_dir = str(Path(__file__).parent.parent.parent / "logs")
        self._audit = AuditLogger(
            log_path=str(Path(log_dir) / "audit.log"),
            enabled=sec.audit_logging,
        )

    def pre_check(self, tool_name: str, params: dict[str, Any]) -> MiddlewareResult:
        """Check if a tool call is allowed. Call this BEFORE executing the tool."""
        if not self._config.security.enabled:
            return MiddlewareResult(allowed=True)

        # 1. Permission check
        perm = self._perm_checker.check(tool_name, params)
        if not perm.allowed:
            self._audit.log_tool_call(tool_name, params, None, allowed=False, deny_reason=perm.reason)
            return MiddlewareResult(allowed=False, reason=perm.reason)

        # 2. Rate limit check
        category = TOOL_CATEGORY.get(tool_name, tool_name)
        if not self._rate_limiter.check(category):
            reason = f"Rate limit exceeded for category '{category}'"
            self._audit.log_tool_call(tool_name, params, None, allowed=False, deny_reason=reason)
            return MiddlewareResult(allowed=False, reason=reason)

        # 3. Confirmation needed?
        needs_confirm = (
            perm.requires_confirmation
            and self._config.security.confirm_dangerous_actions
        )

        return MiddlewareResult(
            allowed=True,
            requires_confirmation=needs_confirm,
        )

    def post_log(self, tool_name: str, params: dict[str, Any], result: Any) -> None:
        """Log a successful tool execution."""
        self._audit.log_tool_call(tool_name, params, result, allowed=True)
