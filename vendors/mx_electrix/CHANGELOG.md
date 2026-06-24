# Changelog - mx_electrix mapping

Records every schema/mapping change for this vendor.
Additive = safe; rename = column-mapping + new version; removal = flag; type change = forbidden.

## 1.1.0 - 2026-06-18
- Split the ambiguous `voltage_unbalance` quantity into `voltage_unbalance_negative_seq` (U2/U1) and
  `voltage_unbalance_zero_seq` (U0/U1) so the two source columns are distinguishable in canonical.
- Carried the vendor field explanations VERBATIM from `secha_electrix_measurements_v1.1.xlsx` into
  `source_schema.yaml` `desc` fields (full data-dictionary text, not abbreviations).
- Added `description` to every canonical quantity in `quantity_vocabulary.yaml`.
- Added the generated lineage report (`docs/lineage_mx_electrix.md`, produced by `lineage.py`).
- Updated the golden fixture to cover both unbalance components.

## 1.0.0 - 2026-06-18
- Initial vertical-slice mapping for `/measurements/`.
- Direct columns: frequency, voltage THD (L1-L3), power factor (L1-L3), voltage unbalance (U2/U1, U0/U1).
- Scaled columns: phase/neutral voltages and currents (scale_by_factor uk/ik).
- Generated: odd voltage harmonics (orders 3,5,7).
- Open items: confirm energy-counter units (Wh vs kWh) and device-factor direction.
