"""Tests for propose.py: everything except the model call.

The model is the one part that cannot be asserted on, so it is kept out of these tests
entirely. What is tested is the machinery around it: that a bad spec is refused, that a
catalog is read as declared, that assembled files say what the spec said, that the
advisory checks fire where they should and stay quiet where they cannot judge, and above
all that the staging gate rejects a proposal the repository would not accept.
"""

from pathlib import Path

import pytest
import yaml

from propose import (
    Point,
    Proposal,
    advisories_for,
    assemble_mapping,
    assemble_validation,
    load_rulebook,
    load_spec,
    parse_reply,
    read_catalog,
    stage_and_validate,
    stratified,
)

ROOT = Path(__file__).resolve().parent.parent
RB = load_rulebook(ROOT)

SPEC = {
    "vendor": "test_vendor",
    "source": "dump",
    "target_schema_version": "1.0.0",
    "mapping_version": "0.1.0",
    "shape": "long",
    "format": {"type": "csv", "encoding": "utf-8"},
    "access": {
        "landing_root_env": "SECHA_LANDING_ROOT",
        "layout": "vendor=test_vendor/date={date}",
        "partition_keys": ["date"],
    },
    "record": {
        "key_field": "measurement_id",
        "row_id_field": "measurement_id",
        "timestamp_field": "timestamp",
        "value_field": "value",
    },
    "long_fields": [
        {"name": "measurement_id", "type": "long", "nullable": False},
        {"name": "value", "type": "string", "nullable": False},
        {"name": "timestamp", "type": "long", "nullable": False},
    ],
    "validation_defaults": [
        {"quantity": "frequency", "type": "range", "min": 45, "max": 65, "on_fail": "flag_suspect"},
        {"quantity": "voltage", "type": "range", "min": 0, "max": 1000, "on_fail": "flag_suspect"},
    ],
    "catalog": {"path": "catalog.csv", "key_column": "id", "name_column": "name"},
}

CATALOG = "id;name;path;unit\n1;A_Freq;/f;Hz\n2;A_UL1;/u;V\n3;A_Udc1;/d;NaN\n"


def _spec_dir(tmp_path: Path, spec: dict | None = None, catalog: str = CATALOG) -> Path:
    (tmp_path / "catalog.csv").write_text(catalog, encoding="utf-8")
    path = tmp_path / "v.spec.yaml"
    path.write_text(yaml.safe_dump(spec or SPEC), encoding="utf-8")
    return path


def _proposal(key: str, name: str, **entry) -> Proposal:
    return Proposal(Point(key=key, name=name, context="", unit=""), entry=entry)


# ------------------------------------------------------------------------------- inputs


def test_spec_missing_required_key_is_refused(tmp_path: Path) -> None:
    broken = {k: v for k, v in SPEC.items() if k != "access"}
    with pytest.raises(SystemExit) as exc:
        load_spec(_spec_dir(tmp_path, broken))
    assert "access" in str(exc.value)


def test_long_shape_requires_long_fields(tmp_path: Path) -> None:
    broken = {k: v for k, v in SPEC.items() if k != "long_fields"}
    with pytest.raises(SystemExit) as exc:
        load_spec(_spec_dir(tmp_path, broken))
    assert "long_fields" in str(exc.value)


def test_catalog_is_read_and_filtered(tmp_path: Path) -> None:
    spec = {**SPEC, "catalog": {**SPEC["catalog"], "delimiter": ";", "unit_column": "unit"}}
    path = _spec_dir(tmp_path, spec)
    points = read_catalog(load_spec(path), path)
    assert [p.name for p in points] == ["A_Freq", "A_UL1", "A_Udc1"]
    assert points[0].unit == "Hz"

    spec["catalog"]["exclude_pattern"] = "_Udc"
    path = _spec_dir(tmp_path, spec)
    assert [p.name for p in read_catalog(load_spec(path), path)] == ["A_Freq", "A_UL1"]


