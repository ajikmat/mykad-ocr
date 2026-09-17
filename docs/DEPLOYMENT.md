# Deployment runbook (staging / production)

Three deployments, **in this order** — service first, backend route second,
frontend last — so the scan button never points at an endpoint that doesn't
exist yet.

## 1. OCR Service → the Linux server

Only the `service/` folder goes to the server — the rest of the monorepo
(packages, examples, benchmark) is never deployed there. Quick way:

```bash
scp -r ocr/service user@server:~/mykad-ocr
```

`~/mykad-ocr` on the server is therefore just `Dockerfile` + `app/` +
`requirements.txt`, and the `docker build` below runs against that.

(Long-term: push this repo to Azure DevOps and `git clone` on the server
instead, so the server can pull updates.)

On the server:

```bash
# one-time, if Docker isn't installed
curl -fsSL https://get.docker.com | sh

cd ~/mykad-ocr
docker build -t mykad-ocr .
docker run -d --name mykad-ocr --restart unless-stopped \
    -p 127.0.0.1:8000:8000 mykad-ocr
curl http://127.0.0.1:8000/health    # → {"status":"ok"}
```

Binding/firewall rules and the reasoning are in
[service/README.md](../service/README.md) — short version: localhost-only
when the Laravel apps share the server; internal interface + firewall when
they don't; **never** public.

Updating to a new version later:

```bash
cd ~/mykad-ocr && git pull   # or re-scp
docker build -t mykad-ocr . && docker rm -f mykad-ocr
docker run -d --name mykad-ocr --restart unless-stopped \
    -p 127.0.0.1:8000:8000 mykad-ocr
```

## 2. Scan Proxy → each Laravel backend

Follow [examples/laravel-proxy/README.md](../examples/laravel-proxy/README.md):
controller + route (+ `throttle` for anonymous-user projects), the
`services.mykad_ocr` config entry, and `MYKAD_OCR_URL=http://127.0.0.1:8000`
in the environment, then `php artisan config:clear`.

Sanity check from anywhere that can reach the staging API:

```bash
curl -X POST https://staging-api.example/scan-mykad -F "image=@card.jpg"
```

## 3. Frontend → normal CI

Commit and push; the pipeline builds as usual (the `local_modules/*.tgz`
packages are committed, so CI's `npm install` needs nothing extra).

Checklist:

- `VITE_MYKAD_SCAN_URL` must **not** be set in CI/staging/production env —
  its absence makes the scanner fall back to
  `VITE_APP_BACKEND_URL + '/scan-mykad'` (the real Scan Proxy).
- The site must be HTTPS, or browsers won't open the camera.

## First day on staging

Open the page on a real phone and scan a real MyKad — if the accuracy gate
(`benchmark/`) hasn't been run with real cards yet, this is the moment the
project meets reality. Auto-capture tuning knobs live in
`packages/core/src/detect.ts` (`DETECT`).
