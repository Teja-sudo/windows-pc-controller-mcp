"""Clipboard read/write tools."""
from __future__ import annotations

from typing import Any

import win32clipboard

from src.utils.errors import tool_error, tool_success, OS_ERROR


def clipboard_read() -> dict[str, Any]:
    """Read the current clipboard text content."""
    try:
        win32clipboard.OpenClipboard()
        try:
            data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            return tool_success(text=data)
        except TypeError:
            return tool_success("Clipboard is empty or contains non-text data", text="")
        finally:
            win32clipboard.CloseClipboard()
    except Exception as e:
        return tool_error(
            str(e), OS_ERROR,
            suggestion="Another application may have the clipboard locked. Try again.",
        )


def clipboard_write(text: str) -> dict[str, Any]:
    """Write text to the clipboard."""
    try:
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
        return tool_success(f"Wrote {len(text)} characters to clipboard")
    except Exception as e:
        return tool_error(
            str(e), OS_ERROR,
            suggestion="Another application may have the clipboard locked. Try again.",
        )
