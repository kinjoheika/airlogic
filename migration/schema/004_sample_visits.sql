-- =============================================================================
-- SAMPLE DATA: the four visits from the aircon-service mockup.
-- Adds two display columns to service_visits, then inserts sample clients and
-- visits. Safe to run twice. Delete later with 005_remove_sample_visits.sql.
-- =============================================================================

alter table service_visits add column if not exists technician_name text;
alter table service_visits add column if not exists sublocation text;

insert into clients (name)
select v.name from (values
  ('Green Valley Residences'),
  ('Sunrise Towers'),
  ('Blue Ridge Mall'),
  ('Casa Felicidad HOA')
) as v(name)
where not exists (select 1 from clients c where c.name = v.name);

insert into service_visits (reference, client_id, visit_date, state, sublocation, technician_name)
select s.reference, c.id, s.visit_date::timestamptz, s.state, s.sublocation, s.technician
from (values
  ('CP-2026-0807-JDC', 'Green Valley Residences', '2026-08-07', 'review',   'Compressor Room', 'Juan dela Cruz'),
  ('CP-2026-0806-CR',  'Sunrise Towers',          '2026-08-06', 'approved', 'Main AHU',        'Carlo Reyes'),
  ('CP-2026-0805-JDC', 'Blue Ridge Mall',         '2026-08-05', 'invoiced', 'Retail Unit 12',  'Juan dela Cruz'),
  ('CP-2026-0804-MI',  'Casa Felicidad HOA',      '2026-08-04', 'draft',    'Rooftop Deck',    'Mark Ignacio')
) as s(reference, client_name, visit_date, state, sublocation, technician)
join clients c on c.name = s.client_name
on conflict (reference) do nothing;
