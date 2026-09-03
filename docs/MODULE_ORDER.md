# MODULE_ORDER.md

Opus planning-pass artifact (plan.md §9.3). The literal build sequence for the execution
pass, with the dependency reasoning for why each module sits where it does.

Derived from plan.md §14 and the execution prompt's seven phases. Two deviations from
that order are marked **⚠ RESEQUENCED** with the reason — both are cases where the
original order would force rework.

---

## Phase 0 — Contracts *(this pass; complete)*

| # | Deliverable | Status |
|---|---|---|
| 0.1 | `db/SCHEMA.sql` | ✅ 31 tables, 2 compat views, RLS on all |
| 0.2 | `docs/API_CONTRACT.md` | ✅ 15 routers, all 35 matrix rows covered |
| 0.3 | `docs/MODULE_ORDER.md` | ✅ this file |
| 0.4 | `docs/ASSUMPTIONS.md` | ✅ 24 decisions + 4 confirmations |
| 0.5 | `.gitignore`, `.env.example`, `git init` | ✅ `.env` verified ignored |

**Gate:** nothing in Phase 1+ starts until 0.1–0.4 exist. They now do.

---

## Phase 1 — Foundation

| # | Module | Depends on | Why here |
|---|---|---|---|
| 1.1 | Scaffolding — folder tree, settings via `python-dotenv`, FastAPI app, CORS, error-envelope handler, `/api/health`, `/api/config` | 0.5 | Every later module imports `settings`. Building it once beats retrofitting config into nine routers. |
| 1.2 | **⚠ RESEQUENCED — apply `SCHEMA.sql` first** | 1.1, real `.env` | The execution prompt puts this at step 4, after auth and profiles. That is backwards: auth writes to `profiles`, so the table must exist before the auth module can be run even once. Moved ahead of 1.3. |
| 1.3 | `css/tokens.css` + app shell + hash router + `api.js` + `store.js` + `i18n.js` | 1.1 | PRD §5.1's mandatory patterns. Every screen depends on these six files; writing screen 1 without them guarantees thirty ad-hoc pages. `t()` exists before the first screen so no literal string is ever committed (A-20). |
| 1.4 | Seed `crops` master | 1.2 | `products`, `buyer_requests`, and `prices` all FK to it. Nothing can be listed before crops exist. |
| 1.5 | Auth — Supabase signup/login/logout in the browser, `get_current_user()` JWT dependency, `/auth/register`, `/auth/me`, role-gated router in the frontend | 1.2, 1.3 | The JWT dependency is what every protected endpoint hangs off. |
| 1.6 | Profiles + KYC — role detail tables, `/profiles/*`, profile screen, phone masking (A-13) | 1.5 | Needs a session to exist. |
| 1.7 | `tests/test_rls.py` — one **negative** test per policy (farmer A cannot read farmer B's draft; transporter A cannot read transporter B's earnings) | 1.2, 1.5 | **⚠ RESEQUENCED — pulled forward from "polish".** RLS bugs found in Phase 7 mean re-auditing every endpoint written since. Found in Phase 1, they cost minutes. This is also the execution prompt's own quality gate, so it must be runnable from the first module, not asserted at the end. |

**Exit:** three roles can sign up, log in, land on their own dashboard shell, and are
provably blocked from each other's rows.

---

## Phase 2 — Core marketplace

| # | Module | Depends on | Why here |
|---|---|---|---|
| 2.1 | `crops` + `locations` endpoints | 1.4 | Feeds every form's dropdowns. |
| 2.2 | Products CRUD + Supabase Storage photo upload | 1.5, 2.1 | The farmer's core loop. |
| 2.3 | AI-1 image grading (`HEURISTIC`) — OpenCV features → per-crop rule table → grade + confidence + feature breakdown | 2.2 | Wired at 2.2's upload endpoint. Built now because the grade is a column on `products` that matching (2.5) reads; adding it later means backfilling every seeded listing. |
| 2.4 | Buyer requests CRUD + the open-requests feed (F-6) | 1.5, 2.1 | The other half of the marketplace loop. |
| 2.5 | AI-5 smart matching — weighted score, geohash proximity prefilter | 2.2, 2.4 | Needs both sides of the market to exist before it has anything to match. |

