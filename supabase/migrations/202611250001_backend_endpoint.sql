-- Publishes the laptop backend's current tunnel address so the website can
-- find it without manual setup. Anyone may read the address; only a caller
-- holding the publisher token (stored here as a SHA-256 hash) may change it.
begin;

create table if not exists public.backend_endpoint (
  id smallint primary key default 1 check (id = 1),
  url text check (url is null or url ~ '^https://[a-z0-9-]+(\.[a-z0-9-]+)*\.(trycloudflare\.com|lhr\.life|localhost\.run)$'),
  updated_at timestamptz not null default now()
);
alter table public.backend_endpoint enable row level security;
drop policy if exists backend_endpoint_read on public.backend_endpoint;
create policy backend_endpoint_read on public.backend_endpoint for select to anon, authenticated using (true);
revoke all on public.backend_endpoint from anon, authenticated;
grant select on public.backend_endpoint to anon, authenticated;

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;
create table if not exists private.backend_publisher (
  id smallint primary key default 1 check (id = 1),
  token_sha256 text not null check (token_sha256 ~ '^[a-f0-9]{64}$')
);
revoke all on private.backend_publisher from public, anon, authenticated;

create or replace function public.publish_backend_endpoint(p_url text, p_token text) returns boolean
language plpgsql security definer set search_path = '' as $$
declare expected text;
begin
  select token_sha256 into expected from private.backend_publisher where id = 1;
  if expected is null or p_token is null or length(p_token) < 32
     or encode(sha256(convert_to(p_token, 'UTF8')), 'hex') <> expected then
    return false;
  end if;
  insert into public.backend_endpoint (id, url, updated_at) values (1, p_url, now())
  on conflict (id) do update set url = excluded.url, updated_at = excluded.updated_at;
  return true;
end; $$;
revoke all on function public.publish_backend_endpoint(text, text) from public;
grant execute on function public.publish_backend_endpoint(text, text) to anon, authenticated;

-- After applying, register the publisher token once (replace the value with
-- the SHA-256 hex digest of NEW_X1_PUBLISH_TOKEN from the laptop's .env):
-- insert into private.backend_publisher (id, token_sha256) values (1, '<sha256 hex>')
--   on conflict (id) do update set token_sha256 = excluded.token_sha256;

commit;
