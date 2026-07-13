# Changelog: vendor config `procem_kampusareena_pq`

## [1.0.0] - 2026-07-06
### Added
- Initial mapping for the Kampusareena EV-charging-station PQ meter (`LV3_EVCharging_*`,
  Laatuvahti 3, rtl_ids 23501-23949, 1 Hz), curated from catalog `Procem_IDs_v1.2.csv`.
- 71 `rows:` entries (long-shape mapping keyed by rtl_id): F; U phase/line-line/fundamental;
  I phases/N/fundamental; P/Q/S 3-phase + per-phase with fundamental and Fryze variants;
  PF/DPF; THD U/I; U2U1/U0U1 unbalance; voltage harmonics 3/5/7 per phase; 6 cumulative
  energy counters (`aggregation: counter` per-row override).
- Out of slice (documented, additive later): harmonic orders 2,4,6,8-20, harmonic currents
  I2-I20, DC voltages `Udc*`.
- Validation rules: not_null key/timestamp (reject), value (drop, by construction), and the
  same physical-range flags as mx_electrix for comparable quality semantics.
- **Vocabulary/unit registry changes required: none.**
