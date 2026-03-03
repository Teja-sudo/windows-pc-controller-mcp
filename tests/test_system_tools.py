"""Tests for system management tools — launch_app, focus_window, close_window, get_system_info."""
import sys
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


# ---------------------------------------------------------------------------
# launch_app
# ---------------------------------------------------------------------------
class TestLaunchApp:
    @patch("src.tools.system.subprocess.Popen")
    def test_launches_app_successfully(self, mock_popen):
        from src.tools.system import launch_app

        mock_popen.return_value = MagicMock()
        result = launch_app("notepad.exe")
        assert result["success"] is True
        assert result["app"] == "notepad.exe"
        assert "launched" in result["message"].lower()
        mock_popen.assert_called_once_with("notepad.exe", shell=False)

    @patch("src.tools.system.subprocess.Popen")
    def test_app_not_found(self, mock_popen):
        from src.tools.system import launch_app

        mock_popen.side_effect = FileNotFoundError("not found")
        result = launch_app("nonexistent.exe")
        assert result["success"] is False
        assert "not found" in result["error"].lower()
        assert "suggestion" in result

    @patch("src.tools.system.subprocess.Popen")
    def test_generic_exception(self, mock_popen):
        from src.tools.system import launch_app

        mock_popen.side_effect = OSError("permission denied")
        result = launch_app("restricted.exe")
        assert result["success"] is False
        assert "permission denied" in result["error"]

    @patch("src.tools.system.subprocess.Popen")
    def test_shell_is_false_for_security(self, mock_popen):
        from src.tools.system import launch_app

        mock_popen.return_value = MagicMock()
        launch_app("calc.exe")
        # Verify shell=False for security (no shell injection)
        mock_popen.assert_called_once_with("calc.exe", shell=False)


# ---------------------------------------------------------------------------
# focus_window
# ---------------------------------------------------------------------------
class TestFocusWindow:
    @patch("src.tools.system.focus_window_by_title")
    def test_focuses_existing_window(self, mock_focus):
        from src.tools.system import focus_window

        mock_focus.return_value = True
        result = focus_window(title="Notepad")
        assert result["success"] is True
        assert "focused" in result["message"].lower()
        mock_focus.assert_called_once_with("Notepad")

    @patch("src.tools.system.enumerate_windows")
    @patch("src.tools.system.focus_window_by_title")
    def test_window_not_found(self, mock_focus, mock_enum):
        from src.tools.system import focus_window

        mock_focus.return_value = False
        mock_enum.return_value = [{"title": "Desktop", "process_name": "explorer.exe"}]
        result = focus_window(title="NonExistentApp")
        assert result["success"] is False
        assert "no window found" in result["error"].lower()
        assert "suggestion" in result
        assert "available_windows" in result

    @patch("src.tools.system.focus_window_by_title")
    def test_handles_exception(self, mock_focus):
        from src.tools.system import focus_window

        mock_focus.side_effect = Exception("win32 error")
        result = focus_window(title="SomeApp")
        assert result["success"] is False
        assert "win32 error" in result["error"]

    def test_requires_title_or_process(self):
        from src.tools.system import focus_window

        result = focus_window()
        assert result["success"] is False
        assert "either" in result["error"].lower()

    @patch("src.tools.system.focus_window_by_process")
    def test_focus_by_process(self, mock_focus_proc):
        from src.tools.system import focus_window

        mock_focus_proc.return_value = True
        result = focus_window(process="msedge.exe")
        assert result["success"] is True
        mock_focus_proc.assert_called_once_with("msedge.exe")

    @patch("src.tools.system.focus_window_by_title")
    def test_blocked_app_denied(self, mock_focus):
        from src.tools.system import focus_window

        mock_focus.return_value = True  # Would succeed without blocking
        result = focus_window(title="1Password", blocked_apps=["1Password"])
        assert result["success"] is False
        assert "denied" in result["error"].lower() or "blocked" in result["error"].lower()

    @patch("src.tools.system.focus_window_by_title")
    @patch("src.tools.system.focus_window_by_process")
    def test_falls_back_to_process_when_title_fails(self, mock_proc, mock_title):
        from src.tools.system import focus_window

        mock_title.return_value = False
        mock_proc.return_value = True
        result = focus_window(title="SomeTitle", process="myapp.exe")
        assert result["success"] is True
        mock_title.assert_called_once()
        mock_proc.assert_called_once()


# ---------------------------------------------------------------------------
# close_window
# ---------------------------------------------------------------------------
class TestCloseWindow:
    @patch("src.tools.system.close_window_by_title")
    def test_closes_existing_window(self, mock_close):
        from src.tools.system import close_window

        mock_close.return_value = True
        result = close_window(title="Notepad")
        assert result["success"] is True
        assert "close" in result["message"].lower()
        mock_close.assert_called_once_with("Notepad")

    @patch("src.tools.system.close_window_by_title")
    def test_window_not_found(self, mock_close):
        from src.tools.system import close_window

        mock_close.return_value = False
        result = close_window(title="NonExistentApp")
        assert result["success"] is False
        assert "no window found" in result["error"].lower()
        assert "suggestion" in result

    @patch("src.tools.system.close_window_by_title")
    def test_handles_exception(self, mock_close):
        from src.tools.system import close_window

        mock_close.side_effect = Exception("access denied")
        result = close_window(title="SomeApp")
        assert result["success"] is False
        assert "access denied" in result["error"]

    @patch("src.tools.system.close_window_by_title")
    def test_blocked_app_denied(self, mock_close):
        from src.tools.system import close_window

        result = close_window(title="KeePass", blocked_apps=["KeePass"])
        assert result["success"] is False
        assert "denied" in result["error"].lower() or "blocked" in result["error"].lower()
        mock_close.assert_not_called()

    def test_requires_title_or_process(self):
        from src.tools.system import close_window

        result = close_window()
        assert result["success"] is False


