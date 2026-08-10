"""Benchmark local TUNI models on the mapping-authoring task.

The question: given a vendor's catalog point (its name, its path, its source unit),
can a model produce the canonical mapping entry a human author would have written?

We can answer that exactly, because the answer key already exists. The 68 curated
`rows:` entries in `vendors/procem_kampusareena_pq/mapping.yaml` were written by hand
and are known correct, so every model proposal can be scored field by field against them.

Two properties make this a fair test rather than a demo:

1. No leakage. In the default `cross` mode the few-shot examples come from the OTHER
   vendor (mx_electrix), so the model never sees a ProCem answer before being asked for
   one. That is also the real scenario: you have onboarded one source and are adding a
   second. `--shots holdout:N` instead takes N ProCem examples and scores the rest,
   which shows the ceiling when in-vendor examples exist.
2. The prompt is generated from the rulebook itself (vocabulary, enums, unit registry),
   so it can never drift from the schema the answer is checked against.

Beyond accuracy we report the rate at which proposals pass `validate.py`'s own guards.
That is the number that matters operationally: a proposal that fails validation cannot
reach the data, so it costs review time but not correctness.

Usage:
    pip install -r requirements.txt
    cp .env.template .env          # add SECHA_AVIARY_API_KEY
    python benchmark.py --dry-run                  # inspect the prompt, no API calls
    python benchmark.py --limit 10                 # cheap smoke run
    python benchmark.py                            # full run, all default models
    python benchmark.py --models granite4-32b phi4-14b
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import validate as rulebook  # noqa: E402  (path set above so the rulebook validator is importable)

HERE = Path(__file__).parent
DEFAULT_ENDPOINT = "https://aviary.fgl.rd.tuni.fi/api/chat/completions"
DEFAULT_CATALOG = REPO.parents[1] / "secha-data-procem" / "catalog_evcharging.csv"
DEFAULT_MODELS = ("granite4-32b", "phi4-14b", "gemma3-12b", "mistral-nemo-12b", "llama3.1-8b")

TEST_VENDOR = "procem_kampusareena_pq"
SHOT_VENDOR = "mx_electrix"
SCORED = ("quantity", "phase", "variant", "harmonic_order", "aggregation", "unit")


# --------------------------------------------------------------------------- rulebook


@dataclass(frozen=True)
class Rulebook:
    """The canonical layer, loaded once and used for both the prompt and the scoring."""

    canonical: dict[str, Any]
    vocabulary: dict[str, Any]
    units: dict[str, Any]
    library: dict[str, Any]

    @property
    def ctx(self) -> dict[str, Any]:
        """The context object `validate._check_column` expects."""
        return {
            "quantities": set(self.vocabulary["quantities"]),
            "quantities_meta": self.vocabulary["quantities"],
            "units": set(self.units["units"]),
            "phases": set(self.canonical["enums"]["phase"]),
            "variants": set(self.canonical["enums"]["variant"]),
            "aggregations": set(self.canonical["enums"]["aggregation"]),
            "qualities": set(self.canonical["enums"]["quality_flag"]),
            "rules": self.library["rules"],
        }


def _yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_rulebook() -> Rulebook:
    return Rulebook(
        canonical=_yaml(REPO / "canonical" / "canonical_schema.yaml"),
        vocabulary=_yaml(REPO / "canonical" / "quantity_vocabulary.yaml"),
        units=_yaml(REPO / "canonical" / "units.yaml"),
        library=_yaml(REPO / "transforms" / "library.yaml"),
    )


# ------------------------------------------------------------------------------ cases


@dataclass(frozen=True)
class Case:
    """One catalog point the model must map, plus the answer a human wrote."""

    point: str
    hint: str
    source_unit: str
    expected: dict[str, Any]


def normalise(entry: dict[str, Any]) -> dict[str, Any]:
    """Compare like with like: apply the same defaults the engine applies."""
    order = entry.get("harmonic_order")
    if isinstance(order, str) and order.strip().isdigit():
        order = int(order)
    return {
        "quantity": entry.get("quantity"),
        "phase": entry.get("phase"),
        "variant": entry.get("variant") or "none",
        "harmonic_order": order,
        # absent aggregation means "inherit the source default", which is a real answer
        "aggregation": entry.get("aggregation"),
        "unit": entry.get("unit"),
    }


def load_catalog(path: Path) -> dict[str, tuple[str, str]]:
    """point name -> (path, source unit) from the vendor's own catalog export."""
    catalog: dict[str, tuple[str, str]] = {}
    with path.open(encoding="utf-8") as handle:
        header = handle.readline().rstrip("\n").split(";")
        idx = {name: i for i, name in enumerate(header)}
        for line in handle:
            parts = line.rstrip("\n").split(";")
            if len(parts) <= idx["name"]:
                continue
            catalog[parts[idx["name"]]] = (parts[idx["path"]], parts[idx["unit"]])
    return catalog


