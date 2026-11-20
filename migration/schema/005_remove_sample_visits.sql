-- Removes the sample visits and clients added by 004_sample_visits.sql.
delete from service_visits where reference in ('CP-2026-0807-JDC','CP-2026-0806-CR','CP-2026-0805-JDC','CP-2026-0804-MI');
delete from clients where name in ('Green Valley Residences','Sunrise Towers','Blue Ridge Mall','Casa Felicidad HOA')
  and not exists (select 1 from service_visits v where v.client_id = clients.id);
