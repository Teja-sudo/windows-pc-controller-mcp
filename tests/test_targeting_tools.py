"""Tests for src.tools.targeting — tiered UI targeting cascade."""
import sys
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------
class TestDeduplicate:
    def test_no_win32_returns_all_uia(self):
        from src.tools.targeting import _deduplicate

        uia = [
            {"center": {"x": 100, "y": 50}, "name": "Save"},
            {"center": {"x": 200, "y": 50}, "name": "Cancel"},
        ]
        result = _deduplicate([], uia)
        assert len(result) == 2

    def test_no_uia_returns_empty(self):
        from src.tools.targeting import _deduplicate

        win32 = [{"center": {"x": 100, "y": 50}, "text": "OK"}]
        result = _deduplicate(win32, [])
        assert result == []

    def test_removes_overlapping_uia(self):
        from src.tools.targeting import _deduplicate

        win32 = [{"center": {"x": 100, "y": 50}, "text": "OK"}]
        uia = [
            {"center": {"x": 105, "y": 55}, "name": "OK"},  # within 20px — duplicate
            {"center": {"x": 300, "y": 50}, "name": "Cancel"},  # far away — unique
        ]
        result = _deduplicate(win32, uia)
        assert len(result) == 1
        assert result[0]["name"] == "Cancel"

    def test_keeps_non_overlapping_uia(self):
        from src.tools.targeting import _deduplicate

        win32 = [{"center": {"x": 100, "y": 50}, "text": "OK"}]
        uia = [
            {"center": {"x": 500, "y": 300}, "name": "Help"},
        ]
        result = _deduplicate(win32, uia)
        assert len(result) == 1
        assert result[0]["name"] == "Help"

    def test_deduplicates_uia_elements_at_same_center(self):
        """BUG-3: Maximize/Restore at same coords should be deduplicated."""
        from src.tools.targeting import _deduplicate

        uia = [
            {"center": {"x": 1772, "y": 22}, "name": "Maximize"},
            {"center": {"x": 1772, "y": 22}, "name": "Restore"},  # same coords
            {"center": {"x": 1830, "y": 22}, "name": "Close"},
        ]
        result = _deduplicate([], uia)
        assert len(result) == 2  # Maximize + Close, Restore deduplicated
        names = [e["name"] for e in result]
        assert "Maximize" in names
        assert "Close" in names


# ---------------------------------------------------------------------------
# _deduplicate_by_center
# ---------------------------------------------------------------------------
class TestDeduplicateByCenter:
    def test_removes_exact_duplicates(self):
        from src.tools.targeting import _deduplicate_by_center

        elements = [
            {"center": {"x": 100, "y": 50}, "name": "A"},
            {"center": {"x": 100, "y": 50}, "name": "B"},
            {"center": {"x": 200, "y": 50}, "name": "C"},
        ]
        result = _deduplicate_by_center(elements)
        assert len(result) == 2
        assert result[0]["name"] == "A"  # keeps first
        assert result[1]["name"] == "C"

    def test_empty_list(self):
        from src.tools.targeting import _deduplicate_by_center
        assert _deduplicate_by_center([]) == []


# ---------------------------------------------------------------------------
# Win32 class blocklist filtering
# ---------------------------------------------------------------------------
class TestWin32Blocklist:
    @patch("src.tools.targeting.is_uia_available", return_value=False)
    @patch("src.tools.targeting.find_win32_controls", return_value=[
        {"hwnd": 1, "text": "Chrome Legacy Window",
         "class_name": "Chrome_RenderWidgetHostHWND",
         "control_type": "chrome_renderwidgethosthwnd", "control_id": 1,
         "rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
         "center": {"x": 960, "y": 540}, "enabled": True, "visible": True},
        {"hwnd": 2, "text": "OK", "class_name": "Button",
         "control_type": "pushbutton", "control_id": 2,
         "rect": {"left": 10, "top": 20, "right": 80, "bottom": 50},
         "center": {"x": 45, "y": 35}, "enabled": True, "visible": True},
    ])
    @patch("src.tools.targeting.find_window_by_title", return_value=42)
    def test_filters_out_blocklisted_win32_classes(self, mock_find, mock_win32, mock_uia):
        from src.tools.targeting import find_ui_elements_tool

        result = find_ui_elements_tool(window_title="Test")
        assert result["success"] is True
        # Chrome Legacy Window should be filtered out
        assert result["count"] == 1
        assert result["elements"][0]["text"] == "OK"

    @patch("src.tools.targeting.is_uia_available", return_value=False)
    @patch("src.tools.targeting.find_win32_controls", return_value=[
        {"hwnd": 1, "text": "", "class_name": "Intermediate D3D Window",
         "control_type": "intermediate d3d window", "control_id": 0,
         "rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
         "center": {"x": 960, "y": 540}, "enabled": False, "visible": True},
    ])
    @patch("src.tools.targeting.find_window_by_title", return_value=42)
    def test_filters_out_d3d_window(self, mock_find, mock_win32, mock_uia):
        from src.tools.targeting import find_ui_elements_tool

        result = find_ui_elements_tool(window_title="Test")
        assert result["success"] is True
        assert result["count"] == 0


