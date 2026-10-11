-- RepoGuardian X / Supabase starter schema
-- Run in Supabase SQL Editor. Enable Google provider in Authentication -> Providers.
create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.scan_reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  source_name text not null default 'Project',
  health_score integer not null check (health_score between 0 and 100),
  files_count integer not null default 0 check (files_count >= 0),
  lines_count integer not null default 0 check (lines_count >= 0),
  findings_count integer not null default 0 check (findings_count >= 0),
  high_count integer not null default 0 check (high_count >= 0),
  report_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists scan_reports_user_created_idx on public.scan_reports(user_id, created_at desc);

create table if not exists public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  provider text not null default 'stripe',
  provider_customer_id text unique,
  provider_subscription_id text unique,
  plan_key text not null check (plan_key in ('pro_monthly','studio_monthly')),
  status text not null default 'incomplete' check (status in ('incomplete','trialing','active','past_due','canceled','unpaid','incomplete_expired')),
  current_period_end timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists subscriptions_user_status_idx on public.subscriptions(user_id, status);

alter table public.profiles enable row level security;
alter table public.scan_reports enable row level security;
alter table public.subscriptions enable row level security;

drop policy if exists "profile owner can read" on public.profiles;
create policy "profile owner can read" on public.profiles for select to authenticated using (auth.uid() = id);
drop policy if exists "profile owner can insert" on public.profiles;
create policy "profile owner can insert" on public.profiles for insert to authenticated with check (auth.uid() = id);
drop policy if exists "profile owner can update" on public.profiles;
create policy "profile owner can update" on public.profiles for update to authenticated using (auth.uid() = id) with check (auth.uid() = id);

drop policy if exists "owners manage own scan reports" on public.scan_reports;
create policy "owners manage own scan reports" on public.scan_reports for all to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "owners read own subscriptions" on public.subscriptions;
create policy "owners read own subscriptions" on public.subscriptions for select to authenticated using (auth.uid() = user_id);
-- IMPORTANT: subscriptions are intentionally read-only to clients. Only a trusted server-side
-- Stripe webhook using the service role should insert/update subscription entitlements.

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id, display_name, avatar_url)
  values (new.id, coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name'), new.raw_user_meta_data->>'avatar_url')
  on conflict (id) do nothing;
  return new;
end;
$$;
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users for each row execute procedure public.handle_new_user();
