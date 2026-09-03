# ASSUMPTIONS.md

Opus planning-pass artifact (plan.md §9.4). Every ambiguity found while producing
`db/SCHEMA.sql`, `docs/API_CONTRACT.md`, and `docs/MODULE_ORDER.md`, resolved as a
**decision** — not left as an open question for the execution pass to guess at.

Conflict rule in force: **`plan.md` wins over the PRD.** Where the PRD adds something
`plan.md` does not contradict, the addition is kept (plan.md §7 explicitly says
"minimum viable, extend as needed").

---

## A-0. The repository did not match the brief

Recorded because it changes what "Phase 1 step 4" can mean.

| Claim in the execution prompt | Actual state on disk | Resolution |
|---|---|---|
| "All API keys are already configured in `D:\Udgam\.env`. This file exists and is populated." | No `.env`, no `.gitignore`, not a git repo. | `.gitignore` and `.env.example` written; `git init` run; `.env` verified ignored by creating a throwaway one and checking `git status --porcelain --ignored`. The real `.env` is the user's to populate. |
| "A UI/UX skill folder exists at `D:\Udgam`." | Three upstream git clones dumped in the project root (`headroom` 139 MB, `ui-ux-pro-max-skill` 29 MB, `superpowers` 6.5 MB). | Six skills copied to `D:\Udgam\.claude\skills\` (4 MB, project-wide scope); the clones moved to `D:\Udgam-tools\`. `ui-styling` was deliberately **not** copied — it teaches shadcn/Tailwind, which §5 of the PRD forbids here. |
| Stitch code is "frontend code" to wire up. | Eight `code.html` files, each loading `cdn.tailwindcss.com` + Google Fonts Material Symbols. | See A-1. |

---

## A-1. Stitch output is a visual reference, not source

Every Stitch `code.html` loads Tailwind from a CDN and Material Symbols from Google
Fonts. plan.md §3 mandates vanilla HTML/CSS/JS with no framework; PRD §5 lists Tailwind
under *explicitly excluded*; PRD §10 warns that a demo depending on live third-party
requests over venue wifi is a demo that fails.

**Decision:** the eight screens are preserved at `design_reference/` as PNG + HTML and
treated as **visual specification**. Every screen is re-implemented in vanilla CSS
against `css/tokens.css`. Material Symbols are replaced by a small inline SVG sprite
committed to the repo — zero network dependency at demo time.

`design_reference/udgam.ai/DESIGN.md` is the design authority, and it is a real
Material-3-style token set. It transfers verbatim into `css/tokens.css`: primary
`#2D6A4F`, background `#F9F7F2`, ink `#1B1C19`, 48px minimum tap target (52px for
primary actions), 16px minimum body text, 1.5× minimum line-height, 1.5px borders over
shadows, 12px/16px/9999px radius scale, 8px spacing rhythm.

Where `DESIGN.md` and the `ui-ux-pro-max` skill disagree, **`DESIGN.md` wins** — it is
project-specific and the skill is generic. Note the two are already consistent on the
points that matter (`DESIGN.md` requires 48px targets, the skill's priority-2 rule
requires ≥44px; the stricter number governs).

## A-2. Stitch covers eight screens; the matrix needs about thirty

Present: landing, farmer signup, farmer dashboard, buyer dashboard, AI quality grading,
demand forecasting, live order tracking, voice assistant.

Absent: **all nine transporter screens (T-1…T-9)**, the entire order/escrow/checkout
chain, profile, feedback, the transport marketplace, price breakdown (F-12), and the FPO
invite flow. Roughly two-thirds of the UI is new build, not integration. The audit
required by the execution prompt's Section 3 Step A lives in
`docs/FEATURE_MATRIX_AUDIT.md` and is produced at the start of the frontend phase.

---

## A-3. `routes` and `empty_legs` become views, not tables

plan.md §7 names `routes` and `empty_legs` as tables. PRD R-7 argues they and F-7 are
three views of one object and unifies them as `transport_capacity`.

**Decision:** unified table + two `CREATE VIEW`s carrying the original names. plan.md's
vocabulary survives verbatim, the PRD's build saving is realised, and no code has to
choose between them. A third table, `route_plans`, stores AI-6 output — plan.md's
`routes` name was doing double duty for "a route a transporter posts" and "an optimised
route the solver produced"; those are different objects and now have different homes.

## A-4. An aggregated order has no single farmer

