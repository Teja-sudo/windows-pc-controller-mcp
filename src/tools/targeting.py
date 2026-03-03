"""Tiered UI targeting tools — find and click elements by name, not coordinates.

Implements a 4-tier cascade:
  Tier 1: Win32 SendMessage (BM_CLICK — fastest, classic controls only)
  Tier 2: UI Automation (pixel-perfect rects, works on modern UI frameworks)
  Tier 3: OCR + SendInput (existing click_text — works on everything visible)
  Tier 4: Raw SendInput (agent provides coordinates — last resort)

Tools:
  find_ui_elements  — discover interactive elements (read-only)
  click_ui_element  — click element via tiered cascade (state-changing)
"""
from __future__ import annotations

from typing import Any

from src.utils.win32_backend import (
    find_win32_controls,
    click_win32_control,
    find_window_by_title,
)
from src.utils.uia_backend import is_uia_available, find_uia_elements
from src.utils.mouse_backend import click as sendinput_click
from src.utils.errors import (
    tool_error, tool_success,
    NOT_FOUND, INVALID_PARAMS, OS_ERROR, DEPENDENCY_MISSING,
)


# ── Deduplication ─────────────────────────────────────────

_DEDUP_THRESHOLD = 20  # pixels — if two elements' centers are within this, they're duplicates

# Win32 class names that are internal rendering surfaces, never useful for agent interaction
_WIN32_CLASS_BLOCKLIST = frozenset({
    "chrome_renderwidgethosthwnd",
    "intermediate d3d window",
    "desktopwindowxamlsource",
    "windows.ui.input.inputsite.windowclass",
})


