"""Score the sealed Kempower proposals against the hand-authored rulebook (see PROTOCOL.md).

This file was written and sealed before any proposal was opened and before the Kempower
rulebook existed, so the analysis is fixed ahead of the result. It refuses to run if a
proposal differs from its seal or if the rulebook in vendors/kempower/ is not committed.

Each proposed column is put in one class by what the rulebook (the gold) does with it:

  A  the gold maps it using only vocabulary that existed when the draft was made, so the
     draft could have been right. Scored exactly as the mapping benchmark scores: six
     fields after the engine's defaults. "strict" is the benchmark's definition, where an
     omitted aggregation only matches an omitted one; "effective" compares aggregation
     after inheriting the source default, which is what the engine writes.
  B  the gold needs vocabulary added for Kempower (a quantity, phase, variant, unit or
     aggregation the draft was never offered). The draft cannot be right; what matters is
     how it fails: not mapped, invented (a value outside the vocabulary it was given), or
     force-fit (valid against that vocabulary, therefore silently wrong).
  C  the gold leaves it unmapped. A draft entry is a false mapping.

Correction effort is the number of edits that turn the draft into the gold: fields
changed on entries both map, entries added, and entries removed.

Usage (from the repository root):
    python experiments/kempower_heldout/score.py
"""

import argparse
import hashlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

import propose  # noqa: E402  (repo root on the path above)
import validate as rulebook  # noqa: E402

SCORED = ("quantity", "phase", "variant", "harmonic_order", "aggregation", "unit")
FACTOR_FIELDS = {"uk", "ik", "uk_ik"}
# The vocabulary each condition was run against. C0 and C1 were drafted before any
# Kempower vocabulary existed; C2 is drafted against the vocabulary the rulebook adds.
BASELINE_REF = "cd564b9cb0bb8392e7d14ae3b2efc3e7f53f76de"
VOCAB_REF_BY_CONDITION = {"C0": BASELINE_REF, "C1": BASELINE_REF, "C2": "HEAD"}
SPEC_BY_CONDITION = {
    "C0": HERE / "kempower.no-convention.spec.yaml",
    "C1": REPO / "specs" / "kempower.spec.yaml",
    "C2": REPO / "specs" / "kempower.spec.yaml",
}
_SEAL_LINE = re.compile(r"^([0-9a-f]{64})  (.+)$")


# ---------------------------------------------------------------------------- inputs


def _yaml_text(text: str) -> dict[str, Any]:
    return yaml.safe_load(text) or {}