`orders.farmer_id` is nullable and means *the sole farmer, or NULL when the order spans
several*. Participants on an aggregated order come from `order_items.farmer_id`. This
keeps the PRD §9 index `orders(farmer_id, status)` meaningful for the common
single-source case while letting B-7 aggregation produce one order across four farmers.
`public.is_order_participant()` folds both cases into one predicate that every
order-adjacent RLS policy reuses.

## A-5. FPO is a flag, not a fourth role

The role enum is exactly `farmer | buyer | transporter` (plan.md §4, §2 non-goals: no
admin). A profile **is** an FPO iff a row exists in `fpos` keyed by its id. The FPO
account also gets a `farmer_profiles` row so it can list on behalf of invited members.

Per PRD R-3, the FPO gets **read + aggregate** rights over linked farmers and never
write rights on their `products` or `orders` — enforced in `farmer_profiles_select`
(`fpo_id = auth.uid()`) with no matching write policy. The one exception is encoded
directly in `products_insert`: an FPO may insert a product for a member **only** while
that member's `onboarding_status = 'invited'`, and the row is stamped
`listed_by_fpo_id` so the "listed by FPO" badge is not optional.

This is a deliberate override of plan.md §4.1/§10.1, which has the FPO creating farmer
logins outright. That design hands an FPO the farmer's password and rebuilds the exact
power asymmetry the product exists to remove. The PRD caught it (R-3); the invite flow
is the safer and more defensible reading of the same requirement, and the FPO still gets
the capability plan.md asked for.

## A-6. Money is integer paise, everywhere

No floats in any monetary column, request body, or response. Rupee formatting happens
once, in the frontend i18n layer. Fees per PRD §3.1: `platform_fee_paise` = 2% of
subtotal (buyer pays), `logistics_facilitation_fee_paise` = 1% off the transporter
payout. Both are stored, both render in F-12 — otherwise "transparent pricing" is a slide
claim rather than a screen.

## A-7. `traditional_chain_price_paise` is a stored comparator, not a live scrape

The §12 metric "farmer share of consumer rupee, ~28% → ~70%" needs a baseline. Storing a
per-order comparator computed at order time from the mandi reference price makes the
number reproducible during judging. Deriving it live would make the headline metric
depend on a third-party API at the worst possible moment.

## A-8. Prices table holds observed history *and* predictions

One table, discriminated by `is_prediction`. A partial unique index enforces one
observed row per (crop, district, date) while allowing many predictions at different
horizons. Avoids a near-duplicate `predicted_prices` table.

## A-9. ETA is computed at request time, never cached

Per plan.md §9's own worked example. An ETA cached against a stale route or an
unassigned transporter is worse than no ETA. B-6 calls the route service per option per
request; the input set is small enough (≤ 10 options) that this is cheap.

## A-10. Grades are A/B/C only; the buyer may overwrite at delivery

`quality_grade` enum is `A|B|C`. `order_items.confirmed_grade` holds the buyer's
confirmation at delivery, which is what makes PRD §2.1's "quality assessment" row an
actual replacement for the middleman rather than a claim. Disagreement between `grade`
and `confirmed_grade` is what a `DISPUTED` order is about.

## A-11. Notifications store i18n keys, not sentences

`notifications.title_key` / `body_key` + a `params` jsonb, rendered client-side through
`t()`. A notification written in English at insert time cannot follow the language
switcher, and C-2 requires the whole UI to flip mid-demo (PRD §13 step 9).

## A-12. The service-role key is confined to exactly two files

PRD R-12: RLS plus a service-role client everywhere is RLS theatre. Therefore:

- Every request-scoped database call goes through a Supabase client **bound to the
  caller's JWT**, so the policies in §13 of `SCHEMA.sql` are genuinely enforced.
- `SUPABASE_SERVICE_ROLE_KEY` is imported by exactly two modules:
  `backend/app/db/admin_client.py` and `backend/scripts/seed_demo.py`.
- The only runtime use of the admin client is the FPO invite endpoint
  (`POST /api/fpo/farmers`), which must create an `auth.users` row.
- A test in `tests/test_no_service_key_leak.py` greps the tree and fails if the variable
  is referenced anywhere else, or if any string matching a Supabase key shape appears
  under `frontend/`.

## A-13. Phone numbers are masked until `ACCEPTED`

PRD §11. RLS cannot hide one column, so masking is applied in the Pydantic response
model: `profiles.phone` serialises as `+91 ·····  4321` unless the caller shares an order
with that profile at status `ACCEPTED` or later. Recorded here because it is a security
requirement that deliberately lives *outside* RLS, which is exactly the kind of thing
that gets silently dropped.

