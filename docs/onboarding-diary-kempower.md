# Onboarding diary: vendor #3, `kempower` (the held-out vendor)

**Purpose.** The same instrument as the [ProCem diary](onboarding-diary-procem.md), for the
vendor nothing was tuned on. For RQ3 it records what onboarding costs: hours, files,
configuration against code, and every engine change, split into generic capability and
vendor-specific logic (the target for the second is zero). For RQ4 it records the effort
measures fixed in [the held-out protocol](../experiments/kempower_heldout/PROTOCOL.md):
time to author the rulebook by hand, and edits needed to correct each machine draft.

**Baseline.** ProCem cost 176 lines of vendor YAML, about 95 lines of generic metadata
tooling, about 60 lines of generic engine code, and no vocabulary change at all. Hours in
both diaries are wall-clock working time of the same researcher with the same tooling.

---

## The source (verified facts, not assumptions)

Kempower shares a passenger charging dataset over Delta Sharing. TAU fetched it once and
wrote it with Spark 4.0.1 as 100 snappy Parquet parts (write job `95d29330`). 99 parts are
landed and verified byte for byte against Spark's checksums; `part-00099` is truncated in
every copy we hold (752,718 rows, United Kingdom, June 2025) and is awaited from the data
provider. Details and open questions: `secha-ingestion/docs/open-questions.md`.

One row is one 10-second step of one charging session. Thirteen columns, and the schema
declares no units and no descriptions: `transactionId`, `country`, `EVModel`, `year`,
`month`, `quarter`, `weekday`, `sampleTime10sIncrement`, `soc`, `tempC`, `avgPowerW`,
`avgCurrentA`, `avgVoltageV`.

| Axis | MX Electrix | ProCem | Kempower |
|---|---|---|---|
| Delivery | HTTPS API | file archives | one-off Spark export of a Delta Sharing table |
| Packaging | JSON | 7z, tab-separated | snappy Parquet parts |
| Shape | wide | long | wide |
| Semantics | column names | external catalog | column names only: no catalog, no units |
| Time | ISO instant, UTC | epoch milliseconds | no clock time: year, month, weekday, and seconds since the session started |
| Identity | meter | platform point | charging session; no charger or site id |
| Electrical system | AC three-phase | AC three-phase | DC charger output (likely; unconfirmed) |

## What the canonical layer already anticipated (checked 2026-09-23, before authoring)

- **Anticipated:** `kempower` is already a `source_vendor` value; a `charging_session`
  entity exists (`session_id`, `ev_model`, `ev_brand`, `country`, `cal_year`, `cal_month`,
  `weekday`); a measurement carries `session_id` and `ts_session_offset_s`, and `ts_utc`
  is nullable; the unit registry has `degC`.
- **Not anticipated**, each a decision for the rulebook:
  1. No quantity for state of charge or for temperature (vocabulary 1.2.0).
  2. The phase enum and the voltage and current descriptions assume AC. A DC output has
     no phase, and ProCem's DC-link voltages (`_Udc`) are unmapped for the same reason.
  3. `record:` cannot declare a session id or a session-relative time field.
  4. **The merge identity cannot tell Kempower readings apart.** `measurement_id` hashes
     `[source_vendor, device_id, ts_utc, quantity, phase, variant, harmonic_order,
     aggregation, source_row_id]`. With `ts_utc` null and no session in the tuple, every
     reading of a quantity on one device gets the same id, and an idempotent MERGE would
     keep one row. The identity must include `session_id` and `ts_session_offset_s`, and
     even then 17.8% of rows share a session and offset with another row, so a source row
     id is needed as well.
  5. The fact table is partitioned by `event_date`, derived from `ts_utc`, which Kempower
     does not have.
  6. The transform reader parses JSON and delimited text, one date at a time; Kempower is
     Parquet, partitioned by export and part.

## Entries

### 2026-09-22, Step 0: ingestion (≈0.7 h, 10:08 to 10:50 UTC, plus ≈0.45 h review)
- Studied both delivered folders, found them byte-identical, profiled the 99 good parts
  (71,793,566 rows, 9 countries, January 2024 to June 2025), and wrote the facts above.
- `secha-ingestion` connector `connectors/kempower.py` (195 lines with docstrings): lands
  each Spark part verbatim after checking every 512-byte chunk against Spark's CRC32; a
  damaged part is refused and named, the rest land. CLI command, one setting, 18 offline
  connector tests (every line of the connector runs under test).
- **`core/` changes: one line**, the Parquet media type in the sink's extension table. A
  format, not vendor logic; the connector protocol, runner and landing logic took a third,
  very different source unchanged.
- Live run: 99 of 100 parts, 606,521,747 bytes, in 12 seconds; a second run lands nothing
  new. Committed as `secha-ingestion@eb7ace7`.

### 2026-09-23, Step 1: the held-out draft, pre-registered and sealed (09:39 to 10:00 UTC)
- Wrote the protocol, both specs, the seal tool and the scorer before any model saw the
  catalog. The scorer was checked on synthetic inputs with hand-computed answers; that
  check caught one flaw (a provider failure counted as a missing entry), fixed before
  sealing. Sealed at 09:54:11 UTC together with the catalog, `propose.py`, the vocabulary
  and the example sources, all unchanged since `cd564b9`.
- Ran `phi4-14b` (Aviary) and `codestral-2508` (Mistral) under C0 and C1. Every point was
  answered; each draft mapped all 5 columns, and the validator rejected all four drafts
  (9 and 5 problems for `phi4-14b`, 5 and 5 for `codestral-2508`). Outputs and the 20 raw
  replies were sealed at 09:58:55 UTC. **No entry has been opened.**
