"""Request-scoped Supabase clients.

PRD R-12: RLS plus a service-role client everywhere is RLS theatre. Every
request-scoped call goes through a client bound to the CALLER'S JWT, so the
policies in db/SCHEMA.sql section 13 are genuinely enforced by Postgres.

The service-role client lives in admin_client.py and is imported by exactly
two modules (A-12). Do not import it here.

PERFORMANCE (frontend-audit finding, backend fix)
--------------------------------------------------
`user_client()` runs on every authenticated request (deps.py:get_identity).
Measured cost of `supabase.create_client()` on this stack: 280-650ms per call,
almost entirely `httpx.Client()` building a fresh `ssl.SSLContext` -- Python's
ssl module re-parses the OS/CA trust store on every construction, it is not
cached across instances. Confirmed in isolation: `ssl.create_default_context()`
alone costs ~30ms once; reusing that context via `httpx.Client(verify=ctx)`
drops subsequent construction to ~0.1ms.

`supabase.create_client()` exposes no hook for injecting a shared SSLContext
(ClientOptions has no `verify` field), and it additionally spins up a GoTrue
auth sub-client we never use here -- the backend only ever calls `.table()`
on a request-scoped client (never `.storage`/`.auth`/`.rpc`; those go through
admin_client() or the browser's own Supabase session). So user_client() is
built directly against postgrest-py, which supabase.Client.table() itself
just delegates to, and gets the same `.table()` / `.auth()` surface every
router already calls -- no router changes needed.

SAFETY -- two distinct hazards, both verified directly rather than assumed:

1. The SyncPostgrestClient INSTANCE must never be shared across requests or
   threads. BasePostgrestClient.auth() mutates
   `self.session.headers["Authorization"]` in place, so two concurrent
   requests sharing one instance could run one user's query under another
   user's bearer token. Every call to user_client() returns a fresh instance.

2. The ssl.SSLContext, however, is NOT safe to share across truly
   *concurrent* first-use handshakes either, despite being the standard
   advice for the sequential-reuse case. Sharing ONE global SSLContext across
   several threads issuing genuinely simultaneous requests (the whole point
   of parallelising independent dashboard queries -- see routers/dashboard.py
   and routers/auth.py) intermittently produced a live, reproducible
   `httpx.ConnectError: [SSL: TLSV1_ALERT_DECODE_ERROR]` -- a corrupted TLS
   handshake, not a Python-level race, so `threading.Lock` around client
   construction would not have caught it (the corruption happens inside the
   handshake itself, on first `.execute()`, not at construction).

   The fix actually shipped: one context PER THREAD, cached in
   threading.local() and built lazily on that thread's first use. A thread
   pool (FastAPI/asyncio.to_thread's default executor) reuses its worker
   threads across requests, so each worker still pays the ~30ms context cost
   only once for the life of the process, but two contexts are NEVER touched
   by two threads at the same instant. Verified with 60 rounds of the exact
   4-way-concurrent fan-out routers/dashboard.py now performs: 0 failures,
   versus an ~1-in-20 failure rate with one shared global context under the
   same load.
"""
from __future__ import annotations

import ssl
import threading
from functools import lru_cache

from postgrest import SyncPostgrestClient
from postgrest.constants import DEFAULT_POSTGREST_CLIENT_HEADERS
from supabase import Client, create_client

from ..config import settings
from ..errors import UpstreamUnavailable

# One SSLContext per worker thread, never shared across threads. See "SAFETY"
# above for why a single process-wide context is NOT safe here despite being
# the usual httpx advice -- do not consolidate this into a plain module-level
# context, and do not share the SyncPostgrestClient instance itself.
_thread_local = threading.local()


def _thread_ssl_context() -> ssl.SSLContext:
    ctx = getattr(_thread_local, "ssl_context", None)
    if ctx is None:
        ctx = ssl.create_default_context()
        _thread_local.ssl_context = ctx
    return ctx


def _require_config() -> None:
    if not settings.supabase_configured:
        # Deliberately vague: the browser never learns which variable is missing.
        raise UpstreamUnavailable("Database is not reachable right now.")


@lru_cache
def anon_client() -> Client:
    """Anon-key client. Signup and other pre-session calls only.

    lru_cache'd, so this pays the full create_client() cost exactly once per
    process -- unlike user_client() it is not on the per-request hot path, so
    it is left as the full supabase.Client rather than the lighter postgrest
    client below.
    """
    _require_config()
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


def user_client(access_token: str) -> SyncPostgrestClient:
    """Client bound to one user's JWT. auth.uid() resolves inside Postgres,
    so RLS applies. This is the default for all request-scoped work.

    Returns a postgrest SyncPostgrestClient rather than a full supabase.Client
    -- see module docstring. `.table(...)` behaves identically either way:
    supabase.Client.table() is a one-line delegation to this same class.
    """
    _require_config()
    client = SyncPostgrestClient(
        f"{settings.SUPABASE_URL}/rest/v1",
        headers={**DEFAULT_POSTGREST_CLIENT_HEADERS, "apiKey": settings.SUPABASE_ANON_KEY},
        schema="public",
        verify=_thread_ssl_context(),
    )
    client.auth(access_token)
    return client
