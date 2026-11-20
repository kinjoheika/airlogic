-- =============================================================================
-- REALISTIC SAMPLE DATA (generated). Replaces the old "GEN" sample rows.
-- Four sample clients, their rooms, units (brand + model + serial), 16 visits,
-- jobs, readings, inspection checks, and 4 invoices.
-- Remove it all with 013_remove_realistic_sample_data.sql.
-- Run after 001, 004, and 006. Safe to run twice.
-- =============================================================================

-- 1) Remove the old "GEN" sample rows (see 011)
delete from invoices where number like 'GEN-INV-%';
delete from service_visits where reference like 'GEN-%';
delete from equipment where name like 'GEN Unit %';
delete from sublocations where name like 'GEN Room %';
delete from clients where name like 'GEN Client %';

-- 2) Allow several units in one room (real sites have this)
alter table equipment drop constraint if exists equipment_client_id_sublocation_id_key;

-- 3) Brands
insert into equipment_brands (name)
select b.name from (values ('Daikin'), ('Carrier'), ('LG'), ('Samsung'), ('Mitsubishi'), ('Panasonic')) as b(name)
where not exists (select 1 from equipment_brands e where e.name = b.name);

-- 4) Measurement fields (used for readings)
insert into measurement_fields (section, name, unit, standard, sequence)
select m.section, m.name, m.unit, m.standard, m.seq from (values
  ('Electrical', 'Compressor amps', 'A', '≤ 12.5', 10),
  ('Refrigerant', 'Suction pressure', 'psi', '110–125', 20),
  ('Air', 'Supply air temp', '°C', '10–14', 30),
  ('Electrical', 'Supply voltage', 'V', '220–240', 40)
) as m(section, name, unit, standard, seq)
where not exists (select 1 from measurement_fields x where x.name = m.name);

-- 5) Clients
insert into clients (name, address, email, phone)
select v.name, v.address, v.email, v.phone from (values
  ('Harbor View Residences', 'Roxas Blvd, Pasay City', 'facilities@harborview.example', '02-8555-0101'),
  ('Pinecrest Office Tower', 'Ayala Ave, Makati City', 'admin@pinecrest.example', '02-8555-0202'),
  ('Bayside Medical Clinic', 'Macapagal Ave, Pasay City', 'ops@baysideclinic.example', '02-8555-0303'),
  ('Maple Court Subdivision', 'Alabang-Zapote Rd, Muntinlupa', 'hoa@maplecourt.example', '02-8555-0404')
) as v(name, address, email, phone)
where not exists (select 1 from clients c where c.name = v.name);

-- 6) Rooms per client
insert into sublocations (client_id, name)
select c.id, s.name
from (values
  ('Harbor View Residences', 'Lobby — Main Entrance'),
  ('Harbor View Residences', 'Residential Units 101–103'),
  ('Harbor View Residences', 'Pool Area & Parking B1'),
  ('Pinecrest Office Tower', 'Guard House & Reception'),
  ('Pinecrest Office Tower', 'Conference Rooms A & B — 3F'),
  ('Pinecrest Office Tower', 'Management Office — 4F'),
  ('Bayside Medical Clinic', 'Waiting Area — Ground Floor'),
  ('Bayside Medical Clinic', 'Procedure Room 2'),
  ('Bayside Medical Clinic', 'Server Room — 2F'),
  ('Maple Court Subdivision', 'Clubhouse'),
  ('Maple Court Subdivision', 'Gym — Ground Floor'),
  ('Maple Court Subdivision', 'Residential Units 201–204')
) as s(client_name, name)
join clients c on c.name = s.client_name
where not exists (select 1 from sublocations x where x.client_id = c.id and x.name = s.name);

-- 7) Units: two per room, with a real-looking model catalogue
with cat as (
  select * from (values
    (1, 'Daikin',     'FTKF25TV',    2019),
    (2, 'Daikin',     'FTKF35TV',    2020),
    (3, 'Carrier',    '40MBFQ09',    2018),
    (4, 'Carrier',    '40MBFQ12',    2021),
    (5, 'LG',         'S4-W09JA3',   2017),
    (6, 'LG',         'S4-Q12JA3',   2022),
    (7, 'Samsung',    'AR12TYHYCWK', 2016),
    (8, 'Mitsubishi', 'MSZ-GL25VGD', 2019),
    (9, 'Panasonic',  'CS-S18PKH',   2015),
    (10,'Daikin',     'FTXS35G',     2023)
  ) as c(i, brand, model, yr)
),
rooms as (
  select s.id as sub_id, s.client_id,
         row_number() over (order by c.name, s.name) as room_no
  from sublocations s
  join clients c on c.id = s.client_id
  where c.name in ('Harbor View Residences', 'Pinecrest Office Tower', 'Bayside Medical Clinic', 'Maple Court Subdivision')
),
units as (
  select r.sub_id, r.client_id, r.room_no, k.i,
         row_number() over (order by r.room_no, k.i) as n
  from rooms r
  cross join generate_series(1, 2) as k(i)
)
insert into equipment (name, client_id, sublocation_id, brand_id, model, serial_number, install_year, status)
select
  cat.brand || ' ' || cat.model,
  u.client_id,
  u.sub_id,
  (select b.id from equipment_brands b where b.name = cat.brand),
  cat.model,
  '…' || lpad((1000 + u.n)::text, 4, '0'),
  cat.yr,
  'active'
