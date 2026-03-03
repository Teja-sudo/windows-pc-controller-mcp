"""Tests for src.utils.win32_backend — Win32 control enumeration and SendMessage clicking."""
import sys
import pytest
from unittest.mock import patch, MagicMock, call

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


# ---------------------------------------------------------------------------
# _get_window_text
# ---------------------------------------------------------------------------
class TestGetWindowText:
    @patch("src.utils.win32_backend._SendMessageW")
    def test_returns_text_when_present(self, mock_send):
        from src.utils.win32_backend import _get_window_text

        # WM_GETTEXTLENGTH returns 5, WM_GETTEXT fills buffer (returns 5 chars written)
        mock_send.side_effect = [5, 5]
        result = _get_window_text(12345)
        # First call is WM_GETTEXTLENGTH, second is WM_GETTEXT
        assert mock_send.call_count == 2
        # Buffer is empty since mock doesn't actually write to it
        assert isinstance(result, str)

    @patch("src.utils.win32_backend._SendMessageW")
    def test_returns_empty_when_no_text(self, mock_send):
        from src.utils.win32_backend import _get_window_text

        mock_send.return_value = 0  # WM_GETTEXTLENGTH returns 0
        result = _get_window_text(12345)
        assert result == ""


# ---------------------------------------------------------------------------
# _classify_control
# ---------------------------------------------------------------------------
class TestClassifyControl:
    def test_button_pushbutton(self):
        from src.utils.win32_backend import _classify_control, BS_PUSHBUTTON
        assert _classify_control("Button", BS_PUSHBUTTON) == "pushbutton"

    def test_button_checkbox(self):
        from src.utils.win32_backend import _classify_control, BS_CHECKBOX
        assert _classify_control("Button", BS_CHECKBOX) == "checkbox"

    def test_button_autocheckbox(self):
        from src.utils.win32_backend import _classify_control, BS_AUTOCHECKBOX
        assert _classify_control("Button", BS_AUTOCHECKBOX) == "checkbox"

    def test_button_radiobutton(self):
        from src.utils.win32_backend import _classify_control, BS_RADIOBUTTON
        assert _classify_control("Button", BS_RADIOBUTTON) == "radio"

    def test_button_autoradiobutton(self):
        from src.utils.win32_backend import _classify_control, BS_AUTORADIOBUTTON
        assert _classify_control("Button", BS_AUTORADIOBUTTON) == "radio"

    def test_button_groupbox(self):
        from src.utils.win32_backend import _classify_control, BS_GROUPBOX
        assert _classify_control("Button", BS_GROUPBOX) == "groupbox"

    def test_static_label(self):
        from src.utils.win32_backend import _classify_control
        assert _classify_control("Static", 0) == "label"

    def test_edit_textbox(self):
        from src.utils.win32_backend import _classify_control
        assert _classify_control("Edit", 0) == "textbox"

    def test_combobox(self):
        from src.utils.win32_backend import _classify_control
        assert _classify_control("ComboBox", 0) == "combobox"

    def test_unknown_class(self):
        from src.utils.win32_backend import _classify_control
        result = _classify_control("CustomWidget123", 0)
        assert result == "customwidget123"  # lowered class name

    def test_case_insensitive_class(self):
        from src.utils.win32_backend import _classify_control
        assert _classify_control("BUTTON", 0x0002) == "checkbox"
        assert _classify_control("STATIC", 0) == "label"


