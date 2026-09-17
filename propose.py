"""Propose a complete vendor directory from a partner catalog, gated by validate.py.

Onboarding a vendor here is a pull request, not an engine release. The slow part of
that pull request is reading a vendor catalog point by point and deciding which
canonical quantity, phase, unit and variant each one means. This command drafts that
decision for every point and refuses to emit anything the validator would reject.

What is inferred and what is not
--------------------------------
Only *semantics* are proposed: quantity, phase, unit, variant, harmonic_order. Every
operational fact (owner, access layout, format, record fields, defaults) and every
validation threshold is human-authored in the spec file, because those are decisions
about a system and a domain rather than readings of a point name. A model that guesses
a landing path is not helping.

What this does not promise
--------------------------
The validator stops malformed configs, not wrong ones. Measured on 68 hand-curated
ProCem entries, proposals were 98 to 100% valid while accuracy ranged from 38 to 84%,
so nearly every wrong proposal was still a legal config (see experiments/llm_mapping).
The output of this command is a reviewable draft. It is marked as machine-proposed in
every file it writes, and the advisory checks below exist to point a reviewer at the
places most likely to be wrong. None of that replaces reading the diff.

Usage:
    python propose.py --spec <spec.yaml>                  # propose into proposals/<vendor>/
    python propose.py --spec <spec.yaml> --dry-run        # print one prompt, no API calls
    python propose.py --spec <spec.yaml> --limit 10       # cheap trial on a stratified sample
    python propose.py --spec <spec.yaml> --apply          # install into vendors/<vendor>/
    python propose.py --spec <spec.yaml> --model phi4-14b --endpoint <url>

The endpoint is any OpenAI-compatible chat-completions URL; the key is read from the
environment variable matching its host (see KEY_ENV_BY_HOST).
"""

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import jsonschema
import yaml

from validate import validate

ROOT = Path(__file__).parent
DEFAULT_ENDPOINT = os.environ.get(
    "SECHA_AVIARY_URL", "https://aviary.fgl.rd.tuni.fi/api/chat/completions"
)
DEFAULT_MODEL = "phi4-14b"
DEFAULT_SHOTS = 16

KEY_ENV_BY_HOST = {
    "aviary.fgl.rd.tuni.fi": "SECHA_AVIARY_API_KEY",
    "api.mistral.ai": "SECHA_MISTRAL_API_KEY",
    "integrate.api.nvidia.com": "SECHA_NVIDIA_API_KEY",
}

SCORED_FIELDS = ("quantity", "phase", "unit", "variant", "harmonic_order", "aggregation")


# ------------------------------------------------------------------------------- inputs


@dataclass
class Point:
    """One catalog entry: what the vendor says exists, before any interpretation."""

    key: str
    name: str
    context: str
    unit: str


@dataclass
class Proposal:
    """One point, its proposed mapping entry, and everything a reviewer should know."""

    point: Point
    entry: dict[str, Any] | None = None
    error: str = ""
    advisories: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.entry is not None


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_spec(path: Path) -> dict:
    """Read the human-authored spec and check it against its meta-schema."""
    spec = _load_yaml(path)
    schema_path = ROOT / "meta-schemas" / "propose_spec.schema.json"
    with schema_path.open(encoding="utf-8") as handle:
        schema = json.load(handle)
    validator = jsonschema.Draft202012Validator(schema)
    problems = sorted(validator.iter_errors(spec), key=str)
    if problems:
        lines = [f"spec {path.name} does not conform to propose_spec.schema.json:"]
        lines += [
            f"  - {'/'.join(str(p) for p in err.path) or '<root>'}: {err.message}"
            for err in problems
        ]
        raise SystemExit("\n".join(lines))
    return spec


