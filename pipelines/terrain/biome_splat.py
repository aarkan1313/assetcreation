"""Biome-aware splat compiler.

Reads a world's biome_labels.png + biome_texture_registry.json, writes a fresh
splat_rgba where each biome occupies a fixed RGBA channel (per the registry).

This replaces the old "grass/rock/forest/snow" splat for biome worlds — the
terrain shader now blends 4 biome PBR sets directly.

Soft edges: uses a small Gaussian over each channel so transitions read smooth
in the shader instead of a hard 1-pixel step.

Usage:
  python biome_splat.py --world D:/assets/world/worlds/qa_fjord_4biome
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

REGISTRY_PATH = Path(r"D:\assets\art_lab\biomes\biome_texture_registry.json")
CHANNEL_INDEX = {"R": 0, "G": 1, "B": 2, "A": 3}


def load_registry() -> dict:
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def biome_label_to_id(world_dir: Path) -> dict[int, str]:
    """Read world.json to learn the biome ordering, then return label_idx -> biome_id."""
    with (world_dir / "world.json").open("r", encoding="utf-8") as f:
        wj = json.load(f)
    return {i: bid for i, bid in enumerate(wj["biomes"])}


def compile_splat(world_dir: Path, blur_px: float = 1.6) -> Path:
    """Compile biome_labels → biome_splat_rgba.png.

    Channels are assigned by **position in world.json's `biomes` list** (slot 0=R,
    1=G, 2=B, 3=A), NOT by the registry's `splat_channel`. This lets any 4-tuple
    of biomes coexist in a scene without channel collisions. The registry's
    `splat_channel` is now a legacy/hint field and is ignored here.

    The downstream `biome_pbr_pack.json` written by `biome_texture_bind.py` re-
    derives channels from this same scene-position rule, so the chain stays
    consistent end-to-end (splat → pack → shader).
    """
    registry = load_registry()
    label_to_biome = biome_label_to_id(world_dir)

    labels = np.asarray(Image.open(world_dir / "biome_labels.png"))
    h, w = labels.shape[:2]
    splat = np.zeros((h, w, 4), dtype=np.float32)

    # Map each scene-position to its RGBA channel letter.
    pos_to_letter = {0: "R", 1: "G", 2: "B", 3: "A"}
    channel_to_biome: dict[str, str] = {}

    for label_idx, biome_id in label_to_biome.items():
        if biome_id not in registry["biomes"]:
            print(f"[warn] biome '{biome_id}' has no registry entry — skipping in splat")
            continue
        if label_idx >= 4:
            print(f"[warn] world has >4 biomes; only first 4 fit in RGBA splat")
            break
        ch = label_idx
        splat[..., ch] = (labels == label_idx).astype(np.float32)
        channel_to_biome[pos_to_letter[ch]] = biome_id

    if blur_px > 0:
        for ch in range(4):
            im = Image.fromarray((splat[..., ch] * 255).astype(np.uint8), mode="L")
            im = im.filter(ImageFilter.GaussianBlur(radius=blur_px))
            splat[..., ch] = np.asarray(im, dtype=np.float32) / 255.0

    s = splat.sum(axis=2, keepdims=True)
    s = np.where(s < 1e-6, 1.0, s)
    splat = splat / s

    out_path = world_dir / "biome_splat_rgba.png"
    Image.fromarray((splat * 255).clip(0, 255).astype(np.uint8), mode="RGBA").save(out_path)

    manifest = {
        "channel_to_biome": channel_to_biome,
        "blur_px": blur_px,
        "size": [w, h],
    }
    with (world_dir / "biome_splat.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"wrote {out_path}")
    print(f"channels: {manifest['channel_to_biome']}")
    return out_path


SPLAT_MODES = {
    "gaussian": {
        "blur_px": 1.6,
        "description": "Soft Gaussian-blurred boundaries (default). 1.6 px feather.",
    },
    "soft": {
        "blur_px": 3.2,
        "description": "Wider Gaussian (3.2 px). Use for atmospheric biome zones.",
    },
    "hard": {
        "blur_px": 0.0,
        "description": "No blur. 1-pixel-sharp boundaries. Best when paired with "
                       "future height-blend shader for crisp pebble-into-sand transitions.",
    },
    "height_blend": {
        "blur_px": 0.0,
        "description": "RESERVED — height-based blend using albedo alpha as height. "
                       "Implementation pending in biome_terrain_heightblend.gdshader; "
                       "currently behaves like 'hard' (no blur) so the future shader sees "
                       "crisp splat data.",
    },
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", type=Path, required=True,
                    help="world output directory (containing biome_labels.png + world.json)")
    ap.add_argument("--splat-mode", choices=list(SPLAT_MODES.keys()), default="gaussian",
                    help="splat boundary blending strategy. Sets blur_px from preset. "
                         "Override via --blur-px.")
    ap.add_argument("--blur-px", type=float, default=None,
                    help="Override splat-mode's blur radius. Set 0 to disable.")
    args = ap.parse_args()

    if not args.world.is_dir():
        raise SystemExit(f"world dir not found: {args.world}")

    mode = SPLAT_MODES[args.splat_mode]
    blur_px = args.blur_px if args.blur_px is not None else mode["blur_px"]
    print(f"  [splat] mode={args.splat_mode} blur_px={blur_px} :: {mode['description']}")

    compile_splat(args.world, blur_px=blur_px)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
