"""Mystery sampler — generate random unknown bbox candidates worldwide.

Walks a series of "interesting-looking-by-rule" filters to seed N random regions
that we have no prior knowledge of. Output is appended to data_wishlist.json
as a 'mystery' tier so bulk_pull.py can fetch them.

Heuristic for "interesting":
  - Avoid pure ocean (random bbox in ocean = nothing).
  - Avoid pure flat (no relief = boring).
  - Avoid populated areas if we want untouched-feeling.
  - Bias toward latitude bands with mountain belts / fjord coasts / desert / volcanism.

We don't have ground-truth landcover here without extra data, so we use a
land-mask approximation: probability bands by latitude that match the ratio of
land-to-sea in each strip + tagged "interesting strips" (Andes, Himalayas, etc).

Usage:
  python mystery_sampler.py --count 300 --seed 42 --out data_wishlist_mystery.json
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

# (lon_min, lon_max, lat_min, lat_max, weight, tag) — biased toward landscape-rich strips
INTERESTING_STRIPS = [
    # Latitude / longitude land-rich + interesting strips
    (-180,  -50,  50,   80, 1.0, "north_america_arctic"),     # Arctic Canada / Alaska
    (-130, -100,  35,   55, 2.5, "rockies_cascades"),         # Pacific NW / Rockies
    (-115,  -95,  30,   45, 1.8, "great_basin"),              # Nevada / Utah / Colorado
    ( -85,  -65, -55,  -20, 2.2, "andes"),                    # The whole Andes
    ( -10,   30,  35,   50, 2.0, "med_alps"),                 # Mediterranean + Alps
    (   5,   35,  55,   72, 2.0, "scandinavia"),              # Norway/Sweden/Finland
    ( -25,  -15,  60,   72, 1.4, "iceland_faroes"),
    (  20,   80,  25,   45, 2.2, "central_asia_high"),        # Caucasus to Pamir
    (  60,   95,  25,   40, 2.5, "himalaya"),                 # Hindu Kush to E Himalaya
    ( 100,  150,  20,   55, 1.8, "east_asia"),                # China + Japan + Korea
    (  90,  170, -45,    0, 1.6, "indonesia_oceania"),
    ( 165,  180, -50,  -34, 1.3, "new_zealand"),
    (  17,   35, -35,   -5, 1.5, "africa_east"),
    ( -10,   30, -35,   -5, 1.0, "africa_south"),
    ( -20,   45,  20,   35, 1.4, "north_africa"),
    ( 130,  155, -45,  -10, 1.6, "australia"),
    ( -80,  -65,  10,   28, 0.8, "caribbean_central_am"),
    (  35,   60,   8,   20, 1.0, "arabian_peninsula"),
    ( 145,  160,  45,   60, 1.5, "kamchatka_kurils"),
]


def random_bbox_from_strip(strip, rng: random.Random, size_deg: float = 0.20) -> tuple[float, float, float, float]:
    lon_min, lon_max, lat_min, lat_max, _, _ = strip
    # Pick a random center in the strip, build a square bbox around it.
    # Size 0.20 deg ≈ 22km at equator (smaller toward poles, expected).
    cx = rng.uniform(lon_min, lon_max)
    cy = rng.uniform(lat_min, lat_max)
    half = size_deg * 0.5
    return (round(cx - half, 4), round(cy - half, 4),
            round(cx + half, 4), round(cy + half, 4))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=300)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--size-deg", type=float, default=0.20,
                    help="bbox edge in degrees (0.20 deg ≈ 22km at equator)")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    total_weight = sum(w for _, _, _, _, w, _ in INTERESTING_STRIPS)

    regions = []
    for i in range(args.count):
        # Weighted strip choice
        roll = rng.uniform(0.0, total_weight)
        accum = 0.0
        chosen_strip = INTERESTING_STRIPS[0]
        for s in INTERESTING_STRIPS:
            accum += s[4]
            if roll <= accum:
                chosen_strip = s
                break
        bbox = random_bbox_from_strip(chosen_strip, rng, args.size_deg)
        # Latitude-aware dataset choice: high-lat areas use AW3D30
        lat_mid = (bbox[1] + bbox[3]) / 2
        dataset = "AW3D30" if abs(lat_mid) > 60.0 else "COP30"
        regions.append({
            "id": f"mystery_{i:03d}_{chosen_strip[5]}",
            "bbox": list(bbox),
            "dataset": dataset,
            "tags": ["mystery", chosen_strip[5]],
            "fantasy_styles": ["realistic", "exaggerated", "mythic"],
            "tagline": f"Procedurally-sampled {chosen_strip[5]} bbox"
        })

    out_obj = {
        "_doc": "Mystery tier of data_wishlist.json — procedurally sampled unknown bboxes worldwide.",
        "version": 1,
        "count": len(regions),
        "seed": args.seed,
        "size_deg": args.size_deg,
        "regions": regions,
    }
    args.out.write_text(json.dumps(out_obj, indent=2), encoding="utf-8")
    print(f"wrote {args.out} — {len(regions)} mystery regions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
