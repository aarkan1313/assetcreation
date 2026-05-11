"""F.3.4 — Generalized M11 bundle library.

Extracts the reusable logic from `build_m11_fourway_corner_proof.py` and
`build_m11_junction_layer_proof.py` and exposes it as a library any
generator can call. M11's hand-authored builder becomes the reference;
this library lets F.3 invoke the same logic with per-bundle inputs.

Public API:
  build_bundle(spec) -> dict of paths emitted

A `spec` is a BundleSpec dataclass describing:
  - output paths (texture_out, topo_out, manifest_out)
  - heightmap dims, world size, elev envelope, seed
  - the biome kit's 5 slot material ids (for the .tres binding)
  - the "domain composition": 1-4 sub-domains and their weight masks
  - optional neighbor-edge constraints (F.3.1 contiguity)

Library responsibilities (one per function, mirrors M11):
  - build_domain_fields_general:  procedural weight masks per domain
  - build_height_general:         per-domain height contributions blended
  - build_layers_general:         RGBA splat weights + scatter masks
  - build_macro_preview_general:  per-pixel macro composited from
                                  domain-material RGB references
  - emit_bundle:                  writes all outputs (PNG + .tres + meta)

A single-biome bundle is a 1-domain spec (weights = 1 everywhere).
A boundary bundle is a 2-domain spec with crossfade weights at the edge.
A corner bundle is a 4-domain spec (full M11 fourway case).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]  # world3/
DEFAULT_CATALOG = ROOT / "materials" / "catalog.json"

# Shader slot conventions (matches terrain_splat_unified.gdshader's 5 slots).
SLOTS = ["grass", "dirt", "rock_light", "rock_dark", "snow"]
BASE_MAPS = ["albedo", "normal", "roughness", "ao"]
DETAIL_MAPS = ["detail_albedo", "detail_normal", "detail_roughness"]
SHORT_MAP = {
    "albedo": "albedo",
    "normal": "normal",
    "roughness": "rough",
    "ao": "ao",
    "detail_albedo": "detail_albedo",
    "detail_normal": "detail_normal",
    "detail_roughness": "detail_rough",
}


@dataclass
class Domain:
    """One sub-region of a bundle. M11 fourway has 4 domains; a
    single-biome bundle has 1 domain with weight = 1.0 everywhere."""
    name: str
    material_id: str        # catalog material id (drives the per-domain macro RGB ref)
    weight_field: np.ndarray  # (h, w) float32 in 0..1; weights sum to 1 across all domains
    elev_offset_m: float = 0.0   # bias for this domain's height contribution
    elev_range_m: float = 12.0


@dataclass
class FourwayBundleSpec:
    """Specialized spec for M11-style fourway bundles. Distinct from
    BundleSpec because it carries 4 fixed-quadrant domains + a real
    source-stack reference (real DEM + ortho) + per-quadrant elev ranges.

    Use this when you want to recreate M11 fourway's compositional
    pattern: a real-source crop in one quadrant, 3 procedural domains
    in the others, all blended via split_x/split_y."""
    bundle_id: str
    biome_kit: str
    width_px: int
    height_px: int
    world_size_m: tuple[float, float]
    seed: int
    # Quadrant material ids (used both for macro RGB compositing and the
    # per-bundle .tres slot bindings)
    nw_material_id: str
    ne_material_id: str
    se_material_id: str
    sw_material_id: str
    # Per-quadrant elev range in meters
    nw_elev_range_m: float
    ne_elev_range_m: float
    se_elev_range_m: float
    sw_elev_range_m: float
    # Optional real-source anchoring (M11's pattern: SW quadrant draws
    # heights + macro from a real Gloss source). When None, SW is purely
    # procedural like the others.
    source_height_m: np.ndarray | None
    source_rgb: np.ndarray | None
    # Output paths
    bundle_dir: Path
    layers_dir: Path
    edges_dir: Path
    # Optional shader slot override mapping (defaults to a sensible
    # mapping per quadrant materials but you can override per-bundle)
    slot_materials: dict[str, str] = field(default_factory=dict)


@dataclass
class BundleSpec:
    bundle_id: str
    biome_kit: str            # for the .tres slot bindings
    width_px: int
    height_px: int
    world_size_m: tuple[float, float]
    elev_min_m: float
    elev_range_m: float
    seed: int
    domains: list[Domain]     # 1-4 domains
    # Output paths
    bundle_dir: Path
    layers_dir: Path
    edges_dir: Path
    # F.3.1 contiguity (optional)
    neighbor_west_edge_meters: np.ndarray | None = None
    neighbor_north_edge_meters: np.ndarray | None = None
    neighbor_edge_feather_px: int = 32


# ----------------------------------------------------------------------
# Math helpers (copies of eco lib functions — kept here so the library
# is self-contained and doesn't import build_ecotone_layer_proof)
# ----------------------------------------------------------------------

def normalize01(arr: np.ndarray, low_pct: float = 1.0, high_pct: float = 99.0) -> np.ndarray:
    lo = float(np.percentile(arr, low_pct))
    hi = float(np.percentile(arr, high_pct))
    if hi <= lo:
        return np.zeros_like(arr, dtype=np.float32)
    return np.clip((arr - lo) / max(hi - lo, 1e-6), 0.0, 1.0).astype(np.float32)


def smooth_noise(width: int, height: int, grid: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    small_w = max(2, int(np.ceil(width / grid)))
    small_h = max(2, int(np.ceil(height / grid)))
    raw = rng.random((small_h, small_w), dtype=np.float32)
    img = Image.fromarray((raw * 255.0).astype(np.uint8), mode="L")
    img = img.resize((width, height), Image.Resampling.BICUBIC)
    return np.asarray(img, dtype=np.float32) / 255.0


def gaussian_gray(arr: np.ndarray, radius: float) -> np.ndarray:
    if radius <= 0.0:
        return arr
    img = Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), mode="L")
    return np.asarray(img.filter(ImageFilter.GaussianBlur(radius=radius)), dtype=np.float32) / 255.0


# ----------------------------------------------------------------------
# Per-domain procedural macro RGB reference
# (M11 builds these in build_m11_junction_layer_proof.py; we reproduce
# the logic so the library doesn't depend on that script)
# ----------------------------------------------------------------------

def load_catalog(catalog_path: Path | None = None) -> dict[str, dict]:
    path = catalog_path if catalog_path is not None else DEFAULT_CATALOG
    data = json.loads(path.read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in data.get("materials", [])}


def build_procedural_macro(material_id: str, catalog: dict[str, dict],
                            width: int, height: int, seed: int) -> np.ndarray:
    """Build a tiled RGB macro reference for one catalog material.
    Used for the bundle's macro_preview compositing — each domain's
    catalog material is sampled here and then blended per-pixel by the
    domain weights."""
    if material_id not in catalog:
        raise KeyError(f"material '{material_id}' not in catalog")
    entry = catalog[material_id]
    albedo_path_str = entry["pbr_maps"]["albedo"]
    albedo_disk = (ROOT / albedo_path_str) if not Path(albedo_path_str).is_absolute() else Path(albedo_path_str)
    if not albedo_disk.exists():
        # Some catalog entries store paths as "world3/textures/..."
        alt = ROOT.parent / albedo_path_str
        if alt.exists():
            albedo_disk = alt
    img = Image.open(albedo_disk).convert("RGB")
    arr = np.asarray(img, dtype=np.float32) / 255.0
    # Tile to bundle dims
    th, tw = height, width
    h, w = arr.shape[:2]
    rep_h = (th + h - 1) // h
    rep_w = (tw + w - 1) // w
    tiled = np.tile(arr, (rep_h, rep_w, 1))[:th, :tw]
    # Add a small noise-driven warm/cool wash so the macro reads as
    # natural variation instead of a uniform tile.
    low = smooth_noise(width, height, 96, seed + 31)
    fine = smooth_noise(width, height, 24, seed + 37)
    wash = (low * 0.7 + fine * 0.3 - 0.5).astype(np.float32)
    return np.clip(tiled + wash[:, :, None] * 0.06, 0.0, 1.0)


# ----------------------------------------------------------------------
# Domain fields — replaces M11's hardcoded 4-quadrant split with a
# general "use whatever domain weights the spec gave us, plus derived
# junction/quad/cross-wash masks for natural blending and scatter"
# ----------------------------------------------------------------------

def build_split_quadrant_fields(width: int, height: int, seed: int) -> dict[str, np.ndarray]:
    """M11 fourway's split_x/split_y quadrant decomposition.
    Returns 4 weight fields summing to 1.0 per pixel, plus 3 auxiliary
    masks (junction, quad_core, cross_wash) for blend softening.

    Direct port from build_m11_fourway_corner_proof.py:build_domain_fields.
    Use this when a bundle should look like M11 fourway — four domains
    meeting at a noisy split point near the bundle center.
    """
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    x = (xx / max(width - 1, 1) - 0.5) * 2.0
    y = (yy / max(height - 1, 1) - 0.5) * 2.0

    low = smooth_noise(width, height, 164, seed + 11) * 2.0 - 1.0
    med = smooth_noise(width, height, 64, seed + 17) * 2.0 - 1.0
    fine = smooth_noise(width, height, 24, seed + 23) * 2.0 - 1.0

    split_x = -0.05 + low * 0.17 + np.sin((y * 1.18 + med * 0.28) * np.pi) * 0.15
    split_y = 0.04 + med * 0.16 + np.sin((x * 1.02 - low * 0.32) * np.pi) * 0.14
    east = np.clip(((x - split_x) / 0.56) * 0.5 + 0.5, 0.0, 1.0)
    south = np.clip(((y - split_y) / 0.60) * 0.5 + 0.5, 0.0, 1.0)
    east = east * east * (3.0 - 2.0 * east)
    south = south * south * (3.0 - 2.0 * south)

    weights = np.stack(
        [
            (1.0 - east) * (1.0 - south),  # NW (grass in M11)
            east * (1.0 - south),          # NE (fantasy in M11)
            east * south,                  # SE (canyon in M11)
            (1.0 - east) * south,          # SW (source scrub in M11)
        ],
        axis=2,
    )
    eddy = np.exp(-((x * x + y * y) / 0.36)) * 0.18
    weights[:, :, 0] += eddy * np.clip(0.62 - south, 0.0, 1.0)
    weights[:, :, 1] += eddy * np.clip(east - 0.38, 0.0, 1.0)
    weights[:, :, 2] += eddy * np.clip(south - 0.36, 0.0, 1.0)
    weights[:, :, 3] += eddy * np.clip(0.60 - east, 0.0, 1.0)
    weights += np.stack(
        [
            np.maximum(low, 0.0) * 0.025,
            np.maximum(med, 0.0) * 0.024,
            np.maximum(-low, 0.0) * 0.025,
            np.maximum(-med, 0.0) * 0.024,
        ],
        axis=2,
    )
    weights /= np.maximum(np.sum(weights, axis=2, keepdims=True), 1e-6)

    for idx in range(4):
        weights[:, :, idx] = gaussian_gray(weights[:, :, idx], 1.15)
    weights /= np.maximum(np.sum(weights, axis=2, keepdims=True), 1e-6)

    max_w = np.max(weights, axis=2)
    junction = np.clip((1.0 - max_w) / 0.70, 0.0, 1.0)
    junction = np.power(junction, 0.68)
    quad = np.clip(np.prod(weights, axis=2) * 430.0, 0.0, 1.0)
    quad = gaussian_gray(quad, 3.2)

    rel_x = x - split_x
    rel_y = y - split_y
    cross_a = np.exp(-np.square((rel_x + rel_y + low * 0.10) / 0.24))
    cross_b = np.exp(-np.square((rel_x - rel_y + med * 0.12) / 0.24))
    cross_wash = gaussian_gray(np.clip((cross_a + cross_b) * junction * 0.42, 0.0, 1.0), 2.0)

    return {
        "quadrant_nw": weights[:, :, 0].astype(np.float32),
        "quadrant_ne": weights[:, :, 1].astype(np.float32),
        "quadrant_se": weights[:, :, 2].astype(np.float32),
        "quadrant_sw": weights[:, :, 3].astype(np.float32),
        "junction_weight": junction.astype(np.float32),
        "quad_core_weight": quad.astype(np.float32),
        "cross_wash_weight": cross_wash.astype(np.float32),
        "noise_low": low.astype(np.float32),
        "noise_med": med.astype(np.float32),
        "noise_fine": fine.astype(np.float32),
    }


def build_domain_aux_fields(domains: list[Domain], width: int, height: int,
                             seed: int) -> dict[str, np.ndarray]:
    """Compute junction / quad / cross-wash / noise auxiliary fields.
    These are the "blend zone" masks M11 uses to soften domain borders
    and drive scatter masks. For a single-domain spec they're all-zero;
    for multi-domain specs they activate where weights overlap."""
    low = smooth_noise(width, height, 164, seed + 11) * 2.0 - 1.0
    med = smooth_noise(width, height, 64, seed + 17) * 2.0 - 1.0
    fine = smooth_noise(width, height, 24, seed + 23) * 2.0 - 1.0

    # Junction: where any single domain doesn't dominate (i.e. multiple
    # domains contribute). For single-domain bundles, junction ≈ 0.
    if len(domains) <= 1:
        junction = np.zeros((height, width), dtype=np.float32)
        quad = np.zeros((height, width), dtype=np.float32)
        cross_wash = np.zeros((height, width), dtype=np.float32)
    else:
        stack = np.stack([d.weight_field for d in domains], axis=2).astype(np.float32)
        max_w = np.max(stack, axis=2)
        junction = np.clip((1.0 - max_w) / 0.70, 0.0, 1.0)
        junction = np.power(junction, 0.68)
        # Quad core only meaningful when ≥3 domains overlap
        if len(domains) >= 3:
            quad = np.clip(np.prod(stack, axis=2) * (100.0 ** len(domains)), 0.0, 1.0)
            quad = gaussian_gray(quad, 3.2)
        else:
            quad = np.zeros((height, width), dtype=np.float32)
        # Cross wash: thin "channel" through the junction band
        yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
        x = (xx / max(width - 1, 1) - 0.5) * 2.0
        y = (yy / max(height - 1, 1) - 0.5) * 2.0
        cross_a = np.exp(-np.square((x + y + low * 0.10) / 0.24))
        cross_b = np.exp(-np.square((x - y + med * 0.12) / 0.24))
        cross_wash = gaussian_gray(np.clip((cross_a + cross_b) * junction * 0.42, 0.0, 1.0), 2.0)

    return {
        "junction_weight": junction.astype(np.float32),
        "quad_core_weight": quad.astype(np.float32),
        "cross_wash_weight": cross_wash.astype(np.float32),
        "noise_low": low.astype(np.float32),
        "noise_med": med.astype(np.float32),
        "noise_fine": fine.astype(np.float32),
    }


# ----------------------------------------------------------------------
# Height
# ----------------------------------------------------------------------

def build_height_general(spec: BundleSpec, aux: dict[str, np.ndarray]) -> np.ndarray:
    """Per-domain height blended via the domain weights. Each domain
    contributes its own procedural heightfield centered on
    `elev_offset_m`. The base envelope is `spec.elev_min_m + elev_range_m`."""
    w, h = spec.width_px, spec.height_px
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    x = xx / max(w - 1, 1)
    y = yy / max(h - 1, 1)

    target_mid = spec.elev_min_m + spec.elev_range_m * 0.5

    blended = np.zeros((h, w), dtype=np.float32)
    for i, d in enumerate(spec.domains):
        low = smooth_noise(w, h, 210, spec.seed + 101 + i * 100)
        med = smooth_noise(w, h, 72, spec.seed + 107 + i * 100)
        small = smooth_noise(w, h, 28, spec.seed + 113 + i * 100)
        ridge = 0.022 * np.sin((x * 1.35 - y * 0.42 + med * 0.12) * np.pi * 2.0)
        slope = x * 0.22 + y * 0.10
        field = slope + low * 0.22 + med * 0.06 + small * 0.012 + ridge
        field = normalize01(field)
        domain_h = (target_mid + d.elev_offset_m
                    + (field - 0.5) * d.elev_range_m)
        blended += domain_h.astype(np.float32) * d.weight_field.astype(np.float32)

    # Soften junctions like M11 does
    if len(spec.domains) > 1:
        low_relief = gaussian_gray(normalize01(blended), 2.8)
        low_relief = float(np.min(blended)) + low_relief * max(float(np.max(blended) - np.min(blended)), 1e-6)
        blend = np.clip(aux["junction_weight"] * 0.58 + aux["quad_core_weight"] * 0.20, 0.0, 0.76)
        blended = blended * (1.0 - blend) + low_relief * blend
        blended -= aux["cross_wash_weight"] * (spec.elev_range_m * 0.12)

    # F.3.1 edge constraints
    if spec.neighbor_west_edge_meters is not None:
        blended = _apply_edge_meters(blended, spec.neighbor_west_edge_meters, "west", spec.neighbor_edge_feather_px)
    if spec.neighbor_north_edge_meters is not None:
        blended = _apply_edge_meters(blended, spec.neighbor_north_edge_meters, "north", spec.neighbor_edge_feather_px)
    if (spec.neighbor_west_edge_meters is not None
            and spec.neighbor_north_edge_meters is not None):
        # Corner reconcile so both edges stay byte-exact (per F.3.1 closure)
        corner_avg = 0.5 * (
            float(spec.neighbor_west_edge_meters[0])
            + float(spec.neighbor_north_edge_meters[0])
        )
        blended[:, 0] = _resampled(spec.neighbor_west_edge_meters, h)
        blended[0, :] = _resampled(spec.neighbor_north_edge_meters, w)
        blended[0, 0] = corner_avg

    return blended.astype(np.float32)


def _resampled(values: np.ndarray, n: int) -> np.ndarray:
    if values.shape[0] == n:
        return values.astype(np.float32)
    idx = np.linspace(0.0, float(values.shape[0] - 1), n, dtype=np.float32)
    return np.interp(idx, np.arange(values.shape[0], dtype=np.float32), values).astype(np.float32)


def _apply_edge_meters(field: np.ndarray, edge_values: np.ndarray, kind: str, feather: int) -> np.ndarray:
    h, w = field.shape
    out = field.copy()
    if kind == "west":
        edge = _resampled(edge_values, h)
        feather = max(1, min(feather, w))
        weights = np.linspace(1.0, 0.0, feather, dtype=np.float32)
        for c in range(feather):
            t = weights[c]
            out[:, c] = edge * t + out[:, c] * (1.0 - t)
        out[:, 0] = edge
    elif kind == "north":
        edge = _resampled(edge_values, w)
        feather = max(1, min(feather, h))
        weights = np.linspace(1.0, 0.0, feather, dtype=np.float32)
        for r in range(feather):
            t = weights[r]
            out[r, :] = edge * t + out[r, :] * (1.0 - t)
        out[0, :] = edge
    return out


# ----------------------------------------------------------------------
# Splat weights + scatter masks
# ----------------------------------------------------------------------

def build_layers_general(spec: BundleSpec, height_m: np.ndarray,
                          aux: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Compute RGBA splat weights + scatter masks. The splat's 4 channels
    map to the shader's 4 explicit slots (grass/dirt/rock_light/rock_dark);
    snow is the implicit remainder slot."""
    h, w = height_m.shape
    grad_y, grad_x = np.gradient(height_m)
    slope = normalize01(np.sqrt(grad_x * grad_x + grad_y * grad_y), 42.0, 99.7)

    junction = aux["junction_weight"]
    quad = aux["quad_core_weight"]
    cross_wash = aux["cross_wash_weight"]
    low = (aux["noise_low"] + 1.0) * 0.5
    med = (aux["noise_med"] + 1.0) * 0.5

    # Derive an aggregate "domain feature" so single-biome bundles still
    # have natural slot variation (otherwise R=1 everywhere again).
    # Strategy: dominant domain's weight modulated by height + slope +
    # noise. Each slot is a function of height-band + slope + noise.
    h_range = max(float(height_m.max() - height_m.min()), 1e-6)
    h_norm = (height_m - height_m.min()) / h_range

    soil_exposure = np.clip(junction * (0.13 + med * 0.28) + quad * 0.20 + cross_wash * 0.22, 0.0, 1.0)
    rock_cluster = np.clip(slope * 0.78 + junction * slope * 0.40, 0.0, 1.0)
    dry_grass_density = np.clip((1.0 - slope) * (0.46 + low * 0.26), 0.0, 1.0)
    wash_line = np.clip(cross_wash * 0.70, 0.0, 1.0)
    no_scatter = np.clip(slope * 0.82 + rock_cluster * 0.28, 0.0, 1.0)

    # 4 explicit splat channels — M11-style mix from height + slope +
    # organic noise. For single-biome bundles, the per-pixel mix
    # still varies (because of slope and noise) so the rendered bundle
    # uses all 5 catalog materials (snow as implicit remainder).
    w_grass = np.clip(0.95 - slope * 0.70 - np.abs(h_norm - 0.40) * 0.55
                      + (low - 0.5) * 0.30, 0.0, 1.0)
    w_dirt = np.clip(0.50 - slope * 0.30 - np.abs(h_norm - 0.20) * 0.70
                     + (med - 0.5) * 0.25 + soil_exposure * 0.30, 0.0, 1.0)
    w_rl = np.clip(0.45 + slope * 0.45 - np.abs(h_norm - 0.60) * 0.40
                   + (low - 0.5) * 0.20, 0.0, 1.0)
    w_rd = np.clip(0.30 + slope * 0.90 + np.maximum(h_norm - 0.70, 0.0) * 0.85
                   + rock_cluster * 0.30, 0.0, 1.0)

    stack = np.stack([w_grass, w_dirt, w_rl, w_rd], axis=2).astype(np.float32)
    stack = np.power(np.maximum(stack, 1e-5), 1.10)
    stack /= np.maximum(np.sum(stack, axis=2, keepdims=True), 1e-6)

    return {
        "splat_grass": stack[..., 0],
        "splat_dirt": stack[..., 1],
        "splat_rock_light": stack[..., 2],
        "splat_rock_dark": stack[..., 3],
        "soil_exposure_mask": soil_exposure.astype(np.float32),
        "rock_cluster_mask": rock_cluster.astype(np.float32),
        "dry_grass_density_mask": dry_grass_density.astype(np.float32),
        "wash_line_mask": wash_line.astype(np.float32),
        "no_scatter_mask": no_scatter.astype(np.float32),
        "junction_weight": junction,
        "quad_core_weight": quad,
        "cross_wash_weight": cross_wash,
        "slope": slope.astype(np.float32),
    }


