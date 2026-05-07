"""Pure geodesy/array helpers for DEM data. No I/O, no network."""
from __future__ import annotations
import math
import numpy as np
from PIL import Image

DEG_TO_M = 111_320.0  # 1 deg of latitude in metres (constant)


def bbox_span_meters(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    """Return (span_x_m, span_z_m) for a (W,S,E,N) bbox using lat-aware lon."""
    w, s, e, n = bbox
    lat_mid = (s + n) * 0.5
    span_z_m = (n - s) * DEG_TO_M
    span_x_m = (e - w) * DEG_TO_M * math.cos(math.radians(lat_mid))
    return span_x_m, span_z_m


def normalize_to_uint16(arr: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Map float elevations to 0..65535 uint16. Returns (u16, lo, hi)."""
    lo = float(arr.min())
    hi = float(arr.max())
    if hi <= lo:
        return np.zeros_like(arr, dtype=np.uint16), lo, hi
    norm = (arr - lo) / (hi - lo)
    u16 = (norm * 65535.0).round().astype(np.uint16)
    return u16, lo, hi


def resample_to_size(arr: np.ndarray, target: int) -> np.ndarray:
    """Resample 2D float array to (target, target) using PIL bilinear."""
    img = Image.fromarray(arr.astype(np.float32), mode="F")
    img = img.resize((target, target), Image.Resampling.BILINEAR)
    return np.asarray(img, dtype=np.float32)
