# Findings: can a model author canonical mappings?

Runs from 2026-08-10 (local models, TUNI Aviary), 2026-08-31 (commercial models,
GitHub Copilot and Mistral) and 2026-09-03 (open weight, NVIDIA NIM). Ground truth is
the 68 hand-curated `procem_kampusareena_pq` rows. Every number below is reproducible
from `benchmark.py`; replies are cached, so re-running costs nothing.

## 1. Which model

68 cases, cross-vendor examples, no naming convention in the prompt.

| Model | Usable reply | Exact | Valid | Median s |
|---|---|---|---|---|
| **phi4-14b** | 100% | **56%** | 99% | 0.8 |
| granite4-32b | 100% | 34% | 100% | 1.0 |
| mistral-nemo-12b | 100% | 28% | 100% | 0.8 |
| gemma3-12b | 100% | 19% | 82% | 1.1 |
| llama3.1-8b | 0% | n/a | n/a | 2.6 |

`phi4-14b` wins clearly, and it is less than half the size of the runner-up. Parameter
count did not predict performance on this task, which is the argument for measuring
rather than assuming.

`llama3.1-8b` answered every call but never with a single mapping: it echoed the whole
example list back each time. That is an instruction-following failure, not an
availability or knowledge one, which is why the report separates those columns.
`gemma3-12b` and `llama3.1-8b` also hit intermittent `model not found` errors from the
service, worth reporting to whoever maintains Aviary.

## 2. What actually limits accuracy

The failures were not spread evenly. Of phi4's 30 misses at 56%, twenty were the
`variant` field and fourteen of those were the same mistake: the model called a
fundamental-component point `none`.

Look at the point names it missed: `U1L1`, `I1L1`, `P1L1`, `Q1L1`, `S1L1`. In Laatuvahti
naming the numeral before the phase is the harmonic order, and order 1 means the
fundamental. Nothing in the prompt said so. Likewise `Qf` for Fryze, `U31` for the
line-to-line voltage between L3 and L1, `DPF` as a distinct quantity from `PF`.

These are not reasoning failures. They are missing metadata. A human author needed the
same knowledge, and would normally write it down.

## 3. So we wrote it down

`vendors/procem_kampusareena_pq/source_schema.yaml` gained a `naming_convention` block:
about twenty lines describing the vendor's point-name grammar. It documents the grammar
only, never a point-to-quantity answer. The benchmark reads it from the source schema
like any other config, so any vendor that documents its naming gets the benefit with no
code change.

Full 2x2 on an identical 56-case test set (12 stratified cases reserved in every
condition so the runs stay comparable), phi4-14b:

|  | cross-vendor examples | in-vendor examples |
|---|---|---|
| **no convention** | 54% | 79% |
| **with convention** | 79% | **96%** |

Read it three ways:

- **Documenting the naming convention is worth +25 points** (54 to 79), and it is a
  one-time cost of a few lines of YAML that belongs in the repo anyway.
- **A dozen in-vendor examples are worth the same +25 points** (54 to 79). Two very
  different interventions, the same size of effect.
- **Together they reach 96%**, or 54 of 56 correct. Slightly less than the sum of the
  parts, which makes sense: both are teaching the same conventions, one by description
  and one by example.

The practical reading for onboarding a new source: write the naming convention down
first, because it is cheap and it helps immediately. Once a handful of entries have been
mapped by hand, feeding those back as examples closes most of the remaining gap.

## 4. The last two errors are ours, not the model's

At 96%, exactly two cases remain, and they are the same case twice:

```
LV3_EVCharging_EQ1_plus    expected phase none, model said three_phase
LV3_EVCharging_EQ1_minus   expected phase none, model said three_phase
```

The model followed the documented convention correctly. Our own mapping is what is
inconsistent: instantaneous three-phase totals (`P`, `Q1`, `S`) are mapped as
`phase: three_phase`, while the cumulative energy counters measuring the same
three-phase quantity are mapped as `phase: none`.

