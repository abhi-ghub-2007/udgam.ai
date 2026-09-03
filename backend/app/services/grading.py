"""AI-1 produce grading — EXPLAINABLE_CV_HEURISTIC.

Genuine OpenCV-based computer vision heuristic to extract visual
characteristics from the uploaded produce image.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)

GRADE_A, GRADE_B, GRADE_C = "A", "B", "C"


@dataclass
class Features:
    color_score: int
    blemish_score: int
    sharpness_score: int
    shape_score: int


@dataclass
class Grade:
    grade: str
    confidence: float
    method: str
    features: dict
    reasons: list[str]


def grade_image(image_bytes: bytes, crop_code: str | None = None) -> Grade:
    """Public entry point: image bytes -> Grade.
    Analyzes the image for color, blemishes, and sharpness using OpenCV.
    """
    if not image_bytes or len(image_bytes) < 10:
        raise ValueError("Image quality is insufficient for reliable visual assessment. Please upload a clearer produce image.")

    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception as e:
        logger.error(f"Image decode failed: {e}")
        img = None

    if img is None:
        raise ValueError("Image quality is insufficient for reliable visual assessment. Please upload a clearer produce image.")

    # 1. Resize for performance and normalization (max 800px)
    h, w = img.shape[:2]
    max_dim = 800
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
        h, w = img.shape[:2]

    # 2. Convert Color Spaces
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 3. Foreground Segmentation (Otsu's Thresholding on Saturation)
    # Produce usually has higher saturation than backgrounds
    s_channel = hsv[:, :, 1]
    _, mask = cv2.threshold(s_channel, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Clean up mask
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # Check mask size
    fg_area = cv2.countNonZero(mask)
    total_area = h * w
    fg_ratio = fg_area / total_area if total_area > 0 else 0

    if fg_ratio < 0.05: # Less than 5% foreground found
        # Fallback to whole image if segmentation fails dramatically
        mask = np.ones(gray.shape, dtype=np.uint8) * 255
        fg_area = total_area
        segmentation_confidence = 0.4
    else:
        segmentation_confidence = min(1.0, fg_ratio * 3)  # Peak confidence if produce fills >33%

    # 4. Feature Extraction
    
    # -- Sharpness --
    # Laplacian variance as proxy for sharpness/focus
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    # Normalize sharpness (approx range 0 to 500)
    sharpness_score = int(min(100, max(0, (laplacian_var / 500.0) * 100)))

    # Reject if way too blurry
    if sharpness_score < 10:
        raise ValueError("Image is too blurry for reliable visual assessment. Please upload a clearer produce image.")

    # -- Color Score --
    # Analyze Value and Saturation within mask
    mean_val = cv2.mean(hsv[:, :, 2], mask=mask)[0]
    mean_sat = cv2.mean(hsv[:, :, 1], mask=mask)[0]
    # Simple metric: brighter and more saturated produces are generally healthier looking
    # Assuming val/sat range 0-255
    color_health = ((mean_val + mean_sat) / 2) / 255.0
    color_score = int(min(100, max(0, color_health * 100)))

    # -- Blemish Score --
    # Detect high gradient variations (edges) and local color anomalies inside the produce body
    # Smooth surfaces = low edge density and uniform local intensity
    edges = cv2.Canny(gray, 30, 100)
    # Exclude the outer boundary of the mask to avoid counting the crop edge as a blemish
    eroded_mask = cv2.erode(mask, np.ones((7, 7), np.uint8), iterations=2)
    internal_edges = cv2.bitwise_and(edges, edges, mask=eroded_mask)
    eroded_area = max(1, cv2.countNonZero(eroded_mask))
    edge_density = cv2.countNonZero(internal_edges) / eroded_area
    
    # Also measure local standard deviation within the eroded produce area
    mean_g, std_g = cv2.meanStdDev(gray, mask=eroded_mask)
    std_val = float(std_g[0][0])
    
    # Combined blemish metric: edge density (high frequency) + std deviation (contrast variations)
    blemish_factor = (edge_density * 25.0) + (std_val / 128.0 * 0.5)
    blemish_score = int(min(100, max(0, 100 - (blemish_factor * 100))))

    # -- Shape Score --
    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        # Get largest contour
        c = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(c)
        perimeter = cv2.arcLength(c, True)
        if perimeter > 0:
            circularity = 4 * np.pi * (area / (perimeter * perimeter))
            shape_score = int(min(100, max(0, circularity * 100)))
        else:
            shape_score = 50
    else:
        shape_score = 50

    # 5. Composite Score & Grading
    # Weights
    w_color = 0.30
    w_blemish = 0.30
    w_sharpness = 0.20
    w_shape = 0.20

    final_score = (
        color_score * w_color +
        blemish_score * w_blemish +
        sharpness_score * w_sharpness +
        shape_score * w_shape
    )

    if final_score >= 80:
        grade = GRADE_A
    elif final_score >= 60:
        grade = GRADE_B
    else:
        grade = GRADE_C

    # 6. Confidence Score
    # Combine segmentation confidence, sharpness, and a base model confidence
    base_confidence = 0.7
    overall_confidence = (base_confidence + segmentation_confidence + (sharpness_score/100.0)) / 3.0
    overall_confidence = min(0.95, max(0.2, overall_confidence))

    # 7. Explanations
    reasons = []
    if color_score > 80:
        reasons.append("Good color consistency")
    elif color_score < 50:
        reasons.append("Low color consistency or dullness")

    if blemish_score > 85:
        reasons.append("Low visible blemish ratio")
    elif blemish_score < 60:
        reasons.append("Significant visible surface irregularities")

    if sharpness_score > 70:
        reasons.append("Strong image sharpness")
    elif sharpness_score < 40:
        reasons.append("Low image sharpness")

    if shape_score > 80:
        reasons.append("High shape uniformity")

    if not reasons:
        reasons.append("Standard visual characteristics")

    # Add the overall score to the features dict so it can be passed to the DB and frontend
    features_dict = asdict(Features(color_score, blemish_score, sharpness_score, shape_score))
    features_dict["score"] = round(final_score, 1)
    
    # Store explanations in features so the UI can retrieve them easily
    features_dict["explanations"] = reasons

    return Grade(
        grade=grade,
        confidence=round(overall_confidence, 2),
        method="HEURISTIC",
        features=features_dict,
        reasons=reasons
    )
