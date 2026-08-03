#!/usr/bin/env python3
"""MyKad OCR benchmark — Phase 0 accuracy spike (SPEC.md §7).

Runs every photo in ./photos through PaddleOCR + MyKad field parsing and
scores the result against ground_truth.json. See README.md for setup and
the privacy rules for handling the test photos.

This is throwaway spike code: it exists to answer one question — is the
PaddleOCR pipeline accurate enough to build on? The field-parsing heuristics
here are a first draft of what the real OCR Service will refine.
"""

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}

# Accuracy gate from SPEC.md §7
GATE = {"icNumber": 0.95, "name": 0.85}

STATES = [
    "JOHOR", "KEDAH", "KELANTAN", "MELAKA", "NEGERI SEMBILAN", "PAHANG",
    "PULAU PINANG", "PERAK", "PERLIS", "SABAH", "SARAWAK", "SELANGOR",
    "TERENGGANU", "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "WILAYAH PERSEKUTUAN LABUAN", "WILAYAH PERSEKUTUAN PUTRAJAYA",
]

# Header/label text that is printed on the card but is never part of a field
NOISE_SUBSTRINGS = ["PENGENALAN", "MYKAD", "IDENTITY CARD", "WARGANEGARA"]
NOISE_EXACT = {"MALAYSIA", "KAD", "LELAKI", "PEREMPUAN"}

ADDRESS_START = re.compile(
    r"^(NO\b|NO\.|LOT\b|PT\b|JALAN\b|JLN\b|LORONG\b|LRG\b|TAMAN\b|TMN\b"
    r"|KAMPUNG\b|KAMPONG\b|KG\b|BATU\b|PERSIARAN\b|LEBUH\b|BLOK\b|BLOCK\b"
    r"|FLAT\b|PANGSAPURI\b|APARTMENT\b|TINGKAT\b|UNIT\b|\d)"
)

IC_RE = re.compile(r"(\d{6})\s*[-–—]?\s*(\d{2})\s*[-–—]?\s*(\d{4})")
# Place-of-birth codes that do not exist; everything else is accepted
INVALID_PB = {"00", "17", "18", "19", "20", "69", "70", "73", "80", "81",
              "94", "95", "96", "97"}


# --------------------------------------------------------------- small utils

def norm(s):
    return re.sub(r"\s+", " ", s.strip().upper())


def sim(a, b):
    return SequenceMatcher(None, a or "", b or "").ratio()


def has_cjk(s):
    return any(0x4E00 <= ord(c) <= 0x9FFF for c in s)


def digits_only(s):
    return re.sub(r"\D", "", s or "")


# ---------------------------------------------------------------- OCR runner

def make_ocr():
    from paddleocr import PaddleOCR
    try:  # PaddleOCR 3.x
        return PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=True,
        )
    except TypeError:  # PaddleOCR 2.x
        return PaddleOCR(lang="en", use_angle_cls=True, show_log=False)


def _unwrap_3x(res):
    """Get the dict payload out of a PaddleOCR 3.x result object."""
    if isinstance(res, dict):
        return res
    j = getattr(res, "json", None)
    if isinstance(j, dict):
        return j.get("res", j)
    raise TypeError("unrecognized PaddleOCR result object")


def run_ocr(ocr, image_path):
    """Return text boxes as dicts {text, conf, y, x0, x1}, sorted top-to-bottom."""
    boxes = []
    if hasattr(ocr, "predict"):  # 3.x
        for res in ocr.predict(str(image_path)):
            d = _unwrap_3x(res)
            texts = d.get("rec_texts") or []
            scores = d.get("rec_scores") or [1.0] * len(texts)
            polys = d.get("rec_polys")
            if polys is None or len(polys) != len(texts):
                polys = d.get("dt_polys")
            if polys is None or len(polys) != len(texts):
                polys = [None] * len(texts)
            for i, (text, score, poly) in enumerate(zip(texts, scores, polys)):
                if poly is not None:
                    ys = [float(p[1]) for p in poly]
                    xs = [float(p[0]) for p in poly]
                    boxes.append({"text": str(text), "conf": float(score),
                                  "y": sum(ys) / len(ys),
                                  "x0": min(xs), "x1": max(xs)})
                else:
                    boxes.append({"text": str(text), "conf": float(score),
                                  "y": float(i), "x0": 0.0, "x1": 0.0})
    else:  # 2.x
        result = ocr.ocr(str(image_path), cls=True)
        for line in (result[0] or []):
            poly, (text, score) = line
            ys = [float(p[1]) for p in poly]
            xs = [float(p[0]) for p in poly]
            boxes.append({"text": str(text), "conf": float(score),
                          "y": sum(ys) / len(ys),
                          "x0": min(xs), "x1": max(xs)})
    boxes.sort(key=lambda b: b["y"])
    return boxes


