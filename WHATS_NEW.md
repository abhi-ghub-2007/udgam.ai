# What's New — SIH26132

Plain-English guide to what was added and how to use it.

---

## 1. What this work was for

The old UDGAM helped a farmer **list** produce and find a buyer.

The new problem statement (SIH26132) asks a harder question:

> "Given my crop, my quantity, my location, today's prices, transport costs and
> risk — **what is the best way and time for me to sell?**"

So the platform now answers that. Nothing that worked before was removed or
rebuilt. Everything below is an addition.

---

## 2. What was added, in plain words

### The Market Decision Center
A new page for the farmer. Pick one of your crop lots, and it tells you three
things:

1. **Best exit** — the best way to sell it, with the full sum shown
2. **Sell now or wait?** — whether holding the crop is actually worth it
3. **Nearby markets** — what each market is paying, and how far away it is

### Five engines behind it

| Engine | What it does |
|---|---|
| **Net Exit Optimizer** | Works out what you actually take home from each option, not just the sticker price |
| **Risk-Adjusted Sale Window** | Compares selling today vs waiting 3, 7, 14 days |
| **Dynamic Supply Aggregation** | Combines several small farmers to fill one big buyer order |
| **Emergency Exit** | If a buyer cancels, finds your crop a new home |
| **Neutral Orchestration** | Guarantees no buyer or market is secretly favoured |

### The important idea: highest price ≠ best deal

A far-away mandi may offer more per kg, but after transport, commission and
spoilage you can end up with **less**. The system does that whole sum for you
and shows every line, so you can see why.

Real example from your own demo data (420 kg of tomato):

```
  Gross sale value        ₹10,080.00   (paid by the buyer)
  Platform fee             −₹201.60    (paid by the buyer)
  Transport              −₹2,027.40    (paid by the buyer)
  Expected spoilage        −₹720.00    ← you pay this
  ─────────────────────────────────
  YOU TAKE HOME           ₹9,360.00
```

And the comparison it made:

```
  Direct buyer (Sunita)    ₹9,360.00   ← best
  Nashik mandi             ₹7,054.95
  Aurangabad mandi         ₹5,816.78
  Nagpur mandi            −₹2,526.17   ← 566 km away, you'd lose money
```

---

## 3. How to run it

You need **two terminals**, both opened in `C:\udgam_ai\udgam.ai`.

**Terminal 1 — the backend:**

```powershell
C:\udgam_ai\Udgam\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8001
```

**Terminal 2 — the website:**

```powershell
C:\udgam_ai\Udgam\.venv\Scripts\python.exe -m http.server 3000 --directory frontend
```

**Then open:**

```powershell
Start-Process "http://127.0.0.1:3000/index.html"
```

> **Port 8001 is not optional.** The website looks for the backend there.
> Use **3000** for the website — other ports are blocked by CORS.

---

## 4. How to use it

1. Log in as **`demo.farmer@udgam.test`**, password **`Udgam@1234`**
2. On the dashboard, click **Market Decision Center** (or use the left sidebar)
3. Pick a crop lot from the dropdown
4. Read the three cards

Click **"Compare all 6 options"** to see every market side by side, and
**"3 options we could not compare"** to see what was left out and why.

Other logins: `demo.buyer@udgam.test`, `demo.transporter@udgam.test`
(same password).

---

## 5. Being honest about the data

This matters if judges ask.

**There is no live mandi price feed, and no trained prediction model.** The
market prices are **generated**. So every price carries a label saying so:

| Label | Meaning |
|---|---|
| **Simulated** | Made-up data for the demo. Not a real market price. |
| **Estimated** | A forecast, not an observation |
| **Algorithm** | Worked out by arithmetic, not by AI |

Nothing is ever labelled "Real" unless it genuinely is. If the system doesn't
know something, it says so instead of guessing — for example, if no transport
is available for a route, that market is **excluded** from the comparison
rather than being shown as if transport were free.

**What is real:** your listings, buyers, requirements, orders, transport routes
and storage — all of it is live data from your Supabase database.

---

## 6. Things worth knowing

**After changing any frontend file, press Ctrl+Shift+R.** The browser caches
the old code otherwise, and your fix will look like it didn't work.

**Port 5500 may also be running** from testing. Ignore it — use 3000. Mixing
them shows you an older version of the site.

**If port 8001 answers but the new pages 404**, an old server is stuck on it:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'multiprocessing' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

**To check everything is healthy:**

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/health | ConvertTo-Json -Compress
```

You want to see `"db":"up"`.

**To run the tests** (expect `230 passed, 3 failed` — those 3 failed before this
work started and are unrelated):

```powershell
C:\udgam_ai\Udgam\.venv\Scripts\python.exe -m pytest -q
```

**To put the demo data back** after a database reset:

```powershell
C:\udgam_ai\Udgam\.venv\Scripts\python.exe -c "from scripts.seed_demo import seed_logistics_and_storage, seed_market_prices; seed_logistics_and_storage(); seed_market_prices()"
```

---

## 7. Security fixes made along the way

Five real holes were found and closed:

1. **Anyone could post transport routes.** A farmer could invent a fake cheap
   truck to make their own numbers look better. Now only transporters can.
2. **Anyone could create a buyer's group order.** Now only that buyer can, and
   only against their own requirement.
3. **The group-order tables were completely unusable** — the database threw an
   error every time they were read. Fixed.
4. **Anyone could post a buyer requirement.** A farmer or transporter could
   create one naming themselves as the buyer. Now only buyers can.
5. **Anyone could create a transporter route plan.** Now only transporters can.

None of these were caused by this work; they were already there.

---

## 8. Still to do

- **Rotate your database password.** It was printed to a terminal during setup.
  Supabase → Settings → Database. It was never saved into the code.
- Only 6 crops have market prices. The others correctly say "no data" rather
  than inventing a number.

---

## 9. Where the code lives

```
backend/app/services/    the five engines
backend/app/routers/     the web endpoints
frontend/js/views/farmer/decisions.js    the Market Decision Center page
tests/                   1,900+ lines of tests
db/SCHEMA.sql            database structure and security rules
```

Backups of the whole project:
`C:\udgam_ai\udgam-ai-source.zip` and `C:\udgam_ai\udgam-ai-repo.bundle`
