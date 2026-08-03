"""End-to-end pipeline test with a synthetic card and the real OCR model.

Skipped automatically when paddleocr or Pillow is not installed — the unit
tests cover the logic; this one proves the real pipeline wiring. Uses only
invented data.
"""

import io

import pytest

paddleocr = pytest.importorskip("paddleocr")
PIL = pytest.importorskip("PIL")

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _font(size):
    for path in FONTS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    pytest.skip("no TrueType font available for rendering the test card")


def synthetic_card_bytes():
    w, h = 1030, 650
    img = Image.new("RGB", (w, h), (205, 225, 240))
    d = ImageDraw.Draw(img)
    d.text((40, 28), "KAD PENGENALAN", font=_font(34), fill=(20, 40, 90))
    d.text((40, 68), "MALAYSIA", font=_font(30), fill=(20, 40, 90))
    d.text((40, 130), "900215-08-6113", font=_font(46), fill=(10, 10, 40))
    d.rectangle([700, 150, 960, 480], fill=(160, 175, 195))
    y = 300
    for line in ("MUHAMMAD AIMAN BIN", "ABDULLAH"):
        d.text((40, y), line, font=_font(34), fill=(10, 10, 40))
        y += 44
    y += 20
    for line in ("LOT 88 KAMPUNG PADANG", "34000 TAIPING", "PERAK"):
        d.text((40, y), line, font=_font(30), fill=(10, 10, 40))
        y += 40
    d.text((760, 500), "ISLAM", font=_font(30), fill=(10, 10, 40))
    d.text((760, 545), "WARGANEGARA", font=_font(26), fill=(10, 10, 40))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def test_scan_image_end_to_end():
    from app.pipeline import scan_image

    result = scan_image(synthetic_card_bytes())
    assert result["ok"] is True
    f = result["fields"]
    assert f["icNumber"] == "900215-08-6113"
    assert f["name"] == "MUHAMMAD AIMAN BIN ABDULLAH"
    assert f["gender"] == "M"
    assert f["religion"] == "ISLAM"
    assert f["address"]["postcode"] == "34000"
    assert f["address"]["city"] == "TAIPING"
    assert f["address"]["state"] == "PERAK"
    assert result["confidence"]["icNumber"] > 0.5


def test_garbage_bytes_rejected():
    from app.pipeline import scan_image

    assert scan_image(b"not an image") == {"ok": False,
                                           "reason": "IMAGE_UNREADABLE"}
