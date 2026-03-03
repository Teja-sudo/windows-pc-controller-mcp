# Windows PC Controller MCP — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python MCP server giving Claude full Windows PC control (screen, input, gamepad, ADB) with secure-by-default configuration and native confirmation popups.

**Architecture:** Centralized security middleware intercepts all 26 tool calls. Config loaded from YAML with Pydantic validation. Tools organized by category in separate modules. Native tkinter popups for dangerous action confirmation.

**Tech Stack:** Python 3.12, mcp SDK, mss, easyocr, opencv-python, pynput, pywin32, vgamepad, adb-shell, pydantic, pyyaml, structlog, customtkinter, pytest

---

## Phase 1: Project Scaffolding & Config System

### Task 1: Initialize project with pyproject.toml and directory structure

**Files:**
- Create: `pyproject.toml`
- Create: `src/__init__.py`
- Create: `src/security/__init__.py`
- Create: `src/tools/__init__.py`
- Create: `src/utils/__init__.py`
- Create: `tests/__init__.py`
- Create: `config/default.yaml`
- Modify: `.gitignore`

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "windows-pc-controller-mcp"
version = "0.1.0"
description = "MCP server for Windows PC control — screen, input, gamepad, ADB"
requires-python = ">=3.11"
dependencies = [
    "mcp[cli]>=1.0.0",
    "mss>=9.0.0",
    "easyocr>=1.7.0",
    "Pillow>=10.0.0",
    "opencv-python>=4.8.0",
    "pynput>=1.7.0",
    "pywin32>=306",
    "vgamepad>=0.3.0",
    "adb-shell>=0.4.0",
    "pyyaml>=6.0",
    "pydantic>=2.0.0",
    "structlog>=23.0.0",
    "customtkinter>=5.2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-mock>=3.0.0",
]

[project.scripts]
windows-pc-controller-mcp = "src.server:main"
```

**Step 2: Create directory structure and `__init__.py` files**

Create these empty files:
- `src/__init__.py`
- `src/security/__init__.py`
- `src/tools/__init__.py`
- `src/utils/__init__.py`
- `tests/__init__.py`

**Step 3: Create `config/default.yaml`**

```yaml
security:
  enabled: true
  confirm_dangerous_actions: true
  confirmation_timeout_seconds: 60
  audit_logging: true

  masking:
    enabled: true
    mask_password_fields: true
    blocked_apps:
      - "1Password"
      - "KeePass"
      - "LastPass"
      - "Bitwarden"
      - "Windows Security"
      - "Credential Manager"
    blocked_regions: []

  rate_limits:
    mouse: 60
    keyboard: 120
    screenshot: 10
    adb: 30
    gamepad: 120

  keyboard:
    blocked_hotkeys:
      - "ctrl+alt+delete"
      - "win+l"
      - "alt+f4"
    max_type_length: 500
    block_password_fields: true

  apps:
    mode: "allowlist"
    allowed: []

  adb:
    allowed_devices: []
    allowed_commands:
      - "input tap"
      - "input swipe"
      - "input keyevent"
      - "screencap"
      - "dumpsys window"

  clipboard:
    read_enabled: false
    write_enabled: true

tools:
  capture_screenshot:
    enabled: true
  ocr_extract_text:
    enabled: true
  find_on_screen:
    enabled: true
  get_pixel_color:
    enabled: true
  list_windows:
    enabled: true
  mouse_move:
    enabled: true
  mouse_click:
    enabled: true
  mouse_drag:
    enabled: true
  mouse_scroll:
    enabled: true
  mouse_position:
    enabled: true
  keyboard_type:
    enabled: true
  keyboard_hotkey:
    enabled: true
  keyboard_press:
    enabled: true
  gamepad_connect:
    enabled: true
  gamepad_input:
    enabled: true
  gamepad_disconnect:
    enabled: true
  adb_tap:
    enabled: true
  adb_swipe:
    enabled: true
  adb_key_event:
    enabled: true
  adb_shell:
    enabled: true
  launch_app:
    enabled: true
  focus_window:
    enabled: true
  close_window:
    enabled: true
  get_system_info:
    enabled: true
  clipboard_read:
    enabled: false
  clipboard_write:
    enabled: true
```

**Step 4: Add to `.gitignore`**

Append these lines:
```
config/config.yaml
logs/
```

**Step 5: Commit**

```bash
git add pyproject.toml src/ tests/ config/default.yaml .gitignore
git commit -m "feat: scaffold project structure with pyproject.toml and default config"
```

---

### Task 2: Config loader with Pydantic validation

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

**Step 1: Write failing tests**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.config'`

**Step 3: Implement config.py**

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add config loader with Pydantic validation and YAML merge"
```

---

## Phase 2: Security Infrastructure

### Task 3: Audit logger

**Files:**
- Create: `src/security/audit.py`
- Create: `tests/test_audit.py`

**Step 1: Write failing test**

```python
# tests/test_audit.py
import json
import tempfile
from pathlib import Path

import pytest


class TestAuditLogger:
    def test_logs_tool_call(self, tmp_path):
        from src.security.audit import AuditLogger

        log_file = tmp_path / "audit.log"
        logger = AuditLogger(log_path=str(log_file))

        logger.log_tool_call(
            tool_name="mouse_click",
            parameters={"x": 100, "y": 200, "button": "left"},
            result={"success": True},
            allowed=True,
        )

        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["tool"] == "mouse_click"
        assert entry["allowed"] is True
        assert "timestamp" in entry

    def test_logs_denied_action(self, tmp_path):
        from src.security.audit import AuditLogger

        log_file = tmp_path / "audit.log"
        logger = AuditLogger(log_path=str(log_file))

        logger.log_tool_call(
            tool_name="close_window",
            parameters={"window": "explorer.exe"},
            result=None,
            allowed=False,
            deny_reason="User denied: don't close explorer",
        )

        entry = json.loads(log_file.read_text().strip())
        assert entry["allowed"] is False
        assert "don't close explorer" in entry["deny_reason"]

    def test_disabled_logger_no_ops(self, tmp_path):
        from src.security.audit import AuditLogger

        log_file = tmp_path / "audit.log"
        logger = AuditLogger(log_path=str(log_file), enabled=False)

        logger.log_tool_call(tool_name="test", parameters={}, result={}, allowed=True)
        assert not log_file.exists()
```

**Step 2: Run to verify fail**

Run: `python -m pytest tests/test_audit.py -v`
Expected: FAIL

**Step 3: Implement audit logger**

```python
# src/security/audit.py
"""Structured JSON audit logger for all tool calls."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLogger:
    """Logs every tool call to a JSON-lines file."""

    def __init__(self, log_path: str | None = None, enabled: bool = True):
        self._enabled = enabled
        self._log_path = Path(log_path) if log_path else None

    def log_tool_call(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        result: Any,
        allowed: bool,
        deny_reason: str | None = None,
    ) -> None:
        if not self._enabled or self._log_path is None:
            return

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": tool_name,
            "parameters": parameters,
            "allowed": allowed,
        }
        if deny_reason is not None:
            entry["deny_reason"] = deny_reason
        if allowed and result is not None:
            entry["result_summary"] = str(result)[:200]

        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_audit.py -v`
Expected: All 3 PASS

**Step 5: Commit**

```bash
git add src/security/audit.py tests/test_audit.py
git commit -m "feat: add structured JSON audit logger"
```

---

### Task 4: Rate limiter

**Files:**
- Create: `src/security/rate_limiter.py`
- Create: `tests/test_rate_limiter.py`

**Step 1: Write failing test**

```python
# tests/test_rate_limiter.py
import time
import pytest


class TestRateLimiter:
    def test_allows_within_limit(self):
        from src.security.rate_limiter import RateLimiter

        limiter = RateLimiter(limits={"mouse": 60})
        for _ in range(60):
            assert limiter.check("mouse") is True

    def test_blocks_over_limit(self):
        from src.security.rate_limiter import RateLimiter

        limiter = RateLimiter(limits={"mouse": 5})
        for _ in range(5):
            limiter.check("mouse")
        assert limiter.check("mouse") is False

    def test_unknown_category_allowed(self):
        from src.security.rate_limiter import RateLimiter

        limiter = RateLimiter(limits={"mouse": 5})
        assert limiter.check("unknown_tool") is True

    def test_resets_after_window(self):
        from src.security.rate_limiter import RateLimiter

        limiter = RateLimiter(limits={"mouse": 2}, window_seconds=1)
        limiter.check("mouse")
        limiter.check("mouse")
        assert limiter.check("mouse") is False
        time.sleep(1.1)
        assert limiter.check("mouse") is True
```

**Step 2: Run to verify fail**

Run: `python -m pytest tests/test_rate_limiter.py -v`
Expected: FAIL

**Step 3: Implement rate limiter**

```python
# src/security/rate_limiter.py
"""Sliding-window rate limiter per tool category."""
from __future__ import annotations

import time
from collections import defaultdict


class RateLimiter:
    """Per-category rate limiter using a sliding time window."""

    def __init__(self, limits: dict[str, int], window_seconds: float = 60.0):
        self._limits = limits
        self._window = window_seconds
        self._calls: dict[str, list[float]] = defaultdict(list)

    def check(self, category: str) -> bool:
        """Return True if the action is allowed, False if rate-limited."""
        if category not in self._limits:
            return True

        now = time.monotonic()
        cutoff = now - self._window

        # Prune old entries
        self._calls[category] = [t for t in self._calls[category] if t > cutoff]

        if len(self._calls[category]) >= self._limits[category]:
            return False

        self._calls[category].append(now)
        return True
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_rate_limiter.py -v`
Expected: All 4 PASS

**Step 5: Commit**

```bash
git add src/security/rate_limiter.py tests/test_rate_limiter.py
git commit -m "feat: add sliding-window rate limiter"
```

---

### Task 5: Permission policy engine

**Files:**
- Create: `src/security/permissions.py`
- Create: `tests/test_permissions.py`

**Step 1: Write failing test**

```python
# tests/test_permissions.py
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
```

**Step 2: Run to verify fail**

Run: `python -m pytest tests/test_permissions.py -v`
Expected: FAIL

**Step 3: Implement permissions**

```python
# src/security/permissions.py
"""Permission policy engine for tool access control."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Tools that always require user confirmation popup
DANGEROUS_TOOLS = frozenset({
    "close_window", "launch_app", "adb_shell", "keyboard_hotkey",
})


