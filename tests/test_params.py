"""Tests for src.utils.params — parameter normalization."""
from __future__ import annotations

from src.utils.params import normalize_params


class TestAliasMapping:
    """Verify alias replacement works correctly."""

    def test_focus_window_aliases(self):
        params = normalize_params("focus_window", {"window_title": "Notepad"})
        assert params == {"title": "Notepad"}

    def test_focus_window_process_alias(self):
        params = normalize_params("focus_window", {"process_name": "notepad.exe"})
        assert params == {"process": "notepad.exe"}

    def test_canonical_takes_priority_over_alias(self):
        # If both alias and canonical are provided, canonical wins
        params = normalize_params("focus_window", {"title": "Real", "window_title": "Alias"})
        assert params["title"] == "Real"

    def test_launch_app_aliases(self):
        params = normalize_params("launch_app", {"application": "notepad.exe"})
        assert params == {"app": "notepad.exe"}

    def test_keyboard_hotkey_aliases(self):
        params = normalize_params("keyboard_hotkey", {"shortcut": "ctrl+c"})
        assert params == {"keys": "ctrl+c"}

    def test_click_text_alias(self):
        params = normalize_params("click_text", {"label": "Submit"})
        assert params == {"text": "Submit"}

    def test_open_url_alias(self):
        params = normalize_params("open_url", {"link": "https://example.com"})
        assert params == {"url": "https://example.com"}

    def test_unknown_tool_passes_through(self):
        params = normalize_params("some_unknown_tool", {"foo": "bar"})
        assert params == {"foo": "bar"}

    def test_mouse_click_count_alias(self):
        params = normalize_params("mouse_click", {"count": 2})
        assert params == {"clicks": 2}


class TestTypeCoercion:
    """Verify string-to-int coercion for coordinate fields."""

    def test_string_x_y_coerced_to_int(self):
        params = normalize_params("mouse_click", {"x": "100", "y": "200"})
        assert params["x"] == 100
        assert params["y"] == 200

    def test_already_int_unchanged(self):
        params = normalize_params("mouse_click", {"x": 100, "y": 200})
        assert params["x"] == 100

    def test_non_numeric_string_left_as_is(self):
        params = normalize_params("mouse_click", {"x": "not_a_number"})
        assert params["x"] == "not_a_number"

    def test_clicks_coerced(self):
        params = normalize_params("mouse_click", {"clicks": "3"})
        assert params["clicks"] == 3

    def test_monitor_coerced(self):
        params = normalize_params("capture_screenshot", {"monitor": "1"})
        assert params["monitor"] == 1


class TestCombinedAliasAndCoercion:
    """Verify alias + coercion work together."""

    def test_alias_then_coercion(self):
        params = normalize_params("mouse_click", {"count": "5", "x": "100"})
        assert params["clicks"] == 5
        assert params["x"] == 100