from units u
join cat on cat.i = ((u.n - 1) % 10) + 1
where not exists (
  select 1 from equipment e
  where e.sublocation_id = u.sub_id and e.serial_number = '…' || lpad((1000 + u.n)::text, 4, '0')
);

-- 8) Visits: 16 over the summer, spread across the four clients
insert into service_visits (reference, client_id, visit_date, state, sublocation, technician_name)
select
  'CP-2026-' || to_char(date '2026-07-01' + (n * 2), 'MMDD') || '-' || lpad(n::text, 2, '0'),
  c.id,
  (date '2026-07-01' + (n * 2))::timestamptz,
  (array['draft', 'review', 'approved', 'invoiced'])[1 + (n % 4)],
  (select s.name from sublocations s where s.client_id = c.id order by s.name offset (n % 3) limit 1),
  (array['Juan dela Cruz', 'Carlo Reyes', 'Mark Ignacio', 'Jose Mendoza'])[1 + (n % 4)]
from generate_series(1, 16) as n
join clients c on c.name = (array['Harbor View Residences', 'Pinecrest Office Tower', 'Bayside Medical Clinic', 'Maple Court Subdivision'])[1 + ((n - 1) % 4)]
on conflict (reference) do nothing;

-- 9) Jobs: two units per visit
with ranked as (
  select e.id as eq_id, e.client_id,
         row_number() over (partition by e.client_id order by e.name, e.serial_number) as rn
  from equipment e
  join clients c on c.id = e.client_id
  where c.name in ('Harbor View Residences', 'Pinecrest Office Tower', 'Bayside Medical Clinic', 'Maple Court Subdivision')
)
insert into service_jobs (reference, visit_id, equipment_id, client_id, visit_date, state)
select 'JOB-' || v.reference || '-' || r.rn, v.id, r.eq_id, v.client_id, v.visit_date, 'draft'
from service_visits v
join ranked r on r.client_id = v.client_id and r.rn <= 2
where v.reference like 'CP-2026-%'
on conflict (reference) do nothing;

-- 10) Readings (about 1 in 8 outside standard)
insert into reading_lines (job_id, measurement_field_id, value, is_out_of_range)
select j.id, m.id,
       round((b.base + random() * b.span)::numeric, 1)::text,
       random() < 0.125
from service_jobs j
join clients c on c.id = j.client_id and c.name in ('Harbor View Residences', 'Pinecrest Office Tower', 'Bayside Medical Clinic', 'Maple Court Subdivision')
join measurement_fields m on m.name in ('Compressor amps', 'Suction pressure', 'Supply air temp', 'Supply voltage')
cross join lateral (select
    case m.name when 'Compressor amps' then 6 when 'Suction pressure' then 105 when 'Supply air temp' then 9 else 216 end as base,
    case m.name when 'Compressor amps' then 6 when 'Suction pressure' then 25 when 'Supply air temp' then 8 else 26 end as span) b
where j.reference like 'JOB-CP-2026-%'
  and not exists (select 1 from reading_lines x where x.job_id = j.id and x.measurement_field_id = m.id);

-- 11) Inspection checks: mostly Normal
insert into checklist_lines (job_id, phase, key, label, value)
select j.id, 1, c.key, c.label, case when random() < 0.1 then 'Check' else 'Normal' end
from service_jobs j
join clients cl on cl.id = j.client_id and cl.name in ('Harbor View Residences', 'Pinecrest Office Tower', 'Bayside Medical Clinic', 'Maple Court Subdivision')
cross join (values
  ('breaker_wires', 'Breaker Wires & Terminals'),
  ('compressor_body', 'Compressor Body'),
  ('coils_fins', 'Coils & Fins'),
  ('motor_fan', 'Motor & Fan'),
  ('pcb', 'PCB')
) as c(key, label)
where j.reference like 'JOB-CP-2026-%'
  and not exists (select 1 from checklist_lines x where x.job_id = j.id and x.key = c.key);

-- 12) Invoices: one per client
insert into invoices (number, client_id, issue_date, due_date, period_start, period_end, status)
select 'CP-INV-2026-' || lpad((200 + x.idx)::text, 4, '0'), x.id,
       date '2026-08-01', date '2026-08-15', date '2026-07-01', date '2026-07-31',
       (array['paid', 'unpaid', 'unpaid', 'draft'])[x.idx]
from (select c.id, row_number() over (order by c.name) as idx
      from clients c
      where c.name in ('Harbor View Residences', 'Pinecrest Office Tower', 'Bayside Medical Clinic', 'Maple Court Subdivision')) x
on conflict (number) do nothing;

insert into invoice_lines (invoice_id, service_type, equipment_label, visits, unit_rate, amount)
select i.id, 'Preventive maintenance', 'Split and packaged units', 2, 1500, 3000
from invoices i
where i.number like 'CP-INV-2026-02%'
  and not exists (select 1 from invoice_lines l where l.invoice_id = i.id);

-- Check counts
select 'clients' as t, count(*) from clients where name in ('Harbor View Residences', 'Pinecrest Office Tower', 'Bayside Medical Clinic', 'Maple Court Subdivision')
union all select 'equipment', count(*) from equipment e join clients c on c.id = e.client_id where c.name in ('Harbor View Residences', 'Pinecrest Office Tower', 'Bayside Medical Clinic', 'Maple Court Subdivision')
union all select 'visits', count(*) from service_visits where reference like 'CP-2026-%'
union all select 'jobs', count(*) from service_jobs where reference like 'JOB-CP-2026-%'
union all select 'invoices', count(*) from invoices where number like 'CP-INV-2026-02%';
