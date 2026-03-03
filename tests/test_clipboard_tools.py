"""Tests for clipboard tools — clipboard_read, clipboard_write."""
import sys
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


# ---------------------------------------------------------------------------
# clipboard_read
# ---------------------------------------------------------------------------
class TestClipboardRead:
    @patch("src.tools.clipboard.win32clipboard")
    def test_reads_text_successfully(self, mock_cb):
        from src.tools.clipboard import clipboard_read

        mock_cb.CF_UNICODETEXT = 13
        mock_cb.GetClipboardData.return_value = "hello world"

        result = clipboard_read()
        assert result["success"] is True
        assert result["text"] == "hello world"
        mock_cb.OpenClipboard.assert_called_once()
        mock_cb.GetClipboardData.assert_called_once_with(13)
        mock_cb.CloseClipboard.assert_called_once()

    @patch("src.tools.clipboard.win32clipboard")
    def test_empty_clipboard_returns_empty_text(self, mock_cb):
        from src.tools.clipboard import clipboard_read

        mock_cb.CF_UNICODETEXT = 13
        mock_cb.GetClipboardData.side_effect = TypeError("no text data")

        result = clipboard_read()
        assert result["success"] is True
        assert result["text"] == ""
        assert "message" in result
        mock_cb.CloseClipboard.assert_called_once()

    @patch("src.tools.clipboard.win32clipboard")
    def test_open_clipboard_error(self, mock_cb):
        from src.tools.clipboard import clipboard_read

        mock_cb.OpenClipboard.side_effect = Exception("clipboard locked")

        result = clipboard_read()
        assert result["success"] is False
        assert "clipboard locked" in result["error"]

    @patch("src.tools.clipboard.win32clipboard")
    def test_close_clipboard_called_on_read_error(self, mock_cb):
        """CloseClipboard is called even when GetClipboardData raises a non-TypeError."""
        from src.tools.clipboard import clipboard_read

        mock_cb.CF_UNICODETEXT = 13
        mock_cb.GetClipboardData.side_effect = RuntimeError("unexpected error")

        result = clipboard_read()
        # The RuntimeError propagates to the outer except, so success is False
        assert result["success"] is False
        assert "unexpected error" in result["error"]
        # CloseClipboard should still be called via finally
        mock_cb.CloseClipboard.assert_called_once()


# ---------------------------------------------------------------------------
# clipboard_write
# ---------------------------------------------------------------------------
class TestClipboardWrite:
    @patch("src.tools.clipboard.win32clipboard")
    def test_writes_text_successfully(self, mock_cb):
        from src.tools.clipboard import clipboard_write

        mock_cb.CF_UNICODETEXT = 13

        result = clipboard_write(text="test data")
        assert result["success"] is True
        assert "9" in result["message"]  # 9 characters
        mock_cb.OpenClipboard.assert_called_once()
        mock_cb.EmptyClipboard.assert_called_once()
        mock_cb.SetClipboardText.assert_called_once_with("test data", 13)
        mock_cb.CloseClipboard.assert_called_once()

    @patch("src.tools.clipboard.win32clipboard")
    def test_writes_empty_string(self, mock_cb):
        from src.tools.clipboard import clipboard_write

        mock_cb.CF_UNICODETEXT = 13

        result = clipboard_write(text="")
        assert result["success"] is True
        assert "0" in result["message"]  # 0 characters

    @patch("src.tools.clipboard.win32clipboard")
    def test_open_clipboard_error_on_write(self, mock_cb):
        from src.tools.clipboard import clipboard_write

        mock_cb.OpenClipboard.side_effect = Exception("clipboard locked")

        result = clipboard_write(text="data")
        assert result["success"] is False
        assert "clipboard locked" in result["error"]

    @patch("src.tools.clipboard.win32clipboard")
    def test_set_clipboard_text_error(self, mock_cb):
        from src.tools.clipboard import clipboard_write

        mock_cb.CF_UNICODETEXT = 13
        mock_cb.SetClipboardText.side_effect = Exception("write failed")

        result = clipboard_write(text="data")
        # The error propagates to the outer except
        assert result["success"] is False
        assert "write failed" in result["error"]
        # CloseClipboard should still be called via finally
        mock_cb.CloseClipboard.assert_called_once()

    @patch("src.tools.clipboard.win32clipboard")
    def test_close_clipboard_called_on_write_error(self, mock_cb):
        """CloseClipboard is called even when EmptyClipboard raises."""
        from src.tools.clipboard import clipboard_write

        mock_cb.CF_UNICODETEXT = 13
        mock_cb.EmptyClipboard.side_effect = RuntimeError("cannot empty")

        result = clipboard_write(text="data")
        assert result["success"] is False
        assert "cannot empty" in result["error"]
        mock_cb.CloseClipboard.assert_called_once()
