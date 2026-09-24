# Kempower held-out test: scores

Gold: `vendors/kempower` at 569dc7854d85defc643425e3bfbf871dc94c9060 2026-09-23T13:58:42+03:00. Every scored file matched its seal.

### C0-no-convention / codestral-2508 (vocabulary at cd564b9cb0bb)

- Class A (answerable): 0, exact 0 strict / 0 effective
- Class B (needed new vocabulary): 5, outcomes: soc invented, tempC invented, avgPowerW force-fit, avgCurrentA force-fit, avgVoltageV force-fit
- Class C (gold leaves unmapped): 0, outcomes: none
- Correction effort: 5 edit(s) (5 field(s) changed, 0 entr(y/ies) added, 0 removed)
- Draft entries invalid against the vocabulary offered: 2
- Whole-draft gate: 5 problem(s), 2 naming a proposed column
- Provider failures (no reply, excluded from everything above): 0

| Column | Class | Gold | Draft | Outcome | Wrong (strict) | Wrong (effective) |
|---|---|---|---|---|---|---|
| `soc` | B | quantity=state_of_charge, phase=none, aggregation=instantaneous, unit=percent | quantity=state_of_charge, phase=none, unit=percent | invented | aggregation | aggregation |
| `tempC` | B | quantity=temperature, phase=none, aggregation=instantaneous, unit=degC | quantity=temperature, phase=none, unit=degC | invented | aggregation | aggregation |
| `avgPowerW` | B | quantity=active_power, phase=dc, unit=W | quantity=active_power, phase=none, aggregation=average, unit=W | force-fit | phase, aggregation | phase |
| `avgCurrentA` | B | quantity=current, phase=dc, unit=A | quantity=current, phase=L1, aggregation=average, unit=A | force-fit | phase, aggregation | phase |
| `avgVoltageV` | B | quantity=voltage, phase=dc, unit=V | quantity=voltage, phase=none, aggregation=average, unit=V | force-fit | phase, aggregation | phase |

Gate problems as recorded:

- [schema] kempower/mapping: columns/2: Additional properties are not allowed ('aggregation' was unexpected)
- [schema] kempower/mapping: columns/3: Additional properties are not allowed ('aggregation' was unexpected)
- [schema] kempower/mapping: columns/4: Additional properties are not allowed ('aggregation' was unexpected)
- [xref] kempower/mapping[soc]: quantity 'state_of_charge' not in vocabulary
- [xref] kempower/mapping[tempC]: quantity 'temperature' not in vocabulary

### C0-no-convention / kimi-k3 (vocabulary at cd564b9cb0bb)

- Class A (answerable): 0, exact 0 strict / 0 effective
- Class B (needed new vocabulary): 5, outcomes: soc invented, tempC invented, avgPowerW force-fit, avgCurrentA force-fit, avgVoltageV force-fit
- Class C (gold leaves unmapped): 0, outcomes: none
- Correction effort: 6 edit(s) (6 field(s) changed, 0 entr(y/ies) added, 0 removed)
- Draft entries invalid against the vocabulary offered: 2
- Whole-draft gate: 5 problem(s), 2 naming a proposed column
- Provider failures (no reply, excluded from everything above): 0

| Column | Class | Gold | Draft | Outcome | Wrong (strict) | Wrong (effective) |
|---|---|---|---|---|---|---|
| `soc` | B | quantity=state_of_charge, phase=none, aggregation=instantaneous, unit=percent | quantity=none, phase=none, unit=percent | invented | quantity, aggregation | quantity, aggregation |
| `tempC` | B | quantity=temperature, phase=none, aggregation=instantaneous, unit=degC | quantity=temperature, phase=none, unit=degC | invented | aggregation | aggregation |
| `avgPowerW` | B | quantity=active_power, phase=dc, unit=W | quantity=active_power, phase=none, aggregation=average, unit=W | force-fit | phase, aggregation | phase |
| `avgCurrentA` | B | quantity=current, phase=dc, unit=A | quantity=current, phase=none, aggregation=average, unit=A | force-fit | phase, aggregation | phase |
| `avgVoltageV` | B | quantity=voltage, phase=dc, unit=V | quantity=voltage, phase=none, aggregation=average, unit=V | force-fit | phase, aggregation | phase |

Gate problems as recorded:

- [schema] kempower/mapping: columns/2: Additional properties are not allowed ('aggregation' was unexpected)
- [schema] kempower/mapping: columns/3: Additional properties are not allowed ('aggregation' was unexpected)
- [schema] kempower/mapping: columns/4: Additional properties are not allowed ('aggregation' was unexpected)
- [xref] kempower/mapping[soc]: quantity 'none' not in vocabulary
- [xref] kempower/mapping[tempC]: quantity 'temperature' not in vocabulary

