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
- 2026-09-24: all 337 seals verify from a fresh clone (`verify_seals.py`); the 300 drafts and
  model replies, which the repository does not hold, are archived with the partner catalog.

### 2026-09-24, Step 4: the engine (≈0.4 h, 09:43 to 10:07 UTC, then a 2.3 h unattended run)
- **Five generic capabilities in `secha-transform`, zero vendor logic:** Parquet payloads read
  in streamed batches; access layouts with any placeholders (`export`/`part` as well as
  `date`/`meter`); row ids from a row's position in its immutable landed part; sessions
  (`session_id` and `ts_session_offset_s` on every row, one `charging_session` row per
  session, typed from the canonical schema); rows without a date, whose `event_date` is a
  real null. Plus per-column aggregation, and a generic `secha-transform run <vendor>`, so the
  third vendor needed no command of its own. No vendor name appears in the engine or IO code.
- **Counts:** +243 lines of code, all generic: engine and model 62, about what ProCem's engine
  change was (about 60); reader 59, writer 37, the generic command 84, config 1.
  Vendor-specific code: 0 lines.
  Metadata: the golden contract (6 synthetic records, 24 expected rows, 2 sessions).
- **Traps the new source exposed, all generic and all fixed:** the writer stored the string
  `"unknown"` as `event_date`, which the Delta table's DATE column would reject; files typed
  their columns per batch, so an all-null `ts_utc` clashed with other vendors' files (now one
  fixed schema); pyarrow cannot infer a partition type when every `event_date` is null (the
  writer now declares its partitioning for readers); a session spanning two batches was
  written twice (now once per landed part); and `dataclasses.asdict` took over half the run
  time (removed; output identical on 500,000 rows).
- **Full real run (10:07:36 to 12:24:44 UTC, 8,228 s, about 8,700 records a second):** 99
  parts, **71,793,566 records into 358,967,830 canonical rows** and 396,848 sessions; 709
  suspect, 0 dropped, 0 rejected, 0 unmapped; 14 GB of canonical Parquet.
- **Reconciled against the raw parts, independently of the engine:** rows equal the raw
  non-empty cells, per quantity; the value sums match for all five quantities; aggregation and
  phase are as the rulebook says; the 709 suspect readings are exactly the 709 negative
  voltages found when the export was first profiled; distinct sessions equal the raw distinct
  `transactionId`s. The session dataset holds 96 extra rows, precisely the 96 sessions that
  straddle two parts, merged on `session_id` at load. `measurement_id` is unique in every part.
- **Gates:** 81 transform tests (1 skipped that needs the platform), mypy strict, ruff.

### 2026-09-24, Step 5: into Unity Catalog (≈1 h, 12:56 to 13:58 UTC, 17 min of it waiting)
- **One generic sink change:** the Delta sink loads any entity the target declares under
  `dimensions:`, with the same DDL, dedupe and MERGE builders as the fact table
  (`delta-load --entity charging_session`, merged on `session_id`). +120 / -33 lines in the
  sink and CLI (docstrings included; the final count, after the pre-commit review of
  2026-09-25 added fail-fast checks and a deterministic dedupe for keys without
  `ingested_at`), no vendor name in either; the fact table's SQL is byte-identical to
  before. The one Kempower-specific file is the operational load script outside the package.
  Rulebook changes: 0. `charging_session` and its merge key have been declared in
  `targets/canonical.yaml` since the first scaffold (2026-06-24), three months before this
  vendor arrived.
- **Pilot, part 0:** 3,680,010 rows and 3,593 sessions, verified in Unity Catalog. Spark
  reads the null `event_date` as a real NULL. A second run changed nothing.
- **A platform limit, found the hard way:** a 10-part MERGE filled a worker's scratch space
  (a 32 GB swap-backed `/tmp`), and its re-run, made only to read the error, left an 8 GB copy
  that blocked every job on that worker for 28 minutes, until Spark's periodic cleanup. Nothing
  in the table changed. Recorded in `secha-transform/docs/phase3-log.md` with the lessons.
- **Loaded: every tenth part** (0, 10, ..., 90), one per MERGE: **36,348,545 Kempower rows**
  (10.1% of 358,967,830), 41,884,113 in the table, and **40,175 sessions**. Each MERGE grew the
  table by exactly its part's local row count. The full 359M rows stay in local canonical
  Parquet until the platform's scratch space moves to disk.
- **Verified in Unity Catalog against the local files:** 7,269,709 rows per quantity with the
  declared phase and aggregation; 55 suspect, all voltage; no clock time and a session on every
  row; every session present in `charging_session`; the other two vendors unchanged.
- **Three vendors, one catalog:** after `delta-views`, the quantity dimension covers
  Kempower's `state_of_charge` and `temperature`, so every fact row of all three vendors joins
  it (14,539,418 rows did not before). `pq_minute_wide` is unchanged, as it must be: a minute
  view needs clock time, which Kempower does not have.
- **Gates:** 90 transform tests (1 skipped that needs the platform), mypy strict, ruff; the
  rulebook validator and 64 metadata tests.

### Next
1. Questions for the provider, now sharper: what `tempC` measures, whether the electrical
   columns are the DC output, and whether `soc` and `tempC` are samples or averages. An
   absolute session start time would also give the rows clock time.
2. The full Kempower load, once the platform's Spark scratch space moves from `/tmp` to disk.
