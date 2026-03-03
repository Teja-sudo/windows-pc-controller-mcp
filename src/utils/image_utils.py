"""Image processing helpers for screenshots and template matching."""
from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image


def pil_to_base64(image: Image.Image, format: str = "PNG") -> str:
    """Convert a PIL Image to a base64-encoded string."""
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def base64_to_pil(b64_string: str) -> Image.Image:
    """Convert a base64 string back to a PIL Image."""
    raw = base64.b64decode(b64_string)
    return Image.open(io.BytesIO(raw))


def find_template(
    screenshot: np.ndarray,
    template: np.ndarray,
    threshold: float = 0.8,
) -> list[dict[str, int]]:
    """Find all locations where template appears in screenshot."""
    import cv2

    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= threshold)

    matches = []
    h, w = template.shape[:2]
    for pt in zip(*locations[::-1]):
        matches.append({
            "x": int(pt[0]),
            "y": int(pt[1]),
            "width": w,
            "height": h,
            "confidence": float(result[pt[1], pt[0]]),
        })
    return matches
