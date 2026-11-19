-- =============================================================================
-- TEST ONLY: lets the anonymous key read and write every AirLogic table.
-- Anyone who has the site's publishable key can read and change all records.
-- Run after 001_airlogic_schema.sql in a TEST project only. Safe to run twice.
-- Remove with 003_remove_test_open_access.sql before any real use.
-- =============================================================================

-- Table permissions (Supabase API roles need these in addition to policies)
grant usage on schema public to anon, authenticated;
grant select, insert, update, delete on all tables in schema public to anon, authenticated;

do $$
declare t text;
begin
  foreach t in array array[
    'profiles','clients','sublocations','equipment_brands','equipment_categories','equipment_hp',
    'history_tags','measurement_fields','equipment','service_contracts','contract_equipment',
    'dispatch_zones','dispatch_requests','service_visits','service_jobs','job_history_tags',
    'reading_lines','checklist_lines','job_revisions','part_requests','consumable_requests','files'
  ] loop
    execute format('drop policy if exists "test_anon_all" on %I', t);
    execute format('create policy "test_anon_all" on %I for all to anon using (true) with check (true)', t);
  end loop;
end $$;
