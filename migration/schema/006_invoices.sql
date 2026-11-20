-- =============================================================================
-- Invoices: header table and line items. Run after 001 and 002.
-- =============================================================================

create table if not exists invoices (
  id uuid primary key default gen_random_uuid(),
  number text unique not null,
  client_id uuid not null references clients(id) on delete cascade,
  issue_date date not null,
  due_date date,
  period_start date,
  period_end date,
  status text not null default 'unpaid' check (status in ('draft', 'unpaid', 'paid')),
  from_name text not null default 'Standard Airlogic Service Co.',
  from_address text,
  vat_reg text,
  created_at timestamptz not null default now()
);

create table if not exists invoice_lines (
  id uuid primary key default gen_random_uuid(),
  invoice_id uuid not null references invoices(id) on delete cascade,
  service_type text not null,
  equipment_label text,
  visits integer not null default 1,
  unit_rate numeric(12,2) not null,
  amount numeric(12,2) not null
);

alter table invoices enable row level security;
alter table invoice_lines enable row level security;

drop policy if exists "signed_in_all" on invoices;
create policy "signed_in_all" on invoices for all to authenticated using (true) with check (true);
drop policy if exists "signed_in_all" on invoice_lines;
create policy "signed_in_all" on invoice_lines for all to authenticated using (true) with check (true);

grant select, insert, update, delete on invoices, invoice_lines to authenticated;
