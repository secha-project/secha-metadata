"""Build the workbook a domain expert fills in when reviewing a vendor's mappings.

`docs/lineage_<vendor>.md` already states what each source point becomes. A reviewer
needs the same content in a form they can answer in: one row per mapped point with a
verdict beside it, the catalog points we did not map, and the limits we chose for
flagging implausible readings. This writes that workbook from the configs, so the
questions asked always match what the engine actually does.

The mapping columns come from the same helpers `lineage.py` uses, so the workbook and
the generated lineage table can never describe an entry differently.

`openpyxl` is imported lazily and is not a dependency of the CI-gated contract
(validate, lineage, tests), which keeps that footprint at two packages.

Usage:
    python review_sheet.py --out ../review              # every vendor
    python review_sheet.py --vendor mx_electrix
    python review_sheet.py --vendor procem_kampusareena_pq --catalog <catalog.csv>

Without a catalog the workbook still lists the mappings; the "Not mapped" sheet is
then limited to what the source schema itself declares.
"""

import argparse
import csv
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

# Shared with the generated lineage table on purpose: one description per entry.
from lineage import _load, _std_ref, _transform_str

ROOT = Path(__file__).parent

MAPPING_COLUMNS = [
    ("#", 5),
    ("Source point", 16),
    ("Vendor's own name", 30),
    ("Source unit", 11),
    ("Canonical quantity", 24),
    ("Phase", 10),
    ("Variant", 12),
    ("Harmonic order", 13),
    ("Canonical unit", 13),
    ("Aggregation", 14),
    ("Transform", 22),
    ("Standard reference", 34),
    ("Correct?", 11),
    ("If not, what should it be?", 30),
    ("Comment", 38),
]
UNMAPPED_COLUMNS = [
    ("#", 5),
    ("Source point", 16),
    ("Vendor's own name", 34),
    ("Where the vendor files it", 34),
    ("Source unit", 11),
    ("Why it is not mapped", 32),
    ("Do you need it?", 14),
    ("Comment", 38),
]
LIMIT_COLUMNS = [
    ("Applies to", 20),
    ("Check", 12),
    ("Minimum", 10),
    ("Maximum", 10),
    ("What happens on failure", 34),
    ("In plain words", 46),
    ("Is this right?", 13),
    ("Suggested limit", 16),
    ("Comment", 38),
]
VOCABULARY_COLUMNS = [
    ("Canonical quantity", 30),
    ("Default unit", 13),
    ("What it means", 56),
    ("Standard reference", 40),
]
QUESTION_COLUMNS = [
    ("Question", 62),
    ("Why we are asking", 62),
    ("Your answer", 34),
    ("Comment", 38),
]
VERDICT = '"yes,no,unsure"'
ON_FAIL_PLAIN = {
    "flag_suspect": "the reading is kept and marked suspect",
    "drop_row": "that single reading is dropped and counted",
    "reject_row": "the whole record is rejected and counted",
}


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def read_catalog(path: Path | None) -> dict[str, dict[str, str]]:
    """The vendor's own catalog export, keyed by the id the mapping refers to."""
    if path is None or not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return {}
    delimiter = ";" if lines[0].count(";") >= lines[0].count(",") else ","
    rows = list(csv.DictReader(lines, delimiter=delimiter))
    if not rows:
        return {}
    key_column = next(
        (c for c in rows[0] if c and c.lower() in {"rtl_id", "id", "key"}), None
    )
    if key_column is None:
        return {}
    return {(row.get(key_column) or "").strip(): row for row in rows}


def open_questions(vendor: str) -> list[list[str]]:
    """Questions for this vendor, from review_questions.yaml, if that file exists."""
    path = ROOT / "review_questions.yaml"
    if not path.exists():
        return []
    entries = (_load(path) or {}).get("questions") or []
    return [
        [entry["question"].strip(), entry["why"].strip()]
        for entry in entries
        if vendor in (entry.get("vendors") or [])
    ]


