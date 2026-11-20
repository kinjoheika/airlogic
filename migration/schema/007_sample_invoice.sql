-- =============================================================================
-- SAMPLE DATA: invoice CP-INV-2026-0142 from the mockup. Run after 004 and 006.
-- Only the first two service lines were visible in the screenshot; add the
-- rest of the lines in the table below before relying on the total.
-- =============================================================================

insert into invoices (number, client_id, issue_date, due_date, period_start, period_end, status, from_address, vat_reg)
select 'CP-INV-2026-0142', c.id, '2026-08-07', '2026-08-14', '2026-08-01', '2026-08-07', 'unpaid',
       '123 EDSA Ave, Quezon City', '000-123-456-000'
from clients c
where c.name = 'Green Valley Residences'
on conflict (number) do nothing;

insert into invoice_lines (invoice_id, service_type, equipment_label, visits, unit_rate, amount)
select i.id, s.service_type, s.equipment_label, 1, s.rate, s.rate
from invoices i,
(values
  ('Preventive Maintenance', 'Daikin FTKF50TV · ···5678', 3500.00),
  ('Preventive Maintenance', 'LG S4-Q12JA3AA · ···1234', 3500.00)
) as s(service_type, equipment_label, rate)
where i.number = 'CP-INV-2026-0142'
  and not exists (select 1 from invoice_lines l where l.invoice_id = i.id);
