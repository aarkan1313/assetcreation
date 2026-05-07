"""Stage 4: build a 4-channel RGBA splat with REAL blending.

Inputs: height_16_edited.png (16-bit), terrain meta from dem_meta.json.

Algorithm: each biome gets a *continuous affinity function* over (height, slope)
instead of a hard argmax classification. The four affinities are combined as
softmax weights and gentle-Gaussian-blurred so biome transitions are wide
aprons (a few hundred metres on a 35 km terrain) rather than 1-pixel seams.

Biome order matches `job.biomes` (the 4-tuple chosen per job):
  0 = desert          — mid elevation, low slope
  1 = salt_flat       — very low elevation, very low slope
  2 = rocky_highland  — anywhere with slope, regardless of height
  3 = sparse_pine     — high elevation, low slope

The previous 'paint_biomes -> argmax mask -> tiny blur' approach produced an
~85% one-hot splat (verified by audit) and that's why the in-engine terrain
looked posterized. This stage replaces the mask-driven path entirely."""
from __future__ import annotations
import json
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
from pipelines.worldgen_v2 import paths
from pipelines.worldgen_v2.job_schema import Job

# 12-px sigma on a 2048² splat over a 35-km terrain = ~210 m blend half-width.
# Wide enough to read as real "biome aprons" not seams, narrow enough that
# small features (a salt-flat island in a desert) don't dissolve.
BLUR_SIGMA_PX = 12.0

# Softmax temperature: lower = sharper transitions, higher = mushier.
# 0.12 picked so that on Death Valley, the salt flat is 80%+ salt_flat at the
# basin floor, fades to 50/50 with desert over ~300 m, then desert dominates.
SOFTMAX_TEMPERATURE = 0.12


def _slope_magnitude(h_u16: np.ndarray) -> np.ndarray:
    """Sobel-ish gradient magnitude, normalized 0..1 by p99."""
    gy, gx = np.gradient(h_u16.astype(np.float32))
    mag = np.hypot(gx, gy)
    p99 = np.percentile(mag, 99) or 1.0
    return np.clip(mag / p99, 0.0, 1.0)


def _affinities(h: np.ndarray, slope: np.ndarray) -> np.ndarray:
    """Return (4, H, W) raw affinity scores per biome before softmax.
    Each affinity is a smooth function of (height, slope), not a threshold.
    Higher score = stronger preference for that biome at that pixel."""
    # Biome 0 — desert: mid elevation, low slope, broad
    aff_desert = (
        np.exp(-((h - 0.30) ** 2) / 0.10)
        * np.exp(-(slope ** 2) / 0.20)
    )
    # Biome 1 — salt_flat: very low elevation, very low slope (sharp peak)
    aff_salt = (
        np.exp(-((h - 0.0) ** 2) / 0.005)
        * np.exp(-(slope ** 2) / 0.02)
    )
    # Biome 2 — rocky_highland: any slope, any height, peak at moderate slope
    aff_rocky = np.exp(-((slope - 0.5) ** 2) / 0.15)
    # Biome 3 — sparse_pine: high elevation, low slope
    aff_pine = (
        np.exp(-((h - 0.85) ** 2) / 0.05)
        * np.exp(-(slope ** 2) / 0.20)
    )
    aff = np.stack([aff_desert, aff_salt, aff_rocky, aff_pine], axis=0)
    return aff


def run(job: Job) -> None:
    out = paths.job_output_dir(job.id)
    src = out / "height_16_edited.png"
    if not src.exists():
        raise FileNotFoundError(f"compile_splat: missing upstream artifact {src}")

    h_u16 = np.asarray(Image.open(src), dtype=np.uint16)
    h = h_u16.astype(np.float32) / 65535.0
    slope = _slope_magnitude(h_u16)
    height_pixels, width_pixels = h.shape

    aff = _affinities(h, slope)  # (4, H, W)

    # Softmax with temperature to convert affinities to weights summing to 1.
    aff_scaled = aff / SOFTMAX_TEMPERATURE
    aff_max = aff_scaled.max(axis=0, keepdims=True)
    exp = np.exp(aff_scaled - aff_max)
    weights = exp / exp.sum(axis=0, keepdims=True)  # (4, H, W), sums to 1

    # Smooth each weight channel — softens any sharp competition zones into
    # wide aprons. After this the channels no longer sum to exactly 1, so
    # we re-normalize at the end.
    blurred = np.zeros_like(weights)
    for i in range(4):
        blurred[i] = gaussian_filter(weights[i], sigma=BLUR_SIGMA_PX, mode="reflect")
    s = blurred.sum(axis=0, keepdims=True)
    s[s < 1e-6] = 1.0
    normed = blurred / s

    splat_u8 = (normed * 255.0).round().clip(0, 255).astype(np.uint8)
    splat = np.transpose(splat_u8, (1, 2, 0))  # (4,H,W) -> (H,W,4)

    Image.fromarray(splat, mode="RGBA").save(out / "biome_splat_rgba.png")

    # Also write a debug histogram so we can verify the splat actually blends.
    hot = (splat > 200).sum(axis=2)
    blend = ((splat > 30) & (splat < 220)).any(axis=2).mean() * 100
    means = [float(splat[..., i].mean()) for i in range(4)]
    print(f"[compile_splat] wrote {height_pixels}x{width_pixels} 4-channel splat "
          f"(blend coverage={blend:.1f}%, channel means={[f'{m:.0f}' for m in means]})")