# ---------------------------------------------------------------------------
# interactive_only on Win32 tier
# ---------------------------------------------------------------------------
class TestInteractiveOnlyWin32:
    @patch("src.tools.targeting.is_uia_available", return_value=False)
    @patch("src.tools.targeting.find_win32_controls", return_value=[
        {"hwnd": 1, "text": "OK", "class_name": "Button",
         "control_type": "pushbutton", "control_id": 1,
         "rect": {"left": 10, "top": 20, "right": 80, "bottom": 50},
         "center": {"x": 45, "y": 35}, "enabled": True, "visible": True},
        {"hwnd": 2, "text": "Label", "class_name": "Static",
         "control_type": "label", "control_id": 2,
         "rect": {"left": 100, "top": 20, "right": 200, "bottom": 50},
         "center": {"x": 150, "y": 35}, "enabled": False, "visible": True},
    ])
    @patch("src.tools.targeting.find_window_by_title", return_value=42)
    def test_interactive_only_filters_disabled(self, mock_find, mock_win32, mock_uia):
        from src.tools.targeting import find_ui_elements_tool

        result = find_ui_elements_tool(window_title="Test", interactive_only=True)
        assert result["success"] is True
        assert result["count"] == 1
        assert result["elements"][0]["text"] == "OK"

    @patch("src.tools.targeting.is_uia_available", return_value=False)
    @patch("src.tools.targeting.find_win32_controls", return_value=[
        {"hwnd": 1, "text": "OK", "class_name": "Button",
         "control_type": "pushbutton", "control_id": 1,
         "rect": {"left": 10, "top": 20, "right": 80, "bottom": 50},
         "center": {"x": 45, "y": 35}, "enabled": True, "visible": True},
        {"hwnd": 2, "text": "Label", "class_name": "Static",
         "control_type": "label", "control_id": 2,
         "rect": {"left": 100, "top": 20, "right": 200, "bottom": 50},
         "center": {"x": 150, "y": 35}, "enabled": False, "visible": True},
    ])
    @patch("src.tools.targeting.find_window_by_title", return_value=42)
    def test_no_filter_when_interactive_only_false(self, mock_find, mock_win32, mock_uia):
        from src.tools.targeting import find_ui_elements_tool

        result = find_ui_elements_tool(window_title="Test", interactive_only=False)
        assert result["success"] is True
        assert result["count"] == 2  # Both returned


# ---------------------------------------------------------------------------
# _resolve_hwnd
# ---------------------------------------------------------------------------
class TestResolveHwnd:
    def test_returns_hwnd_when_provided(self):
        from src.tools.targeting import _resolve_hwnd

        hwnd, err = _resolve_hwnd(hwnd=42)
        assert hwnd == 42
        assert err is None

    @patch("src.tools.targeting.find_window_by_title", return_value=99)
    def test_resolves_from_title(self, mock_find):
        from src.tools.targeting import _resolve_hwnd

        hwnd, err = _resolve_hwnd(window_title="Notepad")
        assert hwnd == 99
        assert err is None

    @patch("src.tools.targeting.find_window_by_title", return_value=None)
    def test_error_when_title_not_found(self, mock_find):
        from src.tools.targeting import _resolve_hwnd

        hwnd, err = _resolve_hwnd(window_title="NonExistent")
        assert hwnd is None
        assert "no window found" in err.lower()

    def test_error_when_neither_provided(self):
        from src.tools.targeting import _resolve_hwnd

        hwnd, err = _resolve_hwnd()
        assert hwnd is None
        assert err is not None


