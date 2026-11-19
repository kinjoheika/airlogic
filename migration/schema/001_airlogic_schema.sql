-- =============================================================================
-- AirLogic on Supabase — DRAFT schema v1 (not yet run against any project)
-- Derived from addons/airlogic_core, airlogic_field_service, airlogic_dispatch.
-- Fresh start: no Odoo import. Run in a TEST Supabase project first.
-- =============================================================================

create extension if not exists "pgcrypto";

-- ---------- helpers ----------------------------------------------------------
create or replace function set_updated_at() returns trigger
language plpgsql as $$
begin new.updated_at = now(); return new; end $$;

-- ---------- users & roles ----------------------------------------------------
-- One profile per Supabase auth user, with one role.
create type airlogic_role as enum ('technician', 'operations_officer', 'manager', 'accounting', 'senior_technician');

create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text not null,
  role airlogic_role not null default 'technician',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create trigger profiles_updated before update on profiles
  for each row execute function set_updated_at();

-- ---------- clients & locations ---------------------------------------------
create table clients (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  address text,
  email text,
  phone text,
  zone_id uuid,                      -- FK added below (dispatch_zones)
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create trigger clients_updated before update on clients
  for each row execute function set_updated_at();

create table sublocations (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references clients(id) on delete cascade,
  name text not null,
  created_at timestamptz not null default now()
);

-- ---------- equipment catalogue ---------------------------------------------
create table equipment_brands (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
);
create table equipment_categories (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
);
create table equipment_hp (
  id uuid primary key default gen_random_uuid(),
  label text not null unique,       -- e.g. "1 HP", "2.5 HP"
);
create table history_tags (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
);
create table measurement_fields (
  id uuid primary key default gen_random_uuid(),
  section text,
  name text not null,
  unit text,
  standard text,
  sequence integer not null default 10,
);

-- ---------- equipment --------------------------------------------------------
create table equipment (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  client_id uuid not null references clients(id) on delete cascade,
  sublocation_id uuid references sublocations(id) on delete set null,
  brand_id uuid references equipment_brands(id),
  category_id uuid references equipment_categories(id),
  hp_id uuid references equipment_hp(id),
  model text,
  serial_number text,
  ipm_model text,
  pcb_model text,
  capacitor_brand text,
  capacitor_uf numeric,
  capacitor_volt numeric,
  refrigerant text,
  compressor_brand text,
  compressor_details text,
  install_year integer,
  active boolean not null default true,
  status text not null default 'active'
    check (status in ('active', 'pending_decommission', 'decommissioned')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  -- rule: one piece of equipment per sublocation (client + sublocation unique)
  unique (client_id, sublocation_id)
);
create trigger equipment_updated before update on equipment
  for each row execute function set_updated_at();

-- ---------- service contracts -----------------------------------------------
create table service_contracts (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  client_id uuid not null references clients(id) on delete cascade,
  billing_period text not null check (billing_period in ('monthly', 'quarterly', 'semi_annual', 'annual')),
  price numeric(14,2) not null,
  currency text not null default 'PHP',
  state text not null default 'draft' check (state in ('draft', 'active', 'paused', 'cancelled')),
  start_date date not null,
  next_billing_date date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create trigger contracts_updated before update on service_contracts
  for each row execute function set_updated_at();

create table contract_equipment (
  contract_id uuid references service_contracts(id) on delete cascade,
  equipment_id uuid references equipment(id) on delete cascade,
  primary key (contract_id, equipment_id)
);

-- ---------- dispatch ---------------------------------------------------------
create table dispatch_zones (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  city text,
  sequence integer not null default 10,
  active boolean not null default true,
);
alter table clients add constraint clients_zone_fk foreign key (zone_id) references dispatch_zones(id);

create table dispatch_requests (
  id uuid primary key default gen_random_uuid(),
  reference text unique,
  client_id uuid not null references clients(id) on delete cascade,
  equipment_id uuid references equipment(id) on delete set null,
  zone_id uuid references dispatch_zones(id),
  urgency text check (urgency in ('routine', 'rush', 'emergency')),
  source text check (source in ('call_in', 'subscription', 'staff', 'technician')),
  requested_date timestamptz,
  requested_by uuid references profiles(id),
  notes text,
  state text not null default 'requested'
    check (state in ('requested', 'suggested', 'confirmed', 'cancelled', 'fulfilled')),
  suggested_technician_id uuid references profiles(id),
  suggested_date timestamptz,
  suggested_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create trigger dispatch_updated before update on dispatch_requests
  for each row execute function set_updated_at();

-- ---------- service visits & jobs -------------------------------------------
create table service_visits (
  id uuid primary key default gen_random_uuid(),
  reference text unique,
  client_id uuid not null references clients(id),
  technician_id uuid references profiles(id),
  visit_date timestamptz not null default now(),
  state text not null default 'draft'
    check (state in ('draft', 'review', 'approved', 'rejected', 'invoiced', 'cancelled')),
  contract_id uuid references service_contracts(id),
  reviewed_by_id uuid references profiles(id),
  invoice_ref text,                  -- invoice reference (free text for now)
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create trigger visits_updated before update on service_visits
  for each row execute function set_updated_at();

create table service_jobs (
  id uuid primary key default gen_random_uuid(),
  reference text unique,
  visit_id uuid references service_visits(id) on delete cascade,
  equipment_id uuid references equipment(id),
  client_id uuid not null references clients(id),
  technician_id uuid references profiles(id),
  visit_date timestamptz,
  state text not null default 'draft',
  visit_state text,
  started_at timestamptz,
  tech_notes text,
  fieldpiece_pdf_path text,          -- stored in Storage, not in the row
  revision_open boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create trigger jobs_updated before update on service_jobs
  for each row execute function set_updated_at();

create table job_history_tags (
  job_id uuid references service_jobs(id) on delete cascade,
  tag_id uuid references history_tags(id) on delete cascade,
  primary key (job_id, tag_id)
);

create table reading_lines (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references service_jobs(id) on delete cascade,
  measurement_field_id uuid references measurement_fields(id),
  value text,
  is_out_of_range boolean not null default false,
);

create table checklist_lines (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references service_jobs(id) on delete cascade,
  phase integer,
  key text not null,
  label text,
  value text,
  note text,
);

create table job_revisions (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references service_jobs(id) on delete cascade,
  reason text,
  created_by uuid references profiles(id),
  created_at timestamptz not null default now(),
);

-- ---------- parts & consumables ---------------------------------------------
create table part_requests (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references service_jobs(id) on delete cascade,
  equipment_id uuid references equipment(id),
  part_name text not null,           -- free text for now; a parts catalogue table can replace it later
  quantity numeric not null default 1,
  requested_by uuid references profiles(id),
  state text not null default 'draft',
  purchase_order_ref text,
  created_at timestamptz not null default now()
);

create table consumable_requests (
  id uuid primary key default gen_random_uuid(),
  technician_id uuid references profiles(id),
  product_name text not null,
  quantity numeric not null default 1,
  state text not null default 'draft',
  purchase_order_ref text,
  created_at timestamptz not null default now()
);

-- ---------- files (Supabase Storage holds the bytes) -------------------------
create table files (
  id uuid primary key default gen_random_uuid(),
  record_table text not null,        -- e.g. 'service_jobs', 'service_contracts'
  record_id uuid not null,
  storage_path text not null,        -- path inside the Storage bucket
  filename text,
  mime_type text,
  uploaded_by uuid references profiles(id),
  created_at timestamptz not null default now()
);
create index files_record_idx on files (record_table, record_id);

-- ---------- indexes ----------------------------------------------------------
create index equipment_client_idx on equipment (client_id);
create index visits_client_idx on service_visits (client_id);
create index visits_state_idx on service_visits (state);
create index jobs_visit_idx on service_jobs (visit_id);
create index dispatch_state_idx on dispatch_requests (state);

-- ---------- row level security -----------------------------------------------
-- Draft policy: any signed-in user can read and write. Tighten per role before go-live.
do $$
declare t text;
begin
  foreach t in array array[
    'profiles','clients','sublocations','equipment_brands','equipment_categories','equipment_hp',
    'history_tags','measurement_fields','equipment','service_contracts','contract_equipment',
    'dispatch_zones','dispatch_requests','service_visits','service_jobs','job_history_tags',
    'reading_lines','checklist_lines','job_revisions','part_requests','consumable_requests','files'
  ] loop
    execute format('alter table %I enable row level security', t);
    execute format('create policy "signed_in_all" on %I for all to authenticated using (true) with check (true)', t);
  end loop;
end $$;
