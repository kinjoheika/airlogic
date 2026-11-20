-- =============================================================================
-- Full inspection checklist (from the service report table) for every unit on
-- visit CP-2026-0807-JDC. Adds section and standard to checklist rows.
-- Actual values are left empty, to be filled in during the visit.
-- Run after 015_green_valley_units.sql.
-- =============================================================================

alter table checklist_lines add column if not exists section text;
alter table checklist_lines add column if not exists standard text;

-- Replace the earlier 5–6 item checklist for these jobs
delete from checklist_lines where job_id in (
  select j.id from service_jobs j join service_visits v on v.id = j.visit_id
  where v.reference = 'CP-2026-0807-JDC');

insert into checklist_lines (job_id, phase, key, label, value, section, standard)
select j.id, c.phase, c.key, c.label, null, c.section, c.standard
from service_jobs j
join service_visits v on v.id = j.visit_id and v.reference = 'CP-2026-0807-JDC'
cross join (values
  (1, 'Ph 1 — Outdoor OFF', 'k01', 'Breaker Wires & Terminals', 'Normal'),
  (1, 'Ph 1 — Outdoor OFF', 'k02', 'Compressor Body', 'Normal'),
  (1, 'Ph 1 — Outdoor OFF', 'k03', 'Coils & Fins', 'Normal'),
  (1, 'Ph 1 — Outdoor OFF', 'k04', 'Motor & Fan', 'Normal'),
  (1, 'Ph 1 — Outdoor OFF', 'k05', 'PCB', 'Normal'),
  (1, 'Ph 1 — Outdoor OFF', 'k06', 'IPM', 'Normal'),
  (1, 'Ph 1 — Outdoor OFF', 'k07', 'Wires & Terminals', 'Normal'),
  (1, 'Ph 1 — Outdoor OFF', 'k08', 'Cable Ties/Paste/Grommets', 'Normal'),
  (2, 'Ph 2 — Outdoor ON', 'k09', 'Line Voltage', '198–242 V'),
  (2, 'Ph 2 — Outdoor ON', 'k10', 'Amp Draw L1', 'Nameplate ±10%'),
  (2, 'Ph 2 — Outdoor ON', 'k11', 'Amp Draw L2', 'Nameplate ±10%'),
  (2, 'Ph 2 — Outdoor ON', 'k12', 'Amp Draw L3', 'Nameplate ±10%'),
  (3, 'Ph 3 — Indoor Unit', 'k13', 'Anemometer (CFM)', 'Per BTU rating'),
  (3, 'Ph 3 — Indoor Unit', 'k14', 'Coil & Fins', 'Normal'),
  (3, 'Ph 3 — Indoor Unit', 'k15', 'Drain Pan', 'Normal'),
  (3, 'Ph 3 — Indoor Unit', 'k16', 'Wires (tactile)', 'Normal'),
  (4, 'Ph 4 — Line Set', 'k17', 'Insulation Tape', 'Normal'),
  (4, 'Ph 4 — Line Set', 'k18', 'Wire Condition', 'Normal'),
  (4, 'Ph 4 — Line Set', 'k19', 'Condensation', 'Normal'),
  (4, 'Ph 4 — Line Set', 'k20', 'Leak Check', 'No Leak'),
  (4, 'Ph 4 — Line Set', 'k21', 'Tech Notes', '—'),
  (5, 'Fieldpiece — Air Side', 'k22', 'Return Air Dry Bulb', '—'),
  (5, 'Fieldpiece — Air Side', 'k23', 'Supply Air Dry Bulb', '—'),
  (5, 'Fieldpiece — Air Side', 'k24', 'Target Evaporator Exit', '—'),
  (5, 'Fieldpiece — Air Side', 'k25', 'Return Air Wet Bulb', '—'),
  (5, 'Fieldpiece — Air Side', 'k26', 'Supply Air Wet Bulb', '—'),
  (5, 'Fieldpiece — Air Side', 'k27', 'Return RH%', '—'),
  (5, 'Fieldpiece — Air Side', 'k28', 'Supply RH%', '—'),
  (5, 'Fieldpiece — Air Side', 'k29', 'Return Dew Point', '—'),
  (5, 'Fieldpiece — Air Side', 'k30', 'Supply Dew Point', '—'),
  (5, 'Fieldpiece — Air Side', 'k31', 'Return Enthalpy', '—'),
  (5, 'Fieldpiece — Air Side', 'k32', 'Supply Enthalpy', '—'),
  (5, 'Fieldpiece — Air Side', 'k33', 'Cooling Airflow', '—'),
  (5, 'Fieldpiece — Air Side', 'k34', 'Cooling System Capacity', '—'),
  (5, 'Fieldpiece — Air Side', 'k35', 'Heating Airflow', '—'),
  (5, 'Fieldpiece — Air Side', 'k36', 'Heating System Capacity', '—'),
  (5, 'Fieldpiece — Air Side', 'k37', 'Delta T (T1-T2)', '≥ 8 °C'),
  (6, 'Fieldpiece — Refrigerant Side', 'k38', 'Refrigerant Type', '—'),
  (6, 'Fieldpiece — Refrigerant Side', 'k39', 'Outdoor Dry Bulb Temp', '—'),
  (6, 'Fieldpiece — Refrigerant Side', 'k40', 'Suction Line Pressure', '—'),
  (6, 'Fieldpiece — Refrigerant Side', 'k41', 'Liquid Line Pressure', '—'),
  (6, 'Fieldpiece — Refrigerant Side', 'k42', 'Vapor Saturation Temp', '—'),
  (6, 'Fieldpiece — Refrigerant Side', 'k43', 'Liquid Saturation Temp', '—'),
  (6, 'Fieldpiece — Refrigerant Side', 'k44', 'Suction Line Temperature', '—'),
  (6, 'Fieldpiece — Refrigerant Side', 'k45', 'Liquid Line Temperature', '—'),
  (6, 'Fieldpiece — Refrigerant Side', 'k46', 'Target Superheat', '—'),
  (6, 'Fieldpiece — Refrigerant Side', 'k47', 'Actual Superheat', '—'),
  (6, 'Fieldpiece — Refrigerant Side', 'k48', 'Target Subcooling', '—'),
  (6, 'Fieldpiece — Refrigerant Side', 'k49', 'Actual Subcooling', '—'),
  (7, 'Fieldpiece — Manometer Pressure', 'k50', 'Manometer P1', '—'),
  (7, 'Fieldpiece — Manometer Pressure', 'k51', 'Manometer P2', '—'),
  (7, 'Fieldpiece — Manometer Pressure', 'k52', 'P1 − P2', '—')
) as c(phase, section, key, label, standard);

-- Check: rows per unit (should be 52)
select j.reference, count(c.id) as checklist_rows
from service_jobs j
join service_visits v on v.id = j.visit_id and v.reference = 'CP-2026-0807-JDC'
left join checklist_lines c on c.job_id = j.id
group by j.reference order by j.reference
limit 5;
