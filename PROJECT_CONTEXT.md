# UDGAM.ai — Full Project Context

One file with everything needed to pick this project back up cold: what it is, how it's built, what's been done, what's known-broken, and how to run it. Written so a new session (human or AI) doesn't have to re-derive any of this from git log archaeology.

---

## 1. What this project is

**UDGAM.ai** is an agricultural marketplace connecting three kinds of users directly:

- **Farmers** — list produce, see market intelligence, decide how/when/where to sell
- **Buyers** — post requirements, browse listings, place orders
- **Transporters** — post capacity/routes, pick up delivery jobs, get matched to shipments

It started as a straightforward listing marketplace, then was extended to answer a harder question for a hackathon problem statement called **SIH26132**:

> "Given my crop, my quantity, my location, today's prices, transport costs, and risk — what is the best way and time for me to sell?"

Everything under "SIH26132 features" below exists to answer that.

---

## 2. Canonical location and the tree that doesn't matter

**There are two copies of this codebase on disk. Only one is real:**

| Path | Status |
|---|---|
| `C:\udgam_ai\udgam.ai` | **Canonical.** All work described in this file lives here. Git-tracked, 15 commits. |
| `C:\udgam_ai\Udgam` | **Not canonical.** An older/parallel tree. Left untouched throughout. Do not port work into it or out of it without being asked. |

The Python virtual environment used to run everything is at `C:\udgam_ai\Udgam\.venv\Scripts\python.exe` — yes, the venv lives in the *other* tree's folder but is used to run the canonical one. This is intentional/historical, not a mistake to fix.

---

## 3. Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, `uvicorn` |
| Database | Supabase (hosted Postgres) — accessed via `supabase-py` / `postgrest-py`, never raw SQL from the app |
| Auth | Supabase Auth (JWT), verified backend-side by decoding claims + RLS enforcement in Postgres |
| Authorization | Postgres Row-Level Security (RLS) policies, defined in `db/SCHEMA.sql` — this is the actual security boundary, not application code |
| Frontend | **Vanilla HTML/CSS/JavaScript.** No framework, no build step, no bundler. ES modules loaded directly by the browser. |
| Frontend routing | A hand-written hash router (`frontend/js/core/router.js`) |
| i18n | Three locales — English, Hindi, Marathi — JSON dictionaries in `frontend/i18n/*.json`, looked up via `t()` |
| Testing | `pytest`, 230+ tests, all backend/service-level (no frontend test runner) |

A full frontend-architecture audit was done partway through this project's history (see §8) and concluded the vanilla-JS stack is **not** the performance bottleneck — see §9. No framework migration was performed or is recommended.

---

## 4. Repository layout

```
backend/app/
  main.py              FastAPI app, router registration
  config.py            Settings from .env (Supabase URL/keys, feature flags)
  deps.py              Auth dependency chain: get_identity -> get_current_user -> require_role
  errors.py            Typed error hierarchy -> consistent JSON error envelope
  db/
    supabase_client.py Request-scoped Supabase/Postgrest client construction (see §10 — this file
                       has a load-bearing docstring explaining two verified concurrency hazards)
    admin_client.py    Service-role client. Imported by exactly two modules on purpose (A-12 rule)
  routers/             One file per resource area (see table below)
  services/            Pure business logic, no I/O where possible (see table below)
  ml/                  Empty. No trained model exists in this project — see §7 honesty section

frontend/
  index.html           Single entry point. Cache-busted script tag (?v=N, bump on every JS change)
  js/
    app.js             Boot sequence: i18n -> supabase config -> session -> router
    routes.js           All ~29 routes registered here, each mapped to a view module
    core/               router, store (pub/sub state), api client, i18n, nav
    views/              One module per screen, grouped by role: farmer/, buyer/, transporter/
  css/                  tokens.css (design system vars), base, components, shell, landing
  i18n/                 en.json, hi.json, mr.json — must stay in key-parity (checked in review, not enforced by tooling)

db/
  SCHEMA.sql            The entire database schema AND all RLS policies. ~1300 lines. This is the
                        single source of truth for authorization — read this before assuming any
                        table's access rules.

scripts/
  seed_demo.py          Idempotent demo-data seeding (crops, demo accounts, market data, transport
                        capacity, storage listings). Safe to re-run.
  apply_schema.py       Applies db/SCHEMA.sql to the configured Supabase instance

tests/                  pytest suite, ~230 passing tests + 3 known pre-existing failures (§6)

WHATS_NEW.md            Plain-English changelog of the SIH26132 work, written for a non-technical
                        reader (e.g. a judge or teammate). Complements this file rather than
                        duplicating it — read that one for "what does this feature do for a user,"
                        read this one for "how is the whole system built."
```

