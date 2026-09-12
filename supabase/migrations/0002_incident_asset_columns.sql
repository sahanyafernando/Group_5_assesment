-- Adds asset-enrichment columns to incidents, populated by
-- app/services/asset_service.py (Step 6) and app/services/enrichment_pipeline.py
-- (Step 8). Safe to re-run: every statement is guarded.
--
-- Run this in the Supabase SQL editor after supabase/schema.sql.

alter table public.incidents
    add column if not exists road_class text,
    add column if not exists asset_types jsonb not null default '[]'::jsonb,
    add column if not exists nearest_facility text,
    add column if not exists facility_distance_m double precision,
    add column if not exists priority_factors jsonb;

create index if not exists idx_incidents_road_class
    on public.incidents(road_class);
