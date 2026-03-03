"""Virtual gamepad emulation via ViGEmBus."""
from __future__ import annotations

from typing import Any

from src.utils.errors import tool_error, tool_success, DEPENDENCY_MISSING, OS_ERROR, INVALID_PARAMS

try:
    import vgamepad
except ImportError:
    vgamepad = None

_active_gamepad: Any = None


def gamepad_connect() -> dict[str, Any]:
    """Create a virtual Xbox 360 controller."""
    global _active_gamepad
    if vgamepad is None:
        return tool_error(
            "vgamepad not installed", DEPENDENCY_MISSING,
            suggestion="Install vgamepad and ViGEmBus driver: pip install vgamepad",
        )
    try:
        if _active_gamepad is not None:
            return tool_success("Gamepad already connected")
        _active_gamepad = vgamepad.VX360Gamepad()
        return tool_success("Virtual Xbox 360 controller connected")
    except Exception as e:
        return tool_error(
            str(e), DEPENDENCY_MISSING,
            suggestion="Ensure ViGEmBus driver is installed: https://github.com/nefarius/ViGEmBus/releases",
        )


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
        return tool_error(
            "No gamepad connected", INVALID_PARAMS,
            suggestion="Call gamepad_connect first",
        )

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
        return tool_success()
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="Check ViGEmBus driver is running")


def gamepad_disconnect() -> dict[str, Any]:
    """Disconnect the virtual controller."""
    global _active_gamepad
    if _active_gamepad is None:
        return tool_success("No gamepad was connected")
    try:
        _active_gamepad.reset()
        _active_gamepad.update()
        _active_gamepad = None
        return tool_success("Gamepad disconnected")
    except Exception as e:
        _active_gamepad = None
        return tool_error(str(e), OS_ERROR, suggestion="Gamepad state was reset despite the error")
