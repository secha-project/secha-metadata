-- pq_minute_wide: minute-level wide power-quality overview per device, all vendors.
--
-- Serving definitions are config-as-code: this file holds ONE SELECT over the canonical
-- fact (referenced via the {canonical} placeholder). The sink materialises it per the
-- target's serving_mode: as a VIEW, or as a refreshed Delta TABLE snapshot on platforms
-- whose catalog connector lacks view support (the current TUNI UC connector). Either
-- way this body never changes; that is the point of the placeholder.
--
-- Consumers get one friendly wide row per device-minute; the long canonical fact stays the
-- interoperability substrate underneath. Quantities a vendor does not provide are NULL.
-- Only quality = 'ok' readings contribute (flagged values are excluded, per the EE ask).
-- A minute view needs clock time: sources that only count time from a session start
-- (Kempower) have no ts_utc and would otherwise form one NULL-minute row per device.
SELECT
    source_vendor,
    device_id,
    date_trunc('minute', CAST(ts_utc AS TIMESTAMP)) AS minute_utc,
    avg(CASE WHEN quantity = 'frequency' AND variant = 'none' THEN value END) AS frequency_hz,
    avg(CASE WHEN quantity = 'voltage' AND phase = 'L1' AND variant = 'none' THEN value END) AS voltage_l1_v,
    avg(CASE WHEN quantity = 'voltage' AND phase = 'L2' AND variant = 'none' THEN value END) AS voltage_l2_v,
    avg(CASE WHEN quantity = 'voltage' AND phase = 'L3' AND variant = 'none' THEN value END) AS voltage_l3_v,
    avg(CASE WHEN quantity = 'current' AND phase = 'L1' AND variant = 'none' THEN value END) AS current_l1_a,
    avg(CASE WHEN quantity = 'current' AND phase = 'L2' AND variant = 'none' THEN value END) AS current_l2_a,
    avg(CASE WHEN quantity = 'current' AND phase = 'L3' AND variant = 'none' THEN value END) AS current_l3_a,
    avg(CASE WHEN quantity = 'current' AND phase = 'N' AND variant = 'none' THEN value END) AS current_n_a,
    avg(CASE WHEN quantity = 'active_power' AND phase = 'three_phase' AND variant = 'none' THEN value END) AS active_power_total_w,
    avg(CASE WHEN quantity = 'reactive_power' AND phase = 'three_phase' AND variant = 'fundamental' THEN value END) AS reactive_power_fund_var,
    avg(CASE WHEN quantity = 'apparent_power' AND phase = 'three_phase' AND variant = 'none' THEN value END) AS apparent_power_total_va,
    avg(CASE WHEN quantity = 'power_factor' AND phase = 'L1' AND variant = 'none' THEN value END) AS power_factor_l1,
    avg(CASE WHEN quantity = 'thd_voltage' AND phase = 'L1' AND variant = 'none' THEN value END) AS thd_voltage_l1_pct,
    avg(CASE WHEN quantity = 'thd_current' AND phase = 'L1' AND variant = 'none' THEN value END) AS thd_current_l1_pct,
    avg(CASE WHEN quantity = 'voltage_unbalance_negative_seq' THEN value END) AS voltage_unbalance_neg_seq_pct,
    count(*) AS source_rows
FROM {canonical}
WHERE quality = 'ok'
  AND ts_utc IS NOT NULL
GROUP BY
    source_vendor,
    device_id,
    date_trunc('minute', CAST(ts_utc AS TIMESTAMP))
