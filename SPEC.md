# MyKad Scan-to-Fill — Specification

Terms in **bold capitals** are defined in [CONTEXT.md](CONTEXT.md). The foundational
constraint — no third-party processing of card images — is recorded in
[ADR-0001](docs/adr/0001-in-house-ocr-no-third-party.md).

## 1. What this is

**Scan-to-Fill**: a user opens the camera in a web browser, frames their MyKad,
the fields are extracted by an in-house **OCR Service**, and the host project's
form is pre-filled. The user always confirms and can edit every field on the
project's own **Review-and-Correct screen** before anything is submitted.

Not in scope: identity verification (eKYC), liveness, face matching, fraud
detection, card-type classification, reading the card's chip.

## 2. Architecture

```
Browser (Vue/React app)
│  mykad-scan-vue / mykad-scan-react  (thin wrappers)
│  mykad-scan-core                    (camera, auto-capture, upload fallback, API client)
│
▼  POST /api/scan-mykad  (image, same-origin)
Project's Laravel backend — SCAN PROXY
│  auth or throttle · size cap · forwards image
│
▼  POST http://<internal>:8000/scan   (never exposed to the internet)
OCR SERVICE (Docker, Python)
   PaddleOCR + MyKad layout post-processing
   in-memory only — ZERO-RETENTION
```

Three deliverables, one repo (monorepo):

```
/
├── packages/
│   ├── core/        mykad-scan-core   (TypeScript, framework-agnostic)
│   ├── vue/         mykad-scan-vue    (thin wrapper component)
│   └── react/       mykad-scan-react  (thin wrapper component)
├── service/         OCR Service       (Python, Dockerfile)
├── examples/
│   └── laravel-proxy/                 reference Scan Proxy implementation
├── CONTEXT.md
├── SPEC.md
└── docs/adr/
```

## 3. The field contract

The one schema every layer agrees on. Additive changes only — fields are never
renamed or repurposed once a project consumes them.

```json
{
  "ok": true,
  "fields": {
    "name": "TAN AH KOW",
    "icNumber": "880101-14-5567",
    "gender": "M",
    "religion": "ISLAM",
    "address": {
      "lines": ["NO 12 JALAN MAWAR 3", "TAMAN SRI MAWAR", "68000 AMPANG", "SELANGOR"],
      "postcode": "68000",
      "city": "AMPANG",
      "state": "SELANGOR"
    }
  },
  "confidence": { "name": 0.94, "icNumber": 0.99, "address": 0.81 }
}
```

Rejection (not-a-card / unreadable):

```json
{ "ok": false, "reason": "NO_IC_FOUND" }
```

Field rules (from CONTEXT.md):

| Field       | Rule |
|-------------|------|
| `name`      | Romanized name only; wrapped lines joined; Chinese-script line dropped via script detection. |
| `icNumber`  | 12 digits, validated: first 6 form a real date, middle 2 a known place-of-birth code. Returned formatted `XXXXXX-XX-XXXX`. |
| `gender`    | Derived, never OCR'd: last IC digit odd = `"M"`, even = `"F"`. |
| `religion`  | `"ISLAM"` or `null`. Never inferred from absence. |
| `address`   | Raw `lines` always; `postcode` (5-digit pattern), `state` (closed list of 16), `city` (remainder of postcode line) best-effort, `null` when unparseable. |

**Accepted cards**: anything that parses — MyKad, pre-2012 designs, MyPR,
MyTentera. Rejection means exactly one thing: no valid IC number found.

## 4. OCR Service

Python (FastAPI) + PaddleOCR, one Docker image, CPU-only.

### API

- `POST /scan` — multipart image (JPEG/PNG, ≤ 8 MB). Returns the field contract.
- `GET /health` — liveness for ops.

### Pipeline

1. **Preprocess** — decode, downscale to working resolution, locate the card
   rectangle, perspective-correct (deskew) and crop to the card.
2. **OCR** — PaddleOCR detection + recognition over the corrected crop.
3. **Layout mapping** — assign text boxes to MyKad regions by relative position
   (IC number top-left, name/address block lower-left, ISLAM right side under photo).
4. **Field parsing** — the rules in §3: IC validation, gender derivation,
   name line joining + script filter, address parse, religion detection.
5. **Respond** — fields + per-field confidence, or `NO_IC_FOUND`.

### Zero-retention (binding)

