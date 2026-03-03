"""Tests for ADB tools — tap, swipe, key event, shell, and validation."""
import subprocess

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# validate_adb_command
# ---------------------------------------------------------------------------
class TestValidateAdbCommand:
    def test_allows_allowlisted_command(self):
        from src.tools.adb import validate_adb_command

        allowed = ["input tap", "input swipe"]
        assert validate_adb_command("input tap 100 200", allowed) is True

    def test_allows_allowlisted_swipe(self):
        from src.tools.adb import validate_adb_command

        allowed = ["input tap", "input swipe"]
        assert validate_adb_command("input swipe 0 0 100 100 300", allowed) is True

    def test_blocks_non_allowlisted_command(self):
        from src.tools.adb import validate_adb_command

        allowed = ["input tap", "input swipe"]
        assert validate_adb_command("rm -rf /", allowed) is False

    def test_blocks_partial_prefix_mismatch(self):
        from src.tools.adb import validate_adb_command

        allowed = ["input tap"]
        assert validate_adb_command("input tapx 100 200", allowed) is True  # prefix match

    def test_empty_allowlist_blocks_everything(self):
        from src.tools.adb import validate_adb_command

        assert validate_adb_command("input tap 100 200", []) is False

    def test_strips_whitespace_before_matching(self):
        from src.tools.adb import validate_adb_command

        allowed = ["input tap"]
        assert validate_adb_command("  input tap 100 200", allowed) is True


# ---------------------------------------------------------------------------
# adb_tap
# ---------------------------------------------------------------------------
class TestAdbTap:
    @patch("src.tools.adb._run_adb_command")
    def test_tap_sends_input_command(self, mock_run):
        from src.tools.adb import adb_tap

        mock_run.return_value = {"success": True, "output": ""}
        result = adb_tap(x=100, y=200, device="emulator-5554")
        mock_run.assert_called_once_with("input tap 100 200", device="emulator-5554")
        assert result["success"] is True

    @patch("src.tools.adb._run_adb_command")
    def test_tap_without_device(self, mock_run):
        from src.tools.adb import adb_tap

        mock_run.return_value = {"success": True, "output": ""}
        result = adb_tap(x=50, y=75)
        mock_run.assert_called_once_with("input tap 50 75", device=None)
        assert result["success"] is True

    @patch("src.tools.adb._run_adb_command")
    def test_tap_propagates_failure(self, mock_run):
        from src.tools.adb import adb_tap

        mock_run.return_value = {"success": False, "error": "device offline"}
        result = adb_tap(x=0, y=0)
        assert result["success"] is False
        assert "device offline" in result["error"]


# ---------------------------------------------------------------------------
# adb_swipe
# ---------------------------------------------------------------------------
class TestAdbSwipe:
    @patch("src.tools.adb._run_adb_command")
    def test_swipe_sends_command(self, mock_run):
        from src.tools.adb import adb_swipe

        mock_run.return_value = {"success": True, "output": ""}
        result = adb_swipe(x1=100, y1=200, x2=300, y2=400, duration_ms=500, device="emulator-5554")
        mock_run.assert_called_once_with("input swipe 100 200 300 400 500", device="emulator-5554")
        assert result["success"] is True

    @patch("src.tools.adb._run_adb_command")
    def test_swipe_default_duration(self, mock_run):
        from src.tools.adb import adb_swipe

        mock_run.return_value = {"success": True, "output": ""}
        result = adb_swipe(x1=0, y1=0, x2=100, y2=100)
        mock_run.assert_called_once_with("input swipe 0 0 100 100 300", device=None)
        assert result["success"] is True

    @patch("src.tools.adb._run_adb_command")
    def test_swipe_propagates_failure(self, mock_run):
        from src.tools.adb import adb_swipe

        mock_run.return_value = {"success": False, "error": "timeout"}
        result = adb_swipe(x1=0, y1=0, x2=10, y2=10)
        assert result["success"] is False