def test_unknown_catalog_column_names_what_it_found(tmp_path: Path) -> None:
    spec = {**SPEC, "catalog": {**SPEC["catalog"], "delimiter": ";", "name_column": "nope"}}
    path = _spec_dir(tmp_path, spec)
    with pytest.raises(SystemExit) as exc:
        read_catalog(load_spec(path), path)
    assert "nope" in str(exc.value)


def test_stratified_sample_spans_the_catalog() -> None:
    points = [Point(key=str(i), name=f"p{i}", context="", unit="") for i in range(100)]
    sample = stratified(points, 5)
    assert len(sample) == 5
    assert sample[0].name == "p0" and sample[-1].name == "p80"


# -------------------------------------------------------------------------------- parse


@pytest.mark.parametrize(
    "reply",
    [
        "quantity: voltage\nphase: L1\nunit: V",
        "```yaml\nquantity: voltage\nphase: L1\nunit: V\n```",
        "<think>the L1 suffix is the phase</think>\nquantity: voltage\nphase: L1\nunit: V",
    ],
)
def test_parse_reply_tolerates_fences_and_reasoning(reply: str) -> None:
    assert parse_reply(reply) == {"quantity": "voltage", "phase": "L1", "unit": "V"}


@pytest.mark.parametrize("reply", ["not yaml at all: [", "- quantity: voltage", "phase: L1"])
def test_parse_reply_rejects_non_entries(reply: str) -> None:
    assert parse_reply(reply) is None


# ----------------------------------------------------------------------------- advisory


def test_advisory_flags_dimensional_mismatch() -> None:
    entry = {"quantity": "harmonic_voltage", "phase": "L1", "unit": "V", "harmonic_order": 3}
    notes = advisories_for(entry, Point("1", "U3L1", "", ""), RB)
    assert any("measures voltage" in n for n in notes)


def test_advisory_flags_order_absent_from_point_name() -> None:
    entry = {"quantity": "harmonic_voltage", "phase": "L1", "unit": "percent", "harmonic_order": 9}
    notes = advisories_for(entry, Point("1", "LV3_U19L1", "", ""), RB)
    assert any("harmonic_order 9 does not appear" in n for n in notes)


def test_advisory_accepts_order_present_in_point_name() -> None:
    entry = {"quantity": "harmonic_voltage", "phase": "L1", "unit": "percent", "harmonic_order": 19}
    assert advisories_for(entry, Point("1", "LV3_U19L1", "", ""), RB) == []


def test_advisory_stays_quiet_on_unit_spelling() -> None:
    """A vendor writing "%" for percent is not a disagreement it can be asked about."""
    entry = {"quantity": "thd_voltage", "phase": "L1", "unit": "percent"}
    assert advisories_for(entry, Point("1", "TDUL1", "", "%"), RB) == []


def test_advisory_flags_real_vendor_unit_conflict() -> None:
    entry = {"quantity": "thd_voltage", "phase": "L1", "unit": "percent"}
    notes = advisories_for(entry, Point("1", "TDUL1", "", "V"), RB)
    assert any("vendor declares source unit 'V'" in n for n in notes)


# ----------------------------------------------------------------------------- assembly


def test_mapping_uses_rows_for_long_sources_and_drops_none_variants() -> None:
    doc = yaml.safe_load(
        assemble_mapping(
            SPEC,
            [
                _proposal(
                    "1", "A_Freq", quantity="frequency", phase="none", unit="Hz", variant="none"
                )
            ],
            [],
        )
    )
    assert "columns" not in doc
    assert doc["rows"] == [
        {"key": "1", "quantity": "frequency", "phase": "none", "unit": "Hz", "desc": "A_Freq"}
    ]


def test_mapping_uses_columns_for_wide_sources() -> None:
    wide = {**SPEC, "shape": "wide"}
    doc = yaml.safe_load(
        assemble_mapping(
            wide, [_proposal("f", "fhz", quantity="frequency", phase="none", unit="Hz")], []
        )
    )
    assert doc["columns"][0]["src"] == "fhz"
    assert "key" not in doc["columns"][0]