def spec_for(vendor: str) -> dict[str, Any]:
    path = ROOT / "specs" / f"{vendor}.spec.yaml"
    return _load(path) if path.exists() else {}


def mapped_entries(
    vendor_dir: Path, vocab: dict, catalog: dict[str, dict[str, str]]
) -> tuple[dict, list[list[Any]]]:
    """One row per mapped point, in the order the engine reads them."""
    source_schema = _load(vendor_dir / "source_schema.yaml")
    mapping = _load(vendor_dir / "mapping.yaml")
    fields = {f["name"]: f for f in source_schema.get("fields", [])}
    default_aggregation = (source_schema.get("defaults") or {}).get("aggregation", "instantaneous")

    def entry_row(source: str, name: str, unit: str, entry: dict, quantity: str) -> list[Any]:
        return [
            source,
            name,
            unit,
            quantity,
            entry.get("phase", ""),
            entry.get("variant", "none"),
            entry.get("harmonic_order", ""),
            entry.get("unit", ""),
            entry.get("aggregation", default_aggregation),
            _transform_str(entry),
            _std_ref(vocab, quantity),
        ]

    rows: list[list[Any]] = []
    for column in mapping.get("columns", []):
        field = fields.get(column["src"], {})
        rows.append(
            entry_row(
                column["src"],
                field.get("desc", ""),
                field.get("unit") or "",
                column,
                column["quantity"],
            )
        )
    for rule in mapping.get("generated", []):
        for order in rule["order"]:
            for index, phase in rule["phase_map"].items():
                source = rule["pattern"].format(order=order, p=index)
                field = fields.get(source, {})
                built = entry_row(
                    source,
                    field.get("desc", ""),
                    field.get("unit") or "",
                    {"phase": phase, "harmonic_order": order, "unit": rule["unit"]},
                    rule["quantity"],
                )
                built[9] = f"none (field named by rule {rule['pattern']})"
                rows.append(built)
    for entry in mapping.get("rows", []):
        key = str(entry["key"])
        rows.append(
            entry_row(
                f"rtl {key}",
                entry.get("desc", ""),
                (catalog.get(key, {}).get("unit") or "").strip(),
                entry,
                entry["quantity"],
            )
        )
    return mapping, rows


def unmapped_points(
    vendor: str, vendor_dir: Path, catalog: dict[str, dict[str, str]]
) -> list[list[str]]:
    """Points the vendor offers that no mapping entry claims."""
    source_schema = _load(vendor_dir / "source_schema.yaml")
    mapping = _load(vendor_dir / "mapping.yaml")
    exclude = (spec_for(vendor).get("catalog") or {}).get("exclude_pattern")
    pattern = re.compile(exclude) if exclude else None

    if mapping.get("rows"):
        claimed = {str(entry["key"]) for entry in mapping["rows"]}
        rows = []
        for key, entry in catalog.items():
            if not key or key in claimed:
                continue
            name = (entry.get("name") or "").strip()
            reason = (
                f"left out on purpose: names matching {exclude} have no canonical quantity yet"
                if pattern and pattern.search(name)
                else "not mapped yet"
            )
            rows.append(
                [
                    f"rtl {key}",
                    name,
                    (entry.get("path") or "").strip(),
                    (entry.get("unit") or "").strip(),
                    reason,
                ]
            )
        return sorted(rows, key=lambda row: row[1])

    record = source_schema.get("record") or {}
    used = {column["src"] for column in mapping.get("columns", [])}
    for rule in mapping.get("generated", []):
        for order in rule["order"]:
            for index in rule["phase_map"]:
                used.add(rule["pattern"].format(order=order, p=index))
    structural = {value for key, value in record.items() if key.endswith("_field")}
    return [
        [field["name"], field.get("desc", ""), "", field.get("unit") or "", "not mapped yet"]
        for field in source_schema.get("fields", [])
        if field["name"] not in used and field["name"] not in structural
    ]


