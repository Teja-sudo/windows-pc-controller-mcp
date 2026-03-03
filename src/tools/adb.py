"""ADB tools for BlueStacks/Android emulator control."""
from __future__ import annotations

import subprocess
from typing import Any

from src.utils.errors import tool_error, tool_success, NOT_FOUND, TIMEOUT, DEPENDENCY_MISSING, OS_ERROR


def validate_adb_command(command: str, allowed_commands: list[str]) -> bool:
    """Check if an ADB command is in the allowlist.

    Uses prefix matching: the command (after stripping whitespace)
    must start with one of the allowed command prefixes.
    """
    return any(command.strip().startswith(cmd) for cmd in allowed_commands)


def _run_adb_command(command: str, device: str | None = None) -> dict[str, Any]:
    """Execute an ADB shell command and return the output.

    Builds an ``adb [-s device] shell <command>`` invocation using a list
    (shell=False) so there is no shell-injection risk.
    """
    try:
        cmd: list[str] = ["adb"]
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
            return tool_error(
                result.stderr.strip(), OS_ERROR,
                suggestion="Check ADB connection and device serial. Use 'adb devices' to verify.",
            )
        return tool_success(output=result.stdout.strip())
    except FileNotFoundError:
        return tool_error(
            "ADB not found", DEPENDENCY_MISSING,
            suggestion=(
                "Install ADB or add it to PATH. For BlueStacks, ADB is usually "
                "at C:\\Program Files\\BlueStacks_nxt\\HD-Adb.exe"
            ),
        )
    except subprocess.TimeoutExpired:
        return tool_error(
            "ADB command timed out", TIMEOUT,
            suggestion="The device may be unresponsive. Check connection with 'adb devices'.",
        )
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="Check ADB installation and device connection")


def adb_tap(x: int, y: int, device: str | None = None) -> dict[str, Any]:
    """Tap at x,y on the emulator screen."""
    return _run_adb_command(f"input tap {x} {y}", device=device)


def adb_swipe(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    duration_ms: int = 300,
    device: str | None = None,
) -> dict[str, Any]:
    """Swipe from (x1, y1) to (x2, y2) on the emulator screen."""
    return _run_adb_command(
        f"input swipe {x1} {y1} {x2} {y2} {duration_ms}", device=device
    )


def adb_key_event(keycode: int | str, device: str | None = None) -> dict[str, Any]:
    """Send an Android key event (e.g. 3 for HOME, ``KEYCODE_BACK``)."""
    return _run_adb_command(f"input keyevent {keycode}", device=device)


def adb_shell(command: str, device: str | None = None) -> dict[str, Any]:
    """Run an arbitrary (allowlisted) ADB shell command."""
    return _run_adb_command(command, device=device)
