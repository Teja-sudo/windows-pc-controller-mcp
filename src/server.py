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
    {
        "name": "capture_screenshot",
        "description": "Take a screenshot of the screen, a specific monitor, or a region. Returns base64 PNG image.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "monitor": {"type": "integer", "description": "Monitor index (0=all, 1=primary, etc.)", "default": 0},
                "region": {
                    "type": "object",
                    "properties": {
                        "left": {"type": "integer"},
                        "top": {"type": "integer"},
                        "width": {"type": "integer"},
                        "height": {"type": "integer"},
                    },
                    "description": "Capture a specific region instead of full screen",
                },
                "window_title": {"type": "string", "description": "Capture a specific window by title substring"},
            },
        },
    },
    {
        "name": "ocr_extract_text",
        "description": "Extract text from screen or a region using OCR.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "region": {
                    "type": "object",
                    "properties": {
                        "left": {"type": "integer"},
                        "top": {"type": "integer"},
                        "width": {"type": "integer"},
                        "height": {"type": "integer"},
                    },
                },
                "monitor": {"type": "integer", "default": 0},
            },
        },
    },
    {
        "name": "find_on_screen",
        "description": "Find where a template image appears on screen using template matching.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "template_base64": {"type": "string", "description": "Base64-encoded PNG of the image to find"},
                "threshold": {"type": "number", "default": 0.8, "description": "Match confidence threshold (0-1)"},
                "monitor": {"type": "integer", "default": 0},
            },
            "required": ["template_base64"],
        },
    },
    {
        "name": "get_pixel_color",
        "description": "Get the RGB color of a pixel at screen coordinates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "list_windows",
        "description": "List all visible windows with titles, process names, and positions.",
        "inputSchema": {"type": "object", "properties": {}},
    },

    # Mouse (5)
    {
        "name": "mouse_move",
        "description": "Move the mouse cursor to coordinates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "relative": {"type": "boolean", "default": False, "description": "If true, move relative to current position"},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "mouse_click",
        "description": "Click the mouse at coordinates or current position.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
                "clicks": {"type": "integer", "default": 1, "description": "1=single, 2=double, 3=triple"},
            },
        },
    },
    {
        "name": "mouse_drag",
        "description": "Click and drag from start to end coordinates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start_x": {"type": "integer"},
                "start_y": {"type": "integer"},
                "end_x": {"type": "integer"},
                "end_y": {"type": "integer"},
                "button": {"type": "string", "default": "left"},
                "duration": {"type": "number", "default": 0.5},
            },
            "required": ["start_x", "start_y", "end_x", "end_y"],
        },
    },
    {
        "name": "mouse_scroll",
        "description": "Scroll the mouse wheel.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dx": {"type": "integer", "default": 0, "description": "Horizontal scroll"},
                "dy": {"type": "integer", "default": 0, "description": "Vertical scroll (positive=up, negative=down)"},
            },
        },
    },
    {
        "name": "mouse_position",
        "description": "Get the current mouse cursor position.",
        "inputSchema": {"type": "object", "properties": {}},
    },

    # Keyboard (3)
    {
        "name": "keyboard_type",
        "description": "Type a string of text character by character.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "speed": {"type": "number", "default": 0.02, "description": "Delay between characters in seconds"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "keyboard_hotkey",
        "description": "Press a key combination (e.g., 'ctrl+c', 'alt+tab').",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keys": {"type": "string", "description": "Key combo separated by + (e.g., ctrl+shift+s)"},
            },
            "required": ["keys"],
        },
    },
    {
        "name": "keyboard_press",
        "description": "Press, release, or tap a single key.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "action": {"type": "string", "enum": ["press", "release", "tap"], "default": "tap"},
            },
            "required": ["key"],
        },
    },

    # Gamepad (3)
    {
        "name": "gamepad_connect",
        "description": "Create a virtual Xbox 360 controller (requires ViGEmBus driver).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "gamepad_input",
        "description": "Set gamepad buttons, analog sticks, and triggers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "buttons": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Buttons to press: A, B, X, Y, LB, RB, START, BACK, DPAD_UP/DOWN/LEFT/RIGHT, LS, RS",
                },
                "left_stick": {
                    "type": "object",
                    "properties": {"x": {"type": "number"}, "y": {"type": "number"}},
                    "description": "Left stick position (-1.0 to 1.0)",
                },
                "right_stick": {
                    "type": "object",
                    "properties": {"x": {"type": "number"}, "y": {"type": "number"}},
                },
                "left_trigger": {"type": "number", "default": 0.0, "description": "0.0 to 1.0"},
                "right_trigger": {"type": "number", "default": 0.0},
            },
        },
    },
    {
        "name": "gamepad_disconnect",
        "description": "Disconnect the virtual controller.",
        "inputSchema": {"type": "object", "properties": {}},
    },

    # ADB (4)
    {
        "name": "adb_tap",
        "description": "Tap at x,y on the Android emulator screen.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "device": {"type": "string", "description": "ADB device serial (e.g., emulator-5554)"},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "adb_swipe",
        "description": "Swipe from (x1,y1) to (x2,y2) on the emulator.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x1": {"type": "integer"},
                "y1": {"type": "integer"},
                "x2": {"type": "integer"},
                "y2": {"type": "integer"},
                "duration_ms": {"type": "integer", "default": 300},
                "device": {"type": "string"},
            },
            "required": ["x1", "y1", "x2", "y2"],
        },
    },
    {
        "name": "adb_key_event",
        "description": "Send an Android key event (e.g., 3=HOME, 4=BACK, 24=VOLUME_UP).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keycode": {"type": "integer"},
                "device": {"type": "string"},
            },
            "required": ["keycode"],
        },
    },
    {
        "name": "adb_shell",
        "description": "Run an allowlisted ADB shell command on the emulator.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "device": {"type": "string"},
            },
            "required": ["command"],
        },
    },

    # System (4)
    {
        "name": "launch_app",
        "description": "Launch an application (must be in the config allowlist).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "Application name or full path"},
            },
            "required": ["app"],
        },
    },
    {
        "name": "focus_window",
        "description": "Bring a window to the foreground by title.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Window title or substring to match"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "close_window",
        "description": "Close a window gracefully by title (sends WM_CLOSE).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "get_system_info",
        "description": "Get CPU, memory, disk usage, and battery info (sanitized, no usernames).",
        "inputSchema": {"type": "object", "properties": {}},
    },

    # Clipboard (2)
    {
        "name": "clipboard_read",
        "description": "Read the current clipboard text content.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "clipboard_write",
        "description": "Write text to the clipboard.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
            },
            "required": ["text"],
        },
    },
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

        "mouse_move": lambda: mouse.mouse_move(
            x=params["x"], y=params["y"], relative=params.get("relative", False),
        ),
        "mouse_click": lambda: mouse.mouse_click(
            x=params.get("x"), y=params.get("y"),
            button=params.get("button", "left"), clicks=params.get("clicks", 1),
        ),
        "mouse_drag": lambda: mouse.mouse_drag(
            start_x=params["start_x"], start_y=params["start_y"],
            end_x=params["end_x"], end_y=params["end_y"],
            button=params.get("button", "left"), duration=params.get("duration", 0.5),
        ),
        "mouse_scroll": lambda: mouse.mouse_scroll(
            dx=params.get("dx", 0), dy=params.get("dy", 0),
        ),
        "mouse_position": lambda: mouse.mouse_position(),

        "keyboard_type": lambda: keyboard.keyboard_type(
            text=params["text"], speed=params.get("speed", 0.02),
            max_length=config.security.keyboard.max_type_length,
        ),
        "keyboard_hotkey": lambda: keyboard.keyboard_hotkey(keys=params["keys"]),
        "keyboard_press": lambda: keyboard.keyboard_press(
            key=params["key"], action=params.get("action", "tap"),
        ),

        "gamepad_connect": lambda: gamepad.gamepad_connect(),
        "gamepad_input": lambda: gamepad.gamepad_input(
            buttons=params.get("buttons"),
            left_stick=params.get("left_stick"),
            right_stick=params.get("right_stick"),
            left_trigger=params.get("left_trigger", 0.0),
            right_trigger=params.get("right_trigger", 0.0),
        ),
        "gamepad_disconnect": lambda: gamepad.gamepad_disconnect(),

        "adb_tap": lambda: adb.adb_tap(
            x=params["x"], y=params["y"], device=params.get("device"),
        ),
        "adb_swipe": lambda: adb.adb_swipe(
            x1=params["x1"], y1=params["y1"],
            x2=params["x2"], y2=params["y2"],
            duration_ms=params.get("duration_ms", 300), device=params.get("device"),
        ),
        "adb_key_event": lambda: adb.adb_key_event(
            keycode=params["keycode"], device=params.get("device"),
        ),
        "adb_shell": lambda: adb.adb_shell(
            command=params["command"], device=params.get("device"),
        ),

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
    """Run the MCP server with stdio transport."""
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    """Entry point for the MCP server."""
    asyncio.run(_run())


if __name__ == "__main__":
    main()
