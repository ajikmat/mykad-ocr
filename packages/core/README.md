# mykad-scan-core

Framework-agnostic capture library for MyKad Scan-to-Fill: opens the camera,
guides the user with a card frame, auto-captures when a card is framed and
steady, falls back to photo upload, and posts the image to the consuming
project's Scan Proxy. Returns the extracted fields; rendering the
Review-and-Correct form is the host app's job.

```ts
import { createMykadScanner } from "mykad-scan-core";

const scanner = createMykadScanner({
  proxyUrl: "/api/scan-mykad",           // your backend's Scan Proxy
  onResult: ({ fields, confidence }) => prefillForm(fields),
  onReject: (reason) => {},              // NO_IC_FOUND etc. — UI already shows "try again"
  onError: (err) => {},                  // network/server failures
  autoCapture: true,                     // default
  labels: { guide: "Letakkan MyKad anda dalam bingkai" }, // optional overrides
});

scanner.mount(document.getElementById("scanner")!); // container needs a height
// scanner.captureNow()        — manual shutter, also a visible button
// scanner.submitImage(blob)   — feed an image you obtained yourself
// scanner.resume()            — restart after a successful scan stopped the camera
scanner.destroy();
```

Behavior notes:

- **HTTPS required** — browsers only allow camera access on secure origins
  (localhost is fine for dev).
- **Auto-capture is a heuristic**, not card recognition: edge-on-frame +
  sharpness, with a steadiness hold (~0.6 s) that is deliberately forgiving —
  normal hand tremor pauses progress instead of resetting it; only losing
  the card or focus decays it. Every auto-capture is then blur-checked
  (`DETECT.captureSharpMin`) and silently retried if motion-blurred, so a
  shaky capture never wastes a server round-trip. Thresholds are exported
  as `DETECT` for tuning on real devices. The manual button and upload
  fallback are always available, and whether the image is actually a MyKad
  is decided server-side.
- **Privacy:** frames are analyzed in-page; the only thing that leaves the
  browser is the captured JPEG, sent to your `proxyUrl`. The camera is
  stopped after a successful scan.
- On camera denial/absence the scanner switches to upload-only mode by
  itself.
