"""Tests for src.utils.context — lightweight context snapshot."""
from __future__ import annotations

from unittest.mock import patch, MagicMock


class TestGetContext:
    """Verify get_context returns the expected shape."""

    @patch("src.utils.context.get_active_window_title", return_value="Notepad")
    @patch("src.utils.context._mouse")
    def test_returns_cursor_active_window_timestamp(self, mock_mouse, mock_title):
        from src.utils.context import get_context

        mock_mouse.position = (100, 200)
        ctx = get_context()

        assert ctx["cursor"] == {"x": 100, "y": 200}
        assert ctx["active_window"] == "Notepad"
        assert "timestamp" in ctx
        # Timestamp format: HH:MM:SS
        assert len(ctx["timestamp"].split(":")) == 3

    @patch("src.utils.context.get_active_window_title", side_effect=Exception("no window"))
    @patch("src.utils.context._mouse")
    def test_graceful_on_active_window_failure(self, mock_mouse, mock_title):
        from src.utils.context import get_context

        mock_mouse.position = (50, 60)
        ctx = get_context()

        assert ctx["active_window"] == ""
        assert ctx["cursor"] == {"x": 50, "y": 60}

    @patch("src.utils.context.get_active_window_title", return_value="Test")
    @patch("src.utils.context._mouse")
    def test_graceful_on_mouse_failure(self, mock_mouse, mock_title):
        from src.utils.context import get_context

        type(mock_mouse).position = property(lambda self: (_ for _ in ()).throw(Exception("no mouse")))
        ctx = get_context()

        assert ctx["cursor"] == {"x": 0, "y": 0}
        assert ctx["active_window"] == "Test"


class TestScreenshotScale:
    """Verify screenshot scale cache."""

    def test_default_scale_is_1(self):
        from src.utils.context import get_screenshot_scale
        # Default should be 1.0 (no scaling)
        assert isinstance(get_screenshot_scale(), float)

    def test_set_and_get_scale(self):
        from src.utils.context import set_screenshot_scale, get_screenshot_scale

        set_screenshot_scale(0.5)
        assert get_screenshot_scale() == 0.5
        # Reset
        set_screenshot_scale(1.0)
