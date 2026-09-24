# Findings: the Kempower held-out test

The protocol is in [PROTOCOL.md](PROTOCOL.md). The pre-registered scores are in
[REPORT.md](REPORT.md), written by `score.py`. Breakdowns marked *post hoc* come from
`analysis_posthoc.py`, written after unsealing; they add detail and change no
pre-registered figure. Each run drafts five columns, so every result is a count from a case
study, not a rate.

Order of events: pre-registration committed `2c98448` (10:41 UTC); drafts sealed
unopened; gold rulebook sealed 10:51 and committed `569dc78` (10:58); unsealed 10:59.

## 1. With the vocabulary as it stood, no column could be answered

The hand-authored rulebook needed something the drafts were never offered for every one of
the five columns: two quantities (`state_of_charge`, `temperature`) and one phase value
(`dc`). So under C0 and C1 an exact draft was impossible by construction, in every arm, and
the useful question is how each draft failed. That is itself the first finding for RQ3: the
first vendor from outside power quality forced a vocabulary change, where ProCem needed
none.

## 2. Missing quantities were invented, and the validator caught every one

For `soc` and `tempC`, 12 of 12 answers (3 arms, 2 conditions, 2 columns) named a quantity
outside the vocabulary. None was forced onto an existing quantity, and the gate rejected
all 12.

- 8 of the 12 invented names are exactly the names the rulebook adopted.
- 2 were abstentions in disguise: `kimi-k3` wrote `quantity: none` and `phi4-14b` wrote
  `quantity: unknown` with no phase or unit. The prompt offers no way to decline, so the
  models made one.
- `codestral-2508` with the convention used the column names themselves (`soc`, `tempC`).

So before a vendor's concepts exist in the vocabulary, the useful output of a draft is its
invented names: they are proposals for the vocabulary change, not mappings. Whether a
draft invents or force-fits plausibly depends on whether the vocabulary holds a near
neighbour; state of charge and temperature had none, so this test cannot say.

## 3. A missing phase value was force-fitted, and nothing caught it

The three electrical columns needed phase `dc`, which did not exist. All 18 of those
entries under C0 and C1 used a phase the vocabulary had, so the gate never questioned their
phase (it did object to their `aggregation` key, section 5). 11 chose `none`, the least
wrong answer available; 7 asserted an AC phase that a DC output does not have (`phi4-14b`
wrote `three_phase` 6 times, `codestral-2508` wrote `L1` once). No draft invented a phase,
although every one invented a quantity.

This asymmetry is the most useful practical result. **A missing quantity produces a visible
error; a missing qualifier produces a plausible wrong answer.** The validator guards the
vocabulary's nouns, not the distinctions its enums fail to make.

## 4. With the vocabulary in place, documentation decided the phase

Condition C2 re-ran the same arms against the extended vocabulary (1.3.0 with phase `dc`).

| Arm | Quantity right | Unit right | `dc` chosen, with convention | `dc` chosen, without |
|---|---|---|---|---|
| `codestral-2508` | 10/10 | 10/10 | 3/3 | 0/3 |
| `phi4-14b` | 10/10 | 10/10 | 2/3 | 0/3 |
| `kimi-k3` | 10/10 | 10/10 | 3/3 | 0/3 |

Every quantity and unit was right, 30 of 30. The phase was decided by one sentence of the
convention: "power, current and voltage most likely describe the DC output to the vehicle".
With it, the drafts chose `dc` in 8 of 9 entries; without it, in 0 of 9, even though `dc`
was on offer.

## 5. The remaining disagreement is one judgment in the gold

No draft, in any condition, marked `soc` or `tempC` as instantaneous. The gold does,
because they lack the `avg` prefix the other three carry. The provider has not confirmed
this, so it is a reading of the naming grammar rather than a fact. *Post hoc sensitivity:*
had the gold left both columns to the source default (average), C2 with the convention would
score 5/5 exact for `codestral-2508` and `kimi-k3` and 4/5 for `phi4-14b`, against 3/5, 3/5
and 2/5 as pre-registered. Both are reported; the pre-registered figure stands.

