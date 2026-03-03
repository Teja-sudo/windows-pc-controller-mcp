"""Windows API wrappers for window enumeration and management."""
from __future__ import annotations

from typing import Any

import win32gui
import win32process
import psutil


def enumerate_windows() -> list[dict[str, Any]]:
    """List all visible windows with their titles, positions, and process info."""
    windows: list[dict[str, Any]] = []

    def callback(hwnd: int, _: Any) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return True

        rect = win32gui.GetWindowRect(hwnd)
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            process_name = proc.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            process_name = "unknown"

        windows.append({
            "hwnd": hwnd,
            "title": title,
            "process_name": process_name,
            "rect": {"left": rect[0], "top": rect[1], "right": rect[2], "bottom": rect[3]},
        })
        return True

    win32gui.EnumWindows(callback, None)
    return windows


def get_active_window_title() -> str:
    """Get the title of the currently focused window."""
    hwnd = win32gui.GetForegroundWindow()
    return win32gui.GetWindowText(hwnd) or ""


def focus_window_by_title(title_substring: str) -> bool:
    """Bring a window matching the title substring to the foreground."""
    for w in enumerate_windows():
        if title_substring.lower() in w["title"].lower():
            hwnd = w["hwnd"]
            win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
            win32gui.SetForegroundWindow(hwnd)
            return True
    return False


def close_window_by_title(title_substring: str) -> bool:
    """Send WM_CLOSE to a window matching the title substring."""
    import win32con
    for w in enumerate_windows():
        if title_substring.lower() in w["title"].lower():
            hwnd = w["hwnd"]
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            return True
    return False