def _deduplicate(
    win32_controls: list[dict[str, Any]],
    uia_elements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge Win32 + UIA results, removing UIA entries that overlap with Win32.

    Win32 results take priority (faster click path). A UIA element is
    considered a duplicate if its center is within _DEDUP_THRESHOLD pixels
    of any Win32 control's center.

    Also deduplicates within UIA results — elements at the exact same center
    (e.g., Maximize/Restore buttons which share coordinates) keep only the first.
    """
    if not win32_controls:
        # Still deduplicate within UIA results
        return _deduplicate_by_center(uia_elements)
    if not uia_elements:
        return []

    win32_centers = set()
    for ctrl in win32_controls:
        c = ctrl.get("center", {})
        win32_centers.add((c.get("x", 0), c.get("y", 0)))

    unique_uia: list[dict[str, Any]] = []
    for elem in uia_elements:
        ec = elem.get("center", {})
        ex, ey = ec.get("x", 0), ec.get("y", 0)
        is_dup = any(
            abs(ex - wx) <= _DEDUP_THRESHOLD and abs(ey - wy) <= _DEDUP_THRESHOLD
            for wx, wy in win32_centers
        )
        if not is_dup:
            unique_uia.append(elem)

    return _deduplicate_by_center(unique_uia)


def _deduplicate_by_center(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove elements that share the exact same center coordinates.

    Keeps the first occurrence. Handles cases like Maximize/Restore buttons
    which are at the exact same position (only one is active at a time).
    """
    seen_centers: set[tuple[int, int]] = set()
    unique: list[dict[str, Any]] = []
    for elem in elements:
        c = elem.get("center", {})
        center = (c.get("x", 0), c.get("y", 0))
        if center not in seen_centers:
            seen_centers.add(center)
            unique.append(elem)
    return unique


# ── Window handle resolution ──────────────────────────────

def _resolve_hwnd(
    window_title: str | None = None,
    hwnd: int | None = None,
) -> tuple[int | None, str | None]:
    """Resolve a window handle from title or direct hwnd.

    Returns (hwnd, error_message). Error is None on success.
    """
    if hwnd:
        return hwnd, None
    if window_title:
        resolved = find_window_by_title(window_title)
        if resolved is None:
            return None, f"No window found matching '{window_title}'"
        return resolved, None
    return None, "Either 'window_title' or 'hwnd' must be provided"


# ── Tool: find_ui_elements ────────────────────────────────

def find_ui_elements_tool(
    *,
    window_title: str | None = None,
    hwnd: int | None = None,
    name: str | None = None,
    control_type: str | None = None,
    interactive_only: bool = False,
    max_results: int = 50,
) -> dict[str, Any]:
    """Discover interactive UI elements in a window without screenshots.

    Combines Win32 EnumChildWindows (Tier 1) and UI Automation (Tier 2)
    results, deduplicating overlapping elements.
    """
    try:
        resolved_hwnd, err = _resolve_hwnd(window_title, hwnd)
        if err:
            return tool_error(err, NOT_FOUND, suggestion="Use list_windows to find window titles")

        all_elements: list[dict[str, Any]] = []
        sources_used: list[str] = []

        # Tier 1: Win32 controls
        try:
            win32_results = find_win32_controls(
                resolved_hwnd,
                name_filter=name,
                control_type=control_type,
                visible_only=True,
            )
            # BUG-4 fix: filter out useless internal rendering surfaces
            win32_results = [
                ctrl for ctrl in win32_results
                if ctrl.get("class_name", "").lower() not in _WIN32_CLASS_BLOCKLIST
            ]
            # BUG-2 fix: enforce interactive_only on Win32 tier
            if interactive_only:
                win32_results = [
                    ctrl for ctrl in win32_results
                    if ctrl.get("enabled", True)
                ]
            for ctrl in win32_results:
                ctrl["source"] = "win32"
            all_elements.extend(win32_results)
            if win32_results:
                sources_used.append("win32")
        except Exception:
            win32_results = []

        # Tier 2: UI Automation
        uia_available = is_uia_available()
        if uia_available:
            try:
                uia_results = find_uia_elements(
                    hwnd=resolved_hwnd,
                    name_filter=name,
                    control_type=control_type,
                    interactive_only=interactive_only,
                    max_results=max_results,
                )
                # Deduplicate against Win32 results
                unique_uia = _deduplicate(win32_results, uia_results)
                for elem in unique_uia:
                    elem["source"] = "uia"
                all_elements.extend(unique_uia)
                if unique_uia:
                    sources_used.append("uia")
            except Exception:
                pass

        # Cap results
        if len(all_elements) > max_results:
            all_elements = all_elements[:max_results]

        result = tool_success(
            elements=all_elements,
            count=len(all_elements),
            sources=sources_used,
            uia_available=uia_available,
        )
        if not uia_available:
            result["hint"] = (
                "UI Automation not available — only Win32 controls shown. "
                "Install with: pip install uiautomation"
            )
        if not all_elements:
            result["suggestion"] = (
                "No elements found. Try capture_screenshot + click_text for OCR-based targeting, "
                "or verify the window title is correct with list_windows."
            )
        return result
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="Verify window exists with list_windows")


# ── Tool: click_ui_element ────────────────────────────────

_VALID_TIERS = frozenset({"auto", "win32", "uia", "ocr"})