# ---------------------------------------------------------------------------
# find_ui_elements_tool
# ---------------------------------------------------------------------------
class TestFindUiElementsTool:
    @patch("src.tools.targeting.is_uia_available", return_value=False)
    @patch("src.tools.targeting.find_win32_controls", return_value=[
        {"hwnd": 1001, "text": "OK", "class_name": "Button",
         "control_type": "pushbutton", "control_id": 1,
         "rect": {"left": 10, "top": 20, "right": 80, "bottom": 50},
         "center": {"x": 45, "y": 35}, "enabled": True, "visible": True},
    ])
    @patch("src.tools.targeting.find_window_by_title", return_value=42)
    def test_returns_win32_controls(self, mock_find_wnd, mock_win32, mock_uia):
        from src.tools.targeting import find_ui_elements_tool

        result = find_ui_elements_tool(window_title="Test")
        assert result["success"] is True
        assert result["count"] == 1
        assert result["elements"][0]["text"] == "OK"
        assert result["elements"][0]["source"] == "win32"
        assert "hint" in result  # UIA not available hint

    @patch("src.tools.targeting.is_uia_available", return_value=True)
    @patch("src.tools.targeting.find_uia_elements", return_value=[
        {"name": "Save", "control_type": "button",
         "center": {"x": 200, "y": 50}, "is_interactive": True},
    ])
    @patch("src.tools.targeting.find_win32_controls", return_value=[])
    @patch("src.tools.targeting.find_window_by_title", return_value=42)
    def test_returns_uia_elements_when_no_win32(self, mock_find, mock_win32, mock_uia, mock_avail):
        from src.tools.targeting import find_ui_elements_tool

        result = find_ui_elements_tool(window_title="Test")
        assert result["success"] is True
        assert result["count"] == 1
        assert result["elements"][0]["name"] == "Save"
        assert result["elements"][0]["source"] == "uia"

    def test_error_when_no_window_specified(self):
        from src.tools.targeting import find_ui_elements_tool

        result = find_ui_elements_tool()
        assert result["success"] is False

    @patch("src.tools.targeting.find_window_by_title", return_value=None)
    def test_error_when_window_not_found(self, mock_find):
        from src.tools.targeting import find_ui_elements_tool

        result = find_ui_elements_tool(window_title="NonExistent")
        assert result["success"] is False
        assert "no window found" in result["error"].lower()


