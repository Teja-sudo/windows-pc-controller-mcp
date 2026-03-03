import pytest
from unittest.mock import MagicMock, patch
import yaml
import tempfile


class TestSecurityMiddleware:
    def _make_config(self, **overrides):
        from src.config import load_config

        base = {
            "security": {
                "enabled": True,
                "confirm_dangerous_actions": False,
                "confirmation_timeout_seconds": 60,
                "audit_logging": False,
                "masking": {"enabled": True, "mask_password_fields": True, "blocked_apps": [], "blocked_regions": []},
                "rate_limits": {"mouse": 60, "keyboard": 120, "screenshot": 10, "adb": 30, "gamepad": 120},
                "keyboard": {"blocked_hotkeys": ["ctrl+alt+delete"], "max_type_length": 500, "block_password_fields": True},
                "apps": {"mode": "allowlist", "allowed": ["notepad.exe"]},
                "adb": {"allowed_devices": [], "allowed_commands": ["input tap"]},
                "clipboard": {"read_enabled": False, "write_enabled": True},
            },
            "tools": {
                "mouse_click": {"enabled": True},
                "clipboard_read": {"enabled": False},
                "launch_app": {"enabled": True},
                "keyboard_hotkey": {"enabled": True},
            },
        }
        for key, val in overrides.items():
            parts = key.split(".")
            d = base
            for p in parts[:-1]:
                d = d[p]
            d[parts[-1]] = val

        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.dump(base, tmp)
        tmp.close()
        return load_config(default_path=tmp.name)

    def test_allows_enabled_tool(self):
        from src.security.middleware import SecurityMiddleware

        config = self._make_config()
        mw = SecurityMiddleware(config)
        result = mw.pre_check("mouse_click", {"x": 100, "y": 200})
        assert result.allowed is True

    def test_blocks_disabled_tool(self):
        from src.security.middleware import SecurityMiddleware

        config = self._make_config()
        mw = SecurityMiddleware(config)
        result = mw.pre_check("clipboard_read", {})
        assert result.allowed is False

    def test_blocks_blocked_hotkey(self):
        from src.security.middleware import SecurityMiddleware

        config = self._make_config()
        mw = SecurityMiddleware(config)
        result = mw.pre_check("keyboard_hotkey", {"keys": "ctrl+alt+delete"})
        assert result.allowed is False

    def test_rate_limiting(self):
        from src.security.middleware import SecurityMiddleware

        config = self._make_config(**{"security.rate_limits": {
            "mouse": 2, "keyboard": 120, "screenshot": 10, "adb": 30, "gamepad": 120,
        }})
        mw = SecurityMiddleware(config)
        mw.pre_check("mouse_click", {"x": 1, "y": 1})
        mw.pre_check("mouse_click", {"x": 1, "y": 1})
        result = mw.pre_check("mouse_click", {"x": 1, "y": 1})
        assert result.allowed is False
        assert "rate" in result.reason.lower()

    def test_security_disabled_allows_all(self):
        from src.security.middleware import SecurityMiddleware

        config = self._make_config(**{"security.enabled": False})
        mw = SecurityMiddleware(config)
        result = mw.pre_check("clipboard_read", {})
        assert result.allowed is True

    def test_dangerous_tool_requires_confirmation(self):
        from src.security.middleware import SecurityMiddleware

        config = self._make_config(**{"security.confirm_dangerous_actions": True})
        mw = SecurityMiddleware(config)
        result = mw.pre_check("launch_app", {"app": "notepad.exe"})
        assert result.allowed is True
        assert result.requires_confirmation is True
