# Integrating a consuming project

The worked example: `smart-amil-fe-public` (Vue 3 + Laravel API, anonymous
users). Steps below are what was actually done there — copy the pattern.

## 1. Install the packages (no registry yet)

From this repo, pack the tarballs straight into the consuming project:

```bash
npm run build
npm pack -w mykad-scan-core -w mykad-scan-vue \
    --pack-destination ../your-project/local_modules
```

In the consuming project (installs both at once — the wrapper needs core):

```bash
npm install ./local_modules/mykad-scan-core-0.1.0.tgz \
            ./local_modules/mykad-scan-vue-0.1.0.tgz
```

Commit `local_modules/` — that's what makes CI work with `file:` deps.
React projects: same, with `mykad-scan-react`.

When a private npm registry exists (e.g. Verdaccio in Docker), publish the
three packages once and replace this with normal installs.

## 2. Wrap the scanner in a small component

Pattern used in smart-amil
(`src/components/shared/MykadScanInput.vue`): a camera-icon button that
opens a full-screen Drawer/modal containing `<MykadScanner>`, with labels
in Malay, emitting `result` and closing on success. Key detail — mount the
scanner with `v-if="visible"` so the camera starts when the drawer opens
and stops when it closes.

Endpoint resolution, dev-vs-prod:

```js
const proxyUrl = import.meta.env.VITE_MYKAD_SCAN_URL
    || `${import.meta.env.VITE_APP_BACKEND_URL}/scan-mykad`;
```

## 3. Wire the result into the form

- **IC number:** strip to digits — `fields.icNumber.replace(/\D/g, '')` —
  if the input is a 12-digit masked field.
- **Name:** fill, but never overwrite user edits after the fact.
- Show the scan button only where it makes sense (smart-amil: only when
  card type is "Awam" — scanning a MyKad into a passport field is wrong).
- The library returns more than most forms need (religion, address parts);
  take only what the form has — that's the intended design.

## 4. Local dev against the local OCR service

Vite dev proxy (in `vite.config.js`) plays the Scan Proxy role so the FE
can be developed with no Laravel at all:

```js
server: {
    proxy: {
        '/api/scan-mykad': {
            target: 'http://127.0.0.1:8000',
            rewrite: () => '/scan',
        },
    },
},
```

Plus a git-ignored `.env.local`:

```
VITE_MYKAD_SCAN_URL=/api/scan-mykad
```

Run the OCR service locally (`uvicorn app.main:app --port 8000` in
`service/`), and the full scan flow works in `npm run dev`.

## 5. The backend half

Each consuming project's Laravel backend needs the Scan Proxy route —
[examples/laravel-proxy/README.md](../examples/laravel-proxy/README.md).
Without it, the production build's scan button hits a 404.
