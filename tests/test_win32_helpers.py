import sys
import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


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
