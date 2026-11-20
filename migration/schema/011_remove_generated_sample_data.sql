-- =============================================================================
-- Removes everything 010_generated_sample_data.sql created ("GEN" rows only).
-- Real data is not touched. Order matters: visits and invoices first, then
-- equipment, rooms, and clients (child rows cascade).
-- =============================================================================

delete from invoices where number like 'GEN-INV-%';                    -- invoice_lines cascade
delete from service_visits where reference like 'GEN-%';               -- service_jobs, readings, checklists cascade
delete from equipment where name like 'GEN Unit %';
delete from sublocations where name like 'GEN Room %';
delete from clients where name like 'GEN Client %';

-- Check: all counts should be 0
select 'clients' as t, count(*) from clients where name like 'GEN Client %'
union all select 'equipment', count(*) from equipment where name like 'GEN Unit %'
union all select 'visits', count(*) from service_visits where reference like 'GEN-%'
union all select 'invoices', count(*) from invoices where number like 'GEN-INV-%';
