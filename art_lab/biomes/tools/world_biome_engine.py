"""World Biome Engine — coherent multi-biome terrain with feature-aware transitions.

Takes a list of biome kit JSONs + a region size and produces:
  - Heightmap (carved per-biome to match each biome's identity)
  - Biome label image (categorical)
  - Three zoom-level previews:
      * world_view.png    (low-res, one color per biome)
      * regional_view.png (medium res, palette + glyphs + smooth transitions)
      * local_view.png    (full res, hypsometric-shaded with biome tint)
  - All standard terrain bundle layers (splat/normal/water/flow/etc) — Godot ready

Algorithm:
  1. Place biome anchor seeds (Poisson-disc, with priority-based density)
  2. Compute per-biome influence field (Voronoi distance + altitude affinity + slope affinity)
  3. Pick label per pixel by argmax of influence (NOT raw Voronoi distance)
  4. Apply per-biome terrain feature carving (lava cracks, ice spires, crystal spikes...)
  5. Apply per-biome height bias (re-shape histogram in each biome's pixels)
  6. Smooth transitions: snap boundaries to terrain features (rivers/ridges/altitude),
     apply per-pair blending width
  7. Render three zoom levels

Usage:
  python world_biome_engine.py --id mythos_world `
    --biomes lava_field,ice_cavern,mana_crystal,grassland `
    --size 1024 --seed 7
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# Reach into the terrain pipeline for the noise + erosion primitives
sys.path.insert(0, str(Path(r"D:\assets\pipelines\terrain")))
from generate_heightmap import fbm, thermal_erode, normal_from_height, hypsometric_preview
from terrain_bundle import (
    slope_from_height, flow_accumulation_d8, splat_rgba,
    vegetation_density, water_mask, hillshade, to_png_16bit,
    GODOT_TERRAIN3D_HINT, heightmapshape3d_tres,
)


KITS_DIR = Path(r"D:\assets\art_lab\biomes\world_kits")
OUT_ROOT = Path(r"D:\assets\world\worlds")


# --- Base heightmap with continental structure -------------------------------
def _load_dem_meta(region_id: str) -> dict:
    """Look up the upstream DEM tool's metadata so we know the real-world
    bbox + elevation range for this region. Returns {} when synthetic.

    Inspects pipelines/terrain/output/<id>/ for one of:
      - terrain.json         (import_dem.py output)
      - tile_grid.json       (tile_stitch.py output)
    Both contain bbox + elevation range; tile_grid uses 'target_bbox' and
    'elevation_range_m', terrain uses 'bbox' + 'elevation_min_m'/'max_m'.
    """
    out_dir = Path(r"D:\assets\pipelines\terrain\output") / region_id
    candidates = [
        ("terrain.json",   "bbox"),
        ("tile_grid.json", "target_bbox"),
    ]
    for fname, bbox_key in candidates:
        p = out_dir / fname
        if not p.exists():
            continue
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        bbox = j.get(bbox_key)
        if not bbox or len(bbox) != 4:
            continue
        # Elevation range — both schemas, normalize to (min, max) metres.
        if "elevation_range_m" in j:
            emin, emax = j["elevation_range_m"]
        else:
            emin = j.get("elevation_min_m")
            emax = j.get("elevation_max_m")
            if emin is None or emax is None:
                emin, emax = 0.0, 1.0
        # Compute real-world spans. bbox is [W, S, E, N] in degrees.
        import math
        lat_mid = (bbox[1] + bbox[3]) / 2.0
        deg_lon_per_m = 1.0 / (111320.0 * math.cos(math.radians(lat_mid)))
        deg_lat_per_m = 1.0 / 110540.0
        span_x_m = (bbox[2] - bbox[0]) / deg_lon_per_m
        span_z_m = (bbox[3] - bbox[1]) / deg_lat_per_m
        return {
            "source_file": fname,
            "bbox": list(bbox),
            "span_x_m": float(span_x_m),
            "span_z_m": float(span_z_m),
            "elev_min_m": float(emin),
            "elev_max_m": float(emax),
            "elev_range_m": float(emax - emin),
        }
    return {}


def continental_heightmap(size: int, seed: int) -> np.ndarray:
    """Build a heightmap with three frequency bands stacked:
       1. continental (very low frequency, defines big land masses)
       2. mountain ranges (medium frequency, ridged)
       3. fine detail (high frequency, regular FBM)

    The result has the topology of a real-ish continent rather than noise blobs.
    """
    # 1. Continental — base_scale=2 octaves=2 makes huge soft hills
    cont = fbm(size, base_scale=2, octaves=2, persistence=0.5, seed=seed)
    cont = (cont - cont.min()) / (cont.max() - cont.min() + 1e-9)
    # Boost contrast so the continental layer is binary-ish (land vs sea)
    cont = np.clip((cont - 0.42) * 2.4 + 0.5, 0, 1)

    # 2. Mountain ranges — base_scale=6 octaves=4 then ridged transform
    mtn = fbm(size, base_scale=6, octaves=4, persistence=0.55, seed=seed + 7)
    mtn = (mtn - mtn.min()) / (mtn.max() - mtn.min() + 1e-9)
    # Ridged: peaks where the noise crosses the mean
    mtn = 1.0 - np.abs(mtn - 0.5) * 2.0
    mtn = np.clip(mtn, 0, 1) ** 1.5

    # 3. Fine detail
    fine = fbm(size, base_scale=12, octaves=5, persistence=0.5, seed=seed + 13)
    fine = (fine - fine.min()) / (fine.max() - fine.min() + 1e-9)

    # Combine: continental * (continent_mask) + mountain_ranges (only where land) + fine
    land_mask = cont
    h = cont * 0.55 + mtn * land_mask * 0.30 + fine * 0.15
    h = (h - h.min()) / (h.max() - h.min() + 1e-9)
    return h.astype(np.float32)


# --- Height bias re-shaping ----------------------------------------------------
# Each biome wants its pixels at a particular altitude. We don't re-generate the
# heightmap from scratch — we apply a soft per-biome remap that shifts the
# distribution toward the biome's preferred range.

def remap_altitude(h: np.ndarray, biome_mask: np.ndarray, target_range: tuple[float, float],
                   strength: float = 0.5) -> np.ndarray:
    """Soft-shift heightmap pixels under biome_mask toward target_range."""
    out = h.copy()
    masked = h[biome_mask]
    if masked.size == 0:
        return out
    # Current distribution
    lo, hi = float(np.percentile(masked, 5)), float(np.percentile(masked, 95))
    target_lo, target_hi = target_range
    cur_range = max(hi - lo, 1e-3)
    target_r = max(target_hi - target_lo, 1e-3)
    # Linear remap with strength interpolation
    remapped = (masked - lo) / cur_range * target_r + target_lo
    out[biome_mask] = h[biome_mask] * (1 - strength) + remapped * strength
    return np.clip(out, 0, 1)


# --- Feature carving -----------------------------------------------------------
# All scales below assume 1 px ≈ 0.5 m (so 1024 px ≈ 512 m playable world).
# Carved features are CLIPPED to their biome mask and won't bleed across boundaries.

def carve_lava_cracks(h: np.ndarray, mask: np.ndarray, seed: int) -> np.ndarray:
    """Lava cracks ≈ 8-15 m wide hexagonal cells with 0.5-1.5 m deep slits.

    At 1024 px / 0.5 m per pixel, that's seed spacing ≈ 16-30 px and crack
    width ≈ 1-2 px.  We use far sparser seeds (one per ~250 px²) and only
    apply within the mask.
    """
    if not mask.any():
        return h
    rng = np.random.default_rng(seed + 100)
    # Seeds per biome area: aim for one cell per ~30×30 px patch
    target_density = 1.0 / 900.0
    n_pts = max(8, int(mask.sum() * target_density))
    rows, cols = np.where(mask)
    pick = rng.choice(len(rows), size=min(n_pts, len(rows)), replace=False)
    pts = np.stack([rows[pick], cols[pick]], axis=1)

    # Compute distance to nearest two seeds
    ys, xs = np.indices(h.shape)
    d_first = np.full(h.shape, np.inf, dtype=np.float32)
    d_second = np.full(h.shape, np.inf, dtype=np.float32)
    for py, px in pts:
        d = np.sqrt((ys - py) ** 2 + (xs - px) ** 2)
        # Update first/second nearest
        is_closer = d < d_first
        d_second = np.where(is_closer, d_first, np.minimum(d_second, d))
        d_first = np.where(is_closer, d, d_first)

    # Crack = thin band where second-nearest minus first-nearest is small
    band_width = 1.5  # in pixels — ~0.75 m crack
    crack = np.clip(1.0 - (d_second - d_first) / band_width, 0, 1)
    crack = crack ** 3  # sharpen so it's a thin line, not a wide stain
    crack *= mask.astype(np.float32)

    # Cracks go down 0.5-1.5m (in 0..1 normalized = ~0.01-0.03 of full range).
    h2 = h - crack * 0.025
    return np.clip(h2, 0, 1)


def carve_ice_spires(h: np.ndarray, mask: np.ndarray, seed: int) -> np.ndarray:
    """Ice spires: tall narrow columns 5-15 m tall, ~5 m wide, sparse (≈ one per 40×40 m).

    At 1024 px / 0.5 m: spire half-width ≈ 5 px, density ≈ 1 per 80×80 px.
    """
    if not mask.any():
        return h
    rng = np.random.default_rng(seed + 200)
    target_density = 1.0 / 6400.0
    n_pts = max(4, int(mask.sum() * target_density))
    rows, cols = np.where(mask)
    pick = rng.choice(len(rows), size=min(n_pts, len(rows)), replace=False)
    out = h.copy()
    ys, xs = np.indices(h.shape)
    mask_f = mask.astype(np.float32)
    for idx in pick:
        py, px = rows[idx], cols[idx]
        d = np.sqrt((ys - py) ** 2 + (xs - px) ** 2)
        # Tall narrow spire: gaussian profile, width ~5 px
        spire_height = rng.uniform(0.10, 0.22)  # 5-11m at 50m world height
        spire = np.exp(-(d / 5.0) ** 2) * spire_height
        # Hard-clip to mask (no bleed into other biomes)
        out = out + spire * mask_f
    return np.clip(out, 0, 1)


def carve_crystal_spikes(h: np.ndarray, mask: np.ndarray, seed: int) -> np.ndarray:
    """Mana crystal clusters: 3-7 sharp spikes per cluster, clusters 30-60m apart.

    At 1024 px / 0.5 m: cluster spacing ≈ 60-120 px; spike width ~3 px,
    height up to 30m (0.6 of full range).
    """
    if not mask.any():
        return h
    rng = np.random.default_rng(seed + 300)
    target_density = 1.0 / 8000.0  # one cluster per ~90×90 px patch
    n_clusters = max(3, int(mask.sum() * target_density))
    rows, cols = np.where(mask)
    pick = rng.choice(len(rows), size=min(n_clusters, len(rows)), replace=False)
    out = h.copy()
    ys, xs = np.indices(h.shape)
    mask_f = mask.astype(np.float32)
    for idx in pick:
        py, px = rows[idx], cols[idx]
        n_spikes = rng.integers(4, 9)
        for _ in range(n_spikes):
            # Spikes within 8-12 px (4-6 m) of cluster centre
            dy = rng.normal(0, 6); dx = rng.normal(0, 6)
            sy = int(np.clip(py + dy, 0, h.shape[0] - 1))
            sx = int(np.clip(px + dx, 0, h.shape[1] - 1))
            if not mask[sy, sx]:
                continue
            d = np.sqrt((ys - sy) ** 2 + (xs - sx) ** 2)
            # Sharper falloff, taller height
            spike_height = rng.uniform(0.20, 0.45)  # up to 22m
            spike = np.exp(-(d / 2.0) ** 4) * spike_height  # exponent 4 = much sharper falloff
            out = out + spike * mask_f
    return np.clip(out, 0, 1)


def carve_glassy_smooth(h: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Macro-smoothing on glassy biomes (obsidian, glacier)."""
    smooth = np.asarray(
        Image.fromarray((h * 255).astype(np.uint8), mode="L")
             .filter(ImageFilter.GaussianBlur(radius=4)),
        dtype=np.float32,
    ) / 255.0
    out = h.copy()
    out[mask] = smooth[mask] * 0.7 + h[mask] * 0.3
    return out


