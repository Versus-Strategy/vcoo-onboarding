-- =============================================================================
-- VCOO Onboarding — Supabase Schema
-- =============================================================================
-- Run this in the Supabase SQL Editor to create the required tables,
-- enable Realtime, and set up Row-Level Security (RLS).
-- =============================================================================

-- ═══ Extensions ═══
create extension if not exists "uuid-ossp";
create extension if not exists pgcrypto;

-- ═══ Tables ═══

create table if not exists vcoos (
    id          uuid primary key default gen_random_uuid(),
    name        text,
    created_at  timestamptz not null default now(),
    integrations text
);

create table if not exists provision_tokens (
    token       text primary key,
    vcoo_id     uuid not null references vcoos(id) on delete cascade,
    created_at  timestamptz not null default now(),
    expires_at  timestamptz,
    used        boolean not null default false
);
create index if not exists idx_provision_tokens_vcoo_id on provision_tokens(vcoo_id);

create table if not exists agents (
    id          uuid primary key default gen_random_uuid(),
    vcoo_id     uuid not null references vcoos(id) on delete cascade,
    info        text,
    last_seen   timestamptz default now(),
    status      text not null default 'offline',
    token_jti   text
);
create index if not exists idx_agents_vcoo_id on agents(vcoo_id);

create table if not exists commands (
    id          uuid primary key default gen_random_uuid(),
    agent_id    uuid not null references agents(id) on delete cascade,
    command     text not null,
    status      text not null default 'pending',
    result      text,
    created_at  timestamptz not null default now()
);
create index if not exists idx_commands_agent_id on commands(agent_id);

create table if not exists command_logs (
    id          uuid primary key default gen_random_uuid(),
    command_id  uuid not null references commands(id) on delete cascade,
    timestamp   timestamptz not null default now(),
    stream      text not null default 'stdout',
    chunk       text not null
);
create index if not exists idx_command_logs_cmd_id on command_logs(command_id);

-- Clients table (for client registration/login system)
create table if not exists clients (
    id          uuid primary key default gen_random_uuid(),
    email       text not null unique,
    password_hash text not null,
    name        text,
    vcoo_id     uuid references vcoos(id) on delete set null,
    created_at  timestamptz not null default now()
);
create index if not exists idx_clients_email on clients(email);
create index if not exists idx_clients_vcoo_id on clients(vcoo_id);

-- Enable realtime for clients table
alter publication supabase_realtime add table clients;

-- RLS for clients
alter table clients enable row level security;
-- Service role bypasses RLS; policies for authenticated users
drop policy if exists "Clients read own" on clients;
create policy "Clients read own" on clients
    for select
    to authenticated
    using (true);
drop policy if exists "Service insert clients" on clients;
create policy "Service insert clients" on clients
    for insert
    to service_role
    with check (true);

-- ═══ Realtime ═══
-- Enable realtime for tables the UI will subscribe to
alter publication supabase_realtime add table commands;
alter publication supabase_realtime add table command_logs;

-- ═══ RLS Policies ═══
-- Enable RLS on all tables
alter table vcoos            enable row level security;
alter table provision_tokens enable row level security;
alter table agents           enable row level security;
alter table commands         enable row level security;
alter table command_logs     enable row level security;

-- Service role bypass (Vercel functions use SERVICE_ROLE key)
-- The service_role bypasses RLS entirely; no policies needed for it.
-- Policies below apply to authenticated users (operator UI) and anon.

-- vcoos: operators can read their own VCOOs
drop policy if exists "Operators read own vcoos" on vcoos;
create policy "Operators read own vcoos" on vcoos
    for select
    to authenticated
    using (true);  -- refine with owner column later

-- provision_tokens: only service_role writes/reads
-- (no anon/authenticated policies — only service_role accesses this table)

-- agents: operators read agents for their VCOOs
drop policy if exists "Operators read agents" on agents;
create policy "Operators read agents" on agents
    for select
    to authenticated
    using (true);

-- commands: operators read/write commands for their VCOOs
drop policy if exists "Operators select commands" on commands;
create policy "Operators select commands" on commands
    for select to authenticated using (true);
drop policy if exists "Operators insert commands" on commands;
create policy "Operators insert commands" on commands
    for insert to authenticated with check (true);

-- command_logs: operators read logs
drop policy if exists "Operators select logs" on command_logs;
create policy "Operators select logs" on command_logs
    for select to authenticated using (true);

-- ═══ Helper: view for operator dashboard ═══
create or replace view vcoo_dashboard as
select
    v.id as vcoo_id,
    v.name,
    v.created_at,
    a.id as agent_id,
    a.status as agent_status,
    a.last_seen as agent_last_seen,
    (select count(*) from commands c where c.agent_id = a.id) as total_commands,
    (select count(*) from commands c where c.agent_id = a.id and c.status = 'pending') as pending_commands
from vcoos v
left join lateral (
    select * from agents where vcoo_id = v.id order by last_seen desc limit 1
) a on true;
