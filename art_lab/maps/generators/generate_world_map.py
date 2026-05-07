"""World Map generator — emits the layered map contract from G_deep_dive.

Output structure (per G):
  world/maps/<map_id>/
    map.json                  -- seed, projection, dimensions, style, layer paths
    layers/
      height.png              -- 16-bit grayscale base elevation
      biome.png                  RGB hypsometric biome image
      water.geojson           -- ocean/lake polygons
      rivers.geojson          -- river LineStrings
      roads.geojson           -- road LineStrings
      regions.geojson         -- political polygons (Voronoi)
      settlements.json        -- list with name, type, x/y, importance
      landmarks.json          -- list with name, type, x/y
      labels.json             -- list with text, x/y, priority
      fog_mask.png            -- discovered/undiscovered mask
    previews/
      map_full.png
      map_biomes.png
      map_political.png
      map_roads_rivers.png
      map_fogged.png
    godot/
      world_map.tscn
      map_layers.tres

Algorithm (pure Python, no browser):
  1. Base height from FBM (reuse pipelines/terrain primitives)
  2. River network from steepest-descent flow accumulation
  3. Settlement candidates scored on biome+slope+water access
  4. Political regions from weighted Voronoi seeded at top settlements
  5. Roads from A* over slope cost between settlements
  6. Labels from settlement/landmark names (placeholder pool)
  7. Render to layered PNG/SVG and Godot scene

Usage:
  python generate_world_map.py --id mythos_a --size 2048 --seed 7
"""
from __future__ import annotations

import argparse
import heapq
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Pull primitives from the terrain pipeline
sys.path.insert(0, str(Path(r"D:\assets\pipelines\terrain")))
from generate_heightmap import fbm, shape_biome, thermal_erode, hypsometric_preview, normal_from_height
from terrain_bundle import slope_from_height, flow_accumulation_d8, derive_biome, BIOME_PALETTE

# Settlement / landmark / region naming pools (placeholder; LLM can override)
SETTLEMENT_PREFIXES = ["Aelb", "Bren", "Caer", "Dorn", "Eld", "Fros", "Gild", "Heim", "Ith", "Kor",
                      "Lain", "Mor", "Nava", "Oren", "Pyrm", "Quen", "Rast", "Sael", "Tal", "Uin",
                      "Vael", "Wyn", "Yarn", "Zal"]
SETTLEMENT_SUFFIXES = ["holm", "wick", "moor", "hold", "fall", "reach", "stead", "ford", "haven",
                       "marsh", "burg", "dale", "crag", "vale", "ridge", "spire", "watch", "glen"]
LANDMARK_NAMES = ["The Sundered Pass", "Old Wyrm Ruins", "Sunken Tor", "Whispering Cairns",
                  "The Iron Mire", "Frozen Sentinel", "Hollow King's Tomb", "Star-Lit Mere",
                  "Bonewood Crossing", "The Ember Caves", "Tide-Worn Spire", "Hag's Marsh"]


def make_name(rng: random.Random) -> str:
    return rng.choice(SETTLEMENT_PREFIXES) + rng.choice(SETTLEMENT_SUFFIXES)


