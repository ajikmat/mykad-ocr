"""The scan pipeline: bytes in, SPEC.md §3 field contract out.
The image lives only in memory for the duration of this call and is never
persisted or logged (Zero-retention, CONTEXT.md).
"""
import cv2

from . import mykad, preprocess
from .ocr_engine import get_engine

# Cap the longest image side before OCR. Detection cost scales with pixel
# area, so phone photos (3000-4000px) are 2-4x slower for no accuracy gain
# on MyKad-sized text.
MAX_SIDE = 1280


def _downscale(img):
    h, w = img.shape[:2]
    scale = MAX_SIDE / max(h, w)
    if scale < 1:
        img = cv2.resize(img, None, fx=scale, fy=scale,
                         interpolation=cv2.INTER_AREA)
    return img


def scan_image(data: bytes) -> dict:
    img = preprocess.decode(data)
    if img is None:
        return {"ok": False, "reason": "IMAGE_UNREADABLE"}
    img = preprocess.normalize(img)
    img = _downscale(img)
    boxes = get_engine().run(img)
    fields, confidence = mykad.parse_fields(boxes)
    if fields["icNumber"] is None:
        return {"ok": False, "reason": "NO_IC_FOUND"}
    return {"ok": True, "fields": fields, "confidence": confidence}