- Image bytes live in memory only; no temp files, no disk writes.
- Access logs must not contain request bodies or extracted values.
- The only accuracy signal kept is what consuming projects choose to send
  separately: per-field correction counts (no values, no images).

### Deployment

```bash
docker build -t mykad-ocr ./service
docker run -d --name mykad-ocr --restart unless-stopped -p 8000:8000 mykad-ocr
```

Bind to the internal interface / firewall so port 8000 is reachable only from
the Laravel apps on the same server or network. No public exposure, ever.

## 5. Capture Library

### `mykad-scan-core` (framework-agnostic)

```ts
const scanner = createMykadScanner({
  proxyUrl: "/api/scan-mykad",      // the project's Scan Proxy
  onResult: (fields) => { ... },    // the field contract's `fields`
  onReject: (reason) => { ... },    // NO_IC_FOUND → "try again" UI
  onError:  (err)    => { ... },    // camera denied, network, server down
});
scanner.mount(containerEl);         // renders viewfinder UI
scanner.destroy();
```

Responsibilities:

- **Camera**: `getUserMedia` with rear-camera preference; requires HTTPS.
- **Guided Auto-capture**: card-shaped frame overlay; low-res edge/contour
  detection per frame; when a card-sized rectangle fills the guide and holds
  steady for ~1 s, capture automatically. Manual shutter button always visible.
  No client-side "is it a MyKad" model — rejection is the OCR Service's job.
- **Upload Fallback**: always-visible "upload a photo instead" using
  `<input type="file" accept="image/*" capture>`; same pipeline.
- **Client-side prep**: crop to guide frame, JPEG-compress to ≤ ~1 MB upload.
- No OCR, no field logic, no storage in the browser beyond the in-flight request.

### Wrappers

`mykad-scan-vue` and `mykad-scan-react` are ~100-line components that mount the
core and translate callbacks into idiomatic events/props:

```vue
<MykadScanner proxy-url="/api/scan-mykad" @result="fill" @reject="retry" />
```

```tsx
<MykadScanner proxyUrl="/api/scan-mykad" onResult={fill} onReject={retry} />
```

All fixes land in core; wrappers change only when the public API does.

## 6. Scan Proxy (per consuming project, Laravel)

One route added to each project's own backend — reference implementation ships
in `examples/laravel-proxy/`:

```php
Route::post('/api/scan-mykad', ScanMykadController::class)
    ->middleware(['throttle:10,1']);   // or 'auth' where users are logged in
```

- Validates content type and size (≤ 8 MB), forwards to the internal OCR
  Service, streams the JSON response back unchanged.
- Anonymous-user project: IP throttle + origin check instead of auth.
- Never logs the image. Same-origin, so no CORS configuration anywhere.

## 7. Build order

**Phase 0 — accuracy spike (do this before anything else).**
Collect ~20 volunteer MyKad photos across phones/lighting/card ages. Run them
through a throwaway PaddleOCR script. Gate: IC number ≥ 95% exact, name ≥ 85%
exact — comfortably achievable given the Review-and-Correct backstop. If the
gate fails, tune preprocessing or evaluate alternative in-house engines
*before* any real code exists. This is the project's only real technical risk;
spend the first week here.

**Phase 1 — OCR Service.** Full pipeline + tests against the Phase 0 image set
(the images stay on dev machines, not in the repo). Dockerize; DevOps deploys
to the Linux server internally.

**Phase 2 — core + pilot.** `mykad-scan-core`, integrated into ONE pilot
project (pick the anonymous one — it's the hardest case: throttling, no auth).
Ship the Laravel proxy reference alongside.

**Phase 3 — wrappers + rollout.** Vue and React wrappers, publish packages
(private npm registry or Git-based install — to be decided), roll out to the
remaining projects with the correction-count telemetry hook if adopted.

## 8. Risks

| Risk | Mitigation |
|------|------------|
| PaddleOCR accuracy below gate on real cards | Phase 0 spike before committing; layout post-processing and IC validation recover many raw-OCR errors |
| Low-end Android performance in auto-capture | Detection runs on downscaled frames; manual shutter and Upload Fallback always available |
| Anonymous endpoint abuse | Throttle + size cap + origin check; worst case is wasted CPU, no data exposure |
| Server outage takes scan down for all projects | Feature degrades to normal manual form entry — Scan-to-Fill is an accelerator, never a gate |
| Schema drift across three consuming projects | Additive-only contract (§3); versioned packages |