## A-14. OTPs are stored hashed

`orders.delivery_otp_hash` and `shipments.pickup_otp_hash` hold a bcrypt hash. The
plaintext is returned exactly once, to the party who must recite it (buyer for delivery,
farmer for pickup), and never logged. An OTP readable from the database is not proof of
anything.

## A-15. `USE_MOCK_INTEGRATIONS=true` is the default

PRD §10. Every external service has a `Mock` implementation behind an interface in
`backend/app/services/external/`. The full demo runs with **zero** external keys present.
A missing key logs one clear line
(`"AGMARKNET_API_KEY not set — using committed CSV snapshot"`) and degrades; it never
crashes and never names the missing variable in a response to the browser.

## A-16. `SUPABASE_ANON_KEY` reaches the browser via `GET /api/config`

The frontend needs the anon key for Supabase Auth session handling and Storage uploads —
both explicitly permitted by plan.md §3. The anon key is publishable by design and
powerless without RLS. It is nevertheless **not hardcoded into any committed file**;
the backend serves it at runtime. This keeps the execution prompt's "zero secret exposure
in any frontend file" rule literally true, and means rotating the key touches `.env`
only. The service-role key never leaves the server under any circumstance.

## A-17. Honesty labels ship in the payload

Per PRD R-9, every AI response carries `"method"`: `REAL` (price, demand — trained on
Agmarknet data), `HEURISTIC` (image grading — OpenCV feature table, deliberately not a
CNN), `ALGORITHMIC` (matching, recommendation, routing), `SYNTHETIC` (any model that fell
back to generated training data). The UI renders the label. Calling six things "AI" when
four are deterministic algorithms is how a technical judge is lost.

## A-18. Mandi data is a committed CSV snapshot

`backend/data/mandi_prices.csv`, committed. `services/external/mandi.py` refreshes it and
is **not on the demo path** (PRD R-10). If the data.gov.in resource cannot be reached
during the build, training falls back to generated data and every affected payload
carries `method: SYNTHETIC` plus `data_source: "synthetic"` — visible in the UI, stated
in the README. The fallback is labelled, never disguised.

## A-19. Languages are English, Hindi, Marathi

plan.md §10.4 says "English + Hindi + one regional language"; the PRD names Marathi. The
demo is set in Nashik/Pune (PRD §13), so Marathi is the coherent choice. `crops` carries
`name_en`/`name_hi`/`name_mr` because crop names are the strings a low-literacy farmer
most needs in their own language.

## A-20. i18n keys exist from the first screen

Per the execution prompt's quality gate: no literal user-facing string is ever written
into markup, even before translations are filled. `t('farmer.dashboard.title')` from the
first commit. Retrofitting i18n across thirty screens in Phase 6 is the single most
predictable way to lose a day.

## A-21. Voice input needs a typed fallback on the demo path

PRD §14: the Web Speech API requires a network round-trip in Chrome. Every voice
affordance is paired with a typed equivalent, and the demo script does not depend on the
microphone. The voice moment is a bonus, not a load-bearing step.

## A-22. `DISPUTED` resolves by mutual confirmation

There is no admin (plan.md §2), so a dispute holds escrow release and clears only when
both parties confirm, or after a 72-hour timeout that releases to the farmer. Stated
plainly in the pitch as a v1 limitation rather than dressed up as arbitration.

## A-23. Pagination is default 20, cursor-less

`?limit=&offset=` on every list endpoint (PRD §11). Offset pagination is adequate at
hackathon data volumes and keeps the vanilla-JS client trivial.

## A-24. Realtime is polling first

Live tracking (F-4, B-4) polls `GET /api/shipments/{id}/track` every 10 s, with Supabase
Realtime as a progressive enhancement layered on afterwards. Polling degrades correctly on
bad rural bandwidth and cannot break the demo; a dropped websocket can.

---

## Carried forward from plan.md §15 — confirmed as final

| Original item | Status |
|---|---|
| Multilingual capped at EN + HI + one regional | **Confirmed**, regional = Marathi (A-19) |
| Voice assistant is rules/FAQ + LLM fallback, not a trained model | **Confirmed**, plus mandatory typed fallback (A-21) |
| Real-vs-synthetic training split stated in the build summary | **Confirmed and tightened**: also surfaced in the UI per payload (A-17) |
| Payment + SMS run sandbox/test mode | **Confirmed**, and mock is the *default* (A-15) |
