"""Screen capture, OCR, template matching, pixel color, and window listing tools."""
from __future__ import annotations

from typing import Any

import mss
import numpy as np
from PIL import Image

from src.utils.image_utils import pil_to_base64, find_template
from src.utils.win32_helpers import enumerate_windows, get_window_rect_by_title, get_active_window_title
from src.utils.dpi import get_dpi_scale_factor
from src.security.masking import filter_windows, should_redact_window

# Cached RapidOCR engine — models load once, reuse across all calls
_ocr_engine = None
_OCR_MAX_DIMENSION = 1920  # Downscale images larger than this for faster OCR


def capture_screenshot(
    monitor: int = 0,
    region: dict[str, int] | None = None,
    blocked_apps: list[str] | None = None,
    window_title: str | None = None,
) -> dict[str, Any]:
    """Capture a screenshot and return as base64 PNG."""
    try:
        # Window-specific capture: find the window rect first
        if window_title and not region:
            rect = get_window_rect_by_title(window_title)
            if rect is None:
                return {
                    "success": False,
                    "error": f"No window found matching '{window_title}'",
                    "suggestion": "Use list_windows to see available window titles",
                }
            region = rect

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
            "dpi_scale": get_dpi_scale_factor(),
            "active_window": get_active_window_title(),
        }
    except Exception as e:
        return {"success": False, "error": str(e), "suggestion": "Try specifying a different monitor index or region"}


def _get_ocr_engine():
    """Get or create the cached RapidOCR engine (lazy singleton)."""
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
    return _ocr_engine


def _ocr_via_rapidocr(img_array: np.ndarray) -> list[dict[str, Any]]:
    """Run OCR using RapidOCR (ONNX Runtime). Fast, ~1-3 seconds."""
    engine = _get_ocr_engine()
    results, _ = engine(img_array)
    if not results:
        return []
    extracted = []
    for bbox, text, confidence in results:
        extracted.append({
            "text": text,
            "confidence": round(float(confidence), 3),
            "bbox": bbox,
        })
    return extracted


def _ocr_via_windows_native(img: Image.Image) -> list[dict[str, Any]]:
    """Fallback: Windows 10/11 native OCR via PowerShell + WinRT API. No pip packages needed."""
    import subprocess, tempfile, os, json as _json

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img.save(f, format="PNG")
        tmp_path = f.name.replace("\\", "\\\\")

    ps_script = f'''
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {{
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
}})[0]
Function Await($WinRtTask, $ResultType) {{
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}}
[Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder,Windows.Foundation,ContentType=WindowsRuntime] | Out-Null

$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync("{tmp_path}")) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
$ocrResult = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])

$lines = @()
foreach ($line in $ocrResult.Lines) {{
    $words = @()
    foreach ($word in $line.Words) {{
        $rect = $word.BoundingRect
        $words += @{{text=$word.Text; x=[int]$rect.X; y=[int]$rect.Y; w=[int]$rect.Width; h=[int]$rect.Height}}
    }}
    $lines += @{{text=$line.Text; words=$words}}
}}
$lines | ConvertTo-Json -Depth 4 -Compress
'''
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=30,
        )
        os.unlink(tmp_path)

        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError(result.stderr.strip() or "Windows OCR returned no output")

        raw = _json.loads(result.stdout.strip())
        # PowerShell returns a single object (not array) if only one line
        if isinstance(raw, dict):
            raw = [raw]

        extracted = []
        for line in raw:
            extracted.append({
                "text": line["text"],
                "confidence": 1.0,  # Windows OCR doesn't return confidence
                "bbox": None,
            })
        return extracted
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def ocr_extract_text(
    region: dict[str, int] | None = None,
    monitor: int = 0,
) -> dict[str, Any]:
    """Extract text from a screen region. Uses RapidOCR, falls back to Windows native OCR."""
    try:
        shot = capture_screenshot(monitor=monitor, region=region)
        if not shot["success"]:
            return shot

        import base64, io
        img_bytes = base64.b64decode(shot["image_base64"])
        img = Image.open(io.BytesIO(img_bytes))

        # Downscale large images for faster OCR
        max_dim = max(img.width, img.height)
        if max_dim > _OCR_MAX_DIMENSION:
            scale = _OCR_MAX_DIMENSION / max_dim
            img = img.resize(
                (int(img.width * scale), int(img.height * scale)),
                Image.LANCZOS,
            )

        img_array = np.array(img)

        # Try RapidOCR first (fast, ONNX-based)
        try:
            extracted = _ocr_via_rapidocr(img_array)
        except Exception:
            # Fallback to Windows native OCR
            extracted = _ocr_via_windows_native(img)

        full_text = " ".join(item["text"] for item in extracted)
        return {"success": True, "text": full_text, "details": extracted}
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "suggestion": "Install rapidocr-onnxruntime: pip install rapidocr-onnxruntime",
        }


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


def get_screen_info() -> dict[str, Any]:
    """Get essential screen context: dimensions, DPI scale, monitor count, active window."""
    try:
        with mss.mss() as sct:
            monitors = sct.monitors
            # monitors[0] is the virtual screen (all monitors combined)
            # monitors[1+] are individual monitors
            primary = monitors[1] if len(monitors) > 1 else monitors[0]

        return {
            "success": True,
            "primary_monitor": {
                "width": primary["width"],
                "height": primary["height"],
                "left": primary["left"],
                "top": primary["top"],
            },
            "monitor_count": len(monitors) - 1,  # exclude virtual screen
            "dpi_scale": get_dpi_scale_factor(),
            "active_window": get_active_window_title(),
        }
    except Exception as e:
        return {"success": False, "error": str(e), "suggestion": "This tool requires Windows"}


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
