"""Tests for compound tools — click_text, wait_for_window, type_text."""
import sys
import time
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


# ---------------------------------------------------------------------------
# click_text
# ---------------------------------------------------------------------------
class TestClickText:
    @patch("src.tools.compound.mouse_click")
    @patch("src.tools.compound.ocr_extract_text")
    def test_clicks_found_text(self, mock_ocr, mock_click):
        from src.tools.compound import click_text

        mock_ocr.return_value = {
            "success": True,
            "text": "File Edit View Help",
            "details": [
                {"text": "File", "confidence": 0.99, "bbox": [[10, 5], [50, 5], [50, 20], [10, 20]]},
                {"text": "Edit", "confidence": 0.98, "bbox": [[60, 5], [100, 5], [100, 20], [60, 20]]},
            ],
        }
        mock_click.return_value = {"success": True, "button": "left", "clicks": 1}

        result = click_text("Edit")
        assert result["success"] is True
        assert result["clicked_text"] == "Edit"
        assert result["x"] == 80  # center of [60,100]
        assert result["y"] == 12  # center of [5,20] (rounded)
        mock_click.assert_called_once_with(x=80, y=12, button="left", clicks=1, from_screenshot=True)

    @patch("src.tools.compound.ocr_extract_text")
    def test_text_not_found_returns_visible_text(self, mock_ocr):
        from src.tools.compound import click_text

        mock_ocr.return_value = {
            "success": True,
            "text": "File Edit View",
            "details": [
                {"text": "File", "confidence": 0.99, "bbox": [[10, 5], [50, 5], [50, 20], [10, 20]]},
            ],
        }

        result = click_text("Settings")
        assert result["success"] is False
        assert "not found" in result["error"].lower()
        assert "visible_text_sample" in result
        assert "File" in result["visible_text_sample"]

    @patch("src.tools.compound.ocr_extract_text")
    def test_ocr_failure_propagated(self, mock_ocr):
        from src.tools.compound import click_text

        mock_ocr.return_value = {"success": False, "error": "OCR engine not available"}

        result = click_text("anything")
        assert result["success"] is False
        assert "OCR" in result["error"]

    @patch("src.tools.compound.mouse_click")
    @patch("src.tools.compound.ocr_extract_text")
    def test_occurrence_parameter(self, mock_ocr, mock_click):
        from src.tools.compound import click_text

        mock_ocr.return_value = {
            "success": True,
            "text": "OK OK",
            "details": [
                {"text": "OK", "confidence": 0.99, "bbox": [[10, 10], [30, 10], [30, 30], [10, 30]]},
                {"text": "OK", "confidence": 0.99, "bbox": [[100, 10], [120, 10], [120, 30], [100, 30]]},
            ],
        }
        mock_click.return_value = {"success": True}

        # Click second occurrence
        result = click_text("OK", occurrence=2)
        assert result["success"] is True
        assert result["x"] == 110  # center of second bbox

    @patch("src.tools.compound.ocr_extract_text")
    def test_occurrence_out_of_range(self, mock_ocr):
        from src.tools.compound import click_text

        mock_ocr.return_value = {
            "success": True,
            "text": "OK",
            "details": [
                {"text": "OK", "confidence": 0.99, "bbox": [[10, 10], [30, 10], [30, 30], [10, 30]]},
            ],
        }

        result = click_text("OK", occurrence=5)
        assert result["success"] is False
        assert "occurrence" in result["error"].lower()

    @patch("src.tools.compound.mouse_click")
    @patch("src.tools.compound.ocr_extract_text")
    def test_region_offset_applied(self, mock_ocr, mock_click):
        from src.tools.compound import click_text

        mock_ocr.return_value = {
            "success": True,
            "text": "Click Me",
            "details": [
                {"text": "Click Me", "confidence": 0.99, "bbox": [[10, 10], [80, 10], [80, 30], [10, 30]]},
            ],
        }
        mock_click.return_value = {"success": True}

        result = click_text("Click Me", region={"left": 100, "top": 200, "width": 300, "height": 300})
        assert result["success"] is True
        # Center of bbox is (45, 20), plus region offset (100, 200)
        assert result["x"] == 145
        assert result["y"] == 220