### C0-no-convention / phi4-14b (vocabulary at cd564b9cb0bb)

- Class A (answerable): 0, exact 0 strict / 0 effective
- Class B (needed new vocabulary): 5, outcomes: soc invented, tempC invented, avgPowerW force-fit, avgCurrentA force-fit, avgVoltageV force-fit
- Class C (gold leaves unmapped): 0, outcomes: none
- Correction effort: 8 edit(s) (8 field(s) changed, 0 entr(y/ies) added, 0 removed)
- Draft entries invalid against the vocabulary offered: 2
- Whole-draft gate: 9 problem(s), 4 naming a proposed column
- Provider failures (no reply, excluded from everything above): 0

| Column | Class | Gold | Draft | Outcome | Wrong (strict) | Wrong (effective) |
|---|---|---|---|---|---|---|
| `soc` | B | quantity=state_of_charge, phase=none, aggregation=instantaneous, unit=percent | quantity=unknown | invented | quantity, phase, aggregation, unit | quantity, phase, aggregation, unit |
| `tempC` | B | quantity=temperature, phase=none, aggregation=instantaneous, unit=degC | quantity=temperature, phase=none, unit=degC | invented | aggregation | aggregation |
| `avgPowerW` | B | quantity=active_power, phase=dc, unit=W | quantity=active_power, phase=three_phase, aggregation=average, unit=W | force-fit | phase, aggregation | phase |
| `avgCurrentA` | B | quantity=current, phase=dc, unit=A | quantity=current, phase=three_phase, aggregation=average, unit=A | force-fit | phase, aggregation | phase |
| `avgVoltageV` | B | quantity=voltage, phase=dc, unit=V | quantity=voltage, phase=three_phase, aggregation=average, unit=V | force-fit | phase, aggregation | phase |

Gate problems as recorded:

- [schema] kempower/mapping: columns/2: Additional properties are not allowed ('aggregation' was unexpected)
- [schema] kempower/mapping: columns/3: Additional properties are not allowed ('aggregation' was unexpected)
- [schema] kempower/mapping: columns/4: Additional properties are not allowed ('aggregation' was unexpected)
- [schema] kempower/mapping: columns/0/phase: None is not of type 'string'
- [schema] kempower/mapping: columns/0/unit: None is not of type 'string'
- [xref] kempower/mapping[soc]: quantity 'unknown' not in vocabulary
- [xref] kempower/mapping[soc]: phase 'None' not a canonical phase
- [xref] kempower/mapping[soc]: unit 'None' not in unit registry
- [xref] kempower/mapping[tempC]: quantity 'temperature' not in vocabulary

### C1-convention / codestral-2508 (vocabulary at cd564b9cb0bb)

- Class A (answerable): 0, exact 0 strict / 0 effective
- Class B (needed new vocabulary): 5, outcomes: soc invented, tempC invented, avgPowerW force-fit, avgCurrentA force-fit, avgVoltageV force-fit
- Class C (gold leaves unmapped): 0, outcomes: none
- Correction effort: 7 edit(s) (7 field(s) changed, 0 entr(y/ies) added, 0 removed)
- Draft entries invalid against the vocabulary offered: 2
- Whole-draft gate: 5 problem(s), 2 naming a proposed column
- Provider failures (no reply, excluded from everything above): 0

| Column | Class | Gold | Draft | Outcome | Wrong (strict) | Wrong (effective) |
|---|---|---|---|---|---|---|
| `soc` | B | quantity=state_of_charge, phase=none, aggregation=instantaneous, unit=percent | quantity=soc, phase=none, unit=percent | invented | quantity, aggregation | quantity, aggregation |
| `tempC` | B | quantity=temperature, phase=none, aggregation=instantaneous, unit=degC | quantity=tempC, phase=none, unit=degC | invented | quantity, aggregation | quantity, aggregation |
| `avgPowerW` | B | quantity=active_power, phase=dc, unit=W | quantity=active_power, phase=none, aggregation=average, unit=W | force-fit | phase, aggregation | phase |
| `avgCurrentA` | B | quantity=current, phase=dc, unit=A | quantity=current, phase=none, aggregation=average, unit=A | force-fit | phase, aggregation | phase |
| `avgVoltageV` | B | quantity=voltage, phase=dc, unit=V | quantity=voltage, phase=none, aggregation=average, unit=V | force-fit | phase, aggregation | phase |

Gate problems as recorded:

- [schema] kempower/mapping: columns/2: Additional properties are not allowed ('aggregation' was unexpected)
- [schema] kempower/mapping: columns/3: Additional properties are not allowed ('aggregation' was unexpected)
- [schema] kempower/mapping: columns/4: Additional properties are not allowed ('aggregation' was unexpected)
- [xref] kempower/mapping[soc]: quantity 'soc' not in vocabulary
- [xref] kempower/mapping[tempC]: quantity 'tempC' not in vocabulary

### C1-convention / kimi-k3 (vocabulary at cd564b9cb0bb)

- Class A (answerable): 0, exact 0 strict / 0 effective
- Class B (needed new vocabulary): 5, outcomes: soc invented, tempC invented, avgPowerW force-fit, avgCurrentA force-fit, avgVoltageV force-fit
- Class C (gold leaves unmapped): 0, outcomes: none
- Correction effort: 5 edit(s) (5 field(s) changed, 0 entr(y/ies) added, 0 removed)
- Draft entries invalid against the vocabulary offered: 2
- Whole-draft gate: clean
- Provider failures (no reply, excluded from everything above): 0

| Column | Class | Gold | Draft | Outcome | Wrong (strict) | Wrong (effective) |
|---|---|---|---|---|---|---|
| `soc` | B | quantity=state_of_charge, phase=none, aggregation=instantaneous, unit=percent | quantity=state_of_charge, phase=none, unit=percent | invented | aggregation | aggregation |
| `tempC` | B | quantity=temperature, phase=none, aggregation=instantaneous, unit=degC | quantity=temperature, phase=none, unit=degC | invented | aggregation | aggregation |
| `avgPowerW` | B | quantity=active_power, phase=dc, unit=W | quantity=active_power, phase=none, aggregation=average, unit=W | force-fit | phase, aggregation | phase |
| `avgCurrentA` | B | quantity=current, phase=dc, unit=A | quantity=current, phase=none, aggregation=average, unit=A | force-fit | phase, aggregation | phase |
| `avgVoltageV` | B | quantity=voltage, phase=dc, unit=V | quantity=voltage, phase=none, aggregation=average, unit=V | force-fit | phase, aggregation | phase |

### C1-convention / phi4-14b (vocabulary at cd564b9cb0bb)

- Class A (answerable): 0, exact 0 strict / 0 effective
- Class B (needed new vocabulary): 5, outcomes: soc invented, tempC invented, avgPowerW force-fit, avgCurrentA force-fit, avgVoltageV force-fit
- Class C (gold leaves unmapped): 0, outcomes: none
- Correction effort: 5 edit(s) (5 field(s) changed, 0 entr(y/ies) added, 0 removed)
- Draft entries invalid against the vocabulary offered: 2
- Whole-draft gate: 5 problem(s), 2 naming a proposed column
- Provider failures (no reply, excluded from everything above): 0

| Column | Class | Gold | Draft | Outcome | Wrong (strict) | Wrong (effective) |
|---|---|---|---|---|---|---|
| `soc` | B | quantity=state_of_charge, phase=none, aggregation=instantaneous, unit=percent | quantity=state_of_charge, phase=none, unit=percent | invented | aggregation | aggregation |
| `tempC` | B | quantity=temperature, phase=none, aggregation=instantaneous, unit=degC | quantity=temperature, phase=none, unit=degC | invented | aggregation | aggregation |
| `avgPowerW` | B | quantity=active_power, phase=dc, unit=W | quantity=active_power, phase=three_phase, aggregation=average, unit=W | force-fit | phase, aggregation | phase |
| `avgCurrentA` | B | quantity=current, phase=dc, unit=A | quantity=current, phase=three_phase, aggregation=average, unit=A | force-fit | phase, aggregation | phase |
| `avgVoltageV` | B | quantity=voltage, phase=dc, unit=V | quantity=voltage, phase=three_phase, aggregation=average, unit=V | force-fit | phase, aggregation | phase |

Gate problems as recorded:

- [schema] kempower/mapping: columns/2: Additional properties are not allowed ('aggregation' was unexpected)
- [schema] kempower/mapping: columns/3: Additional properties are not allowed ('aggregation' was unexpected)
- [schema] kempower/mapping: columns/4: Additional properties are not allowed ('aggregation' was unexpected)
- [xref] kempower/mapping[soc]: quantity 'state_of_charge' not in vocabulary
- [xref] kempower/mapping[tempC]: quantity 'temperature' not in vocabulary

### C2-convention / codestral-2508 (vocabulary at HEAD)