# ---------------------------------------------------------------------------
# Settlement scoring
# ---------------------------------------------------------------------------
def settlement_candidates(height: np.ndarray, slope: np.ndarray, water: np.ndarray,
                          biome_labels: np.ndarray, n_settlements: int = 12,
                          rng: random.Random = None) -> list[dict]:
    rng = rng or random.Random(7)
    h, w = height.shape

    # Score: low slope + medium height + near-water + grass/forest biome
    score = np.zeros_like(height)
    score += np.clip(1.0 - slope * 4.0, 0, 1) * 0.5
    score += np.clip(1.0 - np.abs(height - 0.45) * 2.5, 0, 1) * 0.3
    # near-water bonus
    water_dist = np.zeros_like(height)
    from scipy.ndimage import distance_transform_edt
    if water.any():
        water_dist = distance_transform_edt((water > 0).astype(np.uint8) == 0)
        max_d = max(water_dist.max(), 1)
        score += np.clip(1.0 - water_dist / (max_d * 0.05), 0, 1) * 0.3
    # biome bonus (grass=2, forest=3 in derive_biome)
    score += ((biome_labels == 2) | (biome_labels == 3)).astype(np.float32) * 0.2
    # exclude under sea level
    score[height < 0.32] = 0
    # snow uninhabitable
    score[height > 0.78] *= 0.1

    # Pick top spots with min separation
    min_dist = max(20, min(h, w) // 24)
    candidates = []
    flat = score.flatten()
    order = np.argsort(flat)[::-1]
    for idx in order:
        if flat[idx] < 0.3:
            break
        y, x = divmod(int(idx), w)
        too_close = any(abs(c["x"] - x) + abs(c["y"] - y) < min_dist for c in candidates)
        if too_close:
            continue
        importance = float(flat[idx])
        kind = "city" if importance > 0.85 else "town" if importance > 0.65 else "village"
        candidates.append({
            "id": f"s{len(candidates):03d}",
            "name": make_name(rng),
            "kind": kind,
            "x": x, "y": y,
            "importance": importance,
        })
        if len(candidates) >= n_settlements:
            break
    return candidates


# ---------------------------------------------------------------------------
# Landmarks — placed at scenic but uninhabited spots
# ---------------------------------------------------------------------------
def landmark_candidates(height: np.ndarray, slope: np.ndarray, biome_labels: np.ndarray,
                        settlements: list[dict], n: int = 8, rng: random.Random = None) -> list[dict]:
    rng = rng or random.Random(11)
    h, w = height.shape
    # extreme terrain or unusual biome edges
    score = np.zeros_like(height)
    score += np.clip((slope - 0.4) * 2, 0, 1) * 0.5  # steep
    score += (biome_labels == 4).astype(np.float32) * 0.3  # rock
    score += np.clip(1.0 - np.abs(height - 0.85) * 6, 0, 1) * 0.3  # near-snow

    # Avoid settlements
    for s in settlements:
        sy, sx = s["y"], s["x"]
        ymin, ymax = max(0, sy - 60), min(h, sy + 60)
        xmin, xmax = max(0, sx - 60), min(w, sx + 60)
        score[ymin:ymax, xmin:xmax] *= 0.2

    score[height < 0.32] = 0  # no underwater landmarks

    candidates = []
    flat = score.flatten()
    order = np.argsort(flat)[::-1]
    for idx in order:
        if flat[idx] < 0.3:
            break
        y, x = divmod(int(idx), w)
        too_close = any(abs(c["x"] - x) + abs(c["y"] - y) < 80 for c in candidates)
        if too_close:
            continue
        candidates.append({
            "id": f"l{len(candidates):03d}",
            "name": rng.choice(LANDMARK_NAMES),
            "kind": rng.choice(["ruin", "cairn", "tomb", "shrine", "cave", "spire"]),
            "x": x, "y": y,
        })
        if len(candidates) >= n:
            break
    return candidates


# ---------------------------------------------------------------------------
# Roads via A* over slope cost
# ---------------------------------------------------------------------------
def astar_road(start: tuple[int, int], goal: tuple[int, int],
               cost_grid: np.ndarray, max_steps: int = 100_000) -> list[tuple[int, int]] | None:
    h, w = cost_grid.shape
    open_h = [(0.0, start)]
    came_from = {start: None}
    cost_so_far = {start: 0.0}
    steps = 0
    while open_h and steps < max_steps:
        _, current = heapq.heappop(open_h)
        if current == goal:
            break
        cy, cx = current
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
            ny, nx = cy + dy, cx + dx
            if not (0 <= ny < h and 0 <= nx < w):
                continue
            step_cost = cost_grid[ny, nx] * (1.41 if dy and dx else 1.0)
            new_cost = cost_so_far[current] + step_cost
            if (ny, nx) not in cost_so_far or new_cost < cost_so_far[(ny, nx)]:
                cost_so_far[(ny, nx)] = new_cost
                priority = new_cost + abs(goal[0] - ny) + abs(goal[1] - nx)
                heapq.heappush(open_h, (priority, (ny, nx)))
                came_from[(ny, nx)] = current
        steps += 1
    if goal not in came_from:
        return None
    path = [goal]
    while came_from[path[-1]] is not None:
        path.append(came_from[path[-1]])
    return path[::-1]


def build_roads(settlements: list[dict], height: np.ndarray, slope: np.ndarray,
                water_mask_arr: np.ndarray) -> list[list[tuple[int, int]]]:
    """Connect each settlement to its 2 nearest neighbors via A*."""
    cost = 1.0 + slope * 8.0
    cost[water_mask_arr > 0] = 50.0  # crossing water costs but possible
    cost[height < 0.32] = 100.0  # ocean is bad

    sxs = [(s["y"], s["x"], s["id"]) for s in settlements]
    roads = []
    seen = set()
    for i, (y1, x1, id1) in enumerate(sxs):
        # find 2 closest others
        dists = sorted(
            ((j, abs(y2 - y1) + abs(x2 - x1))
             for j, (y2, x2, _) in enumerate(sxs) if j != i),
            key=lambda x: x[1],
        )
        for j, _ in dists[:2]:
            key = tuple(sorted([id1, sxs[j][2]]))
            if key in seen:
                continue
            seen.add(key)
            path = astar_road((y1, x1), (sxs[j][0], sxs[j][1]), cost)
            if path:
                roads.append(path)
    return roads


# ---------------------------------------------------------------------------
# Political regions via weighted Voronoi
# ---------------------------------------------------------------------------
def weighted_voronoi(seeds: list[dict], h: int, w: int, weights: list[float]) -> np.ndarray:
    """Each pixel labelled with index of nearest seed (weighted)."""
    out = np.zeros((h, w), dtype=np.int32)
    ys, xs = np.indices((h, w))
    best_d = np.full((h, w), np.inf)
    for i, s in enumerate(seeds):
        d = np.sqrt((ys - s["y"]) ** 2 + (xs - s["x"]) ** 2) / max(weights[i], 1e-3)
        mask = d < best_d
        best_d[mask] = d[mask]
        out[mask] = i
    return out


# ---------------------------------------------------------------------------
# River extraction from flow accumulation
# ---------------------------------------------------------------------------
def extract_rivers(flow: np.ndarray, threshold: float = 0.4, height: np.ndarray = None,
                   sea_level: float = 0.32, min_length: int = 10) -> list[list[tuple[int, int]]]:
    """Trace river paths from high-flow cells downstream until they hit sea or edge."""
    h, w = flow.shape
    rivers = []
    visited = np.zeros((h, w), dtype=bool)

    high_cells = np.argwhere(flow > threshold)
    rng = np.random.default_rng(13)
    rng.shuffle(high_cells)

    for start in high_cells[:200]:  # cap how many we trace
        y, x = start
        if visited[y, x]:
            continue
        path = [(int(y), int(x))]
        for _ in range(2000):
            visited[y, x] = True
            # find lowest neighbor
            best = None
            best_h = height[y, x] if height is not None else 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy == 0 and dx == 0:
                        continue
                    ny, nx = y + dy, x + dx
                    if not (0 <= ny < h and 0 <= nx < w):
                        continue
                    if height is not None and height[ny, nx] < best_h:
                        best_h = height[ny, nx]
                        best = (ny, nx)
            if best is None:
                break
            y, x = best
            if height is not None and height[y, x] < sea_level:
                path.append((int(y), int(x)))
                break
            path.append((int(y), int(x)))
            if visited[y, x]:
                break

        if len(path) >= min_length:
            rivers.append(path)
    return rivers


# ---------------------------------------------------------------------------
# GeoJSON helpers
# ---------------------------------------------------------------------------
def linestring_geojson(paths: list[list[tuple[int, int]]], properties_fn=None) -> dict:
    features = []
    for i, path in enumerate(paths):
        coords = [[float(x), float(y)] for (y, x) in path]  # GeoJSON [lon, lat]
        props = {"id": i}
        if properties_fn:
            props.update(properties_fn(i, path))
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": props,
        })
    return {"type": "FeatureCollection", "features": features}


