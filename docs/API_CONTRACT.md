# API_CONTRACT.md

Opus planning-pass artifact (plan.md §9.2). Every endpoint needed to cover the
Section 10 Feature Matrix, each traceable back to the matrix row it serves.

**Base URL:** `/api` · **Auth:** `Authorization: Bearer <supabase_jwt>` unless marked
public · **Money:** integer paise · **Pagination:** `?limit=20&offset=0` on every list.

Matrix IDs use PRD notation, which is one-to-one with plan.md §10:
`F-n` farmer §10.1 · `B-n` buyer §10.2 · `T-n` transporter §10.3 · `C-n` common §10.4.

---

## 0. Conventions

**Error envelope.** Every non-2xx response, no exception:

```json
{ "error": { "code": "INVALID_STATE_TRANSITION",
             "message": "Order is DELIVERED; cannot transition to ACCEPTED.",
             "field": null } }
```

`js/core/api.js` is the only place that unwraps this. Codes in use:
`UNAUTHENTICATED` 401 · `FORBIDDEN` 403 · `NOT_FOUND` 404 · `VALIDATION_ERROR` 422 ·
`INVALID_STATE_TRANSITION` 409 · `DUPLICATE` 409 · `RATE_LIMITED` 429 ·
`UPSTREAM_UNAVAILABLE` 503 · `INTERNAL` 500.

A 503 from a missing integration key never names the environment variable (A-15).

**AI envelope.** Every AI/ML response carries an honesty label (A-17):

```json
{ "data": { ... },
  "method": "REAL",
  "model": { "name": "price_gbr", "version": "1.2.0", "trained_at": "...",
             "metric": {"name": "MAE_paise", "value": 118.4, "baseline": 197.0} },
  "data_source": "agmarknet" }
```

**Idempotency.** `POST` endpoints that move money or advance the order state machine
accept `Idempotency-Key: <uuid>` and replay the stored response (`idempotency_keys`).
Marked **⧉** below.

**Ownership.** Every protected endpoint depends on `get_current_user()`, which validates
the Supabase JWT and returns `(user_id, role)`. Database access uses a client bound to
that JWT so RLS is genuinely enforced (A-12). Router-level ownership checks are
duplicated on top — defence in depth, PRD §11.

---

## 1. `auth.py` — session, config, bootstrap

| Method | Path | Auth | Purpose | Matrix |
|---|---|---|---|---|
| GET | `/api/config` | public | Returns `{supabase_url, supabase_anon_key, languages, app_env}`. How the anon key reaches the browser without living in a committed file (A-16). **Never** returns the service-role key. | — |
| GET | `/api/health` | public | `{status, db, integrations:{mandi,weather,maps,payments,sms}}` — each `live` or `mock`. | — |
| POST | `/api/auth/register` | public | Completes signup after Supabase Auth creates the user. Body: `{role, full_name, phone, district, state, pincode, preferred_language, role_details{...}, kyc{...}}`. Creates `profiles` + the role detail row + `kyc_documents`. | C-1 |
| GET | `/api/auth/me` | ✔ | Current `profiles` row joined with its role detail row. The frontend's role-gate calls this on every page load. | C-1 |
| POST | `/api/auth/activate` | public | FPO-invited farmer sets their own password with the 6-digit invite code. `{invite_code, phone, new_password}` → `onboarding_status: 'active'`. | F-11 |

Login, logout, and token refresh are handled by the Supabase JS client in the browser
(permitted by plan.md §3). FastAPI never sees a password.

## 2. `profiles.py` — profile & ratings

| Method | Path | Auth | Purpose | Matrix |
|---|---|---|---|---|
| GET | `/api/profiles/{id}` | ✔ | Public profile card: name, role, district, `avg_rating`, `rating_count`, `verification_status`. Phone masked unless the caller shares an order at `ACCEPTED`+ (A-13). | C-1 |
| PATCH | `/api/profiles/me` | ✔ | Edit own details. | C-1 |
| GET | `/api/profiles/me/ratings` | ✔ | Own received feedback, paginated, with tag histogram. | C-1, F-8, B-5, T-8 |
| POST | `/api/profiles/me/storage-provider` | ✔ | Toggle `is_storage_provider`. Gate for T-9. | T-9 |
| GET | `/api/crops` | ✔ | Crop master with `name_en/hi/mr`. Cached client-side. | — |

