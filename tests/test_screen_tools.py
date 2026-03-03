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


class TestGetPixelColor:
    def test_returns_rgb(self):
        from src.tools.screen import get_pixel_color

        result = get_pixel_color(x=0, y=0)
        assert result["success"] is True
        assert "r" in result and "g" in result and "b" in result
        assert 0 <= result["r"] <= 255


class TestListWindows:
    def test_returns_window_list(self):
        from src.tools.screen import list_windows_tool

        result = list_windows_tool(blocked_apps=[])
        assert result["success"] is True
        assert isinstance(result["windows"], list)
