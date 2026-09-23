"""Unit tests for the validator's cross-reference guards (synthetic configs)."""

from pathlib import Path

from validate import (
    _check_column,
    _check_no_collapse,
    _check_reference_dimensions,
    _check_serving_views,
    _check_source_blocks,
)

CTX = {
    "quantities": {"voltage", "harmonic_voltage"},
    "quantities_meta": {
        "voltage": {"default_unit": "V"},
        "harmonic_voltage": {"default_unit": "percent", "requires": ["harmonic_order"]},
    },
    "phases": {"L1", "none"},
    "variants": {"none"},
    "aggregations": {"average", "instantaneous"},
    "qualities": {"ok"},
    "units": {"V", "percent"},
    "rules": {
        "none": {"params": {}},
        "scale_by_factor": {
            "params": {
                "factor_field": {"type": "string", "required": True},
                "op": {"type": "enum", "required": False},
            }
        },
    },
}
FACTORS = {"uk", "ik", "uk_ik"}


def _column_errors(col: dict) -> list[str]:
    errors: list[str] = []
    _check_column(col, CTX, FACTORS, errors, "t")
    return errors


def test_valid_scaled_column_passes() -> None:
    col = {
        "src": "v",
        "quantity": "voltage",
        "phase": "L1",
        "unit": "V",
        "transform": "scale_by_factor",
        "args": {"factor_field": "uk"},
    }
    assert _column_errors(col) == []


def test_typoed_factor_field_is_caught() -> None:
    """A bad factor_field would make the engine silently drop every affected column."""
    col = {
        "src": "v",
        "quantity": "voltage",
        "phase": "L1",
        "unit": "V",
        "transform": "scale_by_factor",
        "args": {"factor_field": "uk2"},
    }
    assert any("factor_field 'uk2'" in e for e in _column_errors(col))


def test_unknown_transform_arg_is_caught() -> None:
    """A typo'd arg (e.g. op_) would be silently ignored and change behaviour."""
    col = {
        "src": "v",
        "quantity": "voltage",
        "phase": "L1",
        "unit": "V",
        "transform": "scale_by_factor",
        "args": {"factor_field": "uk", "op_": "divide"},
    }
    assert any("unknown args ['op_']" in e for e in _column_errors(col))


def test_harmonic_quantity_forbidden_in_direct_column() -> None:
    """Direct columns cannot express harmonic_order; rows would land with a null order."""
    col = {"src": "u3l1", "quantity": "harmonic_voltage", "phase": "L1", "unit": "percent"}
    assert any("requires harmonic_order" in e for e in _column_errors(col))


def _source_errors(source_schema: dict) -> list[str]:
    errors: list[str] = []
    _check_source_blocks(source_schema, CTX, errors, "t")
    return errors


def test_record_field_typo_is_caught() -> None:
    """A typo'd timestamp_field would silently null every row's timestamp."""
    schema = {
        "fields": [{"name": "meter", "type": "int"}, {"name": "timestamp", "type": "string"}],
        "record": {"meter_field": "meter", "timestamp_field": "timestmap"},
    }
    assert any("record.timestamp_field 'timestmap'" in e for e in _source_errors(schema))


def test_device_id_template_placeholder_is_checked() -> None:
    """An unknown placeholder would crash the engine at runtime; catch it in CI instead."""
    schema = {
        "fields": [{"name": "meter", "type": "int"}],
        "record": {"device_id_template": "v:meter:{metre}"},
    }
    assert any("placeholder '{metre}'" in e for e in _source_errors(schema))


def test_non_canonical_default_aggregation_is_caught() -> None:
    schema = {"fields": [], "defaults": {"aggregation": "avg"}}
    assert any("defaults.aggregation 'avg'" in e for e in _source_errors(schema))


def test_duplicate_field_names_are_caught() -> None:
    schema = {"fields": [{"name": "fhz", "type": "float"}, {"name": "fhz", "type": "float"}]}
    assert any("duplicate field names" in e for e in _source_errors(schema))


