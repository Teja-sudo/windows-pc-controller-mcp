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

    def test_filters_by_process_name_key(self):
        """Regression: enumerate_windows uses 'process_name', not 'process'."""
        from src.security.masking import filter_windows

        windows = [
            {"title": "My Vault", "process_name": "1password.exe"},
            {"title": "Notepad", "process_name": "notepad.exe"},
        ]
        filtered = filter_windows(windows, blocked_apps=["1password"])
        assert len(filtered) == 1
        assert filtered[0]["title"] == "Notepad"

    def test_filters_by_both_process_key_variants(self):
        """Handles dicts with either 'process' or 'process_name' key."""
        from src.security.masking import filter_windows

        windows = [
            {"title": "Vault", "process": "bitwarden.exe"},
            {"title": "Editor", "process_name": "code.exe"},
        ]
        filtered = filter_windows(windows, blocked_apps=["bitwarden"])
        assert len(filtered) == 1
        assert filtered[0]["title"] == "Editor"


class TestTextRedaction:
    def test_redacts_blocked_app_text(self):
        from src.security.masking import should_redact_window

        assert should_redact_window("1Password - Vault", blocked_apps=["1Password"]) is True

    def test_allows_normal_app(self):
        from src.security.masking import should_redact_window

        assert should_redact_window("Notepad", blocked_apps=["1Password"]) is False
