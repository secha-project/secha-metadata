"""Post-hoc analysis of the Kempower drafts. NOT pre-registered; see FINDINGS.md.

Written after unsealing, to answer questions the pre-registered scores raise but do not
break down. Every number it prints is derived from the same sealed drafts and the same
committed gold as score.py, using score.py's own normalisation, and it refuses to run if
a draft differs from its seal. It changes no pre-registered score.

Three breakdowns:
  - per field, over the five columns: how often each scored field matches the gold
    (aggregation compared as the engine writes it, after the source default)
  - the phase chosen for the three electrical columns: dc, none (no phase), or an AC phase
  - a sensitivity check on the one gold decision the provider has not confirmed: that
    soc and tempC are instantaneous samples. It re-counts exact entries as if the gold
    had left both to the source default (average).

Usage (from the repository root):
    python experiments/kempower_heldout/analysis_posthoc.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import score  # noqa: E402  (this folder on the path above)

ELECTRICAL = ("avgPowerW", "avgCurrentA", "avgVoltageV")
SAMPLED = ("soc", "tempC")
AC_PHASES = {"L1", "L2", "L3", "N", "L1_L2", "L2_L3", "L3_L1", "three_phase"}
FIELDS = ("quantity", "phase", "unit", "aggregation")


def run_dirs(proposals: Path) -> list[Path]:
    return sorted(p.parent for p in proposals.glob("*/*/mapping.yaml"))


def main() -> int:
    gold_dir = score.REPO / "vendors" / "kempower"
    proposals = score.REPO / "proposals" / "kempower"
    dirs = run_dirs(proposals)
    problems = score.check_seals(dirs, score.load_seals(HERE / "SEALS.md"))
    if problems:
        raise SystemExit("refusing to analyse:\n  " + "\n  ".join(problems))

    gold_map = score.columns_by_src(score._yaml_text((gold_dir / "mapping.yaml").read_text()))
    gold_source = score._yaml_text((gold_dir / "source_schema.yaml").read_text())
    gold_default = (gold_source.get("defaults") or {}).get("aggregation")

    lines = [
        "| Condition | Arm | quantity | phase | unit | aggregation | electrical phases | "
        "soc, tempC quantity | exact | exact if soc, tempC inherit |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for run in dirs:
        draft_map = score.columns_by_src(score._yaml_text((run / "mapping.yaml").read_text()))
        draft_source = score._yaml_text((run / "source_schema.yaml").read_text())
        draft_default = (draft_source.get("defaults") or {}).get("aggregation")

        right = dict.fromkeys(FIELDS, 0)
        exact = exact_inherit = 0
        phases: list[str] = []
        sampled: list[str] = []
        for column, gold in gold_map.items():
            d = score.normalise(draft_map.get(column), draft_default)
            g = score.normalise(gold, gold_default)
            wrong = score.differing(d, g, effective=True)
            for name in FIELDS:
                right[name] += name not in wrong
            exact += not wrong
            if column in SAMPLED:
                relaxed = dict(gold)
                relaxed.pop("aggregation", None)
                g2 = score.normalise(relaxed, gold_default)
                exact_inherit += not score.differing(d, g2, effective=True)
                q = d["quantity"]
                sampled.append("gold name" if q == g["quantity"] else f"`{q}`")
            else:
                exact_inherit += not wrong
            if column in ELECTRICAL:
                p = d["phase"]
                phases.append("dc" if p == "dc" else "none" if p == "none" else f"AC ({p})")

        n = len(gold_map)
        lines.append(
            f"| {run.parent.name} | {run.name} | "
            + " | ".join(f"{right[f]}/{n}" for f in FIELDS)
            + f" | {', '.join(phases)} | {', '.join(sampled)} | {exact}/{n} | {exact_inherit}/{n} |"
        )
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
