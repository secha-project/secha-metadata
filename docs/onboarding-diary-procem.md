# Onboarding diary: vendor #2, `procem_kampusareena_pq`

**Purpose.** This diary is the RQ3 evaluation instrument: it records, live, what onboarding a
second heterogeneous vendor into the SECHA framework actually costs. The claim under test is
"new vendor = configuration, not code". Every entry logs hours, files touched, config-vs-code
line counts, and (most importantly) **engine changes required**: the target is near zero, and
only generic capabilities, never vendor logic.

**Baseline for comparison.** The legacy `spark-data-transformer` onboards a ProCem source as a
dedicated Scala transformer class (`PowerQualityTransformer.scala` + `GeneralUtils` + `Schemas`
+ factory registration): compiled vendor code, hard-coded catalog interpretation, redeploy to
change a mapping. This framework's target: the same onboarding as YAML in `secha-metadata`,
with the engine untouched except for generic, vendor-blind capabilities.

**What is counted.**
- *Config LOC*: YAML/JSON added under `vendors/`, `tests/fixtures/`, meta-schemas.
- *Code LOC*: Python changes in `validate.py`/`lineage.py` (metadata tooling), the ingestion
  connector, and the transform engine, split into **generic capability** (usable by any future
  vendor) vs **vendor-specific** (should be zero).
- *Hours*: wall-clock working time per step.

---

## The source (verified facts, not assumptions)

ProCem platform, Kampusareena, Hervanta. Raw = daily 7-Zip on the TUNI group drive
(`S:\81404_ProCem\kampusareena\data\YYYY-MM-DD_procem.7z`, 2,944 archives, 2018-05-03 → today,
feed live). One archive = **one whole-day CSV** (2026-06-15: 3.78 GB, 131.7M rows). Row format:
`rtl_id<TAB>value<TAB>epoch_ms`, no header, decimal-string values. Semantics come only from the
catalog `Procem_IDs_v1.2.csv` (4,878 variables; `rtl_id;name;path;unit;datatype;…;source`).

Scope: the **EV charging station** meter `LV3_EVCharging_*` (a Laatuvahti 3, the same instrument
family as the MX Electrix Viinikka meters, delivered through a completely different pipeline):
rtl_ids **23501-23949, 179 variables, 1 Hz** (~15.4M rows/day). Logged 2019 → **2026-06-28**,
then stopped (field-hardware churn; treated as normal). Onboarding day: **2026-06-15**.

Heterogeneity vs MX Electrix (the axes the framework must absorb):

| Axis | MX Electrix | ProCem |
|---|---|---|
| Delivery | HTTPS API + Api-Key | file archives on group drive / SSH |
| Packaging | JSON | 7z → tab-separated CSV |
| Shape | wide (~240 columns/record) | **long** (one triple per row) |
| Semantics | in column names | in an external **catalog** keyed by integer id |
| Timestamp | naive ISO string (UTC) | **epoch milliseconds** |
| Day boundary | UTC midnight | **Helsinki-local midnight** (verified: first rows of the 2026-06-15 file are stamped 2026-06-14T20:59:59Z) |
| Scaling | raw × per-device uk/ik | engineering units as stored |

## Design decisions (made before code; rationale recorded once, here)

1. **Explicit `rows:` mapping, not regex classification.** Mapping entries are keyed by the
   *value* of the record's key field (`rows: [{key: "23501", quantity: frequency, …}]`), the
   long-shape counterpart of wide `columns:`. Rejected alternative: deriving quantity/phase
   from point-name regexes (clever, unauditable, validator-hostile). The explicit table gets
   the full three-layer validation, including no-collapse over rtl_ids.
2. **Zero new engine concepts for device identity.** `record.device_id_template` with zero
   placeholders (`procem:kampusareena:evcharging`) reuses the existing mechanism; one mapping
   file per device family.
3. **`shape: long` + `key_field`/`value_field`/`timestamp_format: epoch_ms`** declared in
   `source_schema.yaml`; the engine grows three generic capabilities (long-record lookup,
   epoch-ms timestamps, DSV parsing per the `format:` block), all vendor-blind.