- Already visible without opening anything: no model left a column unmapped, in any run.
  The prompt offers no way to decline, so the question P1 asks is only which way each
  column fails, and that is sealed.
- `mistral-medium-2604` still answers HTTP 429 (zero request limit), so the commercial arm
  is `codestral-2508`. `kimi-k3` (NIM) is running as the optional arm.
- **Limitation noted:** `propose.py` caches the reply text but not the model name the
  service reports. The reachability probe the same morning recorded `ollama/phi4:14b` and
  `codestral-2508` as served.

### 2026-09-23, Step 2: the rulebook by hand, blind (10:42:57 to 10:51:29 UTC)
- **Decisions.** Eight, prepared from the analysis in Step 1 and accepted as recommended at
  10:42 UTC: new quantities `state_of_charge` and `temperature` (ask the provider what
  `tempC` measures); phase `dc` for the charger output; a row identity that keeps every
  reading; `event_date` left null; one dataset-level device; vehicle model verbatim, no
  brand, no quarter; bounds 0 to 100 % for state of charge and 0 to 1000 V for voltage.
- **One decision refined while authoring.** Adding `session_id` and `ts_session_offset_s`
  to the merge key would change the id of every existing MX Electrix and ProCem row, since
  the engine hashes the declared field list, and a reload would duplicate 5.5 million rows.
  The key already holds `source_row_id`. Giving each Kempower row its position in its
  immutable landed part as that id keeps every reading, both rows of a repeated session
  and offset included, and leaves every existing id unchanged. The merge key did not change.
- **Two things found while authoring.** `soc` and `tempC` have no `avg` prefix, so they
  are samples while the other three columns are averages, and a wide mapping could not
  say so: only long `rows:` could carry an aggregation. Wide `columns:` now can, and the
  no-collapse check counts it. And `pq_minute_wide` would have grouped Kempower rows, which
  have no clock time, into one NULL-minute row per device; it now requires `ts_utc`.
- **Checked in the data:** the five session attributes are constant within every session
  across all 99 parts. 96 sessions straddle two parts, which is harmless because
  `charging_session` merges on `session_id`.
- **Counts.** Vendor YAML: 103 non-blank lines (source schema 73, mapping 18, validation
  12), against ProCem's 176. Canonical: two quantities, `dc` in the phase enum, and DC
  wording for voltage, current and active power (vocabulary 1.3.0, canonical schema 1.1.0);
  ProCem needed none. Generic tooling: meta-schemas +23 lines (a `session` block,
  `record.row_id_from`, per-column `aggregation`), `validate.py` +39, six new validator
  tests, one serving guard line, comments in the target binding. Engine: 0 lines so far.
- **Gates:** `validate.py` clean for three vendors, lineage generated, 63 metadata tests
  pass, and the `secha-transform` suite passes against this metadata (53 passed, 1 skipped
  that needs the platform).
- **Sealed** at 10:51:29 UTC, before any proposal was opened.
- **`kimi-k3`** answered all ten points and is included. Its C1 gate ran against the
  extended rulebook (protocol deviation D1); recomputed against the frozen rulebook, it has
  5 problems, not 0.
- **Effort caveat.** Writing took 8.5 minutes once the decisions were made; the analysis
  behind them is part of Step 1. "By hand" means the researcher's decisions written with
  the same assistant-supported workflow as the ProCem diary, and the correction effort will
  be measured in that same workflow, so the comparison is like for like.

### 2026-09-23, Step 3: unsealed and scored (from 10:59 UTC)
- **Order of events, all on record:** pre-registration committed `2c98448` at 10:41:45;
  gold sealed at 10:51:29 and committed `569dc78` at 10:58:42, byte-identical to its seal;
  unsealed at 10:59:25 by `score.py`, which checked every draft against its seal first.
- **Headline** (details in `experiments/kempower_heldout/FINDINGS.md`):
  1. With the vocabulary as it stood, none of the five columns could be answered: the
     rulebook needed two new quantities and a new phase value.
  2. Missing quantities were invented, 12 of 12, and the validator caught every one; 8 of
     the invented names are the ones the rulebook adopted.
  3. The missing phase value was force-fitted, 18 of 18, and nothing caught it: 7 of those
     entries claim an AC phase for a DC output. The validator guards nouns, not qualifiers.
  4. With the vocabulary extended (C2, run 11:01 to 12:06), every quantity and unit was
     right in all three arms, and the convention's one sentence about DC decided the
     phase: `dc` in 8 of 9 entries with it, 0 of 9 without.
- **Correction effort:** 2 field edits (`codestral-2508`, `kimi-k3`) and 3 (`phi4-14b`)
  with the vocabulary and the documentation in place, out of 30 fields; 5 to 8 without,
  plus the vocabulary work itself. The remaining edits come mostly from one gold judgment the
  provider has not confirmed (`soc` and `tempC` as instantaneous).
- **Review time** was not measured by an independent reviewer: the only people who could
  review knew the gold. Edits are the effort measure, as pre-registered.
- Protocol deviations D3 (gate-problem split) and D4 (C2 after unsealing) appended.

### Next
1. Engine capabilities for the transform step: a Parquet reader, the export and part
   layout, session fields, the positional row id, and a null `event_date`.
2. Questions for the provider, now sharper: what `tempC` measures, whether the electrical
   columns are the DC output, and whether `soc` and `tempC` are samples or averages.
