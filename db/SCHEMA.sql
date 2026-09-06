-- ===========================================================================
-- UDGAM.ai — SCHEMA.sql
-- SIH26033 · Opus planning-pass artifact (plan.md §9.1)
--
-- BINDING CONTRACT. The execution pass writes against these tables and columns
-- and does not invent new ones. If a column is genuinely missing, add it here
-- first and record the reason in docs/ASSUMPTIONS.md.
--
-- Covers every table in plan.md §7, plus the additions PRD §9 marks [+].
-- plan.md's `routes` and `empty_legs` survive as VIEWS over the unified
-- `transport_capacity` table (PRD R-7 / LG-1), so both documents are satisfied
-- literally.
--
-- Apply with:  python scripts/apply_schema.py
-- Idempotent: safe to re-run.
-- ===========================================================================

begin;

-- SQL-language function bodies are validated against referenced relations at
-- CREATE time. Section 2 defines helpers before section 3 creates their
-- tables, so defer that check for this transaction (this is what pg_dump
-- does). plpgsql bodies are deferred anyway; this covers the `language sql`
-- helpers.
set local check_function_bodies = off;

-- ---------------------------------------------------------------------------
-- Clean slate. A prior partial apply can leave enums half-created (the
-- Supabase SQL editor commits DDL that our BEGIN/COMMIT did not roll back),
-- which then fails re-apply with "invalid input value for enum ...". This
-- resets the public schema to empty first, so re-running SCHEMA.sql is always
-- safe on a database with no data yet.
--
-- WARNING: this DROPs every table in `public`. Safe now (fresh project); once
-- real data exists, migrate instead of re-running this file.
--
-- IT IS NO LONGER SAFE, AND THIS FILE IS NO LONGER A "JUST RE-RUN IT" SCRIPT.
-- The project has real data. Re-running the reset below destroyed the contents
-- of every public table several times (profiles, orders, products, crops,
-- prices, feedback -- auth.users survives, so logins outlive their own data),
-- because scripts/apply_schema.py advertises the file as idempotent while the
-- file opens by dropping the schema. Everything after this block genuinely is
-- idempotent: `create table if not exists`, `create or replace function`,
-- `drop policy if exists` + `create policy`, `add column if not exists`.
--
-- So the reset is now opt-in. Set SCHEMA_ALLOW_DESTRUCTIVE_RESET=1 to get the
-- old clean-slate behaviour on a genuinely empty project; without it, applying
-- this file is an additive migration and leaves data alone.
-- ---------------------------------------------------------------------------
do $$
begin
  if current_setting('udgam.allow_destructive_reset', true) = '1' then
    raise notice 'SCHEMA.sql: destructive reset ENABLED - dropping schema public';
    execute 'drop schema if exists public cascade';
    execute 'create schema public';
  end if;
end $$;
grant usage on schema public to postgres, anon, authenticated, service_role;
grant all on schema public to postgres, service_role;
alter default privileges in schema public
  grant all on tables to postgres, anon, authenticated, service_role;
alter default privileges in schema public
  grant all on sequences to postgres, anon, authenticated, service_role;
alter default privileges in schema public
  grant all on functions to postgres, anon, authenticated, service_role;

-- pgcrypto lives in the extensions schema on Supabase; gen_random_uuid() is
-- resolvable from public regardless.
create extension if not exists "pgcrypto" with schema extensions;

-- ===========================================================================
-- 1. ENUMS
-- Postgres has no CREATE TYPE ... IF NOT EXISTS, hence the guard blocks.
-- ===========================================================================

do $$ begin
  create type user_role as enum ('farmer','buyer','transporter');
exception when duplicate_object then null; end $$;

do $$ begin
  create type verification_status as enum ('self_declared','document_submitted','verified');
exception when duplicate_object then null; end $$;

do $$ begin
  create type onboarding_status as enum ('invited','active','suspended');
exception when duplicate_object then null; end $$;

do $$ begin
  create type buyer_type as enum ('individual','bulk');
exception when duplicate_object then null; end $$;

do $$ begin
  create type quality_grade as enum ('A','B','C');
exception when duplicate_object then null; end $$;

-- How a value was produced. Returned to the client as `method` on every AI
-- payload. PRD §7.1 (R-9): four of the six capabilities are deterministic
-- algorithms, and the UI says so.
do $$ begin
  create type method_label as enum ('REAL','HEURISTIC','ALGORITHMIC','SYNTHETIC');
exception when duplicate_object then null; end $$;

do $$ begin
  create type product_status as enum ('draft','active','reserved','sold','expired','withdrawn');
exception when duplicate_object then null; end $$;

do $$ begin
  create type request_status as enum ('open','partially_fulfilled','fulfilled','cancelled','expired');
exception when duplicate_object then null; end $$;

