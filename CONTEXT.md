# CONTEXT.md — Glossary

Vocabulary for the MyKad scan-to-fill library. Definitions only — no implementation details.

## MyKad

The Malaysian national identity card. The front face carries the fields this project extracts: name, IC number, address, and (for Muslims only) the word ISLAM. Gender is not printed as a field — it is derived from the IC number.

## IC number

The 12-digit MyKad number, format `YYMMDD-PB-###G`. Encodes date of birth (first 6 digits), place of birth (PB), and gender (last digit: odd = male, even = female). Because it has a fixed format, it can be validated after OCR with a checksum-style sanity check (valid date, known PB code).

## Religion (extracted field)

Returned by the OCR Service as `"ISLAM"` or `null` — nothing else. `null` means "the word ISLAM was not read", which covers both non-Muslims and OCR misses; the form leaves the field empty and the user selects manually. Absence is never converted into an asserted value like "Non-Muslim".

## Gender (derived field)

Not read by OCR at all. Derived from the last digit of the IC number: odd = male, even = female. Returned by the OCR Service alongside the extracted fields.

## Scan-to-Fill

The feature this project delivers: the user points their phone/laptop camera at a MyKad in the browser, the card is captured, fields are extracted by OCR, and a form is pre-filled with the results. Extraction feeds a form; it is **not** identity verification (eKYC) — no liveness, no face match, no fraud detection.

## Accepted cards

Anything that parses. The pipeline accepts any card where a valid IC number and fields can be extracted — current MyKad, pre-2012 designs, MyPR (permanent resident), MyTentera — because they share the layout and 12-digit IC format. There is no card-type classification; rejection means one thing only: "no valid IC number found".

## Name (extracted field)

The Latin-script (romanized) name only, with wrapped lines joined — long Malay/Indian names often continue onto a second line, and those lines are one name. A Chinese-character name line, when present, is deliberately dropped (script detection distinguishes "continuation line — join" from "different script — ignore"). If a project ever needs the Chinese-script name, it becomes a new additive field; `name` never changes meaning.

## OCR Service

The in-house microservice that does the actual extraction: a Dockerized Python service (PaddleOCR + MyKad-layout post-processing) running on the company Linux server. Receives a card image, returns structured fields. The only place OCR happens — consuming projects never run OCR themselves. See ADR-0001.

## Zero-retention

The OCR Service's storage posture: card images are processed in memory and never written to disk, logged, or persisted anywhere — including on failure. Accuracy is monitored instead via per-field correction counts from the Review-and-Correct screen (no values, no images). Any future exception (e.g. short-lived storage of failed scans for debugging) requires explicit management/compliance sign-off first.

## Address (extracted field)

Returned by the OCR Service in both shapes at once: the raw printed lines (`lines`, as they appear on the card) and a best-effort parse into `{ postcode, city, state }` (postcode by 5-digit pattern, state matched against the closed list of 16 states/federal territories). Consuming projects take whichever shape their form needs. Both ship from day one so the schema never has to change under existing consumers.

## Capture Library

The shared frontend piece consumed by the Vue and React projects. Three packages: a framework-agnostic TypeScript core (`mykad-scan-core`) that owns camera access, Guided Auto-capture, and talking to the OCR Service; plus thin wrappers (`mykad-scan-vue`, `mykad-scan-react`) that mount the core as a component. The scanner UI (viewfinder, overlay, shutter) ships in the library; the Review-and-Correct screen does **not** — the library returns extracted fields (`name`, `icNumber`, `address`, `religion`, `gender`) and each project renders its own pre-filled form.

## Guided Auto-capture

The capture UX: the viewfinder shows a card-shaped frame overlay, and the Capture Library snaps automatically when a card-shaped rectangle fills the frame and holds steady. A manual shutter button remains as fallback. The library does **not** recognize MyKads client-side — whether the captured card is actually a MyKad is decided by the OCR Service, which rejects images where no valid IC number pattern is found ("not a MyKad — try again").

## Scan Proxy

The one endpoint each consuming project adds to its own Laravel backend (e.g. `POST /api/scan-mykad`). It forwards the captured image to the internal OCR Service and returns the extracted fields. Projects with logged-in users protect it with their normal auth; the anonymous-user project protects it with IP rate-limiting, image size caps, and origin checks. The OCR Service itself is never exposed to the internet — the Capture Library only ever knows the proxy URL.

## Upload Fallback

The Capture Library's escape hatch when live camera capture isn't possible (permission denied, no/broken camera, desktop webcam too poor): an "upload a photo of your MyKad" option that accepts an image file and sends it through the same Scan Proxy → OCR Service pipeline. It uses `<input type="file" accept="image/*">`; on mobile the native chooser offers both the camera app and the gallery, so it doubles as manual capture.

## Review-and-Correct screen

The mandatory step after extraction where the user sees every extracted field and can edit any of them before submitting. This is the accuracy backstop: OCR must be good, not perfect, because the user confirms all values.
