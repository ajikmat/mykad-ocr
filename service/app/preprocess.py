"""Image normalization before OCR: decode, size cap, card crop + deskew.

Everything operates on in-memory arrays — nothing is ever written to disk
(Zero-retention, CONTEXT.md).
"""

import cv2
import numpy as np

# MyKad aspect ratio ≈ 85.60 × 53.98 mm
TARGET_W, TARGET_H = 1030, 650
MAX_SIDE = 1600
ASPECT_MIN, ASPECT_MAX = 1.3, 1.9
MIN_CARD_AREA_FRAC = 0.25


def decode(data: bytes):
    """JPEG/PNG bytes → BGR array, or None if undecodable."""
    arr = np.frombuffer(data, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def normalize(img):
    """Cap resolution, then crop+deskew to the card if one is found.

    Falls back to the (capped) original when no card-shaped quad is
    detected — e.g. the photo is already cropped tight to the card.
    """
    img = _cap_size(img)
    quad = _find_card_quad(img)
    if quad is not None:
        return _warp(img, quad)
    return img


def _cap_size(img):
    h, w = img.shape[:2]
    longest = max(h, w)
    if longest <= MAX_SIDE:
        return img
    scale = MAX_SIDE / longest
    return cv2.resize(img, (int(w * scale), int(h * scale)),
                      interpolation=cv2.INTER_AREA)


def _find_card_quad(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    img_area = img.shape[0] * img.shape[1]
    for c in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
        if cv2.contourArea(c) < MIN_CARD_AREA_FRAC * img_area:
            break
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        quad = _order_quad(approx.reshape(4, 2).astype(np.float32))
        tl, tr, br, bl = quad
        w = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2
        h = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2
        if h > 0 and ASPECT_MIN <= w / h <= ASPECT_MAX:
            return quad
    return None


def _order_quad(pts):
    """Order 4 points as top-left, top-right, bottom-right, bottom-left."""
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).reshape(-1)
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)],
                     pts[np.argmax(s)], pts[np.argmax(d)]], dtype=np.float32)


def _warp(img, quad):
    dst = np.array([[0, 0], [TARGET_W - 1, 0],
                    [TARGET_W - 1, TARGET_H - 1], [0, TARGET_H - 1]],
                   dtype=np.float32)
    m = cv2.getPerspectiveTransform(quad, dst)
    return cv2.warpPerspective(img, m, (TARGET_W, TARGET_H))