def load_test_cases(catalog: dict[str, tuple[str, str]]) -> list[Case]:
    mapping = _yaml(REPO / "vendors" / TEST_VENDOR / "mapping.yaml")
    cases: list[Case] = []
    for row in mapping["rows"]:
        point = row.get("desc", "")
        node_path, source_unit = catalog.get(point, ("", ""))
        cases.append(
            Case(
                point=point,
                hint=node_path,
                source_unit=source_unit,
                expected=normalise(row),
            )
        )
    return cases


def stratified_holdout(cases: list[Case], n: int) -> tuple[list[Case], list[Case]]:
    """Split off n examples spread evenly across the file, not the first n.

    The mapping is grouped by quantity family, so taking the first n would hand over
    twelve voltages and nothing else. Even spacing gives the shots a chance to cover
    the families that actually differ. Removing the same n in every mode keeps the
    test set identical, so cross-vendor and in-vendor runs are directly comparable.
    """
    if n <= 0:
        return [], list(cases)
    step = len(cases) / n
    picked = sorted({min(len(cases) - 1, int(i * step)) for i in range(n)})
    chosen = {i for i in picked}
    return [cases[i] for i in picked], [c for i, c in enumerate(cases) if i not in chosen]


def load_cross_vendor_shots() -> list[Case]:
    """Few-shot examples from the OTHER vendor, so no test answer is ever shown."""
    mapping = _yaml(REPO / "vendors" / SHOT_VENDOR / "mapping.yaml")
    schema = _yaml(REPO / "vendors" / SHOT_VENDOR / "source_schema.yaml")
    fields = {f["name"]: f for f in schema.get("fields", [])}
    shots: list[Case] = []
    for column in mapping.get("columns", []):
        meta = fields.get(column["src"], {})
        shots.append(
            Case(
                point=column["src"],
                hint=meta.get("desc", ""),
                source_unit=str(meta.get("unit", "")),
                expected=normalise(column),
            )
        )
    return shots


# ----------------------------------------------------------------------------- prompt


def source_naming_convention(vendor: str) -> str:
    """The vendor's documented point-name grammar, if its source schema declares one.

    Read from `source_schema.yaml`, so this is metadata the framework already carries
    rather than knowledge hardcoded in the benchmark. Any vendor that documents its
    naming gets the benefit automatically.
    """
    schema = _yaml(REPO / "vendors" / vendor / "source_schema.yaml")
    return str(schema.get("naming_convention") or "").strip()


def build_system_prompt(rb: Rulebook, convention: str = "") -> str:
    """Generated from the rulebook, so the instructions cannot drift from the schema."""
    quantities = "\n".join(
        f"  {name}: unit {meta.get('default_unit')}. {meta.get('description', '')}"
        + ("  REQUIRES harmonic_order." if "harmonic_order" in (meta.get("requires") or []) else "")
        for name, meta in rb.vocabulary["quantities"].items()
    )
    enums = rb.canonical["enums"]
    convention_block = (
        f"\n\nThe points you will be asked about follow this naming convention:\n{convention}\n"
        if convention
        else ""
    )
    opening = "You map a vendor's measurement point onto the SECHA canonical schema."
    return f"""{opening}{convention_block}

Allowed quantity values (with their canonical unit and meaning):
{quantities}

Allowed phase values: {", ".join(enums["phase"])}
  Use three_phase for a total or aggregate over all phases, and none when phase does
  not apply. L1_L2, L2_L3 and L3_L1 are line-to-line measurements.

Allowed variant values: {", ".join(enums["variant"])}
  fundamental means the fundamental-frequency component only.
  fryze means the Fryze definition of reactive power.
  Use none when the point is a plain total.

Allowed aggregation values: {", ".join(enums["aggregation"])}
  Only state aggregation when the point is a cumulative counter (use counter).
  Otherwise omit it and the source default applies.

Allowed unit values: {", ".join(rb.units["units"])}
  Note that a percentage is written as percent, and a dimensionless ratio as ratio.

Set harmonic_order only for quantities that require it, using the harmonic number.

Answer with a YAML mapping and nothing else. No prose, no code fences, no explanation.
Include quantity, phase and unit always. Include variant, harmonic_order or aggregation
only when they apply."""