- Class A (answerable): 5, exact 0 strict / 3 effective
- Class B (needed new vocabulary): 0, outcomes: none
- Class C (gold leaves unmapped): 0, outcomes: none
- Correction effort: 2 edit(s) (2 field(s) changed, 0 entr(y/ies) added, 0 removed)
- Draft entries invalid against the vocabulary offered: 0
- Whole-draft gate: clean
- Provider failures (no reply, excluded from everything above): 0

| Column | Class | Gold | Draft | Outcome | Wrong (strict) | Wrong (effective) |
|---|---|---|---|---|---|---|
| `soc` | A | quantity=state_of_charge, phase=none, aggregation=instantaneous, unit=percent | quantity=state_of_charge, phase=none, unit=percent | wrong | aggregation | aggregation |
| `tempC` | A | quantity=temperature, phase=none, aggregation=instantaneous, unit=degC | quantity=temperature, phase=none, unit=degC | wrong | aggregation | aggregation |
| `avgPowerW` | A | quantity=active_power, phase=dc, unit=W | quantity=active_power, phase=dc, aggregation=average, unit=W | wrong | aggregation | - |
| `avgCurrentA` | A | quantity=current, phase=dc, unit=A | quantity=current, phase=dc, aggregation=average, unit=A | wrong | aggregation | - |
| `avgVoltageV` | A | quantity=voltage, phase=dc, unit=V | quantity=voltage, phase=dc, aggregation=average, unit=V | wrong | aggregation | - |

### C2-convention / kimi-k3 (vocabulary at HEAD)

- Class A (answerable): 5, exact 0 strict / 3 effective
- Class B (needed new vocabulary): 0, outcomes: none
- Class C (gold leaves unmapped): 0, outcomes: none
- Correction effort: 2 edit(s) (2 field(s) changed, 0 entr(y/ies) added, 0 removed)
- Draft entries invalid against the vocabulary offered: 0
- Whole-draft gate: clean
- Provider failures (no reply, excluded from everything above): 0

| Column | Class | Gold | Draft | Outcome | Wrong (strict) | Wrong (effective) |
|---|---|---|---|---|---|---|
| `soc` | A | quantity=state_of_charge, phase=none, aggregation=instantaneous, unit=percent | quantity=state_of_charge, phase=none, unit=percent | wrong | aggregation | aggregation |
| `tempC` | A | quantity=temperature, phase=none, aggregation=instantaneous, unit=degC | quantity=temperature, phase=none, aggregation=average, unit=degC | wrong | aggregation | aggregation |
| `avgPowerW` | A | quantity=active_power, phase=dc, unit=W | quantity=active_power, phase=dc, aggregation=average, unit=W | wrong | aggregation | - |
| `avgCurrentA` | A | quantity=current, phase=dc, unit=A | quantity=current, phase=dc, aggregation=average, unit=A | wrong | aggregation | - |
| `avgVoltageV` | A | quantity=voltage, phase=dc, unit=V | quantity=voltage, phase=dc, aggregation=average, unit=V | wrong | aggregation | - |

### C2-convention / phi4-14b (vocabulary at HEAD)

- Class A (answerable): 5, exact 0 strict / 2 effective
- Class B (needed new vocabulary): 0, outcomes: none
- Class C (gold leaves unmapped): 0, outcomes: none
- Correction effort: 3 edit(s) (3 field(s) changed, 0 entr(y/ies) added, 0 removed)
- Draft entries invalid against the vocabulary offered: 0
- Whole-draft gate: clean
- Provider failures (no reply, excluded from everything above): 0

| Column | Class | Gold | Draft | Outcome | Wrong (strict) | Wrong (effective) |
|---|---|---|---|---|---|---|
| `soc` | A | quantity=state_of_charge, phase=none, aggregation=instantaneous, unit=percent | quantity=state_of_charge, phase=none, unit=percent | wrong | aggregation | aggregation |
| `tempC` | A | quantity=temperature, phase=none, aggregation=instantaneous, unit=degC | quantity=temperature, phase=none, unit=degC | wrong | aggregation | aggregation |
| `avgPowerW` | A | quantity=active_power, phase=dc, unit=W | quantity=active_power, phase=dc, aggregation=average, unit=W | wrong | aggregation | - |
| `avgCurrentA` | A | quantity=current, phase=dc, unit=A | quantity=current, phase=three_phase, aggregation=average, unit=A | wrong | phase, aggregation | phase |
| `avgVoltageV` | A | quantity=voltage, phase=dc, unit=V | quantity=voltage, phase=dc, aggregation=average, unit=V | wrong | aggregation | - |

### C2-no-convention / codestral-2508 (vocabulary at HEAD)

