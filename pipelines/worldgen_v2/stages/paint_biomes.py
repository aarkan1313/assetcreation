"""Stage 3: paint a 4-biome mask from heightmap + slope.
Output: biome_mask.png (8-bit, pixel value = biome index 0..3)."""
from __future__ import annotations
import numpy as np
from PIL import Image
from pipelines.worldgen_v2 import paths
from pipelines.worldgen_v2.job_schema import Job


def _slope_magnitude(h: np.ndarray) -> np.ndarray:
    """Sobel-ish gradient magnitude, normalized 0..1."""
    gy, gx = np.gradient(h.astype(np.float32))
    mag = np.hypot(gx, gy)
    p99 = np.percentile(mag, 99) or 1.0
    return np.clip(mag / p99, 0.0, 1.0)


def run(job: Job) -> None:
    out = paths.job_output_dir(job.id)
    src = out / "height_16_edited.png"
    if not src.exists():
        raise FileNotFoundError(f"paint_biomes: missing upstream artifact {src}")

    h_u16 = np.asarray(Image.open(src), dtype=np.uint16)
    h = h_u16.astype(np.float32) / 65535.0
    slope = _slope_magnitude(h_u16)

    # Default everyone to biome 0 (desert), then carve out the others.
    # Tightened thresholds so salt_flat (often near-white) only covers the
    # genuine basin floor, not "anything below 20% elevation".
    mask = np.zeros_like(h, dtype=np.uint8)
    salt_flat = (h < 0.05) & (slope < 0.15)
    high_flat = (h >= 0.55) & (slope < 0.35)
    steep = slope >= 0.35

    mask[salt_flat] = 1  # biomes[1] (salt_flat) — only the lowest, flattest 5%
    mask[steep] = 2      # biomes[2] (rocky_highland)
    mask[high_flat] = 3  # biomes[3] (sparse_pine)
    # everything else stays 0 (desert)

    Image.fromarray(mask, mode="L").save(out / "biome_mask.png")
    counts = np.bincount(mask.ravel(), minlength=4)
    print(f"[paint_biomes] mask written; biome counts {counts.tolist()}")
