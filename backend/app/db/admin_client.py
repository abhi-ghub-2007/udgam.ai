"""Service-role client. BYPASSES ALL RLS.

A-12: this module and backend/scripts/seed_demo.py are the ONLY two places
allowed to touch SUPABASE_SERVICE_ROLE_KEY. tests/test_no_service_key_leak.py
fails the build if a third appears, or if a key-shaped string turns up under
frontend/.

Runtime callers, each a narrow, backend-validated write that legitimately
crosses an RLS ownership boundary a caller's own JWT-scoped client cannot:
POST /api/products/{id}/photo (routers/products.py) uploads the farmer's
graded photo to Storage, and POST /api/orders (routers/orders.py) reserves
quantity on the farmer's listing once a buyer's order has already been
validated against it.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from supabase import Client, create_client

from ..config import settings
from ..errors import UpstreamUnavailable

log = logging.getLogger("udgam.admin")


@lru_cache
def admin_client() -> Client:
    if not (settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY):
        raise UpstreamUnavailable("This action is unavailable right now.")
    log.info("Service-role client initialised (RLS bypassed - privileged path)")
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
