-- Migration: onboarding_state + commands extension
-- SPEC v2.0

-- 1. Nueva tabla: onboarding_state
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

-- Trigger: update timestamp on change
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

-- 2. Extender tabla commands
alter table commands add column if not exists step text;
alter table commands add column if not exists ttl_seconds integer default 300;
alter table commands add column if not exists sent_at timestamptz;
alter table commands add column if not exists acked boolean default false;

-- 3. Vista para dashboard (recrear si existe)
drop view if exists vcoo_dashboard;
create view vcoo_dashboard as
select
    v.id as vcoo_id,
    v.name,
    v.created_at,
    os.step,
    os.status as onboarding_status,
    os.modules,
    os.completed,
    os.errors,
    a.id as agent_id,
    a.status as agent_status,
    a.last_seen as agent_last_seen,
    (select count(*) from commands c where c.agent_id = a.id and c.status = 'pending') as pending_commands
from vcoos v
left join onboarding_state os on os.vcoo_id = v.id
left join lateral (
    select * from agents where vcoo_id = v.id order by last_seen desc limit 1
) a on true
order by v.created_at desc;

-- 4. Extender vcoos con modules (si no existe)
alter table vcoos add column if not exists modules jsonb default '["core"]';