def click_ui_element_tool(
    *,
    name: str,
    window_title: str | None = None,
    hwnd: int | None = None,
    control_type: str | None = None,
    tier: str = "auto",
    button: str = "left",
    clicks: int = 1,
) -> dict[str, Any]:
    """Click a UI element by name using tiered targeting cascade.

    Tiers tried in order (unless forced):
      1. Win32 SendMessage — fastest, no coordinates, classic controls only
      2. UI Automation — pixel-perfect rect, modern UI frameworks
      3. OCR + SendInput — works on everything visible (slowest)

    Args:
        name: Element text/label to click (case-insensitive).
        window_title: Window to search in (title substring).
        hwnd: Direct window handle (alternative to window_title).
        control_type: Filter by type ('button', 'checkbox', etc.).
        tier: 'auto' (cascade), 'win32', 'uia', or 'ocr' to force a specific tier.
        button: Mouse button ('left', 'right', 'middle') — used for Tier 2/3.
        clicks: Number of clicks (default 1) — used for Tier 2/3.
    """
    if tier not in _VALID_TIERS:
        return tool_error(
            f"Invalid tier '{tier}'. Valid: {', '.join(sorted(_VALID_TIERS))}",
            INVALID_PARAMS,
        )

    if not name:
        return tool_error("'name' is required — the text/label of the element to click", INVALID_PARAMS)

    try:
        # Resolve window handle (required for Win32 and UIA tiers)
        resolved_hwnd = None
        if window_title or hwnd:
            resolved_hwnd, err = _resolve_hwnd(window_title, hwnd)
            if err and tier in ("win32", "uia"):
                return tool_error(err, NOT_FOUND, suggestion="Use list_windows to find window titles")

        tiers_tried: list[str] = []

        # ── Tier 1: Win32 SendMessage ──
        if tier in ("auto", "win32") and resolved_hwnd:
            tiers_tried.append("win32")
            try:
                controls = find_win32_controls(
                    resolved_hwnd,
                    name_filter=name,
                    control_type=control_type,
                    visible_only=True,
                )
                if controls:
                    # Pick best match — prefer exact match, then first partial match
                    target = None
                    for ctrl in controls:
                        if ctrl["text"].lower() == name.lower():
                            target = ctrl
                            break
                    if target is None:
                        target = controls[0]

                    if click_win32_control(target["hwnd"]):
                        return tool_success(
                            f"Clicked '{target['text']}' via Win32 SendMessage",
                            tier_used="win32",
                            tiers_tried=tiers_tried,
                            element_text=target["text"],
                            control_type=target["control_type"],
                        )
            except Exception:
                pass

            if tier == "win32":
                return tool_error(
                    f"Win32 control '{name}' not found in this window",
                    NOT_FOUND,
                    suggestion="Try tier='auto' to fall through to UIA/OCR, or use find_ui_elements to discover controls",
                    tiers_tried=tiers_tried,
                )

        # ── Tier 2: UI Automation ──
        if tier in ("auto", "uia"):
            uia_available = is_uia_available()
            if uia_available and resolved_hwnd:
                tiers_tried.append("uia")
                try:
                    elements = find_uia_elements(
                        hwnd=resolved_hwnd,
                        name_filter=name,
                        control_type=control_type,
                        interactive_only=True,
                        max_results=10,
                    )
                    if elements:
                        # Pick best match — prefer exact name match
                        target = None
                        for elem in elements:
                            if elem["name"].lower() == name.lower():
                                target = elem
                                break
                        if target is None:
                            target = elements[0]

                        # Click at the element's center using SendInput
                        cx = target["center"]["x"]
                        cy = target["center"]["y"]
                        sendinput_click(x=cx, y=cy, button=button, clicks=clicks)

                        return tool_success(
                            f"Clicked '{target['name']}' via UI Automation at ({cx}, {cy})",
                            tier_used="uia",
                            tiers_tried=tiers_tried,
                            element_name=target["name"],
                            control_type=target["control_type"],
                            x=cx, y=cy,
                        )
                except Exception:
                    pass

            if tier == "uia":
                if not uia_available:
                    return tool_error(
                        "UI Automation not available",
                        DEPENDENCY_MISSING,
                        suggestion="Install with: pip install uiautomation",
                        tiers_tried=tiers_tried,
                    )
                return tool_error(
                    f"UIA element '{name}' not found",
                    NOT_FOUND,
                    suggestion="Try tier='auto' to fall through to OCR, or use find_ui_elements to discover elements",
                    tiers_tried=tiers_tried,
                )

        # ── Tier 3: OCR + SendInput ──
        if tier in ("auto", "ocr"):
            tiers_tried.append("ocr")
            try:
                from src.tools.compound import click_text
                ocr_result = click_text(text=name, button=button, clicks=clicks)
                if ocr_result.get("success"):
                    ocr_result["tier_used"] = "ocr"
                    ocr_result["tiers_tried"] = tiers_tried
                    return ocr_result
            except Exception:
                pass

            if tier == "ocr":
                return tool_error(
                    f"Text '{name}' not found on screen via OCR",
                    NOT_FOUND,
                    suggestion="Check spelling, or the text may not be visible. Use capture_screenshot to verify.",
                    tiers_tried=tiers_tried,
                )

        # All tiers exhausted
        return tool_error(
            f"Element '{name}' not found by any tier",
            NOT_FOUND,
            suggestion="Use find_ui_elements to discover available elements, or capture_screenshot to see the screen",
            tiers_tried=tiers_tried,
        )
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="Check the window exists and is visible")
