"""Unit tests for the validator's cross-reference guards (synthetic configs, no disk)."""

from validate import _check_column, _check_source_blocks

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
