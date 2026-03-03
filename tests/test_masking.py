import pytest


class TestWindowFilter:
    def test_filters_blocked_apps(self):
        from src.security.masking import filter_windows

        windows = [
            {"title": "My Document - Notepad", "process": "notepad.exe"},
            {"title": "1Password", "process": "1password.exe"},
            {"title": "Chrome", "process": "chrome.exe"},
        ]
        filtered = filter_windows(windows, blocked_apps=["1Password"])
        assert len(filtered) == 2
        assert all(w["title"] != "1Password" for w in filtered)

    def test_no_blocked_apps_returns_all(self):
        from src.security.masking import filter_windows

        windows = [
            {"title": "Notepad", "process": "notepad.exe"},
        ]
        filtered = filter_windows(windows, blocked_apps=[])
        assert len(filtered) == 1


class TestTextRedaction:
    def test_redacts_blocked_app_text(self):
        from src.security.masking import should_redact_window

        assert should_redact_window("1Password - Vault", blocked_apps=["1Password"]) is True

    def test_allows_normal_app(self):
        from src.security.masking import should_redact_window

        assert should_redact_window("Notepad", blocked_apps=["1Password"]) is False
