# Changelog

Repository-level changes to `secha-metadata`. Per-vendor mapping changes are logged in
`vendors/<vendor>/CHANGELOG.md`.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning: [SemVer](https://semver.org/).

## [Unreleased]
### Added
- Validator guards against silent misconfiguration: unknown transform args are rejected;
  `scale_by_factor.factor_field` must be declared in `source_schema.device_factors`; quantities
  requiring `harmonic_order` are forbidden in direct columns (generated rules only); the engine-facing
  `record`/`defaults` blocks are shape-checked (fields exist, template placeholders resolve, canonical
  aggregation, integer interval); duplicate field names are flagged. Unit tests pin each guard.
### Changed
- `measurement_id_from` now includes `aggregation` — the full identity tuple — so min/max/mean variants
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
