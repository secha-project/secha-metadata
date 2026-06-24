# Lineage — mx_electrix

Source `measurements` · mapping_version `1.1.0`.
Generated from `secha-metadata` configs by `lineage.py` — **do not edit by hand**.

| Source field | Meaning (vendor) | Canonical quantity | Phase | Unit | Transform | Standard |
|---|---|---|---|---|---|---|
| `fhz` | fundamental power line frequency | `frequency` | none | Hz | none | IEC 61000-4-30:2025 (power frequency) |
| `dl1` | voltage distortion relative to fundamental phase L1 | `thd_voltage` | L1 | percent | none | IEC 61000-4-7 |
| `dl2` | voltage distortion relative to fundamental phase L2 | `thd_voltage` | L2 | percent | none | IEC 61000-4-7 |
| `dl3` | voltage distortion relative to fundamental phase L3 | `thd_voltage` | L3 | percent | none | IEC 61000-4-7 |
| `pfl1` | Power factor phase L1 | `power_factor` | L1 | ratio | none | IEEE 1459-2010 |
| `pfl2` | Power factor phase L2 | `power_factor` | L2 | ratio | none | IEEE 1459-2010 |
| `pfl3` | Power factor phase L3 | `power_factor` | L3 | ratio | none | IEEE 1459-2010 |
| `u2u1` | Voltage unbalance U2/U1, negative phase sequence component percentage of the positive phase sequence component | `voltage_unbalance_negative_seq` | none | percent | none | IEC 61000-4-30:2025 (U2/U1) |
| `u0u1` | Voltage unbalance U0/U1, zero component percentage of the positive phase sequence component | `voltage_unbalance_zero_seq` | none | percent | none | IEC 61000-4-30:2025 (U0/U1) |
| `ul1v` | voltage for phase L1 | `voltage` | L1 | V | scale_by_factor(uk) | IEC 61000-4-30:2025 (voltage magnitude); EN 50160 limits |
| `ul2v` | voltage for phase L2 | `voltage` | L2 | V | scale_by_factor(uk) | IEC 61000-4-30:2025 (voltage magnitude); EN 50160 limits |
| `ul3v` | voltage for phase L3 | `voltage` | L3 | V | scale_by_factor(uk) | IEC 61000-4-30:2025 (voltage magnitude); EN 50160 limits |
| `il1a` | current for phase L1 | `current` | L1 | A | scale_by_factor(ik) | IEC 61000-4-30:2025 |
| `il2a` | current for phase L2 | `current` | L2 | A | scale_by_factor(ik) | IEC 61000-4-30:2025 |
| `il3a` | current for phase L3 | `current` | L3 | A | scale_by_factor(ik) | IEC 61000-4-30:2025 |
| `i_n` | current for neutral line | `current` | N | A | scale_by_factor(ik) | IEC 61000-4-30:2025 |
| `u3l1` | 3rd harmonic voltage component relative to fundamental phase L1 | `harmonic_voltage (order 3)` | L1 | percent | none | IEC 61000-4-7 |
| `u3l2` | 3rd harmonic voltage component relative to fundamental phase L2 | `harmonic_voltage (order 3)` | L2 | percent | none | IEC 61000-4-7 |
| `u3l3` | 3rd harmonic voltage component relative to fundamental phase L3 | `harmonic_voltage (order 3)` | L3 | percent | none | IEC 61000-4-7 |
| `u5l1` | 5th harmonic voltage component relative to fundamental phase L1 | `harmonic_voltage (order 5)` | L1 | percent | none | IEC 61000-4-7 |
| `u5l2` | 5th harmonic voltage component relative to fundamental phase L2 | `harmonic_voltage (order 5)` | L2 | percent | none | IEC 61000-4-7 |
| `u5l3` | 5th harmonic voltage component relative to fundamental phase L3 | `harmonic_voltage (order 5)` | L3 | percent | none | IEC 61000-4-7 |
| `u7l1` | 7th harmonic voltage component relative to fundamental phase L1 | `harmonic_voltage (order 7)` | L1 | percent | none | IEC 61000-4-7 |
| `u7l2` | 7th harmonic voltage component relative to fundamental phase L2 | `harmonic_voltage (order 7)` | L2 | percent | none | IEC 61000-4-7 |
| `u7l3` | 7th harmonic voltage component relative to fundamental phase L3 | `harmonic_voltage (order 7)` | L3 | percent | none | IEC 61000-4-7 |

