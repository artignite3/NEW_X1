-- Apply to the selected Supabase project before enabling authenticated API access.
begin;
create table if not exists public.explanations (
  id text primary key check (id ~ '^[a-f0-9]{32}$'),
  user_id uuid not null references auth.users(id) on delete cascade,
  payload jsonb not null check (octet_length(payload::text) <= 524288),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null check (expires_at <= created_at + interval '1 hour')
);
create table if not exists public.saved_analyses (
  id text primary key check (id ~ '^[a-f0-9]{32}$'),
  user_id uuid not null references auth.users(id) on delete cascade,
  payload jsonb not null check (octet_length(payload::text) <= 524288),
  created_at timestamptz not null default now()
);
create index if not exists saved_analyses_owner_date on public.saved_analyses(user_id, created_at desc);
create index if not exists explanations_expiry on public.explanations(expires_at);
alter table public.explanations enable row level security;
alter table public.saved_analyses enable row level security;
create policy own_explanations_select on public.explanations for select to authenticated
  using (user_id = (select auth.uid()) and expires_at > now());
create policy own_explanations_insert on public.explanations for insert to authenticated
  with check (user_id = (select auth.uid()) and created_at between now() - interval '1 minute' and now() + interval '1 minute');
create policy own_analyses_select on public.saved_analyses for select to authenticated using (user_id = (select auth.uid()));
create policy own_analyses_insert on public.saved_analyses for insert to authenticated with check (user_id = (select auth.uid()));
create policy own_analyses_delete on public.saved_analyses for delete to authenticated using (user_id = (select auth.uid()));
grant select, insert on public.explanations to authenticated;
grant select, insert, delete on public.saved_analyses to authenticated;
revoke all on public.explanations, public.saved_analyses from anon;

create table if not exists public.generation_usage (
  user_id uuid not null references auth.users(id) on delete cascade,
  usage_day date not null,
  used integer not null default 0,
  primary key(user_id, usage_day)
);
alter table public.generation_usage enable row level security;
revoke all on public.generation_usage from anon, authenticated;
create or replace function public.consume_generation_quota() returns boolean
language plpgsql security definer set search_path = '' as $$
declare current_user_id uuid := auth.uid(); allowed integer;
begin
  if current_user_id is null then return false; end if;
  insert into public.generation_usage(user_id, usage_day, used)
  values (current_user_id, (now() at time zone 'UTC')::date, 1)
  on conflict (user_id, usage_day) do update set used = public.generation_usage.used + 1
    where public.generation_usage.used < 20
  returning used into allowed;
  return allowed is not null;
end; $$;
revoke all on function public.consume_generation_quota() from public, anon;
grant execute on function public.consume_generation_quota() to authenticated;
-- Schedule this through Supabase pg_cron or the deployment operator:
-- delete from public.explanations where expires_at < now();
-- delete from public.generation_usage where usage_day < current_date - 30;
commit;
