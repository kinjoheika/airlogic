-- =============================================================================
-- Green Valley Residences: the 25 units from the site list (serials ···1001 to
-- ···1025), placed in their rooms. Also links them to visit CP-2026-0807-JDC
-- with the inspection results (all Normal). Replaces the old "GEN" sample rows.
-- Safe to run twice. Run after 001, 004, 008, and 009.
-- =============================================================================

-- 1) Remove the old "GEN" sample rows (same as 011)
delete from invoices where number like 'GEN-INV-%';
delete from service_visits where reference like 'GEN-%';
delete from equipment where name like 'GEN Unit %';
delete from sublocations where name like 'GEN Room %';
delete from clients where name like 'GEN Client %';

-- 2) Several units can share a room
alter table equipment drop constraint if exists equipment_client_id_sublocation_id_key;

-- 3) Client
insert into clients (name, address, email, phone)
select 'Green Valley Residences', 'Muntinlupa City', 'facilities@greenvalley.example', '02-8555-0100'
where not exists (select 1 from clients where name = 'Green Valley Residences');

-- 4) Brands
insert into equipment_brands (name)
select b.name from (values ('Daikin'), ('LG'), ('Carrier'), ('Samsung'), ('Mitsubishi'), ('Panasonic')) as b(name)
where not exists (select 1 from equipment_brands e where e.name = b.name);

-- 5) Rooms
insert into sublocations (client_id, name)
select c.id, s.name
from clients c
cross join (values
  ('Lobby — Main Entrance'), ('Guard House & Reception'), ('Gym — Ground Floor'),
  ('Conference Rooms A & B — 3F'), ('Management Office — 4F'),
  ('Residential Units 101–103'), ('Residential Units 201–204'), ('Pool Area & Parking B1')
) as s(name)
where c.name = 'Green Valley Residences'
  and not exists (select 1 from sublocations x where x.client_id = c.id and x.name = s.name);

-- 6) The 25 units
insert into equipment (name, client_id, sublocation_id, brand_id, model, serial_number, install_year, status)
select u.brand || ' ' || u.model, c.id, sl.id, br.id, u.model, u.serial, null, 'active'
from (values
  ('…1001', 'Lobby — Main Entrance',          'Daikin',     'FTKF25TV'),
  ('…1002', 'Lobby — Main Entrance',          'LG',         'S4-W09JA3'),
  ('…1003', 'Lobby — Main Entrance',          'Carrier',    '40MBFQ09'),
  ('…1004', 'Guard House & Reception',        'Samsung',    'AR09TYHYCWK'),
  ('…1005', 'Guard House & Reception',        'Daikin',     'FTKF18TV'),
  ('…1006', 'Gym — Ground Floor',             'Mitsubishi', 'MSZ-GL25VGD'),
  ('…1007', 'Gym — Ground Floor',             'LG',         'S4-Q12JA3'),
  ('…1008', 'Gym — Ground Floor',             'Carrier',    '40MBFQ12'),
  ('…1009', 'Conference Rooms A & B — 3F',    'Daikin',     'FTXS35G'),
  ('…1010', 'Conference Rooms A & B — 3F',    'Carrier',    '40MBFQ09'),
  ('…1011', 'Conference Rooms A & B — 3F',    'Samsung',    'AR12TYHYCWK'),
  ('…1012', 'Management Office — 4F',         'Daikin',     'FTKF25TV'),
  ('…1013', 'Management Office — 4F',         'LG',         'Inverter V PLNC12'),
  ('…1014', 'Management Office — 4F',         'Mitsubishi', 'MSZ-GL18VGD'),
  ('…1015', 'Management Office — 4F',         'Carrier',    '40MBFQ09'),
  ('…1016', 'Residential Units 101–103',      'Daikin',     'FTKF25TV'),
  ('…1017', 'Residential Units 101–103',      'LG',         'S4-W09JA3'),
  ('…1018', 'Residential Units 101–103',      'Daikin',     'FTKF35TV'),
  ('…1019', 'Residential Units 201–204',      'Carrier',    '40MBFQ09'),
  ('…1020', 'Residential Units 201–204',      'LG',         'S4-Q12JA3'),
  ('…1021', 'Residential Units 201–204',      'Mitsubishi', 'MSZ-GL25VGD'),
  ('…1022', 'Residential Units 201–204',      'Panasonic',  'CS-S18PKH'),
  ('…1023', 'Pool Area & Parking B1',         'Carrier',    '40MBFQ12'),
  ('…1024', 'Pool Area & Parking B1',         'Mitsubishi', 'PEA-M60GAA'),
  ('…1025', 'Pool Area & Parking B1',         'Daikin',     'FTKF50TV')
) as u(serial, sub_name, brand, model)
join clients c on c.name = 'Green Valley Residences'
join sublocations sl on sl.client_id = c.id and sl.name = u.sub_name
join equipment_brands br on br.name = u.brand
where not exists (select 1 from equipment e where e.client_id = c.id and e.serial_number = u.serial);

-- 7) Jobs for visit CP-2026-0807-JDC: one per unit (existing jobs are kept)
insert into service_jobs (reference, visit_id, equipment_id, client_id, visit_date, state)
select 'JOB-0807-' || substr(e.serial_number, 2), v.id, e.id, c.id, v.visit_date, 'draft'
from equipment e
join clients c on c.id = e.client_id and c.name = 'Green Valley Residences'
join service_visits v on v.reference = 'CP-2026-0807-JDC'
where e.serial_number like '…10__'
  and not exists (select 1 from service_jobs j where j.reference = 'JOB-0807-' || substr(e.serial_number, 2));

-- 8) Inspection results: all Normal
insert into checklist_lines (job_id, phase, key, label, value)
select j.id, 1, c.key, c.label, 'Normal'
from service_jobs j
join service_visits v on v.id = j.visit_id and v.reference = 'CP-2026-0807-JDC'
cross join (values
  ('breaker_wires', 'Breaker Wires & Terminals'),
  ('compressor_body', 'Compressor Body'),
  ('coils_fins', 'Coils & Fins'),
  ('motor_fan', 'Motor & Fan'),
  ('pcb', 'PCB'),
  ('ipm', 'IPM')
) as c(key, label)
where not exists (select 1 from checklist_lines x where x.job_id = j.id and x.key = c.key);

-- Check: 25 units on Green Valley
select count(*) as green_valley_units from equipment e
join clients c on c.id = e.client_id where c.name = 'Green Valley Residences';
