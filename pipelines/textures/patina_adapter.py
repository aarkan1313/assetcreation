"""PATINA adapter (fal.ai) for image-to-PBR and text-to-material.

Per the SOTA report: PATINA on fal.ai is the most directly aligned 2026 API
for PBR derivation — returns basecolor/normal/roughness/metalness/height
rather than just RGB.

This is a thin wrapper. Set FAL_KEY env var first:
  https://fal.ai/dashboard/keys

Usage:
  python patina_adapter.py --mode image --albedo path.png --id stone_a --category Rock
  python patina_adapter.py --mode text  --prompt "mossy basalt cliff" --id basalt_a
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CATALOG = Path("D:/assets/world/textures/catalog/materials.jsonl")
LIBRARY = Path("D:/assets/world/textures/library")


def need_fal_client():
    try:
        import fal_client  # noqa: F401
    except ImportError:
        raise SystemExit("fal-client not installed; pip install fal-client")
    if not os.environ.get("FAL_KEY"):
        raise SystemExit("Set FAL_KEY env var. Get key at https://fal.ai/dashboard/keys")


def save_url(url: str, dest: Path):
    with urllib.request.urlopen(url) as r, dest.open("wb") as f:
        f.write(r.read())


def run_image_to_maps(albedo_path: Path, asset_id: str, category: str | None):
    import fal_client
    print(f"[patina:image] uploading {albedo_path.name}")
    handle = fal_client.upload_file(str(albedo_path))
    print(f"  uploaded -> {handle}")
    print("  calling fal-ai/patina (image-to-maps)...")
    result = fal_client.subscribe(
        "fal-ai/patina",
        arguments={"image_url": handle},
    )
    out_dir = LIBRARY / asset_id
    out_dir.mkdir(parents=True, exist_ok=True)

    maps = {}
    for key, our_name in [
        ("basecolor", "albedo"),
        ("normal", "normal"),
        ("roughness", "roughness"),
        ("metalness", "metallic"),
        ("height", "height"),
    ]:
        if key in result and isinstance(result[key], dict) and "url" in result[key]:
            ext = Path(result[key]["url"]).suffix or ".png"
            fname = f"{asset_id}_{our_name}{ext}"
            save_url(result[key]["url"], out_dir / fname)
            maps[our_name] = fname
            print(f"  saved {our_name} -> {fname}")

    record = {
        "id": asset_id,
        "source": "patina:image-to-maps",
        "source_image": str(albedo_path),
        "category": category,
        "license": "patina-commercial-api",
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "library_path": str(out_dir.relative_to(Path("D:/assets"))),
        "maps": maps,
        "map_completeness": sorted(maps.keys()),
    }
    CATALOG.parent.mkdir(parents=True, exist_ok=True)
    with CATALOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print(f"  catalog updated for {asset_id}")


def run_text_to_material(prompt: str, asset_id: str):
    import fal_client
    print(f"[patina:text] prompt={prompt!r}")
    print("  calling fal-ai/patina/material...")
    result = fal_client.subscribe(
        "fal-ai/patina/material",
        arguments={"prompt": prompt, "seamless": True},
    )
    out_dir = LIBRARY / asset_id
    out_dir.mkdir(parents=True, exist_ok=True)

    maps = {}
    for key, our_name in [
        ("basecolor", "albedo"),
        ("normal", "normal"),
        ("roughness", "roughness"),
        ("metalness", "metallic"),
        ("height", "height"),
    ]:
        if key in result and isinstance(result[key], dict) and "url" in result[key]:
            ext = Path(result[key]["url"]).suffix or ".png"
            fname = f"{asset_id}_{our_name}{ext}"
            save_url(result[key]["url"], out_dir / fname)
            maps[our_name] = fname
            print(f"  saved {our_name} -> {fname}")

    record = {
        "id": asset_id,
        "source": "patina:text-to-material",
        "prompt": prompt,
        "license": "patina-commercial-api",
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "library_path": str(out_dir.relative_to(Path("D:/assets"))),
        "maps": maps,
        "map_completeness": sorted(maps.keys()),
        "seamless": True,
    }
    CATALOG.parent.mkdir(parents=True, exist_ok=True)
    with CATALOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print(f"  catalog updated for {asset_id}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["image", "text"])
    ap.add_argument("--albedo", type=Path, help="(mode=image) source albedo")
    ap.add_argument("--prompt", type=str, help="(mode=text) text prompt")
    ap.add_argument("--id", required=True)
    ap.add_argument("--category", default=None)
    args = ap.parse_args()

    need_fal_client()

    if args.mode == "image":
        if not args.albedo or not args.albedo.exists():
            raise SystemExit("--albedo required and must exist")
        run_image_to_maps(args.albedo, args.id, args.category)
    else:
        if not args.prompt:
            raise SystemExit("--prompt required for text mode")
        run_text_to_material(args.prompt, args.id)


if __name__ == "__main__":
    main()