def render_case(case: Case) -> str:
    hint = case.hint or "(none)"
    unit = case.source_unit or "(not stated)"
    return f"point: {case.point}\ncontext: {hint}\nsource unit: {unit}"


def render_answer(case: Case) -> str:
    body = {
        k: v
        for k, v in case.expected.items()
        if v is not None and not (k == "variant" and v == "none")
    }
    return yaml.safe_dump(body, sort_keys=False, default_flow_style=False).strip()


def build_messages(system: str, shots: list[Case], case: Case) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for shot in shots:
        messages.append({"role": "user", "content": render_case(shot)})
        messages.append({"role": "assistant", "content": render_answer(shot)})
    messages.append({"role": "user", "content": render_case(case)})
    return messages


# ------------------------------------------------------------------------------ model

_FENCE = re.compile(r"```(?:ya?ml|json)?\s*(.*?)```", re.DOTALL)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def parse_reply(text: str) -> dict[str, Any] | None:
    """Pull a mapping out of the reply, tolerating fences and reasoning traces."""
    cleaned = _THINK.sub("", text).strip()
    fenced = _FENCE.search(cleaned)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        parsed = yaml.safe_load(cleaned)  # JSON is valid YAML, so both forms work
    except yaml.YAMLError:
        return None
    # a one-item list is a harmless formatting variation; a longer list means the model
    # answered with the whole example set instead of the point it was asked about
    if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
        parsed = parsed[0]
    return parsed if isinstance(parsed, dict) else None


class ModelClient:
    """OpenAI-compatible client with a disk cache, so re-scoring never re-calls the API."""

    def __init__(self, endpoint: str, api_key: str, cache_dir: Path, timeout: int) -> None:
        self._endpoint = endpoint
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self._cache_dir = cache_dir
        self._timeout = timeout

    def complete(self, model: str, messages: list[dict[str, str]]) -> tuple[str | None, float, str]:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0,  # structured output: same prompt, same answer
            "max_tokens": 300,
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[
            :20
        ]
        cached = self._cache_dir / model / f"{digest}.json"
        if cached.exists():
            blob = json.loads(cached.read_text(encoding="utf-8"))
            # reuse the recorded timing, otherwise a cached run reports a median of zero
            return blob.get("content"), float(blob.get("elapsed") or 0.0), "cache"

        last_error = "unknown error"
        for attempt in range(3):
            started = time.monotonic()
            try:
                response = requests.post(
                    self._endpoint, headers=self._headers, json=payload, timeout=self._timeout
                )
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                time.sleep(2 * (attempt + 1))
                continue
            elapsed = time.monotonic() - started
            if response.status_code != 200:
                last_error = f"HTTP {response.status_code}: {response.text[:160]}"
                if response.status_code < 500:
                    break  # a client error will not fix itself on retry
                time.sleep(2 * (attempt + 1))
                continue
            content = response.json()["choices"][0]["message"]["content"]
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(
                json.dumps({"content": content, "elapsed": elapsed}), encoding="utf-8"
            )
            return content, elapsed, ""
        return None, 0.0, last_error


# ----------------------------------------------------------------------------- scoring