def read_catalog(spec: dict, spec_path: Path) -> list[Point]:
    """Read the vendor's own catalog export into points, per the spec's catalog block."""
    cat = spec["catalog"]
    path = (spec_path.parent / cat["path"]).resolve()
    if not path.exists():
        raise SystemExit(f"catalog not found: {path}")

    key_col = cat["key_column"]
    name_col = cat["name_column"]
    unit_col = cat.get("unit_column")
    context_col = cat.get("context_column")

    points: list[Point] = []
    with path.open(encoding=cat.get("encoding", "utf-8"), newline="") as handle:
        reader = csv.DictReader(handle, delimiter=cat.get("delimiter", ","))
        missing = [
            c
            for c in (key_col, name_col, unit_col, context_col)
            if c and c not in reader.fieldnames
        ]
        if missing:
            raise SystemExit(
                f"catalog {path.name} has no column(s) {missing}; it has {reader.fieldnames}"
            )
        for row in reader:
            name = (row.get(name_col) or "").strip()
            if not name:
                continue
            points.append(
                Point(
                    key=(row.get(key_col) or "").strip(),
                    name=name,
                    context=(row.get(context_col) or "").strip() if context_col else "",
                    unit=(row.get(unit_col) or "").strip() if unit_col else "",
                )
            )

    include = cat.get("include_pattern")
    if include:
        pattern = re.compile(include)
        points = [p for p in points if pattern.search(p.name)]
    exclude = cat.get("exclude_pattern")
    if exclude:
        pattern = re.compile(exclude)
        points = [p for p in points if not pattern.search(p.name)]
    if not points:
        raise SystemExit(f"catalog {path.name} yielded no points after filtering")
    return points


def load_rulebook(root: Path) -> dict[str, Any]:
    """The canonical vocabulary the prompt is generated from and proposals are scored against.

    Read from canonical/ rather than restated here, so the instructions given to a model
    cannot drift from the schema its output is validated against.
    """
    canon = _load_yaml(root / "canonical" / "canonical_schema.yaml")
    vocab = _load_yaml(root / "canonical" / "quantity_vocabulary.yaml")
    units = _load_yaml(root / "canonical" / "units.yaml")
    return {
        "quantities": vocab["quantities"],
        "units": units["units"],
        "phases": canon["enums"]["phase"],
        "variants": canon["enums"]["variant"],
        "aggregations": canon["enums"]["aggregation"],
    }


# ------------------------------------------------------------------------------- prompt

# Deliberately not imported from experiments/llm_mapping/benchmark.py. That experiment is
# a fixed measurement whose cached results are keyed on its exact prompt; making it depend
# on this file would silently invalidate published numbers the next time this one changes.


def build_system_prompt(rb: dict[str, Any], convention: str = "") -> str:
    lines = ["You map a vendor's measurement point onto the SECHA canonical schema.", ""]
    if convention:
        lines += [
            "The points you will be asked about follow this naming convention:",
            convention,
            "",
        ]
    lines.append("Canonical quantities (name: unit, meaning):")
    for name, meta in rb["quantities"].items():
        requires = meta.get("requires") or []
        extra = f" [requires {', '.join(requires)}]" if requires else ""
        lines.append(f"  {name}: {meta.get('default_unit')}, {meta.get('description', '')}{extra}")
    lines += [
        "",
        f"Phases: {', '.join(rb['phases'])}",
        f"Variants: {', '.join(rb['variants'])}",
        f"Aggregations: {', '.join(rb['aggregations'])}",
        f"Units: {', '.join(rb['units'])}",
        "",
        "Answer with YAML for ONE mapping entry and nothing else. Keys: quantity, phase,",
        "unit, and variant / harmonic_order / aggregation only when they apply.",
        "Do not restate the question, do not explain, do not emit a list.",
    ]
    return "\n".join(lines)


def render_point(point: Point) -> str:
    parts = [f"point: {point.name}"]
    if point.context:
        parts.append(f"context: {point.context}")
    if point.unit:
        parts.append(f"source unit: {point.unit}")
    return "\n".join(parts)


def render_entry(entry: dict[str, Any]) -> str:
    keep = {k: entry[k] for k in SCORED_FIELDS if entry.get(k) is not None}
    return yaml.safe_dump(keep, sort_keys=False, default_flow_style=False).strip()