def polygon_from_voronoi(label_arr: np.ndarray, label: int) -> dict | None:
    """Build a simplified polygon outline from a region mask via simple boundary trace."""
    mask = (label_arr == label).astype(np.uint8)
    if mask.sum() < 4:
        return None
    # Just provide bounding-box outline as a fast approximation
    ys, xs = np.where(mask > 0)
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    coords = [
        [float(x0), float(y0)], [float(x1), float(y0)],
        [float(x1), float(y1)], [float(x0), float(y1)],
        [float(x0), float(y0)],
    ]
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [coords]},
        "properties": {"region_id": int(label)},
    }


# ---------------------------------------------------------------------------
# Preview rendering
# ---------------------------------------------------------------------------
def render_full_preview(height: np.ndarray, biome_rgb: np.ndarray,
                        rivers: list, roads: list, settlements: list,
                        landmarks: list, regions: np.ndarray | None) -> Image.Image:
    img = Image.fromarray(biome_rgb, mode="RGB").copy()
    draw = ImageDraw.Draw(img, "RGBA")

    # Region overlay — translucent colors
    if regions is not None:
        n_regs = int(regions.max()) + 1
        rng = np.random.default_rng(42)
        colors = [tuple(rng.integers(60, 230, 3).tolist()) + (60,) for _ in range(n_regs)]
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ovd = ImageDraw.Draw(overlay)
        h, w = regions.shape
        for label in range(n_regs):
            mask = regions == label
            ys, xs = np.where(mask)
            if len(ys) == 0:
                continue
            color = colors[label]
            # quick render: draw bounding rect
            ovd.rectangle([int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], fill=color)
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img, "RGBA")

    # Rivers — thin blue lines
    for path in rivers:
        if len(path) < 2:
            continue
        draw.line([(x, y) for (y, x) in path], fill=(40, 100, 200, 220), width=1)

    # Roads — tan dashed
    for path in roads:
        if len(path) < 2:
            continue
        draw.line([(x, y) for (y, x) in path], fill=(180, 140, 70, 230), width=2)

    # Settlements — circles + labels
    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except Exception:
        font = ImageFont.load_default()
    for s in settlements:
        x, y = s["x"], s["y"]
        r = 4 if s["kind"] == "city" else 3 if s["kind"] == "town" else 2
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 235, 200), outline=(40, 30, 20))
        draw.text((x + r + 2, y - 6), s["name"], fill=(20, 20, 20), font=font)

    # Landmarks — diamonds
    for l in landmarks:
        x, y = l["x"], l["y"]
        r = 3
        draw.polygon([(x, y - r), (x + r, y), (x, y + r), (x - r, y)],
                    fill=(180, 50, 200), outline=(60, 20, 80))

    return img


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--biome", default="custom",
                    choices=["mountains", "plains", "islands", "canyon", "custom"])
    ap.add_argument("--n-settlements", type=int, default=14)
    ap.add_argument("--n-landmarks", type=int, default=8)
    ap.add_argument("--n-factions", type=int, default=4)
    ap.add_argument("--out-root", type=Path,
                    default=Path(r"D:\assets\world\maps"))
    args = ap.parse_args()

    out_dir = args.out_root / args.id
    layers_dir = out_dir / "layers"
    previews_dir = out_dir / "previews"
    godot_dir = out_dir / "godot"
    for d in [layers_dir, previews_dir, godot_dir]:
        d.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)

    # 1. Base height
    print(f"[1/9] FBM heightmap {args.size}x{args.size}")
    h = fbm(args.size, base_scale=4, octaves=6, seed=args.seed)
    h = (h - h.min()) / (h.max() - h.min() + 1e-9)
    h = shape_biome(h, args.biome)
    h = thermal_erode(h, iterations=30)

    print("[2/9] slope, flow, biome")
    slope = slope_from_height(h)
    flow = flow_accumulation_d8(h, iterations=15)
    biome_rgb, biome_labels = derive_biome(h, slope)
    water_mask_arr = (h < 0.32).astype(np.uint8) * 255

    # Save base layers
    Image.fromarray((h * 65535).astype(np.uint16), mode="I;16").save(layers_dir / "height.png")
    Image.fromarray(biome_rgb, mode="RGB").save(layers_dir / "biome.png")
    Image.fromarray(water_mask_arr, mode="L").save(layers_dir / "fog_mask.png")  # placeholder fog = water

    # 3. Rivers
    print("[3/9] rivers")
    rivers = extract_rivers(flow, threshold=0.4, height=h, sea_level=0.32, min_length=8)
    (layers_dir / "rivers.geojson").write_text(json.dumps(linestring_geojson(rivers)), encoding="utf-8")

    # 4. Settlements
    print("[4/9] settlements")
    settlements = settlement_candidates(h, slope, water_mask_arr, biome_labels,
                                        n_settlements=args.n_settlements, rng=rng)
    (layers_dir / "settlements.json").write_text(json.dumps(settlements, indent=2), encoding="utf-8")

    # 5. Landmarks
    print("[5/9] landmarks")
    landmarks = landmark_candidates(h, slope, biome_labels, settlements,
                                    n=args.n_landmarks, rng=rng)
    (layers_dir / "landmarks.json").write_text(json.dumps(landmarks, indent=2), encoding="utf-8")

    # 6. Roads
    print("[6/9] roads")
    roads = build_roads(settlements, h, slope, water_mask_arr)
    (layers_dir / "roads.geojson").write_text(json.dumps(linestring_geojson(roads)), encoding="utf-8")

    # 7. Political regions — Voronoi seeded at top-importance settlements
    print("[7/9] political regions")
    capitals = sorted(settlements, key=lambda s: -s["importance"])[:args.n_factions]
    weights = [s["importance"] for s in capitals]
    regions = weighted_voronoi(capitals, args.size, args.size, weights) if capitals else None
    region_features = []
    if regions is not None:
        for label in range(len(capitals)):
            poly = polygon_from_voronoi(regions, label)
            if poly:
                poly["properties"]["capital"] = capitals[label]["name"]
                region_features.append(poly)
    (layers_dir / "regions.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": region_features}), encoding="utf-8"
    )

    # 8. Labels — flatten settlements + landmarks + regions
    print("[8/9] labels")
    labels = []
    for s in settlements:
        labels.append({"text": s["name"], "x": s["x"], "y": s["y"],
                       "priority": int(s["importance"] * 10), "kind": s["kind"]})
    for l in landmarks:
        labels.append({"text": l["name"], "x": l["x"], "y": l["y"], "priority": 5,
                       "kind": l["kind"]})
    (layers_dir / "labels.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")

    # Water polygon (simple bbox of water mask)
    (layers_dir / "water.geojson").write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [args.size, 0],
                          [args.size, args.size], [0, args.size], [0, 0]]]},
            "properties": {"note": "see fog_mask.png for actual water mask"}
        }]
    }), encoding="utf-8")

    # 9. Previews
    print("[9/9] previews")
    full = render_full_preview(h, biome_rgb, rivers, roads, settlements, landmarks, regions)
    full.save(previews_dir / "map_full.png")
    Image.fromarray(biome_rgb, mode="RGB").save(previews_dir / "map_biomes.png")
    # Political: just biome + regions tint + capitals
    pol = render_full_preview(h, biome_rgb, [], [], [s for s in settlements if s["importance"] > 0.7],
                               [], regions)
    pol.save(previews_dir / "map_political.png")
    rr = render_full_preview(h, biome_rgb, rivers, roads, [], [], None)
    rr.save(previews_dir / "map_roads_rivers.png")

    # Fogged: dark out everything > some distance from settlements
    fogged = full.copy().convert("RGBA")
    fog_overlay = Image.new("RGBA", fogged.size, (0, 0, 0, 220))
    fog_draw = ImageDraw.Draw(fog_overlay)
    for s in settlements:
        r = 50
        fog_draw.ellipse([s["x"] - r, s["y"] - r, s["x"] + r, s["y"] + r], fill=(0, 0, 0, 0))
    fogged = Image.alpha_composite(fogged, fog_overlay).convert("RGB")
    fogged.save(previews_dir / "map_fogged.png")

    # Godot scene + map.json
    map_meta = {
        "id": args.id,
        "created": datetime.now(timezone.utc).isoformat(),
        "size": args.size, "seed": args.seed, "biome_preset": args.biome,
        "n_settlements": len(settlements), "n_landmarks": len(landmarks),
        "n_rivers": len(rivers), "n_roads": len(roads),
        "n_regions": len(region_features),
        "layers": {
            "height": "layers/height.png",
            "biome": "layers/biome.png",
            "water": "layers/water.geojson",
            "rivers": "layers/rivers.geojson",
            "roads": "layers/roads.geojson",
            "regions": "layers/regions.geojson",
            "settlements": "layers/settlements.json",
            "landmarks": "layers/landmarks.json",
            "labels": "layers/labels.json",
            "fog_mask": "layers/fog_mask.png",
        },
        "previews": {
            "full": "previews/map_full.png",
            "biomes": "previews/map_biomes.png",
            "political": "previews/map_political.png",
            "roads_rivers": "previews/map_roads_rivers.png",
            "fogged": "previews/map_fogged.png",
        },
    }
    (out_dir / "map.json").write_text(json.dumps(map_meta, indent=2), encoding="utf-8")

    # Minimal Godot scene that displays map_full.png as a Sprite2D background
    tscn = f"""[gd_scene load_steps=2 format=3 uid="uid://{args.id}_map"]

[ext_resource type="Texture2D" path="res://map_full.png" id="1"]

[node name="WorldMap" type="Node2D"]

[node name="Background" type="Sprite2D" parent="."]
texture = ExtResource("1")
centered = false
"""
    (godot_dir / "world_map.tscn").write_text(tscn, encoding="utf-8")
    # Copy preview into godot dir for the scene's res:// reference
    full.save(godot_dir / "map_full.png")

    print(f"\ndone: {out_dir}")
    print(f"  settlements: {len(settlements)}")
    print(f"  landmarks: {len(landmarks)}")
    print(f"  rivers: {len(rivers)}")
    print(f"  roads: {len(roads)}")
    print(f"  factions: {len(region_features)}")


if __name__ == "__main__":
    main()
