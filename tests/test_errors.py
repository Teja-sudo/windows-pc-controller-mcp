"""Tests for src.utils.errors — standardized error codes and helpers."""
from __future__ import annotations

from src.utils.errors import (
    tool_error, tool_success,
    NOT_FOUND, BLOCKED, RATE_LIMITED, TIMEOUT, INVALID_PARAMS,
    DEPENDENCY_MISSING, OS_ERROR,
)


class TestErrorConstants:
    """Verify error code constants exist and are strings."""

    def test_all_constants_are_strings(self):
        for code in [NOT_FOUND, BLOCKED, RATE_LIMITED, TIMEOUT,
                     INVALID_PARAMS, DEPENDENCY_MISSING, OS_ERROR]:
            assert isinstance(code, str)
            assert code == code.upper()  # all caps convention


class TestToolError:
    """Verify tool_error builds correct dicts."""

    def test_basic_error(self):
        result = tool_error("Something failed", OS_ERROR)
        assert result["success"] is False
        assert result["error"] == "Something failed"
        assert result["error_code"] == "OS_ERROR"
        assert "suggestion" not in result

    def test_error_with_suggestion(self):
        result = tool_error("Not found", NOT_FOUND, suggestion="Try again")
        assert result["suggestion"] == "Try again"
        assert result["error_code"] == "NOT_FOUND"

    def test_error_with_extras(self):
        result = tool_error("Bad", INVALID_PARAMS, suggestion="Fix it",
                            available_windows=["Notepad"])
        assert result["available_windows"] == ["Notepad"]
        assert result["success"] is False

    def test_default_code_is_os_error(self):
        result = tool_error("generic fail")
        assert result["error_code"] == "OS_ERROR"


class TestToolSuccess:
    """Verify tool_success builds correct dicts."""

    def test_basic_success(self):
        result = tool_success("Done")
        assert result["success"] is True
        assert result["message"] == "Done"

    def test_success_without_message(self):
        result = tool_success()
        assert result["success"] is True
        assert "message" not in result

    def test_success_with_extras(self):
        result = tool_success("Clicked", x=100, y=200, confidence=0.95)
        assert result["x"] == 100
        assert result["y"] == 200
        assert result["confidence"] == 0.95
