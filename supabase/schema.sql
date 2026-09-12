-- Muthuwella Works Dispatch
-- Run this file in Supabase SQL Editor.

create extension if not exists pgcrypto;

create table if not exists public.raw_reports (
    id uuid primary key default gen_random_uuid(),
    source_file text not null default 'reports.csv',
    source_row_number integer not null,
    source_report_id text,
    channel text,
    received_at timestamptz,
    reporter_name text,
    reporter_contact text,
    location_text text,
    latitude double precision,
    longitude double precision,
    description text,
    category text,
    urgency text,
    photo text,
    source_status text,
    normalized_location text,
    location_confidence double precision,
    ai_analysis jsonb,
    ai_confidence double precision,
    needs_review boolean not null default false,
    raw_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (source_file, source_row_number)
);

-- Safe to re-run: adds columns if this table already existed without them.
alter table public.raw_reports
    add column if not exists location_confidence double precision;
alter table public.raw_reports
    add column if not exists incident_id uuid references public.incidents(id) on delete restrict;

create index if not exists idx_raw_reports_source_report_id
    on public.raw_reports(source_report_id);

create index if not exists idx_raw_reports_received_at
    on public.raw_reports(received_at);

create table if not exists public.assets (
    id uuid primary key default gen_random_uuid(),
    source_file text not null default 'assets.csv',
    source_row_number integer not null,
    road_name text,
    also_known_as text,
    road_class text,
    ward text,
    asset_type text,
    asset_id text,
    nearest_facility text,
    facility_distance_m double precision,
    raw_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (source_file, source_row_number)
);

create index if not exists idx_assets_road_name
    on public.assets(road_name);

create index if not exists idx_assets_asset_type
    on public.assets(asset_type);

create table if not exists public.jobs_history (
    id uuid primary key default gen_random_uuid(),
    source_file text not null default 'jobs-history.csv',
    source_row_number integer not null,
    source_job_id text,
    completed_date date,
    crew text,
    work_type text,
    road_name text,
    notes text,
    raw_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (source_file, source_row_number)
);

create index if not exists idx_jobs_history_road_name
    on public.jobs_history(road_name);

create index if not exists idx_jobs_history_completed_date
    on public.jobs_history(completed_date desc);

create table if not exists public.incidents (
    id uuid primary key default gen_random_uuid(),
    incident_code text unique,
    title text not null,
    summary text,
    canonical_road text,
    ward text,
    category text,
    work_type text,
    severity text,
    hazards jsonb not null default '[]'::jsonb,
    impact jsonb not null default '[]'::jsonb,
    report_count integer not null default 1 check (report_count >= 1),
    first_reported_at timestamptz,
    latest_reported_at timestamptz,
    priority_score integer not null default 0 check (priority_score between 0 and 100),
    priority_level text,
    priority_reasons jsonb not null default '[]'::jsonb,
    required_crew text,
    status text not null default 'New',
    classification_confidence double precision,
    location_confidence double precision,
    needs_review boolean not null default false,
    recent_job_warning jsonb,
    ai_metadata jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_incidents_priority
    on public.incidents(priority_score desc);

create index if not exists idx_incidents_required_crew
    on public.incidents(required_crew);

create index if not exists idx_incidents_status
    on public.incidents(status);

create table if not exists public.incident_reports (
    incident_id uuid not null references public.incidents(id) on delete cascade,
    report_id uuid not null references public.raw_reports(id) on delete restrict,
    match_confidence double precision,
    match_reason text,
    created_at timestamptz not null default now(),
    primary key (incident_id, report_id)
);

create table if not exists public.assignments (
    id uuid primary key default gen_random_uuid(),
    incident_id uuid not null references public.incidents(id) on delete cascade,
    crew text not null,
    status text not null default 'Assigned',
    assigned_by text default 'Maya',
    assigned_at timestamptz not null default now(),
    completed_at timestamptz,
    notes text,
    created_at timestamptz not null default now()
);

create index if not exists idx_assignments_incident
    on public.assignments(incident_id);

create table if not exists public.overrides (
    id uuid primary key default gen_random_uuid(),
    incident_id uuid not null references public.incidents(id) on delete cascade,
    field_name text not null,
    previous_value jsonb,
    new_value jsonb,
    reason text,
    changed_by text default 'Maya',
    changed_at timestamptz not null default now()
);

-- Keep updated_at useful.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_incidents_updated_at on public.incidents;
create trigger trg_incidents_updated_at
before update on public.incidents
for each row execute function public.set_updated_at();

-- RLS is enabled. This starter intentionally creates no anon/public write policy.
-- The FastAPI backend should use a server-side Supabase secret/service credential.
alter table public.raw_reports enable row level security;
alter table public.assets enable row level security;
alter table public.jobs_history enable row level security;
alter table public.incidents enable row level security;
alter table public.incident_reports enable row level security;
alter table public.assignments enable row level security;
alter table public.overrides enable row level security;
alter table public.raw_reports
    add column if not exists location_confidence double precision;
