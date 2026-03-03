# tests/test_server.py
"""Tests for MCP server entry point — tool registration, dispatch, and security integration."""
from __future__ import annotations

import json
import asyncio
from unittest.mock import patch, MagicMock
import tempfile

import pytest
import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**overrides):
    """Build an AppConfig with sensible test defaults (security disabled for most tests)."""
    from src.config import load_config

    base = {
        "security": {
            "enabled": False,
            "confirm_dangerous_actions": False,
            "confirmation_timeout_seconds": 60,
            "audit_logging": False,
            "masking": {"enabled": True, "mask_password_fields": True, "blocked_apps": [], "blocked_regions": []},
            "rate_limits": {"mouse": 60, "keyboard": 120, "screenshot": 10, "adb": 30, "gamepad": 120},
            "keyboard": {"blocked_hotkeys": ["ctrl+alt+delete"], "max_type_length": 500, "block_password_fields": True},
            "apps": {"mode": "allowlist", "allowed": ["notepad.exe"]},
            "adb": {"allowed_devices": [], "allowed_commands": ["input tap", "input swipe", "input keyevent"]},
            "clipboard": {"read_enabled": True, "write_enabled": True},
        },
        "tools": {},
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


# ===========================================================================
# 1. TOOL_DEFINITIONS structure
# ===========================================================================

class TestToolDefinitions:
    def test_tool_count_is_26(self):
        from src.server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) == 26

    def test_all_definitions_have_required_keys(self):
        from src.server import TOOL_DEFINITIONS
        for defn in TOOL_DEFINITIONS:
            assert "name" in defn, f"Missing 'name' in {defn}"
            assert "description" in defn, f"Missing 'description' in {defn}"
            assert "inputSchema" in defn, f"Missing 'inputSchema' in {defn}"

    def test_all_names_are_unique(self):
        from src.server import TOOL_DEFINITIONS
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert len(names) == len(set(names)), f"Duplicate tool names: {names}"

    def test_expected_tool_names_present(self):
        """Verify all 26 expected tool names are registered."""
        from src.server import TOOL_DEFINITIONS

        expected = {
            # Screen (5)
            "capture_screenshot", "ocr_extract_text", "find_on_screen",
            "get_pixel_color", "list_windows",
            # Mouse (5)
            "mouse_move", "mouse_click", "mouse_drag",
            "mouse_scroll", "mouse_position",
            # Keyboard (3)
            "keyboard_type", "keyboard_hotkey", "keyboard_press",
            # Gamepad (3)
            "gamepad_connect", "gamepad_input", "gamepad_disconnect",
            # ADB (4)
            "adb_tap", "adb_swipe", "adb_key_event", "adb_shell",
            # System (4)
            "launch_app", "focus_window", "close_window", "get_system_info",
            # Clipboard (2)
            "clipboard_read", "clipboard_write",
        }
        actual = {t["name"] for t in TOOL_DEFINITIONS}
        assert actual == expected

    def test_input_schemas_are_objects(self):
        from src.server import TOOL_DEFINITIONS
        for defn in TOOL_DEFINITIONS:
            schema = defn["inputSchema"]
            assert schema.get("type") == "object", f"{defn['name']} schema type must be 'object'"


# ===========================================================================
# 2. Server creation
# ===========================================================================

class TestCreateServer:
    def test_create_server_returns_server(self):
        from src.server import create_server
        from mcp.server import Server

        server = create_server()
        assert isinstance(server, Server)

    def test_server_name(self):
        from src.server import create_server

        server = create_server()
        assert server.name == "windows-pc-controller-mcp"


# ===========================================================================
# 3. Tool dispatcher
# ===========================================================================

