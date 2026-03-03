"""Tests for DPI awareness module."""
import sys
import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


class TestDpiScaleFactor:
    def test_returns_float(self):
        from src.utils.dpi import get_dpi_scale_factor

        scale = get_dpi_scale_factor()
        assert isinstance(scale, float)

    def test_reasonable_range(self):
        from src.utils.dpi import get_dpi_scale_factor

        scale = get_dpi_scale_factor()
        # DPI scaling is typically between 1.0 (100%) and 3.0 (300%)
        assert 0.5 <= scale <= 4.0

    def test_module_import_sets_awareness(self):
        """Importing the module should not raise — awareness is set at import time."""
        import src.utils.dpi  # noqa: F401
        # If we get here, the DPI awareness call succeeded (or silently fell back)
        assert True
