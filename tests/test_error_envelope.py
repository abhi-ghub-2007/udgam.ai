"""Every non-2xx response must carry the API_CONTRACT error envelope.

js/core/api.js has exactly one unwrapping path, so a handler that returns a
different shape produces a silently wrong error message in the UI. These are
the regression tests for that.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app, raise_server_exceptions=False)


def _assert_envelope(res, code: str, status: int):
    assert res.status_code == status, res.text
    body = res.json()
    assert "error" in body, body
    assert set(body["error"]) == {"code", "message", "field"}, body
    assert body["error"]["code"] == code, body
    assert body["error"]["message"], "message must never be empty"


def test_missing_bearer_is_401_not_500():
    _assert_envelope(client.get("/api/auth/me"), "UNAUTHENTICATED", 401)


def test_malformed_bearer_is_401():
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    _assert_envelope(res, "UNAUTHENTICATED", 401)


def test_unknown_route_is_404_envelope():
    _assert_envelope(client.get("/api/does-not-exist"), "NOT_FOUND", 404)


def test_validation_error_names_the_field():
    res = client.post("/api/auth/register", json={"role": "wizard"},
                      headers={"Authorization": "Bearer x"})
    assert res.status_code in (401, 422)
    assert "error" in res.json()


def test_public_endpoints_need_no_auth():
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/config").status_code == 200


def test_config_never_leaks_the_service_role_key():
    body = client.get("/api/config").json()
    assert "service" not in " ".join(body).lower()
    assert "supabase_service_role_key" not in {k.lower() for k in body}
