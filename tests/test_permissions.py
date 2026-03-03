import pytest


class TestPermissionChecker:
    def test_tool_disabled_blocks(self):
        from src.security.permissions import PermissionChecker

        checker = PermissionChecker(
            tool_configs={"clipboard_read": {"enabled": False}},
            security_config={
                "keyboard": {"blocked_hotkeys": []},
                "apps": {"mode": "allowlist", "allowed": []},
                "adb": {"allowed_commands": [], "allowed_devices": []},
            },
        )
        result = checker.check("clipboard_read", {})
        assert result.allowed is False
        assert "disabled" in result.reason.lower()

    def test_tool_enabled_allows(self):
        from src.security.permissions import PermissionChecker

        checker = PermissionChecker(
            tool_configs={"mouse_click": {"enabled": True}},
            security_config={
                "keyboard": {"blocked_hotkeys": []},
                "apps": {"mode": "allowlist", "allowed": []},
                "adb": {"allowed_commands": [], "allowed_devices": []},
            },
        )
        result = checker.check("mouse_click", {"x": 100, "y": 200})
        assert result.allowed is True

    def test_blocked_hotkey_denied(self):
        from src.security.permissions import PermissionChecker

        checker = PermissionChecker(
            tool_configs={"keyboard_hotkey": {"enabled": True}},
            security_config={
                "keyboard": {"blocked_hotkeys": ["ctrl+alt+delete", "win+l"]},
                "apps": {"mode": "allowlist", "allowed": []},
                "adb": {"allowed_commands": [], "allowed_devices": []},
            },
        )
        result = checker.check("keyboard_hotkey", {"keys": "ctrl+alt+delete"})
        assert result.allowed is False
        assert "blocked" in result.reason.lower()

    def test_app_not_in_allowlist_denied(self):
        from src.security.permissions import PermissionChecker

        checker = PermissionChecker(
            tool_configs={"launch_app": {"enabled": True}},
            security_config={
                "keyboard": {"blocked_hotkeys": []},
                "apps": {"mode": "allowlist", "allowed": ["notepad.exe"]},
                "adb": {"allowed_commands": [], "allowed_devices": []},
            },
        )
        result = checker.check("launch_app", {"app": "cmd.exe"})
        assert result.allowed is False

    def test_app_in_allowlist_allowed(self):
        from src.security.permissions import PermissionChecker

        checker = PermissionChecker(
            tool_configs={"launch_app": {"enabled": True}},
            security_config={
                "keyboard": {"blocked_hotkeys": []},
                "apps": {"mode": "allowlist", "allowed": ["notepad.exe"]},
                "adb": {"allowed_commands": [], "allowed_devices": []},
            },
        )
        result = checker.check("launch_app", {"app": "notepad.exe"})
        assert result.allowed is True

    def test_adb_command_not_in_allowlist_denied(self):
        from src.security.permissions import PermissionChecker

        checker = PermissionChecker(
            tool_configs={"adb_shell": {"enabled": True}},
            security_config={
                "keyboard": {"blocked_hotkeys": []},
                "apps": {"mode": "allowlist", "allowed": []},
                "adb": {"allowed_commands": ["input tap"], "allowed_devices": []},
            },
        )
        result = checker.check("adb_shell", {"command": "rm -rf /"})
        assert result.allowed is False

    def test_requires_confirmation_for_dangerous(self):
        from src.security.permissions import PermissionChecker

        checker = PermissionChecker(
            tool_configs={"close_window": {"enabled": True}},
            security_config={
                "keyboard": {"blocked_hotkeys": []},
                "apps": {"mode": "allowlist", "allowed": []},
                "adb": {"allowed_commands": [], "allowed_devices": []},
            },
        )
        result = checker.check("close_window", {"window": "explorer.exe"})
        assert result.allowed is True
        assert result.requires_confirmation is True