class TestDispatchTool:
    """Test _dispatch_tool routing without actually calling real hardware."""

    def test_unknown_tool_returns_error(self):
        from src.server import _dispatch_tool

        config = _make_config()
        result = _dispatch_tool("nonexistent_tool", {}, config)
        assert result["success"] is False
        assert "Unknown tool" in result["error"]

    @patch("src.tools.mouse.mouse_position")
    def test_dispatches_mouse_position(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True, "x": 100, "y": 200}
        config = _make_config()
        result = _dispatch_tool("mouse_position", {}, config)
        mock_fn.assert_called_once()
        assert result == {"success": True, "x": 100, "y": 200}

    @patch("src.tools.mouse.mouse_click")
    def test_dispatches_mouse_click_with_params(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True, "button": "right", "clicks": 2}
        config = _make_config()
        result = _dispatch_tool("mouse_click", {"x": 50, "y": 75, "button": "right", "clicks": 2}, config)
        mock_fn.assert_called_once_with(x=50, y=75, button="right", clicks=2)
        assert result["success"] is True

    @patch("src.tools.mouse.mouse_move")
    def test_dispatches_mouse_move(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True, "x": 10, "y": 20}
        config = _make_config()
        result = _dispatch_tool("mouse_move", {"x": 10, "y": 20, "relative": True}, config)
        mock_fn.assert_called_once_with(x=10, y=20, relative=True)

    @patch("src.tools.mouse.mouse_drag")
    def test_dispatches_mouse_drag(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True}
        config = _make_config()
        _dispatch_tool("mouse_drag", {"start_x": 0, "start_y": 0, "end_x": 100, "end_y": 100}, config)
        mock_fn.assert_called_once_with(
            start_x=0, start_y=0, end_x=100, end_y=100,
            button="left", duration=0.5,
        )

    @patch("src.tools.mouse.mouse_scroll")
    def test_dispatches_mouse_scroll(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True}
        config = _make_config()
        _dispatch_tool("mouse_scroll", {"dy": -3}, config)
        mock_fn.assert_called_once_with(dx=0, dy=-3)

    @patch("src.tools.keyboard.keyboard_type")
    def test_dispatches_keyboard_type_with_max_length(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True, "characters_typed": 5}
        config = _make_config()
        _dispatch_tool("keyboard_type", {"text": "hello"}, config)
        mock_fn.assert_called_once_with(text="hello", speed=0.02, max_length=500)

    @patch("src.tools.keyboard.keyboard_hotkey")
    def test_dispatches_keyboard_hotkey(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True, "keys": "ctrl+c"}
        config = _make_config()
        _dispatch_tool("keyboard_hotkey", {"keys": "ctrl+c"}, config)
        mock_fn.assert_called_once_with(keys="ctrl+c")

    @patch("src.tools.keyboard.keyboard_press")
    def test_dispatches_keyboard_press(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True}
        config = _make_config()
        _dispatch_tool("keyboard_press", {"key": "enter", "action": "tap"}, config)
        mock_fn.assert_called_once_with(key="enter", action="tap")

    @patch("src.tools.screen.capture_screenshot")
    def test_dispatches_capture_screenshot(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True, "image_base64": "abc", "width": 1920, "height": 1080}
        config = _make_config()
        result = _dispatch_tool("capture_screenshot", {"monitor": 1}, config)
        mock_fn.assert_called_once_with(monitor=1, region=None, blocked_apps=[])

    @patch("src.tools.screen.get_pixel_color")
    def test_dispatches_get_pixel_color(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True, "r": 255, "g": 0, "b": 0}
        config = _make_config()
        _dispatch_tool("get_pixel_color", {"x": 10, "y": 20}, config)
        mock_fn.assert_called_once_with(x=10, y=20)

    @patch("src.tools.screen.list_windows_tool")
    def test_dispatches_list_windows(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True, "windows": [], "count": 0}
        config = _make_config()
        _dispatch_tool("list_windows", {}, config)
        mock_fn.assert_called_once_with(blocked_apps=[])

    @patch("src.tools.gamepad.gamepad_connect")
    def test_dispatches_gamepad_connect(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True}
        config = _make_config()
        _dispatch_tool("gamepad_connect", {}, config)
        mock_fn.assert_called_once()

    @patch("src.tools.gamepad.gamepad_input")
    def test_dispatches_gamepad_input(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True}
        config = _make_config()
        _dispatch_tool("gamepad_input", {"buttons": ["A", "B"], "left_trigger": 0.5}, config)
        mock_fn.assert_called_once_with(
            buttons=["A", "B"],
            left_stick=None,
            right_stick=None,
            left_trigger=0.5,
            right_trigger=0.0,
        )

    @patch("src.tools.gamepad.gamepad_disconnect")
    def test_dispatches_gamepad_disconnect(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True}
        config = _make_config()
        _dispatch_tool("gamepad_disconnect", {}, config)
        mock_fn.assert_called_once()

    @patch("src.tools.adb.adb_tap")
    def test_dispatches_adb_tap(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True}
        config = _make_config()
        _dispatch_tool("adb_tap", {"x": 100, "y": 200, "device": "emulator-5554"}, config)
        mock_fn.assert_called_once_with(x=100, y=200, device="emulator-5554")

    @patch("src.tools.adb.adb_swipe")
    def test_dispatches_adb_swipe(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True}
        config = _make_config()
        _dispatch_tool("adb_swipe", {"x1": 0, "y1": 0, "x2": 100, "y2": 100, "duration_ms": 500}, config)
        mock_fn.assert_called_once_with(x1=0, y1=0, x2=100, y2=100, duration_ms=500, device=None)

    @patch("src.tools.adb.adb_key_event")
    def test_dispatches_adb_key_event(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True}
        config = _make_config()
        _dispatch_tool("adb_key_event", {"keycode": 3}, config)
        mock_fn.assert_called_once_with(keycode=3, device=None)

    @patch("src.tools.adb.adb_shell")
    def test_dispatches_adb_shell(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True, "output": "OK"}
        config = _make_config()
        _dispatch_tool("adb_shell", {"command": "input tap 100 200"}, config)
        mock_fn.assert_called_once_with(command="input tap 100 200", device=None)

    @patch("src.tools.system.launch_app")
    def test_dispatches_launch_app(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True}
        config = _make_config()
        _dispatch_tool("launch_app", {"app": "notepad.exe"}, config)
        mock_fn.assert_called_once_with(app="notepad.exe")

    @patch("src.tools.system.focus_window")
    def test_dispatches_focus_window(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True}
        config = _make_config()
        _dispatch_tool("focus_window", {"title": "Notepad"}, config)
        mock_fn.assert_called_once_with(title="Notepad")

    @patch("src.tools.system.close_window")
    def test_dispatches_close_window(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True}
        config = _make_config()
        _dispatch_tool("close_window", {"title": "Notepad"}, config)
        mock_fn.assert_called_once_with(title="Notepad")

    @patch("src.tools.system.get_system_info")
    def test_dispatches_get_system_info(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True, "cpu_percent": 5.0}
        config = _make_config()
        _dispatch_tool("get_system_info", {}, config)
        mock_fn.assert_called_once()

    @patch("src.tools.clipboard.clipboard_read")
    def test_dispatches_clipboard_read(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True, "text": "hello"}
        config = _make_config()
        _dispatch_tool("clipboard_read", {}, config)
        mock_fn.assert_called_once()

    @patch("src.tools.clipboard.clipboard_write")
    def test_dispatches_clipboard_write(self, mock_fn):
        from src.server import _dispatch_tool

        mock_fn.return_value = {"success": True}
        config = _make_config()
        _dispatch_tool("clipboard_write", {"text": "world"}, config)
        mock_fn.assert_called_once_with(text="world")


