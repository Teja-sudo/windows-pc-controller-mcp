import sys
import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


class TestMousePosition:
    def test_returns_coordinates(self):
        from src.tools.mouse import mouse_position

        result = mouse_position()
        assert result["success"] is True
        assert "x" in result and "y" in result
        assert isinstance(result["x"], int)


class TestConvertCoords:
    def test_no_conversion_when_false(self):
        from src.tools.mouse import _convert_coords

        x, y = _convert_coords(100, 200, from_screenshot=False)
        assert x == 100 and y == 200

    def test_converts_when_scale_not_1(self):
        from src.tools.mouse import _convert_coords
        from src.utils.context import set_screenshot_scale

        set_screenshot_scale(2.0)
        x, y = _convert_coords(100, 200, from_screenshot=True)
        assert x == 200 and y == 400
        set_screenshot_scale(1.0)  # reset

    def test_no_change_when_scale_is_1(self):
        from src.tools.mouse import _convert_coords
        from src.utils.context import set_screenshot_scale

        set_screenshot_scale(1.0)
        x, y = _convert_coords(100, 200, from_screenshot=True)
        assert x == 100 and y == 200


class TestMouseMove:
    def test_moves_cursor(self):
        from src.tools.mouse import mouse_move, mouse_position

        mouse_move(x=100, y=100)
        pos = mouse_position()
        assert abs(pos["x"] - 100) <= 2
        assert abs(pos["y"] - 100) <= 2
