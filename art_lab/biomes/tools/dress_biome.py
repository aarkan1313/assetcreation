"""Biome dressing compiler.

Given:
  - A biome kit JSON (defines materials, decals, scatter rules, shader hints)
  - A terrain bundle (height/normal/slope/biome/water/vegetation_density masks)
  - Optional landmark/road overlays from the world map

Emit:
  - Per-asset placement instances (x, y, z, scale, rotation, scene path)
  - Per-decal placement instances
  - Material assignment plan
  - Shader rules manifest
  - A Godot-ready dressing.tres + preview render

Output structure:
  biomes/output/<biome_id>_<terrain_id>/
    dressing.json                    -- canonical placement plan
    placements/
      scatter.csv                    -- per-instance: asset, x, y, z, sx,sy,sz, rx,ry,rz
      decals.csv                     -- per-decal: id, x, y, sx, sy
    masks/
      mask_<rule>.png                -- visualizations of computed masks
    preview_dressed.png              -- top-down render of the placement
    godot/
      scatter.tres                   -- MultiMesh data for fast Godot import
      placement_recipe.json          -- LLM-readable summary

Usage:
  python dress_biome.py --kit mossy_highland_ruins --terrain mythos_terrain_a \
      --map mythos_a --id mossy_highland_x_mythos
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

KITS_DIR = Path(r"D:\assets\art_lab\biomes\kits")
OUT_ROOT = Path(r"D:\assets\art_lab\biomes\output")
TERRAIN_OUT = Path(r"D:\assets\pipelines\terrain\output")
MAPS_ROOT = Path(r"D:\assets\world\maps")


def load_height(terrain_dir: Path) -> np.ndarray:
    h_im = Image.open(terrain_dir / "height_16.png")
    return np.asarray(h_im, dtype=np.float32) / 65535.0


def load_mask(path: Path) -> np.ndarray | None:
    if not path.exists():
        return None
    im = Image.open(path).convert("L")
    return np.asarray(im, dtype=np.float32) / 255.0


def slope_from_height(h: np.ndarray) -> np.ndarray:
    pad = np.pad(h, 1, mode="edge")
    gx = pad[1:-1, 2:] - pad[1:-1, :-2]
    gy = pad[2:, 1:-1] - pad[:-2, 1:-1]
    s = np.sqrt(gx * gx + gy * gy)
    return s / max(s.max(), 1e-9)


def shade_estimate(height: np.ndarray) -> np.ndarray:
    """Crude shade map: cells next to high terrain are shadier (NW-light)."""
    pad = np.pad(height, 8, mode="edge")
    nw = pad[:-16, :-16]  # neighbors to upper-left
    diff = np.clip((nw - height) * 4, 0, 1)
    return diff


def wetness_estimate(water_mask: np.ndarray | None, height: np.ndarray) -> np.ndarray:
    """Wetness ~ 1 / distance-to-water + low-elevation bonus."""
    h, w = height.shape
    if water_mask is None or not (water_mask > 0.5).any():
        return np.clip(1.0 - height, 0, 1) * 0.4
    try:
        from scipy.ndimage import distance_transform_edt
        dist = distance_transform_edt((water_mask > 0.5).astype(np.uint8) == 0)
        max_d = max(dist.max(), 1)
        wet = np.clip(1.0 - dist / (max_d * 0.15), 0, 1)
        # low-elevation bonus
        wet += np.clip(0.4 - height, 0, 0.4) * 1.2
        return np.clip(wet, 0, 1)
    except ImportError:
        return np.clip(1.0 - height, 0, 1) * 0.4


def landmark_proximity_mask(h: int, w: int, landmarks: list[dict], radius_px: int = 60) -> np.ndarray:
    mask = np.zeros((h, w), dtype=np.float32)
    if not landmarks:
        return mask
    ys, xs = np.indices((h, w))
    for l in landmarks:
        d = np.sqrt((ys - l["y"]) ** 2 + (xs - l["x"]) ** 2)
        bump = np.clip(1.0 - d / radius_px, 0, 1)
        mask = np.maximum(mask, bump)
    return mask


def road_proximity_mask(h: int, w: int, roads: list, radius_px: int = 8) -> np.ndarray:
    """Returns mask where pixels close to any road are 1.0."""
    mask = np.zeros((h, w), dtype=np.float32)
    if not roads:
        return mask
    img = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
    draw = ImageDraw.Draw(img)
    for path in roads:
        if len(path) < 2:
            continue
        # path is list of (y,x); GeoJSON has [x,y]
        coords = path if isinstance(path[0], dict) else path
        if isinstance(coords[0], list):
            pts = [(c[0], c[1]) for c in coords]
        else:
            pts = [(x, y) for (y, x) in coords]
        draw.line(pts, fill=255, width=radius_px * 2)
    return np.asarray(img, dtype=np.float32) / 255.0


def sample_blue_noise(mask: np.ndarray, density_per_m2: float, m_per_pixel: float = 1.0,
                      min_separation_px: float = 1.5,
                      rng: random.Random = None) -> list[tuple[int, int]]:
    """Poisson-disk-ish sampling weighted by mask intensity."""
    rng = rng or random.Random(0)
    h, w = mask.shape
    n_samples = int(density_per_m2 * h * w * (m_per_pixel ** 2))
    n_samples = min(n_samples, 200_000)

    accepted = []
    grid_cell = max(1, int(min_separation_px))
    grid_w = w // grid_cell + 1
    grid_h = h // grid_cell + 1
    grid = [[None] * grid_w for _ in range(grid_h)]

    attempts = n_samples * 4
    for _ in range(attempts):
        if len(accepted) >= n_samples:
            break
        x = rng.randint(0, w - 1)
        y = rng.randint(0, h - 1)
        if mask[y, x] < rng.random():
            continue
        # check grid cell + neighbors for too-close
        gx = x // grid_cell; gy = y // grid_cell
        too_close = False
        for ddy in (-1, 0, 1):
            for ddx in (-1, 0, 1):
                ngy = gy + ddy; ngx = gx + ddx
                if 0 <= ngy < grid_h and 0 <= ngx < grid_w:
                    other = grid[ngy][ngx]
                    if other is not None:
                        dx, dy = x - other[0], y - other[1]
                        if dx * dx + dy * dy < min_separation_px ** 2:
                            too_close = True
                            break
            if too_close:
                break
        if not too_close:
            accepted.append((x, y))
            grid[gy][gx] = (x, y)
    return accepted


def evaluate_rule_mask(rule: dict, ctx: dict) -> np.ndarray:
    """Compose a mask from rule constraints (slope_max, wetness_min, etc)."""
    mask = np.ones_like(ctx["height"])
    if "slope_max" in rule:
        mask *= np.clip(1.0 - (ctx["slope"] / max(rule["slope_max"], 1e-3)), 0, 1)
    if "slope_min" in rule:
        mask *= np.clip((ctx["slope"] - rule["slope_min"]) * 5, 0, 1)
    if "wetness_min" in rule:
        mask *= np.clip((ctx["wetness"] - rule["wetness_min"]) * 5, 0, 1)
    if "shade_min" in rule:
        mask *= np.clip((ctx["shade"] - rule["shade_min"]) * 5, 0, 1)
    if "near_landmark" in rule and "landmark_mask" in ctx:
        mask *= ctx["landmark_mask"]
    if "avoid_roads_m" in rule and "road_mask" in ctx:
        mask *= (1.0 - ctx["road_mask"])
    # always avoid water + steep snow
    mask *= (ctx["height"] > 0.32).astype(np.float32)
    mask *= (ctx["height"] < 0.78).astype(np.float32)
    return mask


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", required=True, help="biome kit name in art_lab/biomes/kits/")
    ap.add_argument("--terrain", required=True, help="terrain id under pipelines/terrain/output/")
    ap.add_argument("--map", default=None, help="(optional) map id under world/maps/ for landmarks/roads")
    ap.add_argument("--id", required=True, help="output id")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--m-per-pixel", type=float, default=1.0)
    args = ap.parse_args()

    kit_path = KITS_DIR / f"{args.kit}.json"
    if not kit_path.exists():
        raise SystemExit(f"kit not found: {kit_path}")
    kit = json.loads(kit_path.read_text(encoding="utf-8"))

    terrain_dir = TERRAIN_OUT / args.terrain
    if not terrain_dir.exists():
        raise SystemExit(f"terrain not found: {terrain_dir}")

    out_dir = OUT_ROOT / args.id
    placements_dir = out_dir / "placements"
    masks_dir = out_dir / "masks"
    godot_dir = out_dir / "godot"
    for d in [placements_dir, masks_dir, godot_dir]:
        d.mkdir(parents=True, exist_ok=True)

    print(f"[1/5] loading terrain {args.terrain}")
    height = load_height(terrain_dir)
    h, w = height.shape
    slope = slope_from_height(height)
    water = load_mask(terrain_dir / "water_mask.png")
    veg = load_mask(terrain_dir / "vegetation_density.png")
    wetness = wetness_estimate(water, height)
    shade = shade_estimate(height)

    landmarks = []
    roads = []
    if args.map:
        map_dir = MAPS_ROOT / args.map
        if (map_dir / "layers" / "landmarks.json").exists():
            landmarks = json.loads((map_dir / "layers" / "landmarks.json").read_text(encoding="utf-8"))
        if (map_dir / "layers" / "roads.geojson").exists():
            geo = json.loads((map_dir / "layers" / "roads.geojson").read_text(encoding="utf-8"))
            roads = [[(int(c[1]), int(c[0])) for c in f["geometry"]["coordinates"]]
                     for f in geo.get("features", [])]

    print(f"[2/5] context masks (wetness, shade, landmark, road)")
    landmark_mask = landmark_proximity_mask(h, w, landmarks)
    road_mask = road_proximity_mask(h, w, roads)

    Image.fromarray((wetness * 255).astype(np.uint8), mode="L").save(masks_dir / "wetness.png")
    Image.fromarray((shade * 255).astype(np.uint8), mode="L").save(masks_dir / "shade.png")
    Image.fromarray((landmark_mask * 255).astype(np.uint8), mode="L").save(masks_dir / "landmarks.png")
    Image.fromarray((road_mask * 255).astype(np.uint8), mode="L").save(masks_dir / "roads.png")

    ctx = {
        "height": height, "slope": slope, "wetness": wetness, "shade": shade,
        "landmark_mask": landmark_mask, "road_mask": road_mask,
    }
    rng = random.Random(args.seed)

    # Scatter placements
    print(f"[3/5] scatter placements ({len(kit['scatter'])} rules)")
    scatter_rows = []
    scatter_summary = {}
    for rule in kit["scatter"]:
        rule_mask = evaluate_rule_mask(rule, ctx)
        Image.fromarray((rule_mask * 255).astype(np.uint8), mode="L").save(masks_dir / f"scatter_{rule['asset']}.png")
        density = rule.get("density_per_m2", 0.1)
        # scatter density is expensive; cap by mask area ratio
        instances = sample_blue_noise(rule_mask, density, args.m_per_pixel,
                                      min_separation_px=2.0, rng=rng)
        scatter_summary[rule["asset"]] = len(instances)
        for (x, y) in instances:
            sx = rng.uniform(rule.get("scale_min", 1.0), rule.get("scale_max", 1.0))
            ry = rng.uniform(0, 2 * math.pi) if rule.get("rotation_random") else 0
            z = float(height[y, x])
            scatter_rows.append({
                "asset": rule["asset"], "x": x, "y": y, "z": z,
                "sx": sx, "sy": sx, "sz": sx,
                "rx": 0, "ry": ry, "rz": 0,
            })
        print(f"  {rule['asset']}: {len(instances)} instances")

    # Decal placements
    print(f"[4/5] decal placements ({len(kit['decals'])} rules)")
    decal_rows = []
    decal_summary = {}
    for rule in kit["decals"]:
        rule_mask = evaluate_rule_mask(rule, ctx)
        max_d = rule.get("max_per_m2", 0.1)
        instances = sample_blue_noise(rule_mask, max_d, args.m_per_pixel,
                                      min_separation_px=4.0, rng=rng)
        decal_summary[rule["id"]] = len(instances)
        for (x, y) in instances:
            decal_rows.append({
                "id": rule["id"], "x": x, "y": y,
                "sx": rule.get("size_m", 1.0),
                "sy": rule.get("size_m", 1.0),
            })
        print(f"  {rule['id']}: {len(instances)} instances")

    # Write CSVs
    if scatter_rows:
        with (placements_dir / "scatter.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(scatter_rows[0].keys()))
            writer.writeheader()
            writer.writerows(scatter_rows)
    if decal_rows:
        with (placements_dir / "decals.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(decal_rows[0].keys()))
            writer.writeheader()
            writer.writerows(decal_rows)

    # Top-down preview
    print(f"[5/5] preview")
    biome_path = terrain_dir / "biome.png"
    if biome_path.exists():
        base = Image.open(biome_path).convert("RGBA").resize((w, h))
    else:
        base = Image.fromarray((height * 255).astype(np.uint8), mode="L").convert("RGBA")
    draw = ImageDraw.Draw(base, "RGBA")
    asset_colors = {}
    rng2 = random.Random(args.seed + 1)
    for r in scatter_rows[::max(1, len(scatter_rows) // 5000)]:  # cap dots drawn
        if r["asset"] not in asset_colors:
            asset_colors[r["asset"]] = tuple(rng2.randint(60, 240) for _ in range(3)) + (200,)
        c = asset_colors[r["asset"]]
        draw.ellipse([r["x"] - 1, r["y"] - 1, r["x"] + 1, r["y"] + 1], fill=c)
    base.convert("RGB").save(out_dir / "preview_dressed.png")

    # Manifest
    manifest = {
        "id": args.id,
        "created": datetime.now(timezone.utc).isoformat(),
        "kit": args.kit,
        "terrain": args.terrain,
        "map": args.map,
        "size": [w, h],
        "m_per_pixel": args.m_per_pixel,
        "totals": {
            "scatter": len(scatter_rows),
            "decals": len(decal_rows),
        },
        "scatter_summary": scatter_summary,
        "decal_summary": decal_summary,
        "shader_rules": kit.get("shader_rules", {}),
    }
    (out_dir / "dressing.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # LLM-readable recipe
    recipe = {
        "what_to_place": {
            "scatter": [{"asset": k, "instances": v} for k, v in scatter_summary.items()],
            "decals": [{"id": k, "instances": v} for k, v in decal_summary.items()],
        },
        "shader_rules_to_apply": kit.get("shader_rules", {}),
        "next_steps": [
            "Each scatter row in placements/scatter.csv is one MultiMesh instance.",
            "In Godot 4.5: import scatter.csv into a MultiMeshInstance3D per asset.",
            "Apply shader_rules from the manifest to the source materials/scenes.",
            "decals.csv -> Godot Decal nodes with the listed size_m extents.",
        ],
    }
    (godot_dir / "placement_recipe.json").write_text(json.dumps(recipe, indent=2), encoding="utf-8")

    # Minimal scatter.tres stub (a real one would embed MultiMesh transforms;
    # this is a placeholder readable by Godot)
    tres = """[gd_resource type="Resource" load_steps=2 format=3]

[resource]
note = "MultiMesh data — generate from scatter.csv in a Godot importer plugin."
"""
    (godot_dir / "scatter.tres").write_text(tres, encoding="utf-8")

    print(f"\ndone: {out_dir}")
    print(f"  total scatter instances: {len(scatter_rows)}")
    print(f"  total decal instances: {len(decal_rows)}")


if __name__ == "__main__":
    main()