### Backend routers (what each one owns)

| Router | Owns |
|---|---|
| `auth.py` | `/api/config`, `/api/health`, `/api/auth/register`, `/api/auth/me`, `/api/auth/activate` |
| `dashboard.py` | `/api/dashboard/{farmer,buyer,transporter}` — role landing-page summaries |
| `products.py` | Farmer listings CRUD, photo upload |
| `buyer_matching.py` | Buyer requirement <-> farmer listing matching feed |
| `orders.py` | Order lifecycle, state machine transitions |
| `transport.py` | Transport capacity posting, shipment tracking |
| `profiles.py` | Profile read/update, storage-provider flag |
| `notifications.py` | Notification list, mark-read, mark-all-read |
| `market.py` | Market price data (Phase 1 of SIH26132) |
| `decisions.py` | Net Exit Optimizer, Sale Window, Emergency Exit (farmer decision-support) |
| `aggregations.py` | Dynamic Supply Aggregation lifecycle (suggest -> consent -> confirm/cancel) |

### Backend services (pure logic, mostly no I/O)

| Service | Does |
|---|---|
| `pricing.py` | Platform-sale fee/payout breakdown (2% platform fee, farmer gets subtotal) |
| `state_machine.py` | Order status transition validation |
| `route_optimizer.py` | Haversine distance calc |
| `grading.py` | OpenCV-based produce quality grading (HEURISTIC method label) |
| `masking.py` | Phone number masking until order accepted |
| `market_data.py` | Synthetic price/demand generation + freshness/provenance grading |
| `opportunity.py` | Shared `Opportunity` dataclass — the contract every decision engine returns |
| `net_exit.py` | Net Exit Optimizer: ranks sale channels by farmer net realization |
| `sale_window.py` | Risk-Adjusted Sale Window: sell-now vs wait, penalized by forecast uncertainty |
| `aggregation.py` | Dynamic Supply Aggregation: greedy cheapest-first lot selection |
| `emergency_exit.py` | Re-ranks alternatives when an order is cancelled/disputed |
| `orchestration.py` | Neutral Orchestration: the single declared ranking-factor policy every engine imports, plus the fairness-audit contract |

---

## 5. The SIH26132 feature set (what was built, in order)

Built as six phases plus a UI phase, each gated on the previous being tested and approved. Full detail and a non-technical explanation is in `WHATS_NEW.md`; this is the engineering summary.

