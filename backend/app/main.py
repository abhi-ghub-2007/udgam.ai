"""UDGAM.ai FastAPI application.

Run:  .venv/Scripts/python -m uvicorn backend.app.main:app --reload --port 8000
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .errors import NotFound, register_error_handlers
from .routers import (aggregations, auth, buyer_matching, dashboard, decisions, forecast,
                      market, notifications, orders, products, profiles, reviews, transport)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

app = FastAPI(
    title="UDGAM.ai API",
    description="Direct farmer-to-buyer agricultural marketplace (SIH26033).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(auth.router)
app.include_router(profiles.router)
app.include_router(products.router)
app.include_router(buyer_matching.router)
app.include_router(dashboard.router)
app.include_router(orders.router)
app.include_router(transport.router)
app.include_router(notifications.router)
app.include_router(market.router)
app.include_router(forecast.router)
app.include_router(decisions.router)
app.include_router(aggregations.router)
app.include_router(reviews.router)


@app.get("/", tags=["meta"])
async def root():
    return {"name": "UDGAM.ai", "version": app.version, "docs": "/docs"}


# ---------------------------------------------------------------------------
# Optional SPA hosting.
#
# The React frontend is a single-page app: a hard refresh on /farmer/decisions
# asks the SERVER for that path, and a plain static host answers 404 because no
# such file exists. Mounting the built bundle here with an index.html fallback
# makes `uvicorn backend.app.main:app` able to serve the whole product from one
# origin, which also sidesteps CORS entirely in production.
#
# This block is deliberately:
#   - additive       -- it registers AFTER every API router, so it can never
#                       shadow an /api/* route;
#   - opt-in         -- it does nothing at all until `frontend/dist` exists, so
#                       local API-only development is unaffected;
#   - non-exclusive  -- deploying the frontend to a separate static host
#                       (Vercel/Netlify/Pages) still works exactly as before.
# ---------------------------------------------------------------------------
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if _DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="spa-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """Serve the SPA shell for any non-API path.

        An unknown /api/* path must still 404 as JSON rather than silently
        returning HTML -- otherwise a typo'd endpoint would look like a
        working page to the caller.
        """
        if full_path.startswith("api/"):
            raise NotFound("That endpoint does not exist.")
        candidate = (_DIST / full_path).resolve()
        # Only serve real files that are genuinely inside dist -- this guards
        # the mount against path traversal (`..%2f` and friends).
        if full_path and candidate.is_file() and candidate.is_relative_to(_DIST):
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
