# MyKad OCR Service

The in-house extraction service (SPEC.md §4). Receives a MyKad photo,
returns the field contract. Internal-only, zero-retention — see
[ADR-0001](../docs/adr/0001-in-house-ocr-no-third-party.md).

## API

### `POST /scan`

Multipart form, field `image` (JPEG/PNG, ≤ 8 MB by default).

```bash
curl -F "image=@card.jpg" http://localhost:8000/scan
```

Success → `200`:

```json
{
  "ok": true,
  "fields": {
    "name": "TAN AH KOW",
    "icNumber": "880101-14-5567",
    "gender": "M",
    "religion": null,
    "address": {
      "lines": ["NO 12 JALAN MAWAR 3", "TAMAN SRI MAWAR", "68000 AMPANG", "SELANGOR"],
      "postcode": "68000",
      "city": "AMPANG",
      "state": "SELANGOR"
    }
  },
  "confidence": { "icNumber": 0.99, "name": 0.94, "address": 0.88 }
}
```

Rejections: `200 {"ok": false, "reason": "NO_IC_FOUND"}` (readable image,
but no valid IC number — probably not a MyKad), `400 IMAGE_UNREADABLE`,
`413 IMAGE_TOO_LARGE`, `422` (missing `image` field).

### `GET /health`

`{"status": "ok"}` — for ops checks.

## Configuration

| Env var              | Default | Meaning                                  |
|----------------------|---------|------------------------------------------|
| `MYKAD_MAX_IMAGE_MB` | `8`     | Upload size limit                        |
| `MYKAD_WARMUP`       | `1`     | Load models at boot (`0` = on first use) |

## Deploy (Docker)

```bash
docker build -t mykad-ocr .
docker run -d --name mykad-ocr --restart unless-stopped -p 127.0.0.1:8000:8000 mykad-ocr
```

- The OCR models ship inside the RapidOCR package — the container needs **no
  internet at runtime**, and the image stays small (a few hundred MB).
- `-p 127.0.0.1:8000:8000` binds to localhost only — right when the Laravel
  apps live on the same server. If they're on other machines, bind to the
  internal interface and firewall the port. **Never expose it publicly**; the
  service has no auth by design — the per-project Scan Proxies are the front
  door.

## Zero-retention (binding, see CONTEXT.md)

- Images are processed in memory; nothing is written to disk.
- Access logs contain method/path/status only — never bodies or field values.
- Keep it this way in every change.

## Development

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt   # unit + API tests, no OCR engine needed
pytest

pip install -r requirements.txt pillow  # adds the real-model integration test
pytest
```

Layout: `app/mykad.py` holds all field-parsing rules (pure Python — this is
where accuracy tuning happens), `app/preprocess.py` card crop/deskew,
`app/ocr_engine.py` the RapidOCR (ONNX Runtime) adapter, `app/pipeline.py` glues them,
`app/main.py` the HTTP layer.
