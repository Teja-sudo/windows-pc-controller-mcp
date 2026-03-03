"""Screen capture, OCR, template matching, pixel color, and window listing tools."""
from __future__ import annotations

from typing import Any

import mss
import numpy as np
from PIL import Image

from src.utils.image_utils import pil_to_base64, find_template
from src.utils.win32_helpers import enumerate_windows
from src.security.masking import filter_windows, should_redact_window


def capture_screenshot(
    monitor: int = 0,
    region: dict[str, int] | None = None,
    blocked_apps: list[str] | None = None,
) -> dict[str, Any]:
    """Capture a screenshot and return as base64 PNG."""
    try:
        with mss.mss() as sct:
            if region:
                grab_area = {
                    "left": region["left"],
                    "top": region["top"],
                    "width": region["width"],
                    "height": region["height"],
                }
            else:
                monitors = sct.monitors
                idx = min(monitor, len(monitors) - 1)
                grab_area = monitors[idx]

            screenshot = sct.grab(grab_area)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        return {
            "success": True,
            "image_base64": pil_to_base64(img),
            "width": img.width,
            "height": img.height,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "suggestion": "Try specifying a different monitor index or region"}


def ocr_extract_text(
    region: dict[str, int] | None = None,
    monitor: int = 0,
) -> dict[str, Any]:
    """Extract text from a screen region using EasyOCR."""
    try:
        import easyocr

        shot = capture_screenshot(monitor=monitor, region=region)
        if not shot["success"]:
            return shot

        import base64, io
        img_bytes = base64.b64decode(shot["image_base64"])
        img_array = np.array(Image.open(io.BytesIO(img_bytes)))

        reader = easyocr.Reader(["en"], gpu=False)
        results = reader.readtext(img_array)

        extracted = []
        for bbox, text, confidence in results:
            extracted.append({
                "text": text,
                "confidence": round(confidence, 3),
                "bbox": bbox,
            })

        full_text = " ".join(item["text"] for item in extracted)
        return {"success": True, "text": full_text, "details": extracted}
    except Exception as e:
        return {"success": False, "error": str(e), "suggestion": "Ensure easyocr is installed: pip install easyocr"}


def find_on_screen(
    template_base64: str,
    threshold: float = 0.8,
    monitor: int = 0,
) -> dict[str, Any]:
    """Find where a template image appears on screen."""
    try:
        import cv2, base64, io

        shot = capture_screenshot(monitor=monitor)
        if not shot["success"]:
            return shot

        screen_bytes = base64.b64decode(shot["image_base64"])
        screen_img = np.array(Image.open(io.BytesIO(screen_bytes)))
        screen_bgr = cv2.cvtColor(screen_img, cv2.COLOR_RGB2BGR)

        tmpl_bytes = base64.b64decode(template_base64)
        tmpl_img = np.array(Image.open(io.BytesIO(tmpl_bytes)))
        tmpl_bgr = cv2.cvtColor(tmpl_img, cv2.COLOR_RGB2BGR)

        if tmpl_bgr.shape[0] > screen_bgr.shape[0] or tmpl_bgr.shape[1] > screen_bgr.shape[1]:
            return {"success": False, "error": "Template larger than screenshot", "suggestion": "Use a smaller template image"}

        matches = find_template(screen_bgr, tmpl_bgr, threshold)
        return {"success": True, "matches": matches, "count": len(matches)}
    except Exception as e:
        return {"success": False, "error": str(e), "suggestion": "Ensure template is a valid base64-encoded PNG image"}


def get_pixel_color(x: int, y: int) -> dict[str, Any]:
    """Get the RGB color of a pixel at screen coordinates."""
    try:
        with mss.mss() as sct:
            region = {"left": x, "top": y, "width": 1, "height": 1}
            pixel = sct.grab(region)
            r, g, b = pixel.pixel(0, 0)[:3]
        return {"success": True, "r": r, "g": g, "b": b, "hex": f"#{r:02x}{g:02x}{b:02x}"}
    except Exception as e:
        return {"success": False, "error": str(e), "suggestion": "Check that x,y coordinates are within screen bounds"}


def list_windows_tool(blocked_apps: list[str] | None = None) -> dict[str, Any]:
    """List all visible windows, filtering out blocked apps."""
    try:
        windows = enumerate_windows()
        if blocked_apps:
            windows = filter_windows(windows, blocked_apps)
        clean = [
            {"title": w["title"], "process": w["process_name"], "position": w["rect"]}
            for w in windows
        ]
        return {"success": True, "windows": clean, "count": len(clean)}
    except Exception as e:
        return {"success": False, "error": str(e), "suggestion": "This tool requires Windows"}
