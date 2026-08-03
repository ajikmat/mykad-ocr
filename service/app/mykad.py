"""MyKad field extraction from positioned OCR text boxes.

Pure Python — no OCR or image dependencies — so every parsing rule is
unit-testable without models. Field rules follow SPEC.md §3 / CONTEXT.md.

A "box" is one recognized text line: {"text", "conf", "y", "x0", "x1"},
sorted top-to-bottom by the caller.
"""

import re
from difflib import SequenceMatcher

STATES = [
    "JOHOR", "KEDAH", "KELANTAN", "MELAKA", "NEGERI SEMBILAN", "PAHANG",
    "PULAU PINANG", "PERAK", "PERLIS", "SABAH", "SARAWAK", "SELANGOR",
    "TERENGGANU", "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "WILAYAH PERSEKUTUAN LABUAN", "WILAYAH PERSEKUTUAN PUTRAJAYA",
]

# Card labels/headers that are never part of an extracted field
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

MIN_LINE_CONF = 0.55   # boxes below this are ignored for name/address
MIN_IC_CONF = 0.30     # IC search casts a wider net; the regex+checks filter


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().upper())


def _sim(a, b):
    return SequenceMatcher(None, a or "", b or "").ratio()


def has_cjk(s):
    return any(0x4E00 <= ord(c) <= 0x9FFF for c in s)


def digits_only(s):
    return re.sub(r"\D", "", s or "")


def valid_ic_date(d6):
    mm, dd = int(d6[2:4]), int(d6[4:6])
    return 1 <= mm <= 12 and 1 <= dd <= 31


def _match_ic(text):
    for m in IC_RE.finditer(text):
        d6, pb, last = m.groups()
        if valid_ic_date(d6) and pb not in INVALID_PB:
            return f"{d6}-{pb}-{last}"
    return None


def find_ic(boxes):
    """Return (formatted IC or None, confidence)."""
    usable = [(b["text"], b["conf"]) for b in boxes if b["conf"] >= MIN_IC_CONF]
    for text, conf in usable:
        ic = _match_ic(text)
        if ic:
            return ic, conf
    # tolerate the number being split across boxes
    ic = _match_ic(" ".join(t for t, _ in usable))
    if ic:
        confs = [c for t, c in usable if any(ch.isdigit() for ch in t)]
        return ic, (sum(confs) / len(confs) if confs else 0.0)
    return None, 0.0


def derive_gender(ic):
    """Gender is never OCR'd: last IC digit odd = M, even = F (CONTEXT.md)."""
    d = digits_only(ic)
    if len(d) != 12:
        return None
    return "M" if int(d[-1]) % 2 else "F"


def is_noise(text):
    n = norm(text)
    if n in NOISE_EXACT:
        return True
    return any(sub in n for sub in NOISE_SUBSTRINGS)


def match_state(line):
    """A state line is a line that IS a state name (tolerating OCR noise)."""
    n = norm(line).replace(".", "").replace(",", "")
    for s in STATES:
        if n == s or _sim(n, s) >= 0.85:
            return s
    if n.startswith(("WP ", "W P ")) or "PERSEKUTUAN" in n:
        if "KUALA LUMPUR" in n:
            return "WILAYAH PERSEKUTUAN KUALA LUMPUR"
        if "LABUAN" in n:
            return "WILAYAH PERSEKUTUAN LABUAN"
        if "PUTRAJAYA" in n:
            return "WILAYAH PERSEKUTUAN PUTRAJAYA"
    return None


def find_religion(boxes):
    """Return "ISLAM" or None — never anything else (CONTEXT.md)."""
    for b in boxes:
        n = norm(b["text"])
        if n == "ISLAM" or (b["conf"] >= 0.5 and len(n) <= 7
                            and _sim(n, "ISLAM") >= 0.8):
            return "ISLAM"
    return None


def parse_fields(boxes):
    """Extract MyKad fields. Returns (fields dict, confidence dict).

    fields follows the SPEC.md §3 contract; icNumber is None when no valid
    IC was found (the caller turns that into a NO_IC_FOUND rejection).
    """
    ic, ic_conf = find_ic(boxes)
    gender = derive_gender(ic)
    religion = find_religion(boxes)

    # name/address sit below the main IC number box, in the left column
    ic_digits = digits_only(ic)
    ic_y = 0.0
    for b in boxes:
        if ic_digits and ic_digits in digits_only(b["text"]):
            ic_y = b["y"]
            break

    max_x1 = max((b["x1"] for b in boxes), default=0.0) or 1.0
    cands = [
        b for b in boxes
        if b["conf"] >= MIN_LINE_CONF
        and b["y"] > ic_y
        and b["x0"] < 0.5 * max_x1                       # left column only
        and not is_noise(b["text"])
        and not (ic_digits and ic_digits in digits_only(b["text"]))  # ghost IC
        and norm(b["text"]) != "ISLAM"
    ]

    name_parts, name_confs = [], []
    addr_lines, addr_confs = [], []
    state = None
    in_addr = False
    for b in cands:
        t = norm(b["text"])
        if not t or has_cjk(b["text"]):   # Chinese-script name line: dropped
            continue
        st = match_state(t)
        if st and (in_addr or addr_lines or name_parts):
            state = st
            addr_lines.append(st)
            addr_confs.append(b["conf"])
            break
        if not in_addr and (ADDRESS_START.match(t)
                            or any(ch.isdigit() for ch in t)):
            in_addr = True
        if in_addr:
            addr_lines.append(t)
            addr_confs.append(b["conf"])
        else:
            name_parts.append(t)          # wrapped name lines are joined
            name_confs.append(b["conf"])

    postcode = city = None
    for t in addr_lines:
        m = re.match(r"^(\d{5})\s*(.*)$", t)
        if m:
            postcode = m.group(1)
            city = m.group(2).strip() or None

    fields = {
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

    confidence = {}
    if ic:
        confidence["icNumber"] = round(ic_conf, 2)
    if name_confs:
        confidence["name"] = round(sum(name_confs) / len(name_confs), 2)
    if addr_confs:
        confidence["address"] = round(sum(addr_confs) / len(addr_confs), 2)
    return fields, confidence
