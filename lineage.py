"""Generate a human-readable source -> canonical lineage table per vendor, from the configs.

For each vendor it answers, in one place: what each source field *means* (verbatim vendor text),
which canonical quantity/phase/unit it maps to, the transform applied, and the aligned standard.

Usage:
    python lineage.py            # (re)write docs/lineage_<vendor>.md for every vendor
    python lineage.py --check    # exit non-zero if any generated doc is stale (CI drift guard)
"""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
HEADER = (
    "| Source field | Meaning (vendor) | Canonical quantity | Phase | Unit | Transform | Standard |"
)
SEP = "|---|---|---|---|---|---|---|"


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _transform_str(col: dict) -> str:
    transform = col.get("transform", "none")
    args = col.get("args") or {}
    if args:
        return f"{transform}({', '.join(str(v) for v in args.values())})"
    return transform


def _std_ref(vocab: dict, quantity: str) -> str:
    return (vocab["quantities"].get(quantity) or {}).get("standard_ref", "")


def _rows(vendor_dir: Path, vocab: dict) -> tuple[dict, list[tuple[str, ...]]]:
    source_schema = _load(vendor_dir / "source_schema.yaml")
    mapping = _load(vendor_dir / "mapping.yaml")
    desc_by_field = {f["name"]: f.get("desc", "") for f in source_schema.get("fields", [])}

    rows: list[tuple[str, ...]] = []
    for col in mapping.get("columns", []):
        rows.append(
            (
                col["src"],
                desc_by_field.get(col["src"], ""),
                col["quantity"],
                col["phase"],
                col["unit"],
                _transform_str(col),
                _std_ref(vocab, col["quantity"]),
            )
        )
    for gen in mapping.get("generated", []):
        std = _std_ref(vocab, gen["quantity"])
        for order in gen["order"]:
            for idx, phase in gen["phase_map"].items():
                field = gen["pattern"].format(order=order, p=idx)
                rows.append(
                    (
                        field,
                        desc_by_field.get(field, ""),
                        f"{gen['quantity']} (order {order})",
                        phase,
                        gen["unit"],
                        "none",
                        std,
                    )
                )
    return mapping, rows


def _render(vendor: str, mapping: dict, rows: list[tuple[str, ...]]) -> str:
    lines = [
        f"# Lineage — {vendor}",
        "",
        f"Source `{mapping.get('source')}` · mapping_version `{mapping.get('mapping_version')}`.",
        "Generated from `secha-metadata` configs by `lineage.py` — **do not edit by hand**.",
        "",
        HEADER,
        SEP,
    ]
    for src, meaning, quantity, phase, unit, transform, std in rows:
        lines.append(
            f"| `{src}` | {meaning} | `{quantity}` | {phase} | {unit} | {transform} | {std} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def generate() -> dict[str, str]:
    vocab = _load(ROOT / "canonical" / "quantity_vocabulary.yaml")
    outputs: dict[str, str] = {}
    for vendor_dir in sorted((ROOT / "vendors").iterdir()):
        if not vendor_dir.is_dir():
            continue
        mapping, rows = _rows(vendor_dir, vocab)
        outputs[vendor_dir.name] = _render(vendor_dir.name, mapping, rows)
    return outputs


def main(argv: list[str]) -> int:
    check = "--check" in argv
    DOCS.mkdir(exist_ok=True)
    stale: list[str] = []
    for vendor, content in generate().items():
        path = DOCS / f"lineage_{vendor}.md"
        if check:
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != content:
                stale.append(vendor)
        else:
            path.write_text(content, encoding="utf-8")
    if check and stale:
        print("STALE lineage docs:", ", ".join(stale), "- run: python lineage.py")
        return 1
    print("lineage docs " + ("up to date" if check else "generated"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
