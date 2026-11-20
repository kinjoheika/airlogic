-- =============================================================================
-- Links equipment units from the Equipment Data screenshot to visit
-- CP-2026-0807-JDC (Green Valley Residences), with the inspection results
-- visible in that screenshot. Safe to run twice.
-- Readings (numbers) are not in the screenshot, so only inspection items are
-- added. Run after 004_sample_visits.sql and 008_equipment_from_registry.sql.
-- =============================================================================

-- The schema allowed only one unit per client + sublocation, but the real
-- sites have several units in the same room (see screenshot). Drop that rule.
alter table equipment drop constraint if exists equipment_client_id_sublocation_id_key;

-- Client and sublocations
insert into clients (name)
select 'Green Valley Residences'
where not exists (select 1 from clients where name = 'Green Valley Residences');

insert into sublocations (client_id, name)
select c.id, s.name
from clients c
cross join (values
  ('Gym — Ground Floor'),
  ('Conference Rooms A & B — 3F'),
  ('Management Office — 4F')
) as s(name)
where c.name = 'Green Valley Residences'
  and not exists (select 1 from sublocations x where x.client_id = c.id and x.name = s.name);

-- Brands
insert into equipment_brands (name)
select b.name from (values ('LG'), ('Carrier'), ('Daikin'), ('Samsung')) as b(name)
where not exists (select 1 from equipment_brands e where e.name = b.name);

-- Equipment units (serial shown as last 4 digits in the screenshot)
insert into equipment (name, client_id, sublocation_id, brand_id, model, serial_number, status)
select u.name, c.id, sl.id, br.id, u.model, u.serial, 'active'
from (values
  ('LG S4-Q12JA3',        'LG',      'S4-Q12JA3',     '…1007', 'Gym — Ground Floor'),
  ('Carrier 40MBFQ12',    'Carrier', '40MBFQ12',      '…1008', 'Gym — Ground Floor'),
  ('Daikin FTXS35G',      'Daikin',  'FTXS35G',       '…1009', 'Conference Rooms A & B — 3F'),
  ('Carrier 40MBFQ09',    'Carrier', '40MBFQ09',      '…1010', 'Conference Rooms A & B — 3F'),
  ('Samsung AR12TYHYCWK', 'Samsung', 'AR12TYHYCWK',   '…1011', 'Conference Rooms A & B — 3F'),
  ('Daikin FTKF25TV',     'Daikin',  'FTKF25TV',      '…1012', 'Management Office — 4F')
) as u(name, brand_name, model, serial, sub_name)
join clients c on c.name = 'Green Valley Residences'
join sublocations sl on sl.client_id = c.id and sl.name = u.sub_name
join equipment_brands br on br.name = u.brand_name
where not exists (
  select 1 from equipment x
  where x.client_id = c.id and x.sublocation_id = sl.id and x.name = u.name
);

-- One service job per unit on the visit
insert into service_jobs (reference, visit_id, equipment_id, client_id, visit_date, state)
select
  'JOB-0807-' || substr(e.serial_number, 2),
  v.id, e.id, c.id, v.visit_date, 'draft'
from equipment e
join clients c on c.id = e.client_id and c.name = 'Green Valley Residences'
join service_visits v on v.reference = 'CP-2026-0807-JDC'
where e.serial_number in ('…1007', '…1008', '…1009', '…1010', '…1011', '…1012')
  and not exists (select 1 from service_jobs j where j.reference = 'JOB-0807-' || substr(e.serial_number, 2));

-- Inspection results (all "Normal" in the screenshot)
insert into checklist_lines (job_id, phase, key, label, value)
select j.id, c.phase, c.key, c.label, 'Normal'
from service_jobs j
join service_visits v on v.id = j.visit_id and v.reference = 'CP-2026-0807-JDC'
cross join (values
  (1, 'breaker_wires', 'Breaker Wires & Terminals'),
  (1, 'compressor_body', 'Compressor Body'),
  (1, 'coils_fins', 'Coils & Fins'),
  (1, 'motor_fan', 'Motor & Fan'),
  (1, 'pcb', 'PCB')
) as c(phase, key, label)
where not exists (
  select 1 from checklist_lines x where x.job_id = j.id and x.key = c.key
);

-- Check: should list the 6 jobs on this visit
select j.reference, e.name as unit, sl.name as sublocation, e.serial_number
from service_jobs j
join service_visits v on v.id = j.visit_id
join equipment e on e.id = j.equipment_id
left join sublocations sl on sl.id = e.sublocation_id
where v.reference = 'CP-2026-0807-JDC'
order by sl.name, e.name;
