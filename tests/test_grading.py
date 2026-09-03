"""AI-1 grading is deterministic and explainable.

OpenCV-based CV tests validating extraction of real features.
"""
from __future__ import annotations

import cv2
import numpy as np
import pytest
from backend.app.services.grading import grade_image, GRADE_A, GRADE_B, GRADE_C

FEATURE_KEYS = {
    "color_score", "blemish_score", "sharpness_score", "shape_score", "score", "explanations"
}

def create_test_image(color=(50, 200, 50), blur=False, blemish=False) -> bytes:
    """Create a synthetic produce image as bytes."""
    # Create white background
    img = np.ones((400, 400, 3), dtype=np.uint8) * 255
    # Draw a circle (produce)
    cv2.circle(img, (200, 200), 150, color, -1)
    
    if blemish:
        # Draw some dark spots
        cv2.circle(img, (150, 150), 20, (0, 0, 0), -1)
        cv2.circle(img, (250, 220), 10, (0, 0, 0), -1)
        
    if blur:
        img = cv2.GaussianBlur(img, (41, 41), 0)
        
    success, encoded = cv2.imencode('.jpg', img)
    assert success
    return encoded.tobytes()

def test_contract_shape():
    img_bytes = create_test_image()
    g = grade_image(img_bytes, "TOMATO")
    assert g.grade in {GRADE_A, GRADE_B, GRADE_C}
    assert 0.0 <= g.confidence <= 1.0
    assert g.method == "HEURISTIC"
    assert set(g.features.keys()) == FEATURE_KEYS
    assert g.reasons
    assert isinstance(g.features["score"], float)

def test_invalid_bytes_handling():
    with pytest.raises(ValueError, match="Image quality is insufficient"):
        grade_image(b"", "ONION")
        
    with pytest.raises(ValueError, match="Image quality is insufficient"):
        grade_image(b"not-an-image-at-all", "ONION")

def test_blurry_image_rejection():
    img_bytes = create_test_image(blur=True)
    with pytest.raises(ValueError, match="too blurry"):
        grade_image(img_bytes)

def test_feature_variation():
    # Good vibrant green produce
    good_bytes = create_test_image(color=(50, 200, 50), blemish=False)
    g1 = grade_image(good_bytes)
    
    # Dull, heavily blemished produce
    bad_bytes = create_test_image(color=(100, 100, 100), blemish=True)
    g2 = grade_image(bad_bytes)
    
    assert g1.features["blemish_score"] > g2.features["blemish_score"], "Blemishes should lower the blemish score"
    assert g1.features["color_score"] > g2.features["color_score"], "Dull color should lower color score"
    assert g1.features["score"] > g2.features["score"], "Overall score should be higher for good produce"
    
def test_hash_independence():
    # Test that different bytes with the SAME image content produce same scores
    img = np.ones((200, 200, 3), dtype=np.uint8) * 200
    cv2.circle(img, (100, 100), 50, (50, 200, 50), -1)
    
    # Encode with different JPG quality = different hashes, different bytes, same content
    _, enc1 = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    _, enc2 = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    
    bytes1 = enc1.tobytes()
    bytes2 = enc2.tobytes()
    
    assert bytes1 != bytes2
    
    g1 = grade_image(bytes1)
    g2 = grade_image(bytes2)
    
    # Features should be nearly identical (allowing minor JPG compression artifacts)
    assert abs(g1.features["score"] - g2.features["score"]) < 5.0
