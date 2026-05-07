import math
import numpy as np
from pipelines.worldgen_v2 import dem_math


def test_bbox_span_meters_at_equator():
    sx, sz = dem_math.bbox_span_meters((0.0, 0.0, 1.0, 1.0))
    assert abs(sx - 111_320) < 200  # 1 deg lon at equator ≈ 111.32 km
    assert abs(sz - 111_320) < 200


def test_bbox_span_meters_high_latitude():
    sx, sz = dem_math.bbox_span_meters((0.0, 60.0, 1.0, 61.0))
    assert sx < 60_000  # cos(60.5°) ≈ 0.49 → ~55 km
    assert abs(sz - 111_320) < 200


def test_normalize_to_uint16_preserves_relative_heights():
    arr = np.array([[0.0, 100.0], [50.0, 100.0]], dtype=np.float32)
    u16, lo, hi = dem_math.normalize_to_uint16(arr)
    assert lo == 0.0 and hi == 100.0
    assert u16.dtype == np.uint16
    assert u16[0, 0] == 0
    assert u16[0, 1] == 65535
    assert u16[1, 0] == 32767 or u16[1, 0] == 32768


def test_resample_to_size_downsamples_correctly():
    arr = np.arange(16, dtype=np.float32).reshape(4, 4)
    out = dem_math.resample_to_size(arr, 2)
    assert out.shape == (2, 2)