The benchmark found a real inconsistency in the hand-curated ground truth. Deliberately
not "fixed" here, because changing the answer key after seeing the results would taint
the experiment, and because which convention is right is a domain question worth putting
to the EE side. The consistent choice looks like `three_phase` for the energy counters.

## 5. Operationally: valid is not the same as correct

Across every condition, validity sat at 98 to 100% while accuracy ranged from 19% to 96%.
Almost every wrong proposal was still a legal config that `validate.py` would accept and
that could be merged.

That is the honest framing for using a model here. The validator stops malformed configs,
not wrong ones. It removes the failure mode where bad output corrupts the pipeline, and
it does not remove the need for a human to read the diff.

## 6. A commercial model, on the same ground truth

The research plan asks for a locally hosted model compared against a commercial
one. Two providers were tried, on exactly the ground truth, prompt and scoring
the local models faced. Only the endpoint changed.

**GitHub Copilot**, reached through the `copilot-api` proxy, turned out to be
mostly unavailable. The account lists 55 models and can call four, all GPT-4
class; every frontier model (Claude, Gemini, GPT-5, Kimi) is refused with
`model_not_supported`. That is a per-model entitlement rather than a quota
limit, since 182 of 200 premium requests were unused, and the GPT-4 class
models consume no premium quota at all. The best of the four,
`gpt-4.1-2025-04-14`, reached 78% with the naming convention and 38% without.

**Mistral**, used directly, reached 47 of its 48 listed models on a free-tier
key on 2026-08-31; only `mistral-large` was tier-blocked. That did not last: by
2026-09-15 the free plan gave every Medium and Small model tried a limit of zero
requests. Mistral also exposes a clean size ladder inside one model family, which
makes it possible to ask whether capability predicts accuracy on this task.

Screening on 20 stratified cases with the convention supplied:

| Model | Exact | Note |
|---|---|---|
| ministral-8b-2512 | 85% | |
| mistral-small-2603 | 80% | |
| mistral-medium-latest | 80% | |
| ministral-14b-2512 | 75% | |
| magistral-medium-latest | 73% | answered only 75%, all HTTP 429 throttling |
| ministral-3b-2512 | 55% | |

That screen then mis-ranked its own finalists. On the full 68 cases,
`mistral-medium-latest` reached 84% while `ministral-8b-2512` fell to 78% and
`mistral-small-2603` to 74%. Twenty cases is enough to eliminate a weak
candidate and not enough to order the strong ones: a screen selects, it does not
rank. The three-way comparison, all on 68 cases with cross-vendor examples:

| Condition | phi4-14b (local) | gpt-4.1-2025-04-14 | mistral-medium-latest |
|---|---|---|---|
| **without convention** | **56%** | 38% | 43% |
| **with convention** | 79% | 78% | **84%** |
| gain from documenting | +23 | +40 | +41 |

Three things follow, and the second is the one worth arguing in the thesis.

The best commercial model available beats the best local one, but by six points
rather than by a category. `mistral-medium-latest` at 84% is the strongest
result recorded here.

**Without the naming convention, the local 14B model beats both commercial
models.** That is not a small effect: 56% against 38% and 43%. Documentation is
not a substitute for capability at the margin, it dominates it. The bottom row
makes the same point from the other side, since the commercial models gain
roughly twice as much from the convention as the local one does. A capable
model without documentation is not more accurate, it is more confidently wrong
across more fields: `mistral-medium` commits 66 individual field errors without
the convention and 12 with it, and `gpt-4.1` spreads its errors across quantity,
phase, variant and harmonic order rather than concentrating them in variant the
way phi4 does.

Capability did not predict accuracy inside the Mistral family either. The 3B
model is clearly worse at 55%, but above that the ordering is not monotonic in
size, which matches what the local comparison already showed when a 14B model
beat a 32B one. Across three model families now, size has failed to predict
performance on this task, and section 7 adds a fourth: a frontier-tier
open-weight model scored the same 84% as this mid-tier commercial one.

