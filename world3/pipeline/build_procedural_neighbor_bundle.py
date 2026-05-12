#!/usr/bin/env python3
"""Build a small procedural terrain bundle for M10 seam-integration proofs.

The output intentionally matches the real-source bundle shape expected by
build_terrain_seam_integration_proof.py: macro albedo, valid mask, heightmap,
and meta. This keeps real-to-procedural tests on the same runtime path as
real-to-real tests.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]


def parse_size(value: str) -> tuple[int, int]:
    parts = [int(part.strip()) for part in value.split(",")]
    if len(parts) != 2:
        raise ValueError("size must be width,height")
    w, h = parts
    if w <= 0 or h <= 0:
        raise ValueError("size values must be positive")
    return w, h


def parse_world_size(value: str) -> tuple[float, float]:
    parts = [float(part.strip()) for part in value.split(",")]
    if len(parts) != 2:
        raise ValueError("world size must be width_m,height_m")
    w, h = parts
    if w <= 0.0 or h <= 0.0:
        raise ValueError("world size values must be positive")
    return w, h


def resolve_repo_path(path: str) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return ROOT.parent / p


def res_path(path: Path) -> str:
    """Convert an absolute path into a Godot res:// path if it lives
    inside the world3 ROOT, else return the absolute path as a string.

    Previously this raised ValueError when --out was outside ROOT,
    making cold-run + validation runs from /tmp/ crash before any
    output was written (Phase B.3 finding, 2026-05-11)."""
    try:
        rel = path.resolve().relative_to(ROOT.resolve())
        return "res://" + rel.as_posix()
    except ValueError:
        return str(path.resolve())


def load_material(material_id: str, catalog_path: Path) -> dict[str, Any]:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    for mat in catalog.get("materials", []):
        if mat.get("id") == material_id:
            return mat
    raise KeyError(f"material id not found in catalog: {material_id}")


def smooth_noise(width: int, height: int, grid: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    small_w = max(2, int(np.ceil(width / grid)))
    small_h = max(2, int(np.ceil(height / grid)))
    small = rng.normal(0.0, 1.0, (small_h, small_w)).astype(np.float32)
    small = (small - small.min()) / max(float(small.max() - small.min()), 1e-6)
    img = Image.fromarray(np.clip(small * 255.0, 0, 255).astype(np.uint8), mode="L")
    img = img.resize((width, height), Image.Resampling.BICUBIC)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return arr * 2.0 - 1.0


def normalize01(arr: np.ndarray) -> np.ndarray:
    low = float(np.percentile(arr, 1))
    high = float(np.percentile(arr, 99))
    return np.clip((arr - low) / max(high - low, 1e-6), 0.0, 1.0)


def tiled_detail(albedo_path: Path, width: int, height: int, repeat_px: int, seed: int) -> np.ndarray:
    src = Image.open(albedo_path).convert("RGB")
    tile = src.resize((repeat_px, repeat_px), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (width + repeat_px * 2, height + repeat_px * 2))
    rng = np.random.default_rng(seed)
    ox = int(rng.integers(0, repeat_px))
    oy = int(rng.integers(0, repeat_px))
    for y in range(-repeat_px, height + repeat_px, repeat_px):
        for x in range(-repeat_px, width + repeat_px, repeat_px):
            canvas.paste(tile, (x + ox + repeat_px, y + oy + repeat_px))
    crop = canvas.crop((repeat_px, repeat_px, repeat_px + width, repeat_px + height))
    return np.asarray(crop, dtype=np.float32) / 255.0


def build_macro(material: dict[str, Any], width: int, height: int, seed: int) -> np.ndarray:
    """Build the procedural-neighbor macro albedo by tiling the catalog
    material's albedo at full strength, then adding gentle procedural
    variation on top (value modulation, wash bands, vertical tint).

    History: the original implementation (pre-2026-05-11) collapsed the
    catalog albedo to its median RGB color, then re-introduced texture
    at only 42% strength under smooth value noise. That produced the
    "broad smooth tan/sand" visual veto that drove M18 to conditional
    status (Phase B.3 root-cause finding).

    The fix: use the catalog albedo AS the texture, with the procedural
    bits supplying only large-scale variation. Same procedural intent
    (wash bands, value modulation, vertical gradient) but the catalog's
    actual texture is preserved at full strength so the result reads as
    "real material with procedural placement," not "tinted noise."
    """
    albedo_path = resolve_repo_path(material["pbr_maps"]["albedo"])

    # Tile the catalog albedo larger than the output dimensions so the
    # tile-grid artifact isn't visible. Using `max_dim` of the output
    # means the catalog only repeats ~1-2 times across the macro and
    # the eye can't pick up the grid. Catalog texture detail dominates;
    # procedural variation modulates on top.
    max_dim = max(width, height)
    tile_repeat_px = max_dim
    base_texture = tiled_detail(albedo_path, width, height, tile_repeat_px, seed + 31)

    # Procedural variation fields (large-scale only — fine detail comes
    # from the catalog texture itself).
    low = smooth_noise(width, height, 220, seed + 11)
    med = smooth_noise(width, height, 72, seed + 17)
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    x = xx / max(width - 1, 1)
    y = yy / max(height - 1, 1)

    # Subtle organic wash patches (not directional bands). Driven by
    # low-frequency noise so they read as natural color variation, not
    # a parametric stripe.
    wash_field = low * 0.6 + med * 0.4  # noise-driven, not sin-driven
    wash_signal = np.clip(wash_field - 0.45, 0.0, 1.0) * 1.4

    # Multiplicative value modulation: ±6% lightness, low-frequency.
    value = 0.97 + low * 0.05 + med * 0.02
    color = base_texture * value[:, :, None]

    # Additive wash patches + gentle vertical tint shift.
    color += wash_signal[:, :, None] * np.array([0.025, 0.015, 0.004], dtype=np.float32)
    color += (1.0 - y[:, :, None]) * np.array([0.012, 0.006, -0.002], dtype=np.float32)

    return np.clip(color, 0.0, 1.0)


def build_height(width: int, height: int, elev_min: float, elev_range: float, seed: int) -> np.ndarray:
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    x = xx / max(width - 1, 1)
    y = yy / max(height - 1, 1)
    low = smooth_noise(width, height, 210, seed + 101)
    med = smooth_noise(width, height, 72, seed + 107)
    small = smooth_noise(width, height, 28, seed + 113)
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


def load_edge_constraint(path: Path | None, expected_len: int) -> np.ndarray | None:
    """Load a neighbor edge constraint JSON. Returns a float32 array of
    `expected_len` elevation values in meters, or None if path is missing."""
    if path is None or not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = payload.get("values_m", [])
    if len(values) != expected_len:
        # Resample to expected_len via numpy linear interp
        src = np.asarray(values, dtype=np.float32)
        if src.size == 0:
            return None
        idx = np.linspace(0.0, float(src.size - 1), expected_len, dtype=np.float32)
        return np.interp(idx, np.arange(src.size, dtype=np.float32), src)
    return np.asarray(values, dtype=np.float32)


def apply_edge_constraint(field_m: np.ndarray, edge_values: np.ndarray,
                          edge_kind: str, feather_px: int) -> np.ndarray:
    """Override the matching edge of field_m with edge_values, blending
    inward over feather_px rows/columns.

    edge_kind:
      'west'  -> overrides field_m[:, 0],  feather towards +x
      'north' -> overrides field_m[0, :],  feather towards +z (down rows)

    Convention: west/east edges are columns, north/south edges are rows.
    With image array [row=z, col=x], north is row 0, south is row -1,
    west is col 0, east is col -1.
    """
    out = field_m.copy()
    h, w = out.shape
    if edge_kind == "west":
        # edge_values length must be h
        if edge_values.shape[0] != h:
            edge_values = np.interp(
                np.linspace(0, edge_values.shape[0] - 1, h, dtype=np.float32),
                np.arange(edge_values.shape[0], dtype=np.float32),
                edge_values
            )
        feather = max(1, min(feather_px, w))
        weights = np.linspace(1.0, 0.0, feather, dtype=np.float32)
        for c in range(feather):
            t = weights[c]
            out[:, c] = edge_values * t + out[:, c] * (1.0 - t)
        # Force exact match at col 0
        out[:, 0] = edge_values
    elif edge_kind == "north":
        if edge_values.shape[0] != w:
            edge_values = np.interp(
                np.linspace(0, edge_values.shape[0] - 1, w, dtype=np.float32),
                np.arange(edge_values.shape[0], dtype=np.float32),
                edge_values
            )
        feather = max(1, min(feather_px, h))
        weights = np.linspace(1.0, 0.0, feather, dtype=np.float32)
        for r in range(feather):
            t = weights[r]
            out[r, :] = edge_values * t + out[r, :] * (1.0 - t)
        out[0, :] = edge_values
    return out


def extract_edge_constraint(field_m: np.ndarray, edge_kind: str) -> list[float]:
    """Pull a bundle's edge as a list of meter values. Used by the F.3.1
    iterator to thread one bundle's east edge into the next bundle's
    west constraint (and south into north).

    Convention: south edge is the last row, east edge is the last column.
    Coordinate-wise: south is high-z, east is high-x.
    """
    h, w = field_m.shape
    if edge_kind == "east":
        return [float(v) for v in field_m[:, w - 1]]
    if edge_kind == "south":
        return [float(v) for v in field_m[h - 1, :]]
    if edge_kind == "west":
        return [float(v) for v in field_m[:, 0]]
    if edge_kind == "north":
        return [float(v) for v in field_m[0, :]]
    raise ValueError(f"unknown edge_kind: {edge_kind}")


def _build_splat_weights(width: int, height: int, height_m: np.ndarray,
                          args: argparse.Namespace) -> np.ndarray:
    """Build an RGBA splat-weights array, 0..1 floats.

    F.3.3 contract — mirrors M11 fourway's height/slope-driven splat:
      R: grass (low-relief, mid-elevation, low-slope)
      G: dirt  (low-elevation, transitional)
      B: rock_light (mid-slope, mid-elevation)
      A: rock_dark (high-slope OR high-elevation)
    Snow is the implicit "1 - sum" slot in the shader; we don't write
    it explicitly.

    Weights normalized so each pixel's RGBA sums to ~1.0.
    """
    # Derive slope from heightmap gradient
    gy, gx = np.gradient(height_m.astype(np.float32))
    slope_raw = np.sqrt(gx * gx + gy * gy)
    if slope_raw.max() > 0:
        slope = slope_raw / max(np.percentile(slope_raw, 99.5), 1e-6)
    else:
        slope = np.zeros_like(slope_raw)
    slope = np.clip(slope, 0.0, 1.0)

    # Normalize elevation to [0, 1] within this bundle
    h_range = max(float(height_m.max() - height_m.min()), 1e-6)
    h_norm = (height_m - height_m.min()) / h_range

    # Add some organic noise variation so the splat isn't dominated by
    # the heightmap's primary slope direction (which produced horizontal
    # banding before).
    seed = int(getattr(args, "seed", 1021))
    n_low = smooth_noise(width, height, 96, seed + 701)
    n_med = smooth_noise(width, height, 36, seed + 707)
    organic = (n_low * 0.6 + n_med * 0.4).astype(np.float32)  # 0..1

    # Per-slot weight rules (matched to M11's intent: grass low-flat,
    # rock high-slope or high-elev, dirt as transitional filler).
    # Each rule mixes height + slope + organic noise so the splat has
    # natural 2D variation rather than tracking the heightmap's banding.
    w_grass = np.clip(0.85 - slope * 0.7 - np.abs(h_norm - 0.40) * 0.6
                      + (organic - 0.5) * 0.30, 0.0, 1.0)
    w_dirt = np.clip(0.55 - slope * 0.5 - np.abs(h_norm - 0.20) * 0.8
                     + (organic - 0.5) * 0.25, 0.0, 1.0)
    w_rl = np.clip(0.45 + slope * 0.4 - np.abs(h_norm - 0.60) * 0.4
                   + (organic - 0.5) * 0.20, 0.0, 1.0)
    w_rd = np.clip(0.30 + slope * 0.9 + np.maximum(h_norm - 0.70, 0.0) * 0.9
                   + (organic - 0.5) * 0.20, 0.0, 1.0)

    stack = np.stack([w_grass, w_dirt, w_rl, w_rd], axis=2).astype(np.float32)
    # Normalize so per-pixel weights sum to 1.0 (let snow fall out of the
    # remainder if we ever want it; M11 shader handles >sum-of-channels)
    total = np.maximum(stack.sum(axis=2, keepdims=True), 1e-6)
    stack = stack / total

    # F.3.3 boundary crossfade: if east/south neighbor has different
    # biome, fade the dominant primary toward 0.5 at that edge so the
    # neighbor's bundle can crossfade in from its side too. Implementation
    # ramps the rock_dark (A) channel up in the crossfade band as a
    # "neighbor present" hint — the neighbor bundle does the same and
    # the rendered result blends because both bundles bind their own
    # catalog materials behind those channels.
    feather = max(1, int(getattr(args, "neighbor_splat_feather_px", 64)))
    east_biome = getattr(args, "neighbor_east_biome", "") or ""
    if east_biome and east_biome != getattr(args, "this_biome", ""):
        feather_w = min(feather, width)
        ramp = np.linspace(0.0, 0.5, feather_w, dtype=np.float32)
        for i, c in enumerate(range(width - feather_w, width)):
            t = ramp[i]
            stack[:, c, 3] = np.clip(stack[:, c, 3] + t, 0.0, 1.0)
    south_biome = getattr(args, "neighbor_south_biome", "") or ""
    if south_biome and south_biome != getattr(args, "this_biome", ""):
        feather_h = min(feather, height)
        ramp = np.linspace(0.0, 0.5, feather_h, dtype=np.float32)
        for i, r in enumerate(range(height - feather_h, height)):
            t = ramp[i]
            stack[r, :, 3] = np.clip(stack[r, :, 3] + t, 0.0, 1.0)

    # Re-normalize after the crossfade nudge
    total = np.maximum(stack.sum(axis=2, keepdims=True), 1e-6)
    stack = stack / total
    return stack


def write_bundle(args: argparse.Namespace) -> dict[str, Any]:
    """F.3.4 — thin wrapper that calls m11_bundle_lib.build_bundle with
    a BundleSpec assembled from CLI args. The library handles macro,
    height, splat, scatter masks, per-bundle .tres, and edge emit.

    For a single-biome bundle, we set up one domain with weight=1
    everywhere. Multi-biome boundary bundles (when we extend the
    iterator) will instantiate multiple domains with crossfade weights.
    """
    import m11_bundle_lib as lib
    width, height = parse_size(args.size)
    world_x, world_z = parse_world_size(args.world_size_m)

    out: Path = args.out
    layers_dir = out / "layers"
    edges_dir = out / "edges"

    # Single-domain spec: this bundle's biome material is the only domain.
    # When the iterator threads multi-biome boundary crossfades, it can
    # extend this with additional Domain entries.
    weight_field = np.ones((height, width), dtype=np.float32)
    domains = [
        lib.Domain(
            name=getattr(args, "this_biome", "") or args.material_id,
            material_id=args.material_id,
            weight_field=weight_field,
            elev_offset_m=0.0,
            elev_range_m=float(args.elev_range_m),
        )
    ]

    # Load neighbor edge constraints if present
    west_edge_arr = None
    north_edge_arr = None
    if args.neighbor_west_edge is not None and args.neighbor_west_edge.exists():
        west_edge_arr = np.asarray(
            json.loads(args.neighbor_west_edge.read_text(encoding="utf-8"))["values_m"],
            dtype=np.float32,
        )
    if args.neighbor_north_edge is not None and args.neighbor_north_edge.exists():
        north_edge_arr = np.asarray(
            json.loads(args.neighbor_north_edge.read_text(encoding="utf-8"))["values_m"],
            dtype=np.float32,
        )

    spec = lib.BundleSpec(
        bundle_id=out.name,
        biome_kit=getattr(args, "biome_kit", "") or "",
        width_px=width,
        height_px=height,
        world_size_m=(world_x, world_z),
        elev_min_m=float(args.elev_min_m),
        elev_range_m=float(args.elev_range_m),
        seed=int(args.seed),
        domains=domains,
        bundle_dir=out,
        layers_dir=layers_dir,
        edges_dir=edges_dir,
        neighbor_west_edge_meters=west_edge_arr,
        neighbor_north_edge_meters=north_edge_arr,
        neighbor_edge_feather_px=int(getattr(args, "neighbor_edge_feather_px", 32)),
    )
    result = lib.build_bundle(spec)

    macro_path = Path(result["macro"])
    valid_mask_path = Path(result["valid_mask"])
    splat_path = Path(result["splat"])
    height_path = Path(result["heightmap"])
    bundle_material_path = Path(result["material"])
    meta_path = out / "meta.json"
    material = load_material(args.material_id, args.catalog)

    meta = {
        "name": args.name or f"Procedural {args.material_id} M10 neighbor",
        "builder": "build_procedural_neighbor_bundle.py (F.3.4 lib-driven)",
        "source": "procedural",
        "source_material_id": args.material_id,
        "source_material_albedo": material["pbr_maps"]["albedo"],
        "heightmap_size_px": [width, height],
        "world_size_x_m": world_x,
        "world_size_z_m": world_z,
        "world_size_m": max(world_x, world_z),
        "elevation_min_m": result["elev_min_m"],
        "elevation_max_m": result["elev_max_m"],
        "elevation_range_m": result["elev_range_m"],
        "material": args.material_id,
        "texture_is_real_imagery": False,
        "procedural_neighbor": {
            "version": 2,
            "seed": args.seed,
            "macro_policy": "m11_bundle_lib_general_domain_composition",
            "height_policy": "domain_weighted_heightfield_with_junction_softening",
            "target": "F.3.4 plan-driven M11-shape bundle",
        },
        "layers": {
            "render_albedo": res_path(macro_path),
            "source_valid_mask": res_path(valid_mask_path),
            "splat_weights_rgba": res_path(splat_path),
        },
        "bundle_material_path": res_path(bundle_material_path),
        "biome_kit": getattr(args, "biome_kit", "") or None,
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return {
        "macro": str(macro_path),
        "valid_mask": str(valid_mask_path),
        "heightmap": str(height_path),
        "meta": str(meta_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--material-id", default="desert_canyon_rock")
    parser.add_argument("--catalog", type=Path, default=ROOT / "materials/catalog.json")
    parser.add_argument("--out", type=Path, default=ROOT / "toporeview/procedural_desert_canyon_rock_m10")
    parser.add_argument("--size", default="512,1024")
    parser.add_argument("--world-size-m", default="120,240")
    parser.add_argument("--elev-min-m", type=float, default=412.0)
    parser.add_argument("--elev-range-m", type=float, default=18.0)
    parser.add_argument("--seed", type=int, default=1021)
    parser.add_argument("--name", default="")
    parser.add_argument("--neighbor-west-edge", type=Path, default=None,
                        help="F.3.1: optional JSON file with the west "
                             "neighbor's east_edge values_m. If present, "
                             "this bundle's west column matches it.")
    parser.add_argument("--neighbor-north-edge", type=Path, default=None,
                        help="F.3.1: optional JSON file with the north "
                             "neighbor's south_edge values_m.")
    parser.add_argument("--neighbor-edge-feather-px", type=int, default=32,
                        help="F.3.1: how many pixels to feather the neighbor "
                             "edge inward to avoid a hard seam.")
    parser.add_argument("--this-biome", default="",
                        help="F.3.2: this bundle's biome id, used to decide "
                             "whether the east/south neighbor differs.")
    parser.add_argument("--neighbor-east-biome", default="",
                        help="F.3.2: biome id of the east neighbor (if any).")
    parser.add_argument("--neighbor-south-biome", default="",
                        help="F.3.2: biome id of the south neighbor (if any).")
    parser.add_argument("--neighbor-splat-feather-px", type=int, default=64,
                        help="F.3.2: pixels of inward feather for splat-weight "
                             "boundary crossfade.")
    parser.add_argument("--biome-kit", default="",
                        help="F.3.3: biome kit (alpine/desert/tundra/grassland/"
                             "temperate_forest). Used to pick the 5 catalog "
                             "materials bound into this bundle's .tres.")
    args = parser.parse_args()

    result = write_bundle(args)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
