"""Meshy hero-prop adapter with explicit spend authorization gate.

This route mirrors the procedural prop output contract but never calls Meshy
unless the user/session sets:

  MESHY_AUTH_FOR_THIS_BATCH=YES

Dry runs write a prop_asset.v1-shaped manifest under
world/props/ai_routes/meshy/<id>/ so downstream tooling can inspect the shape
without spending credits or touching the network.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ASSETS = Path(r"D:\assets")
MESHY_GENERATE = ASSETS / "meshy" / "generate.py"
MESHY_OUTPUT = ASSETS / "meshy" / "output"
MESHY_PREPROCESS = ASSETS / "meshy" / "preprocess.py"
ROUTE_OUT = ASSETS / "world" / "props" / "ai_routes" / "meshy"
LIBRARY = ASSETS / "world" / "props" / "library"


def authorized() -> bool:
    return os.environ.get("MESHY_AUTH_FOR_THIS_BATCH", "").strip().upper() in {"1", "YES", "TRUE", "AUTHORIZED"}


def manifest_for(
    *,
    prop_id: str,
    image: Path,
    family: str,
    render_class: str,
    collision: str,
    target_tris: int,
    texture_prompt: str | None,
    status: str,
) -> dict[str, Any]:
    return {
        "schema": "prop_asset.v1",
        "id": prop_id,
        "family": family,
        "kit": "ai_hero_props",
        "source_method": "meshy_image_to_3d",
        "source_image": str(image),
        "source_prompt": texture_prompt or "",
        "license": "meshy_output_review_required",
        "render_class": render_class,
        "collision": collision,
        "origin": "bottom_center",
        "scale_m": [1.0, 1.0, 1.0],
        "footprint_radius_m": 0.75,
        "lods": [
            {"file": "model_lod0.glb", "max_distance_m": 25, "triangles": target_tris}
        ],
        "thumbnail": "thumbnail.png",
        "placement_tags": ["ai_prop", family],
        "material_slots": ["meshy_pbr"],
        "qa": "qa.json",
        "generation_status": status,
        "route": {
            "adapter": "pipelines/props/meshy_route.py",
            "spend_gate": "MESHY_AUTH_FOR_THIS_BATCH=YES",
            "cloud_endpoint": "meshy/openapi/v1/image-to-3d via meshy/generate.py",
            "postprocess": [
                "meshy/preprocess.py --target-tris",
                "pipelines/props/lod_chain.py",
                "pipelines/props/collision_decompose.py when collision != none",
                "pipelines/props/billboard_bake.py",
                "pipelines/props/export_godot.py",
            ],
        },
        "provenance": {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "target_tris_hint": target_tris,
            "cloud_spend_authorized": authorized(),
        },
    }


def write_manifest(out_dir: Path, manifest: dict[str, Any], image: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "source").mkdir(exist_ok=True)
    if image.exists():
        shutil.copyfile(image, out_dir / "source" / image.name)
    (out_dir / "prop.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    qa = {
        "schema": "meshy_route_qa.v1",
        "ok": True,
        "status": manifest["generation_status"],
        "image_exists": image.exists(),
        "spend_authorized": authorized(),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (out_dir / "qa.json").write_text(json.dumps(qa, indent=2), encoding="utf-8")


def run_meshy(image: Path, prop_id: str, *, texture_prompt: str | None) -> Path:
    cmd = [sys.executable, str(MESHY_GENERATE), str(image), "--name", prop_id, "--skip-render"]
    if texture_prompt:
        cmd.extend(["--texture-prompt", texture_prompt])
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"meshy/generate.py failed with exit {result.returncode}")
    glb = MESHY_OUTPUT / prop_id / "model.glb"
    if not glb.exists():
        raise RuntimeError(f"Meshy did not produce {glb}")
    return glb


def preprocess(meshy_glb: Path, out_glb: Path, target_tris: int) -> None:
    cmd = [
        sys.executable, str(MESHY_PREPROCESS), str(meshy_glb), str(out_glb),
        "--target-tris", str(target_tris),
        "--normalize-scale",
    ]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"meshy/preprocess.py failed with exit {result.returncode}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=Path)
    ap.add_argument("--id", required=True)
    ap.add_argument("--family", default="hero_prop")
    ap.add_argument("--render-class", default="hero_prop",
                    choices=("hero_prop", "scene_prop", "scatter_multimesh"))
    ap.add_argument("--collision", default="convex")
    ap.add_argument("--target-tris", type=int, default=8000)
    ap.add_argument("--texture-prompt", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--publish", action="store_true",
                    help="Write actual generated prop to world/props/library/<id>.")
    ap.add_argument("--out-root", type=Path, default=ROUTE_OUT)
    args = ap.parse_args()

    if not args.image.exists():
        print(f"[meshy_route] missing image: {args.image}", file=sys.stderr)
        return 1

    dry_run = args.dry_run or not args.publish
    out_dir = (LIBRARY if args.publish and not dry_run else args.out_root) / args.id
    manifest = manifest_for(
        prop_id=args.id,
        image=args.image,
        family=args.family,
        render_class=args.render_class,
        collision=args.collision,
        target_tris=args.target_tris,
        texture_prompt=args.texture_prompt,
        status="dry_run" if dry_run else "generated_pending_lod",
    )

    if dry_run:
        write_manifest(out_dir, manifest, args.image)
        print(f"[meshy_route] dry-run manifest -> {out_dir / 'prop.json'}")
        print("[meshy_route] no cloud call performed")
        return 0

    if not authorized():
        print(
            "[meshy_route] blocked: set MESHY_AUTH_FOR_THIS_BATCH=YES to authorize this paid Meshy batch",
            file=sys.stderr,
        )
        write_manifest(args.out_root / args.id, {**manifest, "generation_status": "blocked_no_spend_auth"}, args.image)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        meshy_glb = run_meshy(args.image, args.id, texture_prompt=args.texture_prompt)
        preprocess(meshy_glb, out_dir / "model_lod0.glb", args.target_tris)
        write_manifest(out_dir, manifest, args.image)
    except Exception as exc:
        print(f"[meshy_route] failed: {exc}", file=sys.stderr)
        return 1
    print(f"[meshy_route] generated -> {out_dir / 'model_lod0.glb'}")
    print("[meshy_route] next: lod_chain/collision/billboard/export_godot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

