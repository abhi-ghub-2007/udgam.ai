"""Service-role client. BYPASSES ALL RLS.

A-12: this module and backend/scripts/seed_demo.py are the ONLY two places
allowed to touch SUPABASE_SERVICE_ROLE_KEY. tests/test_no_service_key_leak.py
fails the build if a third appears, or if a key-shaped string turns up under
frontend/.

Its single runtime caller is POST /api/fpo/farmers, which must create an
auth.users row for an invited farmer.
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
