"""
Test-only stand-in for Supabase's GET /auth/v1/user verification call.
app.auth.get_current_user asks Supabase's real Auth API to verify a bearer
token (necessary since Supabase signs tokens with whichever algorithm --
legacy HS256 secret or newer asymmetric ES256 keys -- the project happens
to use, so there's no one algorithm this app can decode locally). Hitting
the real endpoint from tests would mean creating real accounts via the
Supabase Admin API (needs the service-role key, and pollutes a real
auth.users table), so tests fake the HTTP call instead: the fake "token"
IS the email it should resolve to, and the patched call just echoes it
back the same shape Supabase's endpoint returns on success.
"""
from unittest.mock import Mock, patch

_FAKE_TOKEN_PREFIX = "test-token:"


def auth_headers(email: str = "test.user@example.com") -> dict:
    return {"Authorization": f"Bearer {_FAKE_TOKEN_PREFIX}{email}"}


def _fake_supabase_get(url, headers=None, timeout=None):
    token = (headers or {}).get("Authorization", "").removeprefix("Bearer ")
    resp = Mock()
    if token.startswith(_FAKE_TOKEN_PREFIX):
        resp.status_code = 200
        resp.json.return_value = {"email": token[len(_FAKE_TOKEN_PREFIX):]}
    else:
        resp.status_code = 401
        resp.json.return_value = {}
    return resp


def patch_supabase_auth():
    """Context manager/decorator: wrap any test that hits an authenticated
    route in `with patch_supabase_auth(): ...`, or apply it for a whole
    TestCase via setUp/tearDown (see test_matter_walls.py)."""
    return patch("app.auth.httpx.get", side_effect=_fake_supabase_get)