**Exit:** a farmer lists produce, it gets graded, a buyer discovers it; a buyer posts a
requirement, every farmer sees it.

---

## Phase 3 — Intelligence

| # | Module | Depends on | Why here |
|---|---|---|---|
| 3.1 | Mandi data acquisition → `backend/data/mandi_prices.csv`, committed (A-18) | — | **Start this first in the phase and in parallel** — it is the single biggest demo risk (PRD R-10). If data.gov.in is unreachable, 3.2 and 3.3 fall back to synthetic and every payload must say so. Finding that out on day one is recoverable; on day five it is not. |
| 3.2 | AI-2 price prediction (`REAL`) + `/pricing/*` + both role-facing screens | 3.1 | |
| 3.3 | AI-3 demand forecasting (`REAL`) + seasonal-naive baseline + MAE report | 3.1 | Same feature pipeline as 3.2; building them together avoids writing the lag/calendar feature code twice. |
| 3.4 | AI-4 recommendation engine (`ALGORITHMIC`) | 3.2, 2.5 | Scores sale channels using predicted price — needs 3.2 to exist. |
| 3.5 | `model_runs` + the `method` envelope on every AI response | 3.2, 3.3 | The honesty label (A-17). |

**Exit:** listings and requests carry real numbers, each labelled with how it was
produced.

---

## Phase 4 — Orders & escrow

> **⚠ RESEQUENCED — moved ahead of logistics.** The execution prompt places Orders at
> step 18, after all of logistics. But `shipments` FK to `orders`, `LOGISTICS_ASSIGNED`
> is an order state, and transport is requested *for an order*. Building logistics first
> means stubbing an order object and then rewriting every logistics endpoint once the
> real one lands. plan.md §14 step 4 has the same latent ordering problem; PRD §15 step 5
> gets it right, and PRD §8 calls the state machine "the spine of the product".

| # | Module | Depends on | Why here |
|---|---|---|---|
| 4.1 | `state_machine.py` — the single authority for transitions, `409` on illegal ones, writes `order_status_history` | 1.2 | Everything below calls it. Written before the first transition endpoint, not extracted afterwards. |
| 4.2 | Orders CRUD, `DRAFT→PLACED→ACCEPTED`, quantity reservation, phone unmasking | 4.1, 2.2, 2.4 | |
| 4.3 | Aggregation (B-7) — greedy bin-packing, multi-farmer order (A-4) | 4.2, 2.5 | |
| 4.4 | Payments/escrow — mock provider default, Razorpay sandbox behind it; `→ PAYMENT_HELD` | 4.2 | |
| 4.5 | F-12 price breakdown screen | 4.2, 3.2 | The screen that proves the PS claim. Not polish — it is the deliverable. |

**Exit:** a buyer accepts an offer and funds escrow; the order has a real, audited state.

---

## Phase 5 — Logistics

| # | Module | Depends on | Why here |
|---|---|---|---|
| 5.1 | `transport_capacity` CRUD — one module serving F-7, T-5, T-6 (A-3) | 4.2 | Three matrix rows, one build. |
| 5.2 | Transport request → `LOGISTICS_ASSIGNED`, `shipments`, `logistics_arranged_by` enforcement (PRD §6.6) | 5.1, 4.1 | |
| 5.3 | AI-6 route optimisation — OR-Tools VRP, nearest-neighbour + 2-opt fallback, saved-vs-naive reporting, `route_plans` | 5.2 | |
| 5.4 | ETA per option (B-6), computed per request (A-9) | 5.3 | |
| 5.5 | Consolidation requests — F-10 and T-7, one table, two views (A-3/LG-2) | 5.1 | |
| 5.6 | Live tracking — `ping`/`track`, 10 s polling, Leaflet + OSM map, status timeline | 5.2 | |
| 5.7 | Pickup OTP → `PICKED_UP`; delivery OTP → `DELIVERED`, escrow release | 5.6, 4.4 | Proof of delivery without an admin (R-13). |
| 5.8 | Storage listings + bookings (T-9, ST-1, ST-2) | 1.6 | Gated on `is_storage_provider`. |
| 5.9 | Transporter earnings (T-4) | 5.7 | Needs completed shipments to sum. |

