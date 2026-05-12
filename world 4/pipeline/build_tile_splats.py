"""Build per-tile splat textures + meta from a biome catalog + tile assignments.

For each tile under `<bundle_dir>/tiles/tile_X_Z/`:
- Read the tile's meta.json (must have a "biome" field).
- Write a splat.png (RGBA8) at splat_size x splat_size.
- Write a splat_meta.json describing the 4 RGBA channels: each channel
  is one contributing biome with per-slot (tier, slot) addressing so
  the shader can sample the right Texture2DArray layer for ground/mid/
  rock independently. This lets a single biome span tiers (e.g. forest:
  ground+rock at hero, mid at standard).

Slot-pool indirection (Stage 5c):
- The `slot` value emitted is a *slot-pool index*, not a raw array
  layer. The manifest's `slot_pool` array maps slot index -> array
  layer index. In v1 the pool is identity (pool[i] == i), so the
  numbers in splat_meta are unchanged from the raw-layer scheme; the
  semantic shift makes streaming (paging biomes in/out of array
  slots) a CPU-side change instead of a splat-regenerate.
- ScaleWorld owns the pool->layer lookup at material-init time. The
  shader sees only packed (tier, layer) ints as uniforms.

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
      {"biome": "<name>", "ground": {"tier": "...", "slot": <i>},
                          "mid":    {"tier": "...", "slot": <j>},
                          "rock":   {"tier": "...", "slot": <k>}},
      ...  // 4 channels total; empty channels have all values null
    ]
  }

(Pre-5c builds emit `"layer"` in place of `"slot"`. ScaleWorld accepts
both for backwards-compat with on-disk splats from earlier sessions.)

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
    """Return {ground, mid, rock} -> {tier, slot} dict for a biome.

    Walks both tiers' layers in the manifest looking for matches on the
    given biome name. The emitted `slot` value is a slot-pool index, not
    a raw array layer index — ScaleWorld translates pool -> layer via
    the manifest's `slot_pool` map at material-init time.

    In v1 the slot pool is identity (pool[i] == i), so the numbers we
    emit equal the raw layer indices we receive. The semantic shift is
    what matters: streaming layer paging becomes a CPU-side concern.

    Returns None if the biome is unknown OR if it's missing any of the
    3 slots.
    """
    found: dict[str, dict] = {}
    for tier_name, tdata in manifest["tiers"].items():
        slot_pool = tdata.get("slot_pool")
        for layer in tdata["layers"]:
            if layer["biome"] != biome:
                continue
            raw_layer = int(layer["layer"])
            # Translate raw layer -> slot-pool index (the position in
            # slot_pool whose value == raw_layer). v1 is identity so this
            # equals raw_layer, but writing it via the lookup ensures the
            # contract is honoured if a future manifest uses a non-identity
            # pool (streaming follow-up).
            if slot_pool is None:
                slot_idx = raw_layer  # legacy pre-5c manifest
            else:
                try:
                    slot_idx = list(slot_pool).index(raw_layer)
                except ValueError:
                    # Pool doesn't reference this layer; skip.
                    continue
            found[layer["slot"]] = {"tier": tier_name, "slot": slot_idx}
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
    if mode not in ("hard", "feather"):
        raise NotImplementedError(f"mode={mode!r} not implemented")
    bundle = Path(bundle_dir)
    tiles_dir = bundle / "tiles"
    # Pre-scan: build (tx, tz) -> biome map so we can look up neighbors.
    tile_biomes: dict[tuple[int, int], str] = {}
    tile_size_m: float = 256.0
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
        tile_biomes[(int(meta["tile_x"]), int(meta["tile_z"]))] = biome
        tile_size_m = float(meta.get("tile_size_m", tile_size_m))
    # Build splat per tile.
    for (tx, tz), biome in sorted(tile_biomes.items()):
        tile_dir = tiles_dir / f"tile_{tx}_{tz}"
        slots = _biome_slots(manifest, biome)
        if slots is None:
            raise SplatError(
                f"{tile_dir}: biome {biome!r} not found (or missing slots) in manifest")
        this_rec = _channel_record(biome, slots)
        if mode == "hard" or feather_width_m <= 0.0:
            arr = np.zeros((splat_size, splat_size, 4), dtype=np.uint8)
            arr[..., 0] = 255
            ch_meta = [this_rec, _empty_channel(), _empty_channel(), _empty_channel()]
        else:
            arr, ch_meta = _feather_splat(
                tx=tx, tz=tz, this_biome=biome, this_rec=this_rec,
                tile_biomes=tile_biomes, manifest=manifest,
                splat_size=splat_size, tile_size_m=tile_size_m,
                feather_width_m=feather_width_m,
            )
        Image.fromarray(arr, mode="RGBA").save(tile_dir / "splat.png")
        splat_meta = {
            "splat_size": splat_size,
            "mode": mode,
            "channels": ch_meta,
        }
        (tile_dir / "splat_meta.json").write_text(
            json.dumps(splat_meta, indent=2) + "\n",
            encoding="utf-8", newline="\n",
        )


def _feather_splat(*, tx: int, tz: int, this_biome: str, this_rec: dict,
                   tile_biomes: dict[tuple[int, int], str], manifest: dict,
                   splat_size: int, tile_size_m: float,
                   feather_width_m: float) -> tuple[np.ndarray, list[dict]]:
    """Build a feathered splat for tile (tx, tz).

    Channel 0 is always this_biome at base weight 1.0.
    Channels 1..3 are up to 3 *unique* different-biome neighbors, in
    NESW iteration order. If more than 3 distinct neighbor biomes
    surround a tile (4-way junction with all-different), the 4th
    neighbor is dropped (rare; documented as a v1 limitation).

    Per pixel, each neighbor's weight ramps from 0 (more than
    feather_width_m from any boundary with that neighbor) to 0.5 at
    the very edge. The neighbor tile's mirror-side contributes the
    other 0.5, so summed across the boundary you get a smooth
    100% -> 50/50 -> 100% transition over 2*feather_width_m.
    """
    nb_dirs = {
        "N": (tx, tz + 1),  # +Z = north
        "E": (tx + 1, tz),  # +X = east
        "S": (tx, tz - 1),  # -Z = south
        "W": (tx - 1, tz),  # -X = west
    }
    # Allocate up to 3 channels for unique different-biome neighbors.
    neighbor_channels: list[tuple[str, dict]] = []  # (biome_name, channel_record)
    dir_to_channel: dict[str, int] = {}             # "N" -> channel idx (1..3)
    for d in ("N", "E", "S", "W"):
        nc = nb_dirs[d]
        if nc not in tile_biomes:
            continue  # off-world edge — no feather
        nb_name = tile_biomes[nc]
        if nb_name == this_biome:
            continue  # same biome — no feather
        existing = next(
            (i for i, (b, _) in enumerate(neighbor_channels) if b == nb_name),
            None,
        )
        if existing is not None:
            dir_to_channel[d] = existing + 1
        elif len(neighbor_channels) < 3:
            slots = _biome_slots(manifest, nb_name)
            if slots is None:
                raise SplatError(
                    f"neighbor biome {nb_name!r} of tile ({tx},{tz}) not in manifest")
            neighbor_channels.append((nb_name, _channel_record(nb_name, slots)))
            dir_to_channel[d] = len(neighbor_channels)  # 1, 2, or 3
        # If 3 distinct neighbors already + a 4th different biome appears,
        # we silently drop it. v1 limitation.

    px = splat_size
    weights = np.zeros((px, px, 4), dtype=np.float32)
    weights[..., 0] = 1.0  # base: this_biome everywhere

    if dir_to_channel:
        # Per-pixel distance to each tile edge, in METERS.
        m_per_px = tile_size_m / px
        j = np.arange(px, dtype=np.float32)
        i = np.arange(px, dtype=np.float32)
        # In our splat-UV convention, splat row 0 maps to v_world_pos.z =
        # tile_origin_z (the south edge), and row (px-1) maps to the
        # north edge. The splat builder writes the array straight to
        # disk, and PIL.Image.fromarray treats arr[0, :] as the top
        # row of the PNG. The shader samples splat_uv = (xz - origin) /
        # size, where +Z is "up" in UV. Since PNG-row-0 is the top of
        # the image, and +Z is up in world, PNG-row-0 corresponds to
        # the north edge. So:
        #   - row 0 = north edge -> dist_N small there
        #   - row px-1 = south edge -> dist_S small there
        dist_N = (i + 0.5) * m_per_px           # shape (px,)
        dist_S = (px - 0.5 - i) * m_per_px      # shape (px,)
        dist_W = (j + 0.5) * m_per_px           # shape (px,)
        dist_E = (px - 0.5 - j) * m_per_px      # shape (px,)

        def edge_ramp(d_m: np.ndarray) -> np.ndarray:
            # 0 at distance >= feather_width_m, 0.5 at the edge (d=0).
            r = np.clip(1.0 - d_m / feather_width_m, 0.0, 1.0)
            return 0.5 * r

        rN = edge_ramp(dist_N)[:, np.newaxis]  # (px, 1)
        rS = edge_ramp(dist_S)[:, np.newaxis]
        rW = edge_ramp(dist_W)[np.newaxis, :]  # (1, px)
        rE = edge_ramp(dist_E)[np.newaxis, :]
        ramps = {"N": rN, "S": rS, "W": rW, "E": rE}

        for d, ch in dir_to_channel.items():
            # Add ramp to neighbor's channel; subtract from base.
            weights[..., ch] += ramps[d]
            weights[..., 0]  -= ramps[d]

    # Clamp + normalize so per-pixel weights sum to 1.0.
    weights = np.clip(weights, 0.0, 1.0)
    total = weights.sum(axis=-1, keepdims=True)
    total = np.maximum(total, 1e-6)
    weights = weights / total
    arr = (weights * 255.0 + 0.5).astype(np.uint8)

    ch_meta = [this_rec]
    for _, rec in neighbor_channels:
        ch_meta.append(rec)
    while len(ch_meta) < 4:
        ch_meta.append(_empty_channel())
    return arr, ch_meta


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
