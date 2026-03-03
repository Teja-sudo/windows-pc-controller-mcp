"""Tests for src.utils.mouse_backend — ctypes SendInput mouse control."""
import sys
import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


class TestGetCursorPos:
    def test_returns_int_tuple(self):
        from src.utils.mouse_backend import get_cursor_pos

        x, y = get_cursor_pos()
        assert isinstance(x, int)
        assert isinstance(y, int)


class TestMove:
    def test_moves_to_absolute_coords(self):
        from src.utils.mouse_backend import move, get_cursor_pos

        move(200, 200)
        x, y = get_cursor_pos()
        assert abs(x - 200) <= 1
        assert abs(y - 200) <= 1

    def test_pixel_perfect_center_of_screen(self):
        """Moving to screen center should land exactly there."""
        import ctypes
        from src.utils.mouse_backend import move, get_cursor_pos

        # Get primary monitor dimensions
        w = ctypes.windll.user32.GetSystemMetrics(0)  # SM_CXSCREEN
        h = ctypes.windll.user32.GetSystemMetrics(1)  # SM_CYSCREEN
        cx, cy = w // 2, h // 2

        move(cx, cy)
        x, y = get_cursor_pos()
        assert abs(x - cx) <= 1
        assert abs(y - cy) <= 1


class TestMoveRelative:
    def test_relative_offset(self):
        from src.utils.mouse_backend import move, move_relative, get_cursor_pos

        move(300, 300)
        move_relative(50, -25)
        x, y = get_cursor_pos()
        assert abs(x - 350) <= 2
        assert abs(y - 275) <= 2


class TestClick:
    def test_click_at_current_pos(self):
        """Click without coords should not crash."""
        from src.utils.mouse_backend import click

        click()  # Should not raise

    def test_click_at_coords(self):
        from src.utils.mouse_backend import click, get_cursor_pos

        click(x=400, y=400)
        x, y = get_cursor_pos()
        assert abs(x - 400) <= 1
        assert abs(y - 400) <= 1

    def test_double_click(self):
        from src.utils.mouse_backend import click

        click(x=400, y=400, clicks=2)  # Should not raise

    def test_right_click(self):
        from src.utils.mouse_backend import click

        click(button="right")  # Should not raise


class TestScroll:
    def test_vertical_scroll(self):
        from src.utils.mouse_backend import scroll

        scroll(dy=3)  # Should not raise

    def test_horizontal_scroll(self):
        from src.utils.mouse_backend import scroll

        scroll(dx=2)  # Should not raise


class TestToAbsolute:
    def test_origin_maps_to_zero(self):
        """Physical (0, 0) should map to near 0 in absolute coords."""
        from src.utils.mouse_backend import _to_absolute

        abs_x, abs_y = _to_absolute(0, 0)
        # With virtual desktop origin at (0,0), should be near 0
        assert abs_x >= 0
        assert abs_y >= 0


class TestConvertCoordsWithOffset:
    """Test _convert_coords applies both scale and offset for window captures."""

    def test_no_conversion_when_from_screenshot_false(self):
        from src.tools.mouse import _convert_coords

        x, y = _convert_coords(100, 200, from_screenshot=False)
        assert (x, y) == (100, 200)

    def test_applies_scale_only_for_monitor_capture(self):
        from src.tools.mouse import _convert_coords
        from src.utils.context import set_screenshot_scale

        set_screenshot_scale(1.5, offset=(0, 0))
        x, y = _convert_coords(100, 200, from_screenshot=True)
        assert x == 150
        assert y == 300
        set_screenshot_scale(1.0, offset=(0, 0))

    def test_applies_scale_and_offset_for_window_capture(self):
        from src.tools.mouse import _convert_coords
        from src.utils.context import set_screenshot_scale

        # Simulate window capture at screen (60, 10) with 1.5x scale
        set_screenshot_scale(1.5, offset=(60, 10))
        x, y = _convert_coords(100, 200, from_screenshot=True)
        # Expected: (100 * 1.5) + 60 = 210, (200 * 1.5) + 10 = 310
        assert x == 210
        assert y == 310
        set_screenshot_scale(1.0, offset=(0, 0))

    def test_zero_scale_with_offset(self):
        from src.tools.mouse import _convert_coords
        from src.utils.context import set_screenshot_scale

        # Scale of 1.0 (no downscale) but with window offset
        set_screenshot_scale(1.0, offset=(100, 50))
        x, y = _convert_coords(20, 30, from_screenshot=True)
        assert x == 120  # 20 * 1.0 + 100
        assert y == 80   # 30 * 1.0 + 50
        set_screenshot_scale(1.0, offset=(0, 0))
