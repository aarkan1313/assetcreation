"""Build per-tile splat textures + meta from a biome catalog + tile assignments.

For each tile under `<bundle_dir>/tiles/tile_X_Z/`:
- Read the tile's meta.json (must have a "biome" field).
- Write a splat.png (RGBA8) at splat_size x splat_size.
- Write a splat_meta.json describing the 4 RGBA channels: each channel
  is one contributing biome with per-slot (tier, layer) addressing so
  the shader can sample the right Texture2DArray layer for ground/mid/
  rock independently. This lets a single biome span tiers (e.g. forest:
  ground+rock at hero, mid at standard).

Modes:
- "hard"    : every pixel = (255, 0, 0, 0), channel 0 = the tile's own biome.
              Channels 1..3 empty. Regression-check vs single-material path.
- "feather" : pixels within feather_width_m of a tile edge adjacent to a
              different biome ramp from this biome -> neighbor (Stage 5b).

splat_meta.json schema:
  {
    "splat_size": <int>,
    "mode": "<hard|feather>",
    "channels": [
      {"biome": "<name>", "ground": {"tier": "...", "layer": <i>},
                          "mid":    {"tier": "...", "layer": <j>},
                          "rock":   {"tier": "...", "layer": <k>}},
      ...  // 4 channels total; empty channels have all values null
    ]
  }

Usage:
    python build_tile_splats.py \\
        --bundle  "<path>/scale_demo" \\
        --manifest "<path>/arrays/layer_manifest.json" \\
        --mode hard \\
        --splat-size 64
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image


class SplatError(RuntimeError):
    pass


def _biome_slots(manifest: dict, biome: str) -> Optional[dict]:
    """Return {ground, mid, rock} -> {tier, layer} dict for a biome.

    Walks both tiers' layers in the manifest looking for matches on the
    given biome name. Returns None if the biome is unknown OR if it's
    missing any of the 3 slots.
    """
    found: dict[str, dict] = {}
    for tier_name, tdata in manifest["tiers"].items():
        for layer in tdata["layers"]:
            if layer["biome"] != biome:
                continue
            found[layer["slot"]] = {"tier": tier_name, "layer": int(layer["layer"])}
    if not all(s in found for s in ("ground", "mid", "rock")):
        return None
    return found


def _channel_record(biome: str, slots: dict) -> dict:
    return {
        "biome":  biome,
        "ground": slots["ground"],
        "mid":    slots["mid"],
        "rock":   slots["rock"],
    }


def _empty_channel() -> dict:
    return {"biome": None, "ground": None, "mid": None, "rock": None}


def build_splats(*, bundle_dir: Path | str, manifest: dict,
                 mode: str, splat_size: int, feather_width_m: float) -> None:
    if mode != "hard":
        raise NotImplementedError(f"mode={mode!r} not implemented in stage 5a")
    bundle = Path(bundle_dir)
    tiles_dir = bundle / "tiles"
    for tile_dir in sorted(tiles_dir.iterdir()):
        if not tile_dir.is_dir() or not tile_dir.name.startswith("tile_"):
            continue
        meta_path = tile_dir / "meta.json"
        if not meta_path.is_file():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        biome = meta.get("biome")
        if not biome:
            raise SplatError(f"{tile_dir}: tile meta has no biome field")
        slots = _biome_slots(manifest, biome)
        if slots is None:
            raise SplatError(
                f"{tile_dir}: biome {biome!r} not found (or missing slots) in manifest")
        arr = np.zeros((splat_size, splat_size, 4), dtype=np.uint8)
        arr[..., 0] = 255
        Image.fromarray(arr, mode="RGBA").save(tile_dir / "splat.png")
        ch_meta = [_channel_record(biome, slots)]
        for _ in range(3):
            ch_meta.append(_empty_channel())
        splat_meta = {
            "splat_size": splat_size,
            "mode": mode,
            "channels": ch_meta,
        }
        (tile_dir / "splat_meta.json").write_text(
            json.dumps(splat_meta, indent=2) + "\n",
            encoding="utf-8", newline="\n",
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--mode", default="hard", choices=["hard", "feather"])
    ap.add_argument("--splat-size", type=int, default=64)
    ap.add_argument("--feather-width-m", type=float, default=32.0)
    args = ap.parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    build_splats(bundle_dir=args.bundle, manifest=manifest, mode=args.mode,
                 splat_size=args.splat_size, feather_width_m=args.feather_width_m)
    print(f"splats: mode={args.mode} size={args.splat_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
