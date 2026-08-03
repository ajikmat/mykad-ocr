# Phase 0 — MyKad OCR accuracy benchmark

Answers one question before any real code gets written: **is PaddleOCR accurate
enough on real MyKads to build the OCR Service on?** (SPEC.md §7.)

Gate: IC number ≥ 95% exact, name ≥ 85% exact.

## Privacy rules (read first)

The test photos are real people's identity cards. Non-negotiable:

1. **Consent** — colleagues volunteer their card knowingly. Tell them what
   it's for (accuracy testing) and that it's deleted afterwards.
2. **This machine only** — photos and `ground_truth.json` stay in this folder,
   which is gitignored. Never commit them, never upload them, never put them
   on a shared drive or chat.
3. **Delete when done** — once the gate passes, delete `photos/` and
   `ground_truth.json`. Keep individual images longer only if that card's
   owner explicitly agreed to it (useful as a regression set).

Nothing here trains anything. PaddleOCR is a pre-trained model; these photos
are only ever *read* to measure accuracy.

## Collecting photos (~20)

Variety is the point — the benchmark is only as honest as the sample:

- different phones (cheap Android included), different lighting
- old cards (pre-2012 design, worn/faded print) and new ones
- at least a few Chinese-name cards (tests the script-filter)
- at least a few long Malay/Indian names that wrap to two lines
- frame the card like the app's guide overlay will: card filling most of the
  photo, roughly straight-on. Don't crop pixel-perfect — the real capture
  won't be either.

Name files simply (`01.jpg`, `02.jpg`, ...) and drop them in `photos/`.

## Setup and run

```bash
cd benchmark
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp ground_truth.example.json ground_truth.json
# fill ground_truth.json with each card's true values, then:
python benchmark.py
```

First run downloads the PaddleOCR models (~20 MB) — after that it's offline.

## Reading the result

Per-image mismatches print first, then a summary table and the gate verdict.
Exit code 0 = gate passed.

- `REJECTED (no valid IC number found)` — the pipeline couldn't read that
  photo at all; counts against every field.
- `AVG SIM` — character-level similarity. A field with low exact-match but
  high similarity (e.g. name 70% exact / 0.95 sim) means near-misses
  (one wrong character), which better preprocessing usually fixes.

## If the gate fails

In order of likely payoff:

1. **Crop + deskew first** — locate the card rectangle and
   perspective-correct before OCR (this is in the real pipeline's design;
   the benchmark deliberately starts without it to get a floor reading).
2. Retake the worst photos — if only the potato-camera shots fail, that's
   what the Capture Library's guide overlay and client-side crop exist for.
3. Try PaddleOCR's server-grade recognition model instead of the default.
4. Tune the field-parsing heuristics in `benchmark.py` (they're a first
   draft of the real OCR Service's post-processing).

If it still fails after all four, the in-house engine choice itself needs
revisiting — see ADR-0001 for what "revisiting" must not include.