def _missing_field_plain(rule: dict, applies: str, roles: dict[str, str]) -> str:
    role = roles.get(applies, "")
    if rule.get("entity") == "measurement" or role == "value_field":
        return "a reading with no value carries no measurement"
    if role == "timestamp_field":
        return "a reading with no timestamp cannot be placed in time"
    if role in {"meter_field", "key_field"}:
        return f"a record with no {applies} cannot be attributed to a device or a point"
    return f"a record with no {applies} is incomplete"


def validation_limits(vendor_dir: Path) -> list[list[Any]]:
    """The checks we apply before a reading is trusted, in plain words."""
    record = (_load(vendor_dir / "source_schema.yaml").get("record") or {}).items()
    roles = {value: key for key, value in record if key.endswith("_field")}
    rows: list[list[Any]] = []
    for rule in _load(vendor_dir / "validation.yaml").get("rules", []):
        applies = rule.get("quantity") or rule.get("field", "")
        if rule["type"] == "range":
            plain = (
                f"a {applies} reading below {rule.get('min')} or above {rule.get('max')} "
                "is treated as implausible"
            )
        else:
            plain = _missing_field_plain(rule, applies, roles)
        rows.append(
            [
                applies,
                rule["type"],
                rule.get("min", ""),
                rule.get("max", ""),
                ON_FAIL_PLAIN.get(rule.get("on_fail", ""), rule.get("on_fail", "")),
                plain,
            ]
        )
    return rows


# --------------------------------------------------------------------------- workbook


def _header(sheet, columns: list[tuple[str, int]], freeze: str = "A2") -> None:
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    fill = PatternFill("solid", fgColor="EDEDED")
    border = Border(bottom=Side(style="thin", color="999999"))
    for index, (name, width) in enumerate(columns, start=1):
        cell = sheet.cell(row=1, column=index, value=name)
        cell.font = Font(bold=True)
        cell.fill = fill
        cell.border = border
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = freeze


def _finish(sheet, columns: list[tuple[str, int]], verdict_column: str | None = None) -> None:
    from openpyxl.styles import Alignment
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    last_column = get_column_letter(len(columns))
    sheet.auto_filter.ref = f"A1:{last_column}{max(sheet.max_row, 1)}"
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    if verdict_column and sheet.max_row > 1:
        validation = DataValidation(type="list", formula1=VERDICT, allowBlank=True)
        sheet.add_data_validation(validation)
        validation.add(f"{verdict_column}2:{verdict_column}{sheet.max_row}")


def _guide_sheet(sheet, vendor: str, mapping: dict, mapped: int, missing: int) -> None:
    from openpyxl.styles import Alignment, Font

    sheet.column_dimensions["A"].width = 26
    sheet.column_dimensions["B"].width = 96
    lines = [
        ("Mapping review", vendor),
        ("", ""),
        (
            "What this file is",
            "Every measurement point we read from this source, and what we turned it into."
            " It is generated from the configuration, so it matches what the pipeline does"
            " today.",
        ),
        (
            "What would help",
            "A look through the Mappings sheet, and a mark in Correct? wherever something"
            " looks wrong or unclear, with a note if you have one. There is no need to go"
            " through every row, and unsure is a useful answer.",
        ),
        (
            "If you have a view",
            "Not mapped lists the points we do not carry, Validation limits the bounds we"
            " chose, and Open questions the few decisions we cannot make ourselves. Answer"
            " what you have an opinion on and leave the rest.",
        ),
        (
            "What we do with it",
            "Your answers become changes to the configuration, reviewed and version"
            " controlled, and they are cited in the thesis as the domain expert review.",
        ),
        ("Out of scope here", "Analysis methods, and how the data is stored on the platform."),
        ("", ""),
        ("Reviewer", ""),
        ("Date reviewed", ""),
        ("", ""),
        ("Vendor", vendor),
        ("Source", str(mapping.get("source", ""))),
        ("Mapping version", str(mapping.get("mapping_version", ""))),
        ("Canonical schema", str(mapping.get("target_schema_version", ""))),
        ("Configuration commit", _git_commit()),
        ("Generated", date.today().isoformat()),
        ("Mapped points", str(mapped)),
        ("Points not mapped", str(missing)),
    ]
    for index, (label, value) in enumerate(lines, start=1):
        left = sheet.cell(row=index, column=1, value=label)
        left.font = Font(bold=True)
        left.alignment = Alignment(vertical="top")
        right = sheet.cell(row=index, column=2, value=value)
        right.alignment = Alignment(vertical="top", wrap_text=True)
    sheet.cell(row=1, column=1).font = Font(bold=True, size=14)
    sheet.cell(row=1, column=2).font = Font(bold=True, size=14)


