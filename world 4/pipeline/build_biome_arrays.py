"""Builds a layer manifest from a biome catalog.

Outputs a JSON manifest enumerating, per tier, which PBR files
correspond to which layer index. This manifest is consumed by:

- A Godot-side .tres emitter that builds Texture2DArray resources.
- ScaleWorld.gd at runtime, to map (biome, slot) -> (tier, layer).

We deliberately do NOT pack the texture array bytes here in Python.
Godot owns the import + compression path; we just hand it a layered
file list. See write_array_tres.py for the .tres emitter.

Auto-upsample policy: a Texture2DArray requires all layers to have the
same resolution. If a source PNG is *smaller* than the tier's
resolution (e.g. a 512² AO map referenced by a 1024 standard tier, or
a 16² placeholder AO in a 4096 hero tier), the builder writes an
upsampled sibling alongside the original (LANCZOS resample) named
`<source>__upsampled<tier_res>.png` and points the manifest at the
upsampled file. Originals are preserved. If a source is *larger* than
the tier, raise — this means the catalog put a high-res file in a
low-res tier, which is probably a misconfiguration.

Usage:
    python build_biome_arrays.py \\
        --catalog "<path>/biome_catalog.json" \\
        --w4-root "<path>/the world 4" \\
        --out "<path>/arrays/layer_manifest.json"
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from PIL import Image

import biome_catalog as bc


class BuildError(RuntimeError):
    pass


def _ensure_resolution(file_path: Path, target_res: int) -> Path:
    """Return the path of a PNG at target_res, in RGB mode (so all layers
    in a Texture2DArray share format=RGB8/RGBA8, not mixed L/RGB which
    breaks Godot's Texture2DArray.create_from_images).

    If the file is already at target_res AND in an acceptable mode
    (RGB or RGBA), return as-is. If smaller OR single-channel L, write
    a converted+upsampled sibling and return that. If larger, raise."""
    with Image.open(file_path) as im:
        w, h = im.size
        mode = im.mode
    needs_upsample = (w, h) != (target_res, target_res)
    needs_convert = mode not in ("RGB", "RGBA")
    if not needs_upsample and not needs_convert:
        return file_path
    if w > target_res or h > target_res:
        raise BuildError(
            f"resolution mismatch in {file_path}: expected "
            f"{target_res}x{target_res}, got {w}x{h} (larger than tier — "
            f"misconfigured catalog or wrong tier)")
    suffix_bits: list[str] = []
    if needs_upsample:
        suffix_bits.append(f"upsampled{target_res}")
    if needs_convert:
        suffix_bits.append("rgb")
    suffix = "_".join(suffix_bits)
    out_path = file_path.with_name(
        f"{file_path.stem}__{suffix}{file_path.suffix}")
    # Cache check: if the sibling already exists at correct size+mode, reuse.
    if out_path.is_file():
        with Image.open(out_path) as im2:
            if im2.size == (target_res, target_res) and im2.mode in ("RGB", "RGBA"):
                return out_path
    with Image.open(file_path) as im:
        if needs_upsample:
            im = im.resize((target_res, target_res), Image.LANCZOS)
        if needs_convert:
            im = im.convert("RGB")
        im.save(out_path)
    print(f"  {file_path.name} ({w}x{h} {mode}) -> {out_path.name} ({target_res}x{target_res} RGB)")
    return out_path


def build_manifest(cat: bc.Catalog, w4_root: Path | str) -> dict:
    w4 = Path(w4_root)
    tiers_out: dict[str, dict] = {}
    for tier in cat.tiers:
        layers = []
        for biome, slot, tier_name, layer in cat.all_slot_records():
            if tier_name != tier.name:
                continue
            kit_path = w4 / cat.slot_kit_path(biome, slot)
            entry = {"biome": biome, "slot": slot, "layer": layer, "maps": {}}
            for map_name in cat.map_names:
                file_path = kit_path / f"{map_name}.png"
                if not file_path.is_file():
                    raise BuildError(
                        f"missing PBR map: {file_path} "
                        f"(biome={biome}, slot={slot}, map={map_name})")
                resolved = _ensure_resolution(file_path, tier.resolution)
                rel = resolved.relative_to(w4).as_posix()
                entry["maps"][map_name] = rel
            layers.append(entry)
        tiers_out[tier.name] = {
            "resolution": tier.resolution,
            "layers": layers,
            # v1 slot pool is the identity map: slot_pool[i] = i.
            # Streaming follow-up: slot_pool[i] points to a layer that may
            # change over time as biomes are paged in/out of the array.
            # Consumers (shader, ScaleWorld) treat the splat's per-channel
            # index as a slot-pool index and look up the actual layer via
            # this map. v1 = pass-through; semantics gain meaning later.
            "slot_pool": list(range(len(layers))),
        }
    return {
        "schema_version": 1,
        "tiers": tiers_out,
    }


def write_manifest(manifest: dict, out_path: Path | str) -> None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2) + "\n",
                   encoding="utf-8", newline="\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--w4-root", required=True,
                    help="Path to the Godot project root ('the world 4')")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cat = bc.load_catalog(args.catalog)
    m = build_manifest(cat, w4_root=args.w4_root)
    write_manifest(m, args.out)
    n = sum(len(t["layers"]) for t in m["tiers"].values())
    print(f"wrote {args.out}  ({n} layers across {len(m['tiers'])} tiers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