# --- long-shape (`rows:`) guards -------------------------------------------------------


def test_rows_entry_with_harmonic_order_passes() -> None:
    """Long `rows:` entries carry harmonic_order explicitly; that satisfies `requires`."""
    entry = {
        "key": "23542",
        "quantity": "harmonic_voltage",
        "phase": "L1",
        "harmonic_order": 3,
        "unit": "percent",
    }
    assert _column_errors(entry) == []


def test_harmonic_order_on_nonharmonic_quantity_is_caught() -> None:
    """A meaningless harmonic_order (e.g. on plain voltage) is a config bug."""
    entry = {"key": "23524", "quantity": "voltage", "phase": "L1", "harmonic_order": 3, "unit": "V"}
    assert any("does not use it" in e for e in _column_errors(entry))


def test_noncanonical_row_aggregation_is_caught() -> None:
    """Per-row aggregation overrides must come from the canonical enum."""
    entry = {
        "key": "23944",
        "quantity": "voltage",
        "phase": "L1",
        "aggregation": "cnt",
        "unit": "V",
    }
    assert any("aggregation 'cnt' not canonical" in e for e in _column_errors(entry))


def test_long_shape_requires_record_interpretation_fields() -> None:
    """A long source cannot be interpreted without key/value/timestamp fields."""
    schema = {
        "shape": "long",
        "fields": [{"name": "measurement_id", "type": "long"}],
        "record": {"key_field": "measurement_id"},
    }
    errors = _source_errors(schema)
    assert any("requires record.value_field" in e for e in errors)
    assert any("requires record.timestamp_field" in e for e in errors)


# --- session sources (charging sessions, no clock time) ----------------------------------

SESSION_CTX = {**CTX, "session_attributes": {"ev_model", "country", "cal_year"}}
SESSION_FIELDS = [
    {"name": "transactionId", "type": "string"},
    {"name": "offset", "type": "int"},
    {"name": "EVModel", "type": "string"},
]


def _session_errors(source_schema: dict) -> list[str]:
    errors: list[str] = []
    _check_source_blocks({"fields": SESSION_FIELDS, **source_schema}, SESSION_CTX, errors, "t")
    return errors


def test_valid_session_block_passes() -> None:
    session = {"id_field": "transactionId", "offset_field": "offset"}
    session["attributes"] = {"ev_model": "EVModel"}
    assert _session_errors({"session": session}) == []


def test_session_field_typo_is_caught() -> None:
    """A typo'd offset field would leave every reading without its place in the session."""
    errors = _session_errors({"session": {"id_field": "transactionId", "offset_field": "ofset"}})
    assert any("session.offset_field 'ofset'" in e for e in errors)


def test_session_attribute_must_be_a_charging_session_field() -> None:
    """An attribute the entity does not have would be dropped silently by the engine."""
    session = {"id_field": "transactionId", "attributes": {"ev_modle": "EVModel"}}
    errors = _session_errors({"session": session})
    assert any("'ev_modle' is not a charging_session field" in e for e in errors)


def test_session_attribute_must_read_a_real_field() -> None:
    session = {"id_field": "transactionId", "attributes": {"country": "Country"}}
    errors = _session_errors({"session": session})
    assert any("reads 'Country'" in e for e in errors)


def test_a_row_has_one_identity() -> None:
    """A row key and a positional id together would make the identity ambiguous."""
    record = {"row_id_field": "transactionId", "row_id_from": "payload_position"}
    assert any("are exclusive" in e for e in _session_errors({"record": record}))