**A reproducibility caveat that affects the recommendation.**
These runs requested `mistral-medium-latest`, a name that moves to newer weights
when Mistral releases them. A dated identifier does exist: on 2026-09-15 the
models endpoint listed `mistral-medium-2604` among the aliases of
`mistral-medium-latest`. An earlier version of this section said there was no
such alias, which was wrong. The runs did not use it, though, and the cache keeps
only each reply's text and timing, not the model name the provider reported. So
which snapshot produced these results cannot be shown after the fact.
`mistral-small-2603` and `ministral-8b-2512` were requested by dated name and
scored 10 and 6 points lower, but that trade is not needed: a future run can
request `mistral-medium-2604` and keep the medium tier under a fixed name. Record
which identifier was used, and the model name the provider reports, either way.

## 7. An open-weight frontier model

The commercial arm answers how good a model you rent is. It does not answer how
good a model you could host yourself is, and that is the question a university
deployment actually faces, since partner metadata is easier to justify sending
to a machine on the premises. NVIDIA NIM serves open-weight models on a free
tier, so `deepseek-v4-pro-0813` was scored on exactly the ground truth, prompt
and scoring every other arm faced. Only the endpoint changed.

Availability was the opposite of the Copilot experience: 81 models listed and
`deepseek-ai/deepseek-v4-pro-0813` callable straight away.

Before scoring, one thing had to be ruled out. A reasoning model spends its
generation budget thinking before it writes anything, so a cap set for ordinary
models can leave the answer field empty and make a capable model look as though
it cannot follow instructions. The same request was therefore sent at a cap of
300 and of 3000 tokens. Both returned `finish_reason: stop`, both used 12
completion tokens, and both produced identical text. The standard cap is
provably not binding for this model, so its numbers sit on exactly the footing
the other arms stand on rather than needing an asterisk.

All four arms, 68 cases, cross-vendor examples:

| Condition | phi4-14b | gpt-4.1-2025-04-14 | mistral-medium-latest | deepseek-v4-pro-0813 |
|---|---|---|---|---|
| | local, 14B | commercial | commercial | open weight, frontier |
| **without convention** | **56%** | 38% | 43% | 41% |
| **with convention** | 79% | 78% | **84%** | **84%** |
| gain from documenting | +23 | +40 | +41 | +43 |

Three results, and the first is what the arm was added to test.

**The local 14B model still wins on an undocumented source.** 56% against 41%
for an open-weight frontier model, 43% and 38% for the commercial ones. This
arm was the one most likely to overturn that claim, because it removes the
confound of renting: it is a frontier-scale model a university could host
itself, so a failure here could not be blamed on the commercial services. It
did not overturn it. Across four model families now, the smallest model is the
only one that does well when the source is not documented.

**Documentation is an equaliser.** With the convention supplied, all four arms
land in a narrow band from 78% to 84%, despite spanning 14 billion parameters
to frontier scale. Without it they range from 38% to 56% and the ordering
inverts with respect to capability. The gain row makes the same point from the
other side, and it answers the question the arm was added to settle:
`deepseek-v4-pro` gains +43, which is the commercial pattern rather than phi4's
+23. The distinction is therefore not local against rented, as the design
allowed for. It is that phi4 starts far higher and so has less room to gain.

**The best models are now limited by the answer key.** `deepseek-v4-pro` and
`mistral-medium` tie at 84%, both scoring exactly 57 of 68, and the DeepSeek
failures collapse into two systematic patterns with nothing scattered:

```
7x  variant  fundamental -> none     I1L2 I1L3 P1L1 P1L2 P1L3 EQ1_plus EQ1_minus
6x  phase    none -> three_phase     EP_plus EP_minus EQf_plus EQf_minus EQ1_plus EQ1_minus
```