def test_validation_emits_each_field_once_and_only_mapped_quantities() -> None:
    doc = yaml.safe_load(
        assemble_validation(
            SPEC, [_proposal("1", "A_Freq", quantity="frequency", phase="none", unit="Hz")], []
        )
    )
    not_null = [r["field"] for r in doc["rules"] if r["type"] == "not_null"]
    assert not_null.count("measurement_id") == 1, "key_field and row_id_field are the same field"
    ranges = [r["quantity"] for r in doc["rules"] if r["type"] == "range"]
    assert ranges == ["frequency"], "voltage was never mapped, so its rule does not belong"


def test_validation_says_so_when_no_thresholds_were_declared() -> None:
    bare = {k: v for k, v in SPEC.items() if k != "validation_defaults"}
    text = assemble_validation(
        bare, [_proposal("1", "A_Freq", quantity="frequency", phase="none", unit="Hz")], []
    )
    assert "must be authored" in text


# -------------------------------------------------------------------------------- gate


def _files(proposals: list[Proposal]) -> dict[str, str]:
    source = {k: v for k, v in SPEC.items() if k not in ("catalog", "validation_defaults")}
    source["fields"] = SPEC["long_fields"]
    source.pop("long_fields")
    source.pop("mapping_version")
    source.pop("target_schema_version")
    return {
        "source_schema.yaml": yaml.safe_dump(source),
        "mapping.yaml": assemble_mapping(SPEC, proposals, []),
        "validation.yaml": assemble_validation(SPEC, proposals, []),
        "CHANGELOG.md": "# test\n",
    }


def test_gate_accepts_a_sound_proposal(tmp_path: Path) -> None:
    good = [
        _proposal("1", "A_Freq", quantity="frequency", phase="none", unit="Hz"),
        _proposal("2", "A_UL1", quantity="voltage", phase="L1", unit="V"),
    ]
    assert stage_and_validate(ROOT, "test_vendor", _files(good), tmp_path) == []


def test_gate_rejects_two_points_that_collapse(tmp_path: Path) -> None:
    """The dominant model error: a fundamental component mapped as if it were the plain one.

    Point-wise scoring sees one wrong field. Proposing a whole catalog turns the same
    mistake into two source points sharing one canonical identity, which the no-collapse
    invariant refuses outright.
    """
    collapsing = [
        _proposal("1", "A_UL1", quantity="voltage", phase="L1", unit="V"),
        _proposal("2", "A_U1L1", quantity="voltage", phase="L1", unit="V"),
    ]
    errors = stage_and_validate(ROOT, "test_vendor", _files(collapsing), tmp_path)
    assert any("collapse" in e for e in errors)


def test_gate_rejects_an_out_of_vocabulary_quantity(tmp_path: Path) -> None:
    bad = [_proposal("1", "A_Udc1", quantity="dc_voltage", phase="none", unit="V")]
    errors = stage_and_validate(ROOT, "test_vendor", _files(bad), tmp_path)
    assert any("not in vocabulary" in e for e in errors)


def test_gate_rejects_fundamental_written_as_harmonic_order_one(tmp_path: Path) -> None:
    """Order 1 is the fundamental, not a harmonic; the meta-schema encodes that."""
    bad = [
        _proposal(
            "1", "A_U1L1", quantity="harmonic_voltage", phase="L1", unit="percent", harmonic_order=1
        )
    ]
    errors = stage_and_validate(ROOT, "test_vendor", _files(bad), tmp_path)
    assert any("minimum of 2" in e for e in errors)


def test_gate_leaves_the_real_vendors_directory_untouched(tmp_path: Path) -> None:
    before = sorted(p.name for p in (ROOT / "vendors").iterdir())
    stage_and_validate(
        ROOT,
        "test_vendor",
        _files([_proposal("1", "A_Freq", quantity="frequency", phase="none", unit="Hz")]),
        tmp_path,
    )
    assert sorted(p.name for p in (ROOT / "vendors").iterdir()) == before
