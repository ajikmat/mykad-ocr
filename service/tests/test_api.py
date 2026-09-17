"""API surface tests — the OCR pipeline is stubbed, no models needed."""

import os

os.environ["MYKAD_WARMUP"] = "0"  # must be set before importing the app

from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402

OK_RESULT = {
    "ok": True,
    "fields": {"name": "TAN AH KOW", "icNumber": "880101-14-5567",
               "gender": "M", "religion": None,
               "address": {"lines": [], "postcode": None, "city": None,
                           "state": None}},
    "confidence": {"icNumber": 0.99, "name": 0.94},
}


def post_image(client, data=b"fakejpegbytes"):
    return client.post("/scan", files={"image": ("card.jpg", data,
                                                 "image/jpeg")})


def test_health():
    client = TestClient(main.app)
    assert client.get("/health").json() == {"status": "ok"}


def test_scan_success(monkeypatch):
    monkeypatch.setattr(main, "_scan_impl", lambda data: OK_RESULT)
    r = post_image(TestClient(main.app))
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["fields"]["icNumber"] == "880101-14-5567"


def test_scan_rejection_is_200_with_reason(monkeypatch):
    monkeypatch.setattr(main, "_scan_impl",
                        lambda data: {"ok": False, "reason": "NO_IC_FOUND"})
    r = post_image(TestClient(main.app))
    assert r.status_code == 200
    assert r.json() == {"ok": False, "reason": "NO_IC_FOUND"}


def test_unreadable_image_is_400(monkeypatch):
    monkeypatch.setattr(main, "_scan_impl",
                        lambda data: {"ok": False,
                                      "reason": "IMAGE_UNREADABLE"})
    r = post_image(TestClient(main.app))
    assert r.status_code == 400


def test_oversize_image_is_413(monkeypatch):
    monkeypatch.setattr(main, "MAX_IMAGE_MB", 0.000001)
    monkeypatch.setattr(main, "_scan_impl", lambda data: OK_RESULT)
    r = post_image(TestClient(main.app), data=b"x" * 100)
    assert r.status_code == 413
    assert r.json()["reason"] == "IMAGE_TOO_LARGE"


def test_missing_image_field_is_422():
    client = TestClient(main.app)
    assert client.post("/scan").status_code == 422


def test_pipeline_crash_is_json_500(monkeypatch):
    def boom(data):
        raise RuntimeError("unexpected")
    monkeypatch.setattr(main, "_scan_impl", boom)
    r = post_image(TestClient(main.app))
    assert r.status_code == 500
    assert r.json() == {"ok": False, "reason": "INTERNAL_ERROR"}
