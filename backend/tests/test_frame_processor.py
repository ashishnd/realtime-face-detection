import io

from PIL import Image

from app.services import frame_processor
from app.services.face_detector import FaceBox


def test_clamp_box():
    x0, y0, x1, y1 = frame_processor.clamp_int_box(-10, -10, 1000, 1000, 100, 80)
    assert 0 <= x0 < 100
    assert 0 <= y0 < 80
    assert x0 < x1 <= 100
    assert y0 < y1 <= 80


def test_annotate_jpeg_with_box():
    im = Image.new("RGB", (32, 24), color=(10, 20, 30))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=90)
    jpeg = buf.getvalue()
    box = FaceBox(x_min=2, y_min=2, x_max=20, y_max=18, confidence=0.9)
    out, ints = frame_processor.annotate_jpeg_with_box(jpeg, box)
    assert isinstance(out, bytes)
    assert out.startswith(b"\xff\xd8")
    assert len(ints) == 4


def test_jpeg_to_rgb():
    im = Image.new("RGB", (10, 12), color=(1, 2, 3))
    buf = io.BytesIO()
    im.save(buf, format="JPEG")
    rgb, w, h = frame_processor.jpeg_to_rgb(buf.getvalue())
    assert w == 10 and h == 12
    assert rgb.mode == "RGB"
    assert rgb.size == (10, 12)
