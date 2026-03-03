"""Windows API wrappers for window enumeration and management."""
from __future__ import annotations

import ctypes
import re
import unicodedata
from typing import Any

import win32con
import win32gui
import win32process
import psutil

# Zero-width and invisible Unicode characters that break string matching
_INVISIBLE_RE = re.compile(
    "[\u200b\u200c\u200d\u200e\u200f\u2060\u2061\u2062\u2063\u2064\ufeff\u00ad]"
)


def _normalize_unicode(text: str) -> str:
    """Normalize a string for robust comparison: NFC + strip zero-width chars."""
    return _INVISIBLE_RE.sub("", unicodedata.normalize("NFC", text))


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


def get_window_rect_by_title(title_substring: str) -> dict[str, int] | None:
    """Find a window by title substring and return its bounding rect for capture.

    Returns dict with left, top, width, height suitable for mss region capture,
    or None if no matching window is found.
    """
    title_lower = _normalize_unicode(title_substring.lower())
    for w in enumerate_windows():
        if title_lower in _normalize_unicode(w["title"].lower()):
            r = w["rect"]
            width = r["right"] - r["left"]
            height = r["bottom"] - r["top"]
            if width > 0 and height > 0:
                return {"left": r["left"], "top": r["top"], "width": width, "height": height}
    return None


def _force_foreground(hwnd: int) -> bool:
    """Reliably bring a window to the foreground.

    Windows restricts SetForegroundWindow to the foreground process.
    Workaround: simulate an ALT keypress so our process satisfies the
    "received the last input event" condition, then attach to the
    foreground thread briefly to gain focus-change permission.

    See: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow
    """
    try:
        # Step 1: Restore the window if it is minimized
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        # Step 2: Simulate ALT key to satisfy "received last input event"
        ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)  # ALT down
        ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)  # ALT up

        # Step 3: Attach to the foreground thread to gain permission
        foreground_hwnd = win32gui.GetForegroundWindow()
        if foreground_hwnd:
            fg_thread, _ = win32process.GetWindowThreadProcessId(foreground_hwnd)
            our_thread = ctypes.windll.kernel32.GetCurrentThreadId()
            if fg_thread != our_thread:
                ctypes.windll.user32.AttachThreadInput(our_thread, fg_thread, True)
                try:
                    win32gui.SetForegroundWindow(hwnd)
                finally:
                    ctypes.windll.user32.AttachThreadInput(our_thread, fg_thread, False)
            else:
                win32gui.SetForegroundWindow(hwnd)
        else:
            win32gui.SetForegroundWindow(hwnd)

        # Step 4: Verify the window actually came to the foreground
        if win32gui.GetForegroundWindow() == hwnd:
            return True

        # Fallback: BringWindowToTop (less reliable but sometimes works)
        win32gui.BringWindowToTop(hwnd)
        return True
    except Exception:
        # Last resort: at least try to make the window visible
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.BringWindowToTop(hwnd)
            return True
        except Exception:
            return False


def focus_window_by_title(title_substring: str) -> bool:
    """Bring a window matching the title substring to the foreground.

    Uses Unicode normalization to handle zero-width characters in window titles.
    """
    needle = _normalize_unicode(title_substring.lower())
    for w in enumerate_windows():
        if needle in _normalize_unicode(w["title"].lower()):
            return _force_foreground(w["hwnd"])
    return False


def focus_window_by_process(process_name: str) -> bool:
    """Bring a window matching the process name to the foreground."""
    needle = process_name.lower()
    for w in enumerate_windows():
        if needle in w["process_name"].lower():
            return _force_foreground(w["hwnd"])
    return False


def close_window_by_title(title_substring: str) -> bool:
    """Send WM_CLOSE to a window matching the title substring.

    Uses Unicode normalization to handle zero-width characters in window titles.
    """
    try:
        needle = _normalize_unicode(title_substring.lower())
        for w in enumerate_windows():
            if needle in _normalize_unicode(w["title"].lower()):
                hwnd = w["hwnd"]
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                return True
        return False
    except Exception:
        return False


def close_window_by_process(process_name: str) -> bool:
    """Send WM_CLOSE to a window matching the process name."""
    try:
        needle = process_name.lower()
        for w in enumerate_windows():
            if needle in w["process_name"].lower():
                hwnd = w["hwnd"]
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                return True
        return False
    except Exception:
        return False
