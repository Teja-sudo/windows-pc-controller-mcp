"""System management tools — app launching, window management, system info."""
from __future__ import annotations

import subprocess
from typing import Any

import psutil

from src.utils.win32_helpers import (
    enumerate_windows,
    focus_window_by_title,
    focus_window_by_process,
    close_window_by_title,
    close_window_by_process,
)
from src.security.masking import is_window_blocked
from src.utils.errors import tool_error, tool_success, NOT_FOUND, BLOCKED, INVALID_PARAMS, OS_ERROR


def launch_app(app: str) -> dict[str, Any]:
    """Launch an application by name or path."""
    try:
        subprocess.Popen(app, shell=False)
        return tool_success(f"Launched {app}", app=app)
    except FileNotFoundError:
        return tool_error(
            f"Application not found: {app}", NOT_FOUND,
            suggestion="Provide the full path to the executable, or add it to your config allowlist",
        )
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="Check the application path is correct")


def _check_blocked(title: str | None, process: str | None, blocked_apps: list[str]) -> str | None:
    """Return an error message if the target window is blocked, else None."""
    if not blocked_apps:
        return None
    # Check if the target string itself matches a blocked app
    for target in (title, process):
        if target and is_window_blocked(target, "", blocked_apps):
            return f"Access denied: '{target}' matches a blocked application"
    return None


def focus_window(
    title: str | None = None,
    process: str | None = None,
    blocked_apps: list[str] | None = None,
) -> dict[str, Any]:
    """Bring a window to the foreground by title substring or process name."""
    if not title and not process:
        return tool_error(
            "Either 'title' or 'process' must be provided", INVALID_PARAMS,
            suggestion="Use list_windows to find window titles or process names",
        )

    try:
        # Check blocked apps
        blocked_msg = _check_blocked(title, process, blocked_apps or [])
        if blocked_msg:
            return tool_error(blocked_msg, BLOCKED)

        found = False
        if title:
            found = focus_window_by_title(title)
        if not found and process:
            found = focus_window_by_process(process)

        if found:
            target = title or process
            return tool_success(f"Focused window matching '{target}'")

        # Build helpful failure response with available windows
        windows = enumerate_windows()
        available = [
            {"title": w["title"], "process": w["process_name"]}
            for w in windows[:10]
        ]
        target = title or process
        return tool_error(
            f"No window found matching '{target}'", NOT_FOUND,
            suggestion="Use list_windows to see available windows, or try matching by process name",
            available_windows=available,
        )
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="Try using process name instead of title")


def close_window(
    title: str | None = None,
    process: str | None = None,
    blocked_apps: list[str] | None = None,
) -> dict[str, Any]:
    """Close a window by title substring or process name (sends WM_CLOSE)."""
    if not title and not process:
        return tool_error(
            "Either 'title' or 'process' must be provided", INVALID_PARAMS,
            suggestion="Use list_windows to find window titles or process names",
        )

    try:
        # Check blocked apps
        blocked_msg = _check_blocked(title, process, blocked_apps or [])
        if blocked_msg:
            return tool_error(blocked_msg, BLOCKED)

        found = False
        if title:
            found = close_window_by_title(title)
        if not found and process:
            found = close_window_by_process(process)

        if found:
            target = title or process
            return tool_success(f"Sent close to window matching '{target}'")

        target = title or process
        return tool_error(
            f"No window found matching '{target}'", NOT_FOUND,
            suggestion="Use list_windows to see available windows",
        )
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="Try using process name instead of title")


def get_system_info() -> dict[str, Any]:
    """Get sanitized system information (no usernames or paths)."""
    try:
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")

        info: dict[str, Any] = {
            "success": True,
            "cpu_percent": psutil.cpu_percent(interval=0.5),
            "cpu_count": psutil.cpu_count(),
            "memory": {
                "total_gb": round(mem.total / (1024**3), 1),
                "used_gb": round(mem.used / (1024**3), 1),
                "percent": mem.percent,
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 1),
                "used_gb": round(disk.used / (1024**3), 1),
                "percent": round(disk.percent, 1),
            },
        }

        # Battery (if available)
        battery = psutil.sensors_battery()
        if battery:
            info["battery"] = {
                "percent": battery.percent,
                "plugged_in": battery.power_plugged,
            }

        return info
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="This tool requires Windows with psutil installed")