# ----------------------------------------------------------------------
# Macro preview composition
# ----------------------------------------------------------------------

def build_macro_preview_general(spec: BundleSpec, layers: dict[str, np.ndarray],
                                  catalog: dict[str, dict]) -> np.ndarray:
    """Per-pixel macro composited from each domain's catalog albedo.
    For a single-domain bundle, the macro is just that material's
    tiled albedo (plus M11's light/shadow/noise tinting)."""
    w, h = spec.width_px, spec.height_px
    seed = spec.seed
    low = smooth_noise(w, h, 72, seed + 501)
    fine = smooth_noise(w, h, 24, seed + 503)

    # Sum each domain's macro weighted by its weight field.
    preview = np.zeros((h, w, 3), dtype=np.float32)
    total_w = np.zeros((h, w), dtype=np.float32)
    for i, d in enumerate(spec.domains):
        rgb = build_procedural_macro(d.material_id, catalog, w, h, seed + 200 + i * 100)
        # M11-style brightness modulation
        rgb = np.clip(rgb * (0.88 + low[:, :, None] * 0.12 + fine[:, :, None] * 0.04), 0.0, 1.0)
        preview += rgb * d.weight_field[:, :, None]
        total_w += d.weight_field

    # Normalize where domain weights covered <1 (shouldn't happen after
    # weight normalization but defensive)
    nz = total_w > 1e-3
    preview[nz] = preview[nz] / total_w[nz, None]

    return np.clip(preview, 0.0, 1.0)