def load_examples(root: Path, exclude_vendor: str, limit: int) -> list[tuple[Point, dict]]:
    """Worked examples drawn from vendors already onboarded, never from the target vendor.

    Examples measurably help, and taking them from another vendor keeps the draft honest:
    it is the real situation, where one source is mapped and a second is arriving.
    """
    examples: list[tuple[Point, dict]] = []
    vendors_dir = root / "vendors"
    if not vendors_dir.exists():
        return examples
    for vendor_dir in sorted(vendors_dir.iterdir()):
        if not vendor_dir.is_dir() or vendor_dir.name == exclude_vendor:
            continue
        mapping_path = vendor_dir / "mapping.yaml"
        source_path = vendor_dir / "source_schema.yaml"
        if not mapping_path.exists() or not source_path.exists():
            continue
        mapping = _load_yaml(mapping_path)
        source = _load_yaml(source_path)
        descs = {f["name"]: f.get("desc", "") for f in source.get("fields", [])}
        units = {f["name"]: f.get("unit") or "" for f in source.get("fields", [])}
        for col in mapping.get("columns", []):
            name = col["src"]
            examples.append(
                (
                    Point(
                        key=name, name=name, context=descs.get(name, ""), unit=units.get(name, "")
                    ),
                    col,
                )
            )
        for row in mapping.get("rows", []):
            name = row.get("desc") or row["key"]
            examples.append((Point(key=row["key"], name=name, context="", unit=""), row))

    # Spread the examples across the file rather than taking a head slice, which would
    # show only the quantity families that happen to be listed first.
    if len(examples) > limit > 0:
        step = len(examples) / limit
        examples = [examples[int(i * step)] for i in range(limit)]
    return examples


def build_messages(
    system: str, shots: list[tuple[Point, dict]], point: Point
) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": system}]
    for shot_point, entry in shots:
        messages.append({"role": "user", "content": render_point(shot_point)})
        messages.append({"role": "assistant", "content": render_entry(entry)})
    messages.append({"role": "user", "content": render_point(point)})
    return messages


_FENCE = re.compile(r"```(?:ya?ml|json)?\s*(.*?)```", re.DOTALL)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def parse_reply(text: str) -> dict[str, Any] | None:
    """Pull a single mapping out of the reply, tolerating fences and reasoning traces."""
    cleaned = _THINK.sub("", text).strip()
    fenced = _FENCE.search(cleaned)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        parsed = yaml.safe_load(cleaned)
    except yaml.YAMLError:
        return None
    if not isinstance(parsed, dict) or "quantity" not in parsed:
        return None
    return parsed


# -------------------------------------------------------------------------------- model


def api_key_for(endpoint: str) -> str:
    host = urlparse(endpoint).hostname or ""
    if host in ("localhost", "127.0.0.1"):
        return "local-proxy"
    specific = KEY_ENV_BY_HOST.get(host)
    if specific and os.environ.get(specific):
        return os.environ[specific]
    return os.environ.get("SECHA_LLM_API_KEY", "")


def provider_tag(endpoint: str) -> str:
    host = urlparse(endpoint).hostname or "unknown"
    return re.sub(r"[^A-Za-z0-9]+", "-", host).strip("-").lower()


