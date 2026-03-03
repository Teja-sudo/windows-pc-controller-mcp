"""System management tools — app launching, window management, system info."""
from __future__ import annotations

import subprocess
from typing import Any

import psutil

from src.utils.win32_helpers import (
    focus_window_by_title,
    close_window_by_title,
)


def launch_app(app: str) -> dict[str, Any]:
    """Launch an application by name or path."""
    try:
        subprocess.Popen(app, shell=False)
        return {"success": True, "app": app, "message": f"Launched {app}"}
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"Application not found: {app}",
            "suggestion": "Provide the full path to the executable, or add it to your config allowlist",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def focus_window(title: str) -> dict[str, Any]:
    """Bring a window to the foreground by title substring."""
    try:
        found = focus_window_by_title(title)
        if found:
            return {"success": True, "message": f"Focused window matching '{title}'"}
        return {
            "success": False,
            "error": f"No window found matching '{title}'",
            "suggestion": "Use list_windows to see available windows",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def close_window(title: str) -> dict[str, Any]:
    """Close a window by title substring (sends WM_CLOSE)."""
    try:
        found = close_window_by_title(title)
        if found:
            return {"success": True, "message": f"Sent close to window matching '{title}'"}
        return {
            "success": False,
            "error": f"No window found matching '{title}'",
            "suggestion": "Use list_windows to see available windows",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


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
        return {"success": False, "error": str(e)}
