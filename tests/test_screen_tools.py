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
        raw = base64.b64decode(result["image_base64"])
        assert len(raw) > 0

    def test_capture_region(self):
        from src.tools.screen import capture_screenshot

        result = capture_screenshot(region={"left": 0, "top": 0, "width": 100, "height": 100})
        assert result["success"] is True

    def test_includes_dpi_scale(self):
        from src.tools.screen import capture_screenshot

        result = capture_screenshot(region={"left": 0, "top": 0, "width": 50, "height": 50})
        assert result["success"] is True
        assert "dpi_scale" in result
        assert isinstance(result["dpi_scale"], float)
        assert result["dpi_scale"] >= 1.0


    def test_window_title_capture(self):
        from src.tools.screen import capture_screenshot

        # Capture a known window — every Windows session has a desktop window
        result = capture_screenshot(window_title="Program Manager")
        # Program Manager might not always be visible, so accept success or not-found
        if result["success"]:
            assert "image_base64" in result
            assert result["width"] > 0
        else:
            assert "no window found" in result["error"].lower()

    def test_window_title_not_found(self):
        from src.tools.screen import capture_screenshot

        result = capture_screenshot(window_title="ZZZ_NonExistentWindow_99999")
        assert result["success"] is False
        assert "no window found" in result["error"].lower()
        assert "suggestion" in result

    def test_window_title_ignored_when_region_given(self):
        from src.tools.screen import capture_screenshot

        # When both region and window_title are given, region takes precedence
        result = capture_screenshot(
            region={"left": 0, "top": 0, "width": 50, "height": 50},
            window_title="NonExistent",
        )
        assert result["success"] is True


class TestGetScreenInfo:
    def test_returns_screen_info(self):
        from src.tools.screen import get_screen_info

        result = get_screen_info()
        assert result["success"] is True
        assert "primary_monitor" in result
        assert result["primary_monitor"]["width"] > 0
        assert result["primary_monitor"]["height"] > 0

    def test_includes_dpi_scale(self):
        from src.tools.screen import get_screen_info

        result = get_screen_info()
        assert "dpi_scale" in result
        assert isinstance(result["dpi_scale"], float)
        assert result["dpi_scale"] >= 1.0

    def test_includes_active_window(self):
        from src.tools.screen import get_screen_info

        result = get_screen_info()
        assert "active_window" in result
        assert isinstance(result["active_window"], str)

    def test_includes_monitor_count(self):
        from src.tools.screen import get_screen_info

        result = get_screen_info()
        assert "monitor_count" in result
        assert result["monitor_count"] >= 1


class TestGetPixelColor:
    def test_returns_rgb(self):
        from src.tools.screen import get_pixel_color

        result = get_pixel_color(x=0, y=0)
        assert result["success"] is True
        assert "r" in result and "g" in result and "b" in result
        assert 0 <= result["r"] <= 255


class TestDownscaleForAgent:
    def test_no_downscale_when_within_limits(self):
        from src.tools.screen import _downscale_for_agent
        from PIL import Image

        img = Image.new("RGB", (800, 600))
        scaled, factor = _downscale_for_agent(img, (1280, 800))
        assert scaled.width == 800
        assert scaled.height == 600
        assert factor == 1.0

    def test_downscales_large_image(self):
        from src.tools.screen import _downscale_for_agent
        from PIL import Image

        img = Image.new("RGB", (2560, 1600))
        scaled, factor = _downscale_for_agent(img, (1280, 800))
        assert scaled.width == 1280
        assert scaled.height == 800
        assert factor == 2.0

    def test_downscale_preserves_aspect_ratio(self):
        from src.tools.screen import _downscale_for_agent
        from PIL import Image

        img = Image.new("RGB", (3840, 2160))  # 16:9
        scaled, factor = _downscale_for_agent(img, (1280, 800))
        # 3840/1280 = 3.0, 2160/800 = 2.7 → limited by height
        assert scaled.width <= 1280
        assert scaled.height <= 800
        # Aspect ratio preserved
        orig_ratio = 3840 / 2160
        new_ratio = scaled.width / scaled.height
        assert abs(orig_ratio - new_ratio) < 0.01

    def test_screenshot_includes_scale_metadata(self):
        from src.tools.screen import capture_screenshot

        result = capture_screenshot(region={"left": 0, "top": 0, "width": 100, "height": 100})
        assert result["success"] is True
        assert "screenshot_scale" in result
        assert "original_width" in result
        assert "original_height" in result


class TestListWindows:
    def test_returns_window_list(self):
        from src.tools.screen import list_windows_tool

        result = list_windows_tool(blocked_apps=[])
        assert result["success"] is True
        assert isinstance(result["windows"], list)