# ----------------------------------------------------------------------
# .tres emit (delegates to f33_bundle_material — we're already aligned
# with the .tres shape it writes)
# ----------------------------------------------------------------------

def write_per_bundle_material(spec: BundleSpec, macro_path: Path,
                                weight_mask_path: Path, splat_path: Path,
                                out_tres: Path) -> None:
    """Write the per-bundle ShaderMaterial .tres."""
    from f33_bundle_material import write_bundle_material
    write_bundle_material(
        out_path=out_tres,
        source_macro=macro_path,
        source_macro_weight_mask=weight_mask_path,
        splat_weights=splat_path,
        biome_kit=spec.biome_kit,
    )


# ----------------------------------------------------------------------
# Edge emit (F.3.1 contiguity)
# ----------------------------------------------------------------------

def write_edge_constraints(spec: BundleSpec, height_m: np.ndarray) -> None:
    spec.edges_dir.mkdir(parents=True, exist_ok=True)
    east_values = [float(v) for v in height_m[:, -1]]
    south_values = [float(v) for v in height_m[-1, :]]
    (spec.edges_dir / "east_edge.json").write_text(
        json.dumps({"axis": "east", "values_m": east_values}, indent=2),
        encoding="utf-8",
    )
    (spec.edges_dir / "south_edge.json").write_text(
        json.dumps({"axis": "south", "values_m": south_values}, indent=2),
        encoding="utf-8",
    )


