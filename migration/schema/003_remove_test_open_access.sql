-- =============================================================================
-- Removes the TEST-ONLY anonymous access added by 002_test_open_access.sql.
-- Run this before the site goes live with real data.
-- =============================================================================

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
  end loop;
end $$;
