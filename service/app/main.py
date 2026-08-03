"""MyKad OCR Service — internal-only HTTP API (SPEC.md §4).

POST /scan   multipart image → field contract JSON
GET  /health liveness

Deployment note: this service must never be exposed to the internet.
Consuming projects reach it through their own Scan Proxy endpoints.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

MAX_IMAGE_MB = float(os.environ.get("MYKAD_MAX_IMAGE_MB", "8"))

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
    # Load OCR models at boot instead of on the first request.
    # MYKAD_WARMUP=0 skips this (used by tests).
    if os.environ.get("MYKAD_WARMUP", "1") != "0":
        from .ocr_engine import get_engine
        get_engine()
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
    result = _get_scan_impl()(data)
    if not result["ok"] and result["reason"] == "IMAGE_UNREADABLE":
        return JSONResponse(result, status_code=400)
    return result