## 3. `fpo.py` — FPO-only capability

| Method | Path | Auth | Purpose | Matrix |
|---|---|---|---|---|
| GET | `/api/fpo/summary` | ✔ FPO | Linked-farmer count, aggregate volume, aggregate value. | F-1 |
| GET | `/api/fpo/farmers` | ✔ FPO | Linked farmers + `onboarding_status`. | F-11 |
| POST | `/api/fpo/farmers` ⧉ | ✔ FPO | Invite a farmer: creates `auth.users` with no usable password, `profiles`, `farmer_profiles{onboarding_status:'invited'}`, sends a 6-digit code by SMS (mock). **The only runtime user of the service-role client** (A-12). Returns the profile; never a password. | F-11 |
| POST | `/api/fpo/farmers/{id}/resend-invite` | ✔ FPO | Re-sends the code. | F-11 |

There is no endpoint by which an FPO can write a member's products or orders. That
absence is the point (A-5).

## 4. `products.py` — farmer listings & marketplace

| Method | Path | Auth | Purpose | Matrix |
|---|---|---|---|---|
| GET | `/api/products` | ✔ | Marketplace browse. Filters: `crop_id, grade, min_qty, max_price, district, near=lat,lon&radius_km, sort`. | B-1 |
| GET | `/api/products/mine` | ✔ farmer | Own listings incl. drafts. | F-1, F-2 |
| POST | `/api/products` | ✔ farmer | Create. `{crop_id, quantity_kg, asking_price_paise, harvest_date, available_until, description, location_id}`. FPO-on-behalf passes `farmer_id` + is validated against A-5's invited-only rule. | F-2 |
| GET | `/api/products/{id}` | ✔ | Detail + latest `quality_grades` row + farmer card. | F-2, B-1 |
| PATCH | `/api/products/{id}` | ✔ owner | Update. RLS + router ownership check. | F-2 |
| DELETE | `/api/products/{id}` | ✔ owner | Soft-delete → `status='withdrawn'`. | F-2 |
| POST | `/api/products/{id}/photo` | ✔ owner | Registers a Storage path after direct browser upload, then synchronously runs AI-1 and writes `quality_grades` + `products.grade`. Returns the grade with its **feature breakdown** — the visible one from PRD §13 step 2. | F-2, AI-1 |

## 5. `buyer_matching.py` — requests, matching, aggregation

| Method | Path | Auth | Purpose | Matrix |
|---|---|---|---|---|
| POST | `/api/buyer-requests` | ✔ buyer | Post an open requirement. | B-3 |
| GET | `/api/buyer-requests` | ✔ | **All** open requests, not only matched ones — the F-6 requirement. Filters: `crop_id, district, min_qty, needed_by`. | F-6 |
| GET | `/api/buyer-requests/mine` | ✔ buyer | Own posted requests + fulfilment progress. | B-1, B-3 |
| PATCH | `/api/buyer-requests/{id}` | ✔ owner | Edit / cancel. | B-3 |
| GET | `/api/matching/buyers` | ✔ farmer | **Recommend Buyers.** Ranked buyers for the farmer's crops. Returns per-candidate `score` + a `reasons[]` breakdown (crop match, proximity km, rating, completion rate). `method: ALGORITHMIC`. | F-5 |
| GET | `/api/matching/listings` | ✔ buyer | Recommended listings for this buyer. | B-1 |
| GET | `/api/matching/requests` | ✔ farmer | Requests ranked by fit for a given product. | F-6 |
| POST | `/api/aggregations/suggest` | ✔ bulk buyer | Greedy bin-pack of listings against a request under a grade-variance constraint. Returns groups with combined price, combined transport cost, and `grade_variance_warning`. | B-7 |
| POST | `/api/aggregations/{id}/accept` ⧉ | ✔ buyer | Converts a suggested group into one multi-farmer order (A-4). | B-7 |
| GET | `/api/recommendations/sale-options` | ✔ farmer | Best-selling-option ranking across direct sale / aggregation / store-then-sell, scored on predicted price, transport cost, spoilage window, buyer reliability. | F-5, AI-4 |

## 6. `orders.py` — lifecycle & state machine

All transitions go through `app/services/state_machine.py`. Illegal transitions return
**409 `INVALID_STATE_TRANSITION`**. Every transition writes `order_status_history`.

