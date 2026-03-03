import pytest
from unittest.mock import patch, MagicMock


class TestConfirmationResult:
    def test_allow_result(self):
        from src.security.confirmation_popup import ConfirmationResult

        result = ConfirmationResult(action="allow")
        assert result.is_allowed is True
        assert result.deny_reason is None

    def test_deny_result(self):
        from src.security.confirmation_popup import ConfirmationResult

        result = ConfirmationResult(action="deny")
        assert result.is_allowed is False
        assert result.deny_reason is None

    def test_deny_with_reason(self):
        from src.security.confirmation_popup import ConfirmationResult

        result = ConfirmationResult(action="deny", deny_reason="too dangerous")
        assert result.is_allowed is False
        assert result.deny_reason == "too dangerous"

    def test_timeout_result(self):
        from src.security.confirmation_popup import ConfirmationResult

        result = ConfirmationResult(action="timeout")
        assert result.is_allowed is False


class TestBuildDescription:
    def test_formats_tool_details(self):
        from src.security.confirmation_popup import build_description

        desc = build_description(
            tool_name="close_window",
            parameters={"window": "explorer.exe"},
        )
        assert "close_window" in desc
        assert "explorer.exe" in desc
