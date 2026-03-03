# tests/test_config.py
import pytest
import yaml
import tempfile
import os
from pathlib import Path


class TestConfigLoader:
    def test_loads_default_config(self, tmp_path):
        """Loading with no user config returns secure defaults."""
        from src.config import load_config

        default_yaml = tmp_path / "default.yaml"
        default_yaml.write_text(yaml.dump({
            "security": {
                "enabled": True,
                "confirm_dangerous_actions": True,
                "confirmation_timeout_seconds": 60,
                "audit_logging": True,
                "masking": {
                    "enabled": True,
                    "mask_password_fields": True,
                    "blocked_apps": ["1Password"],
                    "blocked_regions": [],
                },
                "rate_limits": {"mouse": 60, "keyboard": 120, "screenshot": 10, "adb": 30, "gamepad": 120},
                "keyboard": {"blocked_hotkeys": ["ctrl+alt+delete"], "max_type_length": 500, "block_password_fields": True},
                "apps": {"mode": "allowlist", "allowed": []},
                "adb": {"allowed_devices": [], "allowed_commands": ["input tap"]},
                "clipboard": {"read_enabled": False, "write_enabled": True},
            },
            "tools": {"capture_screenshot": {"enabled": True}, "clipboard_read": {"enabled": False}},
        }))

        config = load_config(default_path=str(default_yaml), user_path=None)
        assert config.security.enabled is True
        assert config.security.masking.blocked_apps == ["1Password"]
        assert config.tools["clipboard_read"].enabled is False

    def test_user_config_overrides_defaults(self, tmp_path):
        """User config merges on top of defaults."""
        from src.config import load_config

        default_yaml = tmp_path / "default.yaml"
        default_yaml.write_text(yaml.dump({
            "security": {
                "enabled": True,
                "confirm_dangerous_actions": True,
                "confirmation_timeout_seconds": 60,
                "audit_logging": True,
                "masking": {"enabled": True, "mask_password_fields": True, "blocked_apps": ["1Password"], "blocked_regions": []},
                "rate_limits": {"mouse": 60, "keyboard": 120, "screenshot": 10, "adb": 30, "gamepad": 120},
                "keyboard": {"blocked_hotkeys": ["ctrl+alt+delete"], "max_type_length": 500, "block_password_fields": True},
                "apps": {"mode": "allowlist", "allowed": []},
                "adb": {"allowed_devices": [], "allowed_commands": ["input tap"]},
                "clipboard": {"read_enabled": False, "write_enabled": True},
            },
            "tools": {"clipboard_read": {"enabled": False}},
        }))

        user_yaml = tmp_path / "config.yaml"
        user_yaml.write_text(yaml.dump({
            "security": {"confirmation_timeout_seconds": 30},
            "tools": {"clipboard_read": {"enabled": True}},
        }))

        config = load_config(default_path=str(default_yaml), user_path=str(user_yaml))
        assert config.security.confirmation_timeout_seconds == 30
        assert config.security.enabled is True  # unchanged from default
        assert config.tools["clipboard_read"].enabled is True  # overridden

    def test_invalid_config_raises(self, tmp_path):
        """Invalid config values raise ValidationError."""
        from src.config import load_config

        default_yaml = tmp_path / "default.yaml"
        default_yaml.write_text(yaml.dump({
            "security": {
                "enabled": "not_a_bool",
            }
        }))

        with pytest.raises(Exception):
            load_config(default_path=str(default_yaml), user_path=None)

    def test_missing_default_file_uses_factory_defaults(self, tmp_path):
        """Missing default.yaml falls back to Pydantic factory defaults."""
        from src.config import load_config

        config = load_config(
            default_path=str(tmp_path / "nonexistent.yaml"),
            user_path=None,
        )
        assert config.security.enabled is True
        assert config.security.confirmation_timeout_seconds == 60
        assert len(config.tools) == 0

    def test_empty_yaml_file_uses_factory_defaults(self, tmp_path):
        """Empty YAML file falls back to factory defaults."""
        from src.config import load_config

        default_yaml = tmp_path / "default.yaml"
        default_yaml.write_text("")

        config = load_config(default_path=str(default_yaml), user_path=None)
        assert config.security.enabled is True

    def test_missing_user_file_ignored(self, tmp_path):
        """Non-existent user config file is silently ignored."""
        from src.config import load_config

        default_yaml = tmp_path / "default.yaml"
        default_yaml.write_text(yaml.dump({"security": {"enabled": True}}))

        config = load_config(
            default_path=str(default_yaml),
            user_path=str(tmp_path / "nonexistent.yaml"),
        )
        assert config.security.enabled is True

    def test_invalid_apps_mode_raises(self, tmp_path):
        """Invalid apps.mode value raises validation error."""
        from src.config import load_config

        default_yaml = tmp_path / "default.yaml"
        default_yaml.write_text(yaml.dump({
            "security": {"apps": {"mode": "invalid_mode"}},
        }))

        with pytest.raises(Exception):
            load_config(default_path=str(default_yaml), user_path=None)