# ---------------------------------------------------------------------------
# wait_for_window
# ---------------------------------------------------------------------------
class TestWaitForWindow:
    @patch("src.tools.compound.enumerate_windows")
    def test_finds_window_immediately(self, mock_enum):
        from src.tools.compound import wait_for_window

        mock_enum.return_value = [
            {"title": "Notepad - Untitled", "process_name": "notepad.exe", "hwnd": 1, "rect": {}},
        ]

        result = wait_for_window(title="Notepad", timeout=2)
        assert result["success"] is True
        assert "notepad" in result["title"].lower()
        assert result["elapsed_seconds"] < 1

    @patch("src.tools.compound.enumerate_windows")
    def test_finds_by_process(self, mock_enum):
        from src.tools.compound import wait_for_window

        mock_enum.return_value = [
            {"title": "My App", "process_name": "myapp.exe", "hwnd": 1, "rect": {}},
        ]

        result = wait_for_window(process="myapp", timeout=2)
        assert result["success"] is True
        assert result["process"] == "myapp.exe"

    @patch("src.tools.compound.enumerate_windows")
    def test_timeout_when_not_found(self, mock_enum):
        from src.tools.compound import wait_for_window

        mock_enum.return_value = []  # No windows

        start = time.monotonic()
        result = wait_for_window(title="NonExistent", timeout=1, poll_interval=0.3)
        elapsed = time.monotonic() - start

        assert result["success"] is False
        assert "did not appear" in result["error"].lower()
        assert elapsed >= 0.9  # Should have waited ~1 second

    def test_requires_title_or_process(self):
        from src.tools.compound import wait_for_window

        result = wait_for_window(timeout=1)
        assert result["success"] is False
        assert "either" in result["error"].lower()

    @patch("src.tools.compound.enumerate_windows")
    def test_timeout_capped_at_30(self, mock_enum):
        from src.tools.compound import wait_for_window

        mock_enum.return_value = []

        start = time.monotonic()
        # Request 100s timeout — should be capped to 30s
        # But we don't actually want to wait 30s in tests, so use a side effect
        call_count = 0

        def enum_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                return [{"title": "Found", "process_name": "found.exe", "hwnd": 1, "rect": {}}]
            return []

        mock_enum.side_effect = enum_side_effect

        result = wait_for_window(title="Found", timeout=100, poll_interval=0.2)
        assert result["success"] is True


# ---------------------------------------------------------------------------
# type_text
# ---------------------------------------------------------------------------
class TestTypeText:
    @patch("src.tools.compound._keyboard_type")
    def test_short_text_uses_typing(self, mock_type):
        from src.tools.compound import type_text

        mock_type.return_value = {"success": True}

        result = type_text("Hello")
        assert result["success"] is True
        assert result["method_used"] == "type"
        assert result["characters"] == 5
        mock_type.assert_called_once_with("Hello", speed=0.02)

    @patch("src.tools.compound.keyboard_hotkey")
    @patch("src.tools.compound.clipboard_write")
    def test_long_text_uses_paste(self, mock_clip, mock_hotkey):
        from src.tools.compound import type_text

        mock_clip.return_value = {"success": True}
        mock_hotkey.return_value = {"success": True}

        long_text = "x" * 100
        result = type_text(long_text)
        assert result["success"] is True
        assert result["method_used"] == "paste"
        assert result["characters"] == 100
        mock_clip.assert_called_once_with(long_text)
        mock_hotkey.assert_called_once_with("ctrl+v")

    @patch("src.tools.compound._keyboard_type")
    def test_force_type_method(self, mock_type):
        from src.tools.compound import type_text

        mock_type.return_value = {"success": True}

        long_text = "x" * 100
        result = type_text(long_text, method="type")
        assert result["success"] is True
        assert result["method_used"] == "type"
        mock_type.assert_called_once_with(long_text, speed=0.02)

    @patch("src.tools.compound.keyboard_hotkey")
    @patch("src.tools.compound.clipboard_write")
    def test_force_paste_method(self, mock_clip, mock_hotkey):
        from src.tools.compound import type_text

        mock_clip.return_value = {"success": True}
        mock_hotkey.return_value = {"success": True}

        result = type_text("Hi", method="paste")
        assert result["success"] is True
        assert result["method_used"] == "paste"
        mock_clip.assert_called_once_with("Hi")

    def test_invalid_method(self):
        from src.tools.compound import type_text

        result = type_text("test", method="magic")
        assert result["success"] is False
        assert "magic" in result["error"]

    def test_empty_text(self):
        from src.tools.compound import type_text

        result = type_text("")
        assert result["success"] is False
        assert "empty" in result["error"]

    @patch("src.tools.compound._keyboard_type")
    @patch("src.tools.compound.clipboard_write")
    def test_clipboard_failure_falls_back_to_typing(self, mock_clip, mock_type):
        from src.tools.compound import type_text

        mock_clip.return_value = {"success": False, "error": "clipboard locked"}
        mock_type.return_value = {"success": True}

        long_text = "x" * 100
        result = type_text(long_text)
        assert result["success"] is True
        assert result["method_used"] == "type"
        assert "clipboard unavailable" in result["message"].lower()

    @patch("src.tools.compound._keyboard_type")
    def test_49_chars_uses_typing(self, mock_type):
        """Boundary test: text just under threshold uses typing."""
        from src.tools.compound import type_text

        mock_type.return_value = {"success": True}

        text = "x" * 49
        result = type_text(text)
        assert result["method_used"] == "type"

    @patch("src.tools.compound.keyboard_hotkey")
    @patch("src.tools.compound.clipboard_write")
    def test_50_chars_uses_paste(self, mock_clip, mock_hotkey):
        """Boundary test: text at threshold uses paste."""
        from src.tools.compound import type_text

        mock_clip.return_value = {"success": True}
        mock_hotkey.return_value = {"success": True}

        text = "x" * 50
        result = type_text(text)
        assert result["method_used"] == "paste"
