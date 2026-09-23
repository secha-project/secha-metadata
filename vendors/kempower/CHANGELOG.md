# Changelog: kempower

## 1.0.0 (2026-09-23)

- Initial mapping of the passenger charging dataset (`public_passenger_dataset`), hand-authored
  for the held-out test before any machine draft was opened.
- Five of thirteen columns become measurements: `soc` (state_of_charge), `tempC`
  (temperature), and the DC output `avgPowerW`, `avgCurrentA`, `avgVoltageV` (phase `dc`).
- The session, its attributes and the time offset are declared in `source_schema.yaml`:
  `transactionId` identifies the session, `sampleTime10sIncrement` gives the offset in
  seconds, and country, vehicle model, year, month and weekday fill `charging_session`.
- Needs canonical schema 1.1.0 (phase `dc`) and quantity vocabulary 1.3.0
  (`state_of_charge`, `temperature`).
- Open with the provider: what `tempC` measures, whether power, current and voltage are the
  DC output, the averaging window, and why 17.8% of rows share a session and offset.