Every point in the second group is a cumulative energy counter, which makes it
the inconsistency recorded in section 4 rather than a model error. The mapping
calls an instantaneous three-phase total `three_phase` and calls the energy
counter measuring the same three-phase quantity `none`. This model applied the
documented convention consistently to all six counters; `phi4-14b` at 96% found
two of them. Four of the six are wrong in phase alone, so resolving the answer
key in the consistent direction would put this model at 61 of 68, or 90%.

The answer key is still not being changed, for the reasons given in section 4.
The point worth recording is different: a second, independent and stronger model
has now flagged the same defect, and it found every instance rather than a third
of them. When the best model's remaining errors sit mostly in cases where the
ground truth disagrees with itself, the measurement is at the precision limit of
its own test set, and 68 hand-curated cases will not separate models above
roughly 85%.

**Latency here measures the hosting, not the model.** A mapping entry is about a
dozen tokens, yet medians were 138 seconds with the convention and 280 seconds
without, and raising the cap tenfold changed neither the answer nor the time.
The figure is queueing on a free tier and must not be compared with the
sub-second medians from services that were not queueing.

**The free tier degraded mid-study, which is itself a finding.** Gaps between
successful replies grew to half an hour as failed attempts consumed the retry
budget, and five of the 68 requests in the undocumented condition were lost to
`HTTP 504` after three retries each. A probe with an eight-token prompt failed
the same way, so this is an unhealthy endpoint rather than throttling for
volume, and no change to pacing or prompt size would have helped. Accuracy for
that condition is therefore computed over the 63 answered cases, as everywhere
else in this report, which is why the cell reads 41% rather than the 38% it
would show if the provider's failures were charged to the model.

**A date-pinned identity is not a guarantee of availability.** An earlier draft
of this section argued that `deepseek-v4-pro-0813` should break the tie with
`mistral-medium-latest`, because a date-pinned model can be re-run against the
same weights later. That argument did not last. NVIDIA retired the model on
2026-09-14, ten days after these runs finished, and requests for it now return
`HTTP 410 Gone`. A pinned identifier guarantees that a name refers to fixed
weights; it does not guarantee that anyone keeps serving them. Neither model tied
at 84% can now be queried as it was: one name floats to newer weights, and the
other resolves to nothing. The numbers stand as a record, because the cached
replies re-score exactly, but no hosted model in this study is reproducible by
generation. That needs weights under the project's own control, which is an
argument for the local arm rather than for either of these.

## 8. Limitations

- The naming convention was written **after** seeing the failure analysis, so it is
  better targeted than one written blind from vendor documentation would be. The +25
  points should be read as an upper estimate of what documentation buys.
- One vendor, one model family for the deep runs, one temperature-0 sample per case. No
  repeated sampling, so small differences between conditions are not significant.
- 68 cases is a small test set. Percentage points are worth roughly 1.5 cases each.
- The comparison is bounded by what the accounts could reach. No current
  frontier *commercial* model was tested: Copilot refuses them per-model and
  Mistral's free tier blocks `mistral-large`. The open-weight arm does reach
  frontier scale, so the claim "capability does not substitute for
  documentation" is supported up to GPT-4.1, mistral-medium and
  deepseek-v4-pro, but not against a current frontier commercial model.
- Neither 84% result can be regenerated. The mistral-medium runs requested the
  moving name `mistral-medium-latest` and did not record which snapshot answered,
  although the dated name `mistral-medium-2604` exists. `deepseek-v4-pro-0813` was
  requested by dated name, but its provider retired it on 2026-09-14. Cached
  replies re-score exactly; new replies from the same weights cannot be guaranteed.
- The open-weight arm lost five of 68 requests in the undocumented condition to
  provider errors, so that cell rests on 63 cases rather than 68. Its documented
  condition answered all 68.
- Latency is not comparable across providers. The open-weight figures are
  dominated by free-tier queueing, not by generation, and the same model on
  dedicated hardware would report something entirely different.
- The catalog supplies a `path` field that hints at the quantity group
  (`.../Voltage`, `.../Power`). Sources without that hint would likely score lower.