# ------------------------------------------------------------- field parsing

def valid_ic_date(d6):
    mm, dd = int(d6[2:4]), int(d6[4:6])
    return 1 <= mm <= 12 and 1 <= dd <= 31


def find_ic(texts):
    for t in list(texts) + [" ".join(texts)]:
        for m in IC_RE.finditer(t):
            d6, pb, last = m.groups()
            if valid_ic_date(d6) and pb not in INVALID_PB:
                return f"{d6}-{pb}-{last}"
    return None


def is_noise(text):
    n = norm(text)
    if n in NOISE_EXACT:
        return True
    return any(sub in n for sub in NOISE_SUBSTRINGS)


def match_state(line):
    """A state line is a line that IS a state name (tolerating OCR noise)."""
    n = norm(line).replace(".", "").replace(",", "")
    for s in STATES:
        if n == s or sim(n, s) >= 0.85:
            return s
    # W.P. abbreviations
    if n.startswith(("WP ", "W P ")) or "PERSEKUTUAN" in n:
        for s in STATES:
            if s.startswith("WILAYAH") and sim(n, s) >= 0.5:
                return s
        if "KUALA LUMPUR" in n:
            return "WILAYAH PERSEKUTUAN KUALA LUMPUR"
        if "LABUAN" in n:
            return "WILAYAH PERSEKUTUAN LABUAN"
        if "PUTRAJAYA" in n:
            return "WILAYAH PERSEKUTUAN PUTRAJAYA"
    return None


def parse_fields(boxes):
    """First-draft MyKad field extraction from positioned OCR boxes."""
    texts_all = [b["text"] for b in boxes if b["conf"] >= 0.30]

    ic = find_ic(texts_all)
    gender = None
    if ic:
        gender = "M" if int(ic[-1]) % 2 else "F"

    religion = None
    for b in boxes:
        n = norm(b["text"])
        if n == "ISLAM" or (b["conf"] >= 0.5 and len(n) <= 7
                            and sim(n, "ISLAM") >= 0.8):
            religion = "ISLAM"
            break

    # y-position of the main IC number box; name/address sit below it
    ic_digits = digits_only(ic)
    ic_y = 0.0
    for b in boxes:
        if ic_digits and ic_digits in digits_only(b["text"]):
            ic_y = b["y"]
            break

    max_x1 = max((b["x1"] for b in boxes), default=0.0) or 1.0
    cands = [
        b for b in boxes
        if b["conf"] >= 0.55
        and b["y"] > ic_y
        and b["x0"] < 0.5 * max_x1                      # left column only
        and not is_noise(b["text"])
        and not (ic_digits and ic_digits in digits_only(b["text"]))  # ghost IC
        and norm(b["text"]) != "ISLAM"
    ]

    name_parts, addr_lines, state = [], [], None
    in_addr = False
    for b in cands:
        t = norm(b["text"])
        if not t or has_cjk(b["text"]):   # Chinese-script name line: dropped
            continue
        st = match_state(t)
        if st and (in_addr or addr_lines or name_parts):
            state = st
            addr_lines.append(st)
            break
        if not in_addr and (ADDRESS_START.match(t)
                            or any(ch.isdigit() for ch in t)):
            in_addr = True
        if in_addr:
            addr_lines.append(t)
        else:
            name_parts.append(t)

    postcode = city = None
    for t in addr_lines:
        m = re.match(r"^(\d{5})\s*(.*)$", t)
        if m:
            postcode = m.group(1)
            city = m.group(2).strip() or None

    return {
        "name": " ".join(name_parts) or None,
        "icNumber": ic,
        "gender": gender,
        "religion": religion,
        "address": {
            "lines": addr_lines,
            "postcode": postcode,
            "city": city,
            "state": state,
        },
    }


# ---------------------------------------------------------------- comparison

def derived_gender(ic):
    d = digits_only(ic)
    return ("M" if int(d[-1]) % 2 else "F") if len(d) == 12 else None


