"""Biome -> AAA-texture binder.

For a given world output dir:
  1. Read art_lab/biomes/biome_texture_registry.json
  2. For each biome present in this world, ensure its AAA texture set exists in
     the library; if missing, generate it via aaa_texture.py using the registry's
     prompt_seed.
  3. Emit `<world>/biome_pbr_pack.json` summarising:
       - splat channel ordering
       - per-biome path to each PBR map (albedo/normal/roughness/height/ao/metallic)
       - tiling_meters
     This is the single source the Godot terrain shader reads to wire layers.

Usage:
  python biome_texture_bind.py --world D:/assets/world/worlds/qa_fjord_4biome
  python biome_texture_bind.py --world ... --quality fast      # cheaper regen
  python biome_texture_bind.py --world ... --skip-missing      # error instead of generating
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REGISTRY_PATH = Path(r"D:\assets\art_lab\biomes\biome_texture_registry.json")
LIBRARY = Path(r"D:\assets\world\textures\library")
AAA_TEXTURE = Path(r"D:\assets\pipelines\textures\aaa_texture.py")

PBR_CHANNELS = ["albedo", "normal", "roughness", "height", "ao", "metallic"]


def load_registry() -> dict:
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_world(world_dir: Path) -> dict:
    with (world_dir / "world.json").open("r", encoding="utf-8") as f:
        return json.load(f)


def set_paths(set_id: str) -> dict[str, Path]:
    d = LIBRARY / set_id
    return {ch: d / f"{set_id}_{ch}.png" for ch in PBR_CHANNELS}


def set_complete(set_id: str) -> bool:
    paths = set_paths(set_id)
    # require the four core channels; ao+metallic are nice-to-have but optional
    return all(paths[ch].exists() for ch in ("albedo", "normal", "roughness", "height"))


def generate_set(set_id: str, prompt: str, category: str, quality: str) -> None:
    print(f"\n>>> generating AAA texture set: {set_id}")
    print(f"    prompt: {prompt}")
    print(f"    category={category}  quality={quality}")
    cmd = [
        sys.executable, str(AAA_TEXTURE),
        "--prompt", prompt,
        "--id", set_id,
        "--category", category,
        "--quality", quality,
    ]
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        raise RuntimeError(f"aaa_texture.py failed for {set_id} (rc={rc})")


def bind(world_dir: Path, *, quality: str, skip_missing: bool) -> Path:
    registry = load_registry()
    world = load_world(world_dir)

    biomes_in_world = world["biomes"]
    library_root = Path(registry.get("library_root", str(LIBRARY)))

    # Splat channels are scene-position-assigned by biome_splat.py (RGBA = first
    # 4 biomes in world.json's biomes list). Read its manifest for the
    # authoritative letter→biome mapping; fall back to scene-position derivation
    # if the manifest is missing.
    splat_manifest_path = world_dir / "biome_splat.json"
    if splat_manifest_path.exists():
        splat_manifest = json.loads(splat_manifest_path.read_text(encoding="utf-8"))
        biome_to_channel = {bid: ch for ch, bid in splat_manifest.get("channel_to_biome", {}).items()}
    else:
        pos_to_letter = {0: "R", 1: "G", 2: "B", 3: "A"}
        biome_to_channel = {bid: pos_to_letter[i] for i, bid in enumerate(biomes_in_world[:4])}

    pack = {
        "world_id": world["id"],
        "size": world["size"],
        "library_root": str(library_root).replace("\\", "/"),
        "splat": "biome_splat_rgba.png",
        "channel_order": registry["channel_order"],
        "biomes": {},
    }

    for biome_id in biomes_in_world:
        if biome_id not in registry["biomes"]:
            print(f"[warn] biome '{biome_id}' has no registry entry — skipping")
            continue
        entry = registry["biomes"][biome_id]
        set_id = entry["set_id"]

        if not set_complete(set_id):
            if skip_missing:
                raise SystemExit(f"texture set missing for {biome_id} ({set_id}) — pass without --skip-missing to auto-generate")
            generate_set(set_id, entry["prompt_seed"], entry.get("category", "Ground"), quality)
            if not set_complete(set_id):
                raise RuntimeError(f"after generation, set still incomplete: {set_id}")
        else:
            print(f"[ok] {biome_id} -> {set_id} (already in library)")

        paths = set_paths(set_id)
        pack["biomes"][biome_id] = {
            "set_id": set_id,
            "splat_channel": biome_to_channel.get(biome_id, entry.get("splat_channel", "R")),
            "tiling_meters": entry.get("tiling_meters", 4.0),
            "maps": {ch: str(p).replace("\\", "/") for ch, p in paths.items() if p.exists()},
        }

    out_path = world_dir / "biome_pbr_pack.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(pack, f, indent=2)
    print(f"\nwrote {out_path}")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", type=Path, required=True)
    ap.add_argument("--quality", choices=["fast", "default", "strict"], default="default")
    ap.add_argument("--skip-missing", action="store_true",
                    help="error instead of generating any missing texture set")
    args = ap.parse_args()

    if not args.world.is_dir():
        raise SystemExit(f"world dir not found: {args.world}")

    bind(args.world, quality=args.quality, skip_missing=args.skip_missing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
