"""The scan pipeline: bytes in, SPEC.md §3 field contract out.

The image lives only in memory for the duration of this call and is never
persisted or logged (Zero-retention, CONTEXT.md).
"""

from . import mykad, preprocess
from .ocr_engine import get_engine


def scan_image(data: bytes) -> dict:
    img = preprocess.decode(data)
    if img is None:
        return {"ok": False, "reason": "IMAGE_UNREADABLE"}

    img = preprocess.normalize(img)
    boxes = get_engine().run(img)
    fields, confidence = mykad.parse_fields(boxes)

    if fields["icNumber"] is None:
        return {"ok": False, "reason": "NO_IC_FOUND"}
    return {"ok": True, "fields": fields, "confidence": confidence}
