# Changelog

Repository-level changes to `secha-metadata`. Per-vendor mapping changes are logged in
`vendors/<vendor>/CHANGELOG.md`.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning: [SemVer](https://semver.org/).

## [Unreleased]
### Added (Phase 3, Step 1: platform binding + serving views)
- `targets/canonical.yaml` gained the facts the Phase-3 platform handshake verified:
  `table_properties` with `delta.feature.catalogManaged: supported` (this Unity Catalog
  rejects managed tables without it; the sink's generated DDL always includes it),
  a `staging` declaration (`SECHA_STAGING_ROOT`, the cluster-visible NFS hand-off), and
  `serving_schema: serving`.
- **Serving views as config**: new `serving/` folder; each `<name>.sql` holds one SELECT over
  the `{canonical}` placeholder and is wrapped by the sink as `CREATE OR REPLACE VIEW`.
  First view: `pq_minute_wide` (minute-level wide PQ overview per device, all vendors,
  `quality = 'ok'` only).
- Validator guards for serving views (empty body, hidden DDL/DML, hardcoded table paths,
  missing serving_schema, unknown serving_mode), each pinned by a unit test.
- `serving_mode: table` in the target binding (platform fact: this UC Spark connector has
  neither view ability nor RTAS; serving definitions are materialised as Delta snapshots,
  flip to `view` when the connector matures; the serving/*.sql bodies never change).
### Added (vendor #2: ProCem)
- **Second vendor onboarded as pure config**, `vendors/procem_kampusareena_pq/`: the Kampusareena
  EV-charging-station PQ meter (ProCem platform, long-format 1 Hz triples, catalog-keyed semantics).
  71 mapped variables incl. fundamental/Fryze variants, unbalance, voltage harmonics 3/5/7, and
  cumulative energy counters. **Zero vocabulary or unit-registry changes were needed.**
- **Long-shape mapping construct** (additive): `source_schema.shape: long` +
  `record.key_field/value_field`, and mapping `rows:` entries keyed by the record's key-field VALUE
  (the long counterpart of wide `columns:`), with per-row `harmonic_order` and `aggregation` overrides.
  Meta-schemas extended additively (`format.delimiter/header`, `datetime_format: epoch_ms` usage).
- Validator: rows entries get the full column checks + no-collapse (now including per-row
  aggregation); shape/record consistency (`rows` ⇔ `shape: long`, long requires
  key/value/timestamp fields); harmonic_order required-vs-meaningless checks. Unit tests pin each.
- `lineage.py` renders long-shape mappings (rtl key + catalog point name).
- Golden fixtures for the new vendor from **real 2026-06-15 data** (values verified on the S: drive),
  including the Helsinki-local-midnight timestamp case (`2026-06-14T21:00:00.246Z`).
- `docs/onboarding-diary-procem.md`: the live RQ3 evaluation log (hours, config-vs-code counts,
  engine changes required).
- Canonical enum: `source_vendor` += `procem_kampusareena_pq` (additive).
### Added
- Validator guards against silent misconfiguration: unknown transform args are rejected;
  `scale_by_factor.factor_field` must be declared in `source_schema.device_factors`; quantities
  requiring `harmonic_order` are forbidden in direct columns (generated rules only); the engine-facing
  `record`/`defaults` blocks are shape-checked (fields exist, template placeholders resolve, canonical
  aggregation, integer interval); duplicate field names are flagged. Unit tests pin each guard.
### Changed
- `measurement_id_from` now includes `aggregation` (the full identity tuple), so min/max/mean variants
  of the same quantity can never collide in the merge key (changed now, while no production data exists).
- Energy units corrected to **kWh / kvarh** (vocabulary `1.2.0`, units registry). Confirmed:
  MX Electrix energy values are cumulative kWh despite attribute names ending in `wh`/`varh`.

## [0.1.0] - 2026-06-18
### Added
- Canonical layer: `canonical_schema.yaml` (long fact + thin dims), `quantity_vocabulary.yaml`
  (standards-aware, with per-quantity descriptions), `units.yaml`.
- Typed transformation-rule registry (`transforms/library.yaml`) and shared sink binding
  (`targets/canonical.yaml`).
- Meta-schemas (`meta-schemas/*.schema.json`) + `validate.py` with three layers: JSON-Schema
  conformance, cross-file referential integrity, and the no-collapse identity-tuple check.
- MX Electrix vertical-slice config (`vendors/mx_electrix/`) with verbatim vendor field descriptions;
  split `voltage_unbalance` into negative- and zero-sequence quantities (mapping_version 1.1.0).
- `lineage.py` generator + `docs/lineage_mx_electrix.md` + lineage-drift guard test.
- Architecture diagrams (`docs/secha-metadata-rulebook-flow.svg`, `docs/mx-electrix-slice-mapping.svg`).
- Tooling: pytest, ruff, pre-commit, GitHub Actions CI.