# ---------------------------------------------------------------------------
# click_ui_element_tool — tier cascade
# ---------------------------------------------------------------------------
class TestClickUiElementTool:
    def test_invalid_tier_rejected(self):
        from src.tools.targeting import click_ui_element_tool

        result = click_ui_element_tool(name="OK", tier="invalid")
        assert result["success"] is False
        assert "invalid tier" in result["error"].lower()

    def test_empty_name_rejected(self):
        from src.tools.targeting import click_ui_element_tool

        result = click_ui_element_tool(name="")
        assert result["success"] is False
        assert "required" in result["error"].lower()

    @patch("src.tools.targeting.click_win32_control", return_value=True)
    @patch("src.tools.targeting.find_win32_controls", return_value=[
        {"hwnd": 1001, "text": "OK", "class_name": "Button",
         "control_type": "pushbutton", "control_id": 1,
         "rect": {"left": 10, "top": 20, "right": 80, "bottom": 50},
         "center": {"x": 45, "y": 35}, "enabled": True, "visible": True},
    ])
    @patch("src.tools.targeting.find_window_by_title", return_value=42)
    def test_tier1_win32_click(self, mock_find_wnd, mock_win32, mock_click):
        from src.tools.targeting import click_ui_element_tool

        result = click_ui_element_tool(name="OK", window_title="Test")
        assert result["success"] is True
        assert result["tier_used"] == "win32"
        mock_click.assert_called_once_with(1001)

    @patch("src.tools.targeting.sendinput_click")
    @patch("src.tools.targeting.find_uia_elements", return_value=[
        {"name": "Save", "control_type": "button",
         "center": {"x": 200, "y": 100}, "is_interactive": True},
    ])
    @patch("src.tools.targeting.is_uia_available", return_value=True)
    @patch("src.tools.targeting.find_win32_controls", return_value=[])
    @patch("src.tools.targeting.find_window_by_title", return_value=42)
    def test_tier2_uia_fallback(self, mock_find_wnd, mock_win32, mock_uia_avail, mock_uia, mock_click):
        from src.tools.targeting import click_ui_element_tool

        result = click_ui_element_tool(name="Save", window_title="Test")
        assert result["success"] is True
        assert result["tier_used"] == "uia"
        assert result["x"] == 200
        assert result["y"] == 100
        mock_click.assert_called_once_with(x=200, y=100, button="left", clicks=1)

    @patch("src.tools.compound.click_text", return_value={
        "success": True, "clicked_text": "Submit", "x": 500, "y": 300,
    })
    @patch("src.tools.targeting.is_uia_available", return_value=False)
    @patch("src.tools.targeting.find_win32_controls", return_value=[])
    @patch("src.tools.targeting.find_window_by_title", return_value=42)
    def test_tier3_ocr_fallback(self, mock_find_wnd, mock_win32, mock_uia_avail, mock_ocr):
        from src.tools.targeting import click_ui_element_tool

        result = click_ui_element_tool(name="Submit", window_title="Test")
        assert result["success"] is True
        assert result["tier_used"] == "ocr"

    @patch("src.tools.targeting.click_win32_control", return_value=True)
    @patch("src.tools.targeting.find_win32_controls", return_value=[
        {"hwnd": 1001, "text": "Cancel", "class_name": "Button",
         "control_type": "pushbutton", "control_id": 2,
         "rect": {"left": 10, "top": 20, "right": 80, "bottom": 50},
         "center": {"x": 45, "y": 35}, "enabled": True, "visible": True},
    ])
    @patch("src.tools.targeting.find_window_by_title", return_value=42)
    def test_forced_tier_win32(self, mock_find_wnd, mock_win32, mock_click):
        from src.tools.targeting import click_ui_element_tool

        result = click_ui_element_tool(name="Cancel", window_title="Test", tier="win32")
        assert result["success"] is True
        assert result["tier_used"] == "win32"

    @patch("src.tools.targeting.find_win32_controls", return_value=[])
    @patch("src.tools.targeting.find_window_by_title", return_value=42)
    def test_forced_tier_win32_not_found(self, mock_find_wnd, mock_win32):
        from src.tools.targeting import click_ui_element_tool

        result = click_ui_element_tool(name="Missing", window_title="Test", tier="win32")
        assert result["success"] is False
        assert "not found" in result["error"].lower()
        assert result["tiers_tried"] == ["win32"]

    @patch("src.tools.targeting.find_window_by_title", return_value=42)
    @patch("src.tools.targeting.is_uia_available", return_value=False)
    def test_forced_tier_uia_dependency_missing(self, mock_avail, mock_find_wnd):
        from src.tools.targeting import click_ui_element_tool

        result = click_ui_element_tool(name="OK", window_title="Test", tier="uia")
        assert result["success"] is False
        assert result["error_code"] == "DEPENDENCY_MISSING"

    @patch("src.tools.targeting.click_win32_control", return_value=True)
    @patch("src.tools.targeting.find_win32_controls", return_value=[
        {"hwnd": 1, "text": "OK Button", "class_name": "Button",
         "control_type": "pushbutton", "control_id": 1,
         "rect": {"left": 10, "top": 20, "right": 80, "bottom": 50},
         "center": {"x": 45, "y": 35}, "enabled": True, "visible": True},
        {"hwnd": 2, "text": "OK", "class_name": "Button",
         "control_type": "pushbutton", "control_id": 2,
         "rect": {"left": 100, "top": 20, "right": 160, "bottom": 50},
         "center": {"x": 130, "y": 35}, "enabled": True, "visible": True},
    ])
    @patch("src.tools.targeting.find_window_by_title", return_value=42)
    def test_prefers_exact_name_match(self, mock_find_wnd, mock_win32, mock_click):
        from src.tools.targeting import click_ui_element_tool

        result = click_ui_element_tool(name="OK", window_title="Test")
        assert result["success"] is True
        # Should click hwnd=2 ("OK" exact match) not hwnd=1 ("OK Button" partial)
        mock_click.assert_called_once_with(2)

    @patch("src.tools.compound.click_text", return_value={
        "success": False, "error": "Text not found",
    })
    @patch("src.tools.targeting.is_uia_available", return_value=False)
    @patch("src.tools.targeting.find_win32_controls", return_value=[])
    @patch("src.tools.targeting.find_window_by_title", return_value=42)
    def test_all_tiers_exhausted(self, mock_find_wnd, mock_win32, mock_uia_avail, mock_ocr):
        from src.tools.targeting import click_ui_element_tool

        result = click_ui_element_tool(name="Ghost", window_title="Test")
        assert result["success"] is False
        assert "not found" in result["error"].lower()
        assert "win32" in result["tiers_tried"]
        assert "ocr" in result["tiers_tried"]
