"""Tests for system management tools — launch_app, focus_window, close_window, get_system_info, window_manage, open_url, get_health."""
import sys
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")

if sys.platform == "win32":
    import win32con


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


# ---------------------------------------------------------------------------
# window_manage
# ---------------------------------------------------------------------------
class TestWindowManage:
    def test_invalid_action(self):
        from src.tools.system import window_manage

        result = window_manage(action="explode")
        assert result["success"] is False
        assert "error_code" in result
        assert "explode" in result["error"]

    def test_requires_title_or_process(self):
        from src.tools.system import window_manage

        result = window_manage(action="maximize")
        assert result["success"] is False
        assert "either" in result["error"].lower() or "not found" in result["error"].lower()

    @patch("src.tools.system.enumerate_windows")
    @patch("src.tools.system.win32gui")
    def test_maximize_window(self, mock_win32gui, mock_enum):
        from src.tools.system import window_manage

        mock_enum.return_value = [
            {"title": "Notepad", "process_name": "notepad.exe", "hwnd": 12345},
        ]

        result = window_manage(action="maximize", title="Notepad")
        assert result["success"] is True
        mock_win32gui.ShowWindow.assert_called_once_with(12345, win32con.SW_MAXIMIZE)

    @patch("src.tools.system.enumerate_windows")
    @patch("src.tools.system.win32gui")
    def test_minimize_window(self, mock_win32gui, mock_enum):
        from src.tools.system import window_manage

        mock_enum.return_value = [
            {"title": "Notepad", "process_name": "notepad.exe", "hwnd": 12345},
        ]

        result = window_manage(action="minimize", title="Notepad")
        assert result["success"] is True
        mock_win32gui.ShowWindow.assert_called_once_with(12345, win32con.SW_MINIMIZE)

    @patch("src.tools.system.enumerate_windows")
    @patch("src.tools.system.win32gui")
    def test_restore_window(self, mock_win32gui, mock_enum):
        from src.tools.system import window_manage

        mock_enum.return_value = [
            {"title": "Notepad", "process_name": "notepad.exe", "hwnd": 12345},
        ]

        result = window_manage(action="restore", title="Notepad")
        assert result["success"] is True
        mock_win32gui.ShowWindow.assert_called_once_with(12345, win32con.SW_RESTORE)

    @patch("src.tools.system.enumerate_windows")
    @patch("src.tools.system.win32gui")
    def test_resize_requires_width_and_height(self, mock_win32gui, mock_enum):
        from src.tools.system import window_manage

        mock_enum.return_value = [
            {"title": "Notepad", "process_name": "notepad.exe", "hwnd": 12345},
        ]

        result = window_manage(action="resize", title="Notepad", width=800)
        assert result["success"] is False
        assert "height" in result["error"]

    @patch("src.tools.system.enumerate_windows")
    @patch("src.tools.system.win32gui")
    def test_resize_window(self, mock_win32gui, mock_enum):
        from src.tools.system import window_manage

        mock_enum.return_value = [
            {"title": "Notepad", "process_name": "notepad.exe", "hwnd": 12345},
        ]
        mock_win32gui.GetWindowRect.return_value = (100, 100, 500, 400)

        result = window_manage(action="resize", title="Notepad", width=800, height=600)
        assert result["success"] is True
        mock_win32gui.MoveWindow.assert_called_once_with(12345, 100, 100, 800, 600, True)

    @patch("src.tools.system.enumerate_windows")
    @patch("src.tools.system.win32gui")
    def test_move_requires_x_and_y(self, mock_win32gui, mock_enum):
        from src.tools.system import window_manage

        mock_enum.return_value = [
            {"title": "Notepad", "process_name": "notepad.exe", "hwnd": 12345},
        ]

        result = window_manage(action="move", title="Notepad", x=100)
        assert result["success"] is False
        assert "y" in result["error"]

    @patch("src.tools.system.enumerate_windows")
    @patch("src.tools.system.win32gui")
    def test_move_window(self, mock_win32gui, mock_enum):
        from src.tools.system import window_manage

        mock_enum.return_value = [
            {"title": "Notepad", "process_name": "notepad.exe", "hwnd": 12345},
        ]
        mock_win32gui.GetWindowRect.return_value = (100, 100, 500, 400)

        result = window_manage(action="move", title="Notepad", x=200, y=300)
        assert result["success"] is True
        # Width = 500-100=400, Height = 400-100=300
        mock_win32gui.MoveWindow.assert_called_once_with(12345, 200, 300, 400, 300, True)

    @patch("src.tools.system.enumerate_windows")
    def test_blocked_app_denied(self, mock_enum):
        from src.tools.system import window_manage

        result = window_manage(
            action="maximize", title="1Password", blocked_apps=["1Password"],
        )
        assert result["success"] is False
        assert result["error_code"] == "BLOCKED"

    @patch("src.tools.system.enumerate_windows")
    def test_window_not_found(self, mock_enum):
        from src.tools.system import window_manage

        mock_enum.return_value = []
        result = window_manage(action="maximize", title="NonExistent")
        assert result["success"] is False
        assert result["error_code"] == "NOT_FOUND"

    @patch("src.tools.system.enumerate_windows")
    @patch("src.tools.system.win32gui")
    def test_find_by_process(self, mock_win32gui, mock_enum):
        from src.tools.system import window_manage

        mock_enum.return_value = [
            {"title": "Untitled", "process_name": "notepad.exe", "hwnd": 999},
        ]

        result = window_manage(action="maximize", process="notepad.exe")
        assert result["success"] is True
        mock_win32gui.ShowWindow.assert_called_once_with(999, win32con.SW_MAXIMIZE)

    @patch("src.tools.system.enumerate_windows")
    @patch("src.tools.system.win32gui")
    @patch("mss.mss")
    def test_snap_left(self, mock_mss_cls, mock_win32gui, mock_enum):
        from src.tools.system import window_manage

        mock_enum.return_value = [
            {"title": "Notepad", "process_name": "notepad.exe", "hwnd": 12345},
        ]
        # Mock mss context manager
        mock_sct = MagicMock()
        mock_sct.monitors = [
            {},  # monitor 0 (all monitors combined)
            {"left": 0, "top": 0, "width": 1920, "height": 1080},
        ]
        mock_mss_cls.return_value.__enter__ = MagicMock(return_value=mock_sct)
        mock_mss_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = window_manage(action="snap_left", title="Notepad")
        assert result["success"] is True
        mock_win32gui.ShowWindow.assert_called_once_with(12345, win32con.SW_RESTORE)
        mock_win32gui.MoveWindow.assert_called_once_with(12345, 0, 0, 960, 1080, True)