def test_wide_columns_differing_only_in_aggregation_do_not_collapse() -> None:
    """A sampled and an averaged reading of one quantity are distinct canonical rows."""
    mapping = {
        "columns": [
            {"src": "u", "quantity": "voltage", "phase": "L1", "unit": "V"},
            {"src": "u_inst", "quantity": "voltage", "phase": "L1", "unit": "V"},
        ]
    }
    errors: list[str] = []
    _check_no_collapse(mapping, errors, "t")
    assert any("[collapse]" in e for e in errors)

    mapping["columns"][1]["aggregation"] = "instantaneous"
    errors = []
    _check_no_collapse(mapping, errors, "t")
    assert errors == []


# --- serving-view guards ----------------------------------------------------------------


def _serving_errors(tmp_path: Path, body: str, target: dict | None = None) -> list[str]:
    (tmp_path / "view_under_test.sql").write_text(body, encoding="utf-8")
    errors: list[str] = []
    if target is None:  # an empty dict is a meaningful target here, so no `or` default
        target = {"serving_schema": "serving"}
    _check_serving_views(tmp_path, target, errors)
    return errors


def test_valid_serving_view_passes(tmp_path: Path) -> None:
    body = "-- comment\nSELECT device_id, avg(value) FROM {canonical} GROUP BY device_id\n"
    assert _serving_errors(tmp_path, body) == []


def test_empty_serving_view_is_caught(tmp_path: Path) -> None:
    assert any("empty view body" in e for e in _serving_errors(tmp_path, "-- only comments\n"))


def test_non_select_serving_view_is_caught(tmp_path: Path) -> None:
    """DDL/DML hiding in a view file must never reach the platform."""
    errors = _serving_errors(tmp_path, "DROP TABLE {canonical}")
    assert any("must be a single SELECT" in e for e in errors)


def test_hardcoded_table_path_is_caught(tmp_path: Path) -> None:
    """Views must go through the {canonical} placeholder, staying platform-portable."""
    errors = _serving_errors(tmp_path, "SELECT * FROM secha.canonical.measurement")
    assert any("{canonical} placeholder" in e for e in errors)


def test_serving_views_require_serving_schema(tmp_path: Path) -> None:
    body = "SELECT * FROM {canonical}"
    errors = _serving_errors(tmp_path, body, target={})
    assert any("no serving_schema" in e for e in errors)


def test_unknown_serving_mode_is_caught(tmp_path: Path) -> None:
    body = "SELECT * FROM {canonical}"
    target = {"serving_schema": "serving", "serving_mode": "materialized"}
    errors = _serving_errors(tmp_path, body, target=target)
    assert any("unknown serving_mode" in e for e in errors)


# --- reference-dimension guards ---------------------------------------------------------

_VOCABS = {
    "quantities": {
        "voltage": {"default_unit": "V", "standard_ref": "IEC ...", "description": "RMS voltage"},
        "frequency": {"default_unit": "Hz", "standard_ref": "IEC ...", "description": "Frequency"},
    }
}


def _refdim_errors(target: dict) -> list[str]:
    errors: list[str] = []
    _check_reference_dimensions(target, _VOCABS, errors)
    return errors


def test_valid_reference_dimension_passes() -> None:
    target = {
        "reference_dimensions": {
            "quantity": {
                "source_vocabulary": "quantities",
                "columns": [
                    {"name": "quantity", "from": "__key__"},
                    {"name": "default_unit", "from": "default_unit"},
                    {"name": "description", "from": "description"},
                ],
            }
        }
    }
    assert _refdim_errors(target) == []


def test_reference_dimension_unknown_vocabulary_is_caught() -> None:
    target = {"reference_dimensions": {"q": {"source_vocabulary": "quanta", "columns": []}}}
    assert any("not a known vocabulary" in e for e in _refdim_errors(target))


def test_reference_dimension_dangling_attribute_is_caught() -> None:
    """A column mapping from an attribute no entry has would publish an all-null column."""
    target = {
        "reference_dimensions": {
            "quantity": {
                "source_vocabulary": "quantities",
                "columns": [{"name": "note", "from": "annotation"}],
            }
        }
    }
    assert any("which no 'quantities' entry has" in e for e in _refdim_errors(target))