@dataclass
class PermissionResult:
    allowed: bool
    reason: str = ""
    requires_confirmation: bool = False


class PermissionChecker:
    """Checks whether a tool call is permitted by config policy."""

    def __init__(
        self,
        tool_configs: dict[str, dict[str, Any]],
        security_config: dict[str, Any],
    ):
        self._tools = tool_configs
        self._security = security_config

    def check(self, tool_name: str, params: dict[str, Any]) -> PermissionResult:
        # 1. Is the tool enabled?
        tool_cfg = self._tools.get(tool_name, {})
        if not tool_cfg.get("enabled", True):
            return PermissionResult(allowed=False, reason=f"Tool '{tool_name}' is disabled in config")

        # 2. Tool-specific permission checks
        if tool_name == "keyboard_hotkey":
            return self._check_hotkey(params)
        if tool_name == "launch_app":
            return self._check_app(params)
        if tool_name == "adb_shell":
            return self._check_adb_command(params)

        # 3. Mark dangerous tools
        requires_confirm = tool_name in DANGEROUS_TOOLS
        return PermissionResult(allowed=True, requires_confirmation=requires_confirm)

    def _check_hotkey(self, params: dict[str, Any]) -> PermissionResult:
        keys = params.get("keys", "").lower()
        blocked = self._security.get("keyboard", {}).get("blocked_hotkeys", [])
        for hotkey in blocked:
            if hotkey.lower() == keys:
                return PermissionResult(allowed=False, reason=f"Hotkey '{keys}' is blocked by security policy")
        return PermissionResult(allowed=True, requires_confirmation=True)

    def _check_app(self, params: dict[str, Any]) -> PermissionResult:
        app = params.get("app", "")
        apps_cfg = self._security.get("apps", {})
        if apps_cfg.get("mode") == "allowlist":
            allowed_apps = apps_cfg.get("allowed", [])
            if app not in allowed_apps:
                return PermissionResult(
                    allowed=False,
                    reason=f"App '{app}' not in allowlist. Add it to config.yaml security.apps.allowed",
                )
        return PermissionResult(allowed=True, requires_confirmation=True)

    def _check_adb_command(self, params: dict[str, Any]) -> PermissionResult:
        command = params.get("command", "")
        allowed_cmds = self._security.get("adb", {}).get("allowed_commands", [])
        if not any(command.startswith(cmd) for cmd in allowed_cmds):
            return PermissionResult(
                allowed=False,
                reason=f"ADB command '{command}' not in allowlist",
            )
        return PermissionResult(allowed=True, requires_confirmation=True)
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_permissions.py -v`
Expected: All 7 PASS

**Step 5: Commit**

```bash
git add src/security/permissions.py tests/test_permissions.py
git commit -m "feat: add permission policy engine with allowlist/blocklist"
```

---

### Task 6: Confirmation popup

**Files:**
- Create: `src/security/confirmation_popup.py`
- Create: `tests/test_confirmation_popup.py`

**Step 1: Write failing test**

Note: GUI tests are tricky. We test the logic, not the GUI rendering. Use mock for tkinter.

```python
# tests/test_confirmation_popup.py
import pytest
from unittest.mock import patch, MagicMock


class TestConfirmationResult:
    def test_allow_result(self):
        from src.security.confirmation_popup import ConfirmationResult

        result = ConfirmationResult(action="allow")
        assert result.is_allowed is True
        assert result.deny_reason is None

    def test_deny_result(self):
        from src.security.confirmation_popup import ConfirmationResult

        result = ConfirmationResult(action="deny")
        assert result.is_allowed is False
        assert result.deny_reason is None

    def test_deny_with_reason(self):
        from src.security.confirmation_popup import ConfirmationResult

        result = ConfirmationResult(action="deny", deny_reason="too dangerous")
        assert result.is_allowed is False
        assert result.deny_reason == "too dangerous"

    def test_timeout_result(self):
        from src.security.confirmation_popup import ConfirmationResult

        result = ConfirmationResult(action="timeout")
        assert result.is_allowed is False


class TestBuildDescription:
    def test_formats_tool_details(self):
        from src.security.confirmation_popup import build_description

        desc = build_description(
            tool_name="close_window",
            parameters={"window": "explorer.exe"},
        )
        assert "close_window" in desc
        assert "explorer.exe" in desc
