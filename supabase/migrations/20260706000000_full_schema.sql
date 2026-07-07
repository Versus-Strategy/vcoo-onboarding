-- =============================================================================
-- VCOO Onboarding — Supabase Schema (Full)
-- =============================================================================
-- Run this in the Supabase SQL Editor to create the required tables,
-- enable Realtime, and set up Row-Level Security (RLS).
-- Compatible with: Python models.py (SQLAlchemy)
-- =============================================================================

-- ═══ Extensions ═══
create extension if not exists "uuid-ossp";
create extension if not exists pgcrypto;

-- ═══ Tables ═══

-- 1. VCOOs
create table if not exists vcoos (
    id            uuid primary key default gen_random_uuid(),
    name          text,
    status        text not null default 'active',
    created_at    timestamptz not null default now(),
    integrations  text,
    modules       jsonb default '["core"]'
);

-- 2. Provision tokens
create table if not exists provision_tokens (
    token       text primary key,
    vcoo_id     uuid not null references vcoos(id) on delete cascade,
    created_at  timestamptz not null default now(),
    expires_at  timestamptz,
    used        boolean not null default false
);
create index if not exists idx_provision_tokens_vcoo_id on provision_tokens(vcoo_id);

-- 3. Agents
create table if not exists agents (
    id                uuid primary key default gen_random_uuid(),
    vcoo_id           uuid not null references vcoos(id) on delete cascade,
    info              text,
    last_seen         timestamptz default now(),
    status            text not null default 'offline',
    token_jti         text,
    encryption_key    text,
    health_payload    text,
    capabilities      text,
    template_version  varchar(32),
    supervisor_version varchar(32)
);
create index if not exists idx_agents_vcoo_id on agents(vcoo_id);

-- 4. Commands
create table if not exists commands (
    id          uuid primary key default gen_random_uuid(),
    agent_id    uuid not null references agents(id) on delete cascade,
    command     text not null,
    status      text not null default 'pending',
    result      text,
    created_at  timestamptz not null default now(),
    step        text,
    ttl_seconds integer default 300,
    sent_at     timestamptz,
    acked       boolean default false
);
create index if not exists idx_commands_agent_id on commands(agent_id);

-- 5. Command logs
create table if not exists command_logs (
    id          uuid primary key default gen_random_uuid(),
    command_id  uuid not null references commands(id) on delete cascade,
    timestamp   timestamptz not null default now(),
    stream      text not null default 'stdout',
    chunk       text not null
);
create index if not exists idx_command_logs_cmd_id on command_logs(command_id);

-- 6. Onboarding state
create table if not exists onboarding_state (
    vcoo_id     uuid primary key references vcoos(id) on delete cascade,
    step        text not null default 'bootstrap',
    status      text not null default 'in_progress',
    modules     jsonb not null default '[]',
    completed   jsonb not null default '[]',
    errors      jsonb not null default '[]',
    retry_count jsonb not null default '{}',
    updated_at  timestamptz not null default now()
);

-- 7. Clients
create table if not exists clients (
    id            uuid primary key default gen_random_uuid(),
    email         text not null unique,
    password_hash text not null,
    name          text,
    vcoo_id       uuid references vcoos(id) on delete set null,
    created_at    timestamptz not null default now()
);
create index if not exists idx_clients_email on clients(email);
create index if not exists idx_clients_vcoo_id on clients(vcoo_id);

-- 8. Operators (individual accounts, replaces shared DASHBOARD_PASSWORD)
create table if not exists operators (
    id            uuid primary key default gen_random_uuid(),
    email         text not null unique,
    password_hash text not null,
    name          text,
    created_at    timestamptz not null default now()
);
create index if not exists idx_operators_email on operators(email);

-- 9. Audit log (operator actions trail)
create table if not exists audit_log (
    id          uuid primary key default gen_random_uuid(),
    action      varchar(64) not null,
    actor_email varchar(255),
    actor_id    varchar(36),
    vcoo_id     uuid references vcoos(id) on delete set null,
    log_metadata text,
    created_at  timestamptz not null default now()
);
create index if not exists idx_audit_log_vcoo_id on audit_log(vcoo_id);
create index if not exists idx_audit_log_created_at on audit_log(created_at);

-- 10. Revoked tokens (JWT revocation)
create table if not exists revoked_tokens (
    jti         text primary key,
    token_type  varchar(16),
    revoked_by  varchar(36),
    created_at  timestamptz not null default now()
);

-- ═══ Triggers ═══

-- Update onboarding_state.updated_at on change
create or replace function update_onboarding_timestamp()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists trg_onboarding_timestamp on onboarding_state;
create trigger trg_onboarding_timestamp
    before update on onboarding_state
    for each row
    execute function update_onboarding_timestamp();

-- ═══ Realtime ═══
alter publication supabase_realtime add table commands;
alter publication supabase_realtime add table command_logs;
alter publication supabase_realtime add table clients;

-- ═══ RLS ═══
alter table vcoos            enable row level security;
alter table provision_tokens enable row level security;
alter table agents           enable row level security;
alter table commands         enable row level security;
alter table command_logs     enable row level security;
alter table onboarding_state enable row level security;
alter table clients          enable row level security;
alter table operators        enable row level security;
alter table audit_log        enable row level security;
alter table revoked_tokens   enable row level security;

-- Service role bypasses RLS (used by backend). Policies below for reference.

-- vcoos
drop policy if exists "Service all vcoos" on vcoos;
create policy "Service all vcoos" on vcoos for all to service_role using (true) with check (true);

-- provision_tokens: only service_role
drop policy if exists "Service all provision_tokens" on provision_tokens;
create policy "Service all provision_tokens" on provision_tokens for all to service_role using (true) with check (true);

-- agents
drop policy if exists "Service all agents" on agents;
create policy "Service all agents" on agents for all to service_role using (true) with check (true);

-- commands
drop policy if exists "Service all commands" on commands;
create policy "Service all commands" on commands for all to service_role using (true) with check (true);

-- command_logs
drop policy if exists "Service all command_logs" on command_logs;
create policy "Service all command_logs" on command_logs for all to service_role using (true) with check (true);

-- onboarding_state
drop policy if exists "Service all onboarding_state" on onboarding_state;
create policy "Service all onboarding_state" on onboarding_state for all to service_role using (true) with check (true);

-- clients
drop policy if exists "Service all clients" on clients;
create policy "Service all clients" on clients for all to service_role using (true) with check (true);

-- operators
drop policy if exists "Service all operators" on operators;
create policy "Service all operators" on operators for all to service_role using (true) with check (true);

-- audit_log
drop policy if exists "Service all audit_log" on audit_log;
create policy "Service all audit_log" on audit_log for all to service_role using (true) with check (true);

-- revoked_tokens
drop policy if exists "Service all revoked_tokens" on revoked_tokens;
create policy "Service all revoked_tokens" on revoked_tokens for all to service_role using (true) with check (true);

-- ═══ Views ═══
create or replace view vcoo_dashboard as
select
    v.id as vcoo_id,
    v.name,
    v.status,
    v.created_at,
    os.step,
    os.status as onboarding_status,
    os.modules,
    os.completed,
    os.errors,
    a.id as agent_id,
    a.status as agent_status,
    a.last_seen as agent_last_seen,
    a.template_version,
    a.supervisor_version,
    (select count(*) from commands c where c.agent_id = a.id and c.status = 'pending') as pending_commands
from vcoos v
left join onboarding_state os on os.vcoo_id = v.id
left join lateral (
    select * from agents where vcoo_id = v.id order by last_seen desc limit 1
) a on true
order by v.created_at desc;
