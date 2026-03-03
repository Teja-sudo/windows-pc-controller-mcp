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


class TestMouseMove:
    def test_moves_cursor(self):
        from src.tools.mouse import mouse_move, mouse_position

        mouse_move(x=100, y=100)
        pos = mouse_position()
        assert abs(pos["x"] - 100) <= 2
        assert abs(pos["y"] - 100) <= 2