def carve_ash_drifts(h: np.ndarray, mask: np.ndarray, seed: int) -> np.ndarray:
    """Wind-direction noise dunes in lava/ash biomes."""
    rng = np.random.default_rng(seed + 400)
    drift = fbm(h.shape[0], base_scale=8, octaves=4, seed=int(rng.integers(0, 1 << 31)))
    drift = (drift - drift.min()) / (drift.max() - drift.min() + 1e-9)
    out = h.copy()
    out[mask] = h[mask] + (drift[mask] - 0.5) * 0.04
    return np.clip(out, 0, 1)


def apply_biome_features(h: np.ndarray, mask: np.ndarray, features: list[str], seed: int) -> np.ndarray:
    """Dispatch to per-feature carvers."""
    out = h
    for f in features:
        if f == "lava_cracks":
            out = carve_lava_cracks(out, mask, seed)
        elif f == "ash_drifts":
            out = carve_ash_drifts(out, mask, seed)
        elif f == "ice_spires":
            out = carve_ice_spires(out, mask, seed)
        elif f == "ice_caverns":
            pass  # local subsurface — handled in local view only
        elif f == "glassy_smooth":
            out = carve_glassy_smooth(out, mask)
        elif f == "crystal_spikes":
            out = carve_crystal_spikes(out, mask, seed)
        elif f == "mana_geysers":
            out = carve_crystal_spikes(out, mask, seed + 1)  # similar shape
        elif f == "cracked_dry":
            pass  # surface texture handled in dressing layer
        elif f == "forest_canopy":
            pass  # vegetation only
        elif f == "ruin_terraces":
            pass  # landmark-anchored, handled separately
    return out


