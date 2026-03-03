"""Compound tools — multi-step operations combined into single tool calls."""
from __future__ import annotations

import time
from typing import Any

from src.tools.screen import capture_screenshot, ocr_extract_text
from src.tools.mouse import mouse_click
from src.tools.keyboard import keyboard_type as _keyboard_type
from src.tools.keyboard import keyboard_hotkey
from src.tools.clipboard import clipboard_write
from src.utils.win32_helpers import enumerate_windows, _normalize_unicode
from src.utils.errors import tool_error, tool_success, NOT_FOUND, INVALID_PARAMS, TIMEOUT, OS_ERROR


def click_text(
    text: str,
    button: str = "left",
    clicks: int = 1,
    monitor: int = 0,
    region: dict[str, int] | None = None,
    occurrence: int = 1,
) -> dict[str, Any]:
    """Find text on screen via OCR and click its center coordinate.

    Combines OCR + coordinate calculation + mouse click into one step.
    On failure, returns visible text to help the agent self-correct.
    """
    try:
        # Step 1: Run OCR
        ocr_result = ocr_extract_text(region=region, monitor=monitor)
        if not ocr_result["success"]:
            return ocr_result

        # Step 2: Find the target text in OCR results
        details = ocr_result.get("details", [])
        needle = _normalize_unicode(text.lower())
        matches = []

        for item in details:
            if needle in _normalize_unicode(item["text"].lower()):
                bbox = item.get("bbox")
                if bbox and len(bbox) >= 2:
                    matches.append(item)

        if not matches:
            # Return visible text snippet for debugging
            visible_texts = [d["text"] for d in details[:20]]
            return tool_error(
                f"Text '{text}' not found on screen", NOT_FOUND,
                suggestion="Check spelling, or the text may not be visible. Use capture_screenshot to see current screen state.",
                visible_text_sample=visible_texts,
            )

        if occurrence > len(matches):
            return tool_error(
                f"Only {len(matches)} occurrence(s) of '{text}' found, but occurrence={occurrence} requested",
                INVALID_PARAMS,
                suggestion=f"Use occurrence=1 through {len(matches)}",
            )

        # Step 3: Calculate center of the target bounding box
        target = matches[occurrence - 1]
        bbox = target["bbox"]
        # bbox is [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] — get center
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        center_x = int(sum(xs) / len(xs))
        center_y = int(sum(ys) / len(ys))

        # Adjust for region offset if applicable
        if region:
            center_x += region.get("left", 0)
            center_y += region.get("top", 0)

        # Step 4: Click (coords are in screenshot space since OCR ran on downscaled image)
        click_result = mouse_click(x=center_x, y=center_y, button=button, clicks=clicks, from_screenshot=True)
        if not click_result["success"]:
            return click_result

        return tool_success(
            clicked_text=target["text"],
            x=center_x, y=center_y,
            confidence=target.get("confidence", 0),
        )
    except Exception as e:
        return tool_error(
            str(e), OS_ERROR,
            suggestion="Try capture_screenshot + ocr_extract_text separately for debugging",
        )


def wait_for_window(
    title: str | None = None,
    process: str | None = None,
    timeout: float = 10.0,
    poll_interval: float = 0.5,
) -> dict[str, Any]:
    """Wait for a window to appear, polling at intervals. Essential after launch_app.

    Args:
        title: Window title substring to match.
        process: Process name to match (e.g., 'notepad.exe').
        timeout: Max seconds to wait (capped at 30).
        poll_interval: Seconds between polls.
    """
    if not title and not process:
        return tool_error(
            "Either 'title' or 'process' must be provided", INVALID_PARAMS,
            suggestion="Specify a window title or process name to wait for",
        )

    timeout = min(timeout, 30.0)  # Cap at 30 seconds
    poll_interval = max(poll_interval, 0.2)  # Min 200ms between polls

    try:
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            windows = enumerate_windows()
            for w in windows:
                if title and _normalize_unicode(title.lower()) in _normalize_unicode(w["title"].lower()):
                    return tool_success(
                        f"Window found: '{w['title']}'",
                        title=w["title"], process=w["process_name"],
                        elapsed_seconds=round(time.monotonic() - start, 2),
                    )
                if process and process.lower() in w["process_name"].lower():
                    return tool_success(
                        f"Window found: '{w['title']}'",
                        title=w["title"], process=w["process_name"],
                        elapsed_seconds=round(time.monotonic() - start, 2),
                    )
            time.sleep(poll_interval)

        elapsed = round(time.monotonic() - start, 2)
        target = title or process
        return tool_error(
            f"Window matching '{target}' did not appear within {timeout}s", TIMEOUT,
            suggestion="Increase timeout, check the application is launching, or verify the title/process name",
            elapsed_seconds=elapsed,
        )
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="Check window title/process name spelling")


_PASTE_THRESHOLD = 50  # characters — above this, clipboard+paste is 100x faster


def type_text(
    text: str,
    method: str = "auto",
) -> dict[str, Any]:
    """Smart text input — auto-selects between typing and clipboard paste.

    For short text (<50 chars), types character by character.
    For long text (≥50 chars), uses clipboard + Ctrl+V for 100x speed.

    Args:
        text: The text to type.
        method: "auto" (default), "type" (force char-by-char), "paste" (force clipboard).
    """
    if method not in ("auto", "type", "paste"):
        return tool_error(
            f"Invalid method '{method}'. Use 'auto', 'type', or 'paste'.",
            INVALID_PARAMS,
        )

    if not text:
        return tool_error("text must not be empty", INVALID_PARAMS)

    try:
        use_paste = method == "paste" or (method == "auto" and len(text) >= _PASTE_THRESHOLD)

        if use_paste:
            # Write to clipboard then paste
            clip_result = clipboard_write(text)
            if not clip_result.get("success"):
                # Fall back to typing if clipboard fails
                result = _keyboard_type(text, speed=0.02)
                if not result.get("success"):
                    return result
                return tool_success(
                    f"Typed {len(text)} characters (clipboard unavailable)",
                    method_used="type", characters=len(text),
                )

            time.sleep(0.05)  # small delay for clipboard to settle
            paste_result = keyboard_hotkey("ctrl+v")
            if not paste_result.get("success"):
                return paste_result
            return tool_success(
                f"Pasted {len(text)} characters via clipboard",
                method_used="paste", characters=len(text),
            )
        else:
            # Type character by character
            result = _keyboard_type(text, speed=0.02)
            if not result.get("success"):
                return result
            return tool_success(
                f"Typed {len(text)} characters",
                method_used="type", characters=len(text),
            )
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="Ensure the target window is focused")
