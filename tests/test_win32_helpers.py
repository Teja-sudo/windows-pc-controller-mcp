import sys
import pytest
from unittest.mock import patch

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


class TestNormalizeUnicode:
    def test_strips_zero_width_space(self):
        from src.utils.win32_helpers import _normalize_unicode

        assert _normalize_unicode("Microsoft\u200b Edge") == "Microsoft Edge"

    def test_strips_multiple_invisible_chars(self):
        from src.utils.win32_helpers import _normalize_unicode

        text = "Hello\u200b\u200c\u200dWorld\ufeff"
        assert _normalize_unicode(text) == "HelloWorld"

    def test_preserves_normal_text(self):
        from src.utils.win32_helpers import _normalize_unicode

        assert _normalize_unicode("Normal Title - App") == "Normal Title - App"

    def test_nfc_normalization(self):
        from src.utils.win32_helpers import _normalize_unicode

        # é as combining chars (NFD) vs precomposed (NFC)
        nfd = "e\u0301"  # e + combining acute
        result = _normalize_unicode(nfd)
        assert result == "\u00e9"  # precomposed é


class TestEnumerateWindows:
    def test_returns_list_of_dicts(self):
        from src.utils.win32_helpers import enumerate_windows

        windows = enumerate_windows()
        assert isinstance(windows, list)
        if windows:
            w = windows[0]
            assert "hwnd" in w
            assert "title" in w
            assert "process_name" in w
            assert "rect" in w


class TestGetActiveWindowTitle:
    def test_returns_string(self):
        from src.utils.win32_helpers import get_active_window_title

        title = get_active_window_title()
        assert isinstance(title, str)


class TestGetWindowRectByTitle:
    def test_finds_existing_window(self):
        from src.utils.win32_helpers import get_window_rect_by_title, enumerate_windows

        windows = enumerate_windows()
        if windows:
            # Use the first window's title to test
            title = windows[0]["title"]
            rect = get_window_rect_by_title(title[:5])  # partial match
            # May or may not find it if window has zero dimensions
            if rect:
                assert "left" in rect
                assert "top" in rect
                assert "width" in rect
                assert "height" in rect
                assert rect["width"] > 0
                assert rect["height"] > 0

    def test_returns_none_for_nonexistent(self):
        from src.utils.win32_helpers import get_window_rect_by_title

        result = get_window_rect_by_title("ZZZ_NonExistent_99999")
        assert result is None

    def test_handles_unicode_in_title(self):
        """Verify that zero-width chars in window titles don't break matching."""
        from src.utils.win32_helpers import get_window_rect_by_title

        # This should not raise even with Unicode search terms
        result = get_window_rect_by_title("Microsoft\u200b Edge")
        # Result depends on whether Edge is open; just verify no crash
        assert result is None or isinstance(result, dict)
