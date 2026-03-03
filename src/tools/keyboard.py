"""Keyboard control tools — type, hotkey, press."""
from __future__ import annotations

import time
from typing import Any

from pynput.keyboard import Controller, Key


_keyboard = Controller()

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