**Exit:** the full physical chain runs — assigned, optimised, tracked, delivered, paid.

---

## Phase 6 — Trust & comms

| # | Module | Depends on | Why here |
|---|---|---|---|
| 6.1 | Feedback + rating rollup (F-8, B-5, T-8) | 5.7 | Gated on `DELIVERED`, so it cannot be tested before Phase 5 closes. |
| 6.2 | `→ CLOSED` on both feedbacks or 72 h | 6.1 | |
| 6.3 | Notifications — i18n keys + params (A-11), bell badge, polling | 4.2, 5.2 | Emitted by transitions built in 4 and 5; wiring it earlier means re-touching every one. |
| 6.4 | Rating feedback loop into AI-4 / AI-5 scoring | 6.1, 2.5 | Closes the trust loop the PS asks for. |

---

## Phase 7 — Accessibility

| # | Module | Depends on | Why here |
|---|---|---|---|
| 7.1 | Fill `en` / `hi` / `mr` dictionaries; language switcher; `<html lang>`; `localStorage` persistence | 1.3 | The **key structure exists from 1.3**; this phase fills values. A CI check fails the build on a key missing from any locale (PRD §11). |
| 7.2 | Voice assistant + chatbot — FAQ intent matcher, LLM fallback, Web Speech in three languages, typed fallback everywhere (A-21) | 7.1 | |
| 7.3 | Offline/low-bandwidth (C-5) — cached dashboard payload, stale-data banner, queued writes | 1.3, 6.3 | |

---

## Phase 8 — Polish & demo

| # | Module | Why |
|---|---|---|
| 8.1 | `scripts/seed_demo.py` — Ramesh (farmer, Nashik), an FPO with 2 members, Sunita (bulk buyer, Pune), an individual buyer, Vikram (transporter), plus listings/orders/shipments so judges see a living app on first login | PRD §13's exact narrative must run with no manual DB edit |
| 8.2 | `scripts/smoke_demo.py` — list → grade → match → order → transport → deliver → feedback, asserted end to end, < 4 min | Turns "it works" into a repeatable check |
| 8.3 | `/metrics/impact` screen — §12 numbers from live rows | A metric that exists only on a slide is the one a judge asks you to demonstrate |
| 8.4 | Four-flow verification (execution prompt §3 Step D); fix every dead-end | |
| 8.5 | README — SIH26033 outcome mapping, real-vs-stubbed model table, setup | plan.md §11.5 |
| 8.6 | `tests/test_no_service_key_leak.py` in CI | A-12 |

---

## Critical path

```
0 contracts ─► 1 auth/profiles ─► 2 marketplace ─┬─► 3 intelligence ─┐
                                                 └─► 4 orders ───────┴─► 5 logistics
                                                                          │
                                            8 demo ◄─ 7 a11y ◄─ 6 trust ◄─┘
```

Phase 3 (intelligence) and Phase 4 (orders) both depend only on Phase 2 and are
independent of each other — they can run in parallel if there is a second pair of hands.
**3.1, the mandi data pull, should start on day one regardless of phase order**, because
it is the only task whose failure mode is discovered externally and forces a labelled
downgrade across two models (A-18).

## Standing rule per module

The execution prompt's Section 7 gates apply to every module before it is reported
complete: matrix row has a working screen *and* endpoint · no secret in any frontend
file · RLS negative test passes · error, empty, and loading states all exist · 360 px
with no horizontal scroll · every string i18n-keyed.