class ModelClient:
    """Minimal OpenAI-compatible chat client with a reply cache.

    `requests` is imported lazily so the CI-gated contract (validate, lineage, tests)
    keeps its two-dependency footprint and never needs a network library installed.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        cache_dir: Path,
        timeout: int,
        delay: float,
        max_tokens: int,
    ) -> None:
        self._endpoint = endpoint
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self._cache_dir = cache_dir / provider_tag(endpoint)
        self._timeout = timeout
        self._delay = delay
        self._max_tokens = max_tokens

    def complete(self, model: str, messages: list[dict[str, str]]) -> tuple[str | None, str]:
        import requests

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0,  # a proposal must be reproducible from the same inputs
            "max_tokens": self._max_tokens,
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[
            :20
        ]
        cached = self._cache_dir / model / f"{digest}.json"
        if cached.exists():
            return json.loads(cached.read_text(encoding="utf-8")).get("content"), ""

        last_error = "unknown error"
        for attempt in range(3):
            if self._delay:
                time.sleep(self._delay)
            try:
                response = requests.post(
                    self._endpoint, headers=self._headers, json=payload, timeout=self._timeout
                )
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                time.sleep(2 * (attempt + 1))
                continue
            if response.status_code != 200:
                last_error = f"HTTP {response.status_code}: {response.text[:160]}"
                if response.status_code == 429:
                    time.sleep(5 * (attempt + 1))  # throttling, not refusal
                    continue
                if response.status_code < 500:
                    break
                time.sleep(2 * (attempt + 1))
                continue
            choice = response.json()["choices"][0]
            content = choice["message"].get("content")
            if not (content or "").strip():
                reason = choice.get("finish_reason") or "unknown"
                last_error = (
                    f"empty content, truncated at max_tokens={self._max_tokens}"
                    if reason == "length"
                    else f"empty content, finish_reason={reason}"
                )
                break
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(json.dumps({"content": content}), encoding="utf-8")
            return content, ""
        return None, last_error


# ----------------------------------------------------------------------------- advisory


def advisories_for(entry: dict[str, Any], point: Point, rb: dict[str, Any]) -> list[str]:
    """Checks the validator cannot make, aimed at where proposals are actually wrong.

    validate.py asks whether a unit exists in the registry. It does not ask whether that
    unit could possibly measure that quantity, so a harmonic voltage reported in volts
    passes every gate while being plainly wrong. These notes never block; they tell a
    reviewer which lines to read first.
    """
    notes: list[str] = []
    quantity = entry.get("quantity")
    meta = rb["quantities"].get(quantity)
    if meta is None:
        return notes  # unknown quantity is the validator's error to report, not ours

    unit = entry.get("unit")
    default_unit = meta.get("default_unit")
    unit_meta = rb["units"].get(unit) or {}
    default_meta = rb["units"].get(default_unit) or {}
    if unit and unit in rb["units"] and unit_meta.get("dimension") != default_meta.get("dimension"):
        notes.append(
            f"unit '{unit}' measures {unit_meta.get('dimension')} but quantity "
            f"'{quantity}' is normally {default_unit} ({default_meta.get('dimension')})"
        )
    elif unit and unit != default_unit:
        notes.append(f"unit '{unit}' is dimensionally right but not the default '{default_unit}'")

    # Only compare against the vendor's declared unit when that string is itself a
    # registry unit. Vendors spell the same unit differently ("%" for percent, "-" for
    # ratio), and flagging spelling would fire on most of a catalog and bury the rest.
    declared = {u.lower(): u for u in rb["units"]}.get((point.unit or "").lower())
    if declared and unit and declared != unit:
        declared_dim = (rb["units"].get(declared) or {}).get("dimension")
        if declared_dim != unit_meta.get("dimension"):
            notes.append(
                f"vendor declares source unit '{point.unit}' ({declared_dim}) but the "
                f"proposal reads it as '{unit}' ({unit_meta.get('dimension')})"
            )

    # Catalogs that carry a harmonic order usually write it into the point name. This
    # cannot prove an order right, and says so, but it reliably catches the order being
    # misread: U19L1 proposed as order 9 passes every other check in this repo.
    order = entry.get("harmonic_order")
    if order is not None:
        digits = re.findall(r"[0-9]+", point.name)
        if digits and str(order) not in digits:
            notes.append(
                f"harmonic_order {order} does not appear in the point name "
                f"(found {', '.join(digits)}); confirm the order was read correctly"
            )

    return notes


# ----------------------------------------------------------------------------- assembly


def _provenance(spec: dict, model: str, endpoint: str, catalog_name: str) -> list[str]:
    return [
        "# MACHINE-PROPOSED. Review every line before merging.",
        f"# Drafted by propose.py on {date.today().isoformat()} from {catalog_name}",
        f"# Model: {model} at {provider_tag(endpoint)}",
        "# Semantics (quantity/phase/unit/variant/order) are proposed; everything else is",
        "# taken verbatim from the human-authored spec. Proposals are frequently valid and",
        "# wrong: see experiments/llm_mapping/findings.md.",
    ]


def assemble_source_schema(spec: dict, points: list[Point], header: list[str]) -> str:
    doc: dict[str, Any] = {}
    for key in (
        "vendor",
        "source",
        "owner",
        "contact",
        "sensitivity",
        "refresh_cadence",
        "source_schema_version",
        "shape",
        "naming_convention",
        "format",
        "access",
        "record",
        "defaults",
        "device_factors",
    ):
        if spec.get(key) is not None:
            doc[key] = spec[key]

    if spec.get("shape") == "long":
        # A long source has the same three logical fields on every row; the catalog
        # describes the key VALUES, which live in mapping.rows, not in fields.
        doc["fields"] = spec["long_fields"]
    else:
        field_type = spec["catalog"].get("field_type", "float")
        doc["fields"] = [
            {
                "name": p.name,
                "type": field_type,
                "unit": p.unit or None,
                "nullable": True,
                "desc": p.context or p.name,
            }
            for p in points
        ]
    body = yaml.safe_dump(doc, sort_keys=False, default_flow_style=False, allow_unicode=True)
    return "\n".join(header) + "\n\n" + body


def assemble_mapping(spec: dict, proposals: list[Proposal], header: list[str]) -> str:
    doc: dict[str, Any] = {
        "vendor": spec["vendor"],
        "mapping_version": spec.get("mapping_version", "0.1.0"),
        "target_schema_version": spec["target_schema_version"],
        "source": spec["source"],
    }
    long_shape = spec.get("shape") == "long"
    entries: list[dict[str, Any]] = []
    for proposal in proposals:
        if not proposal.ok:
            continue
        entry = dict(proposal.entry or {})
        clean: dict[str, Any] = {}
        if long_shape:
            clean["key"] = proposal.point.key
        else:
            clean["src"] = proposal.point.name
        for key in ("quantity", "phase", "unit"):
            clean[key] = entry.get(key)
        for key in ("variant", "harmonic_order", "aggregation"):
            value = entry.get(key)
            if value is not None and value != "none":
                clean[key] = value
        if long_shape:
            clean["desc"] = proposal.point.name
        entries.append(clean)
    doc["rows" if long_shape else "columns"] = entries
    body = yaml.safe_dump(doc, sort_keys=False, default_flow_style=False, allow_unicode=True)
    return "\n".join(header) + "\n\n" + body


def assemble_validation(spec: dict, proposals: list[Proposal], header: list[str]) -> str:
    """Structural rules from the record block, plus only those declared bounds that apply.

    Plausibility thresholds are never invented here. They are a domain decision, so the
    spec declares them and this selects the ones whose quantity actually got mapped.
    """
    rules: list[dict[str, Any]] = []
    record = spec.get("record") or {}
    # One field often plays several roles (a key that is also the row id), and emitting
    # the same rule once per role would put duplicates in a reviewed config.
    seen: set[str] = set()
    for key in ("key_field", "row_id_field", "meter_field", "timestamp_field"):
        name = record.get(key)
        if name and name not in seen:
            seen.add(name)
            rules.append({"field": name, "type": "not_null", "on_fail": "reject_row"})
    if record.get("value_field"):
        rules.append(
            {
                "entity": "measurement",
                "field": record["value_field"],
                "type": "not_null",
                "on_fail": "drop_row",
            }
        )

    mapped = {p.entry.get("quantity") for p in proposals if p.ok}
    for rule in spec.get("validation_defaults") or []:
        if rule.get("quantity") in mapped:
            rules.append(rule)

    doc = {"vendor": spec["vendor"], "rules": rules}
    body = yaml.safe_dump(doc, sort_keys=False, default_flow_style=False, allow_unicode=True)
    note = []
    if not (spec.get("validation_defaults") or []):
        note = [
            "# NOTE: the spec declared no validation_defaults, so this file carries only",
            "# structural not-null rules. Physical plausibility bounds are a domain",
            "# decision and must be authored before this vendor is trusted.",
        ]
    return "\n".join(header + note) + "\n\n" + body


def assemble_changelog(spec: dict, proposals: list[Proposal], model: str) -> str:
    mapped = sum(1 for p in proposals if p.ok)
    version = spec.get("mapping_version", "0.1.0")
    return (
        f"# Changelog: {spec['vendor']}\n\n"
        f"## {version} ({date.today().isoformat()})\n\n"
        f"- Initial machine-proposed mapping: {mapped} of {len(proposals)} catalog points, "
        f"drafted by `propose.py` using `{model}`.\n"
        f"- Semantics are proposed and unreviewed. Operational metadata and validation "
        f"thresholds are human-authored in the spec.\n"
        f"- Not to be merged before a domain review of the mapping entries.\n"
    )


def assemble_report(
    spec: dict, proposals: list[Proposal], model: str, endpoint: str, errors: list[str]
) -> str:
    mapped = [p for p in proposals if p.ok]
    unmapped = [p for p in proposals if not p.ok]
    flagged = [p for p in mapped if p.advisories]

    lines = [
        f"# Proposal review: {spec['vendor']}",
        "",
        f"Drafted {date.today().isoformat()} by `propose.py` using `{model}` "
        f"at `{provider_tag(endpoint)}`.",
        "",
        "**This is a draft, not a mapping.** Every entry below was produced by a language",
        "model reading a point name. The validator has confirmed the file is well formed and",
        "internally consistent; it cannot confirm that any entry is correct. On the one",
        "vendor where ground truth exists, proposals were 98 to 100% valid and 38 to 84%",
        "correct, so a clean validator run is the beginning of the review, not the end.",
        "",
        "## Summary",
        "",
        f"| Catalog points | {len(proposals)} |",
        "|---|---|",
        f"| Mapped | {len(mapped)} |",
        f"| Not mapped | {len(unmapped)} |",
        f"| Mapped with advisories | {len(flagged)} |",
        f"| Validator | {'clean' if not errors else f'{len(errors)} problem(s)'} |",
        "",
    ]

    if errors:
        lines += ["## Validator problems", "", "Nothing was written to `vendors/`.", ""]
        lines += [f"- {e}" for e in errors] + [""]

    if flagged:
        lines += [
            "## Read these first",
            "",
            "Checks the validator cannot make. A dimensional mismatch means the proposed unit",
            "could not measure the proposed quantity, which is the error class most often seen",
            "when a source is poorly documented.",
            "",
            "| Point | Proposed | Advisory |",
            "|---|---|---|",
        ]
        for proposal in flagged:
            summary = ", ".join(
                f"{k}={proposal.entry[k]}"
                for k in SCORED_FIELDS
                if proposal.entry.get(k) is not None
            )
            for note in proposal.advisories:
                lines.append(f"| `{proposal.point.name}` | {summary} | {note} |")
        lines.append("")

    if unmapped:
        lines += [
            "## Not mapped",
            "",
            "Left out of the mapping deliberately. A guessed entry that reaches the canonical",
            "fact is more expensive than a missing one, which is visible.",
            "",
            "| Point | Reason |",
            "|---|---|",
        ]
        lines += [f"| `{p.point.name}` | {p.error} |" for p in unmapped]
        lines.append("")

    lines += ["## All proposed entries", "", "| Point | Key | Proposed |", "|---|---|---|"]
    for proposal in mapped:
        summary = ", ".join(
            f"{k}={proposal.entry[k]}" for k in SCORED_FIELDS if proposal.entry.get(k) is not None
        )
        lines.append(f"| `{proposal.point.name}` | `{proposal.point.key}` | {summary} |")
    lines.append("")
    return "\n".join(lines)


# -------------------------------------------------------------------------------- gating


def stage_and_validate(root: Path, vendor: str, files: dict[str, str], workdir: Path) -> list[str]:
    """Validate the proposal in a copy of the repo containing only this vendor.

    Writing into vendors/ and validating afterwards would leave a broken repo behind on
    failure, so the gate runs somewhere disposable and the real tree is never touched
    until the proposal is clean.
    """
    staged = workdir / "staged"
    if staged.exists():
        shutil.rmtree(staged)
    for shared in ("canonical", "transforms", "targets", "meta-schemas", "serving"):
        shutil.copytree(root / shared, staged / shared)
    vendor_dir = staged / "vendors" / vendor
    vendor_dir.mkdir(parents=True)
    for name, text in files.items():
        (vendor_dir / name).write_text(text, encoding="utf-8")
    return validate(staged)


# ---------------------------------------------------------------------------------- cli


def stratified(points: list[Point], n: int) -> list[Point]:
    """An evenly spread sample, because a catalog is grouped and a head slice is biased."""
    if n <= 0 or n >= len(points):
        return points
    step = len(points) / n
    return [points[int(i * step)] for i in range(n)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--spec", type=Path, required=True, help="human-authored vendor spec")
    parser.add_argument("--out", type=Path, help="output directory (default proposals/<vendor>)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--shots", type=int, default=DEFAULT_SHOTS, help="worked examples")
    parser.add_argument("--limit", type=int, default=0, help="propose a stratified sample only")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--delay", type=float, default=0.0, help="pause between live calls")
    parser.add_argument("--max-tokens", type=int, default=300)
    parser.add_argument("--dry-run", action="store_true", help="print one prompt and exit")
    parser.add_argument(
        "--apply", action="store_true", help="install into vendors/<vendor> once validated"
    )
    args = parser.parse_args()

    spec = load_spec(args.spec)
    vendor = spec["vendor"]
    points = read_catalog(spec, args.spec)
    if args.limit:
        points = stratified(points, args.limit)

    rb = load_rulebook(ROOT)
    system = build_system_prompt(rb, spec.get("naming_convention", ""))
    shots = load_examples(ROOT, vendor, args.shots)

    if args.dry_run:
        for message in build_messages(system, shots, points[0]):
            print(f"--- {message['role']} ---\n{message['content']}\n")
        print(f"({len(shots)} examples, {len(points)} catalog points)")
        return 0

    api_key = api_key_for(args.endpoint)
    if not api_key:
        want = KEY_ENV_BY_HOST.get(urlparse(args.endpoint).hostname or "", "SECHA_LLM_API_KEY")
        print(f"No API key for this endpoint. Set {want} in the environment.")
        return 1

    client = ModelClient(
        args.endpoint,
        api_key,
        ROOT / ".cache" / "propose",
        args.timeout,
        args.delay,
        args.max_tokens,
    )

    requires_order = {
        q
        for q, meta in rb["quantities"].items()
        if "harmonic_order" in (meta.get("requires") or [])
    }
    long_shape = spec.get("shape") == "long"

    proposals: list[Proposal] = []
    for i, point in enumerate(points, 1):
        print(f"  [{i}/{len(points)}] {point.name}", flush=True)
        reply, err = client.complete(args.model, build_messages(system, shots, point))
        if reply is None:
            proposals.append(Proposal(point, error=f"no reply: {err}"))
            continue
        entry = parse_reply(reply)
        if entry is None:
            proposals.append(Proposal(point, error="reply was not a single mapping"))
            continue
        if not long_shape and entry.get("quantity") in requires_order:
            # A wide mapping is a `columns:` entry, whose schema has no harmonic_order.
            # Harmonic families belong in a `generated:` block, which is pattern inference
            # over field names rather than reading one point, so it is not drafted here.
            proposals.append(
                Proposal(point, error="harmonic quantity on a wide source needs a generated: rule")
            )
            continue
        proposals.append(Proposal(point, entry=entry, advisories=advisories_for(entry, point, rb)))

    header = _provenance(spec, args.model, args.endpoint, Path(spec["catalog"]["path"]).name)
    files = {
        "source_schema.yaml": assemble_source_schema(spec, points, header),
        "mapping.yaml": assemble_mapping(spec, proposals, header),
        "validation.yaml": assemble_validation(spec, proposals, header),
        "CHANGELOG.md": assemble_changelog(spec, proposals, args.model),
    }

    out = args.out or (ROOT / "proposals" / vendor)
    out.mkdir(parents=True, exist_ok=True)
    errors = stage_and_validate(ROOT, vendor, files, out)

    for name, text in files.items():
        (out / name).write_text(text, encoding="utf-8")
    (out / "PROPOSAL.md").write_text(
        assemble_report(spec, proposals, args.model, args.endpoint, errors), encoding="utf-8"
    )

    mapped = sum(1 for p in proposals if p.ok)
    flagged = sum(1 for p in proposals if p.ok and p.advisories)
    print(f"\n{mapped} of {len(proposals)} points mapped, {flagged} with advisories")
    print(f"written: {out}")

    if errors:
        print(f"\nVALIDATOR REJECTED the proposal ({len(errors)} problem(s)):")
        for err in errors[:20]:
            print("  -", err)
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more, see PROPOSAL.md")
        print("\nNothing was installed into vendors/. Fix the spec or the catalog and re-run.")
        return 1

    print("Validator: clean.")
    if args.apply:
        target = ROOT / "vendors" / vendor
        if target.exists():
            print(f"\nRefusing to overwrite existing vendors/{vendor}. Move it aside first.")
            return 1
        target.mkdir(parents=True)
        for name, text in files.items():
            (target / name).write_text(text, encoding="utf-8")
        print(f"installed: vendors/{vendor} (review the diff before committing)")
    else:
        print(f"Review {out / 'PROPOSAL.md'}, then re-run with --apply to install.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
