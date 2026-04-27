create extension if not exists pgcrypto;

create table if not exists public.beta_interest (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  name text null,
  note text null,
  source text not null default 'dashboard',
  created_at timestamptz not null default now()
);

alter table public.beta_interest enable row level security;

drop policy if exists "beta_interest_insert" on public.beta_interest;
create policy "beta_interest_insert"
on public.beta_interest
for insert
to anon, authenticated
with check (true);