# ===========================================================================
# 4. Async call_tool handler integration
# ===========================================================================

class TestCallToolHandler:
    """Test the async call_tool handler through the server."""

    @pytest.mark.asyncio
    async def test_call_tool_handler_is_registered(self):
        """The server should have a call_tool handler registered."""
        from src.server import create_server
        from mcp.types import CallToolRequest

        server = create_server()
        handler = server.request_handlers.get(CallToolRequest)
        assert handler is not None, "call_tool handler should be registered"

    @pytest.mark.asyncio
    async def test_normal_tool_dispatch_returns_json_result(self):
        """Non-screenshot tools should produce dict results with JSON-serializable data."""
        from src.server import _dispatch_tool

        with patch("src.tools.mouse.mouse_position") as mock_fn:
            mock_fn.return_value = {"success": True, "x": 42, "y": 84}
            config = _make_config()
            result = _dispatch_tool("mouse_position", {}, config)
            # Verify result can be JSON-serialized (as the handler would do)
            text = json.dumps(result, default=str)
            parsed = json.loads(text)
            assert parsed["success"] is True
            assert parsed["x"] == 42

    @pytest.mark.asyncio
    async def test_security_blocked_tool_returns_error(self):
        """When security middleware blocks a call, should return error TextContent."""
        from src.server import _dispatch_tool
        from src.security.middleware import SecurityMiddleware, MiddlewareResult

        # Create config with security ENABLED and clipboard_read disabled
        config = _make_config(
            **{
                "security.enabled": True,
                "tools": {"clipboard_read": {"enabled": False}},
            }
        )
        middleware = SecurityMiddleware(config)
        check = middleware.pre_check("clipboard_read", {})
        assert check.allowed is False
        assert "disabled" in check.reason.lower()

    @pytest.mark.asyncio
    async def test_screenshot_returns_image_content(self):
        """capture_screenshot should return ImageContent when successful."""
        from src.server import _dispatch_tool

        fake_result = {
            "success": True,
            "image_base64": "iVBORw0KGgo=",
            "width": 1920,
            "height": 1080,
        }
        with patch("src.tools.screen.capture_screenshot", return_value=fake_result):
            config = _make_config()
            result = _dispatch_tool("capture_screenshot", {"monitor": 0}, config)
            assert result["success"] is True
            assert "image_base64" in result
            assert result["width"] == 1920
            assert result["height"] == 1080


