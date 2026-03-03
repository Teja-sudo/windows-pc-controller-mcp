import json
from pathlib import Path
import pytest


class TestAuditLogger:
    def test_logs_tool_call(self, tmp_path):
        from src.security.audit import AuditLogger

        log_file = tmp_path / "audit.log"
        logger = AuditLogger(log_path=str(log_file))

        logger.log_tool_call(
            tool_name="mouse_click",
            parameters={"x": 100, "y": 200, "button": "left"},
            result={"success": True},
            allowed=True,
        )

        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["tool"] == "mouse_click"
        assert entry["allowed"] is True
        assert "timestamp" in entry

    def test_logs_denied_action(self, tmp_path):
        from src.security.audit import AuditLogger

        log_file = tmp_path / "audit.log"
        logger = AuditLogger(log_path=str(log_file))

        logger.log_tool_call(
            tool_name="close_window",
            parameters={"window": "explorer.exe"},
            result=None,
            allowed=False,
            deny_reason="User denied: don't close explorer",
        )

        entry = json.loads(log_file.read_text().strip())
        assert entry["allowed"] is False
        assert "don't close explorer" in entry["deny_reason"]

    def test_disabled_logger_no_ops(self, tmp_path):
        from src.security.audit import AuditLogger

        log_file = tmp_path / "audit.log"
        logger = AuditLogger(log_path=str(log_file), enabled=False)

        logger.log_tool_call(tool_name="test", parameters={}, result={}, allowed=True)
        assert not log_file.exists()