def compare(got, truth):
    """Return {field: (ok, got_value, expected_value, similarity)}."""
    out = {}

    g, e = digits_only(got["icNumber"]), digits_only(truth["icNumber"])
    out["icNumber"] = (g == e and g != "", got["icNumber"],
                       truth["icNumber"], sim(g, e))

    g, e = norm(got["name"] or ""), norm(truth["name"] or "")
    out["name"] = (g == e and g != "", got["name"], truth["name"], sim(g, e))

    g, e = got["religion"], truth.get("religion")
    out["religion"] = (g == e, g, e, 1.0 if g == e else 0.0)

    e = derived_gender(truth["icNumber"])
    g = got["gender"]
    out["gender"] = (g == e and g is not None, g, e, 1.0 if g == e else 0.0)

    ta = truth.get("address", {})
    for key in ("postcode", "city", "state"):
        g = norm(got["address"][key] or "")
        e = norm(ta.get(key) or "")
        out[f"address.{key}"] = (g == e, got["address"][key], ta.get(key),
                                 sim(g, e))

    g = norm(" / ".join(got["address"]["lines"]))
    e = norm(" / ".join(ta.get("lines", [])))
    out["address.lines"] = (g == e, g, e, sim(g, e))
    return out


FIELDS = ["icNumber", "name", "religion", "gender",
          "address.postcode", "address.city", "address.state",
          "address.lines"]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--photos", type=Path, default=BENCH_DIR / "photos")
    ap.add_argument("--truth", type=Path, default=BENCH_DIR / "ground_truth.json")
    args = ap.parse_args()

    if not args.truth.exists():
        print(f"ERROR: {args.truth} not found.\n"
              f"Copy ground_truth.example.json to ground_truth.json and fill "
              f"in the real values for each photo.", file=sys.stderr)
        return 2
    truth_all = json.loads(args.truth.read_text())

    images = sorted(p for p in args.photos.glob("*")
                    if p.suffix.lower() in IMAGE_EXTS)
    if not images:
        print(f"ERROR: no images found in {args.photos}/ "
              f"(expected .jpg/.jpeg/.png)", file=sys.stderr)
        return 2

    print("Loading PaddleOCR (first run downloads models, be patient)...")
    ocr = make_ocr()

    per_field = {f: {"ok": 0, "n": 0, "sim": 0.0} for f in FIELDS}
    rejected = []

    for img in images:
        truth = truth_all.get(img.name)
        if truth is None:
            print(f"\n--- {img.name}: SKIPPED (no ground_truth.json entry)")
            continue

        boxes = run_ocr(ocr, img)
        got = parse_fields(boxes)

        if got["icNumber"] is None:
            rejected.append(img.name)
            print(f"\n--- {img.name}: REJECTED (no valid IC number found)")
            for f in FIELDS:
                per_field[f]["n"] += 1
            continue

        results = compare(got, truth)
        misses = {f: r for f, r in results.items() if not r[0]}
        status = "OK" if not misses else f"{len(misses)} field(s) wrong"
        print(f"\n--- {img.name}: {status}")
        for f, (ok, g, e, s) in misses.items():
            print(f"      {f:18s} got: {g!r}\n"
                  f"      {'':18s} exp: {e!r}   (similarity {s:.2f})")

        for f, (ok, _, _, s) in results.items():
            per_field[f]["n"] += 1
            per_field[f]["ok"] += 1 if ok else 0
            per_field[f]["sim"] += s

    # ------------------------------------------------------------- summary
    print("\n" + "=" * 62)
    print(f"{'FIELD':<20}{'EXACT':>12}{'RATE':>8}{'AVG SIM':>10}   GATE")
    print("-" * 62)
    verdicts = {}
    for f in FIELDS:
        st = per_field[f]
        if st["n"] == 0:
            continue
        rate = st["ok"] / st["n"]
        avg = st["sim"] / st["n"]
        gate = ""
        if f in GATE:
            passed = rate >= GATE[f]
            verdicts[f] = passed
            gate = f">={GATE[f]:.0%} {'PASS' if passed else 'FAIL'}"
        print(f"{f:<20}{st['ok']:>5}/{st['n']:<6}{rate:>7.0%}{avg:>10.2f}   {gate}")
    if rejected:
        print(f"\nRejected (no IC found): {len(rejected)} — {', '.join(rejected)}")
    print("=" * 62)

    if verdicts and all(verdicts.values()):
        print("GATE: PASS — pipeline is accurate enough to build on (SPEC §7).")
        return 0
    print("GATE: FAIL — tune preprocessing/parsing before building further.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
