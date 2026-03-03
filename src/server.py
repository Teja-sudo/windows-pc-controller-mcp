# src/server.py
"""MCP Server entry point — registers all tools with security middleware."""
from __future__ import annotations

# DPI awareness MUST be set before any screen/mouse imports
import src.utils.dpi  # noqa: F401  — side-effect: sets process DPI awareness

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent

from src.config import load_config, AppConfig
from src.security.middleware import SecurityMiddleware
from src.security.confirmation_popup import show_confirmation, ConfirmationResult
from src.utils.context import get_context
from src.utils.params import normalize_params

from src.tools import screen, mouse, keyboard, gamepad, adb, system, clipboard, compound


# --- Tool definitions ---

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    # Screen (6)
    {
        "name": "capture_screenshot",
        "description": (
            "Capture a screenshot as base64 PNG. Use monitor=0 for all screens, monitor=1 for primary. "
            "Specify window_title to capture a single window, or region for a pixel-precise area. "
            "Response includes width, height, and dpi_scale — use dpi_scale to convert screenshot "
            "coordinates to mouse coordinates if scaling is not 1.0. Prefer click_text over "
            "screenshot+OCR+click when you need to interact with visible text."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "monitor": {"type": "integer", "description": "Monitor index: 0=all screens combined, 1=primary, 2=secondary, etc.", "default": 0},
                "region": {
                    "type": "object",
                    "properties": {
                        "left": {"type": "integer"},
                        "top": {"type": "integer"},
                        "width": {"type": "integer"},
                        "height": {"type": "integer"},
                    },
                    "description": "Capture a specific pixel region. Coordinates are in screen pixels.",
                },
                "window_title": {"type": "string", "description": "Capture only the window matching this title substring. Ignored if region is also provided."},
            },
        },
    },
    {
        "name": "ocr_extract_text",
        "description": (
            "Extract all visible text from the screen or a region using OCR. Returns full text and "
            "per-word details with bounding boxes and confidence scores. Use this when you need to "
            "read screen content. For clicking on text, prefer click_text which combines OCR and click."
        ),
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
                    "description": "Limit OCR to this screen region for faster results",
                },
                "monitor": {"type": "integer", "default": 0, "description": "Monitor index (0=all, 1=primary)"},
            },
        },
    },
    {
        "name": "find_on_screen",
        "description": (
            "Find where a template image appears on screen using pixel-level template matching. "
            "Returns match coordinates and confidence scores. Requires a base64-encoded PNG template. "
            "Use this for finding icons, buttons, or UI elements that are visually consistent. "
            "For text-based elements, prefer click_text or ocr_extract_text instead."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "template_base64": {"type": "string", "description": "Base64-encoded PNG of the image to find on screen"},
                "threshold": {"type": "number", "default": 0.8, "description": "Match confidence threshold (0.0-1.0). Lower values find more matches but with less precision."},
                "monitor": {"type": "integer", "default": 0, "description": "Monitor index (0=all, 1=primary)"},
            },
            "required": ["template_base64"],
        },
    },
    {
        "name": "get_pixel_color",
        "description": (
            "Get the RGB color of a single pixel at screen coordinates. Returns r, g, b values (0-255) "
            "and hex string. Useful for checking UI state (e.g., is a button highlighted, is a checkbox checked). "
            "Coordinates must be within screen bounds."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate in screen pixels"},
                "y": {"type": "integer", "description": "Y coordinate in screen pixels"},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "list_windows",
        "description": (
            "List all visible windows with their titles, process names, and screen positions. "
            "Use this to discover window titles for focus_window, close_window, or capture_screenshot(window_title=...). "
            "Windows belonging to blocked apps (e.g., password managers) are automatically filtered out."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_screen_info",
        "description": (
            "Get essential screen context: primary monitor dimensions, DPI scale factor, monitor count, "
            "and currently active window title. Call this FIRST before any coordinate-based operations "
            "to understand the screen layout. If dpi_scale is not 1.0, screenshot pixel coordinates "
            "differ from mouse coordinates."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },

    # Mouse (5)
    {
        "name": "mouse_move",
        "description": (
            "Move the mouse cursor to absolute screen coordinates, or relative to current position. "
            "Coordinates are in physical screen pixels. Set from_screenshot=true if coordinates came from "
            "a screenshot (auto-converts using the cached screenshot_scale). Returns the final cursor position."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate (absolute) or X offset (relative)"},
                "y": {"type": "integer", "description": "Y coordinate (absolute) or Y offset (relative)"},
                "relative": {"type": "boolean", "default": False, "description": "If true, x/y are offsets from current position instead of absolute coordinates"},
                "from_screenshot": {"type": "boolean", "default": False, "description": "If true, auto-converts coordinates from screenshot space to screen space using the cached screenshot_scale factor"},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "mouse_click",
        "description": (
            "Click the mouse at specified coordinates or at the current cursor position. "
            "For clicking on visible text, prefer click_text which handles OCR and coordinate "
            "calculation automatically. Omit x/y to click at the current cursor position. "
            "Set from_screenshot=true if coordinates came from a screenshot."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate to click at. Omit to click at current position."},
                "y": {"type": "integer", "description": "Y coordinate to click at. Omit to click at current position."},
                "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
                "clicks": {"type": "integer", "default": 1, "description": "Number of clicks: 1=single, 2=double, 3=triple"},
                "from_screenshot": {"type": "boolean", "default": False, "description": "If true, auto-converts x/y from screenshot space to screen space"},
            },
        },
    },
    {
        "name": "mouse_drag",
        "description": (
            "Click and drag from start coordinates to end coordinates. Useful for drag-and-drop, "
            "selecting text, resizing windows, or drawing. The duration parameter controls drag speed "
            "— increase it for smoother drags in applications that require it."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "start_x": {"type": "integer", "description": "Starting X coordinate"},
                "start_y": {"type": "integer", "description": "Starting Y coordinate"},
                "end_x": {"type": "integer", "description": "Ending X coordinate"},
                "end_y": {"type": "integer", "description": "Ending Y coordinate"},
                "button": {"type": "string", "default": "left", "description": "Mouse button to hold during drag"},
                "duration": {"type": "number", "default": 0.5, "description": "Drag duration in seconds. Increase for smoother drags."},
                "from_screenshot": {"type": "boolean", "default": False, "description": "If true, auto-converts coordinates from screenshot space to screen space"},
            },
            "required": ["start_x", "start_y", "end_x", "end_y"],
        },
    },
    {
        "name": "mouse_scroll",
        "description": (
            "Scroll the mouse wheel at the current cursor position. "
            "Use direction + clicks for simple scrolling (e.g., direction='down', clicks=5). "
            "Move the mouse to the target area first with mouse_move before scrolling."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["up", "down", "left", "right"], "description": "Scroll direction. Use this with 'clicks' for simple scrolling."},
                "clicks": {"type": "integer", "default": 3, "description": "Number of scroll steps (1-10). Each click is one notch of the scroll wheel."},
            },
            "required": ["direction"],
        },
    },
    {
        "name": "mouse_position",
        "description": (
            "Get the current mouse cursor position in physical screen pixels. "
            "Useful for debugging coordinate issues or saving/restoring cursor position."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },

    # Keyboard (3)
    {
        "name": "keyboard_type",
        "description": (
            "Type a string of text character by character, simulating real keyboard input. "
            "Text length is limited by config (default 500 chars). For longer text, use clipboard_write "
            "followed by keyboard_hotkey('ctrl+v'). The speed parameter controls typing delay between characters."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The text to type. Must be within the configured max_type_length."},
                "speed": {"type": "number", "default": 0.02, "description": "Delay between characters in seconds. Use 0 for instant typing."},
            },
            "required": ["text"],
        },
    },
    {
        "name": "keyboard_hotkey",
        "description": (
            "Press a keyboard shortcut combination. Keys are separated by '+'. "
            "Modifier keys: ctrl, alt, shift, win. Common shortcuts: 'ctrl+c' (copy), 'ctrl+v' (paste), "
            "'ctrl+a' (select all), 'alt+tab' (switch window), 'ctrl+shift+s' (save as). "
            "Some dangerous hotkeys like 'ctrl+alt+delete' are blocked by security config."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "keys": {"type": "string", "description": "Key combination separated by + (e.g., 'ctrl+c', 'alt+tab', 'ctrl+shift+s')"},
            },
            "required": ["keys"],
        },
    },
    {
        "name": "keyboard_press",
        "description": (
            "Press, release, or tap a single key. Default action is 'tap' (press+release). "
            "Use 'press' and 'release' separately for holding keys during other operations. "
            "Supported keys: a-z, 0-9, enter, tab, escape, space, backspace, delete, up/down/left/right, "
            "home, end, page_up, page_down, f1-f12, insert, caps_lock, print_screen."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Key name (e.g., 'enter', 'tab', 'escape', 'f5', 'a')"},
                "action": {"type": "string", "enum": ["press", "release", "tap"], "default": "tap", "description": "press=hold down, release=let go, tap=press+release"},
            },
            "required": ["key"],
        },
    },

    # Gamepad (3)
    {
        "name": "gamepad_connect",
        "description": (
            "Create a virtual Xbox 360 controller. Requires the ViGEmBus driver to be installed. "
            "Call this once before sending any gamepad_input commands. The virtual controller "
            "appears as a real Xbox 360 controller to all applications."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "gamepad_input",
        "description": (
            "Set gamepad buttons, analog sticks, and triggers on the virtual controller. "
            "Must call gamepad_connect first. All parameters are optional — only specified inputs "
            "are changed. Stick values range from -1.0 to 1.0, triggers from 0.0 to 1.0."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "buttons": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Buttons to press: A, B, X, Y, LB, RB, START, BACK, DPAD_UP, DPAD_DOWN, DPAD_LEFT, DPAD_RIGHT, LS (left stick click), RS (right stick click)",
                },
                "left_stick": {
                    "type": "object",
                    "properties": {"x": {"type": "number"}, "y": {"type": "number"}},
                    "description": "Left analog stick position. x: -1.0 (left) to 1.0 (right), y: -1.0 (down) to 1.0 (up)",
                },
                "right_stick": {
                    "type": "object",
                    "properties": {"x": {"type": "number"}, "y": {"type": "number"}},
                    "description": "Right analog stick position. Same range as left_stick.",
                },
                "left_trigger": {"type": "number", "default": 0.0, "description": "Left trigger pressure: 0.0 (released) to 1.0 (fully pressed)"},
                "right_trigger": {"type": "number", "default": 0.0, "description": "Right trigger pressure: 0.0 to 1.0"},
            },
        },
    },
    {
        "name": "gamepad_disconnect",
        "description": (
            "Disconnect and remove the virtual Xbox 360 controller. "
            "Call this when done with gamepad operations to clean up the virtual device."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },

    # ADB (4)
    {
        "name": "adb_tap",
        "description": (
            "Tap at x,y coordinates on an Android emulator screen via ADB. "
            "Coordinates are in the emulator's own resolution (not the host screen). "
            "Use adb_shell with 'dumpsys window' to get the emulator's display dimensions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate in emulator pixels"},
                "y": {"type": "integer", "description": "Y coordinate in emulator pixels"},
                "device": {"type": "string", "description": "ADB device serial (e.g., 'emulator-5554'). Omit if only one device is connected."},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "adb_swipe",
        "description": (
            "Swipe from one point to another on an Android emulator screen. "
            "Useful for scrolling, unlocking, and navigating. Coordinates are in emulator pixels. "
            "Increase duration_ms for slower, more precise swipes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "x1": {"type": "integer", "description": "Starting X coordinate"},
                "y1": {"type": "integer", "description": "Starting Y coordinate"},
                "x2": {"type": "integer", "description": "Ending X coordinate"},
                "y2": {"type": "integer", "description": "Ending Y coordinate"},
                "duration_ms": {"type": "integer", "default": 300, "description": "Swipe duration in milliseconds. Increase for slower swipes."},
                "device": {"type": "string", "description": "ADB device serial. Omit if only one device is connected."},
            },
            "required": ["x1", "y1", "x2", "y2"],
        },
    },
    {
        "name": "adb_key_event",
        "description": (
            "Send an Android key event to the emulator. Common keycodes: "
            "3=HOME, 4=BACK, 24=VOLUME_UP, 25=VOLUME_DOWN, 26=POWER, "
            "82=MENU, 187=APP_SWITCH. Full list at Android KeyEvent documentation."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "keycode": {"type": "integer", "description": "Android keycode integer (e.g., 3=HOME, 4=BACK, 24=VOLUME_UP)"},
                "device": {"type": "string", "description": "ADB device serial. Omit if only one device is connected."},
            },
            "required": ["keycode"],
        },
    },
    {
        "name": "adb_shell",
        "description": (
            "Run an allowlisted ADB shell command on the Android emulator. Only commands in the "
            "security config allowlist are permitted (default: input tap/swipe/keyevent, screencap, dumpsys window). "
            "Commands not in the allowlist will be rejected."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute (must be in the config allowlist)"},
                "device": {"type": "string", "description": "ADB device serial. Omit if only one device is connected."},
            },
            "required": ["command"],
        },
    },

    # System (4)
    {
        "name": "launch_app",
        "description": (
            "Launch an application by executable name or full path. The application must be in the "
            "security config allowlist (security.apps.allowed). After launching, use wait_for_window "
            "to confirm the application window has appeared before interacting with it."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "Application executable name (e.g., 'notepad.exe') or full path"},
            },
            "required": ["app"],
        },
    },
    {
        "name": "focus_window",
        "description": (
            "Bring a window to the foreground by title substring or process name. Provide at least one of "
            "title or process. If title matching fails (e.g., due to special characters), try process name "
            "instead — use list_windows to find process names. On failure, returns a list of available "
            "windows to help identify the correct target. Blocked apps cannot be focused."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Window title or substring to match (case-insensitive, Unicode-safe)"},
                "process": {"type": "string", "description": "Process name to match (e.g., 'msedge.exe', 'notepad.exe'). Reliable fallback when title matching fails."},
            },
        },
    },
    {
        "name": "close_window",
        "description": (
            "Close a window gracefully by sending WM_CLOSE (equivalent to clicking the X button). "
            "Provide at least one of title or process. The application may prompt to save unsaved work. "
            "Blocked apps cannot be closed. Use list_windows to find exact window titles."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Window title or substring to match (case-insensitive, Unicode-safe)"},
                "process": {"type": "string", "description": "Process name to match (e.g., 'notepad.exe'). Reliable fallback when title matching fails."},
            },
        },
    },
    {
        "name": "get_system_info",
        "description": (
            "Get CPU usage, memory usage, disk usage, and battery status. "
            "All values are sanitized — no usernames, hostnames, or file paths are included. "
            "Useful for monitoring system health before resource-intensive operations."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },

    # Clipboard (2)
    {
        "name": "clipboard_read",
        "description": (
            "Read the current text content from the Windows clipboard. "
            "Disabled by default in security config — enable clipboard.read_enabled to use. "
            "Returns the clipboard text or an error if empty or not text content."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "clipboard_write",
        "description": (
            "Write text to the Windows clipboard. Useful for transferring large text blocks — "
            "write to clipboard then use keyboard_hotkey('ctrl+v') to paste, which is faster "
            "and more reliable than keyboard_type for long text."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to write to the clipboard"},
            },
            "required": ["text"],
        },
    },

    # Compound (3)
    {
        "name": "click_text",
        "description": (
            "Find text on screen using OCR and click its center — combines screenshot, OCR, coordinate "
            "calculation, and mouse click into one step. PREFER THIS over manual screenshot+OCR+click workflows. "
            "On failure, returns visible text sample to help identify correct text. Use 'occurrence' to "
            "click the Nth match when text appears multiple times. Specify 'region' to limit search area."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The text to find and click on screen (case-insensitive, partial match)"},
                "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
                "clicks": {"type": "integer", "default": 1, "description": "Number of clicks (1=single, 2=double)"},
                "monitor": {"type": "integer", "default": 0, "description": "Monitor index (0=all, 1=primary)"},
                "region": {
                    "type": "object",
                    "properties": {
                        "left": {"type": "integer"},
                        "top": {"type": "integer"},
                        "width": {"type": "integer"},
                        "height": {"type": "integer"},
                    },
                    "description": "Limit OCR search to this screen region for faster and more precise results",
                },
                "occurrence": {"type": "integer", "default": 1, "description": "Which occurrence to click if text appears multiple times (1=first, 2=second, etc.)"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "wait_for_window",
        "description": (
            "Wait for a window to appear by title or process name, polling at intervals. "
            "ALWAYS use this after launch_app to confirm the application window is ready before "
            "interacting with it. Returns the matched window's title and process name on success. "
            "Timeout is capped at 30 seconds. Provide at least one of title or process."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Window title substring to wait for (case-insensitive, Unicode-safe)"},
                "process": {"type": "string", "description": "Process name to wait for (e.g., 'notepad.exe')"},
                "timeout": {"type": "number", "default": 10, "description": "Maximum seconds to wait (capped at 30)"},
                "poll_interval": {"type": "number", "default": 0.5, "description": "Seconds between polling checks"},
            },
        },
    },

    # New tools (Phase 7, Batch 3)
    {
        "name": "window_manage",
        "description": (
            "Manage a window's position and state: maximize, minimize, restore, resize, move, "
            "snap_left, or snap_right. Provide title or process to identify the window. "
            "Use list_windows to find window titles. For resize, provide width+height. "
            "For move, provide x+y. Snap positions the window on the left or right half of the screen."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["maximize", "minimize", "restore", "resize", "move", "snap_left", "snap_right"], "description": "Window management action"},
                "title": {"type": "string", "description": "Window title substring to match"},
                "process": {"type": "string", "description": "Process name to match (e.g., 'notepad.exe')"},
                "width": {"type": "integer", "description": "New window width (for resize)"},
                "height": {"type": "integer", "description": "New window height (for resize)"},
                "x": {"type": "integer", "description": "New window X position (for move)"},
                "y": {"type": "integer", "description": "New window Y position (for move)"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "get_health",
        "description": (
            "Diagnostic snapshot: OCR engine status, DPI scale, ADB availability, ViGEm driver, "
            "screen dimensions, and total tool count. Call this once at session start to understand "
            "the system's capabilities before planning multi-step workflows."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "open_url",
        "description": (
            "Open a URL in the default web browser. Use this instead of launch_app for web pages. "
            "After opening, use wait_for_window to confirm the browser tab loaded. "
            "URL must start with http:// or https://."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full URL to open (must start with http:// or https://)"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "type_text",
        "description": (
            "Smart text input — auto-selects the fastest method. Short text (<50 chars) is typed "
            "character by character. Long text (≥50 chars) is pasted via clipboard+Ctrl+V, which is "
            "100x faster. PREFER THIS over keyboard_type for any text input. "
            "Use method='type' to force character-by-character, or method='paste' to force clipboard."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The text to type or paste"},
                "method": {"type": "string", "enum": ["auto", "type", "paste"], "default": "auto", "description": "Input method: auto (default), type (char-by-char), paste (clipboard+Ctrl+V)"},
            },
            "required": ["text"],
        },
    },
]


# ── Next-action hints — static mapping of tool → suggested follow-up tools ──
NEXT_ACTIONS: dict[str, list[str]] = {
    "launch_app": ["wait_for_window"],
    "focus_window": ["capture_screenshot", "keyboard_type", "click_text"],
    "close_window": ["list_windows"],
    "clipboard_write": ["keyboard_hotkey('ctrl+v')"],
    "clipboard_read": ["keyboard_type(text=...)"],
    "capture_screenshot": ["ocr_extract_text", "click_text", "find_on_screen"],
    "ocr_extract_text": ["click_text", "mouse_click"],
    "mouse_move": ["mouse_click", "capture_screenshot"],
    "mouse_click": ["capture_screenshot"],
    "mouse_drag": ["capture_screenshot"],
    "keyboard_type": ["capture_screenshot"],
    "keyboard_hotkey": ["capture_screenshot"],
    "keyboard_press": ["capture_screenshot"],
    "click_text": ["capture_screenshot"],
    "wait_for_window": ["focus_window", "capture_screenshot", "click_text"],
    "get_screen_info": ["capture_screenshot", "mouse_move"],
    "list_windows": ["focus_window", "close_window"],
    "find_on_screen": ["mouse_click"],
    "get_system_info": ["get_screen_info"],
    "open_url": ["wait_for_window"],
    "type_text": ["capture_screenshot"],
    "window_manage": ["capture_screenshot"],
}

# Tools that change visible UI state — trigger verification screenshot
_STATE_CHANGING_TOOLS = frozenset({
    "mouse_click", "mouse_drag", "keyboard_type", "keyboard_hotkey",
    "keyboard_press", "focus_window", "launch_app", "click_text",
    "close_window", "type_text", "window_manage",
})

_SCROLL_DIRECTION_MAP = {
    "up": (0, 1),
    "down": (0, -1),
    "left": (-1, 0),
    "right": (1, 0),
}


def _scroll_params(params: dict[str, Any]) -> dict[str, int]:
    """Convert direction/clicks to dx/dy for mouse_scroll."""
    direction = params.get("direction")
    if direction and direction in _SCROLL_DIRECTION_MAP:
        clicks = params.get("clicks", 3)
        base_dx, base_dy = _SCROLL_DIRECTION_MAP[direction]
        return {"dx": base_dx * clicks, "dy": base_dy * clicks}
    return {"dx": params.get("dx", 0), "dy": params.get("dy", 0)}


# --- Tool dispatcher ---

def _dispatch_tool(tool_name: str, params: dict[str, Any], config: AppConfig) -> dict[str, Any]:
    """Route a tool call to the correct handler function."""
    params = normalize_params(tool_name, params)
    blocked_apps = config.security.masking.blocked_apps

    handlers: dict[str, Any] = {
        "capture_screenshot": lambda: screen.capture_screenshot(
            monitor=params.get("monitor", 0),
            region=params.get("region"),
            blocked_apps=blocked_apps,
            window_title=params.get("window_title"),
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
            from_screenshot=params.get("from_screenshot", False),
        ),
        "mouse_click": lambda: mouse.mouse_click(
            x=params.get("x"), y=params.get("y"),
            button=params.get("button", "left"), clicks=params.get("clicks", 1),
            from_screenshot=params.get("from_screenshot", False),
        ),
        "mouse_drag": lambda: mouse.mouse_drag(
            start_x=params["start_x"], start_y=params["start_y"],
            end_x=params["end_x"], end_y=params["end_y"],
            button=params.get("button", "left"), duration=params.get("duration", 0.5),
            from_screenshot=params.get("from_screenshot", False),
        ),
        "mouse_scroll": lambda: mouse.mouse_scroll(
            **_scroll_params(params),
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
        "focus_window": lambda: system.focus_window(
            title=params.get("title"),
            process=params.get("process"),
            blocked_apps=blocked_apps,
        ),
        "close_window": lambda: system.close_window(
            title=params.get("title"),
            process=params.get("process"),
            blocked_apps=blocked_apps,
        ),
        "get_system_info": lambda: system.get_system_info(),

        "clipboard_read": lambda: clipboard.clipboard_read(),
        "clipboard_write": lambda: clipboard.clipboard_write(text=params["text"]),

        "get_screen_info": lambda: screen.get_screen_info(),
        "click_text": lambda: compound.click_text(
            text=params["text"],
            button=params.get("button", "left"),
            clicks=params.get("clicks", 1),
            monitor=params.get("monitor", 0),
            region=params.get("region"),
            occurrence=params.get("occurrence", 1),
        ),
        "wait_for_window": lambda: compound.wait_for_window(
            title=params.get("title"),
            process=params.get("process"),
            timeout=params.get("timeout", 10.0),
            poll_interval=params.get("poll_interval", 0.5),
        ),

        "window_manage": lambda: system.window_manage(
            action=params["action"],
            title=params.get("title"),
            process=params.get("process"),
            width=params.get("width"),
            height=params.get("height"),
            x=params.get("x"),
            y=params.get("y"),
            blocked_apps=blocked_apps,
        ),
        "get_health": lambda: system.get_health(),
        "open_url": lambda: system.open_url(url=params["url"]),
        "type_text": lambda: compound.type_text(
            text=params["text"],
            method=params.get("method", "auto"),
        ),
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

        # ── Enrich response with context + next-action hints ──
        if result.get("success"):
            result["_context"] = get_context()
            hints = NEXT_ACTIONS.get(name)
            if hints:
                result["_next"] = hints

        # Handle screenshot results — return as image
        if name == "capture_screenshot" and result.get("success") and "image_base64" in result:
            meta = {
                "width": result["width"],
                "height": result["height"],
                "original_width": result.get("original_width", result["width"]),
                "original_height": result.get("original_height", result["height"]),
                "dpi_scale": result.get("dpi_scale", 1.0),
                "screenshot_scale": result.get("screenshot_scale", 1.0),
                "active_window": result.get("active_window", ""),
                "_context": result.get("_context", {}),
            }
            next_hints = result.get("_next")
            if next_hints:
                meta["_next"] = next_hints
            middleware.post_log(name, arguments, {"success": True, "size": f"{meta['width']}x{meta['height']}"})
            return [
                ImageContent(type="image", data=result["image_base64"], mimeType="image/png"),
                TextContent(type="text", text=json.dumps(meta)),
            ]

        middleware.post_log(name, arguments, result)
        response: list[TextContent | ImageContent] = [
            TextContent(type="text", text=json.dumps(result, default=str)),
        ]

        # ── Verification screenshot after state-changing tools ──
        if (
            result.get("success")
            and config.security.verification_screenshots
            and name in _STATE_CHANGING_TOOLS
        ):
            try:
                import time as _time
                _time.sleep(0.3)  # let UI render
                vshot = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: screen.capture_screenshot(_internal=True),
                )
                if vshot.get("success") and "image_base64" in vshot:
                    response.append(
                        ImageContent(type="image", data=vshot["image_base64"], mimeType="image/png"),
                    )
            except Exception:
                pass  # verification is best-effort

        return response

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