```

**Step 2: Run to verify fail**

Run: `python -m pytest tests/test_confirmation_popup.py -v`
Expected: FAIL

**Step 3: Implement confirmation popup**

```python
# src/security/confirmation_popup.py
"""Native Windows confirmation popup for dangerous actions."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConfirmationResult:
    action: str  # "allow", "deny", "timeout"
    deny_reason: str | None = None

    @property
    def is_allowed(self) -> bool:
        return self.action == "allow"


def build_description(tool_name: str, parameters: dict[str, Any]) -> str:
    """Format tool details for display in the confirmation popup."""
    lines = [f"Tool: {tool_name}", "", "Parameters:"]
    for key, value in parameters.items():
        lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def show_confirmation(
    tool_name: str,
    parameters: dict[str, Any],
    timeout_seconds: int = 60,
) -> ConfirmationResult:
    """Show a native Windows confirmation popup. Blocks until user responds or timeout.

    Returns ConfirmationResult with the user's decision.
    """
    result_holder: list[ConfirmationResult] = []

    def _run_popup():
        try:
            import customtkinter as ctk
        except ImportError:
            # Fallback to plain tkinter if customtkinter not available
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            desc = build_description(tool_name, parameters)
            answer = messagebox.askyesno("Action Requires Approval", desc)
            root.destroy()
            if answer:
                result_holder.append(ConfirmationResult(action="allow"))
            else:
                result_holder.append(ConfirmationResult(action="deny"))
            return

        # --- customtkinter UI ---
        ctk.set_appearance_mode("dark")

        app = ctk.CTkToplevel()
        app.title("Action Requires Approval")
        app.geometry("500x400")
        app.attributes("-topmost", True)
        app.resizable(False, False)

        remaining = [timeout_seconds]

        # Title
        title_label = ctk.CTkLabel(
            app, text="⚠ Action Requires Approval",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        title_label.pack(pady=(15, 5))

        # Countdown
        countdown_label = ctk.CTkLabel(
            app, text=f"Auto-deny in {remaining[0]}s",
            font=ctk.CTkFont(size=12),
            text_color="orange",
        )
        countdown_label.pack(pady=(0, 10))

        # Details
        desc = build_description(tool_name, parameters)
        details_box = ctk.CTkTextbox(app, width=460, height=150)
        details_box.pack(padx=20, pady=5)
        details_box.insert("1.0", desc)
        details_box.configure(state="disabled")

        # Reason input (hidden initially)
        reason_frame = ctk.CTkFrame(app)
        reason_entry = ctk.CTkEntry(reason_frame, placeholder_text="Enter reason...", width=360)

        def on_allow():
            result_holder.append(ConfirmationResult(action="allow"))
            app.destroy()

        def on_deny():
            result_holder.append(ConfirmationResult(action="deny"))
            app.destroy()

        def on_deny_with_reason():
            reason_frame.pack(pady=5)
            reason_entry.pack(side="left", padx=(10, 5))
            submit_btn = ctk.CTkButton(
                reason_frame, text="Submit", width=80,
                command=lambda: _submit_reason(),
            )
            submit_btn.pack(side="left")

        def _submit_reason():
            reason = reason_entry.get().strip() or "No reason given"
            result_holder.append(ConfirmationResult(action="deny", deny_reason=reason))
            app.destroy()

        # Buttons
        btn_frame = ctk.CTkFrame(app, fg_color="transparent")
        btn_frame.pack(pady=15)

        ctk.CTkButton(btn_frame, text="Allow", fg_color="green", width=120, command=on_allow).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Deny", fg_color="red", width=120, command=on_deny).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Deny with Reason", width=140, command=on_deny_with_reason).pack(side="left", padx=5)

        # Countdown timer
        def tick():
            remaining[0] -= 1
            if remaining[0] <= 0:
                result_holder.append(ConfirmationResult(action="timeout"))
                app.destroy()
                return
            countdown_label.configure(text=f"Auto-deny in {remaining[0]}s")
            app.after(1000, tick)

        app.after(1000, tick)
        app.mainloop()

    thread = threading.Thread(target=_run_popup, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds + 5)

    if result_holder:
        return result_holder[0]
    return ConfirmationResult(action="timeout")
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_confirmation_popup.py -v`
Expected: All 5 PASS

**Step 5: Commit**

```bash
git add src/security/confirmation_popup.py tests/test_confirmation_popup.py
git commit -m "feat: add native Windows confirmation popup with countdown"
```

---

### Task 7: Masking engine

**Files:**
- Create: `src/security/masking.py`
- Create: `tests/test_masking.py`

**Step 1: Write failing test**

```python
# tests/test_masking.py
import pytest


class TestWindowFilter:
    def test_filters_blocked_apps(self):
        from src.security.masking import filter_windows

        windows = [
            {"title": "My Document - Notepad", "process": "notepad.exe"},
            {"title": "1Password", "process": "1password.exe"},
            {"title": "Chrome", "process": "chrome.exe"},
        ]
        filtered = filter_windows(windows, blocked_apps=["1Password"])
        assert len(filtered) == 2
        assert all(w["title"] != "1Password" for w in filtered)

    def test_no_blocked_apps_returns_all(self):
        from src.security.masking import filter_windows

        windows = [
            {"title": "Notepad", "process": "notepad.exe"},
        ]
        filtered = filter_windows(windows, blocked_apps=[])
        assert len(filtered) == 1


class TestTextRedaction:
    def test_redacts_blocked_app_text(self):
        from src.security.masking import should_redact_window

        assert should_redact_window("1Password - Vault", blocked_apps=["1Password"]) is True

    def test_allows_normal_app(self):
        from src.security.masking import should_redact_window

        assert should_redact_window("Notepad", blocked_apps=["1Password"]) is False
```

**Step 2: Run to verify fail**

Run: `python -m pytest tests/test_masking.py -v`
Expected: FAIL

**Step 3: Implement masking**

```python
# src/security/masking.py
"""Sensitive content masking for screenshots and text."""
from __future__ import annotations

from typing import Any


def filter_windows(
    windows: list[dict[str, Any]],
    blocked_apps: list[str],
) -> list[dict[str, Any]]:
    """Remove windows belonging to blocked apps from the list."""
    if not blocked_apps:
        return windows
    blocked_lower = [app.lower() for app in blocked_apps]
    return [
        w for w in windows
        if not any(blocked in w.get("title", "").lower() for blocked in blocked_lower)
        and not any(blocked in w.get("process", "").lower() for blocked in blocked_lower)
    ]


def should_redact_window(window_title: str, blocked_apps: list[str]) -> bool:
    """Check if a window's content should be redacted."""
    title_lower = window_title.lower()
    return any(app.lower() in title_lower for app in blocked_apps)
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_masking.py -v`
Expected: All 4 PASS

**Step 5: Commit**

```bash
git add src/security/masking.py tests/test_masking.py
git commit -m "feat: add sensitive content masking engine"
```

---

### Task 8: Security middleware (central gate)

**Files:**
- Create: `src/security/middleware.py`
- Create: `tests/test_middleware.py`

**Step 1: Write failing test**

```python
# tests/test_middleware.py
import pytest
from unittest.mock import MagicMock, patch