# ----------------------------------------------------------------------
# Top-level builder
# ----------------------------------------------------------------------

def build_fourway_height(spec: FourwayBundleSpec, fields: dict[str, np.ndarray]) -> np.ndarray:
    """Direct port of M11's build_height for fourway bundles.
    Each quadrant has its own procedural heightfield centered at the
    bundle midline (or anchored to the real source for SW)."""
    w, h = spec.width_px, spec.height_px
    seed = spec.seed
    if spec.source_height_m is not None:
        source_h = spec.source_height_m.astype(np.float32)
        target_mid = float(np.median(source_h))
    else:
        # No real source — synthesize a baseline
        target_mid = 250.0  # arbitrary baseline; per-quad offsets do the rest
        source_h = np.full((h, w), target_mid, dtype=np.float32)

    # Per-quadrant heights, following M11's offset pattern
    nw_h = (build_height_general_single(w, h, seed + 300, target_mid - spec.nw_elev_range_m * 0.42, spec.nw_elev_range_m))
    ne_h = (build_height_general_single(w, h, seed + 400, target_mid - spec.ne_elev_range_m * 0.50, spec.ne_elev_range_m) - 1.5)
    se_h = (build_height_general_single(w, h, seed + 500, target_mid - spec.se_elev_range_m * 0.38, spec.se_elev_range_m) + 2.2)

    # Center each quadrant on target_mid before blending
    nw_h += target_mid - float(np.median(nw_h))
    ne_h += target_mid - float(np.median(ne_h))
    se_h += target_mid - float(np.median(se_h))

    hard = (
        nw_h * fields["quadrant_nw"]
        + ne_h * fields["quadrant_ne"]
        + se_h * fields["quadrant_se"]
        + source_h * fields["quadrant_sw"]
    )
    low_relief = gaussian_gray(normalize01(hard), 2.8)
    low_relief = float(np.min(hard)) + low_relief * max(float(np.max(hard) - np.min(hard)), 1e-6)
    blend = np.clip(fields["junction_weight"] * 0.58 + fields["quad_core_weight"] * 0.20, 0.0, 0.76)
    out = hard * (1.0 - blend) + low_relief * blend
    out -= fields["cross_wash_weight"] * 2.1
    return out.astype(np.float32)


