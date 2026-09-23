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

### Next: Step 2, the rulebook by hand, blind
The rulebook is authored without opening `proposals/kempower/`, timed from the first
decision to the commit, and committed before `score.py` is run. The decisions listed
above under "Not anticipated" are its agenda.
