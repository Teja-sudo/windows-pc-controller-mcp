"""System management tools — app launching, window management, system info."""
from __future__ import annotations

import shutil
import subprocess
import webbrowser
from typing import Any

import psutil
import win32con
import win32gui

from src.utils.win32_helpers import (
    enumerate_windows,
    focus_window_by_title,
    focus_window_by_process,
    close_window_by_title,
    close_window_by_process,
    _normalize_unicode,
    _force_foreground,
)
from src.security.masking import is_window_blocked
from src.utils.errors import (
    tool_error, tool_success,
    NOT_FOUND, BLOCKED, INVALID_PARAMS, OS_ERROR, DEPENDENCY_MISSING,
)


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


# ── Window management ─────────────────────────────────────

_WINDOW_ACTIONS = frozenset({
    "maximize", "minimize", "restore", "resize", "move",
    "snap_left", "snap_right",
})


def _find_hwnd(
    title: str | None,
    process: str | None,
    blocked_apps: list[str] | None,
) -> tuple[int | None, str | None]:
    """Find a window handle by title or process. Returns (hwnd, error_msg)."""
    if not title and not process:
        return None, "Either 'title' or 'process' must be provided"

    blocked_msg = _check_blocked(title, process, blocked_apps or [])
    if blocked_msg:
        return None, blocked_msg

    needle_title = _normalize_unicode(title.lower()) if title else None
    needle_proc = process.lower() if process else None

    for w in enumerate_windows():
        if needle_title and needle_title in _normalize_unicode(w["title"].lower()):
            return w["hwnd"], None
        if needle_proc and needle_proc in w["process_name"].lower():
            return w["hwnd"], None

    target = title or process
    return None, f"No window found matching '{target}'"


def window_manage(
    action: str,
    title: str | None = None,
    process: str | None = None,
    width: int | None = None,
    height: int | None = None,
    x: int | None = None,
    y: int | None = None,
    blocked_apps: list[str] | None = None,
) -> dict[str, Any]:
    """Manage a window: maximize, minimize, restore, resize, move, snap."""
    if action not in _WINDOW_ACTIONS:
        return tool_error(
            f"Unknown action '{action}'. Valid: {', '.join(sorted(_WINDOW_ACTIONS))}",
            INVALID_PARAMS,
        )

    try:
        hwnd, err = _find_hwnd(title, process, blocked_apps)
        if hwnd is None:
            code = BLOCKED if err and "blocked" in err.lower() else NOT_FOUND
            return tool_error(
                err or "Window not found", code,
                suggestion="Use list_windows to find available windows",
            )

        if action == "maximize":
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        elif action == "minimize":
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        elif action == "restore":
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        elif action == "resize":
            if width is None or height is None:
                return tool_error("resize requires width and height", INVALID_PARAMS)
            rect = win32gui.GetWindowRect(hwnd)
            win32gui.MoveWindow(hwnd, rect[0], rect[1], width, height, True)
        elif action == "move":
            if x is None or y is None:
                return tool_error("move requires x and y", INVALID_PARAMS)
            rect = win32gui.GetWindowRect(hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            win32gui.MoveWindow(hwnd, x, y, w, h, True)
        elif action == "snap_left":
            import mss
            with mss.mss() as sct:
                mon = sct.monitors[1]
            half_w = mon["width"] // 2
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.MoveWindow(hwnd, mon["left"], mon["top"], half_w, mon["height"], True)
        elif action == "snap_right":
            import mss
            with mss.mss() as sct:
                mon = sct.monitors[1]
            half_w = mon["width"] // 2
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.MoveWindow(hwnd, mon["left"] + half_w, mon["top"], half_w, mon["height"], True)

        target = title or process
        return tool_success(f"Applied '{action}' to window matching '{target}'")
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="Check the window still exists")


# ── Open URL ──────────────────────────────────────────────

def open_url(url: str) -> dict[str, Any]:
    """Open a URL in the default web browser (stdlib webbrowser, zero deps)."""
    if not url.startswith(("http://", "https://")):
        return tool_error(
            f"Invalid URL: must start with http:// or https://", INVALID_PARAMS,
            suggestion="Provide a full URL like 'https://example.com'",
        )
    try:
        webbrowser.open(url)
        return tool_success(f"Opened {url}", url=url)
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="Check that a default browser is configured")


# ── Health diagnostic ─────────────────────────────────────

def get_health() -> dict[str, Any]:
    """Return a diagnostic snapshot: OCR status, DPI, ADB, screen info, tool count."""
    try:
        from src.utils.dpi import get_dpi_scale_factor
        from src.tools.screen import get_screen_info

        health: dict[str, Any] = {"success": True}

        # Screen info
        screen = get_screen_info()
        if screen.get("success"):
            health["screen"] = {
                "width": screen["primary_monitor"]["width"],
                "height": screen["primary_monitor"]["height"],
                "monitors": screen["monitor_count"],
            }

        # DPI
        health["dpi_scale"] = get_dpi_scale_factor()

        # OCR engine
        try:
            from rapidocr_onnxruntime import RapidOCR
            health["ocr_engine"] = "rapidocr (available)"
        except ImportError:
            health["ocr_engine"] = "windows_native (rapidocr not installed)"

        # ADB
        health["adb_available"] = shutil.which("adb") is not None

        # ViGEm
        try:
            import vgamepad
            health["vigem_driver"] = "available"
        except ImportError:
            health["vigem_driver"] = "not installed (pip install vgamepad)"

        # UI Automation
        from src.utils.uia_backend import is_uia_available
        health["uia_available"] = is_uia_available()

        # Tool count
        from src.server import TOOL_DEFINITIONS
        health["tool_count"] = len(TOOL_DEFINITIONS)

        return health
    except Exception as e:
        return tool_error(str(e), OS_ERROR)