# ---------------------------------------------------------------------------
# open_url
# ---------------------------------------------------------------------------
class TestOpenUrl:
    @patch("src.tools.system.webbrowser.open")
    def test_opens_valid_url(self, mock_open):
        from src.tools.system import open_url

        result = open_url("https://example.com")
        assert result["success"] is True
        assert result["url"] == "https://example.com"
        mock_open.assert_called_once_with("https://example.com")

    @patch("src.tools.system.webbrowser.open")
    def test_opens_http_url(self, mock_open):
        from src.tools.system import open_url

        result = open_url("http://example.com")
        assert result["success"] is True
        mock_open.assert_called_once_with("http://example.com")

    def test_rejects_non_http_url(self):
        from src.tools.system import open_url

        result = open_url("ftp://example.com")
        assert result["success"] is False
        assert result["error_code"] == "INVALID_PARAMS"
        assert "http" in result["suggestion"]

    def test_rejects_bare_domain(self):
        from src.tools.system import open_url

        result = open_url("example.com")
        assert result["success"] is False
        assert result["error_code"] == "INVALID_PARAMS"

    @patch("src.tools.system.webbrowser.open")
    def test_handles_browser_error(self, mock_open):
        from src.tools.system import open_url

        mock_open.side_effect = Exception("No default browser")
        result = open_url("https://example.com")
        assert result["success"] is False
        assert "browser" in result["suggestion"].lower()


# ---------------------------------------------------------------------------
# get_health
# ---------------------------------------------------------------------------
class TestGetHealth:
    @patch("src.tools.system.shutil.which")
    @patch("src.tools.screen.get_screen_info")
    @patch("src.utils.dpi.get_dpi_scale_factor")
    def test_returns_health_info(self, mock_dpi, mock_screen, mock_which):
        from src.tools.system import get_health

        mock_dpi.return_value = 1.0
        mock_screen.return_value = {
            "success": True,
            "primary_monitor": {"width": 1920, "height": 1080},
            "monitor_count": 2,
        }
        mock_which.return_value = "/usr/bin/adb"

        result = get_health()
        assert result["success"] is True
        assert result["dpi_scale"] == 1.0
        assert result["screen"]["width"] == 1920
        assert result["screen"]["height"] == 1080
        assert result["screen"]["monitors"] == 2
        assert result["adb_available"] is True
        assert "ocr_engine" in result
        assert "tool_count" in result

    @patch("src.tools.system.shutil.which")
    @patch("src.tools.screen.get_screen_info")
    @patch("src.utils.dpi.get_dpi_scale_factor")
    def test_adb_not_available(self, mock_dpi, mock_screen, mock_which):
        from src.tools.system import get_health

        mock_dpi.return_value = 1.25
        mock_screen.return_value = {"success": True, "primary_monitor": {"width": 1920, "height": 1080}, "monitor_count": 1}
        mock_which.return_value = None

        result = get_health()
        assert result["success"] is True
        assert result["adb_available"] is False

    @patch("src.tools.system.shutil.which")
    @patch("src.tools.screen.get_screen_info")
    @patch("src.utils.dpi.get_dpi_scale_factor")
    def test_screen_info_failure_still_returns_health(self, mock_dpi, mock_screen, mock_which):
        from src.tools.system import get_health

        mock_dpi.return_value = 1.0
        mock_screen.return_value = {"success": False, "error": "no display"}
        mock_which.return_value = None

        result = get_health()
        assert result["success"] is True
        # screen key should be absent when screen info fails
        assert "screen" not in result
