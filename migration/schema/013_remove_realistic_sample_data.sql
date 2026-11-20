-- =============================================================================
-- Removes the realistic sample data from 012 (the four sample clients and
-- everything under them). Other data is not touched.
-- =============================================================================

delete from invoices where client_id in (
  select id from clients where name in ('Harbor View Residences', 'Pinecrest Office Tower', 'Bayside Medical Clinic', 'Maple Court Subdivision'));
delete from service_visits where client_id in (
  select id from clients where name in ('Harbor View Residences', 'Pinecrest Office Tower', 'Bayside Medical Clinic', 'Maple Court Subdivision'));
delete from service_jobs where client_id in (
  select id from clients where name in ('Harbor View Residences', 'Pinecrest Office Tower', 'Bayside Medical Clinic', 'Maple Court Subdivision'));
delete from equipment where client_id in (
  select id from clients where name in ('Harbor View Residences', 'Pinecrest Office Tower', 'Bayside Medical Clinic', 'Maple Court Subdivision'));
delete from clients where name in ('Harbor View Residences', 'Pinecrest Office Tower', 'Bayside Medical Clinic', 'Maple Court Subdivision');

-- Check: should be 0
select count(*) as remaining from clients
where name in ('Harbor View Residences', 'Pinecrest Office Tower', 'Bayside Medical Clinic', 'Maple Court Subdivision');
