# Which local model should author mappings?

An experiment, not part of the CI-gated contract. It answers one question with evidence
instead of opinion: **given a vendor catalog point, can a model produce the canonical
mapping entry a human would have written, and which of the TUNI models does it best?**

## Why this is measurable here

The answer key already exists. The 68 `rows:` entries in
`vendors/procem_kampusareena_pq/mapping.yaml` were curated by hand from the vendor
catalog and are known correct, so a proposal can be scored field by field:
quantity, phase, variant, harmonic_order, aggregation, unit.

Two design choices keep it honest:

- **No leakage.** In the default `cross` mode the few-shot examples come from the *other*
  vendor (`mx_electrix`). The model never sees a ProCem answer before being asked for one,
  which is also the real situation: one source is onboarded, and a second is arriving.
  `--shots holdout:N` instead takes N ProCem examples and scores the remainder, showing
  the ceiling when in-vendor examples exist. The gap between the two modes is itself
  interesting.
- **The prompt is generated from the rulebook.** Quantities, enums and the unit registry
  are read from `canonical/`, so the instructions can never drift from the schema the
  answer is scored against. Add a quantity to the vocabulary and the prompt updates itself.

## What gets reported

| Metric | Why it matters |
|---|---|
| **Exact** | every scored field matched, so the entry could be merged as written |
| **Valid** | the proposal passes `validate.py`, so it could reach a pull request at all |
| Per-field | shows *where* a model fails, e.g. good at quantity, weak at variant |
| Median latency | a 32B model that takes a minute per point is a different proposition |

Exact and Valid answer different questions. A wrong but valid proposal costs a reviewer
some time. An invalid one is rejected automatically and costs nothing, which is the whole
point of having the validator in front of the model.

## Results so far

See [findings.md](findings.md) for the full write-up. The short version: `phi4-14b` is the
best of the local models and beats a model twice its size; accuracy is limited less by the
model than by how well the source is documented; and documenting the vendor's naming
convention in `source_schema.yaml` is worth as much as a dozen worked examples.

|  | cross-vendor examples | in-vendor examples |
|---|---|---|
| **no convention** | 54% | 79% |
| **with convention** | 79% | **96%** |

## Running it

```bash
pip install -r requirements.txt
cp .env.template .env          # add SECHA_AVIARY_API_KEY

python benchmark.py --dry-run              # inspect the prompt, no API calls
python benchmark.py --limit 10             # cheap smoke run against every default model
python benchmark.py                        # full run
python benchmark.py --models granite4-32b  # one model

# the 2x2. --holdout-n reserves the same stratified cases in every condition, so the
# test set is identical and the four runs are directly comparable.
python benchmark.py --models phi4-14b --holdout-n 12 --shots cross   --no-convention
python benchmark.py --models phi4-14b --holdout-n 12 --shots holdout --no-convention
python benchmark.py --models phi4-14b --holdout-n 12 --shots cross
python benchmark.py --models phi4-14b --holdout-n 12 --shots holdout
```

`--no-convention` ignores the vendor's `naming_convention` block, which is the A/B
baseline. With it enabled (the default) the block is read from `source_schema.yaml`, so
documenting a source improves authoring accuracy with no change to this script.

Results are written to `results/comparison.md` (a table ready to paste into the thesis)
and `results/raw.json` (every miss, with expected and actual, for error analysis).

Replies are cached in `.cache/` keyed by model and prompt, so re-scoring or changing the
report costs nothing and the shared university service is not hit twice for the same
question. Delete `.cache/` to force fresh calls.

## Notes

- The catalog CSV is partner metadata and is not committed here. Point `--catalog` at it;
  the default is the working copy under `RP and Data/secha-data-procem/`.
- `temperature` is 0 so a run is reproducible.
- Reasoning models such as `deepseek-r1-8b` emit a `<think>` block before answering. The
  parser strips it, so they can be compared fairly, though they are slower.
- If a model scores far below the others, check the context window first. Ollama-backed
  endpoints often default to a small window regardless of what the model supports, which
  truncates the examples rather than the question and looks like poor accuracy.
