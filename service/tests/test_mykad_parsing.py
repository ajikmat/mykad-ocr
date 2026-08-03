"""Unit tests for the MyKad parsing rules — pure Python, no OCR models."""

from app import mykad


def B(text, conf=0.95, y=0.0, x0=40.0, x1=400.0):
    return {"text": text, "conf": conf, "y": y, "x0": x0, "x1": x1}


def full_card(name_lines=("TAN AH KOW",), islam=False, cjk=None):
    """Box layout mimicking a real MyKad scan, incl. labels and ghost IC."""
    boxes = [
        B("KAD PENGENALAN", y=30),
        B("MALAYSIA", y=70),
        B("880101-14-5567", y=130),
    ]
    y = 300
    for line in name_lines:
        boxes.append(B(line, y=y))
        y += 44
    if cjk:
        boxes.append(B(cjk, y=y))
        y += 44
    for line in ("NO 12 JALAN MAWAR 3", "TAMAN SRI MAWAR",
                 "68000 AMPANG", "SELANGOR"):
        boxes.append(B(line, y=y))
        y += 40
    if islam:
        boxes.append(B("ISLAM", y=500, x0=760, x1=860))
    boxes.append(B("WARGANEGARA", y=545, x0=760, x1=900))
    boxes.append(B("880101-14-5567", conf=0.7, y=560, x0=700, x1=900))  # ghost
    return sorted(boxes, key=lambda b: b["y"])


def test_full_card_extraction():
    fields, conf = mykad.parse_fields(full_card())
    assert fields["icNumber"] == "880101-14-5567"
    assert fields["name"] == "TAN AH KOW"
    assert fields["gender"] == "M"
    assert fields["religion"] is None
    assert fields["address"]["postcode"] == "68000"
    assert fields["address"]["city"] == "AMPANG"
    assert fields["address"]["state"] == "SELANGOR"
    assert fields["address"]["lines"] == [
        "NO 12 JALAN MAWAR 3", "TAMAN SRI MAWAR", "68000 AMPANG", "SELANGOR"]
    assert set(conf) == {"icNumber", "name", "address"}


def test_two_line_name_joined():
    fields, _ = mykad.parse_fields(
        full_card(name_lines=("MUHAMMAD AIMAN BIN", "ABDULLAH")))
    assert fields["name"] == "MUHAMMAD AIMAN BIN ABDULLAH"


def test_cjk_name_line_dropped():
    fields, _ = mykad.parse_fields(full_card(cjk="林美玲"))
    assert fields["name"] == "TAN AH KOW"
    assert all("林" not in l for l in fields["address"]["lines"])


def test_religion_islam_detected():
    fields, _ = mykad.parse_fields(full_card(islam=True))
    assert fields["religion"] == "ISLAM"


def test_religion_never_guessed_from_absence():
    fields, _ = mykad.parse_fields(full_card(islam=False))
    assert fields["religion"] is None


def test_gender_derived_even_digit_is_female():
    boxes = full_card()
    for b in boxes:
        b["text"] = b["text"].replace("880101-14-5567", "880101-14-5568")
    fields, _ = mykad.parse_fields(boxes)
    assert fields["gender"] == "F"


def test_ghost_ic_not_in_address():
    fields, _ = mykad.parse_fields(full_card())
    assert all("5567" not in l for l in fields["address"]["lines"])


def test_invalid_ic_month_rejected():
    ic, _ = mykad.find_ic([B("881301-14-5567")])  # month 13
    assert ic is None


def test_invalid_pb_code_rejected():
    ic, _ = mykad.find_ic([B("880101-17-5567")])  # PB 17 does not exist
    assert ic is None


def test_ic_found_when_split_across_boxes():
    ic, _ = mykad.find_ic([B("880101-"), B("14-5567")])
    assert ic == "880101-14-5567"


def test_ic_tolerates_missing_dashes_and_spaces():
    ic, _ = mykad.find_ic([B("880101 14 5567")])
    assert ic == "880101-14-5567"


def test_state_fuzzy_match_tolerates_ocr_noise():
    assert mykad.match_state("SELANG0R") == "SELANGOR"
    assert mykad.match_state("W. PERSEKUTUAN KUALA LUMPUR") == \
        "WILAYAH PERSEKUTUAN KUALA LUMPUR"


def test_city_line_containing_state_name_is_not_the_state_line():
    # "KUALA TERENGGANU" is a city; must not match as state TERENGGANU
    assert mykad.match_state("20000 KUALA TERENGGANU") is None


def test_no_ic_means_rejection_shape():
    fields, _ = mykad.parse_fields([B("SOME RANDOM TEXT")])
    assert fields["icNumber"] is None
    assert fields["gender"] is None


def test_low_confidence_lines_ignored_for_name():
    boxes = full_card()
    boxes.insert(4, B("GARBAGE GLARE", conf=0.4, y=290))
    fields, _ = mykad.parse_fields(boxes)
    assert "GARBAGE" not in (fields["name"] or "")
