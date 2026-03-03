"""Compound tools — multi-step operations combined into single tool calls."""
from __future__ import annotations

import time
from typing import Any

from src.tools.screen import capture_screenshot, ocr_extract_text
from src.tools.mouse import mouse_click
from src.utils.win32_helpers import enumerate_windows, _normalize_unicode


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
            return {
                "success": False,
                "error": f"Text '{text}' not found on screen",
                "suggestion": "Check spelling, or the text may not be visible. Use capture_screenshot to see current screen state.",
                "visible_text_sample": visible_texts,
            }

        if occurrence > len(matches):
            return {
                "success": False,
                "error": f"Only {len(matches)} occurrence(s) of '{text}' found, but occurrence={occurrence} requested",
                "suggestion": f"Use occurrence=1 through {len(matches)}",
            }

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

        # Step 4: Click
        click_result = mouse_click(x=center_x, y=center_y, button=button, clicks=clicks)
        if not click_result["success"]:
            return click_result

        return {
            "success": True,
            "clicked_text": target["text"],
            "x": center_x,
            "y": center_y,
            "confidence": target.get("confidence", 0),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "suggestion": "Try capture_screenshot + ocr_extract_text separately for debugging",
        }


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
        return {
            "success": False,
            "error": "Either 'title' or 'process' must be provided",
            "suggestion": "Specify a window title or process name to wait for",
        }

    timeout = min(timeout, 30.0)  # Cap at 30 seconds
    poll_interval = max(poll_interval, 0.2)  # Min 200ms between polls

    try:
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            windows = enumerate_windows()
            for w in windows:
                if title and _normalize_unicode(title.lower()) in _normalize_unicode(w["title"].lower()):
                    return {
                        "success": True,
                        "message": f"Window found: '{w['title']}'",
                        "title": w["title"],
                        "process": w["process_name"],
                        "elapsed_seconds": round(time.monotonic() - start, 2),
                    }
                if process and process.lower() in w["process_name"].lower():
                    return {
                        "success": True,
                        "message": f"Window found: '{w['title']}'",
                        "title": w["title"],
                        "process": w["process_name"],
                        "elapsed_seconds": round(time.monotonic() - start, 2),
                    }
            time.sleep(poll_interval)

        elapsed = round(time.monotonic() - start, 2)
        target = title or process
        return {
            "success": False,
            "error": f"Window matching '{target}' did not appear within {timeout}s",
            "suggestion": "Increase timeout, check the application is launching, or verify the title/process name",
            "elapsed_seconds": elapsed,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
