"""
Verifies the `Authorization: Bearer <token>` header by asking Supabase's
own Auth API whether it's a valid session, and exposes the caller's
verified email (+ partner flag) to route handlers via FastAPI
dependencies.

Decoding the JWT locally would require knowing which algorithm the
project's tokens are signed with -- Supabase signs with the legacy shared
HS256 secret on older projects and asymmetric ES256 signing keys on newer
ones, and there's no single algorithm this backend can safely hardcode.
Delegating verification to GET /auth/v1/user sidesteps that entirely: it's
correct regardless of signing scheme, at the cost of one extra network
call per request (acceptable at this app's scale, alongside the DB round
-trips every route already makes).
"""
from dataclasses import dataclass

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

# auto_error=False: we raise 401 ourselves below. HTTPBearer's own
# auto_error path returns 403 "Not authenticated", which would be
# inconsistent with every other auth failure in this module.
_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    email: str
    is_partner: bool


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser:
    if creds is None or not creds.credentials:
        raise HTTPException(401, "missing bearer token")

    try:
        resp = httpx.get(
            f"{settings.require_supabase_url()}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {creds.credentials}",
                "apikey": settings.require_supabase_anon_key(),
            },
            timeout=10,
        )
    except httpx.HTTPError as e:
        raise HTTPException(401, f"could not verify session: {e}") from e

    if resp.status_code != 200:
        raise HTTPException(401, "invalid or expired session")

    email = str(resp.json().get("email") or "").strip().lower()
    if not email:
        raise HTTPException(401, "token has no verified email claim")
    return CurrentUser(email=email, is_partner=email in settings.PARTNER_EMAILS)


def require_partner(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_partner:
        raise HTTPException(403, "partner access required")
    return user
