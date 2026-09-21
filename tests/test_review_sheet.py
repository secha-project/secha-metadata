"""Tests for review_sheet.py: the content of a review workbook, not its formatting.

What a reviewer is asked is what matters here: that every mapped point appears once,
that generated harmonic fields are expanded rather than hidden behind a pattern, that
the catalog points we did not map are listed with an honest reason, and that a rule is
explained in words a domain expert can answer.
"""

from pathlib import Path

import yaml

from review_sheet import (
    mapped_entries,
    open_questions,
    read_catalog,
    unmapped_points,
    validation_limits,
)

ROOT = Path(__file__).resolve().parent.parent
VOCAB = yaml.safe_load((ROOT / "canonical" / "quantity_vocabulary.yaml").read_text("utf-8"))
MX = ROOT / "vendors" / "mx_electrix"
PROCEM = ROOT / "vendors" / "procem_kampusareena_pq"

# Column positions in a mapping row, as the workbook lays them out.
SOURCE, NAME, SOURCE_UNIT, QUANTITY, PHASE, VARIANT, ORDER = range(7)
UNIT, AGGREGATION, TRANSFORM = 7, 8, 9


def test_every_mapped_column_appears_once() -> None:
    mapping, rows = mapped_entries(MX, VOCAB, {})
    sources = [row[SOURCE] for row in rows]
    assert len(sources) == len(set(sources)), "a point must be asked about exactly once"
    for column in mapping["columns"]:
        assert column["src"] in sources


def test_generated_harmonics_are_expanded_into_one_row_each() -> None:
    mapping, rows = mapped_entries(MX, VOCAB, {})
    rule = mapping["generated"][0]
    generated = [row for row in rows if "named by rule" in str(row[TRANSFORM])]
    assert len(generated) == len(rule["order"]) * len(rule["phase_map"])
    for row in generated:
        assert row[ORDER] in rule["order"]
        assert row[PHASE] in rule["phase_map"].values()
        assert row[QUANTITY] == rule["quantity"]


def test_a_long_entry_shows_the_unit_the_vendor_declared() -> None:
    mapping, rows = mapped_entries(PROCEM, VOCAB, {"23501": {"unit": "Hz"}})
    first = next(row for row in rows if row[SOURCE] == "rtl 23501")
    assert first[SOURCE_UNIT] == "Hz"
    assert first[NAME] == next(r["desc"] for r in mapping["rows"] if str(r["key"]) == "23501")


def test_defaults_are_shown_rather_than_left_blank() -> None:
    _, rows = mapped_entries(PROCEM, VOCAB, {})
    assert all(row[VARIANT] for row in rows), "variant defaults to none"
    assert all(row[AGGREGATION] for row in rows), "aggregation defaults to the source default"


def test_unmapped_lists_catalog_points_with_a_reason() -> None:
    catalog = {
        "23501": {"name": "LV3_EVCharging_Freq", "path": "/f", "unit": "Hz"},
        "24001": {"name": "LV3_EVCharging_I10L1", "path": "/i", "unit": "%"},
        "24002": {"name": "LV3_EVCharging_Udc1", "path": "/d", "unit": "V"},
    }
    rows = unmapped_points("procem_kampusareena_pq", PROCEM, catalog)
    reasons = {row[1]: row[4] for row in rows}
    assert "LV3_EVCharging_Freq" not in reasons, "a mapped point is not asked about twice"
    assert reasons["LV3_EVCharging_I10L1"] == "not mapped yet"
    assert "_Udc" in reasons["LV3_EVCharging_Udc1"], "an exclusion states why it was excluded"


def test_a_wide_source_does_not_list_its_structural_fields() -> None:
    names = {row[0] for row in unmapped_points("mx_electrix", MX, {})}
    for structural in ("timestamp", "meter", "id"):
        assert structural not in names, "these carry the reading, they are not measurements"


def test_a_missing_value_reads_differently_from_a_missing_timestamp() -> None:
    plain = {row[0]: row[5] for row in validation_limits(PROCEM)}
    assert plain["value"] == "a reading with no value carries no measurement"
    assert "placed in time" in plain["timestamp"]
    assert "45" in plain["frequency"] and "65" in plain["frequency"]


def test_read_catalog_accepts_the_separator_the_vendor_used(tmp_path: Path) -> None:
    path = tmp_path / "catalog.csv"
    path.write_text("rtl_id;name;unit\n23501;LV3_EVCharging_Freq;Hz\n", encoding="utf-8")
    assert read_catalog(path)["23501"]["name"] == "LV3_EVCharging_Freq"
    assert read_catalog(tmp_path / "absent.csv") == {}


def test_questions_are_asked_only_of_the_vendors_they_concern() -> None:
    for vendor in ("mx_electrix", "procem_kampusareena_pq"):
        assert open_questions(vendor), "both live vendors have open questions today"
    assert open_questions("no_such_vendor") == []
