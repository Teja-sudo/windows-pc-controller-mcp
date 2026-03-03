"""Tests for the dashboard FastAPI backend."""
import sys
from unittest.mock import patch, mock_open
import json

import pytest
import yaml

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


class TestConfigAPI:
    def _get_client(self):
        from src.dashboard import create_app
        from fastapi.testclient import TestClient
        return TestClient(create_app())

    def test_get_config_returns_merged(self):
        client = self._get_client()
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "security" in data
        assert "tools" in data

    def test_get_config_includes_metadata(self):
        client = self._get_client()
        resp = client.get("/api/config")
        data = resp.json()
        assert "_has_user_config" in data

    def test_put_config_saves_partial(self, tmp_path):
        """PUT /api/config with partial data should merge into user config."""
        import src.dashboard as dashboard
        original_user = dashboard.USER_YAML
        dashboard.USER_YAML = tmp_path / "config.yaml"
        try:
            client = self._get_client()
            resp = client.put("/api/config", json={
                "tools": {"clipboard_read": {"enabled": True}}
            })
            assert resp.status_code == 200
            # Verify file was written
            saved = yaml.safe_load(dashboard.USER_YAML.read_text())
            assert saved["tools"]["clipboard_read"]["enabled"] is True
        finally:
            dashboard.USER_YAML = original_user

    def test_post_config_reset_returns_defaults(self, tmp_path):
        import src.dashboard as dashboard
        original_user = dashboard.USER_YAML
        dashboard.USER_YAML = tmp_path / "config.yaml"
        dashboard.USER_YAML.write_text("tools:\n  clipboard_read:\n    enabled: true\n")
        try:
            client = self._get_client()
            resp = client.post("/api/config/reset")
            assert resp.status_code == 200
            assert not dashboard.USER_YAML.exists()
        finally:
            dashboard.USER_YAML = original_user