| Method | Path | Auth | Purpose | Matrix |
|---|---|---|---|---|
| GET | `/api/orders` | ✔ | Own orders, role-aware. `?status=&role_view=` | F-1, B-1, T-1 |
| GET | `/api/orders/{id}` | ✔ participant | Full order + items + shipment + status timeline. | F-4, B-4 |
| POST | `/api/orders` ⧉ | ✔ | Create `DRAFT`→`PLACED`. Buyer-initiated from a listing, or farmer-initiated by accepting a buyer request. | B-1, F-6 |
| POST | `/api/orders/{id}/accept` ⧉ | ✔ counterparty | `PLACED → ACCEPTED`. Locks price, reserves `available_quantity_kg`, unmasks phone. | B-8 |
| POST | `/api/orders/{id}/cancel` | ✔ either, pre-pickup | `→ CANCELLED`. Refunds escrow, restores quantity. | B-8 |
| GET | `/api/orders/{id}/breakdown` | ✔ participant | **F-12 price breakdown.** `{farmer_payout, platform_fee, transport_cost, buyer_total, traditional_chain_price, farmer_share_pct, buyer_saving_pct}`. The screen that proves the PS claim. | F-12 |
| GET | `/api/orders/{id}/timeline` | ✔ participant | `order_status_history` — the auditability NFR, rendered as the tracking timeline. | F-4, B-4 |
| POST | `/api/orders/{id}/dispute` | ✔ buyer, ≤24h | `DELIVERED → DISPUTED` with a photo. Holds escrow release. | A-22 |

## 7. `payments.py` — escrow

| Method | Path | Auth | Purpose | Matrix |
|---|---|---|---|---|
| POST | `/api/orders/{id}/escrow` ⧉ | ✔ buyer | `ACCEPTED → PAYMENT_HELD`. Creates the provider order (Razorpay sandbox or mock) and a `payments` row at `held`. | B-8, PM-1 |
| POST | `/api/payments/webhook` | public, signed | Provider callback. Verifies the signature; mock provider posts to itself. | PM-1 |
| GET | `/api/payments/order/{id}` | ✔ participant | Payment + escrow status. | B-8 |

Escrow release is not a public endpoint — it fires as a side effect of the
`→ DELIVERED` transition, so funds cannot be released without proof of delivery.

## 8. `logistics.py` — capacity, consolidation, shipments, routing

Backed by the unified `transport_capacity` table (A-3); `capacity_type` selects between
the farmer-facing browse (F-7), the empty leg (T-5), and the scheduled route (T-6).

| Method | Path | Auth | Purpose | Matrix |
|---|---|---|---|---|
| GET | `/api/transport/capacity` | ✔ | Browse available transport. Filters `origin_district, dest_district, depart_after, min_capacity_kg, capacity_type`. | F-7 |
| POST | `/api/transport/capacity` | ✔ transporter | Post a scheduled route, empty leg, or on-demand availability — one endpoint, `capacity_type` discriminates. | T-5, T-6 |
| GET | `/api/transport/capacity/mine` | ✔ transporter | Own postings. | T-1, T-5, T-6 |
| PATCH | `/api/transport/capacity/{id}` | ✔ owner | Edit / cancel. | T-5, T-6 |
| POST | `/api/transport/requests` ⧉ | ✔ farmer/buyer | Request transport for an order → `PAYMENT_HELD → LOGISTICS_ASSIGNED`, creates `shipments`, notifies the transporter. Caller must match `orders.logistics_arranged_by` (PRD §6.6) else **403**. | F-7, B-6 |
| POST | `/api/consolidation` ⧉ | ✔ farmer | Farmer asks to join an existing capacity. | F-10 |
| GET | `/api/consolidation/inbound` | ✔ transporter | Pending requests against own capacity. | T-7 |
| POST | `/api/consolidation/{id}/respond` ⧉ | ✔ transporter | Accept or reject; on accept decrements `available_capacity_kg`. | T-7 |
| GET | `/api/shipments/mine` | ✔ transporter | Active jobs + upcoming pickups. | T-1 |
| GET | `/api/shipments/{id}` | ✔ participant | Pickup/drop addresses, contacts, cargo, time windows. | T-3 |
| POST | `/api/shipments/{id}/pickup` ⧉ | ✔ transporter | Confirm pickup with the **farmer OTP** → `PICKED_UP`. | T-3 |
| POST | `/api/shipments/{id}/ping` | ✔ transporter | Location ping → `shipment_locations`; first ping flips `→ IN_TRANSIT`. | F-4, B-4 |
| GET | `/api/shipments/{id}/track` | ✔ participant | Latest position + status + ETA. Polled every 10 s (A-24). | F-4, B-4 |
| POST | `/api/shipments/{id}/deliver` ⧉ | ✔ transporter | Enter the **buyer's 4-digit delivery OTP** → `DELIVERED`, releases escrow, unlocks feedback. The proof-of-delivery mechanism that works without an admin. | T-3, R-13 |
| POST | `/api/routes/optimize` | ✔ transporter | Multi-stop optimisation over assigned shipments. Returns ordered stops, `optimized_distance_km`, `naive_distance_km`, `distance_saved_pct`, and both polylines for the map. Persists a `route_plans` row. `method: ALGORITHMIC`, `solver: ortools_vrp \| nearest_neighbour_2opt`. | T-2 |
| GET | `/api/routes/eta` | ✔ | Per-option ETA, computed at request time, never cached (A-9). | B-6 |
| GET | `/api/transport/earnings` | ✔ transporter | Total + per-km, `?from=&to=`. Own rows only — a transporter never sees another's earnings. | T-4 |

