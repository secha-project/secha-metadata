# Lineage: kempower

Source `public_passenger_dataset` · mapping_version `1.0.0`.
Generated from `secha-metadata` configs by `lineage.py`. **Do not edit by hand.**

| Source field | Meaning (vendor) | Canonical quantity | Phase | Unit | Transform | Standard |
|---|---|---|---|---|---|---|
| `soc` | State of charge of the vehicle's battery. No avg prefix; the unit is not declared. | `state_of_charge` | none | percent | none | ISO 15118-2 (EVRESSSOC); DIN SPEC 70121 |
| `tempC` | Temperature in degrees Celsius; ambient, battery or charger is undocumented. | `temperature` | none | degC | none | ISO 80000-5 (temperature) |
| `avgPowerW` | Average power over the sampling step; most likely the DC output to the vehicle. | `active_power` | dc | W | none | IEEE 1459-2010 |
| `avgCurrentA` | Average current over the sampling step; most likely the DC output to the vehicle. | `current` | dc | A | none | IEC 61000-4-30:2025 |
| `avgVoltageV` | Average voltage over the sampling step; most likely the DC output to the vehicle. | `voltage` | dc | V | none | IEC 61000-4-30:2025 (voltage magnitude); EN 50160 limits |

