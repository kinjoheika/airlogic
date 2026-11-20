-- =============================================================================
-- Equipment from the Equipment Registry screenshot (3 units visible).
-- Creates missing clients, sublocations, brands, and the 3 units. Safe to run
-- twice. Serial numbers show only the last 4 digits in the registry, so they
-- are stored as "…XXXX" and should be corrected from the unit nameplate later.
-- Run in the Supabase SQL Editor after 001_airlogic_schema.sql.
-- =============================================================================

-- Clients
insert into clients (name)
select v.name from (values
  ('Green Valley Residences'),
  ('Metro Pacific Offices'),
  ('Blue Ridge Mall')
) as v(name)
where not exists (select 1 from clients c where c.name = v.name);

-- Sublocations
insert into sublocations (client_id, name)
select c.id, s.name
from (values
  ('Green Valley Residences', 'Compressor Room — Unit 4B'),
  ('Metro Pacific Offices',   'Server Room'),
  ('Blue Ridge Mall',         'Retail Unit 12')
) as s(client_name, name)
join clients c on c.name = s.client_name
where not exists (
  select 1 from sublocations x where x.client_id = c.id and x.name = s.name
);

-- Brands
insert into equipment_brands (name)
select b.name from (values ('Daikin'), ('Carrier')) as b(name)
where not exists (select 1 from equipment_brands e where e.name = b.name);

-- Equipment
insert into equipment
  (name, client_id, sublocation_id, brand_id, model, serial_number, install_year, status)
select
  e.name,
  c.id,
  sl.id,
  br.id,
  e.model,
  e.serial_number,
  e.install_year,
  e.status
from (values
  ('Daikin FTKF50TV',      'Green Valley Residences', 'Compressor Room — Unit 4B', 'Daikin',  'FTKF50TV',  '…5678', 2021, 'active'),
  ('Daikin VRV IV',        'Metro Pacific Offices',   'Server Room',              'Daikin',  'VRV IV',    '…3456', 2020, 'pending_decommission'),
  ('Carrier 38XHC009',     'Blue Ridge Mall',         'Retail Unit 12',           'Carrier', '38XHC009',  '…9012', null, 'pending_decommission')
) as e(name, client_name, sublocation_name, brand_name, model, serial_number, install_year, status)
join clients c       on c.name = e.client_name
join sublocations sl on sl.client_id = c.id and sl.name = e.sublocation_name
join equipment_brands br on br.name = e.brand_name
where not exists (
  select 1 from equipment x
  where x.client_id = c.id and x.sublocation_id = sl.id and x.name = e.name
);

-- Check: should list the 3 units
select e.name, c.name as client, sl.name as sublocation, e.serial_number, e.install_year, e.status
from equipment e
join clients c on c.id = e.client_id
left join sublocations sl on sl.id = e.sublocation_id
where e.serial_number in ('…5678', '…3456', '…9012')
order by c.name;