## 9. `storage.py`

| Method | Path | Auth | Purpose | Matrix |
|---|---|---|---|---|
| GET | `/api/storage/listings` | ✔ | Browse storage. | F-4, ST-1 |
| POST | `/api/storage/listings` | ✔ `is_storage_provider` | Create. **403** without the flag. | T-9 |
| PATCH | `/api/storage/listings/{id}` | ✔ owner | Edit. | T-9 |
| POST | `/api/storage/bookings` ⧉ | ✔ farmer | Book capacity. | F-4, ST-2 |
| GET | `/api/storage/bookings/mine` | ✔ | Own bookings (farmer) or bookings against own listings (provider). | F-4 |
| POST | `/api/storage/bookings/{id}/status` | ✔ | Confirm / activate / complete. | ST-2 |

## 10. `pricing_demand.py` — AI-2, AI-3

| Method | Path | Auth | Purpose | Matrix |
|---|---|---|---|---|
| GET | `/api/pricing/predict` | ✔ | `?crop_id=&district=&horizon_days=14`. Current estimate + 14-day forward + confidence interval + **mandi reference price** alongside. Same engine both sides; framing differs in the UI only. | F-9, B-2 |
| GET | `/api/pricing/history` | ✔ | Observed mandi series for the chart. | F-9, B-2 |
| GET | `/api/demand/forecast` | ✔ farmer | `?crop_id=&district=`. 4-week horizon + plain-language recommendation line + **MAE against the seasonal-naive baseline** (a model that cannot beat naive is not a result). | F-3 |
| GET | `/api/models` | ✔ | `model_runs` rows — makes every honesty label auditable. | A-17 |

## 11. `feedback.py`

| Method | Path | Auth | Purpose | Matrix |
|---|---|---|---|---|
| POST | `/api/feedback` ⧉ | ✔ participant | Rate a counterparty. **422** unless the order is `DELIVERED`; **409** on a second rating of the same party (unique constraint). Body `{order_id, ratee_id, rating, tags[], comment}`. Recomputes `profiles.avg_rating`. Both feedbacks (or 72h) → `CLOSED`. | F-8, B-5, T-8 |
| GET | `/api/feedback/pending` | ✔ | Delivered orders still awaiting this user's rating — drives the dashboard nudge. | F-8, B-5, T-8 |
| GET | `/api/feedback/profile/{id}` | ✔ | Received feedback for a profile. | F-5, C-1 |

## 12. `notifications.py`

| Method | Path | Auth | Purpose | Matrix |
|---|---|---|---|---|
| GET | `/api/notifications` | ✔ | Own only — role scoping is structural, `user_id = auth.uid()`. Returns i18n keys + params (A-11). | C-4 |
| GET | `/api/notifications/unread-count` | ✔ | Bell badge. | C-4 |
| POST | `/api/notifications/{id}/read` | ✔ owner | Mark read. | C-4 |
| POST | `/api/notifications/read-all` | ✔ | Mark all read. | C-4 |

## 13. `assistant.py` — C-3

