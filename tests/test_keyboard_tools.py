import sys
import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


class TestKeyboardType:
    def test_type_returns_success(self):
        from src.tools.keyboard import keyboard_type

        result = keyboard_type(text="", speed=0.0)
        assert result["success"] is True

    def test_rejects_over_max_length(self):
        from src.tools.keyboard import keyboard_type

        result = keyboard_type(text="a" * 501, max_length=500)
        assert result["success"] is False
        assert "length" in result["error"].lower()


class TestKeyboardHotkey:
    def test_valid_hotkey(self):
        from src.tools.keyboard import keyboard_hotkey

        result = keyboard_hotkey(keys="ctrl+a")
        assert result["success"] is True
