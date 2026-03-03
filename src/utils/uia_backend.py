"""UI Automation backend — Tier 2 targeting via Microsoft UIA.

Uses the `uiautomation` package (optional dependency) to discover interactive
UI elements with pixel-perfect bounding rectangles. Works for WPF, WinForms,
UWP, Qt, Electron, Chrome/Edge — anything that exposes an accessibility tree.

This module NEVER uses UIA's InvokePattern for clicking (it can hang).
We only use UIA for element discovery, then click with SendInput.

All functions gracefully degrade if uiautomation is not installed.
"""
from __future__ import annotations

from typing import Any

_uia = None  # lazy-loaded module reference
_uia_checked = False


def is_uia_available() -> bool:
    """Check if the uiautomation package is installed and importable."""
    global _uia, _uia_checked
    if _uia_checked:
        return _uia is not None
    _uia_checked = True
    try:
        import uiautomation
        _uia = uiautomation
        return True
    except ImportError:
        _uia = None
        return False


def _get_uia():
    """Get the uiautomation module, raising ImportError if unavailable."""
    if not is_uia_available():
        raise ImportError(
            "uiautomation is not installed. "
            "Install with: pip install uiautomation"
        )
    return _uia


# Control types we consider "interactive" (clickable)
_INTERACTIVE_TYPES = frozenset({
    "ButtonControl",
    "CheckBoxControl",
    "RadioButtonControl",
    "ComboBoxControl",
    "HyperlinkControl",
    "ListItemControl",
    "MenuItemControl",
    "TabItemControl",
    "TreeItemControl",
    "SplitButtonControl",
    "ToggleSwitchControl",
})

# Control types we report but are not clickable in the same way
_INFO_TYPES = frozenset({
    "TextControl",
    "EditControl",
    "SliderControl",
    "ProgressBarControl",
    "ScrollBarControl",
    "MenuBarControl",
    "ToolBarControl",
    "StatusBarControl",
    "GroupControl",
})

_ALL_TYPES = _INTERACTIVE_TYPES | _INFO_TYPES


def _control_to_dict(control: Any) -> dict[str, Any] | None:
    """Convert a UIA control to a serializable dict. Returns None if invalid."""
    try:
        rect = control.BoundingRectangle
        # Skip controls with zero-size or offscreen rectangles
        if rect.width() <= 0 or rect.height() <= 0:
            return None
        if rect.right <= 0 or rect.bottom <= 0:
            return None

        name = control.Name or ""
        ctrl_type = control.ControlTypeName or ""
        class_name = control.ClassName or ""

        # Friendly type name (strip "Control" suffix)
        friendly_type = ctrl_type.replace("Control", "").lower() if ctrl_type else "unknown"

        center_x = int(rect.left + rect.width() / 2)
        center_y = int(rect.top + rect.height() / 2)

        return {
            "name": name,
            "control_type": friendly_type,
            "class_name": class_name,
            "automation_id": control.AutomationId or "",
            "rect": {
                "left": int(rect.left),
                "top": int(rect.top),
                "right": int(rect.right),
                "bottom": int(rect.bottom),
            },
            "center": {"x": center_x, "y": center_y},
            "is_enabled": control.IsEnabled,
            "is_interactive": ctrl_type in _INTERACTIVE_TYPES,
        }
    except Exception:
        return None


def find_uia_elements(
    *,
    hwnd: int | None = None,
    window_title: str | None = None,
    name_filter: str | None = None,
    control_type: str | None = None,
    interactive_only: bool = False,
    max_results: int = 50,
    max_depth: int = 8,
) -> list[dict[str, Any]]:
    """Find UI elements using Microsoft UI Automation.

    Args:
        hwnd: Window handle to search in (preferred — faster).
        window_title: Window title substring to search in (fallback if no hwnd).
        name_filter: Case-insensitive substring to match element Name.
        control_type: Filter by type ('button', 'checkbox', 'edit', etc.).
        interactive_only: If True, only return clickable elements.
        max_results: Cap on number of elements returned (default 50).
        max_depth: Maximum tree traversal depth (default 8).

    Returns:
        List of element dicts with: name, control_type, class_name,
        automation_id, rect, center, is_enabled, is_interactive.

    Raises:
        ImportError: If uiautomation is not installed.
    """
    uia = _get_uia()
    elements: list[dict[str, Any]] = []

    # Find the target window
    root = None
    if hwnd:
        try:
            root = uia.ControlFromHandle(hwnd)
        except Exception:
            root = None

    if root is None and window_title:
        try:
            root = uia.WindowControl(searchDepth=1, SubName=window_title)
            if not root.Exists(maxSearchSeconds=1):
                return []
        except Exception:
            return []

    if root is None:
        return []

    # Normalize control_type filter
    type_filter = None
    if control_type:
        # Accept both "button" and "ButtonControl"
        ct = control_type.strip().lower()
        type_filter = ct.rstrip("control")

    def _walk(control: Any, depth: int) -> None:
        if len(elements) >= max_results or depth > max_depth:
            return

        info = _control_to_dict(control)
        if info is not None:
            # Apply filters
            if name_filter and name_filter.lower() not in info["name"].lower():
                pass  # skip this element but still walk children
            elif type_filter and type_filter not in info["control_type"]:
                pass
            elif interactive_only and not info["is_interactive"]:
                pass
            else:
                elements.append(info)

        # Walk children
        try:
            child = control.GetFirstChildControl()
            while child and len(elements) < max_results and depth < max_depth:
                _walk(child, depth + 1)
                child = child.GetNextSiblingControl()
        except Exception:
            pass

    _walk(root, 0)
    return elements


def find_uia_element_by_name(
    name: str,
    *,
    hwnd: int | None = None,
    window_title: str | None = None,
    control_type: str | None = None,
) -> dict[str, Any] | None:
    """Find a single UIA element by name. Returns the first match or None."""
    results = find_uia_elements(
        hwnd=hwnd,
        window_title=window_title,
        name_filter=name,
        control_type=control_type,
        interactive_only=False,
        max_results=1,
    )
    return results[0] if results else None