| Phase | Feature | Core idea |
|---|---|---|
| 1 | Market Data Spine | Synthetic (labelled `SYNTHETIC`, never `REAL`) price/demand data for 6 crops across 8 Maharashtra districts, with freshness/provenance on every figure |
| 2 | Net Exit Optimizer | For one listing, computes farmer net realization for every reachable channel (direct buyer, mandi) — gross minus transport minus platform fee/commission minus spoilage — and ranks them. Key insight encoded: platform sales have the *buyer* pay transport+fee; mandi sales have the *farmer* pay them. Highest price ≠ best deal. |
| 3 | Risk-Adjusted Sale Window | Sell now vs wait N days, penalized by the forecast's own confidence band (wider uncertainty = bigger penalty on the "wait" option) |
| 4 | Dynamic Supply Aggregation | Combines several small farmer lots to fill one large buyer requirement. Full consent lifecycle: `suggested -> farmer consent -> buyer confirm -> reserved`. Reservation is a *derived* ledger read (not a write to the farmer's listing) — see the security note below. |
| 5 | Emergency Exit Engine | When an order is CANCELLED/DISPUTED, re-ranks alternative buyers/mandis for the stranded quantity. Read-only — never mutates the original order; the cancelling buyer is excluded from its own alternatives. |
| 6 | Neutral Orchestration | Not a feature so much as a constraint: `orchestration.py` declares the only factors any ranking may use (net realization, distance, quantity/quality fit, deadline fit — never buyer/farmer identity, never partner status). A dedicated test suite (`test_neutrality.py`) proves rankings are invariant under renaming counterparties. |
| UI | Market Decision Center | `frontend/js/views/farmer/decisions.js` — the farmer-facing screen surfacing all of the above for one listing at a time, with plain-language explanations and honesty badges (Simulated/Estimated/Algorithm). |

### Honesty labelling convention (load-bearing, do not violate)

Every number surfaced to a user carries a method label:

- **REAL** — an actual observed value. Not used anywhere in this project yet (no live mandi feed, no trained model).
- **SYNTHETIC** — generated data standing in for a real feed, clearly marked as such
- **ALGORITHMIC** — deterministic computation (the decision engines are all this)
- **HEURISTIC** — rule-of-thumb, not learned (the CV grading is this)

`backend/app/ml/` is an empty package on purpose — there is no trained model in this project. Do not let any future work imply otherwise (e.g. by labelling something REAL that is actually generated).

---

## 6. Testing

```powershell
C:\udgam_ai\Udgam\.venv\Scripts\python.exe -m pytest -q
```

**Current state: 230 passed, 3 failed.** The 3 failures are **known and pre-existing** — they predate all work described in this file and are unrelated to it:

1. `test_adversarial_qa.py::test_cv_fine_grained_blemish_sensitivity` — a CV grading edge case
2. `test_adversarial_qa.py::test_unauthenticated_requests_receive_standard_401` — an auth envelope edge case
3. `test_no_service_key_leak.py::test_service_role_key_confined_to_allowed_modules` — flags that `AUTH_FIXES.md` and `SETUP_GUIDE.md` mention the service-role key by name in prose (documentation, not a real leak, but the test doesn't distinguish)

If a future session sees exactly these 3 failures and nothing else, that's the expected baseline — don't spend time "fixing" them unless specifically asked.

---

## 7. Security work done (chronological, each verified live against the database)

RLS is the real authorization boundary in this project (Postgres policies in `db/SCHEMA.sql`), not application code. Several policies were found to check ownership but not *role*, meaning e.g. a farmer could `INSERT` a row into a table that should be buyer-only, naming themselves as the owner. Each of the following was found, fixed, and verified with live INSERT/UPDATE/DELETE attempts across all three roles plus anonymous:

| Table.policy | Problem found | Fix |
|---|---|---|
| `transport_capacity.capacity_write` | Any authenticated user could post transport capacity | Added `role = 'transporter'` to the `WITH CHECK` clause |
| `aggregations.aggregations_write` | Any authenticated user could create an aggregation as a fake "buyer" | Added `role = 'buyer'` + ownership check on the underlying buyer_request |
| `aggregations` / `aggregation_items` SELECT policies | **Infinite recursion** — the two policies each queried the other's table, causing Postgres to reject reads entirely under RLS. This was a functional bug, not just a security one. | Broke the cycle with a `SECURITY DEFINER` helper function |
| `buyer_requests.requests_write` | Any authenticated user (e.g. a transporter) could post a buyer requirement | Added `role = 'buyer'` |
| `route_plans.route_plans_own` | Any authenticated user could create a transporter's route plan | Added `role = 'transporter'` |

**Aggregation reservation is a derived read, not a write.** When a buyer confirms an aggregation, `available_quantity_kg` on the farmer's product row is **never decremented directly** — availability is computed by reading the live `aggregation_items` ledger. This was a deliberate design choice to avoid a write-conflict class of bug (two buyers racing to reserve the same lot).

**Outstanding, not yet done:** the database password was printed to a terminal at some point during setup/debugging in this session's history. It was never committed to the repo, but **should be rotated** in the Supabase dashboard as a precaution. This is flagged in `WHATS_NEW.md` §8 as well.

---

## 8. Frontend performance audit and fix (most recent substantial work)

A full audit was requested comparing "is vanilla JS the bottleneck, and should this migrate to React/Next/Svelte." The audit was rigorous and evidence-based rather than assumed:

**Finding: the frontend stack is not the bottleneck.** Total JS payload is ~192KB across 39 files, CSS ~54KB, one 562-byte SVG logo. Static asset serving measured at 2–125ms locally. **No migration was performed or recommended.**

**The actual bottleneck: backend-to-Supabase latency, made worse by two backend anti-patterns:**

1. `user_client()` (in `backend/app/db/supabase_client.py`) rebuilt a full `supabase.Client` from scratch on **every single authenticated request**, because it's called from `deps.py:get_identity()`, which runs on every protected endpoint. Measured cost: **280–650ms per call**, almost entirely `httpx.Client()` building a fresh `ssl.SSLContext` (Python re-parses the OS/CA trust store every time; it isn't cached across instances by default).

2. Several endpoints ran independent Supabase queries **sequentially** when they had no dependency on each other (e.g. `/api/auth/me` looks up the profile, then the role-detail table, then an FPO check — the last two don't depend on each other).

### The fix, and the two safety hazards found while implementing it

This is the most important engineering narrative in the project's recent history, worth understanding in full before touching `supabase_client.py` again:

**Fix attempt 1 (rejected before shipping):** share one `SyncPostgrestClient` instance across requests. **Unsafe** — `BasePostgrestClient.auth()` mutates `self.session.headers["Authorization"]` **in place**. Two concurrent requests sharing one instance could have one user's query run under another user's bearer token. Verified this is real by reading the library source, not assumed.

**Fix attempt 2 (shipped, then found unsafe under load):** keep building a fresh client per request, but share **one global `ssl.SSLContext`** across all of them (the standard httpx advice for this exact cost). This dropped per-call construction to ~0.15ms. **But** stress-testing the real endpoints (not just a single-threaded benchmark) surfaced an intermittent, reproducible `httpx.ConnectError: [SSL: TLSV1_ALERT_DECODE_ERROR]` — a corrupted TLS handshake — occurring at roughly 1-in-20 requests when two threads performed a genuinely simultaneous *first* handshake against the same shared context object. This is a real hazard of concurrent SSLContext use that isn't covered by the usual "SSLContext is safe to share" advice (that advice covers *sequential* reuse).

**Fix attempt 3 (shipped, currently in production):** one `ssl.SSLContext` **per worker thread**, cached in `threading.local()`, built lazily on that thread's first use. Since FastAPI's `asyncio.to_thread` reuses a bounded pool of worker threads across requests, each thread still only pays the ~30ms context-build cost once for the life of the process — but two threads never touch the same context object at the same instant, because each has its own. **Verified with 150+ live stress-test requests and 0 failures**, versus the ~1-in-20 failure rate of attempt 2 under identical load.

The full narrative, including exact numbers, is preserved in the docstring at the top of `backend/app/db/supabase_client.py` — read it before modifying that file.

**Also fixed:** three places doing sequential-independent-query anti-patterns, converted to `asyncio.gather(asyncio.to_thread(...))` (backend, since supabase-py is synchronous — plain `asyncio.gather` around blocking calls does *not* parallelize them) or `Promise.allSettled` (frontend):

- `/api/auth/me` — detail-table lookup + FPO check
- `/api/dashboard/buyer` — 4 independent queries
- `/api/dashboard/transporter` — 3 independent queries
- `/api/dashboard/farmer` — **deliberately left sequential**, and commented as such: its two queries have a genuine dependency (the second needs `crop_ids` from the first)
- `frontend/js/app.js` boot sequence — i18n init + Supabase config fetch
- `frontend/js/views/farmer/home.js` — dashboard fetch + matching-buyers fetch

**Measured result:** client construction 645ms -> ~0.15ms per request. Real end-to-end (click login -> rendered dashboard, in an actual browser): ~3.0 seconds for the farmer role.

---

## 9. Known issues / things a future session should know about

- **3 pre-existing test failures** — see §6, do not chase these unless asked.
- **DB password was printed to a terminal at some point** — should be rotated in Supabase dashboard (not yet done as of this writing).
- **`SETUP_GUIDE.md` has a stray, unexplained edit** — a line was found changed from `python scripts/apply_schema.py` to `pip install -r requirements.txt` in the working tree, not attributable to any of the work described in this file, and deliberately **left uncommitted** (excluded from the perf-fix commit) rather than silently fixed or silently shipped. Worth investigating/resolving if it resurfaces.
- **No frontend build step, no bundler.** This is a deliberate choice validated by the performance audit, not an oversight — do not "fix" this by introducing webpack/vite/etc. without a new, equally rigorous audit justifying it.
- **`backend/app/ml/` is intentionally empty.** No trained model exists. Don't add one without updating the honesty-labelling convention in §5 accordingly.
- Two demo-tree oddities from early setup are referenced in `WHATS_NEW.md` (an orphaned test account, and the second non-canonical tree at `C:\udgam_ai\Udgam`) — neither needs action, both are just background facts.

---

## 10. How to run everything

**Backend** (from `C:\udgam_ai\udgam.ai`) — must run on port **8001**, because the frontend hardcodes that as its default API base and nothing overrides it in local dev:
```powershell
C:\udgam_ai\Udgam\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8001
```

**Frontend** — no build step. Serve `frontend/` with any static file server (e.g. `python -m http.server` from inside `frontend/`), or open `frontend/index.html` directly. It talks to the backend via `window.__UDGAM_API_BASE__` if set, else falls back to `http://127.0.0.1:8001` (see `frontend/js/app.js`) — if you run the backend on a different port, set that global before `app.js` loads, or edit the fallback.

**Seed demo data** (idempotent, safe to re-run):
```powershell
C:\udgam_ai\Udgam\.venv\Scripts\python.exe scripts\seed_demo.py
```

**Apply/update the database schema:**
```powershell
C:\udgam_ai\Udgam\.venv\Scripts\python.exe scripts\apply_schema.py
```

**Run tests:**
```powershell
C:\udgam_ai\Udgam\.venv\Scripts\python.exe -m pytest -q
```

**Environment:** Supabase URL/keys and feature flags come from a `.env` file read by `backend/app/config.py`. Not committed to the repo (correctly — check `.gitignore`). A fresh clone will need this created before anything runs.

---

## 11. Git history (for orientation, oldest first)

```
bbae2a2  chore: establish verified baseline for SIH26132 work
802c1de  fix: land signed-in users on their own dashboard after login
b11b7c2  feat(market): SIH26132 Phase 1 — market data spine
ed6a7a4  feat(decisions): SIH26132 Phase 2 — Net Exit Optimizer
5f6ac63  feat(decisions): SIH26132 Phase 3 — Risk-Adjusted Sale Window
69eab74  fix(seed): resolve the demo transporter by stable email, make seeding idempotent
7b25c57  security(rls): require the transporter role to write transport_capacity
0987f09  security(rls): require the buyer role and request ownership to write aggregations
3135485  security(rls): break the aggregation policy recursion, add per-farmer consent
83406bc  feat(aggregations): SIH26132 Phase 4 — Dynamic Supply Aggregation
c6e1604  feat: SIH26132 Phases 5 & 6 — Emergency Exit Engine + Neutral Orchestration
6921abf  feat(ui): SIH26132 — Market Decision Center on the farmer dashboard
f9a080d  docs: plain-English guide to the SIH26132 work
e14fcac  feat: build the three placeholder pages, close the last RLS gaps, fix dead links
2ac0dec  perf: eliminate per-request Supabase client construction, parallelize independent queries
```

Each commit message is detailed and was written to be self-sufficient — `git show <hash>` on any of them explains the reasoning, not just the diff. Prefer reading the actual commit over re-deriving intent from the diff alone.

---

## 12. Where to look next, depending on the task

| If you need to... | Start here |
|---|---|
| Understand a feature from a user's perspective | `WHATS_NEW.md` |
| Change an RLS policy | `db/SCHEMA.sql` — read the existing policy comments first, they explain *why*, and check `backend/app/deps.py` to see how the JWT flows in |
| Add a new decision engine (like Net Exit Optimizer) | `backend/app/services/opportunity.py` (the shared contract) + `orchestration.py` (the ranking-factor rules you must not violate) |
| Touch `supabase_client.py` | Read its docstring in full first — two non-obvious concurrency hazards are documented there from hard-won experience |
| Add a frontend view | Look at an existing one in `frontend/js/views/farmer/` for the module shape (`render()` returns HTML string, `mount()` wires listeners), then register it in `routes.js` |
| Investigate "why is it slow" | Don't assume the frontend — see §8. Profile the actual backend-to-Supabase path first. |
| Run a full regression check | `pytest -q` (expect 230 passed / 3 known failures) + manually click through all three role dashboards in a browser (this project doesn't have frontend test automation) |