def build_workbook(vendor: str, catalog_path: Path | None, out_dir: Path) -> Path:
    from openpyxl import Workbook

    vocab = _load(ROOT / "canonical" / "quantity_vocabulary.yaml")
    vendor_dir = ROOT / "vendors" / vendor
    catalog = read_catalog(catalog_path)
    mapping, entries = mapped_entries(vendor_dir, vocab, catalog)
    missing = unmapped_points(vendor, vendor_dir, catalog)
    limits = validation_limits(vendor_dir)

    book = Workbook()
    _guide_sheet(book.active, vendor, mapping, len(entries), len(missing))
    book.active.title = "How to review"

    sheet = book.create_sheet("Mappings")
    _header(sheet, MAPPING_COLUMNS, freeze="C2")
    for number, entry in enumerate(entries, start=1):
        sheet.append([number, *entry, "", "", ""])
    _finish(sheet, MAPPING_COLUMNS, "M")

    sheet = book.create_sheet("Not mapped")
    _header(sheet, UNMAPPED_COLUMNS, freeze="C2")
    for number, entry in enumerate(missing, start=1):
        sheet.append([number, *entry, "", ""])
    if not missing:
        sheet.append(["", "Every point this source declares is mapped.", "", "", "", "", "", ""])
    _finish(sheet, UNMAPPED_COLUMNS, "G" if missing else None)

    sheet = book.create_sheet("Validation limits")
    _header(sheet, LIMIT_COLUMNS)
    for entry in limits:
        sheet.append([*entry, "", "", ""])
    _finish(sheet, LIMIT_COLUMNS, "G")

    questions = open_questions(vendor)
    if questions:
        sheet = book.create_sheet("Open questions")
        _header(sheet, QUESTION_COLUMNS)
        for question in questions:
            sheet.append([*question, "", ""])
        _finish(sheet, QUESTION_COLUMNS)

    sheet = book.create_sheet("Canonical vocabulary")
    _header(sheet, VOCABULARY_COLUMNS)
    for name, meta in vocab["quantities"].items():
        sheet.append(
            [
                name,
                meta.get("default_unit", ""),
                meta.get("description", ""),
                meta.get("standard_ref", ""),
            ]
        )
    _finish(sheet, VOCABULARY_COLUMNS)

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"SECHA_mapping_review_{vendor}_{date.today().isoformat()}.xlsx"
    book.save(path)
    return path


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--vendor", help="one vendor (default: every vendor)")
    parser.add_argument("--catalog", type=Path, help="the vendor's own catalog export")
    parser.add_argument("--out", type=Path, default=ROOT / "review")
    args = parser.parse_args(argv)

    vendors = (
        [args.vendor]
        if args.vendor
        else [d.name for d in sorted((ROOT / "vendors").iterdir()) if d.is_dir()]
    )
    for vendor in vendors:
        catalog = args.catalog
        if catalog is None:
            declared = (spec_for(vendor).get("catalog") or {}).get("path")
            if declared:
                catalog = (ROOT / "specs" / declared).resolve()
        print(f"written: {build_workbook(vendor, catalog, args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
