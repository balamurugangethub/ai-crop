"""Image validation and quality checks before the model sees an image."""
import io

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from . import config

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class ImageRejected(Exception):
    """Raised with a machine-readable code that the frontend translates."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code)
        self.code = code
        self.detail = detail


def load_and_check(data: bytes) -> tuple[Image.Image, dict]:
    if not data:
        raise ImageRejected("empty_file")
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise ImageRejected("file_too_large", f"max {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        img.load()
    except (UnidentifiedImageError, OSError):
        raise ImageRejected("not_an_image")
    if fmt not in ALLOWED_FORMATS:
        raise ImageRejected("unsupported_format", str(fmt))
    img = ImageOps.exif_transpose(img).convert("RGB")
    w, h = img.size
    if min(w, h) < config.MIN_IMAGE_SIDE:
        raise ImageRejected("too_small", f"{w}x{h}")

    # Quality metrics on a downscaled grey copy
    small = img.copy()
    small.thumbnail((512, 512))
    arr = np.asarray(small)
    grey = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    sharpness = float(cv2.Laplacian(grey, cv2.CV_64F).var())
    brightness = float(grey.mean())
    quality = {"width": w, "height": h, "sharpness": round(sharpness, 1),
               "brightness": round(brightness, 1)}
    if brightness < 25:
        raise ImageRejected("too_dark")
    if brightness > 240:
        raise ImageRejected("too_bright")
    if sharpness < config.BLUR_THRESHOLD:
        raise ImageRejected("too_blurry")
    return img, quality
