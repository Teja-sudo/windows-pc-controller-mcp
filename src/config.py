# src/config.py
"""Configuration loader with Pydantic validation and YAML merge."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


# --- Pydantic models ---

class MaskingConfig(BaseModel):
    enabled: bool = True
    mask_password_fields: bool = True
    blocked_apps: list[str] = Field(default_factory=lambda: [
        "1Password", "KeePass", "LastPass", "Bitwarden",
        "Windows Security", "Credential Manager",
    ])
    blocked_regions: list[dict[str, int]] = Field(default_factory=list)


class RateLimitsConfig(BaseModel):
    mouse: int = 60
    keyboard: int = 120
    screenshot: int = 10
    adb: int = 30
    gamepad: int = 120


class KeyboardSecurityConfig(BaseModel):
    blocked_hotkeys: list[str] = Field(default_factory=lambda: [
        "ctrl+alt+delete", "win+l", "alt+f4",
    ])
    max_type_length: int = 500
    block_password_fields: bool = True


class AppsConfig(BaseModel):
    mode: str = "allowlist"
    allowed: list[str] = Field(default_factory=list)


class AdbSecurityConfig(BaseModel):
    allowed_devices: list[str] = Field(default_factory=list)
    allowed_commands: list[str] = Field(default_factory=lambda: [
        "input tap", "input swipe", "input keyevent",
        "screencap", "dumpsys window",
    ])


class ClipboardConfig(BaseModel):
    read_enabled: bool = False
    write_enabled: bool = True


class SecurityConfig(BaseModel):
    enabled: bool = True
    confirm_dangerous_actions: bool = True
    confirmation_timeout_seconds: int = 60
    audit_logging: bool = True
    masking: MaskingConfig = Field(default_factory=MaskingConfig)
    rate_limits: RateLimitsConfig = Field(default_factory=RateLimitsConfig)
    keyboard: KeyboardSecurityConfig = Field(default_factory=KeyboardSecurityConfig)
    apps: AppsConfig = Field(default_factory=AppsConfig)
    adb: AdbSecurityConfig = Field(default_factory=AdbSecurityConfig)
    clipboard: ClipboardConfig = Field(default_factory=ClipboardConfig)


class ToolConfig(BaseModel):
    enabled: bool = True


class AppConfig(BaseModel):
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    tools: dict[str, ToolConfig] = Field(default_factory=dict)


# --- Loader ---

def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override wins on conflicts."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config(
    default_path: str | None = None,
    user_path: str | None = None,
) -> AppConfig:
    """Load and validate config from YAML files.

    Loads default.yaml first, then merges user config.yaml on top.
    Validates the merged result with Pydantic.
    """
    if default_path is None:
        default_path = str(Path(__file__).parent.parent / "config" / "default.yaml")

    raw: dict[str, Any] = {}

    default_file = Path(default_path)
    if default_file.exists():
        with open(default_file) as f:
            raw = yaml.safe_load(f) or {}

    if user_path is not None:
        user_file = Path(user_path)
        if user_file.exists():
            with open(user_file) as f:
                user_raw = yaml.safe_load(f) or {}
            raw = _deep_merge(raw, user_raw)

    return AppConfig.model_validate(raw)
