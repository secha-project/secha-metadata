"""Validate the secha-metadata repository.

Three layers:
1. JSON-Schema conformance of every config against its meta-schema.
2. Cross-file referential integrity: quantities/phases/units/transforms exist; mapping
   src fields exist in the source schema; transform args are complete AND known; scale
   factor fields exist in device_factors; harmonic quantities only via generated rules;
   record/defaults blocks reference real fields; golden fixtures conform to the vocabulary.
3. No-collapse: no two mapped columns share a canonical identity tuple.

Run directly (`python validate.py`) for CI, or via `pytest` (tests/ imports `validate`).
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).parent


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _schema_validate(instance, schema_path: Path, errors: list[str], label: str) -> None:
    validator = jsonschema.Draft202012Validator(_load_json(schema_path))
    for err in sorted(validator.iter_errors(instance), key=str):
        loc = "/".join(str(p) for p in err.path) or "<root>"
        errors.append(f"[schema] {label}: {loc}: {err.message}")


def _check_column(
    col: dict, ctx: dict, factor_fields: set[str], errors: list[str], label: str
) -> None:
    if col["quantity"] not in ctx["quantities"]:
        errors.append(f"[xref] {label}: quantity '{col['quantity']}' not in vocabulary")
    if col["phase"] not in ctx["phases"]:
        errors.append(f"[xref] {label}: phase '{col['phase']}' not a canonical phase")
    if col["unit"] not in ctx["units"]:
        errors.append(f"[xref] {label}: unit '{col['unit']}' not in unit registry")
    variant = col.get("variant", "none")
    if variant not in ctx["variants"]:
        errors.append(f"[xref] {label}: variant '{variant}' not a canonical variant")

    # quantities that REQUIRE harmonic_order can only come from generated rules — a
    # direct column has no way to set the order and would land rows with a null order
    quantity_meta = ctx["quantities_meta"].get(col["quantity"]) or {}
    if "harmonic_order" in (quantity_meta.get("requires") or []):
        errors.append(
            f"[xref] {label}: quantity '{col['quantity']}' requires harmonic_order; "
            "map it via a generated rule, not a direct column"
        )

    transform = col.get("transform", "none")
    rule = ctx["rules"].get(transform)
    if rule is None:
        errors.append(f"[xref] {label}: transform '{transform}' not in rule library")
        return
    params = rule.get("params") or {}
    required = {name for name, spec in params.items() if spec.get("required")}
    provided = set((col.get("args") or {}).keys())
    missing = required - provided
    if missing:
        errors.append(f"[xref] {label}: transform '{transform}' missing args {sorted(missing)}")
    unknown = provided - set(params)
    if unknown:
        # an ignored, typo'd arg (e.g. 'op_') would silently change behaviour downstream
        errors.append(f"[xref] {label}: transform '{transform}' has unknown args {sorted(unknown)}")

    # a typo'd factor_field would make the engine silently skip every affected column
    factor_field = (col.get("args") or {}).get("factor_field")
    if factor_field is not None and factor_field not in factor_fields:
        errors.append(
            f"[xref] {label}: factor_field '{factor_field}' not declared in "
            f"source_schema.device_factors (known: {sorted(factor_fields)})"
        )


def _check_source_blocks(source_schema: dict, ctx: dict, errors: list[str], label: str) -> None:
    """The engine-facing `record` and `defaults` blocks must reference real things."""
    field_names = {f["name"] for f in source_schema.get("fields", [])}

    duplicates = [
        name
        for name, n in Counter(f["name"] for f in source_schema.get("fields", [])).items()
        if n > 1
    ]
    if duplicates:
        errors.append(f"[xref] {label}: duplicate field names {sorted(duplicates)}")

    record = source_schema.get("record") or {}
    for key in ("meter_field", "timestamp_field", "row_id_field"):
        value = record.get(key)
        if value is not None and value not in field_names:
            errors.append(f"[xref] {label}: record.{key} '{value}' not in source_schema.fields")
    template = record.get("device_id_template")
    if template is not None:
        for placeholder in re.findall(r"\{(\w+)\}", template):
            if placeholder not in field_names:
                errors.append(
                    f"[xref] {label}: device_id_template placeholder "
                    f"'{{{placeholder}}}' not in source_schema.fields"
                )

    defaults = source_schema.get("defaults") or {}
    aggregation = defaults.get("aggregation")
    if aggregation is not None and aggregation not in ctx["aggregations"]:
        errors.append(f"[xref] {label}: defaults.aggregation '{aggregation}' not canonical")
    interval = defaults.get("interval_s")
    if interval is not None and not isinstance(interval, int):
        errors.append(f"[xref] {label}: defaults.interval_s must be an integer")


def _check_no_collapse(mapping: dict, errors: list[str], label: str) -> None:
    """No two mapped columns may share a canonical identity tuple.

    Identity = (quantity, phase, variant, harmonic_order, aggregation); two columns sharing it
    collapse into indistinguishable canonical rows. `aggregation` is not yet expressible per
    column, so it is held at None here; add it to the key once the mapping schema supports it.
    """
    seen: dict[tuple, list[str]] = {}

    def record(
        src: str, quantity: str, phase: str, variant: str, harmonic_order: int | None
    ) -> None:
        key = (quantity, phase, variant, harmonic_order, None)
        seen.setdefault(key, []).append(src)

    for col in mapping.get("columns", []):
        record(col["src"], col["quantity"], col["phase"], col.get("variant", "none"), None)
    for gen in mapping.get("generated", []):
        for order in gen["order"]:
            for idx, phase in gen["phase_map"].items():
                record(
                    gen["pattern"].format(order=order, p=idx), gen["quantity"], phase, "none", order
                )

    for (quantity, phase, variant, harmonic_order, _agg), sources in seen.items():
        if len(sources) > 1:
            errors.append(
                f"[collapse] {label}: {sorted(sources)} share identity "
                f"(quantity={quantity} phase={phase} variant={variant} order={harmonic_order}) "
                f"- indistinguishable in canonical"
            )


def _check_canonical_row(row: dict, ctx: dict, errors: list[str], label: str) -> None:
    required = [
        "source_vendor",
        "quantity",
        "phase",
        "variant",
        "value",
        "unit",
        "aggregation",
        "quality",
    ]
    for key in required:
        if key not in row:
            errors.append(f"[golden] {label}: missing required field '{key}'")
    for key, allowed in (
        ("quantity", ctx["quantities"]),
        ("phase", ctx["phases"]),
        ("unit", ctx["units"]),
        ("variant", ctx["variants"]),
        ("aggregation", ctx["aggregations"]),
        ("quality", ctx["qualities"]),
    ):
        if key in row and row[key] not in allowed:
            errors.append(f"[golden] {label}: {key} '{row[key]}' not allowed")
    if "value" in row and not isinstance(row["value"], int | float):
        errors.append(f"[golden] {label}: value must be numeric")


def validate() -> list[str]:
    errors: list[str] = []
    canon = _load_yaml(ROOT / "canonical" / "canonical_schema.yaml")
    vocab = _load_yaml(ROOT / "canonical" / "quantity_vocabulary.yaml")
    units = _load_yaml(ROOT / "canonical" / "units.yaml")
    library = _load_yaml(ROOT / "transforms" / "library.yaml")
    target = _load_yaml(ROOT / "targets" / "canonical.yaml")

    ctx = {
        "quantities": set(vocab["quantities"]),
        "quantities_meta": vocab["quantities"],
        "units": set(units["units"]),
        "phases": set(canon["enums"]["phase"]),
        "variants": set(canon["enums"]["variant"]),
        "aggregations": set(canon["enums"]["aggregation"]),
        "qualities": set(canon["enums"]["quality_flag"]),
        "rules": library["rules"],
    }
    entities = set(canon["entities"])

    if target["table"] not in entities:
        errors.append(f"[target] table '{target['table']}' is not a canonical entity")
    for name, cfg in (target.get("dimensions") or {}).items():
        if cfg["table"] not in entities:
            errors.append(f"[target] dimension '{name}' -> unknown entity '{cfg['table']}'")

    meta = ROOT / "meta-schemas"
    for vendor_dir in sorted((ROOT / "vendors").iterdir()):
        if not vendor_dir.is_dir():
            continue
        name = vendor_dir.name
        source_schema = _load_yaml(vendor_dir / "source_schema.yaml")
        mapping = _load_yaml(vendor_dir / "mapping.yaml")
        validation = _load_yaml(vendor_dir / "validation.yaml")

        _schema_validate(
            source_schema, meta / "source_schema.schema.json", errors, f"{name}/source_schema"
        )
        _schema_validate(mapping, meta / "mapping.schema.json", errors, f"{name}/mapping")
        _schema_validate(validation, meta / "validation.schema.json", errors, f"{name}/validation")

        field_names = {f["name"] for f in source_schema.get("fields", [])}
        factor_fields = set((source_schema.get("device_factors") or {}).values()) | {"uk_ik"}

        _check_source_blocks(source_schema, ctx, errors, f"{name}/source_schema")

        for col in mapping.get("columns", []):
            _check_column(col, ctx, factor_fields, errors, f"{name}/mapping[{col.get('src')}]")
            if col["src"] not in field_names:
                errors.append(
                    f"[xref] {name}/mapping: src '{col['src']}' not in source_schema.fields"
                )

        for gen in mapping.get("generated", []):
            if gen["quantity"] not in ctx["quantities"]:
                errors.append(f"[xref] {name}/mapping gen: quantity '{gen['quantity']}' unknown")
            if gen["unit"] not in ctx["units"]:
                errors.append(f"[xref] {name}/mapping generated: unit '{gen['unit']}' not in units")
            for phase in gen["phase_map"].values():
                if phase not in ctx["phases"]:
                    errors.append(
                        f"[xref] {name}/mapping generated: phase '{phase}' not a canonical phase"
                    )
            for order in gen["order"]:
                for idx in gen["phase_map"]:
                    field = gen["pattern"].format(order=order, p=idx)
                    if field not in field_names:
                        errors.append(
                            f"[xref] {name}/mapping gen: field '{field}' not in source_schema"
                        )

        _check_no_collapse(mapping, errors, f"{name}/mapping")

        for rule in validation.get("rules", []):
            quantity = rule.get("quantity")
            if quantity is not None and quantity not in ctx["quantities"]:
                errors.append(f"[xref] {name}/validation: quantity '{quantity}' not in vocabulary")

        golden = ROOT / "tests" / "fixtures" / name / "expected_canonical.json"
        if golden.exists():
            for i, row in enumerate(_load_json(golden)):
                _check_canonical_row(row, ctx, errors, f"{name} golden[{i}]")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print(f"FAILED: {len(errors)} problem(s):")
        for err in errors:
            print("  -", err)
        return 1
    print("OK: all metadata configs valid and cross-referenced.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
