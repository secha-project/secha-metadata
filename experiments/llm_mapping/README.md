# Which model should author mappings?

An experiment, not part of the CI-gated contract. It answers one question with evidence
instead of opinion: **given a vendor catalog point, can a model produce the canonical
mapping entry a human would have written, and which model does it best?** Local models
on the university service and commercial models are scored on identical ground truth.

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

See [findings.md](findings.md) for the full write-up. Accuracy is limited less by the
model than by how well the source is documented, and that holds across four model
families.

Local models, `phi4-14b`, 56 cases:

|  | cross-vendor examples | in-vendor examples |
|---|---|---|
| **no convention** | 54% | 79% |
| **with convention** | 79% | **96%** |

Local against commercial against open weight, 68 cases, cross-vendor examples:

| Condition | phi4-14b (local) | gpt-4.1 (commercial) | mistral-medium (commercial) | deepseek-v4-pro (open weight) |
|---|---|---|---|---|
| **without convention** | **56%** | 38% | 43% | 41% |
| **with convention** | 79% | 78% | **84%** | **84%** |
| gain from documenting | +23 | +40 | +41 | +43 |

Three results. **Without the naming convention the local 14B model beats every larger
model tested**, including a frontier open-weight one, which is the arm most likely to
have overturned that finding because it removes the confound of renting. **With the
convention supplied all four land between 78% and 84%**, despite spanning 14 billion
parameters to frontier scale, so documenting the source compresses a wide capability
range into a narrow band. And the open-weight model gains +43, matching the commercial
pattern rather than phi4's +23, which shows the smaller gain belongs to phi4 starting
higher rather than to anything about local against rented models.

The two models tied at 84% both score exactly 57 of 68. Six of the eleven DeepSeek
misses are the ground-truth inconsistency described in `findings.md` section 4, where
energy counters are mapped as `phase: none` while the instantaneous totals measuring the
same quantity are mapped as `three_phase`. A consistent answer key would put that model
at 61 of 68. The key is deliberately left alone, but two independent models have now
flagged the same defect.

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

Replies are cached in `.cache/<provider>/<model>/`, keyed by the exact request, so
re-scoring or changing the report costs nothing and the shared university service is not
hit twice for the same question. Delete `.cache/` to force fresh calls.

## Selecting a commercial model

The same harness scores any OpenAI-compatible endpoint, so a commercial model is
compared on exactly the ground truth, prompt and scoring the local models faced.
Only the endpoint changes.

GitHub Copilot is reached through the `copilot-api` proxy, which exposes Copilot
as an OpenAI-compatible service on localhost. Authenticate once, start it with a
rate limit, then point the harness at it:

```bash
# once: device-flow login with your GitHub account
node dist/main.js auth

# per session: serve on 4141, one request per 2 seconds, queue rather than fail
node dist/main.js start --rate-limit 2 --wait
```

```bash
COPILOT=http://localhost:4141/v1/chat/completions

# see what the account can reach
python benchmark.py --list-models --endpoint $COPILOT

# stage 1: screen the candidates cheaply on 20 cases
python benchmark.py --endpoint $COPILOT --delay 2 --limit 20 --models <a> <b> <c> --out results/copilot_screen

# stage 2: full 68 cases on the best one or two, which is what gets reported
python benchmark.py --endpoint $COPILOT --delay 2 --models <winner> --out results/copilot_full
```

Screening before confirming keeps the request volume down, which matters here:
the proxy's own documentation warns that bulk scripted use can trigger GitHub's
abuse detection and suspend Copilot access. Use `--delay`, keep the candidate
list short, and rely on the cache so no question is ever asked twice.

Replies are cached per provider, so Aviary and Copilot results cannot collide
even if two services offer a model of the same name.

**A caveat worth recording in the thesis.** Copilot does not pin or document
which build of a model serves a request, so "the commercial model" is not a
reproducible identity through this proxy. Use it to survey the field and to
choose; if a pinned, versioned endpoint is available for the result you actually
report, prefer it and say which was used.

## Selecting an open-weight frontier model

The commercial arm answers "how good is a model you rent". It does not answer
"how good is a model you could host yourself", which is the question that
matters for a university deployment where partner metadata should not leave the
premises. NVIDIA NIM serves open-weight models on a free tier, so a frontier
open-weight model can be scored on the same ground truth as everything else.

```bash
NIM=https://integrate.api.nvidia.com/v1/chat/completions
MODEL=deepseek-ai/deepseek-v4-pro-0813

python benchmark.py --list-models --endpoint $NIM

# the two conditions that matter, full 68 cases each
python benchmark.py --endpoint $NIM --models $MODEL --timeout 900 --delay 1     --out results/nv_deepseek_conv
python benchmark.py --endpoint $NIM --models $MODEL --timeout 900 --delay 1     --no-convention --out results/nv_deepseek_noconv
```

**This model has since been retired.** NVIDIA took `deepseek-ai/deepseek-v4-pro-0813`
out of service on 2026-09-14, and requests for it now return `HTTP 410 Gone`. The
recorded results still re-score from the cache. To run this arm again, choose a current
open-weight model with `--list-models`.

Two practical notes, both of which cost time to learn.

**Give it a long `--timeout`.** Median replies took 138 seconds with the naming
convention and 280 seconds without, on the free tier. That is queueing, not
generation: the model emits about a dozen tokens for a mapping entry, and raising
`--max-tokens` tenfold changes neither the answer nor the latency. Median latency
against this endpoint therefore measures the hosting, not the model, and should not be
compared with latencies from a service that is not queueing. At those medians a full
condition takes several hours, so run it in the background and rely on the cache.

**Check `finish_reason` before believing a low score.** Several models on this
service return their reasoning trace in a separate `reasoning_content` field
and leave `content` empty when the generation cap binds. A model that thinks
past its budget produces no answer at all, which looks exactly like a model that
cannot follow instructions. `--max-tokens` exists for that case, and the client
now reports a truncated reply as truncation rather than scoring it as wrong.
The default of 300 is left alone deliberately: the cache key is a hash of the
request, so changing the default would invalidate every reply already recorded
against every other provider.

## Notes

- The catalog CSV is partner metadata and is not committed here. Point `--catalog` at it.
- `temperature` is 0 so a run is reproducible.
- Reasoning models such as `deepseek-r1-8b` emit a `<think>` block before answering. The
  parser strips it, so they can be compared fairly, though they are slower.
- If a model scores far below the others, check the context window first. Ollama-backed
  endpoints often default to a small window regardless of what the model supports, which
  truncates the examples rather than the question and looks like poor accuracy.