- Class A (answerable): 5, exact 0 strict / 0 effective
- Class B (needed new vocabulary): 0, outcomes: none
- Class C (gold leaves unmapped): 0, outcomes: none
- Correction effort: 5 edit(s) (5 field(s) changed, 0 entr(y/ies) added, 0 removed)
- Draft entries invalid against the vocabulary offered: 0
- Whole-draft gate: clean
- Provider failures (no reply, excluded from everything above): 0

| Column | Class | Gold | Draft | Outcome | Wrong (strict) | Wrong (effective) |
|---|---|---|---|---|---|---|
| `soc` | A | quantity=state_of_charge, phase=none, aggregation=instantaneous, unit=percent | quantity=state_of_charge, phase=none, unit=percent | wrong | aggregation | aggregation |
| `tempC` | A | quantity=temperature, phase=none, aggregation=instantaneous, unit=degC | quantity=temperature, phase=none, unit=degC | wrong | aggregation | aggregation |
| `avgPowerW` | A | quantity=active_power, phase=dc, unit=W | quantity=active_power, phase=none, aggregation=average, unit=W | wrong | phase, aggregation | phase |
| `avgCurrentA` | A | quantity=current, phase=dc, unit=A | quantity=current, phase=L1, aggregation=average, unit=A | wrong | phase, aggregation | phase |
| `avgVoltageV` | A | quantity=voltage, phase=dc, unit=V | quantity=voltage, phase=none, aggregation=average, unit=V | wrong | phase, aggregation | phase |

### C2-no-convention / kimi-k3 (vocabulary at HEAD)

- Class A (answerable): 5, exact 0 strict / 0 effective
- Class B (needed new vocabulary): 0, outcomes: none
- Class C (gold leaves unmapped): 0, outcomes: none
- Correction effort: 5 edit(s) (5 field(s) changed, 0 entr(y/ies) added, 0 removed)
- Draft entries invalid against the vocabulary offered: 0
- Whole-draft gate: clean
- Provider failures (no reply, excluded from everything above): 0

| Column | Class | Gold | Draft | Outcome | Wrong (strict) | Wrong (effective) |
|---|---|---|---|---|---|---|
| `soc` | A | quantity=state_of_charge, phase=none, aggregation=instantaneous, unit=percent | quantity=state_of_charge, phase=none, unit=percent | wrong | aggregation | aggregation |
| `tempC` | A | quantity=temperature, phase=none, aggregation=instantaneous, unit=degC | quantity=temperature, phase=none, unit=degC | wrong | aggregation | aggregation |
| `avgPowerW` | A | quantity=active_power, phase=dc, unit=W | quantity=active_power, phase=none, aggregation=average, unit=W | wrong | phase, aggregation | phase |
| `avgCurrentA` | A | quantity=current, phase=dc, unit=A | quantity=current, phase=none, aggregation=average, unit=A | wrong | phase, aggregation | phase |
| `avgVoltageV` | A | quantity=voltage, phase=dc, unit=V | quantity=voltage, phase=none, aggregation=average, unit=V | wrong | phase, aggregation | phase |

### C2-no-convention / phi4-14b (vocabulary at HEAD)

- Class A (answerable): 5, exact 0 strict / 0 effective
- Class B (needed new vocabulary): 0, outcomes: none
- Class C (gold leaves unmapped): 0, outcomes: none
- Correction effort: 5 edit(s) (5 field(s) changed, 0 entr(y/ies) added, 0 removed)
- Draft entries invalid against the vocabulary offered: 0
- Whole-draft gate: clean
- Provider failures (no reply, excluded from everything above): 0

| Column | Class | Gold | Draft | Outcome | Wrong (strict) | Wrong (effective) |
|---|---|---|---|---|---|---|
| `soc` | A | quantity=state_of_charge, phase=none, aggregation=instantaneous, unit=percent | quantity=state_of_charge, phase=none, unit=percent | wrong | aggregation | aggregation |
| `tempC` | A | quantity=temperature, phase=none, aggregation=instantaneous, unit=degC | quantity=temperature, phase=none, unit=degC | wrong | aggregation | aggregation |
| `avgPowerW` | A | quantity=active_power, phase=dc, unit=W | quantity=active_power, phase=three_phase, aggregation=average, unit=W | wrong | phase, aggregation | phase |
| `avgCurrentA` | A | quantity=current, phase=dc, unit=A | quantity=current, phase=three_phase, aggregation=average, unit=A | wrong | phase, aggregation | phase |
| `avgVoltageV` | A | quantity=voltage, phase=dc, unit=V | quantity=voltage, phase=three_phase, aggregation=average, unit=V | wrong | phase, aggregation | phase |