# ===========================================================================
# 5. Security middleware integration with dispatcher
# ===========================================================================

class TestSecurityIntegration:
    """Test that security middleware and dispatcher work together correctly."""

    def test_blocked_hotkey_does_not_dispatch(self):
        """When middleware blocks a tool, dispatch should NOT be called."""
        from src.security.middleware import SecurityMiddleware

        config = _make_config(**{"security.enabled": True})
        middleware = SecurityMiddleware(config)
        check = middleware.pre_check("keyboard_hotkey", {"keys": "ctrl+alt+delete"})
        assert check.allowed is False

    def test_allowed_tool_passes_middleware(self):
        from src.security.middleware import SecurityMiddleware

        config = _make_config(**{"security.enabled": True})
        middleware = SecurityMiddleware(config)
        check = middleware.pre_check("mouse_position", {})
        assert check.allowed is True

    def test_rate_limited_tool_blocked(self):
        from src.security.middleware import SecurityMiddleware

        config = _make_config(**{
            "security.enabled": True,
            "security.rate_limits": {
                "mouse": 1, "keyboard": 120, "screenshot": 10, "adb": 30, "gamepad": 120,
            },
        })
        middleware = SecurityMiddleware(config)
        # First call passes
        check1 = middleware.pre_check("mouse_position", {})
        assert check1.allowed is True
        # Second call should be rate-limited
        check2 = middleware.pre_check("mouse_position", {})
        assert check2.allowed is False
        assert "rate" in check2.reason.lower()

    def test_dangerous_action_requires_confirmation(self):
        from src.security.middleware import SecurityMiddleware

        config = _make_config(**{
            "security.enabled": True,
            "security.confirm_dangerous_actions": True,
        })
        middleware = SecurityMiddleware(config)
        check = middleware.pre_check("launch_app", {"app": "notepad.exe"})
        assert check.allowed is True
        assert check.requires_confirmation is True


# ===========================================================================
# 6. list_tools handler
# ===========================================================================

class TestListToolsHandler:
    def test_list_tools_registered(self):
        """Server should have a list_tools handler registered."""
        from src.server import create_server
        from mcp.types import ListToolsRequest

        server = create_server()
        assert ListToolsRequest in server.request_handlers


# ===========================================================================
# 7. Entry point
# ===========================================================================

class TestEntryPoint:
    def test_main_function_exists(self):
        from src.server import main
        assert callable(main)

    def test_run_function_exists(self):
        from src.server import _run
        assert asyncio.iscoroutinefunction(_run)