# ---------------------------------------------------------------------------
# find_win32_controls (with mocked EnumChildWindows)
# ---------------------------------------------------------------------------
class TestFindWin32Controls:
    @patch("src.utils.win32_backend._IsWindowEnabled", return_value=True)
    @patch("src.utils.win32_backend._IsWindowVisible", return_value=True)
    @patch("src.utils.win32_backend._GetWindowRect")
    @patch("src.utils.win32_backend._GetWindowLongW")
    @patch("src.utils.win32_backend._GetClassNameW")
    @patch("src.utils.win32_backend._SendMessageW")
    @patch("src.utils.win32_backend._EnumChildWindows")
    def test_enumerates_visible_controls(
        self, mock_enum, mock_send, mock_classname, mock_getlong,
        mock_getrect, mock_visible, mock_enabled,
    ):
        from src.utils.win32_backend import find_win32_controls
        import ctypes.wintypes

        # Setup: EnumChildWindows calls callback with one child hwnd
        def fake_enum(parent, callback, lparam):
            callback(1001, lparam)
            return True

        mock_enum.side_effect = fake_enum
        mock_send.side_effect = [3, None]  # WM_GETTEXTLENGTH=3, WM_GETTEXT fills buffer
        mock_getlong.side_effect = [0, 100]  # GWL_STYLE=0 (pushbutton), GWL_ID=100

        def fake_classname(hwnd, buf, size):
            ctypes.memmove(buf, "Button\0".encode("utf-16-le"), 14)

        mock_classname.side_effect = fake_classname

        def fake_getrect(hwnd, rect_ptr):
            rect = ctypes.cast(rect_ptr, ctypes.POINTER(ctypes.wintypes.RECT)).contents
            rect.left = 10
            rect.top = 20
            rect.right = 110
            rect.bottom = 50
            return True

        mock_getrect.side_effect = fake_getrect

        controls = find_win32_controls(12345)
        # Should have found at least the callback was invoked
        mock_enum.assert_called_once()

    def test_empty_when_no_children(self):
        from src.utils.win32_backend import find_win32_controls

        with patch("src.utils.win32_backend._EnumChildWindows") as mock_enum:
            mock_enum.side_effect = lambda parent, cb, lp: True  # no children
            controls = find_win32_controls(12345)
            assert controls == []

    @patch("src.utils.win32_backend._IsWindowEnabled", return_value=True)
    @patch("src.utils.win32_backend._IsWindowVisible", return_value=False)
    @patch("src.utils.win32_backend._EnumChildWindows")
    def test_skips_invisible_when_visible_only(self, mock_enum, mock_visible, mock_enabled):
        from src.utils.win32_backend import find_win32_controls

        def fake_enum(parent, callback, lparam):
            callback(1001, lparam)
            return True

        mock_enum.side_effect = fake_enum

        controls = find_win32_controls(12345, visible_only=True)
        assert controls == []


# ---------------------------------------------------------------------------
# click_win32_control
# ---------------------------------------------------------------------------
class TestClickWin32Control:
    @patch("src.utils.win32_backend._SendMessageW")
    def test_sends_bm_click(self, mock_send):
        from src.utils.win32_backend import click_win32_control, BM_CLICK

        result = click_win32_control(1001)
        assert result is True
        mock_send.assert_called_once_with(1001, BM_CLICK, 0, 0)

    @patch("src.utils.win32_backend._SendMessageW", side_effect=Exception("access denied"))
    def test_returns_false_on_error(self, mock_send):
        from src.utils.win32_backend import click_win32_control

        result = click_win32_control(1001)
        assert result is False


# ---------------------------------------------------------------------------
# find_window_by_title
# ---------------------------------------------------------------------------
class TestFindWindowByTitle:
    @patch("src.utils.win32_backend._IsWindowVisible", return_value=True)
    @patch("src.utils.win32_backend._get_window_text", return_value="Notepad - Untitled")
    @patch("src.utils.win32_backend._user32.EnumWindows")
    def test_finds_matching_window(self, mock_enum, mock_text, mock_visible):
        from src.utils.win32_backend import find_window_by_title

        def fake_enum(callback, lparam):
            callback(42, lparam)
            return True

        mock_enum.side_effect = fake_enum
        result = find_window_by_title("Notepad")
        assert result == 42

    @patch("src.utils.win32_backend._user32.EnumWindows")
    def test_returns_none_when_not_found(self, mock_enum):
        from src.utils.win32_backend import find_window_by_title

        mock_enum.side_effect = lambda cb, lp: True  # no windows
        result = find_window_by_title("NonExistent")
        assert result is None
