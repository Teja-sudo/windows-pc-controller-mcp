"""Tests for the dashboard FastAPI backend."""
import sys
import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


class TestCreateApp:
    def test_app_creates_successfully(self):
        from src.dashboard import create_app
        app = create_app()
        assert app.title == "MCP Dashboard"

    def test_index_route_registered(self):
        from src.dashboard import create_app
        app = create_app()
        routes = [r.path for r in app.routes]
        assert "/" in routes

    def test_main_function_exists(self):
        from src.dashboard import main
        assert callable(main)