def read_at(ref: str, relpath: str) -> dict[str, Any]:
    """A rulebook file at a git revision, or from a directory when ref is a path."""
    as_dir = Path(ref)
    if as_dir.is_dir():
        return _yaml_text((as_dir / relpath).read_text(encoding="utf-8"))
    shown = subprocess.run(
        ["git", "show", f"{ref}:{relpath}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return _yaml_text(shown.stdout)


def vocabulary_context(ref: str) -> dict[str, Any]:
    """The context validate._check_column expects, built from the vocabulary at `ref`."""
    canonical = read_at(ref, "canonical/canonical_schema.yaml")
    vocab = read_at(ref, "canonical/quantity_vocabulary.yaml")
    units = read_at(ref, "canonical/units.yaml")
    library = read_at(ref, "transforms/library.yaml")
    return {
        "quantities": set(vocab["quantities"]),
        "quantities_meta": vocab["quantities"],
        "units": set(units["units"]),
        "phases": set(canonical["enums"]["phase"]),
        "variants": set(canonical["enums"]["variant"]),
        "aggregations": set(canonical["enums"]["aggregation"]),
        "qualities": set(canonical["enums"]["quality_flag"]),
        "rules": library["rules"],
    }


def load_seals(path: Path) -> dict[str, str]:
    """Latest digest per path. A later seal of the same path supersedes an earlier one."""
    seals: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _SEAL_LINE.match(line.strip())
        if match:
            seals[match.group(2)] = match.group(1)
    return seals


def check_seals(run_dirs: list[Path], seals: dict[str, str]) -> list[str]:
    """Every file in a scored run must be sealed, and unchanged since."""
    problems: list[str] = []
    for run_dir in run_dirs:
        for file in sorted(p for p in run_dir.rglob("*") if p.is_file()):
            rel = Path(os.path.relpath(file, REPO)).as_posix()
            want = seals.get(rel)
            if want is None:
                problems.append(f"not sealed: {rel}")
            elif want != hashlib.sha256(file.read_bytes()).hexdigest():
                problems.append(f"changed since sealed: {rel}")
    return problems


def gold_is_committed(gold: Path) -> str:
    """The commit that holds the gold, or an explanation of why there is none."""
    rel = Path(os.path.relpath(gold, REPO)).as_posix()
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", rel], cwd=REPO, capture_output=True, text=True
    ).stdout.strip()
    if dirty:
        raise SystemExit(f"{rel} has uncommitted changes; commit the rulebook before scoring")
    commit = subprocess.run(
        ["git", "log", "-1", "--format=%H %cI", "--", rel],
        cwd=REPO,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not commit:
        raise SystemExit(f"{rel} is not in any commit; commit the rulebook before scoring")
    return commit


# --------------------------------------------------------------------------- scoring


def normalise(entry: dict[str, Any] | None, default_aggregation: str | None) -> dict[str, Any]:
    """The benchmark's normalisation, plus the effective aggregation the engine writes."""
    entry = entry or {}
    order = entry.get("harmonic_order")
    if isinstance(order, str) and order.strip().isdigit():
        order = int(order)
    aggregation = entry.get("aggregation")
    return {
        "quantity": entry.get("quantity"),
        "phase": entry.get("phase"),
        "variant": entry.get("variant") or "none",
        "harmonic_order": order,
        "aggregation": aggregation,
        "unit": entry.get("unit"),
        "effective_aggregation": aggregation or default_aggregation,
    }


def differing(draft: dict[str, Any], gold: dict[str, Any], effective: bool) -> list[str]:
    """Scored fields that differ; with `effective`, aggregation is compared as inherited."""
    fields: list[str] = []
    for name in SCORED:
        if name == "aggregation" and effective:
            if draft["effective_aggregation"] != gold["effective_aggregation"]:
                fields.append(name)
        elif draft[name] != gold[name]:
            fields.append(name)
    return fields


def entry_errors(entry: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    """The rulebook's own column guard, against the vocabulary the draft was offered."""
    if not all(key in entry for key in ("quantity", "phase", "unit")):
        return ["missing a required field"]
    errors: list[str] = []
    rulebook._check_column(entry, ctx, FACTOR_FIELDS, errors, "entry")
    return errors


@dataclass
class Case:
    column: str
    klass: str  # A, B or C
    gold: dict[str, Any] | None
    draft: dict[str, Any] | None
    outcome: str
    wrong_strict: list[str] = field(default_factory=list)
    wrong_effective: list[str] = field(default_factory=list)
    new_in_gold: list[str] = field(default_factory=list)
    draft_errors: list[str] = field(default_factory=list)
    edits: int = 0


def columns_by_src(mapping: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {col["src"]: col for col in mapping.get("columns") or []}


def gold_novelties(gold: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    """Which of the gold's values the draft's vocabulary did not offer."""
    new: list[str] = []
    if gold.get("quantity") not in ctx["quantities"]:
        new.append(f"quantity {gold.get('quantity')}")
    if gold.get("phase") not in ctx["phases"]:
        new.append(f"phase {gold.get('phase')}")
    if (gold.get("variant") or "none") not in ctx["variants"]:
        new.append(f"variant {gold.get('variant')}")
    if gold.get("unit") not in ctx["units"]:
        new.append(f"unit {gold.get('unit')}")
    if gold.get("aggregation") is not None and gold.get("aggregation") not in ctx["aggregations"]:
        new.append(f"aggregation {gold.get('aggregation')}")
    return new


def score_run(
    columns: list[str],
    gold_map: dict[str, dict[str, Any]],
    gold_default: str | None,
    draft_map: dict[str, dict[str, Any]],
    draft_default: str | None,
    ctx: dict[str, Any],
    provider_failures: set[str],
) -> list[Case]:
    cases: list[Case] = []
    for column in columns:
        gold = gold_map.get(column)
        draft = draft_map.get(column)
        if column in provider_failures:
            # the model never answered: a fact about the service, not the model
            cases.append(Case(column, "-", gold, None, "provider failure, excluded"))
            continue
        errors = entry_errors(draft, ctx) if draft else []
        if gold is None:
            outcome = "false mapping" if draft else "correctly left out"
            cases.append(
                Case(column, "C", None, draft, outcome, draft_errors=errors, edits=int(bool(draft)))
            )
            continue

        novelties = gold_novelties(gold, ctx)
        g = normalise(gold, gold_default)
        if draft is None:
            klass = "B" if novelties else "A"
            case = Case(column, klass, gold, None, "not mapped", new_in_gold=novelties, edits=1)
            cases.append(case)
            continue

        d = normalise(draft, draft_default)
        strict = differing(d, g, effective=False)
        effective = differing(d, g, effective=True)
        if novelties:
            outcome = "invented" if errors else "force-fit"
            klass = "B"
        else:
            outcome = "exact" if not strict else "wrong"
            klass = "A"
        cases.append(
            Case(
                column,
                klass,
                gold,
                draft,
                outcome,
                wrong_strict=strict,
                wrong_effective=effective,
                new_in_gold=novelties,
                draft_errors=errors,
                edits=len(effective),
            )
        )
    return cases


# ---------------------------------------------------------------------------- report


def validator_problems(proposal_md: Path) -> list[str]:
    """The whole-draft gate's problems, as propose.py recorded them in PROPOSAL.md."""
    if not proposal_md.exists():
        return []
    text = proposal_md.read_text(encoding="utf-8")
    section = re.search(r"## Validator problems\n\n.*?\n\n(.*?)(\n## |\Z)", text, re.DOTALL)
    if not section:
        return []
    return [line[2:] for line in section.group(1).splitlines() if line.startswith("- ")]


def not_mapped_reasons(proposal_md: Path) -> dict[str, str]:
    if not proposal_md.exists():
        return {}
    text = proposal_md.read_text(encoding="utf-8")
    table = r"## Not mapped\n\n.*?\| Point \| Reason \|\n\|---\|---\|\n(.*?)\n\n"
    section = re.search(table, text, re.DOTALL)
    reasons: dict[str, str] = {}
    for line in section.group(1).splitlines() if section else []:
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 2:
            reasons[cells[0].strip("`")] = cells[1]
    return reasons


def fmt(entry: dict[str, Any] | None) -> str:
    if not entry:
        return "(none)"
    return ", ".join(f"{k}={entry[k]}" for k in SCORED if entry.get(k) is not None)


def provider_failures(proposal_md: Path) -> set[str]:
    """Points the service never answered, which say nothing about the model."""
    return {c for c, r in not_mapped_reasons(proposal_md).items() if r.startswith("no reply")}


def report_run(
    label: str, run_dir: Path, cases: list[Case], columns: list[str], failed: set[str]
) -> list[str]:
    gate = validator_problems(run_dir / "PROPOSAL.md")
    semantic = [p for p in gate if any(re.search(rf"\b{re.escape(c)}\b", p) for c in columns)]
    scored = [c for c in cases if c.klass != "-"]
    counts = {k: sum(1 for c in scored if c.klass == k) for k in "ABC"}
    exact = sum(1 for c in scored if c.klass == "A" and not c.wrong_strict and c.draft)
    exact_eff = sum(1 for c in scored if c.klass == "A" and not c.wrong_effective and c.draft)
    lines = [
        f"### {label}",
        "",
        f"- Class A (answerable): {counts['A']}, exact {exact} strict / {exact_eff} effective",
        f"- Class B (needed new vocabulary): {counts['B']}, outcomes: "
        + (", ".join(f"{c.column} {c.outcome}" for c in scored if c.klass == "B") or "none"),
        f"- Class C (gold leaves unmapped): {counts['C']}, outcomes: "
        + (", ".join(f"{c.column} {c.outcome}" for c in scored if c.klass == "C") or "none"),
        f"- Correction effort: {sum(c.edits for c in scored)} edit(s) "
        f"({sum(c.edits for c in scored if c.draft and c.gold)} field(s) changed, "
        f"{sum(1 for c in scored if c.gold and not c.draft)} entr(y/ies) added, "
        f"{sum(1 for c in scored if c.draft and not c.gold)} removed)",
        f"- Draft entries invalid against the vocabulary offered: "
        f"{sum(1 for c in scored if c.draft_errors)}",
        f"- Whole-draft gate: {'clean' if not gate else f'{len(gate)} problem(s)'}"
        + (f", {len(semantic)} naming a proposed column" if gate else ""),
        f"- Provider failures (no reply, excluded from everything above): {len(failed)}",
        "",
        "| Column | Class | Gold | Draft | Outcome | Wrong (strict) | Wrong (effective) |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in cases:
        lines.append(
            f"| `{c.column}` | {c.klass} | {fmt(c.gold)} | {fmt(c.draft)} | {c.outcome} | "
            f"{', '.join(c.wrong_strict) or '-'} | {', '.join(c.wrong_effective) or '-'} |"
        )
    if gate:
        lines += ["", "Gate problems as recorded:", ""] + [f"- {p}" for p in gate]
    lines.append("")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--gold", type=Path, default=REPO / "vendors" / "kempower")
    parser.add_argument("--proposals", type=Path, default=REPO / "proposals" / "kempower")
    parser.add_argument("--seals", type=Path, default=HERE / "SEALS.md")
    parser.add_argument("--out", type=Path, default=HERE / "REPORT.md")
    parser.add_argument("--vocab-ref", action="append", default=[], metavar="COND=REF")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="score synthetic inputs: skips the committed-gold check, never writes REPORT.md",
    )
    args = parser.parse_args()

    refs = dict(VOCAB_REF_BY_CONDITION)
    for item in args.vocab_ref:
        cond, _, ref = item.partition("=")
        refs[cond] = ref

    gold_commit = "self-test" if args.self_test else gold_is_committed(args.gold)
    gold_mapping = _yaml_text((args.gold / "mapping.yaml").read_text(encoding="utf-8"))
    gold_source = _yaml_text((args.gold / "source_schema.yaml").read_text(encoding="utf-8"))
    gold_map = columns_by_src(gold_mapping)
    gold_default = (gold_source.get("defaults") or {}).get("aggregation")

    run_dirs = sorted(p.parent for p in args.proposals.glob("*/*/mapping.yaml"))
    if not run_dirs:
        raise SystemExit(f"no proposals under {args.proposals}")
    seal_problems = check_seals(run_dirs, load_seals(args.seals))
    if seal_problems:
        raise SystemExit("refusing to score:\n  " + "\n  ".join(seal_problems))

    lines = [
        "# Kempower held-out test: scores",
        "",
        f"Gold: `{args.gold.relative_to(REPO).as_posix() if not args.self_test else args.gold}` "
        f"at {gold_commit}. Every scored file matched its seal.",
        "",
    ]
    for run_dir in run_dirs:
        condition = run_dir.parent.name.split("-", 1)[0]
        spec_path = SPEC_BY_CONDITION.get(condition)
        if spec_path is None:
            raise SystemExit(f"unknown condition directory {run_dir.parent.name}")
        spec = propose.load_spec(spec_path)
        columns = [p.name for p in propose.read_catalog(spec, spec_path)]
        draft_mapping = _yaml_text((run_dir / "mapping.yaml").read_text(encoding="utf-8"))
        draft_source = _yaml_text((run_dir / "source_schema.yaml").read_text(encoding="utf-8"))
        ctx = vocabulary_context(refs[condition])
        failed = provider_failures(run_dir / "PROPOSAL.md")
        cases = score_run(
            columns,
            gold_map,
            gold_default,
            columns_by_src(draft_mapping),
            (draft_source.get("defaults") or {}).get("aggregation"),
            ctx,
            failed,
        )
        label = f"{run_dir.parent.name} / {run_dir.name} (vocabulary at {refs[condition][:12]})"
        lines += report_run(label, run_dir, cases, columns, failed)

    text = "\n".join(lines)
    print(text)
    if not args.self_test:
        args.out.write_bytes(text.encode("utf-8"))
        print(f"\nwritten: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