# --- Biome placement -----------------------------------------------------------
def place_biome_seeds(size: int, biome_kits: list[dict], rng: np.random.Generator) -> list[tuple[int, int, int]]:
    """Poisson-disc seed placement, biome priority influences density.

    Returns list of (y, x, biome_idx).
    """
    n_biomes = len(biome_kits)
    # Aim for 4-6 cells per biome on average
    total_seeds = n_biomes * 5
    seeds = []
    min_dist = max(40, size // 12)
    attempts = total_seeds * 100
    biome_counts = [0] * n_biomes
    target_per_biome = total_seeds // n_biomes

    for _ in range(attempts):
        if len(seeds) >= total_seeds:
            break
        y = rng.integers(0, size)
        x = rng.integers(0, size)
        too_close = any(abs(sy - y) + abs(sx - x) < min_dist for sy, sx, _ in seeds)
        if too_close:
            continue
        # Pick under-represented biome with priority-weighted random
        weights = []
        for i, kit in enumerate(biome_kits):
            need = max(0, target_per_biome - biome_counts[i] + 1)
            prio = kit.get("world_map_priority", 5)
            weights.append(need * prio)
        weights = np.asarray(weights, dtype=np.float32)
        if weights.sum() == 0:
            continue
        weights /= weights.sum()
        b = int(rng.choice(n_biomes, p=weights))
        seeds.append((int(y), int(x), b))
        biome_counts[b] += 1
    return seeds


def compute_influence_fields(size: int, seeds: list, biome_kits: list[dict],
                              h: np.ndarray, slope: np.ndarray,
                              sea_level: float = 0.32) -> tuple[np.ndarray, np.ndarray]:
    """Per-pixel biome label + influence strength.

    Influence(pixel, biome) = 1/dist_to_nearest_seed(biome) * altitude_affinity * slope_affinity

    Pixels below sea_level get label 255 (ocean) regardless of influence.
    """
    n_biomes = len(biome_kits)
    ys, xs = np.indices((size, size))
    influence = np.zeros((n_biomes, size, size), dtype=np.float32)

    # Per-biome distance to nearest seed of that biome
    for bi in range(n_biomes):
        biome_seeds = [(sy, sx) for sy, sx, b in seeds if b == bi]
        if not biome_seeds:
            continue
        d_min = np.full((size, size), np.inf, dtype=np.float32)
        for sy, sx in biome_seeds:
            d = np.sqrt((ys - sy) ** 2 + (xs - sx) ** 2)
            d_min = np.minimum(d_min, d)
        # Convert distance to influence (closer = higher)
        infl = 1.0 / (d_min + 1.0)

        # Altitude affinity: how well this biome likes the altitude here
        kit = biome_kits[bi]
        alt_lo, alt_hi = kit["terrain"]["altitude_range"]
        alt_center = (alt_lo + alt_hi) / 2
        alt_width = max((alt_hi - alt_lo) / 2, 0.05)
        alt_aff = np.exp(-((h - alt_center) / alt_width) ** 2)

        # Slope affinity
        sl_lo, sl_hi = kit["terrain"]["preferred_slope_range"]
        sl_center = (sl_lo + sl_hi) / 2
        sl_width = max((sl_hi - sl_lo) / 2, 0.10)
        sl_aff = np.exp(-((slope - sl_center) / sl_width) ** 2)

        influence[bi] = infl * (0.4 + 0.6 * alt_aff) * (0.5 + 0.5 * sl_aff)

    labels = np.argmax(influence, axis=0).astype(np.uint8)

    # Anything below sea_level is ocean (label 255)
    labels[h < sea_level] = 255

    # Apply exclusions: if biome A excludes B, find adjacent A/B pixels and
    # convert a buffer to the intermediate label (or to whichever has higher
    # influence after the exclusion penalty).
    for bi, kit in enumerate(biome_kits):
        for excl_id in kit["transitions"].get("exclusion", []):
            excl_idx = next((i for i, k in enumerate(biome_kits) if k["id"] == excl_id), None)
            if excl_idx is None:
                continue
            # Anywhere this is A and a neighbour within 4px is B → push to second-best
            mask_a = labels == bi
            mask_b = labels == excl_idx
            from scipy.ndimage import binary_dilation
            buffer = binary_dilation(mask_b, iterations=4) & mask_a
            # Rewrite buffer pixels to second-best non-A non-B
            for y, x in zip(*np.where(buffer)):
                row = influence[:, y, x].copy()
                row[bi] = -1; row[excl_idx] = -1
                labels[y, x] = int(np.argmax(row))

    return labels, influence


def snap_boundaries_to_features(labels: np.ndarray, h: np.ndarray, slope: np.ndarray,
                                 flow: np.ndarray, biome_kits: list[dict]) -> np.ndarray:
    """Pull biome boundaries onto natural terrain features (rivers, ridges, altitude bands).

    For each per-pair transition spec, walk the boundary band and re-label
    pixels so the boundary tracks high-flow, high-curvature, or specific
    altitude contours instead of arbitrary Voronoi distance.
    """
    from scipy.ndimage import binary_dilation, gaussian_filter
    out = labels.copy()
    ocean_mask = labels == 255
    n = len(biome_kits)

    # Compute "feature affinity" maps once
    river_field = flow                                          # high where rivers run
    # Ridge field = local height max via subtracting a gaussian-blurred copy
    h_blur = gaussian_filter(h, sigma=4)
    ridge_field = np.clip(h - h_blur, 0, None)
    ridge_field /= max(ridge_field.max(), 1e-9)

    # For each adjacent biome pair, find the boundary band and re-decide
    for a in range(n):
        kit_a = biome_kits[a]
        for b in range(n):
            if a == b:
                continue
            mask_a = out == a
            mask_b = out == b
            # Boundary band = pixels in A that are within `width_px` of B
            spec = kit_a["transitions"]["blend_neighbours"].get(
                biome_kits[b]["id"],
                kit_a["transitions"]["blend_neighbours"].get("default")
            )
            if spec is None:
                continue
            width = max(1, int(spec.get("width_px", 12)))
            priority = spec.get("feature_priority", "ridges")
            band = binary_dilation(mask_b, iterations=width) & mask_a
            band &= ~ocean_mask  # never reassign ocean pixels
            if not band.any():
                continue
            # Build a "should belong to A vs B" score per pixel in the band
            # based on the feature_priority field.
            if priority == "rivers":
                feat = river_field   # rivers belong on the lower-altitude biome
                # Heuristic: whichever of A,B has lower preferred altitude gets the river side
                a_lo = kit_a["terrain"]["altitude_range"][0]
                b_lo = biome_kits[b]["terrain"]["altitude_range"][0]
                a_wants_river = a_lo <= b_lo
            elif priority == "altitude_band":
                # Each biome wants its altitude band; a pixel with altitude closer
                # to A's range stays A
                a_center = sum(kit_a["terrain"]["altitude_range"]) / 2
                b_center = sum(biome_kits[b]["terrain"]["altitude_range"]) / 2
                feat = -np.abs(h - a_center) + np.abs(h - b_center)  # positive = A wins
                a_wants_river = None
            else:  # ridges (default)
                feat = ridge_field
                a_wants_river = None

            ys, xs = np.where(band)
            if priority == "rivers":
                # If A wants river, keep pixel as A where river_field is high; else flip to B
                if a_wants_river:
                    flip = feat[band] < np.percentile(feat[band], 50)
                else:
                    flip = feat[band] > np.percentile(feat[band], 50)
                target = np.full(ys.shape, a, dtype=labels.dtype)
                target[flip] = b
                out[ys, xs] = target
            elif priority == "altitude_band":
                # feat positive = stay A
                target = np.where(feat[band] >= 0, a, b).astype(labels.dtype)
                out[ys, xs] = target
            else:  # ridges
                # Boundary follows ridges — ridge pixels = boundary line
                # Keep band as A unless on a ridge (then flip to B)
                threshold = np.percentile(feat[band], 70)
                flip = feat[band] > threshold
                target = np.full(ys.shape, a, dtype=labels.dtype)
                target[flip] = b
                out[ys, xs] = target

            # Apply per-pair noise jitter so the boundary isn't perfectly straight.
            # Use SPATIALLY-COHERENT noise (FBM) not per-pixel random, so jitter
            # creates natural blobby boundaries instead of speckled noise.
            noise_strength = spec.get("noise_strength", 0.2)
            if noise_strength > 0 and len(ys) > 0:
                # Sample low-frequency noise at the band pixel locations
                # so adjacent pixels move together
                rng_local = np.random.default_rng(hash((a, b)) % (2**31))
                # Use a global FBM seeded by pair, sampled at this band's pixels
                fbm_seed = int(rng_local.integers(0, 1 << 31))
                # Cheap: build a 64x64 noise tile and sample
                noise_tile = rng_local.random((64, 64))
                # Smooth it
                from scipy.ndimage import gaussian_filter as gf
                noise_tile = gf(noise_tile, sigma=2.0)
                # Resample to image-space at band pixel coords
                ny = (ys * 64 // out.shape[0]).clip(0, 63)
                nx = (xs * 64 // out.shape[1]).clip(0, 63)
                noise_at_band = noise_tile[ny, nx]
                threshold = 0.5 + (0.5 - noise_strength * 0.4)
                jitter = noise_at_band > threshold
                if jitter.any():
                    out[ys[jitter], xs[jitter]] = np.where(out[ys[jitter], xs[jitter]] == a, b, a)

    return out


def shape_heightmap_per_biome(h: np.ndarray, labels: np.ndarray,
                              biome_kits: list[dict], seed: int) -> np.ndarray:
    """Per-biome height-bias remap + feature carving."""
    out = h.copy()
    # Apply soft height bias
    for bi, kit in enumerate(biome_kits):
        mask = labels == bi
        if not mask.any():
            continue
        bias = kit["terrain"]["height_bias"]
        rng_targets = {
            "flat_low":              (0.05, 0.30),
            "low_with_local_peaks":  (0.10, 0.55),
            "mid_rolling":           (0.30, 0.55),
            "mid_broken":            (0.30, 0.60),
            "high_smooth":           (0.55, 0.85),
            "high_broken":           (0.55, 0.95),
            "cavern":                (0.20, 0.50),
            "floating":              (0.40, 0.80),
        }
        target = rng_targets.get(bias, (0.30, 0.70))
        out = remap_altitude(out, mask, target, strength=0.4)

    # Smooth label boundaries to avoid sharp histogram cliffs at edges
    # (one-pass blur on the heightmap restricted to a thin boundary band)
    from scipy.ndimage import binary_dilation
    edges = np.zeros_like(labels, dtype=bool)
    for bi in range(len(biome_kits)):
        mask = labels == bi
        edge = binary_dilation(mask, iterations=2) & ~mask
        edges |= edge
    smooth = np.asarray(
        Image.fromarray((out * 255).astype(np.uint8), mode="L")
             .filter(ImageFilter.GaussianBlur(radius=2)),
        dtype=np.float32,
    ) / 255.0
    out[edges] = smooth[edges] * 0.6 + out[edges] * 0.4

    # Feature carving per biome
    for bi, kit in enumerate(biome_kits):
        mask = labels == bi
        if not mask.any():
            continue
        features = kit["terrain"].get("carve_features", [])
        out = apply_biome_features(out, mask, features, seed + bi * 17)
    return np.clip(out, 0, 1)


# --- Three-tier rendering ------------------------------------------------------
OCEAN_COLOR_DEEP = np.array([20, 50, 95], dtype=np.uint8)
OCEAN_COLOR_SHALLOW = np.array([80, 130, 180], dtype=np.uint8)


def render_world_view(labels: np.ndarray, biome_kits: list[dict], h: np.ndarray = None,
                       target_px: int = 256) -> Image.Image:
    """Low-resolution one-pixel-per-cell world map. Ocean is its own color."""
    rgb = np.zeros((labels.shape[0], labels.shape[1], 3), dtype=np.uint8)
    rgb[labels == 255] = OCEAN_COLOR_DEEP
    for bi, kit in enumerate(biome_kits):
        rgb[labels == bi] = kit["identity"]["world_color"]
    im = Image.fromarray(rgb, mode="RGB").resize((target_px, target_px), Image.BOX)
    return im


def render_regional_view(labels: np.ndarray, h: np.ndarray, biome_kits: list[dict],
                          target_px: int = 512) -> Image.Image:
    """Medium-zoom: palette fill + glyph hatching + smooth feature-aware boundaries."""
    rgb = np.zeros((labels.shape[0], labels.shape[1], 3), dtype=np.float32)
    # Ocean: deep blue with shallow-water lerp toward shoreline
    ocean_mask = labels == 255
    if ocean_mask.any():
        # Lerp toward shallow color near sea level (top of ocean range)
        ocean_h = h[ocean_mask]
        t = np.clip(ocean_h / 0.32, 0, 1).reshape(-1, 1)
        cols = OCEAN_COLOR_DEEP * (1 - t) + OCEAN_COLOR_SHALLOW * t
        rgb[ocean_mask] = cols
    for bi, kit in enumerate(biome_kits):
        mask = labels == bi
        palette = kit["identity"]["regional_palette"]
        # Use heightmap to interpolate within palette: low pixels = first color, high = last
        h_norm = h[mask]
        h_idx = np.clip(h_norm * (len(palette) - 1), 0, len(palette) - 1)
        idx_lo = np.floor(h_idx).astype(int)
        idx_hi = np.minimum(idx_lo + 1, len(palette) - 1)
        t = (h_idx - idx_lo).reshape(-1, 1)
        pal = np.asarray(palette, dtype=np.float32)
        cols = pal[idx_lo] * (1 - t) + pal[idx_hi] * t
        rgb[mask] = cols
    rgb_im = Image.fromarray(rgb.clip(0, 255).astype(np.uint8), mode="RGB")
    # Smooth a touch — boundaries are already intentional, just gentle anti-aliasing
    rgb_im = rgb_im.filter(ImageFilter.GaussianBlur(radius=1))
    if target_px and target_px != labels.shape[0]:
        rgb_im = rgb_im.resize((target_px, target_px), Image.LANCZOS)
    return rgb_im


def render_local_view(h: np.ndarray, labels: np.ndarray, biome_kits: list[dict]) -> Image.Image:
    """Full-resolution biome-tinted hypsometric view with hillshade."""
    # Start with biome regional palette colors at this pixel
    base = render_regional_view(labels, h, biome_kits, target_px=labels.shape[0])
    base_arr = np.asarray(base, dtype=np.float32)
    # Multiply by hillshade for relief
    shade = hillshade(h).astype(np.float32) / 255.0
    out = base_arr * (0.5 + 0.5 * shade.reshape(*shade.shape, 1))
    return Image.fromarray(out.clip(0, 255).astype(np.uint8), mode="RGB")


# --- Splat assembly ------------------------------------------------------------
def biome_to_splat(labels: np.ndarray, biome_kits: list[dict]) -> np.ndarray:
    """Pack first 4 biomes into RGBA splat (R=biome0, G=biome1, B=biome2, A=biome3)."""
    h, w = labels.shape
    splat = np.zeros((h, w, 4), dtype=np.uint8)
    for bi in range(min(4, len(biome_kits))):
        splat[..., bi] = (labels == bi).astype(np.uint8) * 255
    return splat


# --- Main ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--biomes", required=True,
                    help="comma-separated biome kit IDs (filenames in art_lab/biomes/world_kits/)")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--erosion", type=int, default=30,
                    help="thermal erosion iterations applied AFTER biome shaping")
    ap.add_argument("--world-view-px", type=int, default=128)
    ap.add_argument("--regional-view-px", type=int, default=512)
    ap.add_argument("--base-heightmap", type=Path, default=None,
                    help="(optional) use a real DEM PNG (16-bit grayscale) as the base heightmap "
                         "instead of synthetic FBM. e.g. a terrain bundle's height_16.png. "
                         "Will be resampled to --size and have biomes painted on top by altitude/slope.")
    ap.add_argument("--sea-level", type=float, default=0.32,
                    help="normalized 0..1 cutoff below which pixels are labeled ocean. "
                         "Default 0.32 (fantasy worlds). Set to 0.0 for real DEMs that have "
                         "no real ocean (e.g. Death Valley basin) — otherwise the basin floor "
                         "gets labeled as ocean and renders black.")
    args = ap.parse_args()

    # Load biome kits
    biome_ids = [b.strip() for b in args.biomes.split(",") if b.strip()]
    biome_kits = []
    for bid in biome_ids:
        path = KITS_DIR / f"{bid}.json"
        if not path.exists():
            raise SystemExit(f"biome kit missing: {path}")
        biome_kits.append(json.loads(path.read_text(encoding="utf-8")))

    print(f"[world] {len(biome_kits)} biomes: {[k['display_name'] for k in biome_kits]}")
    rng = np.random.default_rng(args.seed)

    out_dir = OUT_ROOT / args.id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "godot").mkdir(parents=True, exist_ok=True)

    if args.base_heightmap:
        print(f"[1/8] real-DEM base heightmap from {args.base_heightmap}")
        if not args.base_heightmap.exists():
            raise SystemExit(f"base heightmap not found: {args.base_heightmap}")
        h_im = Image.open(args.base_heightmap)
        # Convert via 'F' mode for any bit depth
        if h_im.size != (args.size, args.size):
            # Resample through F mode (LANCZOS doesn't accept I;16 directly in PIL 12+)
            h_arr = np.asarray(h_im).astype(np.float32)
            if h_arr.max() > 1.0:
                h_arr = h_arr / (65535.0 if h_arr.max() > 256 else 255.0)
            h_im = Image.fromarray(h_arr, mode="F").resize((args.size, args.size), Image.LANCZOS)
            h = np.asarray(h_im, dtype=np.float32)
        else:
            h = np.asarray(h_im, dtype=np.float32)
            if h.max() > 1.0:
                h = h / (65535.0 if h.max() > 256 else 255.0)
        h = np.clip(h, 0.0, 1.0)
        # Re-normalize to use full 0-1 range so biome altitude bands hit reasonable thresholds
        h = (h - h.min()) / (h.max() - h.min() + 1e-9)
    else:
        print(f"[1/8] continental base heightmap {args.size}x{args.size} (continent + ranges + detail)")
        h = continental_heightmap(args.size, args.seed)

    print(f"[2/8] base slope")
    slope = slope_from_height(h)

    print(f"[3/8] place {len(biome_kits)*5} biome seeds (Poisson + priority)")
    seeds = place_biome_seeds(args.size, biome_kits, rng)
    print(f"  placed {len(seeds)} seeds")

    print(f"[4a/8] compute influence + initial label image (sea_level={args.sea_level})")
    labels, influence = compute_influence_fields(args.size, seeds, biome_kits, h, slope,
                                                  sea_level=args.sea_level)

    print(f"[4b/8] snap boundaries to terrain features (rivers/ridges/altitude)")
    base_flow = flow_accumulation_d8(h, iterations=10)
    labels = snap_boundaries_to_features(labels, h, slope, base_flow, biome_kits)

    print(f"[5/8] shape heightmap per biome (bias + features)")
    h = shape_heightmap_per_biome(h, labels, biome_kits, args.seed)

    if args.erosion > 0:
        print(f"[6/8] thermal erosion x{args.erosion}")
        h = thermal_erode(h, iterations=args.erosion)

    print(f"[7/8] re-derive slope/flow/water/normals from final heightmap")
    slope = slope_from_height(h)
    flow = flow_accumulation_d8(h, iterations=15)
    biome_rgb = np.zeros((args.size, args.size, 3), dtype=np.uint8)
    for bi, kit in enumerate(biome_kits):
        biome_rgb[labels == bi] = kit["identity"]["world_color"]

    splat = biome_to_splat(labels, biome_kits)
    veg = vegetation_density(labels, slope, h)
    water = water_mask(h, sea_level=max(0.0, args.sea_level - 0.02))

    print(f"[8/8] write three views + bundle layers")
    # Standard bundle layers
    to_png_16bit(h, out_dir / "height_16.png")
    normal_from_height(h).save(out_dir / "normal.png")
    Image.fromarray(splat, mode="RGBA").save(out_dir / "splat_rgba.png")
    Image.fromarray(biome_rgb, mode="RGB").save(out_dir / "biome.png")
    Image.fromarray(labels, mode="L").save(out_dir / "biome_labels.png")
    # Also save a categorical-color version for human review
    label_rgb = np.zeros((args.size, args.size, 3), dtype=np.uint8)
    for bi, kit in enumerate(biome_kits):
        label_rgb[labels == bi] = kit["identity"]["world_color"]
    Image.fromarray(label_rgb, mode="RGB").save(out_dir / "biome_labels_colored.png")
    Image.fromarray(veg, mode="L").save(out_dir / "vegetation_density.png")
    Image.fromarray(water, mode="L").save(out_dir / "water_mask.png")
    Image.fromarray((flow * 255).astype(np.uint8), mode="L").save(out_dir / "flow.png")
    hypsometric_preview(h).save(out_dir / "preview_hypsometric.png")
    Image.fromarray(hillshade(h), mode="L").save(out_dir / "preview_hillshade.png")

    # Three-zoom views
    render_world_view(labels, biome_kits, h, args.world_view_px).save(out_dir / "world_view.png")
    render_regional_view(labels, h, biome_kits, args.regional_view_px).save(out_dir / "regional_view.png")
    render_local_view(h, labels, biome_kits).save(out_dir / "local_view.png")

    # Godot scaffolding
    (out_dir / "godot" / "terrain3d_import.json").write_text(GODOT_TERRAIN3D_HINT, encoding="utf-8")
    (out_dir / "godot" / "heightmapshape3d.tres").write_text(
        heightmapshape3d_tres("../height_16.png"), encoding="utf-8"
    )

    # Pull DEM metadata (bbox + elevation range) from upstream tool's manifest
    # so the Godot stager can compute true world-space terrain dimensions
    # instead of falling back to fixed 512m × 64m.
    dem_meta = _load_dem_meta(args.id)

    # Manifest
    metadata = {
        "id": args.id,
        "created": datetime.now(timezone.utc).isoformat(),
        "source": "world_biome_engine",
        "base_heightmap": str(args.base_heightmap) if args.base_heightmap else "synthetic_continental",
        "biomes": [k["id"] for k in biome_kits],
        "biome_display_names": [k["display_name"] for k in biome_kits],
        "size": args.size, "seed": args.seed,
        "erosion": args.erosion,
        "n_seeds": len(seeds),
        "biome_seed_counts": {k["id"]: sum(1 for _, _, b in seeds if biome_kits[b]["id"] == k["id"]) for k in biome_kits},
        "biome_pixel_counts": {k["id"]: int((labels == bi).sum()) for bi, k in enumerate(biome_kits)},
        "dem_meta": dem_meta,
        "views": {
            "world": "world_view.png",
            "regional": "regional_view.png",
            "local": "local_view.png",
        },
        "layers": {
            "height": "height_16.png",
            "normal": "normal.png",
            "splat": "splat_rgba.png",
            "biome_rgb": "biome.png",
            "biome_labels": "biome_labels.png",
            "vegetation_density": "vegetation_density.png",
            "water_mask": "water_mask.png",
            "flow": "flow.png",
        },
    }
    (out_dir / "world.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"WORLD: {args.id}")
    print(f"  size:    {args.size}")
    print(f"  biomes:  {len(biome_kits)}")
    for k in biome_kits:
        bi = next(i for i, kk in enumerate(biome_kits) if kk["id"] == k["id"])
        n = (labels == bi).sum()
        pct = n / labels.size * 100
        print(f"    {k['display_name']:20s} {pct:5.1f}%")
    print(f"  views:   world / regional / local")
    print(f"  out:     {out_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