-- PRD §8. The spine of the product.
do $$ begin
  create type order_status as enum (
    'DRAFT','PLACED','ACCEPTED','PAYMENT_HELD','LOGISTICS_ASSIGNED',
    'PICKED_UP','IN_TRANSIT','DELIVERED','CLOSED','CANCELLED','DISPUTED'
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type escrow_status as enum ('none','held','released','refunded');
exception when duplicate_object then null; end $$;

-- PRD §6.6 (R-8): resolves who picks the carrier.
do $$ begin
  create type arranged_by as enum ('farmer','buyer');
exception when duplicate_object then null; end $$;

do $$ begin
  create type capacity_type as enum ('scheduled_route','empty_leg','on_demand');
exception when duplicate_object then null; end $$;

do $$ begin
  create type capacity_status as enum ('open','partially_booked','full','departed','completed','cancelled');
exception when duplicate_object then null; end $$;

do $$ begin
  create type consolidation_status as enum ('pending','accepted','rejected','cancelled');
exception when duplicate_object then null; end $$;

do $$ begin
  create type shipment_status as enum ('created','assigned','picked_up','in_transit','delivered','cancelled');
exception when duplicate_object then null; end $$;

do $$ begin
  create type booking_status as enum ('requested','confirmed','active','completed','cancelled');
exception when duplicate_object then null; end $$;

do $$ begin
  create type payment_status as enum ('created','held','released','refunded','failed');
exception when duplicate_object then null; end $$;

do $$ begin
  create type aggregation_status as enum ('suggested','accepted','rejected','expired');
exception when duplicate_object then null; end $$;


-- ===========================================================================
-- 2. HELPER FUNCTIONS
-- Marked STABLE + SECURITY DEFINER so RLS policies can call them without
-- recursing into the very policies they are being evaluated for.
-- ===========================================================================

create or replace function public.jwt_role()
returns user_role language sql stable security definer set search_path = public as $$
  select role from public.profiles where id = auth.uid();
$$;

create or replace function public.is_fpo(uid uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.fpos where profile_id = uid);
$$;

-- Farmers whose produce a given FPO may READ (never write) — PRD §4.1 point 4.
create or replace function public.fpo_member_ids(fpo uuid)
returns setof uuid language sql stable security definer set search_path = public as $$
  select profile_id from public.farmer_profiles where fpo_id = fpo;
$$;

-- True when `uid` is the buyer, the sole farmer, a line-item farmer, or the
-- assigned transporter on the order. The single predicate every
-- order-adjacent policy reuses.
--
-- LANGUAGE plpgsql, not sql: this function queries `orders` (the very table
-- it secures the SELECT policy for), and PostgREST always requests
-- `Prefer: return=representation` on inserts. Under RLS, an INSERT ...
-- RETURNING re-checks the SELECT policy against the just-inserted row in the
-- same statement. A `language sql` function is inlined by the planner, and
-- inlining a self-referential subquery into that combined INSERT-RETURNING
-- plan made it evaluate as if the new row didn't exist yet -- every buyer's
-- very first order failed with "new row violates row-level security policy
-- for table orders" even though buyer_id = auth.uid() was correct. plpgsql
-- functions are opaque to the planner (never inlined), which is the
-- documented fix for this class of bug; the logic and security model here
-- are unchanged.
create or replace function public.is_order_participant(order_uuid uuid, uid uuid)
returns boolean language plpgsql stable security definer set search_path = public as $$
begin
  return exists (
    select 1 from public.orders o where o.id = order_uuid
      and (o.buyer_id = uid or o.farmer_id = uid)
  ) or exists (
    select 1 from public.order_items oi
    where oi.order_id = order_uuid and oi.farmer_id = uid
  ) or exists (
    select 1 from public.shipments s
    where s.order_id = order_uuid and s.transporter_id = uid
  );
end;
$$;

-- True when `uid` has a line item in the aggregation. SECURITY DEFINER on
-- purpose: aggregations_select needs to consult aggregation_items and
-- agg_items_select needs to consult aggregations, which is a mutual RLS
-- reference and made Postgres raise 42P17 "infinite recursion detected in
-- policy" on every select/update/delete of both tables. Routing one direction
-- through a definer function breaks the cycle, exactly as
-- is_order_participant does for the order-adjacent policies.
create or replace function public.is_aggregation_participant(agg_uuid uuid, uid uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.aggregation_items ai
    where ai.aggregation_id = agg_uuid and ai.farmer_id = uid
  );
$$;

-- True when `uid` owns the aggregation (is its buyer). Definer for the same reason.
create or replace function public.is_aggregation_buyer(agg_uuid uuid, uid uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.aggregations a
    where a.id = agg_uuid and a.buyer_id = uid
  );
$$;

-- True when `uid` is a transporter holding a live offer to carry this shipment.
-- This is what lets an as-yet-unassigned shipment be claimed: shipments_update
-- keys off transporter_id, which is still null before anyone accepts, so
-- without this no transporter could ever take the job. Scoped to a *pending*
-- offer addressed to that transporter, so it grants nothing to anyone who was
-- not actually asked. Definer for the same cycle-breaking reason as above.
create or replace function public.has_open_transport_offer(ship_uuid uuid, uid uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1
    from public.consolidation_requests cr
    join public.transport_capacity c on c.id = cr.capacity_id
    where cr.shipment_id = ship_uuid
      and cr.status = 'pending'
      and (cr.expires_at is null or cr.expires_at > now())
      and c.transporter_id = uid
  );
$$;

-- Same grant, keyed by order: a transporter deciding whether to take a job has
-- to be able to READ that job first. Before they accept they are not yet an
-- order participant, so is_order_participant is false and the order and its
-- shipment are invisible to them -- which would mean answering "will you carry
-- this?" with no idea what "this" is. Scoped to a live offer addressed to
-- them, and it lapses the moment the offer is answered or expires.
create or replace function public.has_open_transport_offer_on_order(order_uuid uuid, uid uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1
    from public.consolidation_requests cr
    join public.transport_capacity c on c.id = cr.capacity_id
    where cr.order_id = order_uuid
      and cr.status = 'pending'
      and (cr.expires_at is null or cr.expires_at > now())
      and c.transporter_id = uid
  );
$$;

create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;


-- ===========================================================================
-- 3. IDENTITY
-- ===========================================================================

create table if not exists public.profiles (
  id                  uuid primary key references auth.users(id) on delete cascade,
  role                user_role           not null,
  full_name           text                not null,
  phone               text,
  email               text,
  preferred_language  text                not null default 'en'
                        check (preferred_language in ('en','hi','mr')),
  verification_status verification_status not null default 'self_declared',
  -- PRD §4.3 (R-4): unlocks creating storage_listings without a fourth role.
  is_storage_provider boolean             not null default false,
  avg_rating          numeric(3,2)        not null default 0
                        check (avg_rating >= 0 and avg_rating <= 5),
  rating_count        integer             not null default 0,
  address_line        text,
  district            text,
  state               text,
  pincode             text,
  lat                 double precision,
  lon                 double precision,
  -- 5-char geohash ≈ 4.9 km cell. Cheap proximity prefilter for AI-5 matching
  -- without PostGIS.
  geohash5            text,
  avatar_path         text,
  created_at          timestamptz         not null default now(),
  updated_at          timestamptz         not null default now()
);

create index if not exists idx_profiles_role_district on public.profiles(role, district);
create index if not exists idx_profiles_geohash      on public.profiles(geohash5);

create table if not exists public.kyc_documents (
  id                uuid primary key default gen_random_uuid(),
  profile_id        uuid not null references public.profiles(id) on delete cascade,
  doc_type          text not null
                      check (doc_type in ('aadhaar_last4','land_record','gstin','driving_licence','vehicle_rc')),
  -- Only the masked form is stored. v1 does format validation only
  -- (PRD §4.4 / R-5); real verification is a roadmap integration.
  doc_number_masked text not null,
  format_valid      boolean not null default false,
  submitted_at      timestamptz not null default now(),
  unique (profile_id, doc_type)
);

-- FPO account. A profile is an FPO iff it has a row here. Role stays 'farmer'
-- (plan.md §4.1: FPO is a Farmer login with one added capability).
create table if not exists public.fpos (
  profile_id      uuid primary key references public.profiles(id) on delete cascade,
  fpo_name        text not null,
  registration_no text,
  district        text,
  state           text,
  created_at      timestamptz not null default now()
);

create table if not exists public.farmer_profiles (
  profile_id        uuid primary key references public.profiles(id) on delete cascade,
  fpo_id            uuid references public.fpos(profile_id) on delete set null,
  created_by_fpo    boolean not null default false,
  -- PRD §4.1 (R-3): FPO-created farmers land as 'invited' with no usable
  -- password and activate themselves. The FPO never holds their credentials.
  onboarding_status onboarding_status not null default 'active',
  land_area_acres   numeric(8,2),
  primary_crop_ids  uuid[] not null default '{}',
  created_at        timestamptz not null default now()
);

create index if not exists idx_farmer_fpo    on public.farmer_profiles(fpo_id);
create index if not exists idx_farmer_crops  on public.farmer_profiles using gin (primary_crop_ids);

create table if not exists public.buyer_profiles (
  profile_id        uuid primary key references public.profiles(id) on delete cascade,
  buyer_type        buyer_type not null default 'individual',
  business_name     text,
  gstin             text,
  delivery_pincode  text,
  created_at        timestamptz not null default now()
);

create table if not exists public.transporter_profiles (
  profile_id            uuid primary key references public.profiles(id) on delete cascade,
  vehicle_type          text,
  vehicle_reg_no        text,
  capacity_kg           numeric(10,2) not null default 0,
  licence_no            text,
  service_districts     text[] not null default '{}',
  base_rate_paise_per_km integer not null default 0,
  created_at            timestamptz not null default now()
);


-- ===========================================================================
-- 4. REFERENCE DATA
-- ===========================================================================

-- PRD §9: free-text crop names destroy matching and price joins.
create table if not exists public.crops (
  id                     uuid primary key default gen_random_uuid(),
  code                   text unique not null,
  name_en                text not null,
  name_hi                text not null,
  name_mr                text not null,
  category               text,
  default_shelf_life_days integer not null default 7,
  created_at             timestamptz not null default now()
);

create table if not exists public.locations (
  id           uuid primary key default gen_random_uuid(),
  owner_id     uuid references public.profiles(id) on delete cascade,
  label        text,
  address_line text,
  district     text,
  state        text,
  pincode      text,
  lat          double precision,
  lon          double precision,
  geohash5     text,
  created_at   timestamptz not null default now()
);

create index if not exists idx_locations_owner on public.locations(owner_id);


-- ===========================================================================
-- 5. MARKETPLACE
-- ===========================================================================

create table if not exists public.products (
  id                    uuid primary key default gen_random_uuid(),
  farmer_id             uuid not null references public.profiles(id) on delete cascade,
  -- Set when an FPO lists on behalf of an invited-but-inactive farmer. Drives
  -- the "listed by FPO" badge. Provenance stays visible (PRD §4.1 point 5).
  listed_by_fpo_id      uuid references public.fpos(profile_id) on delete set null,
  crop_id               uuid not null references public.crops(id),
  quantity_kg           numeric(10,2) not null check (quantity_kg > 0),
  available_quantity_kg numeric(10,2) not null check (available_quantity_kg >= 0),
  asking_price_paise    integer not null check (asking_price_paise > 0),  -- per kg
  grade                 quality_grade,
  grade_confidence      numeric(4,3),
  grade_method          method_label,
  harvest_date          date,
  available_until       date,
  status                product_status not null default 'draft',
  description           text,
  photo_path            text,
  location_id           uuid references public.locations(id) on delete set null,
  district              text,
  geohash5              text,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

create index if not exists idx_products_discovery on public.products(crop_id, status, geohash5);
create index if not exists idx_products_farmer    on public.products(farmer_id, status);

create table if not exists public.quality_grades (
  id           uuid primary key default gen_random_uuid(),
  product_id   uuid not null references public.products(id) on delete cascade,
  photo_path   text not null,
  grade        quality_grade not null,
  confidence   numeric(4,3) not null,
  method       method_label not null default 'HEURISTIC',
  -- {mean_hue, mean_sat, mean_val, colour_variance, laplacian_blur,
  --  blemish_ratio, size_consistency} — the visible feature breakdown the
  --  demo shows alongside the grade (PRD §13 step 2).
  features     jsonb not null default '{}'::jsonb,
  model_run_id uuid,
  created_at   timestamptz not null default now()
);

create index if not exists idx_quality_product on public.quality_grades(product_id);

create table if not exists public.buyer_requests (
  id                 uuid primary key default gen_random_uuid(),
  buyer_id           uuid not null references public.profiles(id) on delete cascade,
  crop_id            uuid not null references public.crops(id),
  quantity_kg        numeric(10,2) not null check (quantity_kg > 0),
  min_grade          quality_grade not null default 'C',
  target_price_paise integer check (target_price_paise > 0),
  needed_by          date,
  delivery_pincode   text,
  delivery_district  text,
  delivery_lat       double precision,
  delivery_lon       double precision,
  geohash5           text,
  status             request_status not null default 'open',
  notes              text,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

create index if not exists idx_requests_discovery on public.buyer_requests(crop_id, status, needed_by);
create index if not exists idx_requests_buyer     on public.buyer_requests(buyer_id, status);


-- ===========================================================================
-- 6. AGGREGATION  (AI-5 aggregation mode → bulk buyer, PRD B-7)
-- ===========================================================================

create table if not exists public.aggregations (
  id                   uuid primary key default gen_random_uuid(),
  buyer_request_id     uuid not null references public.buyer_requests(id) on delete cascade,
  buyer_id             uuid not null references public.profiles(id) on delete cascade,
  status               aggregation_status not null default 'suggested',
  total_quantity_kg    numeric(10,2) not null default 0,
  combined_price_paise bigint not null default 0,
  transport_cost_paise bigint not null default 0,
  -- Set when the group mixes grades; surfaced as the grade-consistency warning.
  grade_variance_warning boolean not null default false,
  match_score          numeric(5,4),
  method               method_label not null default 'ALGORITHMIC',
  created_at           timestamptz not null default now()
);

create table if not exists public.aggregation_items (
  id             uuid primary key default gen_random_uuid(),
  aggregation_id uuid not null references public.aggregations(id) on delete cascade,
  product_id     uuid not null references public.products(id) on delete cascade,
  farmer_id      uuid not null references public.profiles(id) on delete cascade,
  quantity_kg    numeric(10,2) not null check (quantity_kg > 0),
  unit_price_paise integer not null,
  -- Per-farmer consent. aggregations.status describes the group as a whole, so
  -- it cannot record that farmer A agreed while farmer B has not yet answered.
  -- Inventory is reserved only once a line reads 'accepted' (PRD B-7).
  consent_status aggregation_status not null default 'suggested',
  consent_at     timestamptz,
  unique (aggregation_id, product_id)
);

-- Additive for databases created before consent tracking existed.
alter table public.aggregation_items
  add column if not exists consent_status aggregation_status not null default 'suggested';
alter table public.aggregation_items
  add column if not exists consent_at timestamptz;


-- ===========================================================================
-- 7. ORDERS  (state machine: PRD §8)
-- ===========================================================================

create table if not exists public.orders (
  id                    uuid primary key default gen_random_uuid(),
  order_no              text unique not null,
  buyer_id              uuid not null references public.profiles(id) on delete restrict,
  -- Sole farmer on a single-source order; NULL when the order is aggregated
  -- across several farmers (participants then come from order_items).
  farmer_id             uuid references public.profiles(id) on delete restrict,
  aggregation_id        uuid references public.aggregations(id) on delete set null,
  buyer_request_id      uuid references public.buyer_requests(id) on delete set null,
  status                order_status not null default 'DRAFT',
  logistics_arranged_by arranged_by not null default 'farmer',

  -- Money. Integer paise throughout; never float. The price breakdown screen
  -- (F-12) renders these fields directly — that is what makes the
  -- "transparent pricing" claim literally true on screen (PRD §3.1).
  subtotal_paise                    bigint not null default 0,
  transport_cost_paise              bigint not null default 0,
  platform_fee_paise                bigint not null default 0,  -- 2% of subtotal, buyer pays
  logistics_facilitation_fee_paise  bigint not null default 0,  -- 1% off transporter payout
  buyer_total_paise                 bigint not null default 0,
  farmer_payout_paise               bigint not null default 0,
  -- Static comparator for the "farmer share of consumer rupee" metric (§12).
  traditional_chain_price_paise     bigint,

  escrow_status      escrow_status not null default 'none',
  -- PRD §8 / R-13: proof of delivery without an admin. Hash only, never the
  -- plaintext OTP.
  delivery_otp_hash  text,
  delivery_location_id uuid references public.locations(id) on delete set null,
  delivery_pincode   text,
  needed_by          date,
  placed_at          timestamptz,
  accepted_at        timestamptz,
  delivered_at       timestamptz,
  closed_at          timestamptz,
  cancelled_reason   text,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

create index if not exists idx_orders_buyer  on public.orders(buyer_id, status);
create index if not exists idx_orders_farmer on public.orders(farmer_id, status);

create table if not exists public.order_items (
  id               uuid primary key default gen_random_uuid(),
  order_id         uuid not null references public.orders(id) on delete cascade,
  product_id       uuid not null references public.products(id) on delete restrict,
  farmer_id        uuid not null references public.profiles(id) on delete restrict,
  crop_id          uuid not null references public.crops(id),
  quantity_kg      numeric(10,2) not null check (quantity_kg > 0),
  unit_price_paise integer not null check (unit_price_paise > 0),
  line_total_paise bigint not null,
  grade            quality_grade,
  -- Buyer-confirmed grade at delivery (PRD §2.1 quality assessment row).
  confirmed_grade  quality_grade
);

create index if not exists idx_order_items_order  on public.order_items(order_id);
create index if not exists idx_order_items_farmer on public.order_items(farmer_id);

-- Satisfies the auditability NFR (plan.md §13, PRD §11). Surfaced in the UI
-- as the tracking timeline. Append-only: no UPDATE or DELETE policy exists.
create table if not exists public.order_status_history (
  id           uuid primary key default gen_random_uuid(),
  order_id     uuid not null references public.orders(id) on delete cascade,
  from_status  order_status,
  to_status    order_status not null,
  actor_id     uuid references public.profiles(id) on delete set null,
  actor_role   user_role,
  note         text,
  created_at   timestamptz not null default now()
);

create index if not exists idx_status_history_order on public.order_status_history(order_id, created_at);


-- ===========================================================================
-- 8. LOGISTICS
-- LG-1 (PRD R-7): F-7 "get transportation", T-5 "empty leg", T-6 "scheduled
-- route" are three views of one object. One table, three capacity_types.
-- ===========================================================================

create table if not exists public.transport_capacity (
  id                  uuid primary key default gen_random_uuid(),
  transporter_id      uuid not null references public.profiles(id) on delete cascade,
  capacity_type       capacity_type not null,
  origin_location_id  uuid references public.locations(id) on delete set null,
  dest_location_id    uuid references public.locations(id) on delete set null,
  origin_district     text,
  dest_district       text,
  origin_lat          double precision,
  origin_lon          double precision,
  dest_lat            double precision,
  dest_lon            double precision,
  depart_at           timestamptz,
  arrive_estimate_at  timestamptz,
  total_capacity_kg   numeric(10,2) not null check (total_capacity_kg > 0),
  available_capacity_kg numeric(10,2) not null check (available_capacity_kg >= 0),
  price_paise_per_kg  integer not null default 0,
  price_paise_per_km  integer not null default 0,
  -- Empty legs are posted at a discount to fill otherwise-wasted capacity.
  discount_pct        numeric(5,2) not null default 0,
  status              capacity_status not null default 'open',
  notes               text,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

create index if not exists idx_capacity_search on public.transport_capacity(capacity_type, status, depart_at);
create index if not exists idx_capacity_owner  on public.transport_capacity(transporter_id, status);

-- plan.md §7 names `routes` and `empty_legs`. They survive as views so both
-- documents are satisfied without three near-identical CRUD flows.
create or replace view public.routes as
  select * from public.transport_capacity where capacity_type = 'scheduled_route';

create or replace view public.empty_legs as
  select * from public.transport_capacity where capacity_type = 'empty_leg';

-- LG-2: Farmer F-10 and Transporter T-7 are two sides of one row.
create table if not exists public.consolidation_requests (
  id                 uuid primary key default gen_random_uuid(),
  capacity_id        uuid not null references public.transport_capacity(id) on delete cascade,
  requester_id       uuid not null references public.profiles(id) on delete cascade,
  requester_role     user_role not null,
  order_id           uuid references public.orders(id) on delete set null,
  product_id         uuid references public.products(id) on delete set null,
  quantity_kg        numeric(10,2) not null check (quantity_kg > 0),
  pickup_location_id uuid references public.locations(id) on delete set null,
  drop_location_id   uuid references public.locations(id) on delete set null,
  status             consolidation_status not null default 'pending',
  response_note      text,
  responded_at       timestamptz,
  created_at         timestamptz not null default now()
);

create index if not exists idx_consolidation_capacity  on public.consolidation_requests(capacity_id, status);
create index if not exists idx_consolidation_requester on public.consolidation_requests(requester_id, status);


create table if not exists public.shipments (
  id                    uuid primary key default gen_random_uuid(),
  order_id              uuid not null references public.orders(id) on delete cascade,
  transporter_id        uuid references public.profiles(id) on delete set null,
  capacity_id           uuid references public.transport_capacity(id) on delete set null,
  status                shipment_status not null default 'created',
  -- Farmer-side handover code, mirroring the buyer-side delivery OTP.
  pickup_otp_hash       text,
  pickup_location_id    uuid references public.locations(id) on delete set null,
  drop_location_id      uuid references public.locations(id) on delete set null,
  planned_distance_km   numeric(8,2),
  actual_distance_km    numeric(8,2),
  eta_at                timestamptz,
  picked_up_at          timestamptz,
  delivered_at          timestamptz,
  earnings_paise        bigint not null default 0,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

create index if not exists idx_shipments_order       on public.shipments(order_id);
create index if not exists idx_shipments_transporter on public.shipments(transporter_id, status);

-- Additive for databases created before the shipment carried its own logistics
-- detail. A shipment is created (status 'created') by whoever `orders.
-- logistics_arranged_by` names, BEFORE any transporter exists, so a
-- transporter can see what they are being asked to carry before accepting.
-- Pickup/drop are deliberately NOT derived from the farmer's and buyer's
-- profile districts: produce may sit at a different store, and a buyer may
-- want delivery to a warehouse.
alter table public.shipments
  add column if not exists cargo_kg              numeric(10,2);
alter table public.shipments
  add column if not exists pickup_address        text;
alter table public.shipments
  add column if not exists pickup_contact_name   text;
alter table public.shipments
  add column if not exists pickup_contact_phone  text;
alter table public.shipments
  add column if not exists pickup_from           timestamptz;
alter table public.shipments
  add column if not exists pickup_until          timestamptz;
alter table public.shipments
  add column if not exists pickup_instructions   text;
alter table public.shipments
  add column if not exists drop_address          text;
alter table public.shipments
  add column if not exists drop_contact_name     text;
alter table public.shipments
  add column if not exists drop_contact_phone    text;
alter table public.shipments
  add column if not exists deliver_by            timestamptz;
alter table public.shipments
  add column if not exists drop_instructions     text;
-- Estimated at request time from distance x capacity pricing; the final figure
-- is `earnings_paise`, set on delivery. Kept apart so the UI never shows an
-- estimate as if it were settled (there is no payment rail for transport yet).
alter table public.shipments
  add column if not exists transport_cost_estimate_paise bigint;
-- Who ARRANGES transport is orders.logistics_arranged_by; who PAYS is this.
-- They are not the same decision and the schema must not conflate them.
alter table public.shipments
  add column if not exists transport_paid_by     arranged_by;

-- A delivery window that closes before it opens, or a deadline before pickup,
-- is not a shipment anyone can perform. Rejected at the database, not just in
-- the form, because the form is not the security boundary.
do $$ begin
  alter table public.shipments
    add constraint shipments_window_sane
    check (
      (pickup_until is null or pickup_from is null or pickup_until >= pickup_from)
      and (deliver_by is null or pickup_from is null or deliver_by >= pickup_from)
    );
exception when duplicate_object then null; end $$;

-- CONCURRENCY (the invariant two transporters race for): one order has at most
-- one live shipment. Enforced here rather than in the router, so simultaneous
-- accepts cannot both win -- the loser gets a unique violation, which the
-- accept endpoint reports as "already taken" rather than 500.
create unique index if not exists uq_shipment_live_per_order
  on public.shipments(order_id) where status <> 'cancelled';

-- Additive (declared here, after shipments, because it references it):
-- consolidation_requests already modelled "ask a capacity owner to carry
-- goods, they accept or reject" (LG-2 / T-7) but nothing was ever wired to
-- it. The transport offer a transporter accepts or declines IS that row;
-- pointing it at the shipment avoids inventing a second, competing table.
alter table public.consolidation_requests
  add column if not exists shipment_id uuid references public.shipments(id) on delete cascade;
-- An offer nobody answered must not stay acceptable forever (a transporter
-- accepting a week-late pickup is worse than no transporter).
alter table public.consolidation_requests
  add column if not exists expires_at  timestamptz;

create index if not exists idx_consolidation_shipment on public.consolidation_requests(shipment_id, status);

-- The same capacity must not hold two open offers for one shipment, however
-- many times the arranger clicks "request".
create unique index if not exists uq_consolidation_open_offer
  on public.consolidation_requests(shipment_id, capacity_id) where status = 'pending';

create table if not exists public.shipment_locations (
  id          uuid primary key default gen_random_uuid(),
  shipment_id uuid not null references public.shipments(id) on delete cascade,
  lat         double precision not null,
  lon         double precision not null,
  speed_kmph  numeric(6,2),
  note        text,
  recorded_at timestamptz not null default now()
);

create index if not exists idx_shipment_locs on public.shipment_locations(shipment_id, recorded_at desc);

-- Stored output of AI-6. Keeps the "distance saved vs. naive" claim auditable
-- rather than recomputed-on-the-fly for the slide (PRD §12).
create table if not exists public.route_plans (
  id                    uuid primary key default gen_random_uuid(),
  transporter_id        uuid not null references public.profiles(id) on delete cascade,
  shipment_ids          uuid[] not null default '{}',
  stops                 jsonb not null default '[]'::jsonb,
  naive_distance_km     numeric(8,2) not null,
  optimized_distance_km numeric(8,2) not null,
  distance_saved_pct    numeric(5,2) not null,
  naive_duration_min    integer,
  optimized_duration_min integer,
  method                method_label not null default 'ALGORITHMIC',
  solver                text,   -- 'ortools_vrp' | 'nearest_neighbour_2opt'
  created_at            timestamptz not null default now()
);

create index if not exists idx_route_plans_owner on public.route_plans(transporter_id, created_at desc);


-- ===========================================================================
-- 9. STORAGE  (ST-1 / ST-2)
-- ===========================================================================

create table if not exists public.storage_listings (
  id                      uuid primary key default gen_random_uuid(),
  owner_id                uuid not null references public.profiles(id) on delete cascade,
  name                    text not null,
  storage_type            text not null default 'dry'
                            check (storage_type in ('cold','dry','controlled_atmosphere')),
  location_id             uuid references public.locations(id) on delete set null,
  district                text,
  capacity_kg             numeric(10,2) not null check (capacity_kg > 0),
  available_capacity_kg   numeric(10,2) not null check (available_capacity_kg >= 0),
  price_paise_per_kg_day  integer not null default 0,
  temperature_c           numeric(5,2),
  status                  text not null default 'active' check (status in ('active','inactive')),
  created_at              timestamptz not null default now()
);

create index if not exists idx_storage_owner on public.storage_listings(owner_id, status);

create table if not exists public.storage_bookings (
  id                uuid primary key default gen_random_uuid(),
  listing_id        uuid not null references public.storage_listings(id) on delete cascade,
  farmer_id         uuid not null references public.profiles(id) on delete cascade,
  product_id        uuid references public.products(id) on delete set null,
  quantity_kg       numeric(10,2) not null check (quantity_kg > 0),
  start_date        date not null,
  end_date          date not null,
  total_price_paise bigint not null default 0,
  status            booking_status not null default 'requested',
  created_at        timestamptz not null default now(),
  check (end_date >= start_date)
);

create index if not exists idx_bookings_farmer  on public.storage_bookings(farmer_id, status);
create index if not exists idx_bookings_listing on public.storage_bookings(listing_id, status);


-- ===========================================================================
-- 10. INTELLIGENCE
-- ===========================================================================

-- Makes the honesty label auditable: every AI payload's `method` traces to a
-- row here with the metric it actually scored (PRD §7 / R-9).
create table if not exists public.model_runs (
  id                    uuid primary key default gen_random_uuid(),
  model_name            text not null,
  model_version         text not null,
  method                method_label not null,
  trained_at            timestamptz not null default now(),
  metric_name           text,
  metric_value          numeric(12,4),
  baseline_metric_value numeric(12,4),
  data_source           text,       -- 'agmarknet' | 'synthetic'
  row_count             integer,
  notes                 text
);

create table if not exists public.prices (
  id                    uuid primary key default gen_random_uuid(),
  crop_id               uuid not null references public.crops(id) on delete cascade,
  district              text not null,
  state                 text,
  price_date            date not null,
  modal_price_paise     integer,
  min_price_paise       integer,
  max_price_paise       integer,
  arrival_qty_tonnes    numeric(12,3),
  -- false = observed history, true = model output
  is_prediction         boolean not null default false,
  horizon_days          integer,
  confidence_low_paise  integer,
  confidence_high_paise integer,
  method                method_label,
  data_source           text not null default 'agmarknet',
  model_run_id          uuid references public.model_runs(id) on delete set null,
  created_at            timestamptz not null default now()
);

create index if not exists idx_prices_lookup on public.prices(crop_id, district, price_date desc);
create unique index if not exists uq_prices_observed
  on public.prices(crop_id, district, price_date) where is_prediction = false;

create table if not exists public.demand_forecasts (
  id                   uuid primary key default gen_random_uuid(),
  crop_id              uuid not null references public.crops(id) on delete cascade,
  district             text not null,
  forecast_week_start  date not null,
  predicted_qty_tonnes numeric(12,3) not null,
  baseline_qty_tonnes  numeric(12,3),
  change_pct           numeric(6,2),
  confidence           numeric(4,3),
  method               method_label not null default 'REAL',
  model_run_id         uuid references public.model_runs(id) on delete set null,
  created_at           timestamptz not null default now(),
  unique (crop_id, district, forecast_week_start)
);

create index if not exists idx_demand_lookup on public.demand_forecasts(crop_id, district, forecast_week_start);


-- ===========================================================================
-- 11. TRUST & COMMS
-- ===========================================================================

create table if not exists public.feedback (
  id         uuid primary key default gen_random_uuid(),
  order_id   uuid not null references public.orders(id) on delete cascade,
  rater_id   uuid not null references public.profiles(id) on delete cascade,
  ratee_id   uuid not null references public.profiles(id) on delete cascade,
  ratee_role user_role not null,
  rating     smallint not null check (rating between 1 and 5),
  tags       text[] not null default '{}',
  comment    text,
  created_at timestamptz not null default now(),
  -- F-8: only once per counterparty per order.
  unique (order_id, rater_id, ratee_id),
  check (rater_id <> ratee_id)
);

create index if not exists idx_feedback_ratee on public.feedback(ratee_id);

create table if not exists public.notifications (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.profiles(id) on delete cascade,
  type        text not null,
  -- i18n keys, not literal strings: notifications must localise with the UI
  -- (C-2), so the row stores a key + params and the client renders it.
  title_key   text not null,
  body_key    text not null,
  params      jsonb not null default '{}'::jsonb,
  entity_type text,
  entity_id   uuid,
  read_at     timestamptz,
  created_at  timestamptz not null default now()
);

create index if not exists idx_notifications_inbox on public.notifications(user_id, read_at);

create table if not exists public.payments (
  id                  uuid primary key default gen_random_uuid(),
  order_id            uuid not null references public.orders(id) on delete cascade,
  buyer_id            uuid not null references public.profiles(id) on delete restrict,
  provider            text not null default 'mock',   -- 'mock' | 'razorpay'
  provider_order_id   text,
  provider_payment_id text,
  amount_paise        bigint not null check (amount_paise > 0),
  status              payment_status not null default 'created',
  held_at             timestamptz,
  released_at         timestamptz,
  refunded_at         timestamptz,
  created_at          timestamptz not null default now()
);

create index if not exists idx_payments_order on public.payments(order_id);

-- Guards double-submit on money-moving and state-changing POSTs.
create table if not exists public.idempotency_keys (
  key           text primary key,
  user_id       uuid not null references public.profiles(id) on delete cascade,
  endpoint      text not null,
  request_hash  text not null,
  response_body jsonb,
  status_code   integer,
  created_at    timestamptz not null default now()
);


-- ===========================================================================
-- 12. updated_at TRIGGERS
-- ===========================================================================

do $$
declare t text;
begin
  foreach t in array array[
    'profiles','products','buyer_requests','orders','transport_capacity','shipments'
  ] loop
    execute format(
      'drop trigger if exists trg_touch_%1$s on public.%1$s;
       create trigger trg_touch_%1$s before update on public.%1$s
       for each row execute function public.touch_updated_at();', t);
  end loop;
end $$;


-- ===========================================================================
-- 13. ROW LEVEL SECURITY
--
-- Read PRD R-12 before touching this section: RLS plus a service-role client
-- is RLS theatre. The backend issues a per-request Supabase client bound to
-- the caller's JWT, so these policies are actually enforced. The service-role
-- client is confined to the two files named in docs/ASSUMPTIONS.md (A-12).
--
-- Every policy below has a matching negative test in tests/test_rls.py.
-- ===========================================================================

do $$
declare t text;
begin
  foreach t in array array[
    'profiles','kyc_documents','fpos','farmer_profiles','buyer_profiles',
    'transporter_profiles','crops','locations','products','quality_grades',
    'buyer_requests','aggregations','aggregation_items','orders','order_items',
    'order_status_history','transport_capacity','consolidation_requests',
    'shipments','shipment_locations','route_plans','storage_listings',
    'storage_bookings','prices','demand_forecasts','model_runs','feedback',
    'notifications','payments','idempotency_keys'
  ] loop
    execute format('alter table public.%I enable row level security;', t);
  end loop;
end $$;

-- --- profiles ------------------------------------------------------------
-- Counterparty discovery requires reading other profiles, so SELECT is open
-- to authenticated users. Phone masking (PRD §11: masked until ACCEPTED) is
-- enforced at the API serialisation layer, not here, because a policy cannot
-- hide a single column.
drop policy if exists profiles_select on public.profiles;
create policy profiles_select on public.profiles
  for select to authenticated using (true);

drop policy if exists profiles_insert_self on public.profiles;
create policy profiles_insert_self on public.profiles
  for insert to authenticated with check (id = auth.uid());

drop policy if exists profiles_update_self on public.profiles;
create policy profiles_update_self on public.profiles
  for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

-- --- role detail tables ---------------------------------------------------
drop policy if exists farmer_profiles_select on public.farmer_profiles;
create policy farmer_profiles_select on public.farmer_profiles
  for select to authenticated
  using (
    profile_id = auth.uid()
    -- FPO reads its own members. Read + aggregate only, never write (R-3).
    or fpo_id = auth.uid()
  );

drop policy if exists farmer_profiles_write_self on public.farmer_profiles;
create policy farmer_profiles_write_self on public.farmer_profiles
  for update to authenticated using (profile_id = auth.uid()) with check (profile_id = auth.uid());

drop policy if exists farmer_profiles_insert_self on public.farmer_profiles;
create policy farmer_profiles_insert_self on public.farmer_profiles
  for insert to authenticated with check (profile_id = auth.uid());

drop policy if exists buyer_profiles_select on public.buyer_profiles;
create policy buyer_profiles_select on public.buyer_profiles
  for select to authenticated using (true);
drop policy if exists buyer_profiles_write on public.buyer_profiles;
create policy buyer_profiles_write on public.buyer_profiles
  for all to authenticated using (profile_id = auth.uid()) with check (profile_id = auth.uid());

drop policy if exists transporter_profiles_select on public.transporter_profiles;
create policy transporter_profiles_select on public.transporter_profiles
  for select to authenticated using (true);
drop policy if exists transporter_profiles_write on public.transporter_profiles;
create policy transporter_profiles_write on public.transporter_profiles
  for all to authenticated using (profile_id = auth.uid()) with check (profile_id = auth.uid());

drop policy if exists fpos_select on public.fpos;
create policy fpos_select on public.fpos for select to authenticated using (true);
drop policy if exists fpos_write on public.fpos;
create policy fpos_write on public.fpos
  for all to authenticated using (profile_id = auth.uid()) with check (profile_id = auth.uid());

-- KYC is private to its owner. Nobody else reads document numbers.
drop policy if exists kyc_own on public.kyc_documents;
create policy kyc_own on public.kyc_documents
  for all to authenticated using (profile_id = auth.uid()) with check (profile_id = auth.uid());

-- --- reference data (read-only to clients) --------------------------------
drop policy if exists crops_read on public.crops;
create policy crops_read on public.crops for select to authenticated using (true);

drop policy if exists locations_rw on public.locations;
create policy locations_rw on public.locations
  for all to authenticated using (owner_id = auth.uid() or owner_id is null)
  with check (owner_id = auth.uid());

-- --- products -------------------------------------------------------------
-- Anyone authenticated browses the live marketplace; only the owning farmer
-- sees their own drafts and withdrawn listings.
drop policy if exists products_select on public.products;
create policy products_select on public.products
  for select to authenticated
  using (
    status in ('active','reserved','sold')
    or farmer_id = auth.uid()
    or listed_by_fpo_id = auth.uid()
    or farmer_id in (select public.fpo_member_ids(auth.uid()))
  );

-- F-2: write scoped strictly to the owning farmer, or the FPO listing on
-- behalf of a not-yet-activated member (PRD §4.1 point 5).
drop policy if exists products_insert on public.products;
create policy products_insert on public.products
  for insert to authenticated
  with check (
    farmer_id = auth.uid()
    or (
      listed_by_fpo_id = auth.uid()
      and exists (
        select 1 from public.farmer_profiles fp
        where fp.profile_id = products.farmer_id
          and fp.fpo_id = auth.uid()
          and fp.onboarding_status = 'invited'
      )
    )
  );

drop policy if exists products_update on public.products;
create policy products_update on public.products
  for update to authenticated using (farmer_id = auth.uid()) with check (farmer_id = auth.uid());

drop policy if exists products_delete on public.products;
create policy products_delete on public.products
  for delete to authenticated using (farmer_id = auth.uid());

drop policy if exists quality_select on public.quality_grades;
create policy quality_select on public.quality_grades
  for select to authenticated
  using (exists (select 1 from public.products p where p.id = product_id));

drop policy if exists quality_insert on public.quality_grades;
create policy quality_insert on public.quality_grades
  for insert to authenticated
  with check (exists (
    select 1 from public.products p where p.id = product_id and p.farmer_id = auth.uid()));

-- --- buyer_requests -------------------------------------------------------
-- F-6: every farmer sees ALL open requests, not only matched ones.
drop policy if exists requests_select on public.buyer_requests;
create policy requests_select on public.buyer_requests
  for select to authenticated using (status = 'open' or buyer_id = auth.uid());

-- Ownership was enforced, but the role was not: any authenticated user could
-- post a buyer requirement naming themselves as the buyer, including a farmer
-- or a transporter. Same shape as capacity_write / aggregations_write —
-- ownership in USING, ownership plus the role gate in WITH CHECK.
drop policy if exists requests_write on public.buyer_requests;
create policy requests_write on public.buyer_requests
  for all to authenticated
  using (buyer_id = auth.uid())
  with check (
    buyer_id = auth.uid()
    and exists (select 1 from public.profiles p
                where p.id = auth.uid() and p.role = 'buyer')
  );

-- --- aggregations ---------------------------------------------------------
drop policy if exists aggregations_select on public.aggregations;
create policy aggregations_select on public.aggregations
  for select to authenticated
  using (
    buyer_id = auth.uid()
    or public.is_aggregation_participant(id, auth.uid())
  );

-- An aggregation is buyer-owned by construction: buyer_request_id is NOT NULL,
-- and a farmer's participation is an aggregation_items row, not an aggregation.
-- Ownership alone was therefore not enough — the old policy checked only
-- buyer_id = auth.uid(), so a farmer or transporter could create one naming
-- themselves as the buyer. Two gates are added, both in WITH CHECK, following
-- the capacity_write / storage_listings_write shape: the caller must actually
-- be a buyer, and the requirement being aggregated must be their own.
drop policy if exists aggregations_write on public.aggregations;
create policy aggregations_write on public.aggregations
  for all to authenticated
  using (buyer_id = auth.uid())
  with check (
    buyer_id = auth.uid()
    and exists (select 1 from public.profiles p
                where p.id = auth.uid() and p.role = 'buyer')
    and exists (select 1 from public.buyer_requests r
                where r.id = buyer_request_id and r.buyer_id = auth.uid())
  );

drop policy if exists agg_items_select on public.aggregation_items;
create policy agg_items_select on public.aggregation_items
  for select to authenticated
  using (
    farmer_id = auth.uid()
    or public.is_aggregation_buyer(aggregation_id, auth.uid())
  );

drop policy if exists agg_items_write on public.aggregation_items;
create policy agg_items_write on public.aggregation_items
  for all to authenticated
  using (public.is_aggregation_buyer(aggregation_id, auth.uid()))
  with check (public.is_aggregation_buyer(aggregation_id, auth.uid()));

-- A farmer answers the invitation on their OWN line only: UPDATE, never INSERT
-- or DELETE. Consent can be given or withdrawn, but a farmer can never add
-- themselves to a group or remove anyone else (PRD B-7 consent flow).
drop policy if exists agg_items_farmer_consent on public.aggregation_items;
create policy agg_items_farmer_consent on public.aggregation_items
  for update to authenticated
  using (farmer_id = auth.uid())
  with check (farmer_id = auth.uid());

-- --- orders ---------------------------------------------------------------
-- Participants only: buyer, sole farmer, any line-item farmer, or the
-- assigned transporter. Nobody else sees an order exists.
--
-- orders_select and orders_update OR the row's own buyer_id/farmer_id check
-- in ahead of is_order_participant(), even though that function already
-- covers the same two cases -- that function re-queries `orders` by id, and
-- PostgREST always sends `Prefer: return=representation` on writes. For
-- INSERT/UPDATE ... RETURNING under RLS, Postgres re-checks the SELECT/USING
-- policy against the row THIS SAME COMMAND just wrote -- but a command
-- cannot see its own effects via a fresh subquery (standard MVCC command-
-- visibility), so is_order_participant()'s self-referencing subquery on
-- `orders`, called from a policy that protects `orders` itself, always
-- evaluated as if the new/updated row didn't exist yet. The buyer's very
-- first order failed with "new row violates row-level security policy for
-- table orders" even though buyer_id = auth.uid() was correct.
--
-- The fix checks buyer_id/farmer_id inline first -- the executor already has
-- that tuple in hand, no re-query needed, so it works for a row from the
-- current command too -- and falls back to is_order_participant() only for
-- the rarer line-item-farmer/transporter cases. That function must stay a
-- SECURITY DEFINER call here rather than an inlined cross-table EXISTS:
-- order_items_write (below) is a raw, un-wrapped `for all` policy that
-- itself queries `orders` directly, so an un-wrapped reference to
-- order_items from inside orders' own policy is a genuine two-hop RLS
-- cycle ("infinite recursion detected in policy") -- is_order_participant's
-- SECURITY DEFINER runs its internal order_items/shipments lookups as the
-- function owner, bypassing their RLS and breaking that cycle, exactly as
-- it does for every other order-adjacent policy already.
drop policy if exists orders_select on public.orders;
create policy orders_select on public.orders
  for select to authenticated using (
    buyer_id = auth.uid() or farmer_id = auth.uid()
    or public.is_order_participant(id, auth.uid())
    -- A transporter holding a live offer on this order, so they can read the
    -- job (and the accept path can check the order's state) before they are a
    -- participant. Narrow and self-expiring: answering or letting the offer
    -- lapse removes the access. Consistent with what the transporter job list
    -- has always shown for orders awaiting transport.
    or public.has_open_transport_offer_on_order(id, auth.uid())
  );

drop policy if exists orders_insert on public.orders;
create policy orders_insert on public.orders
  for insert to authenticated with check (buyer_id = auth.uid() or farmer_id = auth.uid());

-- Transitions run through app/services/state_machine.py, which re-checks the
-- actor. This policy is the outer fence, not the rulebook.
drop policy if exists orders_update on public.orders;
create policy orders_update on public.orders
  for update to authenticated
  using (buyer_id = auth.uid() or farmer_id = auth.uid() or public.is_order_participant(id, auth.uid()))
  with check (buyer_id = auth.uid() or farmer_id = auth.uid() or public.is_order_participant(id, auth.uid()));

drop policy if exists order_items_select on public.order_items;
create policy order_items_select on public.order_items
  for select to authenticated using (public.is_order_participant(order_id, auth.uid()));

drop policy if exists order_items_write on public.order_items;
create policy order_items_write on public.order_items
  for all to authenticated
  using (exists (select 1 from public.orders o where o.id = order_id and o.buyer_id = auth.uid()))
  with check (exists (select 1 from public.orders o where o.id = order_id and o.buyer_id = auth.uid()));

-- Append-only audit log: SELECT + INSERT only, deliberately no UPDATE/DELETE.
drop policy if exists status_history_select on public.order_status_history;
create policy status_history_select on public.order_status_history
  for select to authenticated using (public.is_order_participant(order_id, auth.uid()));

drop policy if exists status_history_insert on public.order_status_history;
create policy status_history_insert on public.order_status_history
  for insert to authenticated with check (public.is_order_participant(order_id, auth.uid()));

-- --- transport capacity ---------------------------------------------------
-- Open capacity is a public marketplace (that is the point of F-7); editing
-- is owner-only.
drop policy if exists capacity_select on public.transport_capacity;
create policy capacity_select on public.transport_capacity
  for select to authenticated
  using (status in ('open','partially_booked') or transporter_id = auth.uid());

-- Ownership alone is not enough here. The original policy checked only
-- transporter_id = auth.uid(), so ANY authenticated user could post capacity
-- for themselves — a farmer could invent a cheap route to flatter their own
-- net-exit recommendation. Mirrors the storage_listings_write shape below:
-- ownership in USING, ownership plus the role gate in WITH CHECK.
drop policy if exists capacity_write on public.transport_capacity;
create policy capacity_write on public.transport_capacity
  for all to authenticated
  using (transporter_id = auth.uid())
  with check (
    transporter_id = auth.uid()
    and exists (select 1 from public.profiles p
                where p.id = auth.uid() and p.role = 'transporter')
  );

drop policy if exists consolidation_select on public.consolidation_requests;
create policy consolidation_select on public.consolidation_requests
  for select to authenticated
  using (
    requester_id = auth.uid()
    or exists (select 1 from public.transport_capacity c
               where c.id = capacity_id and c.transporter_id = auth.uid())
  );

drop policy if exists consolidation_insert on public.consolidation_requests;
create policy consolidation_insert on public.consolidation_requests
  for insert to authenticated with check (requester_id = auth.uid());

-- Only the owning transporter may accept/reject (T-7).
drop policy if exists consolidation_update on public.consolidation_requests;
create policy consolidation_update on public.consolidation_requests
  for update to authenticated
  using (exists (select 1 from public.transport_capacity c
                 where c.id = capacity_id and c.transporter_id = auth.uid()))
  with check (exists (select 1 from public.transport_capacity c
                      where c.id = capacity_id and c.transporter_id = auth.uid()));

-- --- shipments ------------------------------------------------------------
drop policy if exists shipments_select on public.shipments;
create policy shipments_select on public.shipments
  for select to authenticated
  using (
    transporter_id = auth.uid()
    or public.is_order_participant(order_id, auth.uid())
    -- A transporter who has been asked to carry this load, for as long as
    -- that offer is live. Without it they would be deciding blind.
    or public.has_open_transport_offer(id, auth.uid())
  );

-- Three writers, each for a different part of the shipment's life:
--   the assigned transporter (pickup -> in transit -> delivered),
--   the order's buyer/farmer (logistics detail, and cancelling),
--   a transporter who holds a live offer, claiming an unassigned shipment.
-- The last one is the accept path: before anyone accepts, transporter_id is
-- null, so a policy keyed only on transporter_id could never be satisfied and
-- the job could never be taken. WITH CHECK deliberately omits the offer case:
-- the row a claimer writes must name themselves as transporter, so a claim can
-- only ever assign the job to the caller, never to a third party.
drop policy if exists shipments_update on public.shipments;
create policy shipments_update on public.shipments
  for update to authenticated
  using (
    transporter_id = auth.uid()
    or public.is_order_participant(order_id, auth.uid())
    or (transporter_id is null and public.has_open_transport_offer(id, auth.uid()))
  )
  with check (
    transporter_id = auth.uid()
    or public.is_order_participant(order_id, auth.uid())
  );

drop policy if exists shipments_insert on public.shipments;
create policy shipments_insert on public.shipments
  for insert to authenticated with check (public.is_order_participant(order_id, auth.uid()));

drop policy if exists shipment_locs_select on public.shipment_locations;
create policy shipment_locs_select on public.shipment_locations
  for select to authenticated
  using (exists (select 1 from public.shipments s
                 where s.id = shipment_id
                   and (s.transporter_id = auth.uid()
                        or public.is_order_participant(s.order_id, auth.uid()))));

drop policy if exists shipment_locs_insert on public.shipment_locations;
create policy shipment_locs_insert on public.shipment_locations
  for insert to authenticated
  with check (exists (select 1 from public.shipments s
                      where s.id = shipment_id and s.transporter_id = auth.uid()));

-- A transporter never sees another transporter's routing or earnings.
drop policy if exists route_plans_own on public.route_plans;
-- Route plans are transporter working data; the role gate mirrors
-- capacity_write so a farmer or buyer cannot create one for themselves.
create policy route_plans_own on public.route_plans
  for all to authenticated
  using (transporter_id = auth.uid())
  with check (
    transporter_id = auth.uid()
    and exists (select 1 from public.profiles p
                where p.id = auth.uid() and p.role = 'transporter')
  );

-- --- storage --------------------------------------------------------------
drop policy if exists storage_listings_select on public.storage_listings;
create policy storage_listings_select on public.storage_listings
  for select to authenticated using (status = 'active' or owner_id = auth.uid());

-- T-9: only a profile flagged is_storage_provider may create storage.
drop policy if exists storage_listings_write on public.storage_listings;
create policy storage_listings_write on public.storage_listings
  for all to authenticated
  using (owner_id = auth.uid())
  with check (
    owner_id = auth.uid()
    and exists (select 1 from public.profiles p
                where p.id = auth.uid() and p.is_storage_provider)
  );

drop policy if exists storage_bookings_select on public.storage_bookings;
create policy storage_bookings_select on public.storage_bookings
  for select to authenticated
  using (
    farmer_id = auth.uid()
    or exists (select 1 from public.storage_listings sl
               where sl.id = listing_id and sl.owner_id = auth.uid())
  );

drop policy if exists storage_bookings_insert on public.storage_bookings;
create policy storage_bookings_insert on public.storage_bookings
  for insert to authenticated with check (farmer_id = auth.uid());

drop policy if exists storage_bookings_update on public.storage_bookings;
create policy storage_bookings_update on public.storage_bookings
  for update to authenticated
  using (farmer_id = auth.uid()
         or exists (select 1 from public.storage_listings sl
                    where sl.id = listing_id and sl.owner_id = auth.uid()));

-- --- intelligence (read-only to clients; written by the training pipeline) -
drop policy if exists prices_read on public.prices;
create policy prices_read on public.prices for select to authenticated using (true);

drop policy if exists demand_read on public.demand_forecasts;
create policy demand_read on public.demand_forecasts for select to authenticated using (true);

-- Public so the UI can show "trained on N rows, MAE x vs. baseline y".
drop policy if exists model_runs_read on public.model_runs;
create policy model_runs_read on public.model_runs for select to authenticated using (true);

-- --- trust & comms --------------------------------------------------------
-- Ratings are public (they are the trust signal); writing one requires being
-- a participant on a DELIVERED order — enforced in the feedback router.
drop policy if exists feedback_select on public.feedback;
create policy feedback_select on public.feedback for select to authenticated using (true);

-- Both sides must have been on the order, not just the reviewer: otherwise a
-- genuine buyer could review a transporter who never carried their goods, or
-- any stranger at all, by naming them as ratee. is_order_participant covers
-- buyer, sole farmer, line-item farmer and the assigned transporter, so this
-- authorises exactly the counterparties a reviewer actually dealt with.
-- Self-review and double-review are already impossible: the table carries
-- check (rater_id <> ratee_id) and unique (order_id, rater_id, ratee_id).
-- "Only after the order completed" stays in the router, which can report why.
drop policy if exists feedback_insert on public.feedback;
create policy feedback_insert on public.feedback
  for insert to authenticated
  with check (
    rater_id = auth.uid()
    and public.is_order_participant(order_id, auth.uid())
    and public.is_order_participant(order_id, ratee_id)
  );

-- C-4: role-scoped by construction. A farmer cannot read a transporter's row.
drop policy if exists notifications_own on public.notifications;
create policy notifications_own on public.notifications
  for select to authenticated using (user_id = auth.uid());

drop policy if exists notifications_update_own on public.notifications;
create policy notifications_update_own on public.notifications
  for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists payments_select on public.payments;
create policy payments_select on public.payments
  for select to authenticated
  using (buyer_id = auth.uid() or public.is_order_participant(order_id, auth.uid()));

-- This table had no INSERT policy at all: default-deny meant POST
-- /orders/{id}/pay failed every single time with "new row violates row-level
-- security policy for table payments", 500ing before the caller ever reached
-- the buyer_id/status checks already in mock_payment(). Ownership mirrors
-- orders_insert's shape: the row must name the caller as its own buyer.
drop policy if exists payments_insert on public.payments;
create policy payments_insert on public.payments
  for insert to authenticated with check (buyer_id = auth.uid());

drop policy if exists idempotency_own on public.idempotency_keys;
create policy idempotency_own on public.idempotency_keys
  for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

commit;