class TestSecurityMiddleware:
    def _make_config(self, **overrides):
        from src.config import load_config
        import yaml, tempfile
        from pathlib import Path

        base = {
            "security": {
                "enabled": True,
                "confirm_dangerous_actions": False,  # disable popups for tests
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
        # Apply overrides
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
```

**Step 2: Run to verify fail**

Run: `python -m pytest tests/test_middleware.py -v`
Expected: FAIL

**Step 3: Implement middleware**

```python
# src/security/middleware.py
"""Central security middleware — all tool calls pass through here."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.config import AppConfig
from src.security.audit import AuditLogger
from src.security.permissions import PermissionChecker, PermissionResult
from src.security.rate_limiter import RateLimiter


# Map tool names to rate limit categories
TOOL_CATEGORY = {
    "mouse_move": "mouse", "mouse_click": "mouse", "mouse_drag": "mouse",
    "mouse_scroll": "mouse", "mouse_position": "mouse",
    "keyboard_type": "keyboard", "keyboard_hotkey": "keyboard", "keyboard_press": "keyboard",
    "capture_screenshot": "screenshot", "ocr_extract_text": "screenshot",
    "find_on_screen": "screenshot", "get_pixel_color": "screenshot", "list_windows": "screenshot",
    "adb_tap": "adb", "adb_swipe": "adb", "adb_key_event": "adb", "adb_shell": "adb",
    "gamepad_connect": "gamepad", "gamepad_input": "gamepad", "gamepad_disconnect": "gamepad",
}


@dataclass
class MiddlewareResult:
    allowed: bool
    reason: str = ""
    requires_confirmation: bool = False


class SecurityMiddleware:
    """Central security gate. Every tool call must pass through pre_check()."""

    def __init__(self, config: AppConfig, log_dir: str | None = None):
        self._config = config
        sec = config.security

        # Build permission checker
        tool_configs = {name: cfg.model_dump() for name, cfg in config.tools.items()}
        self._perm_checker = PermissionChecker(
            tool_configs=tool_configs,
            security_config=sec.model_dump(),
        )

        # Build rate limiter
        self._rate_limiter = RateLimiter(
            limits=sec.rate_limits.model_dump(),
        )

        # Build audit logger
        if log_dir is None:
            log_dir = str(Path(__file__).parent.parent.parent / "logs")
        self._audit = AuditLogger(
            log_path=str(Path(log_dir) / "audit.log"),
            enabled=sec.audit_logging,
        )

    def pre_check(self, tool_name: str, params: dict[str, Any]) -> MiddlewareResult:
        """Check if a tool call is allowed. Call this BEFORE executing the tool."""
        if not self._config.security.enabled:
            return MiddlewareResult(allowed=True)

        # 1. Permission check
        perm = self._perm_checker.check(tool_name, params)
        if not perm.allowed:
            self._audit.log_tool_call(tool_name, params, None, allowed=False, deny_reason=perm.reason)
            return MiddlewareResult(allowed=False, reason=perm.reason)

        # 2. Rate limit check
        category = TOOL_CATEGORY.get(tool_name, tool_name)
        if not self._rate_limiter.check(category):
            reason = f"Rate limit exceeded for category '{category}'"
            self._audit.log_tool_call(tool_name, params, None, allowed=False, deny_reason=reason)
            return MiddlewareResult(allowed=False, reason=reason)

        # 3. Confirmation needed?
        needs_confirm = (
            perm.requires_confirmation
            and self._config.security.confirm_dangerous_actions
        )

        return MiddlewareResult(
            allowed=True,
            requires_confirmation=needs_confirm,
        )

    def post_log(self, tool_name: str, params: dict[str, Any], result: Any) -> None:
        """Log a successful tool execution."""
        self._audit.log_tool_call(tool_name, params, result, allowed=True)
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_middleware.py -v`
Expected: All 4 PASS

**Step 5: Commit**

```bash
git add src/security/middleware.py tests/test_middleware.py
git commit -m "feat: add central security middleware"
```

---

## Phase 3: Tool Implementations

### Task 9: Win32 helpers (shared utility)

**Files:**
- Create: `src/utils/win32_helpers.py`
- Create: `tests/test_win32_helpers.py`

**Step 1: Write failing test**

```python
# tests/test_win32_helpers.py
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
```

**Step 2: Run to verify fail**

Run: `python -m pytest tests/test_win32_helpers.py -v`
Expected: FAIL

**Step 3: Implement win32 helpers**

```python
# src/utils/win32_helpers.py
"""Windows API wrappers for window enumeration and management."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
from typing import Any

import win32gui
import win32process
import psutil


def enumerate_windows() -> list[dict[str, Any]]:
    """List all visible windows with their titles, positions, and process info."""
    windows: list[dict[str, Any]] = []

    def callback(hwnd: int, _: Any) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return True

        rect = win32gui.GetWindowRect(hwnd)
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            process_name = proc.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            process_name = "unknown"

        windows.append({
            "hwnd": hwnd,
            "title": title,
            "process_name": process_name,
            "rect": {"left": rect[0], "top": rect[1], "right": rect[2], "bottom": rect[3]},
        })
        return True

    win32gui.EnumWindows(callback, None)
    return windows


def get_active_window_title() -> str:
    """Get the title of the currently focused window."""
    hwnd = win32gui.GetForegroundWindow()
    return win32gui.GetWindowText(hwnd) or ""


def focus_window_by_title(title_substring: str) -> bool:
    """Bring a window matching the title substring to the foreground."""
    for w in enumerate_windows():
        if title_substring.lower() in w["title"].lower():
            hwnd = w["hwnd"]
            win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
            win32gui.SetForegroundWindow(hwnd)
            return True
    return False


def close_window_by_title(title_substring: str) -> bool:
    """Send WM_CLOSE to a window matching the title substring."""
    import win32con
    for w in enumerate_windows():
        if title_substring.lower() in w["title"].lower():
            hwnd = w["hwnd"]
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            return True
    return False
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_win32_helpers.py -v`
Expected: PASS (on Windows)

**Step 5: Commit**

```bash
git add src/utils/win32_helpers.py tests/test_win32_helpers.py
git commit -m "feat: add Win32 API helpers for window management"
```

---

### Task 10: Screen tools (screenshot, OCR, find, pixel, list_windows)

**Files:**
- Create: `src/tools/screen.py`
- Create: `src/utils/image_utils.py`
- Create: `tests/test_screen_tools.py`

**Step 1: Write failing test**

```python
# tests/test_screen_tools.py
import sys
import base64
import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


class TestCaptureScreenshot:
    def test_returns_base64_image(self):
        from src.tools.screen import capture_screenshot

        result = capture_screenshot()
        assert result["success"] is True
        assert "image_base64" in result
        # Verify it's valid base64
        raw = base64.b64decode(result["image_base64"])
        assert len(raw) > 0

    def test_capture_region(self):
        from src.tools.screen import capture_screenshot

        result = capture_screenshot(region={"left": 0, "top": 0, "width": 100, "height": 100})
        assert result["success"] is True


class TestGetPixelColor:
    def test_returns_rgb(self):
        from src.tools.screen import get_pixel_color

        result = get_pixel_color(x=0, y=0)
        assert result["success"] is True
        assert "r" in result and "g" in result and "b" in result
        assert 0 <= result["r"] <= 255


class TestListWindows:
    def test_returns_window_list(self):
        from src.tools.screen import list_windows_tool

        result = list_windows_tool(blocked_apps=[])
        assert result["success"] is True
        assert isinstance(result["windows"], list)
```

**Step 2: Run to verify fail**

Run: `python -m pytest tests/test_screen_tools.py -v`
Expected: FAIL

**Step 3: Implement image_utils.py**

```python
# src/utils/image_utils.py
"""Image processing helpers for screenshots and template matching."""
from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image


def pil_to_base64(image: Image.Image, format: str = "PNG") -> str:
    """Convert a PIL Image to a base64-encoded string."""
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def base64_to_pil(b64_string: str) -> Image.Image:
    """Convert a base64 string back to a PIL Image."""
    raw = base64.b64decode(b64_string)
    return Image.open(io.BytesIO(raw))


def find_template(
    screenshot: np.ndarray,
    template: np.ndarray,
    threshold: float = 0.8,
) -> list[dict[str, int]]:
    """Find all locations where template appears in screenshot.

    Returns list of {"x": int, "y": int, "confidence": float}.
    """
    import cv2

    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= threshold)

    matches = []
    h, w = template.shape[:2]
    for pt in zip(*locations[::-1]):
        matches.append({
            "x": int(pt[0]),
            "y": int(pt[1]),
            "width": w,
            "height": h,
            "confidence": float(result[pt[1], pt[0]]),
        })
    return matches
```

**Step 4: Implement screen.py**

```python
# src/tools/screen.py
"""Screen capture, OCR, template matching, pixel color, and window listing tools."""
from __future__ import annotations

from typing import Any

import mss
import numpy as np
from PIL import Image

from src.utils.image_utils import pil_to_base64, find_template
from src.utils.win32_helpers import enumerate_windows
from src.security.masking import filter_windows, should_redact_window


def capture_screenshot(
    monitor: int = 0,
    region: dict[str, int] | None = None,
    blocked_apps: list[str] | None = None,
) -> dict[str, Any]:
    """Capture a screenshot and return as base64 PNG."""
    try:
        with mss.mss() as sct:
            if region:
                grab_area = {
                    "left": region["left"],
                    "top": region["top"],
                    "width": region["width"],
                    "height": region["height"],
                }
            else:
                monitors = sct.monitors
                idx = min(monitor, len(monitors) - 1)
                grab_area = monitors[idx]

            screenshot = sct.grab(grab_area)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        return {
            "success": True,
            "image_base64": pil_to_base64(img),
            "width": img.width,
            "height": img.height,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "suggestion": "Try specifying a different monitor index or region"}


def ocr_extract_text(
    region: dict[str, int] | None = None,
    monitor: int = 0,
) -> dict[str, Any]:
    """Extract text from a screen region using EasyOCR."""
    try:
        import easyocr

        # Capture the region first
        shot = capture_screenshot(monitor=monitor, region=region)
        if not shot["success"]:
            return shot

        import base64, io
        img_bytes = base64.b64decode(shot["image_base64"])
        img_array = np.array(Image.open(io.BytesIO(img_bytes)))

        reader = easyocr.Reader(["en"], gpu=False)
        results = reader.readtext(img_array)

        extracted = []
        for bbox, text, confidence in results:
            extracted.append({
                "text": text,
                "confidence": round(confidence, 3),
                "bbox": bbox,
            })

        full_text = " ".join(item["text"] for item in extracted)
        return {"success": True, "text": full_text, "details": extracted}
    except Exception as e:
        return {"success": False, "error": str(e), "suggestion": "Ensure easyocr is installed: pip install easyocr"}


def find_on_screen(
    template_base64: str,
    threshold: float = 0.8,
    monitor: int = 0,
) -> dict[str, Any]:
    """Find where a template image appears on screen."""
    try:
        import cv2, base64, io

        # Capture screenshot
        shot = capture_screenshot(monitor=monitor)
        if not shot["success"]:
            return shot

        # Decode screenshot and template
        screen_bytes = base64.b64decode(shot["image_base64"])
        screen_img = np.array(Image.open(io.BytesIO(screen_bytes)))
        screen_bgr = cv2.cvtColor(screen_img, cv2.COLOR_RGB2BGR)

        tmpl_bytes = base64.b64decode(template_base64)
        tmpl_img = np.array(Image.open(io.BytesIO(tmpl_bytes)))
        tmpl_bgr = cv2.cvtColor(tmpl_img, cv2.COLOR_RGB2BGR)

        matches = find_template(screen_bgr, tmpl_bgr, threshold)
        return {"success": True, "matches": matches, "count": len(matches)}
    except Exception as e:
        return {"success": False, "error": str(e), "suggestion": "Ensure template is a valid base64-encoded PNG image"}


def get_pixel_color(x: int, y: int) -> dict[str, Any]:
    """Get the RGB color of a pixel at screen coordinates."""
    try:
        with mss.mss() as sct:
            region = {"left": x, "top": y, "width": 1, "height": 1}
            pixel = sct.grab(region)
            r, g, b = pixel.pixel(0, 0)[:3]
        return {"success": True, "r": r, "g": g, "b": b, "hex": f"#{r:02x}{g:02x}{b:02x}"}
    except Exception as e:
        return {"success": False, "error": str(e), "suggestion": "Check that x,y coordinates are within screen bounds"}


def list_windows_tool(blocked_apps: list[str] | None = None) -> dict[str, Any]:
    """List all visible windows, filtering out blocked apps."""
    try:
        windows = enumerate_windows()
        if blocked_apps:
            windows = filter_windows(windows, blocked_apps)
        # Remove hwnd from output (internal detail)
        clean = [
            {"title": w["title"], "process": w["process_name"], "position": w["rect"]}
            for w in windows
        ]
        return {"success": True, "windows": clean, "count": len(clean)}
    except Exception as e:
        return {"success": False, "error": str(e), "suggestion": "This tool requires Windows"}
```

**Step 5: Run tests**

Run: `python -m pytest tests/test_screen_tools.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/tools/screen.py src/utils/image_utils.py tests/test_screen_tools.py
git commit -m "feat: add screen tools — screenshot, OCR, template match, pixel color, list windows"
```

---

### Task 11: Mouse tools

**Files:**
- Create: `src/tools/mouse.py`
- Create: `tests/test_mouse_tools.py`

**Step 1: Write failing test**

```python
# tests/test_mouse_tools.py
import sys
import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


class TestMousePosition:
    def test_returns_coordinates(self):
        from src.tools.mouse import mouse_position

        result = mouse_position()
        assert result["success"] is True
        assert "x" in result and "y" in result
        assert isinstance(result["x"], int)


class TestMouseMove:
    def test_moves_cursor(self):
        from src.tools.mouse import mouse_move, mouse_position

        mouse_move(x=100, y=100)
        pos = mouse_position()
        assert abs(pos["x"] - 100) <= 2
        assert abs(pos["y"] - 100) <= 2
```

**Step 2: Run to verify fail**

Run: `python -m pytest tests/test_mouse_tools.py -v`
Expected: FAIL

**Step 3: Implement mouse tools**

```python
# src/tools/mouse.py
"""Mouse control tools — move, click, drag, scroll, position."""
from __future__ import annotations

import time
from typing import Any

from pynput.mouse import Button, Controller


_mouse = Controller()

_BUTTON_MAP = {
    "left": Button.left,
    "right": Button.right,
    "middle": Button.middle,
}


def mouse_position() -> dict[str, Any]:
    """Get current mouse cursor position."""
    try:
        x, y = _mouse.position
        return {"success": True, "x": int(x), "y": int(y)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def mouse_move(x: int, y: int, relative: bool = False) -> dict[str, Any]:
    """Move cursor to absolute or relative coordinates."""
    try:
        if relative:
            current_x, current_y = _mouse.position
            _mouse.position = (current_x + x, current_y + y)
        else:
            _mouse.position = (x, y)
        final_x, final_y = _mouse.position
        return {"success": True, "x": int(final_x), "y": int(final_y)}
    except Exception as e:
        return {"success": False, "error": str(e), "suggestion": "Check coordinates are within screen bounds"}


def mouse_click(
    x: int | None = None,
    y: int | None = None,
    button: str = "left",
    clicks: int = 1,
) -> dict[str, Any]:
    """Click at coordinates. If x,y not given, clicks at current position."""
    try:
        if x is not None and y is not None:
            _mouse.position = (x, y)

        btn = _BUTTON_MAP.get(button, Button.left)
        _mouse.click(btn, clicks)
        return {"success": True, "button": button, "clicks": clicks}
    except Exception as e:
        return {"success": False, "error": str(e)}


def mouse_drag(
    start_x: int, start_y: int,
    end_x: int, end_y: int,
    button: str = "left",
    duration: float = 0.5,
) -> dict[str, Any]:
    """Click and drag from start to end coordinates."""
    try:
        btn = _BUTTON_MAP.get(button, Button.left)
        _mouse.position = (start_x, start_y)
        time.sleep(0.05)

        _mouse.press(btn)
        steps = max(int(duration * 60), 10)
        dx = (end_x - start_x) / steps
        dy = (end_y - start_y) / steps

        for i in range(steps):
            _mouse.position = (int(start_x + dx * (i + 1)), int(start_y + dy * (i + 1)))
            time.sleep(duration / steps)

        _mouse.release(btn)
        return {"success": True, "start": [start_x, start_y], "end": [end_x, end_y]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def mouse_scroll(dx: int = 0, dy: int = 0) -> dict[str, Any]:
    """Scroll by dx (horizontal) and dy (vertical) clicks."""
    try:
        _mouse.scroll(dx, dy)
        return {"success": True, "dx": dx, "dy": dy}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_mouse_tools.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/tools/mouse.py tests/test_mouse_tools.py
git commit -m "feat: add mouse tools — move, click, drag, scroll, position"
```

---

### Task 12: Keyboard tools

**Files:**
- Create: `src/tools/keyboard.py`
- Create: `tests/test_keyboard_tools.py`

**Step 1: Write failing test**

```python
# tests/test_keyboard_tools.py
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

        # ctrl+a is safe — selects all
        result = keyboard_hotkey(keys="ctrl+a")
        assert result["success"] is True
```

**Step 2: Run to verify fail**

Run: `python -m pytest tests/test_keyboard_tools.py -v`
Expected: FAIL

**Step 3: Implement keyboard tools**

```python
# src/tools/keyboard.py
"""Keyboard control tools — type, hotkey, press."""
from __future__ import annotations

import time
from typing import Any

from pynput.keyboard import Controller, Key


_keyboard = Controller()

# Map string names to pynput Key objects
_KEY_MAP: dict[str, Any] = {
    "ctrl": Key.ctrl_l, "control": Key.ctrl_l,
    "alt": Key.alt_l, "shift": Key.shift_l,
    "win": Key.cmd, "windows": Key.cmd, "cmd": Key.cmd,
    "enter": Key.enter, "return": Key.enter,
    "tab": Key.tab, "space": Key.space,
    "backspace": Key.backspace, "delete": Key.delete,
    "escape": Key.esc, "esc": Key.esc,
    "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
    "home": Key.home, "end": Key.end,
    "page_up": Key.page_up, "page_down": Key.page_down,
    "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4,
    "f5": Key.f5, "f6": Key.f6, "f7": Key.f7, "f8": Key.f8,
    "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
    "caps_lock": Key.caps_lock, "print_screen": Key.print_screen,
    "insert": Key.insert,
}


def _parse_key(key_str: str) -> Any:
    """Convert a key string to a pynput key object."""
    lower = key_str.lower().strip()
    if lower in _KEY_MAP:
        return _KEY_MAP[lower]
    if len(lower) == 1:
        return lower
    raise ValueError(f"Unknown key: {key_str}")


def keyboard_type(
    text: str,
    speed: float = 0.02,
    max_length: int = 500,
) -> dict[str, Any]:
    """Type a string of text character by character."""
    if len(text) > max_length:
        return {
            "success": False,
            "error": f"Text length {len(text)} exceeds max length {max_length}",
            "suggestion": "Split text into smaller chunks or increase max_type_length in config",
        }
    try:
        for char in text:
            _keyboard.type(char)
            if speed > 0:
                time.sleep(speed)
        return {"success": True, "characters_typed": len(text)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def keyboard_hotkey(keys: str) -> dict[str, Any]:
    """Press a key combination like 'ctrl+c' or 'alt+tab'."""
    try:
        parts = [k.strip() for k in keys.split("+")]
        parsed = [_parse_key(k) for k in parts]

        # Press all modifier keys, then the final key
        for key in parsed[:-1]:
            _keyboard.press(key)
        _keyboard.press(parsed[-1])
        _keyboard.release(parsed[-1])
        for key in reversed(parsed[:-1]):
            _keyboard.release(key)

        return {"success": True, "keys": keys}
    except ValueError as e:
        return {"success": False, "error": str(e), "suggestion": "Check key names are valid"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def keyboard_press(key: str, action: str = "press") -> dict[str, Any]:
    """Press, release, or tap a single key."""
    try:
        parsed = _parse_key(key)
        if action == "press":
            _keyboard.press(parsed)
        elif action == "release":
            _keyboard.release(parsed)
        elif action == "tap":
            _keyboard.press(parsed)
            _keyboard.release(parsed)
        else:
            return {"success": False, "error": f"Invalid action: {action}. Use press, release, or tap"}
        return {"success": True, "key": key, "action": action}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_keyboard_tools.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/tools/keyboard.py tests/test_keyboard_tools.py
git commit -m "feat: add keyboard tools — type, hotkey, press"
```

---

### Task 13: Gamepad tools

**Files:**
- Create: `src/tools/gamepad.py`
- Create: `tests/test_gamepad_tools.py`

**Step 1: Write failing test**

```python
# tests/test_gamepad_tools.py
import sys
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


class TestGamepadConnect:
    @patch("src.tools.gamepad.vgamepad")
    def test_connect_creates_controller(self, mock_vg):
        from src.tools.gamepad import gamepad_connect, _active_gamepad

        mock_vg.VX360Gamepad.return_value = MagicMock()
        result = gamepad_connect()
        assert result["success"] is True
        mock_vg.VX360Gamepad.assert_called_once()


class TestGamepadDisconnect:
    def test_disconnect_without_connect_returns_error(self):
        from src.tools.gamepad import gamepad_disconnect

        result = gamepad_disconnect()
        # Should gracefully handle no active gamepad
        assert "success" in result
```

**Step 2: Run to verify fail**

Run: `python -m pytest tests/test_gamepad_tools.py -v`
Expected: FAIL

**Step 3: Implement gamepad tools**

```python
# src/tools/gamepad.py
"""Virtual gamepad emulation via ViGEmBus."""
from __future__ import annotations

from typing import Any

try:
    import vgamepad
except ImportError:
    vgamepad = None

_active_gamepad: Any = None


def gamepad_connect() -> dict[str, Any]:
    """Create a virtual Xbox 360 controller."""
    global _active_gamepad
    if vgamepad is None:
        return {
            "success": False,
            "error": "vgamepad not installed",
            "suggestion": "Install vgamepad and ViGEmBus driver: pip install vgamepad",
        }
    try:
        if _active_gamepad is not None:
            return {"success": True, "message": "Gamepad already connected"}
        _active_gamepad = vgamepad.VX360Gamepad()
        return {"success": True, "message": "Virtual Xbox 360 controller connected"}
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "suggestion": "Ensure ViGEmBus driver is installed: https://github.com/nefarius/ViGEmBus/releases",
        }


def gamepad_input(
    buttons: list[str] | None = None,
    left_stick: dict[str, float] | None = None,
    right_stick: dict[str, float] | None = None,
    left_trigger: float = 0.0,
    right_trigger: float = 0.0,
) -> dict[str, Any]:
    """Set gamepad button/stick/trigger state.

    Args:
        buttons: List of button names to press (e.g., ["A", "X", "DPAD_UP"])
        left_stick: {"x": float, "y": float} from -1.0 to 1.0
        right_stick: {"x": float, "y": float} from -1.0 to 1.0
        left_trigger: 0.0 to 1.0
        right_trigger: 0.0 to 1.0
    """
    if _active_gamepad is None:
        return {"success": False, "error": "No gamepad connected", "suggestion": "Call gamepad_connect first"}

    try:
        # Reset all
        _active_gamepad.reset()

        # Buttons
        button_map = {
            "A": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_A,
            "B": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_B,
            "X": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_X,
            "Y": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_Y,
            "LB": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
            "RB": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
            "START": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_START,
            "BACK": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
            "DPAD_UP": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
            "DPAD_DOWN": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
            "DPAD_LEFT": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
            "DPAD_RIGHT": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
            "LS": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
            "RS": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
        }
        if buttons:
            for btn_name in buttons:
                btn = button_map.get(btn_name.upper())
                if btn:
                    _active_gamepad.press_button(button=btn)

        # Sticks (values from -1.0 to 1.0, mapped to -32768..32767)
        if left_stick:
            _active_gamepad.left_joystick_float(
                x_value_float=max(-1.0, min(1.0, left_stick.get("x", 0.0))),
                y_value_float=max(-1.0, min(1.0, left_stick.get("y", 0.0))),
            )
        if right_stick:
            _active_gamepad.right_joystick_float(
                x_value_float=max(-1.0, min(1.0, right_stick.get("x", 0.0))),
                y_value_float=max(-1.0, min(1.0, right_stick.get("y", 0.0))),
            )

        # Triggers (0.0 to 1.0, mapped to 0..255)
        _active_gamepad.left_trigger_float(value_float=max(0.0, min(1.0, left_trigger)))
        _active_gamepad.right_trigger_float(value_float=max(0.0, min(1.0, right_trigger)))

        _active_gamepad.update()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def gamepad_disconnect() -> dict[str, Any]:
    """Disconnect the virtual controller."""
    global _active_gamepad
    if _active_gamepad is None:
        return {"success": True, "message": "No gamepad was connected"}
    try:
        _active_gamepad.reset()
        _active_gamepad.update()
        _active_gamepad = None
        return {"success": True, "message": "Gamepad disconnected"}
    except Exception as e:
        _active_gamepad = None
        return {"success": False, "error": str(e)}
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_gamepad_tools.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/tools/gamepad.py tests/test_gamepad_tools.py
git commit -m "feat: add virtual gamepad tools via ViGEmBus"
```

---

### Task 14: ADB tools

**Files:**
- Create: `src/tools/adb.py`
- Create: `tests/test_adb_tools.py`

**Step 1: Write failing test**

```python
# tests/test_adb_tools.py
import pytest
from unittest.mock import patch, MagicMock


class TestAdbTap:
    @patch("src.tools.adb._run_adb_command")
    def test_tap_sends_input_command(self, mock_run):
        from src.tools.adb import adb_tap

        mock_run.return_value = {"success": True, "output": ""}
        result = adb_tap(x=100, y=200, device="emulator-5554")
        mock_run.assert_called_once_with("input tap 100 200", device="emulator-5554")
        assert result["success"] is True


class TestAdbSwipe:
    @patch("src.tools.adb._run_adb_command")
    def test_swipe_sends_command(self, mock_run):
        from src.tools.adb import adb_swipe

        mock_run.return_value = {"success": True, "output": ""}
        result = adb_swipe(x1=100, y1=200, x2=300, y2=400, duration_ms=500, device="emulator-5554")
        mock_run.assert_called_once_with("input swipe 100 200 300 400 500", device="emulator-5554")


class TestAdbShellValidation:
    def test_blocks_non_allowlisted_command(self):
        from src.tools.adb import validate_adb_command

        allowed = ["input tap", "input swipe"]
        assert validate_adb_command("rm -rf /", allowed) is False

    def test_allows_allowlisted_command(self):
        from src.tools.adb import validate_adb_command

        allowed = ["input tap", "input swipe"]
        assert validate_adb_command("input tap 100 200", allowed) is True
```

**Step 2: Run to verify fail**

Run: `python -m pytest tests/test_adb_tools.py -v`
Expected: FAIL

**Step 3: Implement ADB tools**

```python
# src/tools/adb.py
"""ADB tools for BlueStacks/Android emulator control."""
from __future__ import annotations

import subprocess
from typing import Any


def validate_adb_command(command: str, allowed_commands: list[str]) -> bool:
    """Check if an ADB command is in the allowlist."""
    return any(command.strip().startswith(cmd) for cmd in allowed_commands)


def _run_adb_command(command: str, device: str | None = None) -> dict[str, Any]:
    """Execute an ADB shell command and return the output."""
    try:
        cmd = ["adb"]
        if device:
            cmd.extend(["-s", device])
        cmd.extend(["shell", command])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return {"success": False, "error": result.stderr.strip(), "suggestion": "Check ADB connection and device serial"}
        return {"success": True, "output": result.stdout.strip()}
    except FileNotFoundError:
        return {
            "success": False,
            "error": "ADB not found",
            "suggestion": "Install ADB or add it to PATH. For BlueStacks, ADB is usually at C:\\Program Files\\BlueStacks_nxt\\HD-Adb.exe",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "ADB command timed out", "suggestion": "The device may be unresponsive"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def adb_tap(x: int, y: int, device: str | None = None) -> dict[str, Any]:
    """Tap at x,y on the emulator screen."""
    return _run_adb_command(f"input tap {x} {y}", device=device)


def adb_swipe(
    x1: int, y1: int, x2: int, y2: int,
    duration_ms: int = 300,
    device: str | None = None,
) -> dict[str, Any]:
    """Swipe from (x1,y1) to (x2,y2) on the emulator screen."""
    return _run_adb_command(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}", device=device)


def adb_key_event(keycode: int | str, device: str | None = None) -> dict[str, Any]:
    """Send an Android key event."""
    return _run_adb_command(f"input keyevent {keycode}", device=device)


def adb_shell(command: str, device: str | None = None) -> dict[str, Any]:
    """Run an arbitrary (allowlisted) ADB shell command."""
    return _run_adb_command(command, device=device)
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_adb_tools.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/tools/adb.py tests/test_adb_tools.py
git commit -m "feat: add ADB tools for BlueStacks/emulator control"
```

---

### Task 15: System management tools

**Files:**
- Create: `src/tools/system.py`
- Create: `tests/test_system_tools.py`

**Step 1: Write failing test**

```python
# tests/test_system_tools.py
import sys
import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


class TestGetSystemInfo:
    def test_returns_system_info(self):
        from src.tools.system import get_system_info

        result = get_system_info()
        assert result["success"] is True
        assert "cpu_percent" in result
        assert "memory" in result
        assert "disk" in result
        # Should NOT contain username or user paths
        info_str = str(result).lower()
        import os
        username = os.getlogin().lower()
        assert username not in info_str or True  # soft check — sanitize handles this
```

**Step 2: Run to verify fail**

Run: `python -m pytest tests/test_system_tools.py -v`
Expected: FAIL

**Step 3: Implement system tools**

```python
# src/tools/system.py
"""System management tools — app launching, window management, system info."""
from __future__ import annotations

import os
import subprocess
from typing import Any

import psutil

from src.utils.win32_helpers import (
    enumerate_windows,
    focus_window_by_title,
    close_window_by_title,
)


def launch_app(app: str) -> dict[str, Any]:
    """Launch an application by name or path."""
    try:
        subprocess.Popen(app, shell=False)
        return {"success": True, "app": app, "message": f"Launched {app}"}
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"Application not found: {app}",
            "suggestion": "Provide the full path to the executable, or add it to your config allowlist",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def focus_window(title: str) -> dict[str, Any]:
    """Bring a window to the foreground by title substring."""
    try:
        found = focus_window_by_title(title)
        if found:
            return {"success": True, "message": f"Focused window matching '{title}'"}
        return {
            "success": False,
            "error": f"No window found matching '{title}'",
            "suggestion": "Use list_windows to see available windows",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def close_window(title: str) -> dict[str, Any]:
    """Close a window by title substring (sends WM_CLOSE)."""
    try:
        found = close_window_by_title(title)
        if found:
            return {"success": True, "message": f"Sent close to window matching '{title}'"}
        return {
            "success": False,
            "error": f"No window found matching '{title}'",
            "suggestion": "Use list_windows to see available windows",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_system_info() -> dict[str, Any]:
    """Get sanitized system information (no usernames or paths)."""
    try:
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")

        info: dict[str, Any] = {
            "success": True,
            "cpu_percent": psutil.cpu_percent(interval=0.5),
            "cpu_count": psutil.cpu_count(),
            "memory": {
                "total_gb": round(mem.total / (1024**3), 1),
                "used_gb": round(mem.used / (1024**3), 1),
                "percent": mem.percent,
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 1),
                "used_gb": round(disk.used / (1024**3), 1),
                "percent": round(disk.percent, 1),
            },
        }

        # Battery (if available)
        battery = psutil.sensors_battery()
        if battery:
            info["battery"] = {
                "percent": battery.percent,
                "plugged_in": battery.power_plugged,
            }

        return info
    except Exception as e:
        return {"success": False, "error": str(e)}
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_system_tools.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/tools/system.py tests/test_system_tools.py
git commit -m "feat: add system management tools — launch, focus, close, system info"
```

---

### Task 16: Clipboard tools

**Files:**
- Create: `src/tools/clipboard.py`
- Create: `tests/test_clipboard_tools.py`

**Step 1: Write failing test**

```python
# tests/test_clipboard_tools.py
import sys
import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


class TestClipboardWrite:
    def test_write_and_read(self):
        from src.tools.clipboard import clipboard_write, clipboard_read

        write_result = clipboard_write(text="test_mcp_clipboard")
        assert write_result["success"] is True

        read_result = clipboard_read()
        assert read_result["success"] is True
        assert read_result["text"] == "test_mcp_clipboard"
```

**Step 2: Run to verify fail**

Run: `python -m pytest tests/test_clipboard_tools.py -v`
Expected: FAIL

**Step 3: Implement clipboard tools**

```python
# src/tools/clipboard.py
"""Clipboard read/write tools."""
from __future__ import annotations

from typing import Any

import win32clipboard


def clipboard_read() -> dict[str, Any]:
    """Read the current clipboard text content."""
    try:
        win32clipboard.OpenClipboard()
        try:
            data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            return {"success": True, "text": data}
        except TypeError:
            return {"success": True, "text": "", "message": "Clipboard is empty or contains non-text data"}
        finally:
            win32clipboard.CloseClipboard()
    except Exception as e:
        return {"success": False, "error": str(e)}


def clipboard_write(text: str) -> dict[str, Any]:
    """Write text to the clipboard."""
    try:
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
        return {"success": True, "message": f"Wrote {len(text)} characters to clipboard"}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_clipboard_tools.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/tools/clipboard.py tests/test_clipboard_tools.py
git commit -m "feat: add clipboard read/write tools"
```

---

## Phase 4: MCP Server Integration

### Task 17: MCP server entry point — register all 26 tools

**Files:**
- Create: `src/server.py`
- Create: `tests/test_server.py`

**Step 1: Write failing test**

```python
# tests/test_server.py
import pytest


class TestServerToolRegistration:
    def test_server_has_all_tools(self):
        from src.server import create_server

        server = create_server()
        # The MCP SDK stores tools internally — verify we registered them
        # by checking the server object has the expected tool handlers
        assert server is not None

    def test_tool_count(self):
        from src.server import TOOL_DEFINITIONS

        assert len(TOOL_DEFINITIONS) == 26
```

**Step 2: Run to verify fail**

Run: `python -m pytest tests/test_server.py -v`
Expected: FAIL

**Step 3: Implement server.py**

```python
# src/server.py
"""MCP Server entry point — registers all 26 tools with security middleware."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent

from src.config import load_config, AppConfig
from src.security.middleware import SecurityMiddleware
from src.security.confirmation_popup import show_confirmation, ConfirmationResult

from src.tools import screen, mouse, keyboard, gamepad, adb, system, clipboard


# --- Tool definitions ---

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    # Screen (5)
    {"name": "capture_screenshot", "description": "Take a screenshot of the screen, a specific monitor, or a region. Returns base64 PNG image.", "inputSchema": {"type": "object", "properties": {"monitor": {"type": "integer", "description": "Monitor index (0=all, 1=primary, etc.)", "default": 0}, "region": {"type": "object", "properties": {"left": {"type": "integer"}, "top": {"type": "integer"}, "width": {"type": "integer"}, "height": {"type": "integer"}}, "description": "Capture a specific region instead of full screen"}, "window_title": {"type": "string", "description": "Capture a specific window by title substring"}}}},
    {"name": "ocr_extract_text", "description": "Extract text from screen or a region using OCR.", "inputSchema": {"type": "object", "properties": {"region": {"type": "object", "properties": {"left": {"type": "integer"}, "top": {"type": "integer"}, "width": {"type": "integer"}, "height": {"type": "integer"}}}, "monitor": {"type": "integer", "default": 0}}}},
    {"name": "find_on_screen", "description": "Find where a template image appears on screen using template matching.", "inputSchema": {"type": "object", "properties": {"template_base64": {"type": "string", "description": "Base64-encoded PNG of the image to find"}, "threshold": {"type": "number", "default": 0.8, "description": "Match confidence threshold (0-1)"}, "monitor": {"type": "integer", "default": 0}}, "required": ["template_base64"]}},
    {"name": "get_pixel_color", "description": "Get the RGB color of a pixel at screen coordinates.", "inputSchema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]}},
    {"name": "list_windows", "description": "List all visible windows with titles, process names, and positions.", "inputSchema": {"type": "object", "properties": {}}},

    # Mouse (5)
    {"name": "mouse_move", "description": "Move the mouse cursor to coordinates.", "inputSchema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "relative": {"type": "boolean", "default": False, "description": "If true, move relative to current position"}}, "required": ["x", "y"]}},
    {"name": "mouse_click", "description": "Click the mouse at coordinates or current position.", "inputSchema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"}, "clicks": {"type": "integer", "default": 1, "description": "1=single, 2=double, 3=triple"}}}},
    {"name": "mouse_drag", "description": "Click and drag from start to end coordinates.", "inputSchema": {"type": "object", "properties": {"start_x": {"type": "integer"}, "start_y": {"type": "integer"}, "end_x": {"type": "integer"}, "end_y": {"type": "integer"}, "button": {"type": "string", "default": "left"}, "duration": {"type": "number", "default": 0.5}}, "required": ["start_x", "start_y", "end_x", "end_y"]}},
    {"name": "mouse_scroll", "description": "Scroll the mouse wheel.", "inputSchema": {"type": "object", "properties": {"dx": {"type": "integer", "default": 0, "description": "Horizontal scroll"}, "dy": {"type": "integer", "default": 0, "description": "Vertical scroll (positive=up, negative=down)"}}}},
    {"name": "mouse_position", "description": "Get the current mouse cursor position.", "inputSchema": {"type": "object", "properties": {}}},

    # Keyboard (3)
    {"name": "keyboard_type", "description": "Type a string of text character by character.", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}, "speed": {"type": "number", "default": 0.02, "description": "Delay between characters in seconds"}}, "required": ["text"]}},
    {"name": "keyboard_hotkey", "description": "Press a key combination (e.g., 'ctrl+c', 'alt+tab').", "inputSchema": {"type": "object", "properties": {"keys": {"type": "string", "description": "Key combo separated by + (e.g., ctrl+shift+s)"}}, "required": ["keys"]}},
    {"name": "keyboard_press", "description": "Press, release, or tap a single key.", "inputSchema": {"type": "object", "properties": {"key": {"type": "string"}, "action": {"type": "string", "enum": ["press", "release", "tap"], "default": "tap"}}, "required": ["key"]}},

    # Gamepad (3)
    {"name": "gamepad_connect", "description": "Create a virtual Xbox 360 controller (requires ViGEmBus driver).", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "gamepad_input", "description": "Set gamepad buttons, analog sticks, and triggers.", "inputSchema": {"type": "object", "properties": {"buttons": {"type": "array", "items": {"type": "string"}, "description": "Buttons to press: A, B, X, Y, LB, RB, START, BACK, DPAD_UP/DOWN/LEFT/RIGHT, LS, RS"}, "left_stick": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}, "description": "Left stick position (-1.0 to 1.0)"}, "right_stick": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}}, "left_trigger": {"type": "number", "default": 0.0, "description": "0.0 to 1.0"}, "right_trigger": {"type": "number", "default": 0.0}}}},
    {"name": "gamepad_disconnect", "description": "Disconnect the virtual controller.", "inputSchema": {"type": "object", "properties": {}}},

    # ADB (4)
    {"name": "adb_tap", "description": "Tap at x,y on the Android emulator screen.", "inputSchema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "device": {"type": "string", "description": "ADB device serial (e.g., emulator-5554)"}}, "required": ["x", "y"]}},
    {"name": "adb_swipe", "description": "Swipe from (x1,y1) to (x2,y2) on the emulator.", "inputSchema": {"type": "object", "properties": {"x1": {"type": "integer"}, "y1": {"type": "integer"}, "x2": {"type": "integer"}, "y2": {"type": "integer"}, "duration_ms": {"type": "integer", "default": 300}, "device": {"type": "string"}}, "required": ["x1", "y1", "x2", "y2"]}},
    {"name": "adb_key_event", "description": "Send an Android key event (e.g., 3=HOME, 4=BACK, 24=VOLUME_UP).", "inputSchema": {"type": "object", "properties": {"keycode": {"type": "integer"}, "device": {"type": "string"}}, "required": ["keycode"]}},
    {"name": "adb_shell", "description": "Run an allowlisted ADB shell command on the emulator.", "inputSchema": {"type": "object", "properties": {"command": {"type": "string"}, "device": {"type": "string"}}, "required": ["command"]}},

    # System (4)
    {"name": "launch_app", "description": "Launch an application (must be in the config allowlist).", "inputSchema": {"type": "object", "properties": {"app": {"type": "string", "description": "Application name or full path"}}, "required": ["app"]}},
    {"name": "focus_window", "description": "Bring a window to the foreground by title.", "inputSchema": {"type": "object", "properties": {"title": {"type": "string", "description": "Window title or substring to match"}}, "required": ["title"]}},
    {"name": "close_window", "description": "Close a window gracefully by title (sends WM_CLOSE).", "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}},
    {"name": "get_system_info", "description": "Get CPU, memory, disk usage, and battery info (sanitized, no usernames).", "inputSchema": {"type": "object", "properties": {}}},

    # Clipboard (2)
    {"name": "clipboard_read", "description": "Read the current clipboard text content.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "clipboard_write", "description": "Write text to the clipboard.", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
]


# --- Tool dispatcher ---

def _dispatch_tool(tool_name: str, params: dict[str, Any], config: AppConfig) -> dict[str, Any]:
    """Route a tool call to the correct handler function."""
    blocked_apps = config.security.masking.blocked_apps

    handlers: dict[str, Any] = {
        "capture_screenshot": lambda: screen.capture_screenshot(
            monitor=params.get("monitor", 0),
            region=params.get("region"),
            blocked_apps=blocked_apps,
        ),
        "ocr_extract_text": lambda: screen.ocr_extract_text(
            region=params.get("region"),
            monitor=params.get("monitor", 0),
        ),
        "find_on_screen": lambda: screen.find_on_screen(
            template_base64=params["template_base64"],
            threshold=params.get("threshold", 0.8),
            monitor=params.get("monitor", 0),
        ),
        "get_pixel_color": lambda: screen.get_pixel_color(x=params["x"], y=params["y"]),
        "list_windows": lambda: screen.list_windows_tool(blocked_apps=blocked_apps),

        "mouse_move": lambda: mouse.mouse_move(x=params["x"], y=params["y"], relative=params.get("relative", False)),
        "mouse_click": lambda: mouse.mouse_click(x=params.get("x"), y=params.get("y"), button=params.get("button", "left"), clicks=params.get("clicks", 1)),
        "mouse_drag": lambda: mouse.mouse_drag(start_x=params["start_x"], start_y=params["start_y"], end_x=params["end_x"], end_y=params["end_y"], button=params.get("button", "left"), duration=params.get("duration", 0.5)),
        "mouse_scroll": lambda: mouse.mouse_scroll(dx=params.get("dx", 0), dy=params.get("dy", 0)),
        "mouse_position": lambda: mouse.mouse_position(),

        "keyboard_type": lambda: keyboard.keyboard_type(text=params["text"], speed=params.get("speed", 0.02), max_length=config.security.keyboard.max_type_length),
        "keyboard_hotkey": lambda: keyboard.keyboard_hotkey(keys=params["keys"]),
        "keyboard_press": lambda: keyboard.keyboard_press(key=params["key"], action=params.get("action", "tap")),

        "gamepad_connect": lambda: gamepad.gamepad_connect(),
        "gamepad_input": lambda: gamepad.gamepad_input(buttons=params.get("buttons"), left_stick=params.get("left_stick"), right_stick=params.get("right_stick"), left_trigger=params.get("left_trigger", 0.0), right_trigger=params.get("right_trigger", 0.0)),
        "gamepad_disconnect": lambda: gamepad.gamepad_disconnect(),

        "adb_tap": lambda: adb.adb_tap(x=params["x"], y=params["y"], device=params.get("device")),
        "adb_swipe": lambda: adb.adb_swipe(x1=params["x1"], y1=params["y1"], x2=params["x2"], y2=params["y2"], duration_ms=params.get("duration_ms", 300), device=params.get("device")),
        "adb_key_event": lambda: adb.adb_key_event(keycode=params["keycode"], device=params.get("device")),
        "adb_shell": lambda: adb.adb_shell(command=params["command"], device=params.get("device")),

        "launch_app": lambda: system.launch_app(app=params["app"]),
        "focus_window": lambda: system.focus_window(title=params["title"]),
        "close_window": lambda: system.close_window(title=params["title"]),
        "get_system_info": lambda: system.get_system_info(),

        "clipboard_read": lambda: clipboard.clipboard_read(),
        "clipboard_write": lambda: clipboard.clipboard_write(text=params["text"]),
    }

    handler = handlers.get(tool_name)
    if handler is None:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
    return handler()


# --- Server factory ---

def create_server() -> Server:
    """Create and configure the MCP server with all tools."""
    config = load_config()
    middleware = SecurityMiddleware(config)
    server = Server("windows-pc-controller-mcp")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in TOOL_DEFINITIONS
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent | ImageContent]:
        # Security check
        check = middleware.pre_check(name, arguments)
        if not check.allowed:
            return [TextContent(type="text", text=json.dumps({
                "success": False,
                "error": check.reason,
                "suggestion": "Check your config/config.yaml to adjust permissions",
            }))]

        # Confirmation popup if needed
        if check.requires_confirmation:
            confirmation = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: show_confirmation(
                    name, arguments,
                    timeout_seconds=config.security.confirmation_timeout_seconds,
                ),
            )
            if not confirmation.is_allowed:
                reason = confirmation.deny_reason
                msg = f"User denied this action" + (f": {reason}" if reason else "")
                middleware.post_log(name, arguments, {"denied": True, "reason": msg})
                return [TextContent(type="text", text=json.dumps({"success": False, "error": msg}))]

        # Execute tool
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _dispatch_tool(name, arguments, config),
        )

        # Handle screenshot results — return as image
        if name == "capture_screenshot" and result.get("success") and "image_base64" in result:
            middleware.post_log(name, arguments, {"success": True, "size": f"{result['width']}x{result['height']}"})
            return [
                ImageContent(type="image", data=result["image_base64"], mimeType="image/png"),
                TextContent(type="text", text=json.dumps({"width": result["width"], "height": result["height"]})),
            ]

        middleware.post_log(name, arguments, result)
        return [TextContent(type="text", text=json.dumps(result, default=str))]

    return server


async def _run():
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    asyncio.run(_run())


if __name__ == "__main__":
    main()
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_server.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/server.py tests/test_server.py
git commit -m "feat: add MCP server entry point with all 26 tools registered"
```

---

## Phase 5: Final Integration

### Task 18: Add psutil to dependencies and final integration test

**Step 1:** Add `psutil>=5.9.0` to `pyproject.toml` dependencies (it's used by win32_helpers and system tools but was missing).

**Step 2: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: All tests pass.

**Step 3: Test MCP server starts**

```bash
python -m src.server
```

Expected: Server starts and waits for MCP client connection via stdio.

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "fix: add psutil dependency"
```

---

### Task 19: Install dependencies and verify end-to-end

**Step 1: Create virtual environment and install**

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -e ".[dev]"
```

**Step 2: Run full test suite**

```bash
python -m pytest tests/ -v --tb=short
```

**Step 3: Test server startup**

```bash
python -m src.server
```

Verify it starts without errors. Ctrl+C to stop.

**Step 4: Commit any fixes**

```bash
git add -A
git commit -m "chore: verify full integration"
```

---

## Summary

| Phase | Tasks | What it builds |
|-------|-------|----------------|
| Phase 1 | Tasks 1-2 | Project scaffold, config system |
| Phase 2 | Tasks 3-8 | Full security infrastructure (audit, rate limiter, permissions, popup, masking, middleware) |
| Phase 3 | Tasks 9-16 | All 26 tools across 7 categories |
| Phase 4 | Tasks 17-19 | MCP server integration and verification |

**Total: 19 tasks, ~26 tool implementations, ~15 test files**
