# 0001 — OCR runs on an in-house service; MyKad images never go to third-party processors

## Status

Accepted (2026-07-30)

## Context

The scan-to-fill feature extracts name, IC number, address, and religion from a photo of a MyKad. A MyKad image is sensitive personal data under Malaysia's PDPA — the IC number alone is a lifelong national identifier, and religion is explicitly a sensitive category. Sending the image to a third-party AI provider (OpenAI, Google Vision, etc.) would be a cross-border transfer to an external processor.

Vision LLMs would give the best extraction accuracy with the least effort. Browser-side OCR (Tesseract.js) was tried and produced poor results — MyKad's guilloche background, hologram overlay, and text-over-graphics defeat it, and modern in-browser models mean 20–50 MB downloads on low-end phones.

## Decision

OCR runs on a company-controlled server as a standalone microservice: a Dockerized Python service using PaddleOCR plus MyKad-specific post-processing (fixed-layout field mapping, IC number format validation). All consuming projects (Vue and React) call this one service. MyKad images are never sent to any third-party processor.

## Consequences

- PDPA exposure is contained to company infrastructure; no cross-border transfer of card images.
- Accuracy tuning happens in one place and benefits every consuming project.
- We accept somewhat lower extraction accuracy than a vision LLM would give; the mandatory Review-and-Correct screen is the backstop.
- DevOps takes on running a Docker container on the company Linux server (new skill, deliberately kept to a single container — no orchestration).
- If this decision is ever revisited (e.g. a Malaysian-hosted processor with PDPA-compliant terms), the service boundary makes the swap possible without touching the frontend library.
