"""MyKad OCR Service — internal-only HTTP API (SPEC.md §4).

POST /scan   multipart image → field contract JSON
GET  /health liveness

Deployment note: this service must never be exposed to the internet.
Consuming projects reach it through their own Scan Proxy endpoints.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

MAX_IMAGE_MB = float(os.environ.get("MYKAD_MAX_IMAGE_MB", "8"))

log = logging.getLogger("mykad")

# Lazily bound so unit tests can run without paddle/cv2 installed
_scan_impl = None


def _get_scan_impl():
    global _scan_impl
    if _scan_impl is None:
        from .pipeline import scan_image
        _scan_impl = scan_image
    return _scan_impl


@asynccontextmanager
async def lifespan(app):
    # Load OCR models at boot AND run one dummy inference, so the first
    # real user doesn't pay the model-load + kernel-JIT cost.
    # MYKAD_WARMUP=0 skips this (used by tests).
    if os.environ.get("MYKAD_WARMUP", "1") != "0":
        from .ocr_engine import get_engine
        engine = get_engine()
        try:
            import numpy as np
            engine.run(np.full((650, 1030, 3), 255, dtype=np.uint8))
        except Exception:
            log.exception("warmup inference failed")
    yield


app = FastAPI(title="MyKad OCR Service", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


# sync endpoint on purpose: FastAPI runs it in a worker thread, so the
# CPU-bound OCR call does not block the event loop
@app.post("/scan")
def scan(image: UploadFile = File(...)):
    data = image.file.read()
    if len(data) > MAX_IMAGE_MB * 1024 * 1024:
        return JSONResponse({"ok": False, "reason": "IMAGE_TOO_LARGE"},
                            status_code=413)
    try:
        result = _get_scan_impl()(data)
    except Exception:
        # log the traceback only — never the image or extracted values
        log.exception("scan pipeline failed")
        return JSONResponse({"ok": False, "reason": "INTERNAL_ERROR"},
                            status_code=500)
    if not result["ok"] and result["reason"] == "IMAGE_UNREADABLE":
        return JSONResponse(result, status_code=400)
    return result
