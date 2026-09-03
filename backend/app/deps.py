"""Auth dependency. Every protected endpoint hangs off get_current_user.

Validates the Supabase JWT, resolves the caller's role from `profiles`, and
hands back a client BOUND TO THAT JWT so RLS is enforced by Postgres rather
than trusted to the router (A-12, PRD R-12).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Header
from supabase import Client

from .db.supabase_client import user_client
from .errors import Forbidden, Unauthenticated


@dataclass
class CurrentUser:
    id: str
    role: str          # farmer | buyer | transporter
    email: str | None
    token: str
    db: Client         # JWT-bound client; RLS applies

    @property
    def is_farmer(self) -> bool:
        return self.role == "farmer"

    @property
    def is_buyer(self) -> bool:
        return self.role == "buyer"

    @property
    def is_transporter(self) -> bool:
        return self.role == "transporter"


@dataclass
class Identity:
    """A validated Supabase session whose profile may not exist yet.

    This is the pre-onboarding view of the caller: the JWT is decoded and a
    JWT-bound client is ready, but we have NOT required a `profiles` row. Only
    POST /api/auth/register runs on this, because it is the endpoint that
    creates that row — depending on the profile-requiring get_current_user
    here would be an unsatisfiable chicken-and-egg (register could never run).
    """

    id: str
    email: str | None
    token: str
    db: Client


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthenticated("Sign in to continue.")
    return authorization.split(" ", 1)[1].strip()


async def get_identity(
    authorization: Annotated[str | None, Header()] = None,
) -> Identity:
    token = _bearer(authorization)
    try:
        # Signature is verified by Supabase on every PostgREST call the bound
        # client makes; we decode here only to read the subject without a
        # network round-trip.
        claims = jwt.decode(token, options={"verify_signature": False, "verify_exp": True})
    except jwt.ExpiredSignatureError:
        raise Unauthenticated("Your session expired. Sign in again.")
    except jwt.PyJWTError:
        raise Unauthenticated("Your session is not valid. Sign in again.")

    user_id = claims.get("sub")
    if not user_id:
        raise Unauthenticated("Your session is not valid. Sign in again.")

    return Identity(
        id=user_id,
        email=claims.get("email"),
        token=token,
        db=user_client(token),
    )


async def get_current_user(
    identity: Annotated[Identity, Depends(get_identity)],
) -> CurrentUser:
    # This SELECT is itself RLS-checked, which proves the token is live.
    res = (
        identity.db.table("profiles")
        .select("id, role").eq("id", identity.id).limit(1).execute()
    )
    if not res.data:
        raise Unauthenticated("Finish setting up your profile to continue.")

    return CurrentUser(
        id=identity.id,
        role=res.data[0]["role"],
        email=identity.email,
        token=identity.token,
        db=identity.db,
    )


IdentityDep = Annotated[Identity, Depends(get_identity)]
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def require_role(*roles: str):
    """Route guard: require_farmer = Depends(require_role('farmer'))."""

    async def _guard(user: CurrentUserDep) -> CurrentUser:
        if user.role not in roles:
            raise Forbidden("This action is not available for your account type.")
        return user

    return _guard


require_farmer = Depends(require_role("farmer"))
require_buyer = Depends(require_role("buyer"))
require_transporter = Depends(require_role("transporter"))