| Method | Path | Auth | Purpose | Matrix |
|---|---|---|---|---|
| POST | `/api/assistant/ask` | ✔ | `{text, lang}` → rules/FAQ intent match, LLM fallback. Returns `{reply, intent, confidence, quick_actions[], source: 'faq'\|'llm'}`, role-scoped. | C-3 |
| POST | `/api/assistant/parse-listing` | ✔ farmer | Voice-driven listing: `"मेरे पास 200 किलो टमाटर हैं"` → `{crop_id, quantity_kg, confidence}` for a **pre-filled, user-confirmed** form. Never creates a listing directly. | C-3 |

Speech-to-text and text-to-speech are browser-side Web Speech API. Every voice
affordance has a typed equivalent (A-21).

## 14. `dashboard.py` — aggregate reads

One call per dashboard instead of eight, because PRD §11 budgets first meaningful paint
at ≤ 2.5 s on simulated 3G. The response is the payload cached in `localStorage` for
C-5's stale-data banner.

| Method | Path | Auth | Purpose | Matrix |
|---|---|---|---|---|
| GET | `/api/dashboard/farmer` | ✔ farmer | Listings summary, relevant open requests, active orders, month earnings, FPO block if applicable. | F-1 |
| GET | `/api/dashboard/buyer` | ✔ buyer | Active orders, saved farmers, posted requests, recommended listings. | B-1 |
| GET | `/api/dashboard/transporter` | ✔ transporter | Active jobs, upcoming pickups, earnings summary, pending consolidation requests. | T-1 |
| GET | `/api/metrics/impact` | ✔ | The §12 numbers computed from live rows: intermediary steps removed, farmer share of consumer rupee, buyer price vs. mandi reference, route distance saved, price-transparency rate. | §12 |

## 15. Static / i18n

| Method | Path | Auth | Purpose | Matrix |
|---|---|---|---|---|
| GET | `/i18n/{lang}.json` | public | `en` · `hi` · `mr`. Served as a static asset, fetched once, cached in `localStorage`. | C-2 |

---

## Coverage check

Every matrix row maps to at least one endpoint above.

| Row | Endpoints |
|---|---|
| F-1 | `/dashboard/farmer`, `/products/mine`, `/orders`, `/fpo/summary` |
| F-2 | `/products` CRUD, `/products/{id}/photo` |
| F-3 | `/demand/forecast` |
| F-4 | `/shipments/{id}/track`, `/orders/{id}/timeline`, `/storage/bookings/mine` |
| F-5 | `/matching/buyers`, `/recommendations/sale-options` |
| F-6 | `/buyer-requests`, `/matching/requests` |
| F-7 | `/transport/capacity`, `/transport/requests` |
| F-8 | `/feedback`, `/feedback/pending` |
| F-9 | `/pricing/predict`, `/pricing/history` |
| F-10 | `/consolidation` |
| F-11 | `/fpo/farmers`, `/auth/activate` |
| F-12 | `/orders/{id}/breakdown` |
| B-1 | `/dashboard/buyer`, `/products`, `/matching/listings` |
| B-2 | `/pricing/predict` |
| B-3 | `/buyer-requests` |
| B-4 | `/shipments/{id}/track` |
| B-5 | `/feedback` |
| B-6 | `/routes/eta` |
| B-7 | `/aggregations/suggest`, `/aggregations/{id}/accept` |
| B-8 | `/orders/{id}/accept`, `/orders/{id}/escrow` |
| T-1 | `/dashboard/transporter`, `/shipments/mine` |
| T-2 | `/routes/optimize` |
| T-3 | `/shipments/{id}`, `/pickup`, `/deliver` |
| T-4 | `/transport/earnings` |
| T-5 | `/transport/capacity` (`empty_leg`) |
| T-6 | `/transport/capacity` (`scheduled_route`) |
| T-7 | `/consolidation/inbound`, `/consolidation/{id}/respond` |
| T-8 | `/feedback` |
| T-9 | `/storage/listings`, `/profiles/me/storage-provider` |
| C-1 | `/profiles/me`, `/profiles/{id}`, `/auth/me` |
| C-2 | `/i18n/{lang}.json` |
| C-3 | `/assistant/ask`, `/assistant/parse-listing` |
| C-4 | `/notifications` |
| C-5 | `/dashboard/*` (cached payload) |
