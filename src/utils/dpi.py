"""DPI awareness initialization and scale factor retrieval for Windows.

This module MUST be imported early (before any screen/mouse operations) to set
the process DPI awareness mode.  Without it, `mss` screenshots and `pynput`
mouse coordinates use different coordinate systems at non-100% scaling.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes


# ---------------------------------------------------------------------------
# Set DPI awareness at import time
# ---------------------------------------------------------------------------

def _set_dpi_awareness() -> None:
    """Set process DPI awareness to Per-Monitor v2 (best), with fallbacks."""
    try:
        # Per-Monitor v2 (Windows 10 1703+)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            # System-aware fallback (Windows 8.1+)
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            try:
                # Legacy fallback (Windows Vista+)
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass  # Running on non-Windows or very old Windows


_set_dpi_awareness()


# ---------------------------------------------------------------------------
# Scale factor query
# ---------------------------------------------------------------------------

def get_dpi_scale_factor() -> float:
    """Return the system DPI scale factor (e.g. 1.0, 1.25, 1.5, 2.0).

    Uses GetDpiForSystem (Windows 10+), falls back to GetDeviceCaps.
    Returns 1.0 if the DPI cannot be determined.
    """
    try:
        dpi = ctypes.windll.user32.GetDpiForSystem()
        return round(dpi / 96.0, 4)
    except (AttributeError, OSError):
        pass

    # Fallback via GetDeviceCaps on the desktop DC
    try:
        hdc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
        ctypes.windll.user32.ReleaseDC(0, hdc)
        return round(dpi / 96.0, 4)
    except (AttributeError, OSError):
        return 1.0