4. **Ingestion lands a declared rtl_id subset** (line *selection*, never value modification;
   the file-source equivalent of Electrix's per-meter API narrowing); the envelope records the
   id filter + source-archive provenance. Landing 3.8 GB/day of building automation we do not
   use would be waste, and the subset is declared in config, not hard-coded.
5. **Landing date partition = ProCem's local day** (provenance-faithful); canonical
   `event_date` derives from `ts_utc` (truth). The mismatch is documented, not "fixed".
6. **`aggregation: counter` per-row override** for the cumulative energy counters: the
   "per-column aggregation" discriminator that was documented as the additive next step.
7. **Slice scope: 71 of 179 variables**, mirroring + extending the MX Electrix slice: F, U
   (phase + line-line + fundamental), I (phases, N, fundamental), P/Q/S (3-phase + per-phase,
   fundamental + Fryze variants), PF/DPF, THD U/I, U2U1/U0U1 unbalance, voltage harmonics
   3/5/7 per phase, and 6 energy counters. Out of slice (documented): harmonic orders
   2,4,6,8-20, harmonic currents, DC voltages `Udc*`.

## Entries

### 2026-07-06, Step 0: source verification + sample (≈1.5 h)
- Verified S:-drive access first-hand; inventoried 2,944 archives + `counters/` sidecar files.
- Extracted + inspected a real archive: confirmed triple format, single whole-day CSV (not
  part files; the `_part_*` split is post-processing), Helsinki-local day boundary, 1 Hz rate.
- Carved the working sample: `RP and Data/secha-data-procem/2026-06-15_evcharging_rows.csv`
  (14.48M rows, 410 MB) + `catalog_evcharging.csv` (179 entries).
- **Finding:** EVCharging stopped logging 2026-06-28 (like Marjamäki earlier). Sources come
  and go; the framework treats that as normal, not exceptional.

### 2026-07-06, Step 1: `secha-metadata` vendor config (≈2.5 h)
- Added `vendors/procem_kampusareena_pq/` (source_schema, mapping with 71 `rows:` entries,
  validation, per-vendor CHANGELOG) + golden fixtures from **real** 2026-06-15 values.
- Extended meta-schemas additively: `shape`, `format.delimiter/header`, `record.key_field/
  value_field`, mapping `rows:` (with per-row `harmonic_order`/`aggregation`).
- Extended `validate.py` (rows checks, shape-consistency, harmonic_order rules, aggregation
  override) and `lineage.py` (rows lineage): **generic tooling, no vendor logic**.
- **Vocabulary/units additions needed: ZERO.** All 71 variables, including Fryze/fundamental
  variants, unbalance, harmonics, and energy counters, mapped onto the existing canonical
  vocabulary unchanged. The canonical layer absorbed a second vendor without growing.
- Canonical enum: `source_vendor` += `procem_kampusareena_pq` (additive).
- **Measured counts (all gates green):**
  - Vendor config: **176 YAML lines** (mapping 110, source_schema 52, validation 14)
    + 56 fixture lines. Pure declaration, no code.
  - Generic tooling (usable by any future long-shape vendor, zero vendor logic):
    `validate.py` +50 net, `lineage.py` +17, meta-schemas +28 JSON lines.
  - Vocabulary/units/transform-library changes: **0 lines**.
  - Engine (`secha-transform`) changes so far: **0 lines**.
  - Gates: `validate.py` OK (3 layers incl. no-collapse over 71 rtl_ids), lineage generated
    + drift-check clean, ruff clean, **14 tests pass** (4 new guards pinned).

### 2026-07-06, Step 2: `secha-ingestion` ProCem connector (≈1.5 h)
- New `connectors/procem.py` (~150 LOC incl. docstrings): fsspec source URL (local dir / S:
  drive / sftp later, same code), day-file glob (`.7z` or pre-extracted `.csv`), 7z extraction
  to a temp dir, **stream** line-selection by declared rtl_id subset (whole day never held in
  RAM when filtering; malformed lines counted, never invisible), envelope records id_filter +
  selection counts + source-file provenance. CLI `secha-ingest procem`, two settings, `py7zr` dep.
- **`core/` changes required: ZERO lines.** The `SourceConnector` protocol, sink, runner, and
  envelope absorbed a file-based vendor unchanged; even the `.csv` extension mapping already
  existed. The deferred-abstraction bet (refactor on the second/third connector only if it
  pinches) paid off: nothing pinched.
- 8 new offline tests (real tiny 7z built per test): verbatim line selection, envelope counts,
  idempotent re-run, plain-csv support, unfiltered whole-file mode, clear missing-day error,
  filter-syntax guards. Gates: ruff + mypy(strict) clean, **20 tests pass**.
- **Live run against the real S: drive (2026-06-15):** 548,624,636-byte archive → 131,712,383
  lines scanned → **14,476,804 EVCharging lines landed verbatim** (409,697,690 bytes, sha16
  `b5466add85c58527`), 0 malformed; line count exactly matches an independent manual
  extraction (determinism across implementations). Envelope records filter, counts, source
  file + size, `sensitivity: project-internal`, `fetched_at`. **Second run: 0 new, 1 skipped**
  (idempotent), partition still holds exactly one payload + envelope. End-to-end ≈4 min/run
  (network copy + extract + stream-filter dominate).

### 2026-07-07, Step 3: `secha-transform` engine capabilities (≈2 h)
- Three **generic** capabilities, no vendor logic (`grep -ril procem src/` matches only the
  CLI command wiring):
  1. long-shape branch in the engine (`rows:` keyed lookup, per-row aggregation override,
     optional `meter_field`, `records_unmapped` counted): **~60 changed lines** in
     `engine/transform.py` + `models.py` (vs the <~40 estimate: close, honest miss);
  2. `epoch_ms`/`epoch_s` timestamps with integer math (a millisecond can never float-round);
  3. descriptor-driven reader: partitions from `access.layout`, parsing from `format:`
     (JSON + header-less DSV, values kept as strings), lazy/streaming records; CLI batches
     multi-million-row days (500k/batch) with idempotent run-scoped writes.
- Golden test green against the Step-1 metadata contract (real values, Helsinki-midnight
  timestamp, fryze/fundamental variants, harmonic order, counter aggregation).
- Gates: ruff + mypy(strict) clean, **36 tests pass**. MX Electrix re-verified live through
  the refactored reader: identical 36,000 rows.
- **Live, full real day (2026-06-15): 14,476,804 records → 5,499,568 canonical rows**
  (0 suspect / dropped / rejected; 8,977,236 unmapped-id records **counted**;
  mapped + unmapped = records-in, exactly). ≈6 min pure-Python, streaming.

### 2026-07-07, Step 4: the convergence proof (done at the same sitting)
One query over one canonical dataset (5,535,568 rows, both vendors):
`quantity=voltage AND phase=L1` returns
`mx_electrix:meter:21 → 237.20 V (average, ok)` and
`procem:kampusareena:evcharging → 234.57 V (average, ok)`: identical columns, identical
semantics, from a wide 1-min JSON API and a long 1 Hz tab-separated file dump. **That result
is RQ1, live.**

## Final tally (the RQ3 evidence)
| Repo | Vendor-specific | Generic (any future vendor) |
|---|---|---|
| secha-metadata | 176 YAML + 56 fixture lines | validator/lineage/meta-schemas ~95 lines |
| secha-ingestion | connector ~150 LOC + CLI wiring | **core/: 0 lines** |
| secha-transform | CLI command wiring only | engine ~60 lines + reader/CLI (all descriptor-driven) |
| canonical vocabulary/units | **0 lines** | (unchanged) |

Baseline contrast: the legacy Scala route = a compiled per-vendor transformer class +
schema + factory registration + redeploy. Here: the vendor is YAML; every code change was a
reusable capability.

### Remaining
- Open: are 1 Hz values instantaneous samples or 1-s aggregates? (default recorded
  as `average` @ `interval_s: 1`, matching Laatuvahti reporting-interval behaviour); confirm
  values are final engineering units; heads-up that EVCharging stopped 2026-06-28.
- Later (config-only): map the remaining 108 EVCharging variables; more days (backfill loop);
  Phase 3 Delta/UC MERGE.
