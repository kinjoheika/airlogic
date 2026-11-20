-- =============================================================================
-- Drops tables the website does not use. Permanent: the data in them is lost.
-- Keep: clients, equipment, service_visits, service_jobs, invoices,
-- invoice_lines, service_contracts, dispatch_requests, dispatch_zones,
-- part_requests, profiles, reading_lines, checklist_lines, files.
-- Order matters: child tables first, and the equipment.hp_id link is removed
-- before equipment_hp is dropped.
-- =============================================================================

drop table if exists job_history_tags;   -- links jobs to history_tags
drop table if exists history_tags;
drop table if exists job_revisions;
drop table if exists consumable_requests;
drop table if exists contract_equipment;

alter table equipment drop column if exists hp_id;   -- link to equipment_hp
drop table if exists equipment_hp;

-- Check: the remaining tables
select table_name from information_schema.tables
where table_schema = 'public' order by table_name;
