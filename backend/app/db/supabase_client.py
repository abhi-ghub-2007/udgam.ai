"""Request-scoped Supabase clients.

PRD R-12: RLS plus a service-role client everywhere is RLS theatre. Every
request-scoped call goes through a client bound to the CALLER'S JWT, so the
policies in db/SCHEMA.sql section 13 are genuinely enforced by Postgres.

The service-role client lives in admin_client.py and is imported by exactly
two modules (A-12). Do not import it here.
"""
from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from ..config import settings
from ..errors import UpstreamUnavailable


def _require_config() -> None:
    if not settings.supabase_configured:
        # Deliberately vague: the browser never learns which variable is missing.
        raise UpstreamUnavailable("Database is not reachable right now.")


@lru_cache
def anon_client() -> Client:
    """Anon-key client. Signup and other pre-session calls only."""
    _require_config()
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


def user_client(access_token: str) -> Client:
    """Client bound to one user's JWT. auth.uid() resolves inside Postgres,
    so RLS applies. This is the default for all request-scoped work."""
    _require_config()
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.postgrest.auth(access_token)
    return client