# ---------------------------------------------------------------------------
# adb_key_event
# ---------------------------------------------------------------------------
class TestAdbKeyEvent:
    @patch("src.tools.adb._run_adb_command")
    def test_key_event_with_int_keycode(self, mock_run):
        from src.tools.adb import adb_key_event

        mock_run.return_value = {"success": True, "output": ""}
        result = adb_key_event(keycode=3, device="emulator-5554")
        mock_run.assert_called_once_with("input keyevent 3", device="emulator-5554")
        assert result["success"] is True

    @patch("src.tools.adb._run_adb_command")
    def test_key_event_with_string_keycode(self, mock_run):
        from src.tools.adb import adb_key_event

        mock_run.return_value = {"success": True, "output": ""}
        result = adb_key_event(keycode="KEYCODE_HOME")
        mock_run.assert_called_once_with("input keyevent KEYCODE_HOME", device=None)
        assert result["success"] is True

    @patch("src.tools.adb._run_adb_command")
    def test_key_event_propagates_failure(self, mock_run):
        from src.tools.adb import adb_key_event

        mock_run.return_value = {"success": False, "error": "no devices"}
        result = adb_key_event(keycode=4)
        assert result["success"] is False


# ---------------------------------------------------------------------------
# adb_shell
# ---------------------------------------------------------------------------
class TestAdbShell:
    @patch("src.tools.adb._run_adb_command")
    def test_shell_delegates_to_run(self, mock_run):
        from src.tools.adb import adb_shell

        mock_run.return_value = {"success": True, "output": "package:com.example"}
        result = adb_shell(command="pm list packages", device="emulator-5554")
        mock_run.assert_called_once_with("pm list packages", device="emulator-5554")
        assert result["success"] is True
        assert "com.example" in result["output"]

    @patch("src.tools.adb._run_adb_command")
    def test_shell_without_device(self, mock_run):
        from src.tools.adb import adb_shell

        mock_run.return_value = {"success": True, "output": "OK"}
        result = adb_shell(command="getprop ro.build.version.sdk")
        mock_run.assert_called_once_with("getprop ro.build.version.sdk", device=None)


# ---------------------------------------------------------------------------
# _run_adb_command — integration-level tests with subprocess mocked
# ---------------------------------------------------------------------------
class TestRunAdbCommand:
    @patch("src.tools.adb.subprocess.run")
    def test_successful_command(self, mock_subprocess):
        from src.tools.adb import _run_adb_command

        mock_subprocess.return_value = MagicMock(
            returncode=0, stdout="result text\n", stderr=""
        )
        result = _run_adb_command("input tap 100 200")
        mock_subprocess.assert_called_once_with(
            ["adb", "shell", "input tap 100 200"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result["success"] is True
        assert result["output"] == "result text"

    @patch("src.tools.adb.subprocess.run")
    def test_command_with_device(self, mock_subprocess):
        from src.tools.adb import _run_adb_command

        mock_subprocess.return_value = MagicMock(
            returncode=0, stdout="ok\n", stderr=""
        )
        result = _run_adb_command("input tap 1 2", device="emulator-5554")
        mock_subprocess.assert_called_once_with(
            ["adb", "-s", "emulator-5554", "shell", "input tap 1 2"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result["success"] is True

    @patch("src.tools.adb.subprocess.run")
    def test_nonzero_return_code(self, mock_subprocess):
        from src.tools.adb import _run_adb_command

        mock_subprocess.return_value = MagicMock(
            returncode=1, stdout="", stderr="error: device not found"
        )
        result = _run_adb_command("input tap 0 0")
        assert result["success"] is False
        assert "device not found" in result["error"]
        assert "suggestion" in result

    @patch("src.tools.adb.subprocess.run")
    def test_adb_not_found(self, mock_subprocess):
        from src.tools.adb import _run_adb_command

        mock_subprocess.side_effect = FileNotFoundError("adb not found")
        result = _run_adb_command("input tap 0 0")
        assert result["success"] is False
        assert "ADB not found" in result["error"]
        assert "suggestion" in result
        assert "BlueStacks" in result["suggestion"]

    @patch("src.tools.adb.subprocess.run")
    def test_timeout(self, mock_subprocess):
        from src.tools.adb import _run_adb_command

        mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd="adb", timeout=10)
        result = _run_adb_command("input tap 0 0")
        assert result["success"] is False
        assert "timed out" in result["error"]
        assert "suggestion" in result

    @patch("src.tools.adb.subprocess.run")
    def test_generic_exception(self, mock_subprocess):
        from src.tools.adb import _run_adb_command

        mock_subprocess.side_effect = OSError("unexpected")
        result = _run_adb_command("input tap 0 0")
        assert result["success"] is False
        assert "unexpected" in result["error"]
