-- =============================================================================
-- GENERATED SAMPLE DATA for testing. Every row it creates is marked "GEN":
--   clients "GEN Client 01..10", visits "GEN-..." , invoices "GEN-INV-..."
-- Remove it all with 011_remove_generated_sample_data.sql.
-- Run after 001, 004, 006 (and 009 if you want the screenshot visit too).
-- Safe to run twice: skips rows that already exist.
-- =============================================================================

-- Brands
insert into equipment_brands (name)
select b.name from (values ('Daikin'), ('Carrier'), ('LG')) as b(name)
where not exists (select 1 from equipment_brands e where e.name = b.name);

-- Measurement fields (the checks used for readings)
insert into measurement_fields (section, name, unit, standard, sequence)
select m.section, m.name, m.unit, m.standard, m.seq from (values
  ('Electrical', 'Compressor amps', 'A',  '≤ 12.5', 10),
  ('Refrigerant', 'Suction pressure', 'psi', '110–125', 20),
  ('Air', 'Supply air temp', '°C', '10–14', 30),
  ('Electrical', 'Supply voltage', 'V', '220–240', 40)
) as m(section, name, unit, standard, seq)
where not exists (select 1 from measurement_fields x where x.name = m.name);

-- 10 clients, each with 3 rooms
insert into clients (name, address, email, phone)
select 'GEN Client ' || lpad(n::text, 2, '0'),
       'GEN Address ' || n || ', Metro Manila',
       'gen' || n || '@example.test',
       '0917-000-' || lpad(n::text, 4, '0')
from generate_series(1, 10) as n
where not exists (select 1 from clients c where c.name = 'GEN Client ' || lpad(n::text, 2, '0'));

insert into sublocations (client_id, name)
select c.id, 'GEN Room ' || r.letter
from clients c
cross join (values ('A'), ('B'), ('C')) as r(letter)
where c.name like 'GEN Client %'
  and not exists (select 1 from sublocations s where s.client_id = c.id and s.name = 'GEN Room ' || r.letter);

-- 2 units per room (60 units in total)
with units as (
  select s.id as sub_id, s.client_id,
         row_number() over (order by s.id, k.i) as n
  from sublocations s
  join clients c on c.id = s.client_id and c.name like 'GEN Client %'
  cross join generate_series(1, 2) as k(i)
)
insert into equipment (name, client_id, sublocation_id, brand_id, model, serial_number, install_year, status)
select
  'GEN Unit ' || u.n,
  u.client_id,
  u.sub_id,
  (select b.id from equipment_brands b
     where b.name = (array['Daikin', 'Carrier', 'LG'])[1 + (u.n % 3)]),
  'GEN-MODEL-' || (1 + (u.n % 5)),
  '…' || lpad((1000 + u.n)::text, 4, '0'),
  2015 + (u.n % 10)::int,
  'active'
from units u
where not exists (
  select 1 from equipment e
  where e.sublocation_id = u.sub_id and e.name = 'GEN Unit ' || u.n
);

-- 30 visits spread over the 10 clients
insert into service_visits (reference, client_id, visit_date, state, sublocation, technician_name)
select
  'GEN-' || to_char(date '2026-07-01' + (n * 2), 'MMDD') || '-' || lpad(n::text, 2, '0'),
  c.id,
  (date '2026-07-01' + (n * 2))::timestamptz,
  (array['draft', 'review', 'approved', 'invoiced'])[1 + (n % 4)],
  'GEN Room ' || (array['A', 'B', 'C'])[1 + (n % 3)],
  'Technician ' || (1 + (n % 4))
from generate_series(1, 30) as n
join clients c on c.name = 'GEN Client ' || lpad((1 + ((n - 1) % 10))::text, 2, '0')
on conflict (reference) do nothing;

-- Two jobs (one per unit) for each generated visit
with ranked as (
  select e.id as equipment_id, e.client_id,
         row_number() over (partition by e.client_id order by e.name, e.serial_number) as rn
  from equipment e
  join clients c on c.id = e.client_id and c.name like 'GEN Client %'
)
insert into service_jobs (reference, visit_id, equipment_id, client_id, visit_date, state)
select 'GEN-J-' || v.reference || '-' || r.rn, v.id, r.equipment_id, v.client_id, v.visit_date, 'draft'
from service_visits v
join ranked r on r.client_id = v.client_id and r.rn <= 2
where v.reference like 'GEN-%'
on conflict (reference) do nothing;

-- Readings for the 4 measurement fields, about 1 in 8 outside standard
insert into reading_lines (job_id, measurement_field_id, value, is_out_of_range)
select j.id, m.id,
       round((base + random() * span)::numeric, 1)::text,
       random() < 0.125
from service_jobs j
join measurement_fields m on m.name in ('Compressor amps', 'Suction pressure', 'Supply air temp', 'Supply voltage')
cross join lateral (select
    case m.name
      when 'Compressor amps'   then 6
      when 'Suction pressure'  then 105
      when 'Supply air temp'   then 9
      else 216 end as base,
    case m.name
      when 'Compressor amps'   then 6
      when 'Suction pressure'  then 25
      when 'Supply air temp'   then 8
      else 26 end as span) b
where j.reference like 'GEN-%'
  and not exists (select 1 from reading_lines x where x.job_id = j.id and x.measurement_field_id = m.id);

-- Inspection checklist: mostly Normal, some "Check"
insert into checklist_lines (job_id, phase, key, label, value)
select j.id, 1, c.key, c.label,
       case when random() < 0.1 then 'Check' else 'Normal' end
from service_jobs j
cross join (values
  ('breaker_wires', 'Breaker Wires & Terminals'),
  ('compressor_body', 'Compressor Body'),
  ('coils_fins', 'Coils & Fins'),
  ('motor_fan', 'Motor & Fan'),
  ('pcb', 'PCB')
) as c(key, label)
where j.reference like 'GEN-%'
  and not exists (select 1 from checklist_lines x where x.job_id = j.id and x.key = c.key);

-- One invoice per generated client, with one line each
insert into invoices (number, client_id, issue_date, due_date, period_start, period_end, status)
select 'GEN-INV-' || lpad(x.idx::text, 4, '0'), x.id,
       date '2026-08-01', date '2026-08-15', date '2026-07-01', date '2026-07-31',
       (array['paid', 'unpaid', 'draft'])[1 + (x.idx % 3)]
from (select c.id, row_number() over (order by c.name) as idx
      from clients c where c.name like 'GEN Client %') x
on conflict (number) do nothing;

insert into invoice_lines (invoice_id, service_type, equipment_label, visits, unit_rate, amount)
select i.id, 'Preventive maintenance', 'GEN units', 2, 1500, 3000
from invoices i
where i.number like 'GEN-INV-%'
  and not exists (select 1 from invoice_lines l where l.invoice_id = i.id);

-- Check counts
select 'clients' as t, count(*) from clients where name like 'GEN Client %'
union all select 'equipment', count(*) from equipment where name like 'GEN Unit %'
union all select 'visits', count(*) from service_visits where reference like 'GEN-%'
union all select 'jobs', count(*) from service_jobs where reference like 'GEN-%'
union all select 'readings', count(*) from reading_lines r join service_jobs j on j.id = r.job_id where j.reference like 'GEN-%'
union all select 'checklist', count(*) from checklist_lines c join service_jobs j on j.id = c.job_id where j.reference like 'GEN-%'
union all select 'invoices', count(*) from invoices where number like 'GEN-INV-%';
