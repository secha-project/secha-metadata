# Findings: can a local model author canonical mappings?

Runs from 2026-08-10 against TUNI's Aviary endpoint. Ground truth is the 68 hand-curated
`procem_kampusareena_pq` rows. Every number below is reproducible from `benchmark.py`;
replies are cached, so re-running costs nothing.

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

## 6. Limitations

- The naming convention was written **after** seeing the failure analysis, so it is
  better targeted than one written blind from vendor documentation would be. The +25
  points should be read as an upper estimate of what documentation buys.
- One vendor, one model family for the deep runs, one temperature-0 sample per case. No
  repeated sampling, so small differences between conditions are not significant.
- 68 cases is a small test set. Percentage points are worth roughly 1.5 cases each.
- The catalog supplies a `path` field that hints at the quantity group
  (`.../Voltage`, `.../Power`). Sources without that hint would likely score lower.
