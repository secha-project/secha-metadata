# Kempower held-out test: protocol

Written on 2026-09-23, before any model saw the Kempower catalog and before a Kempower
rulebook existed. This file is sealed in [SEALS.md](SEALS.md) together with every input
it names. It is not edited after sealing; changes are appended under Deviations.

## Question

RQ4a asks how accurately a language model can draft mapping metadata from a partner
schema, and what determines that accuracy. Every number so far comes from ProCem, the
vendor the benchmark, the prompt, the worked examples and the naming convention were all
developed on. Kempower is the first vendor none of them was tuned for. This test asks
what `propose.py` drafts for it, how that draft fails, and how much correction it needs.
It also produces the effort measure RQ4 lacks: time and edits to correct a draft,
against time to author the same rulebook by hand.

## Why Kempower is a fair held-out test

- It was not used to build the benchmark, the prompt, the worked examples or any
  naming convention. `propose.py`, the canonical vocabulary and the examples are frozen
  at commit `cd564b9` and were not changed for this test.
- It differs from both mapped vendors in ways the framework has not met: charging
  sessions instead of meters, time counted from the start of a session instead of a
  clock, a DC charger instead of an AC grid connection, and a Parquet export.
- Its catalog is the barest yet: 13 column names and types, no units, no descriptions.

## What is frozen

| Item | Value |
|---|---|
| Instrument | `propose.py` at `cd564b9`, unchanged: temperature 0, 16 worked examples from the two mapped vendors, `max_tokens` 300, reply cache on |
| Vocabulary | `canonical/` at `cd564b9`: quantity vocabulary 1.2.0, units 1.0.0, canonical schema 1.0.0 |
| Catalog | `secha-data-kempower/catalog_public_passenger_dataset.csv`, the Parquet schema of the export (outside the repository, sealed by digest) |
| Condition C1 | `specs/kempower.spec.yaml`, with a naming convention |
| Condition C0 | `kempower.no-convention.spec.yaml`, identical except that the convention is removed |
| Analysis | `score.py`, verified on synthetic inputs with hand-computed answers before sealing |

## Scope of the draft

`propose.py` drafts semantics only; record structure is human-authored by design, as for
ProCem. So the five measurement columns are proposed (`soc`, `tempC`, `avgPowerW`,
`avgCurrentA`, `avgVoltageV`) and the eight structural ones are excluded by the spec
(`transactionId`, `country`, `EVModel`, `year`, `month`, `quarter`, `weekday`,
`sampleTime10sIncrement`). With five points per run, results are reported as counts and
per-column outcomes, never as percentages.

## Conditions and arms

- **C0**: no naming convention. **C1**: the convention in `specs/kempower.spec.yaml`,
  written before any output existed. On ProCem the convention was written after seeing
  failures, so its effect was an upper estimate; here it is measured blind.
- **Arms.** `phi4-14b` on TUNI Aviary is primary: it is the model of the ProCem
  `propose.py` run and the best model on an undocumented source in the benchmark.
  `codestral-2508` on Mistral is the commercial arm, because `mistral-medium-2604`
  still returned HTTP 429 (a zero request limit) when probed on 2026-09-23. `kimi-k3` on
  NVIDIA NIM is optional: `propose.py` does not stream, and NIM's queue can outlast its
  gateway, so this arm is reported only if every point is answered.
- **C2, later.** The same arms and conditions, run against the vocabulary as extended by
  the committed rulebook, sealed before scoring. It separates "the model could not know"
  from "the model got it wrong" for every column that needed new vocabulary.

## Blinding

- Each run writes to `proposals/kempower/<condition>/<arm>/` (not committed), with its
  console output redirected to a log in the same folder.
- Only aggregate counts are read (points mapped, validator problem count, exit status),
  to detect failed runs. No entry is opened.
- Every output file and every newly cached model reply is sealed by SHA-256 as soon as
  the run ends.
- The Kempower rulebook (`vendors/kempower/`) is authored without access to the
  proposals and committed before they are opened. `score.py` refuses to run against an
  uncommitted rulebook or a proposal that differs from its seal.

## Predictions

Written before the run, and reported whether or not they hold.

- **P1.** The vocabulary has no quantity for state of charge or temperature, and the
  prompt offers no way to decline. So in every arm, `soc` and `tempC` will be mapped to
  an existing quantity (valid and silently wrong) or to an invented one (caught by the
  validator). Neither will be left unmapped.
- **P2.** Every arm will map the three electrical columns to `active_power`, `current`
  and `voltage`. Without the convention, the phase will follow the AC examples
  (`three_phase` or `L1`); with it, the arms will converge on `none`.
- **P3.** The convention will matter less than on ProCem, because these names are
  nearly self-describing; any difference will sit in phase and aggregation.

## Scoring

Fixed in `score.py`. The gold is `vendors/kempower/mapping.yaml` as committed. Each
proposed column falls into one class by what the gold does with it:

- **A**: the gold uses only vocabulary the draft was offered, so the draft could have
  been right. Scored as the benchmark scores: six fields (quantity, phase, variant,
  harmonic order, aggregation, unit) after the engine's defaults. *Strict* is the
  benchmark's definition; *effective* compares aggregation after inheriting the source
  default, which is what the engine writes. Both are reported.
- **B**: the gold needs vocabulary added for Kempower. The draft cannot be right; the
  outcome is how it fails: not mapped, invented (a value outside the vocabulary it was
  given), or force-fit (valid against that vocabulary, and wrong).
- **C**: the gold leaves the column unmapped. A draft entry is a false mapping.

Validity of each entry uses the rulebook's own column check (`validate._check_column`)
against the vocabulary the draft was offered, as in the benchmark. The whole-draft gate
result is reported with its problems, and those that name a proposed column are counted
separately from operational ones. Points the service never answered are provider
failures and are excluded, as in the benchmark.

## Effort

- **Authoring.** Wall-clock time to write `vendors/kempower/` by hand, logged in
  `docs/onboarding-diary-kempower.md` with start and end times per decision.
- **Correction.** The number of edits that turn each draft into the gold: fields changed
  on entries both map, entries added, entries removed. Computed by `score.py`. It is
  objective, and it is the primary effort measure.
- **Review time.** A timed review of each draft after unsealing. The reviewer then
  knows the answers, so this is a lower bound and is reported only as one.

## Deviations

None yet. Any change after sealing is appended here with its date and reason.
