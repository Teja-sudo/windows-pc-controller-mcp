"""Clipboard read/write tools."""
from __future__ import annotations

from typing import Any

import win32clipboard


def clipboard_read() -> dict[str, Any]:
    """Read the current clipboard text content."""
    try:
        win32clipboard.OpenClipboard()
        try:
            data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            return {"success": True, "text": data}
        except TypeError:
            return {"success": True, "text": "", "message": "Clipboard is empty or contains non-text data"}
        finally:
            win32clipboard.CloseClipboard()
    except Exception as e:
        return {"success": False, "error": str(e)}


def clipboard_write(text: str) -> dict[str, Any]:
    """Write text to the clipboard."""
    try:
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
        return {"success": True, "message": f"Wrote {len(text)} characters to clipboard"}
    except Exception as e:
        return {"success": False, "error": str(e)}
