from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw

from app.services.face_detector import FaceBox


def jpeg_to_rgb(jpeg_bytes: bytes) -> tuple[np.ndarray, int, int]:
    im = Image.open(BytesIO(jpeg_bytes)).convert("RGB")
    w, h = im.size
    arr = np.asarray(im, dtype=np.uint8)
    return arr, w, h


def clamp_int_box(x_min: float, y_min: float, x_max: float, y_max: float, width: int, height: int) -> tuple[int, int, int, int]:
    xi0 = int(max(0, min(width - 1, round(x_min))))
    yi0 = int(max(0, min(height - 1, round(y_min))))
    xi1 = int(max(0, min(width, round(x_max))))
    yi1 = int(max(0, min(height, round(y_max))))
    if xi1 <= xi0:
        xi1 = min(width, xi0 + 1)
    if yi1 <= yi0:
        yi1 = min(height, yi0 + 1)
    return xi0, yi0, xi1, yi1


def draw_box_on_rgb(rgb: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> bytes:
    im = Image.fromarray(rgb, mode="RGB")
    draw = ImageDraw.Draw(im)
    draw.rectangle([x0, y0, x1, y1], outline=(0, 255, 0), width=3)
    buf = BytesIO()
    im.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def annotate_jpeg_with_box(jpeg_bytes: bytes, box: FaceBox) -> tuple[bytes, tuple[int, int, int, int]]:
    rgb, w, h = jpeg_to_rgb(jpeg_bytes)
    x0, y0, x1, y1 = clamp_int_box(box.x_min, box.y_min, box.x_max, box.y_max, w, h)
    out = draw_box_on_rgb(rgb, x0, y0, x1, y1)
    return out, (x0, y0, x1, y1)