A related observation: every draft in every condition wrote `aggregation: average`
explicitly on the three `avg` columns. The frozen mapping schema did not allow an
aggregation on a wide column, so those entries account for 3 gate problems in every C0 and
C1 draft (of 5, or of 9 for `phi4-14b` without the convention). The drafts reached for the
same capability the rulebook had to add, per-column aggregation, though for different
columns. It is also why *strict* exact, the benchmark's definition, is 0 in every run: an
explicit `average` never equals the gold's inherited one, though the engine writes the same
value for both. The *effective* figures used here compare what the engine writes.

## 6. Correction effort

Field edits that turn each draft into the gold, aggregation compared as the engine writes
it (pre-registered). Out of 30 scored fields (5 entries, 6 fields each). Under C0 and C1
the vocabulary change itself (two quantities and a phase value) is extra work on top.

| Arm | C0 | C1 | C2 without convention | C2 with convention |
|---|---|---|---|---|
| `codestral-2508` | 5 | 7 | 5 | **2** |
| `phi4-14b` | 8 | 5 | 5 | **3** |
| `kimi-k3` | 6 | 5 | 5 | **2** |

With the vocabulary and the documentation in place, a draft needed 2 or 3 field edits; all
three arms needed 5 without the documentation. The ProCem draft needed a review of 173
points; this one is five entries, so the absolute saving is small, and the result says more
about what makes a draft right than about time.

## 7. The predictions

- **P1 held, but not the way expected.** No column was left unmapped, and every `soc` and
  `tempC` answer was force-fitted or invented, as predicted. All 12 were invented; the
  force-fit the prediction worried about never happened.
- **P2 held for quantities, partly for phase.** All three electrical columns got the right
  quantity in every arm and condition. Without the convention `phi4-14b` followed the AC
  examples (`three_phase`) and `codestral-2508` did once (`L1`); `kimi-k3` did not. With
  it, `codestral-2508` and `kimi-k3` converged on `none`; `phi4-14b` did not.
- **P3 did not hold.** Under C0 and C1 the convention mostly changed the invented names
  (and made `codestral-2508` worse, 5 to 7 edits); under C2 it decided the phase, the
  largest single effect in the test.

## 8. What this adds to RQ4a

On ProCem, documenting the source was the lever: accuracy rose 23 to 43 points with it.
Kempower adds an order to that. **Vocabulary coverage comes first**: no draft can be more
right than the vocabulary allows, and a missing qualifier fails silently. **Documentation
comes second**: once the vocabulary could express the answer, one sentence of it decided
the phase. **The model comes last**: with the vocabulary in place, every arm got every
quantity and unit right, and the arms differed mainly in how far they followed the AC
examples against the documentation; `phi4-14b` chose `three_phase` in 10 of its 12
electrical entries, `codestral-2508` and `kimi-k3` in none.

## 9. Limitations

- Five columns per run: a case study, not a rate.
- One author wrote the gold. Two of its decisions are readings, not facts: that the
  electrical columns are DC, and that `soc` and `tempC` are instantaneous (section 5).
- `propose.py` offers no way to decline; abstention would need a tool change this test did
  not make.
- The whole-draft gate for `kimi-k3` C1 is the recomputed 5 problems, not the clean result
  its `PROPOSAL.md` shows (protocol deviation D1).
- The pre-registered split of gate problems undercounts the proposal-caused ones
  (deviation D3): by file, every gate problem in every run is in the drafted mapping.
- `propose.py` records reply text but not the model name the service reports; a probe the
  same morning recorded `ollama/phi4:14b` and `codestral-2508`.
- Effort is measured in edits. A timed review by an independent reviewer was not possible:
  the only reviewer wrote the gold.