@dataclass
class Score:
    """Everything we measure for one model.

    Three failure modes are kept apart on purpose, because they mean different things:
    the service did not answer (availability), the reply was not a single mapping
    (instruction following), or the mapping was wrong (accuracy). Collapsing them into
    one number makes an unavailable model look like an inaccurate one.
    """

    model: str
    total: int = 0
    answered: int = 0  # the service returned a reply at all
    parsed: int = 0  # the reply was a single well-formed mapping
    passes_validator: int = 0
    exact: int = 0
    fields: dict[str, int] = field(default_factory=lambda: dict.fromkeys(SCORED, 0))
    latencies: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    misses: list[dict[str, Any]] = field(default_factory=list)

    @property
    def median_latency(self) -> float:
        return statistics.median(self.latencies) if self.latencies else 0.0

    def of_total(self, value: int) -> str:
        return f"{100 * value / self.total:.0f}%" if self.total else "n/a"

    def of_parsed(self, value: int) -> str:
        """Accuracy is only meaningful over the cases the model actually answered."""
        return f"{100 * value / self.parsed:.0f}%" if self.parsed else "n/a"


def validator_errors(entry: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    """Run the rulebook's own guard over a proposed entry."""
    if not all(key in entry for key in ("quantity", "phase", "unit")):
        return ["missing a required field"]
    errors: list[str] = []
    rulebook._check_column(entry, ctx, {"uk", "ik", "uk_ik"}, errors, "proposal")
    return errors


def score_model(
    model: str,
    client: ModelClient,
    system: str,
    shots: list[Case],
    cases: list[Case],
    ctx: dict[str, Any],
) -> Score:
    score = Score(model=model, total=len(cases))
    for index, case in enumerate(cases, start=1):
        content, elapsed, error = client.complete(model, build_messages(system, shots, case))
        if elapsed:
            score.latencies.append(elapsed)
        print(f"  [{index}/{len(cases)}] {case.point:<28}", end="")
        if content is None:
            score.errors.append(f"{case.point}: {error}")
            print("no reply")
            continue
        score.answered += 1

        proposal = parse_reply(content)
        if proposal is None:
            score.misses.append(
                {"point": case.point, "reason": "not a single mapping", "raw": content[:120]}
            )
            print("wrong shape")
            continue
        score.parsed += 1

        if not validator_errors(proposal, ctx):
            score.passes_validator += 1

        got = normalise(proposal)
        matched = [name for name in SCORED if got[name] == case.expected[name]]
        for name in matched:
            score.fields[name] += 1
        if len(matched) == len(SCORED):
            score.exact += 1
            print("exact")
        else:
            wrong = {
                name: {"expected": case.expected[name], "got": got[name]}
                for name in SCORED
                if name not in matched
            }
            score.misses.append({"point": case.point, "wrong": wrong})
            print(f"wrong: {', '.join(wrong)}")
    return score


# ------------------------------------------------------------------------------ report


def report(scores: list[Score], mode: str, shots: int, cases: int, convention: bool) -> str:
    head = (
        f"# Model comparison: canonical mapping authoring\n\n"
        f"Task: given a catalog point, produce the canonical mapping entry.\n"
        f"Ground truth: {cases} hand-curated `{TEST_VENDOR}` entries.\n"
        f"Few-shot: {shots} examples, `{mode}` mode"
        + (
            f" (from `{SHOT_VENDOR}`, so no test answer is ever shown)"
            if mode == "cross"
            else " (held out of the test set, stratified across quantity families)"
            if mode == "holdout"
            else ""
        )
        + ".\n"
        f"Vendor naming convention in the prompt: **{'yes' if convention else 'no'}**.\n\n"
        "Accuracy columns are over the cases a model actually answered with a single\n"
        "well-formed mapping, so an unavailable model is not scored as an inaccurate one.\n\n"
        "| Model | Answered | Usable reply | Exact | Valid | Quantity | Phase | Variant "
        "| Unit | Order | Aggr. | Median s |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    rows = []
    for s in sorted(scores, key=lambda x: x.exact / x.parsed if x.parsed else -1, reverse=True):
        rows.append(
            f"| `{s.model}` | {s.of_total(s.answered)} | {s.of_total(s.parsed)} "
            f"| **{s.of_parsed(s.exact)}** | {s.of_parsed(s.passes_validator)} "
            f"| {s.of_parsed(s.fields['quantity'])} | {s.of_parsed(s.fields['phase'])} "
            f"| {s.of_parsed(s.fields['variant'])} | {s.of_parsed(s.fields['unit'])} "
            f"| {s.of_parsed(s.fields['harmonic_order'])} "
            f"| {s.of_parsed(s.fields['aggregation'])} | {s.median_latency:.1f} |"
        )
    note = (
        "\n\n**Answered**: the service returned a reply (availability, not model quality). "
        "**Usable reply**: that reply was a single well-formed mapping rather than prose or a "
        "list of examples, which measures instruction following. **Exact**: every scored field "
        "matched. **Valid**: the proposal passes `validate.py`, so it could reach a pull request "
        "at all.\n\nExact and Valid answer different questions. A wrong but valid proposal costs "
        "a reviewer time; an invalid one is rejected automatically and costs nothing. That gap is "
        "the argument for keeping the validator in front of any model.\n"
    )
    return head + "\n".join(rows) + note


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument("--endpoint", default=os.environ.get("SECHA_AVIARY_URL", DEFAULT_ENDPOINT))
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--shots", default="cross", help="cross | holdout | none")
    parser.add_argument(
        "--holdout-n",
        type=int,
        default=0,
        help="reserve N stratified cases. In holdout mode they become the examples; in "
        "every mode they leave the test set, so runs stay directly comparable.",
    )
    parser.add_argument(
        "--no-convention",
        action="store_true",
        help="ignore the vendor's documented naming convention (the A/B baseline)",
    )
    parser.add_argument("--limit", type=int, default=0, help="score only the first N cases")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true", help="print one prompt and exit")
    parser.add_argument("--out", type=Path, default=HERE / "results")
    args = parser.parse_args()

    for line in (
        (HERE / ".env").read_text(encoding="utf-8").splitlines() if (HERE / ".env").exists() else []
    ):
        if "=" in line and not line.strip().startswith("#"):
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))

    rb = load_rulebook()
    convention = "" if args.no_convention else source_naming_convention(TEST_VENDOR)
    system = build_system_prompt(rb, convention)

    if not args.catalog.exists():
        print(f"catalog not found: {args.catalog}\nPass --catalog with the vendor catalog CSV.")
        return 1
    catalog = load_catalog(args.catalog)
    cases = load_test_cases(catalog)

    # the reserved cases leave the test set in every mode, so the modes are comparable
    reserved, cases = stratified_holdout(cases, args.holdout_n)
    if args.shots == "cross":
        shots = load_cross_vendor_shots()
    elif args.shots == "holdout":
        if not reserved:
            print("holdout mode needs --holdout-n N")
            return 1
        shots = reserved
    else:
        shots = []
    if args.limit:
        cases = cases[: args.limit]

    if args.dry_run:
        messages = build_messages(system, shots, cases[0])
        for message in [*messages[:2], messages[-1]]:
            print(f"--- {message['role']} ---\n{message['content']}\n")
        print(f"({len(messages)} messages total: system + {len(shots)} examples + 1 question)")
        return 0

    api_key = os.environ.get("SECHA_AVIARY_API_KEY", "")
    if not api_key:
        print("SECHA_AVIARY_API_KEY is not set. Copy .env.template to .env and add your key.")
        return 1

    client = ModelClient(args.endpoint, api_key, HERE / ".cache", args.timeout)
    scores = []
    for model in args.models:
        print(f"\n{model}")
        scores.append(score_model(model, client, system, shots, cases, rb.ctx))

    args.out.mkdir(parents=True, exist_ok=True)
    table = report(scores, args.shots, len(shots), len(cases), bool(convention))
    (args.out / "comparison.md").write_text(table, encoding="utf-8", newline="\n")
    (args.out / "raw.json").write_text(
        json.dumps(
            [
                {
                    "model": s.model,
                    "total": s.total,
                    "answered": s.answered,
                    "parsed": s.parsed,
                    "passes_validator": s.passes_validator,
                    "exact": s.exact,
                    "fields": s.fields,
                    "median_latency": s.median_latency,
                    "errors": s.errors,
                    "misses": s.misses,
                }
                for s in scores
            ],
            indent=2,
        ),
        encoding="utf-8",
        newline="\n",
    )
    print("\n" + table)
    print(f"written: {args.out / 'comparison.md'} and {args.out / 'raw.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
