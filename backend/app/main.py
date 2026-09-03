"""UDGAM.ai FastAPI application.

Run:  .venv/Scripts/python -m uvicorn backend.app.main:app --reload --port 8000
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .errors import register_error_handlers
from .routers import (auth, buyer_matching, dashboard, market, notifications, orders,
                      products, profiles, transport)

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


@app.get("/", tags=["meta"])
async def root():
    return {"name": "UDGAM.ai", "version": app.version, "docs": "/docs"}