# ---------------------------------------------------------------------------
# get_system_info
# ---------------------------------------------------------------------------
class TestGetSystemInfo:
    @patch("src.tools.system.psutil")
    def test_returns_system_info(self, mock_psutil):
        from src.tools.system import get_system_info

        # Mock virtual_memory
        mock_mem = MagicMock()
        mock_mem.total = 16 * (1024**3)  # 16 GB
        mock_mem.used = 8 * (1024**3)    # 8 GB
        mock_mem.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_mem

        # Mock disk_usage
        mock_disk = MagicMock()
        mock_disk.total = 500 * (1024**3)  # 500 GB
        mock_disk.used = 250 * (1024**3)   # 250 GB
        mock_disk.percent = 50.0
        mock_psutil.disk_usage.return_value = mock_disk

        # Mock CPU
        mock_psutil.cpu_percent.return_value = 25.0
        mock_psutil.cpu_count.return_value = 8

        # No battery
        mock_psutil.sensors_battery.return_value = None

        result = get_system_info()
        assert result["success"] is True
        assert "cpu_percent" in result
        assert "memory" in result
        assert "disk" in result
        assert result["cpu_percent"] == 25.0
        assert result["cpu_count"] == 8
        assert result["memory"]["total_gb"] == 16.0
        assert result["memory"]["used_gb"] == 8.0
        assert result["memory"]["percent"] == 50.0
        assert result["disk"]["total_gb"] == 500.0
        assert result["disk"]["used_gb"] == 250.0
        assert result["disk"]["percent"] == 50.0

    @patch("src.tools.system.psutil")
    def test_includes_battery_when_available(self, mock_psutil):
        from src.tools.system import get_system_info

        # Mock virtual_memory
        mock_mem = MagicMock()
        mock_mem.total = 8 * (1024**3)
        mock_mem.used = 4 * (1024**3)
        mock_mem.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_mem

        # Mock disk_usage
        mock_disk = MagicMock()
        mock_disk.total = 256 * (1024**3)
        mock_disk.used = 100 * (1024**3)
        mock_disk.percent = 39.1
        mock_psutil.disk_usage.return_value = mock_disk

        # Mock CPU
        mock_psutil.cpu_percent.return_value = 10.0
        mock_psutil.cpu_count.return_value = 4

        # Mock battery present
        mock_battery = MagicMock()
        mock_battery.percent = 85
        mock_battery.power_plugged = True
        mock_psutil.sensors_battery.return_value = mock_battery

        result = get_system_info()
        assert result["success"] is True
        assert "battery" in result
        assert result["battery"]["percent"] == 85
        assert result["battery"]["plugged_in"] is True

    @patch("src.tools.system.psutil")
    def test_no_battery_key_when_absent(self, mock_psutil):
        from src.tools.system import get_system_info

        mock_mem = MagicMock()
        mock_mem.total = 8 * (1024**3)
        mock_mem.used = 4 * (1024**3)
        mock_mem.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_mem

        mock_disk = MagicMock()
        mock_disk.total = 256 * (1024**3)
        mock_disk.used = 100 * (1024**3)
        mock_disk.percent = 39.1
        mock_psutil.disk_usage.return_value = mock_disk

        mock_psutil.cpu_percent.return_value = 10.0
        mock_psutil.cpu_count.return_value = 4
        mock_psutil.sensors_battery.return_value = None

        result = get_system_info()
        assert result["success"] is True
        assert "battery" not in result

    @patch("src.tools.system.psutil")
    def test_handles_exception(self, mock_psutil):
        from src.tools.system import get_system_info

        mock_psutil.virtual_memory.side_effect = Exception("access denied")
        result = get_system_info()
        assert result["success"] is False
        assert "access denied" in result["error"]

    @patch("src.tools.system.psutil")
    def test_does_not_include_pii(self, mock_psutil):
        """Verify system info does not include usernames, paths, or other PII."""
        from src.tools.system import get_system_info

        mock_mem = MagicMock()
        mock_mem.total = 16 * (1024**3)
        mock_mem.used = 8 * (1024**3)
        mock_mem.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_mem

        mock_disk = MagicMock()
        mock_disk.total = 500 * (1024**3)
        mock_disk.used = 250 * (1024**3)
        mock_disk.percent = 50.0
        mock_psutil.disk_usage.return_value = mock_disk

        mock_psutil.cpu_percent.return_value = 25.0
        mock_psutil.cpu_count.return_value = 8
        mock_psutil.sensors_battery.return_value = None

        result = get_system_info()
        # Should not contain any username or path-related keys
        result_str = str(result).lower()
        assert "username" not in result_str
        assert "hostname" not in result_str
        assert "users\\" not in result_str