def build_height_general_single(w: int, h: int, seed: int, elev_min: float, elev_range: float) -> np.ndarray:
    """Single-domain procedural heightfield. Used internally by
    build_fourway_height per quadrant. Same shape as the legacy
    procedural builder's build_height but pure-function."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    x = xx / max(w - 1, 1)
    y = yy / max(h - 1, 1)
    low = smooth_noise(w, h, 210, seed + 101)
    med = smooth_noise(w, h, 72, seed + 107)
    small = smooth_noise(w, h, 28, seed + 113)
    channel_wave = np.sin((x * 0.78 + y * 1.18 + low * 0.08) * np.pi * 2.0)
    channel = -0.045 * np.exp(-np.square(channel_wave / 0.35))
    ridge = 0.022 * np.sin((x * 1.35 - y * 0.42 + med * 0.12) * np.pi * 2.0)
    slope = x * 0.22 + y * 0.10
    field = slope + low * 0.22 + med * 0.06 + small * 0.012 + channel + ridge
    field = normalize01(field)
    img = Image.fromarray(np.clip(field * 255.0, 0, 255).astype(np.uint8), mode="L")
    field = np.asarray(img.filter(ImageFilter.GaussianBlur(radius=3.0)), dtype=np.float32) / 255.0
    norm = normalize01(field)
    return elev_min + norm * elev_range


def build_fourway_layers(spec: FourwayBundleSpec, height_m: np.ndarray,
                          fields: dict[str, np.ndarray],
                          source_rgb: np.ndarray | None,
                          quad_rgbs: list[np.ndarray]) -> dict[str, np.ndarray]:
    """M11's build_layers ported. Returns RGBA splat (per shader slot)
    + scatter masks. Splat channels: grass, dirt (fantasy), rock_light
    (canyon), rock_dark (source scrub). Snow is implicit remainder."""
    nw_rgb, ne_rgb, se_rgb, sw_rgb = quad_rgbs
    # If the SW quadrant has a real source, use that; else fall back to
    # the SW procedural macro RGB
    sw_feature_rgb = source_rgb if source_rgb is not None else sw_rgb

    sw_luma = sw_feature_rgb[:, :, 0] * 0.2126 + sw_feature_rgb[:, :, 1] * 0.7152 + sw_feature_rgb[:, :, 2] * 0.0722
    green_excess = np.maximum(sw_feature_rgb[:, :, 1] - np.maximum(sw_feature_rgb[:, :, 0], sw_feature_rgb[:, :, 2]) * 0.86, 0.0)
    dark_mass = np.maximum(0.34 - sw_luma, 0.0)
    sw_feature = gaussian_gray(np.clip(green_excess * 4.2 + dark_mass * 2.0, 0.0, 1.0), 2.4)

    ne_hot = np.clip(ne_rgb[:, :, 0] * 1.22 + ne_rgb[:, :, 1] * 0.62 - ne_rgb[:, :, 2] * 0.42 - 0.42, 0.0, 1.0)
    ne_hot = gaussian_gray(ne_hot, 1.2)

    grad_y, grad_x = np.gradient(height_m)
    slope = normalize01(np.sqrt(grad_x * grad_x + grad_y * grad_y), 42.0, 99.7)
    junction = fields["junction_weight"]
    quad = fields["quad_core_weight"]
    cross_wash = fields["cross_wash_weight"]
    low = (fields["noise_low"] + 1.0) * 0.5
    med = (fields["noise_med"] + 1.0) * 0.5

    soil_exposure = np.clip(junction * (0.13 + med * 0.28) + quad * 0.20 + cross_wash * 0.22, 0.0, 1.0)
    rock_cluster = np.clip(fields["quadrant_se"] * (0.18 + slope * 0.78) + junction * slope * 0.40 + cross_wash * fields["quadrant_se"] * 0.22, 0.0, 1.0)
    shrub_carryover = np.clip(sw_feature * (fields["quadrant_sw"] + junction * 0.46) + quad * 0.10, 0.0, 1.0)
    dry_grass_density = np.clip(fields["quadrant_nw"] * (0.46 + low * 0.26) + junction * (0.14 + med * 0.20), 0.0, 1.0)
    ne_crack_mask = np.clip(fields["quadrant_ne"] * ne_hot * 0.86 + quad * ne_hot * 0.22, 0.0, 1.0)
    wash_line = np.clip(cross_wash * 0.70 + fields["quadrant_se"] * junction * 0.16 + fields["quadrant_ne"] * ne_hot * 0.10, 0.0, 1.0)
    no_scatter = np.clip(slope * 0.82 + rock_cluster * 0.28 + ne_crack_mask * 0.24, 0.0, 1.0)

    # M11's per-quad splat weights, mapped to our shader slots:
    #   grass slot  <- NW quadrant
    #   dirt slot   <- NE quadrant (fantasy in M11)
    #   rock_light  <- SE quadrant (canyon in M11)
    #   rock_dark   <- SW quadrant (source scrub in M11)
    grass_weight = np.clip(fields["quadrant_nw"] * (1.0 - soil_exposure * 0.20 - rock_cluster * 0.10) + dry_grass_density * junction * 0.16, 0.0, 1.0)
    dirt_weight = np.clip(fields["quadrant_ne"] * (0.92 + ne_crack_mask * 0.20) + quad * 0.10 - soil_exposure * 0.04, 0.0, 1.0)
    rl_weight = np.clip(fields["quadrant_se"] * (0.95 + slope * 0.34) + rock_cluster * 0.42 + cross_wash * 0.04, 0.0, 1.0)
    rd_weight = np.clip(fields["quadrant_sw"] * (1.0 - soil_exposure * 0.18 - rock_cluster * 0.12) + shrub_carryover * junction * 0.18, 0.0, 1.0)
    stack = np.stack([grass_weight, dirt_weight, rl_weight, rd_weight], axis=2)
    stack = np.power(np.maximum(stack, 1e-5), 1.10)
    stack /= np.maximum(np.sum(stack, axis=2, keepdims=True), 1e-6)

    return {
        "splat_grass": stack[..., 0].astype(np.float32),
        "splat_dirt": stack[..., 1].astype(np.float32),
        "splat_rock_light": stack[..., 2].astype(np.float32),
        "splat_rock_dark": stack[..., 3].astype(np.float32),
        "shrub_carryover_mask": shrub_carryover.astype(np.float32),
        "dry_grass_density_mask": dry_grass_density.astype(np.float32),
        "soil_exposure_mask": soil_exposure.astype(np.float32),
        "rock_cluster_mask": rock_cluster.astype(np.float32),
        "fantasy_crack_mask": ne_crack_mask.astype(np.float32),
        "wash_line_mask": wash_line.astype(np.float32),
        "no_scatter_mask": no_scatter.astype(np.float32),
    }


def build_fourway_macro_preview(spec: FourwayBundleSpec, layers: dict[str, np.ndarray],
                                  source_rgb: np.ndarray | None,
                                  quad_rgbs: list[np.ndarray]) -> np.ndarray:
    """Direct port of M11's build_macro_preview. Composites per-quadrant
    catalog macros + tinted shading + scatter-mask alpha overlays."""
    nw_rgb, ne_rgb, se_rgb, sw_rgb = quad_rgbs
    w, h = spec.width_px, spec.height_px
    seed = spec.seed
    low = smooth_noise(w, h, 72, seed + 501)
    fine = smooth_noise(w, h, 24, seed + 503)
    ridge_noise = smooth_noise(w, h, 36, seed + 509)

    # Height is the actual rendered height (passed in via layers).
    # We compute slope + lambertian light from a separate pass — pull
    # from layers if available, else derive from a synthesized height.
    # (M11 uses the actual height_out array; we can pass it via the
    # layers dict for cleanliness. Skipping for the simpler v1.)
    light = np.full((h, w), 0.5, dtype=np.float32)

    rock_warm = np.array([0.74, 0.45, 0.24], dtype=np.float32)
    rock_shadow = np.array([0.18, 0.14, 0.11], dtype=np.float32)
    rock_alpha = np.clip(layers["rock_cluster_mask"] * 0.20, 0.0, 0.34)
    shadow_alpha = np.clip(layers["wash_line_mask"] * 0.25, 0.0, 0.32)
    rock_color = np.clip(se_rgb * (0.80 + light[:, :, None] * 0.32 + fine[:, :, None] * 0.035), 0.0, 1.0)
    rock_color = rock_color * (1.0 - rock_alpha[:, :, None]) + rock_warm[None, None, :] * rock_alpha[:, :, None]
    rock_color = rock_color * (1.0 - shadow_alpha[:, :, None]) + rock_shadow[None, None, :] * shadow_alpha[:, :, None]

    grass_color = np.clip(nw_rgb * (0.88 + low[:, :, None] * 0.12 + fine[:, :, None] * 0.04), 0.0, 1.0)
    grass_patch = np.clip((ridge_noise - 0.42) * 0.56 * layers["dry_grass_density_mask"], 0.0, 0.22)
    straw = np.array([0.54, 0.47, 0.29], dtype=np.float32)
    olive = np.array([0.25, 0.33, 0.19], dtype=np.float32)
    patch_color = straw[None, None, :] * (1.0 - ridge_noise[:, :, None]) + olive[None, None, :] * ridge_noise[:, :, None]
    grass_color = grass_color * (1.0 - grass_patch[:, :, None]) + patch_color * grass_patch[:, :, None]

    basalt = np.array([0.14, 0.105, 0.075], dtype=np.float32)
    ember = np.array([0.95, 0.48, 0.16], dtype=np.float32)
    ne_base = np.clip(ne_rgb * 0.78 + basalt[None, None, :] * 0.22, 0.0, 1.0)
    ne_base = ne_base * (0.86 + light[:, :, None] * 0.12 + fine[:, :, None] * 0.030)
    ne_alpha = np.clip(layers["fantasy_crack_mask"][:, :, None] * 0.24, 0.0, 0.24)
    ne_color = ne_base * (1.0 - ne_alpha) + ember[None, None, :] * ne_alpha

    sw_feature_rgb = source_rgb if source_rgb is not None else sw_rgb
    sw_color = np.clip(sw_feature_rgb * (0.95 + fine[:, :, None] * 0.055), 0.0, 1.0)
    preview = (
        grass_color * layers["splat_grass"][:, :, None]
        + ne_color * layers["splat_dirt"][:, :, None]
        + rock_color * layers["splat_rock_light"][:, :, None]
        + sw_color * layers["splat_rock_dark"][:, :, None]
    )

    wash_tint = np.array([0.28, 0.22, 0.16], dtype=np.float32)
    wash_alpha = np.clip(layers["wash_line_mask"][:, :, None] * 0.14, 0.0, 0.14)
    preview = preview * (1.0 - wash_alpha) + wash_tint[None, None, :] * wash_alpha

    shrub_alpha = np.clip(layers["shrub_carryover_mask"] * 0.07, 0.0, 0.24)
    shrub_color = np.array([0.15, 0.21, 0.12], dtype=np.float32)
    preview = preview * (1.0 - shrub_alpha[:, :, None]) + shrub_color[None, None, :] * shrub_alpha[:, :, None]
    return np.clip(preview, 0.0, 1.0)


def build_fourway_bundle(spec: FourwayBundleSpec, catalog: dict[str, dict] | None = None) -> dict[str, Any]:
    """Top-level M11-fourway-equivalent bundle builder. Use this when
    you want to recreate M11 fourway through our pipeline."""
    if catalog is None:
        catalog = load_catalog()
    w, h = spec.width_px, spec.height_px

    fields = build_split_quadrant_fields(w, h, spec.seed)

    # Per-quadrant macro RGBs from each quadrant's catalog material
    nw_rgb = build_procedural_macro(spec.nw_material_id, catalog, w, h, spec.seed + 100)
    ne_rgb = build_procedural_macro(spec.ne_material_id, catalog, w, h, spec.seed + 200)
    se_rgb = build_procedural_macro(spec.se_material_id, catalog, w, h, spec.seed + 250)
    sw_rgb = build_procedural_macro(spec.sw_material_id, catalog, w, h, spec.seed + 300)

    height_m = build_fourway_height(spec, fields)
    layers = build_fourway_layers(spec, height_m, fields, spec.source_rgb,
                                    [nw_rgb, ne_rgb, se_rgb, sw_rgb])
    preview = build_fourway_macro_preview(spec, layers, spec.source_rgb,
                                            [nw_rgb, ne_rgb, se_rgb, sw_rgb])

    # Encode
    actual_min = float(np.min(height_m))
    actual_max = float(np.max(height_m))
    elev_min = actual_min
    elev_range = max(actual_max - actual_min, 0.001)
    height_norm = np.clip((height_m - elev_min) / max(elev_range, 0.001), 0.0, 1.0)

    spec.bundle_dir.mkdir(parents=True, exist_ok=True)
    spec.layers_dir.mkdir(parents=True, exist_ok=True)

    macro_path = spec.layers_dir / "render_albedo.png"
    valid_mask_path = spec.layers_dir / "source_valid_mask.png"
    splat_path = spec.layers_dir / "splat_weights_rgba.png"
    height_path = spec.bundle_dir / "heightmap.png"

    Image.fromarray(np.clip(preview * 255.0, 0, 255).astype(np.uint8), mode="RGB").save(macro_path)
    Image.fromarray(np.full((h, w), 255, dtype=np.uint8), mode="L").save(valid_mask_path)
    Image.fromarray(np.clip(height_norm * 65535.0, 0, 65535).astype(np.uint16), mode="I;16").save(height_path)

    splat_rgba = np.stack([
        layers["splat_grass"], layers["splat_dirt"],
        layers["splat_rock_light"], layers["splat_rock_dark"],
    ], axis=2)
    Image.fromarray(np.clip(splat_rgba * 255.0, 0, 255).astype(np.uint8), mode="RGBA").save(splat_path)

    # Scatter mask sidecars (M11's full set)
    for name in ("shrub_carryover_mask", "dry_grass_density_mask",
                  "soil_exposure_mask", "rock_cluster_mask",
                  "fantasy_crack_mask", "wash_line_mask", "no_scatter_mask"):
        Image.fromarray(np.clip(layers[name] * 255.0, 0, 255).astype(np.uint8), mode="L").save(
            spec.layers_dir / f"{name}.png"
        )

    # Per-bundle material .tres. The slot mapping mirrors M11's fourway:
    # grass=nw_material, dirt=ne_material, rock_light=se_material,
    # rock_dark=sw_material (or source_slot_material), snow=fallback.
    slot_materials = dict(spec.slot_materials) if spec.slot_materials else {}
    slot_materials.setdefault("grass", spec.nw_material_id)
    slot_materials.setdefault("dirt", spec.ne_material_id)
    slot_materials.setdefault("rock_light", spec.se_material_id)
    slot_materials.setdefault("rock_dark", spec.sw_material_id)
    slot_materials.setdefault("snow", "grassland_dirt")  # M11's fallback

    material_tres = spec.bundle_dir / "material.tres"
    _write_fourway_material(spec, material_tres, macro_path, valid_mask_path,
                             splat_path, slot_materials, catalog)

    return {
        "macro": str(macro_path),
        "valid_mask": str(valid_mask_path),
        "splat": str(splat_path),
        "heightmap": str(height_path),
        "material": str(material_tres),
        "elev_min_m": elev_min,
        "elev_range_m": elev_range,
        "elev_max_m": elev_min + elev_range,
        "fields_keys": sorted(fields.keys()),
    }


def _write_fourway_material(spec: FourwayBundleSpec, out_path: Path,
                              macro_path: Path, weight_mask_path: Path,
                              splat_path: Path, slot_materials: dict[str, str],
                              catalog: dict[str, dict]) -> None:
    """Write a fourway .tres with explicit per-slot material assignments
    (mirroring M11's write_fourway_material)."""
    def _res(p: Path) -> str:
        rel = p.resolve().relative_to(ROOT.resolve())
        return "res://" + str(rel).replace("\\", "/")
    def _ext(kind: str, path: str, ident: str) -> str:
        return f'[ext_resource type="{kind}" path="{path}" id="{ident}"]'
    def _material_maps(mid: str) -> dict[str, str]:
        entry = catalog[mid]
        maps = entry.get("pbr_maps", {})
        def m(k, fallback=None):
            raw = maps.get(k) or (maps.get(fallback) if fallback else None)
            if raw is None:
                raise KeyError(f"{mid} missing {k}")
            p = Path(str(raw).replace("\\", "/"))
            if p.is_absolute():
                rel = p.resolve().relative_to(ROOT.resolve())
                return "res://" + rel.as_posix()
            parts = p.parts
            if parts and parts[0] == "world3":
                return "res://" + Path(*parts[1:]).as_posix()
            return "res://" + p.as_posix()
        return {
            "albedo": m("albedo"), "normal": m("normal"),
            "roughness": m("roughness"), "ao": m("ao", "albedo"),
            "detail_albedo": m("detail_albedo", "albedo"),
            "detail_normal": m("detail_normal", "normal"),
            "detail_roughness": m("detail_roughness", "roughness"),
        }

    ext_lines = [
        _ext("Shader", "res://shaders/terrain_splat_unified.gdshader", "shader"),
        _ext("Texture2D", _res(macro_path), "source_macro_albedo"),
        _ext("Texture2D", _res(weight_mask_path), "source_macro_valid_mask"),
        _ext("Texture2D", _res(splat_path), "splat_weights"),
    ]
    res_id_for: dict[tuple[str, str], str] = {}
    for slot in SLOTS:
        mid = slot_materials[slot]
        maps = _material_maps(mid)
        for kind in [*BASE_MAPS, *DETAIL_MAPS]:
            ident = f"{slot}_{SHORT_MAP[kind]}"
            ext_lines.append(_ext("Texture2D", maps[kind], ident))
            res_id_for[(slot, kind)] = ident

    lines = [
        f'[gd_resource type="ShaderMaterial" load_steps={len(ext_lines) + 1} format=3]',
        "",
        *ext_lines,
        "",
        "[resource]",
        'shader = ExtResource("shader")',
        "shader_parameter/use_source_macro_albedo = true",
        'shader_parameter/source_macro_albedo = ExtResource("source_macro_albedo")',
        "shader_parameter/source_macro_strength = 0.72",
        "shader_parameter/use_source_macro_valid_mask = true",
        'shader_parameter/source_macro_valid_mask = ExtResource("source_macro_valid_mask")',
        "shader_parameter/use_source_macro_world_uv = true",
        "shader_parameter/use_splat_weights = true",
        'shader_parameter/splat_weights = ExtResource("splat_weights")',
        "shader_parameter/splat_uv_scale = 1.0",
        "shader_parameter/splat_weight_power = 1.48",
    ]
    for slot in SLOTS:
        for kind in [*BASE_MAPS, *DETAIL_MAPS]:
            uniform = f"{slot}_{SHORT_MAP[kind]}"
            lines.append(f'shader_parameter/{uniform} = ExtResource("{res_id_for[(slot, kind)]}")')
    values: dict[str, float] = {
        "world_uv_scale": 0.012, "hex_strength": 1.0, "blend_sharpness": 8.0,
        "roughness_strength": 1.0, "normal_strength": 0.054, "macro_scale": 180.0,
        "macro_value_strength": 0.0, "macro_hue_strength": 0.0,
        "detail_uv_scale_mult": 11.0, "detail_albedo_strength": 0.030,
        "detail_normal_strength": 0.030, "detail_rough_strength": 0.025,
        "detail_fade_start_m": 6.0, "detail_fade_end_m": 52.0,
        "elev_min_m": 0.0, "elev_range_m": 1.0,
        "slope_threshold": 1.0, "slope_softness": 0.15,
        "h_grass_dirt": 0.2, "h_dirt_rockdark": 0.55, "h_rockdark_snow": 0.85,
        "h_band_softness": 0.08,
    }
    for k, v in values.items():
        lines.append(f"shader_parameter/{k} = {v}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def build_bundle(spec: BundleSpec, catalog: dict[str, dict] | None = None) -> dict[str, Any]:
    if catalog is None:
        catalog = load_catalog()

    # Validate + normalize domain weights so per-pixel weights sum to 1.0
    if not spec.domains:
        raise ValueError("BundleSpec.domains must have at least 1 domain")
    weight_stack = np.stack([d.weight_field for d in spec.domains], axis=2).astype(np.float32)
    total = np.maximum(np.sum(weight_stack, axis=2, keepdims=True), 1e-6)
    weight_stack = weight_stack / total
    for i, d in enumerate(spec.domains):
        d.weight_field = weight_stack[..., i]

    aux = build_domain_aux_fields(spec.domains, spec.width_px, spec.height_px, spec.seed)
    height_m = build_height_general(spec, aux)
    layers = build_layers_general(spec, height_m, aux)
    preview = build_macro_preview_general(spec, layers, catalog)

    spec.bundle_dir.mkdir(parents=True, exist_ok=True)
    spec.layers_dir.mkdir(parents=True, exist_ok=True)

    # Heightmap (16-bit, encoded against the request's nominal envelope
    # — preserves F.3.1 byte-exact neighbor agreement)
    elev_min = float(spec.elev_min_m)
    elev_range = float(spec.elev_range_m)
    if spec.neighbor_west_edge_meters is not None or spec.neighbor_north_edge_meters is not None:
        actual_min = float(np.min(height_m))
        actual_max = float(np.max(height_m))
        elev_min = min(elev_min, actual_min)
        elev_range = max(elev_range, actual_max - elev_min)
    else:
        actual_min = float(np.min(height_m))
        actual_max = float(np.max(height_m))
        elev_min = actual_min
        elev_range = max(actual_max - actual_min, 0.001)
    height_norm = np.clip((height_m - elev_min) / max(elev_range, 0.001), 0.0, 1.0)

    macro_path = spec.layers_dir / "render_albedo.png"
    valid_mask_path = spec.layers_dir / "source_valid_mask.png"
    splat_path = spec.layers_dir / "splat_weights_rgba.png"
    height_path = spec.bundle_dir / "heightmap.png"
    meta_path = spec.bundle_dir / "meta.json"

    Image.fromarray(np.clip(preview * 255.0, 0, 255).astype(np.uint8), mode="RGB").save(macro_path)
    Image.fromarray(np.full((spec.height_px, spec.width_px), 255, dtype=np.uint8), mode="L").save(valid_mask_path)
    Image.fromarray(np.clip(height_norm * 65535.0, 0, 65535).astype(np.uint16), mode="I;16").save(height_path)

    splat_rgba = np.stack([
        layers["splat_grass"],
        layers["splat_dirt"],
        layers["splat_rock_light"],
        layers["splat_rock_dark"],
    ], axis=2)
    Image.fromarray(np.clip(splat_rgba * 255.0, 0, 255).astype(np.uint8), mode="RGBA").save(splat_path)

    # Scatter mask sidecars
    for name in ("soil_exposure_mask", "rock_cluster_mask", "dry_grass_density_mask",
                 "wash_line_mask", "no_scatter_mask"):
        Image.fromarray(np.clip(layers[name] * 255.0, 0, 255).astype(np.uint8), mode="L").save(
            spec.layers_dir / f"{name}.png"
        )

    # Per-bundle material .tres
    material_tres = spec.bundle_dir / "material.tres"
    write_per_bundle_material(spec, macro_path, valid_mask_path, splat_path, material_tres)

    # Edge constraints for F.3.1 contiguity (always emit; cheap)
    write_edge_constraints(spec, height_m)

    return {
        "macro": str(macro_path),
        "valid_mask": str(valid_mask_path),
        "splat": str(splat_path),
        "heightmap": str(height_path),
        "meta": str(meta_path),
        "material": str(material_tres),
        "elev_min_m": elev_min,
        "elev_range_m": elev_range,
        "elev_max_m": elev_min + elev_range,
    }
