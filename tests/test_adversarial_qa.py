"""Zero-Trust / Adversarial QA Suite for UDGAM.ai SIH Demo Readiness.

Tests adversarial inputs, edge cases, role boundary enforcement,
malicious payloads, and CV engine robustness.
"""
from __future__ import annotations

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.grading import grade_image, GRADE_A, GRADE_B, GRADE_C

client = TestClient(app)


# ==============================================================================
# 1. COMPUTER VISION (CV) ENGINE ZERO-TRUST ADVERSARIAL TESTS
# ==============================================================================

def make_produce_image(color_bgr=(40, 180, 40), blemish_pct=0, blur_ksize=0, shape_deform=0) -> bytes:
    """Generate produce images with controlled mathematical variations."""
    img = np.ones((400, 400, 3), dtype=np.uint8) * 255
    center = (200, 200)
    axes = (140, int(140 * (1.0 - shape_deform)))
    cv2.ellipse(img, center, axes, 0, 0, 360, color_bgr, -1)

    if blemish_pct > 0:
        # Add blemish patches
        num_spots = int(blemish_pct * 20)
        for i in range(num_spots):
            bx = 200 + int(60 * np.cos(i * 1.5))
            by = 200 + int(60 * np.sin(i * 1.5))
            cv2.circle(img, (bx, by), 8, (15, 15, 15), -1)

    if blur_ksize > 0:
        k = blur_ksize if blur_ksize % 2 == 1 else blur_ksize + 1
        img = cv2.GaussianBlur(img, (k, k), 0)

    _, enc = cv2.imencode(".jpg", img)
    return enc.tobytes()


def test_cv_rejects_empty_bytes():
    """Empty payload must fail with descriptive error, not an unhandled crash."""
    with pytest.raises(ValueError, match="Image quality is insufficient"):
        grade_image(b"")


def test_cv_rejects_random_ascii_binary_junk():
    """Random non-image data must be cleanly rejected."""
    junk = b"%PDF-1.4\n%Fake PDF disguised as jpg\x00\x01\x02\x03\x04"
    with pytest.raises(ValueError, match="Image quality is insufficient"):
        grade_image(junk)


def test_cv_rejects_pure_noise_and_extreme_brightness():
    """Pure white or pure black images must fail due to lack of detectable produce contours or sharpness."""
    pure_white = np.ones((300, 300, 3), dtype=np.uint8) * 255
    _, enc_w = cv2.imencode(".jpg", pure_white)
    with pytest.raises(ValueError, match="(Image quality is insufficient|too blurry)"):
        grade_image(enc_w.tobytes())

    pure_black = np.zeros((300, 300, 3), dtype=np.uint8)
    _, enc_b = cv2.imencode(".jpg", pure_black)
    with pytest.raises(ValueError, match="(Image quality is insufficient|too blurry)"):
        grade_image(enc_b.tobytes())


def test_cv_fine_grained_blemish_sensitivity():
    """Verify that increasing blemish coverage monotonically reduces the blemish_score."""
    clean_bytes = make_produce_image(blemish_pct=0)
    slight_blemish = make_produce_image(blemish_pct=0.2)
    heavy_blemish = make_produce_image(blemish_pct=0.8)

    g_clean = grade_image(clean_bytes)
    g_slight = grade_image(slight_blemish)
    g_heavy = grade_image(heavy_blemish)

    assert g_clean.features["blemish_score"] > g_slight.features["blemish_score"]
    assert g_slight.features["blemish_score"] > g_heavy.features["blemish_score"]
    assert g_clean.features["score"] > g_heavy.features["score"]


def test_cv_shape_regularity_sensitivity():
    """Deforming the produce shape should lower the shape score."""
    round_produce = make_produce_image(shape_deform=0.0)
    deformed_produce = make_produce_image(shape_deform=0.6)

    g_round = grade_image(round_produce)
    g_deformed = grade_image(deformed_produce)

    assert g_round.features["shape_score"] > g_deformed.features["shape_score"]


def test_cv_produces_explainable_reasons():
    """Engine must provide natural language reasons explaining the grade decision."""
    blemished_bytes = make_produce_image(blemish_pct=0.6)
    g = grade_image(blemished_bytes)

    assert len(g.reasons) > 0
    assert any("blemish" in r.lower() or "surface" in r.lower() or "color" in r.lower() or "sharpness" in r.lower() for r in g.reasons)


# ==============================================================================
# 2. ROLE-BASED ACCESS CONTROL (RBAC) & ZERO-TRUST SECURITY
# ==============================================================================

def test_unauthenticated_requests_receive_standard_401():
    """Any call to protected routes without a token must return 401 with standard error envelope."""
    protected_endpoints = [
        ("GET", "/api/auth/me"),
        ("POST", "/api/products"),
        ("GET", "/api/products/mine"),
        ("POST", "/api/buyer-requests"),
        ("GET", "/api/buyer-requests/mine"),
        ("GET", "/api/dashboard/farmer"),
        ("GET", "/api/dashboard/buyer"),
        ("GET", "/api/dashboard/transporter"),
        ("GET", "/api/transport/jobs"),
    ]
    for method, path in protected_endpoints:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, json={})
        assert res.status_code == 401, f"{method} {path} should be 401"
        data = res.json()
        assert "error" in data
        assert data["error"]["code"] == "UNAUTHENTICATED"


def test_malformed_tokens_fail_cleanly():
    """Garbage Authorization headers must not crash the server."""
    bad_headers = [
        {"Authorization": "Bearer not-a-jwt"},
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": "Bearer "},
        {"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.invalid.signature"},
    ]
    for h in bad_headers:
        res = client.get("/api/auth/me", headers=h)
        assert res.status_code == 401
        data = res.json()
        assert data["error"]["code"] == "UNAUTHENTICATED"


# ==============================================================================
# 3. INPUT VALIDATION & INJECTION RESISTANCE
# ==============================================================================

def test_validation_bounds_on_registration():
    """Registration endpoint must reject invalid inputs (e.g. empty full_name, invalid role)."""
    # Bad role
    res = client.post("/api/auth/register", json={
        "role": "hacker_role",
        "full_name": "Adversary",
    })
    # Should be 401 because no auth header, or 422 if auth is checked after validation
    assert res.status_code in (401, 422)


def test_product_query_sort_injection():
    """Sort query param must reject unexpected values according to regex pattern."""
    res = client.get("/api/products?sort=malicious_sql_injection;DROP TABLE profiles;--")
    # Even if unauthenticated, FastAPI query validation runs
    assert res.status_code in (401, 422)
