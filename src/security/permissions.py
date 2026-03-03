"""Permission policy engine for tool access control."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DANGEROUS_TOOLS = frozenset({
    "close_window", "launch_app", "adb_shell", "keyboard_hotkey", "window_manage",
    "click_ui_element",
})


@dataclass
class PermissionResult:
    allowed: bool
    reason: str = ""
    requires_confirmation: bool = False


class PermissionChecker:
    """Checks whether a tool call is permitted by config policy."""

    def __init__(
        self,
        tool_configs: dict[str, dict[str, Any]],
        security_config: dict[str, Any],
    ):
        self._tools = tool_configs
        self._security = security_config

    def check(self, tool_name: str, params: dict[str, Any]) -> PermissionResult:
        tool_cfg = self._tools.get(tool_name, {})
        if not tool_cfg.get("enabled", True):
            return PermissionResult(allowed=False, reason=f"Tool '{tool_name}' is disabled in config")

        if tool_name == "keyboard_hotkey":
            return self._check_hotkey(params)
        if tool_name == "launch_app":
            return self._check_app(params)
        if tool_name == "adb_shell":
            return self._check_adb_command(params)

        requires_confirm = tool_name in DANGEROUS_TOOLS
        return PermissionResult(allowed=True, requires_confirmation=requires_confirm)

    def _check_hotkey(self, params: dict[str, Any]) -> PermissionResult:
        keys = params.get("keys", "").lower()
        blocked = self._security.get("keyboard", {}).get("blocked_hotkeys", [])
        for hotkey in blocked:
            if hotkey.lower() == keys:
                return PermissionResult(allowed=False, reason=f"Hotkey '{keys}' is blocked by security policy")
        return PermissionResult(allowed=True, requires_confirmation=True)

    def _check_app(self, params: dict[str, Any]) -> PermissionResult:
        app = params.get("app", "")
        apps_cfg = self._security.get("apps", {})
        if apps_cfg.get("mode") == "allowlist":
            allowed_apps = apps_cfg.get("allowed", [])
            if app not in allowed_apps:
                return PermissionResult(
                    allowed=False,
                    reason=f"App '{app}' not in allowlist. Add it to config.yaml security.apps.allowed",
                )
        return PermissionResult(allowed=True, requires_confirmation=True)

    def _check_adb_command(self, params: dict[str, Any]) -> PermissionResult:
        command = params.get("command", "")
        allowed_cmds = self._security.get("adb", {}).get("allowed_commands", [])
        if not any(command.startswith(cmd) for cmd in allowed_cmds):
            return PermissionResult(
                allowed=False,
                reason=f"ADB command '{command}' not in allowlist",
            )
        return PermissionResult(allowed=True, requires_confirmation=True)
