# MyKad Scan-to-Fill

Scan a MyKad with the browser camera, extract the fields in-house, pre-fill
a form the user reviews and corrects. Built for reuse across Vue, React,
and Laravel projects. **Not** eKYC — no liveness, no face match.

Start here: [SPEC.md](SPEC.md) (architecture and contracts),
[CONTEXT.md](CONTEXT.md) (vocabulary),
[docs/adr/](docs/adr/) (why there's no third-party AI — PDPA).

## Repo map

| Path | What |
|------|------|
| `service/` | The OCR Service — FastAPI + PaddleOCR, Docker, internal-only, zero-retention |
| `packages/core/` | `mykad-scan-core` — camera, guided auto-capture, upload fallback (framework-agnostic) |
| `packages/vue/` | `mykad-scan-vue` — Vue 3 component wrapper |
| `packages/react/` | `mykad-scan-react` — React component wrapper |
| `examples/laravel-proxy/` | The Scan Proxy each consuming project adds to its backend |
| `examples/demo/` | Runnable demo: scanner + review form + proxy, wired to the real service |
| `benchmark/` | Phase 0 accuracy benchmark — run this with ~20 real (consented) card photos |

## Try it locally

```bash
# 1. OCR service (needs Python 3.10+; first install is large)
cd service && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

```bash
# 2. Build packages and start the demo (new terminal, repo root)
npm install && npm run build
python3 examples/demo/serve.py --port 5173
# open http://localhost:5173/examples/demo/
```

## Deploy / integrate

- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** — the staging/production
  runbook: OCR container on the Linux server → Laravel Scan Proxy route →
  frontend CI, in that order.
- **[docs/INTEGRATION.md](docs/INTEGRATION.md)** — how to wire a consuming
  project end to end (tarball install, drawer component pattern, dev proxy
  for local testing), with `smart-amil-fe-public` as the worked example.

Short version:

1. **Server:** `docker build -t mykad-ocr service/`, run internal-only —
   [service/README.md](service/README.md).
2. **Backend:** add the Scan Proxy route to each Laravel project —
   [examples/laravel-proxy/](examples/laravel-proxy/README.md).
3. **Frontend:** install `mykad-scan-vue` or `mykad-scan-react`, point it at
   the Scan Proxy, build your Review-and-Correct form from the result.

```vue
<MykadScanner proxy-url="/api/scan-mykad" @result="fill" />
```

```tsx
<MykadScanner proxyUrl="/api/scan-mykad" onResult={fill} />
```

Packages are not yet published to a registry — install via the monorepo
(npm workspaces), a private registry, or git URL, whichever the team adopts.

## Status / open items

- **First consumer integrated:** `smart-amil-fe-public` (ZakatFitrahView) —
  scanner verified live against the local OCR service; its Laravel backend
  still needs the `/scan-mykad` route before staging works end to end. The
  old tesseract.js OCR there was removed.
- **Real-photo accuracy gate not yet run** — everything is verified on
  synthetic cards. Run `benchmark/` with ~20 consented colleague photos
  before rollout; tune `service/app/mykad.py` + `preprocess.py` with what
  it finds.
- Auto-capture thresholds (`packages/core/src/detect.ts`, exported as
  `DETECT`) are untested on real phones — tune on a cheap Android.
- Dockerfile written but first built on the target server.
- Packages installed via committed tarballs for now; a private npm registry
  (e.g. Verdaccio) is the long-term plan.
