"""Tests for the dashboard FastAPI backend."""
import sys
from datetime import datetime, timezone, timedelta
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


class TestAuditAPI:
    @staticmethod
    def _make_entries():
        """Build sample audit entries with timestamps that always fall within the last 24h."""
        now = datetime.now(timezone.utc)
        timestamps = [
            (now - timedelta(minutes=50)).isoformat(),
            (now - timedelta(minutes=40)).isoformat(),
            (now - timedelta(minutes=30)).isoformat(),
            (now - timedelta(minutes=20)).isoformat(),
            (now - timedelta(minutes=10)).isoformat(),
        ]
        return [
            json.dumps({"timestamp": timestamps[0], "tool": "mouse_click", "parameters": {"x": 100, "y": 200}, "allowed": True}),
            json.dumps({"timestamp": timestamps[1], "tool": "launch_app", "parameters": {"app": "notepad"}, "allowed": False, "deny_reason": "Not in allowlist"}),
            json.dumps({"timestamp": timestamps[2], "tool": "capture_screenshot", "parameters": {"monitor": 0}, "allowed": True}),
            json.dumps({"timestamp": timestamps[3], "tool": "keyboard_hotkey", "parameters": {"keys": "alt+f4"}, "allowed": False, "deny_reason": "Blocked hotkey"}),
            json.dumps({"timestamp": timestamps[4], "tool": "mouse_click", "parameters": {"x": 300, "y": 400}, "allowed": True}),
        ]

    def _get_client_with_log(self, tmp_path):
        import src.dashboard as dashboard
        original_log = dashboard.AUDIT_LOG
        dashboard.AUDIT_LOG = tmp_path / "audit.log"
        entries = self._make_entries()
        dashboard.AUDIT_LOG.write_text("\n".join(entries) + "\n")
        from src.dashboard import create_app
        from fastapi.testclient import TestClient
        return TestClient(create_app()), original_log

    def test_get_audit_returns_entries(self, tmp_path):
        client, orig = self._get_client_with_log(tmp_path)
        import src.dashboard as dashboard
        try:
            resp = client.get("/api/audit")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 5
            assert len(data["entries"]) == 5
        finally:
            dashboard.AUDIT_LOG = orig

    def test_get_audit_filter_by_tool(self, tmp_path):
        client, orig = self._get_client_with_log(tmp_path)
        import src.dashboard as dashboard
        try:
            resp = client.get("/api/audit?tool=mouse_click")
            data = resp.json()
            assert data["total"] == 2
        finally:
            dashboard.AUDIT_LOG = orig

    def test_get_audit_filter_by_status(self, tmp_path):
        client, orig = self._get_client_with_log(tmp_path)
        import src.dashboard as dashboard
        try:
            resp = client.get("/api/audit?status=denied")
            data = resp.json()
            assert data["total"] == 2
        finally:
            dashboard.AUDIT_LOG = orig

    def test_get_audit_pagination(self, tmp_path):
        client, orig = self._get_client_with_log(tmp_path)
        import src.dashboard as dashboard
        try:
            resp = client.get("/api/audit?limit=2&offset=0")
            data = resp.json()
            assert len(data["entries"]) == 2
            assert data["total"] == 5
        finally:
            dashboard.AUDIT_LOG = orig

    def test_get_audit_stats(self, tmp_path):
        client, orig = self._get_client_with_log(tmp_path)
        import src.dashboard as dashboard
        try:
            resp = client.get("/api/audit/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_calls"] == 5
            assert data["allowed"] == 3
            assert data["denied"] == 2
        finally:
            dashboard.AUDIT_LOG = orig

    def test_get_audit_empty_log(self, tmp_path):
        import src.dashboard as dashboard
        original_log = dashboard.AUDIT_LOG
        dashboard.AUDIT_LOG = tmp_path / "nonexistent.log"
        from src.dashboard import create_app
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        try:
            resp = client.get("/api/audit")
            data = resp.json()
            assert data["total"] == 0
            assert data["entries"] == []
        finally:
            dashboard.AUDIT_LOG = original_log
