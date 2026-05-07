"""Hunyuan3D-2.5 ComfyUI prop route.

This is the Phase 9 local/open-weights replacement for the paid Meshy route.
Build-time default is a dry-run manifest; real ComfyUI execution is gated by:

  --device cuda --run-model

The current ComfyUI install has no Hunyuan3D custom nodes yet, so dry-run is
the expected verification mode until ComfyUI-Hunyuan3DWrapper (or equivalent)
is installed and the 5090 is free.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ASSETS = Path(r"D:\assets")
sys.path.insert(0, str(ASSETS))

from pipelines._meta.comfy_runner import ComfyError, ComfyRunner  # noqa: E402


DEFAULT_WORKFLOW = ASSETS / "pipelines" / "_meta" / "comfy_workflows" / "hunyuan3d_21_image_to_glb_geo.json"
TEXTURED_WORKFLOW = ASSETS / "pipelines" / "_meta" / "comfy_workflows" / "hunyuan3d_21_image_to_glb_textured.json"
DEFAULT_ROUTE_OUT = ASSETS / "world" / "props" / "ai_routes" / "hunyuan3d"
PUBLISH_LIBRARY = ASSETS / "world" / "props" / "library"


def prop_manifest(
    *,
    prop_id: str,
    image: Path,
    family: str,
    render_class: str,
    collision: str,
    target_tris: int,
    status: str,
    workflow: Path,
    output_node: str,
    seed: int,
) -> dict[str, Any]:
    return {
        "schema": "prop_asset.v1",
        "id": prop_id,
        "family": family,
        "kit": "ai_hero_props",
        "source_method": "hunyuan3d_25_comfy_image_to_3d",
        "source_image": str(image),
        "license": "project_input_plus_tencent_hunyuan_community_review_required",
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
        "material_slots": ["hunyuan3d_pbr"],
        "qa": "qa.json",
        "generation_status": status,
        "route": {
            "adapter": "pipelines/props/hunyuan3d_route.py",
            "backend": "comfyui",
            "workflow": str(workflow),
            "output_node": output_node,
            "runtime_gate": "--device cuda --run-model",
            "required_custom_nodes": ["ComfyUI-Hunyuan3DWrapper or compatible Hunyuan3D-2.5 nodes"],
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
            "device": "cpu_dry_run" if status == "dry_run" else "cuda",
            "target_tris_hint": target_tris,
            "seed": seed,
            "commercial_license_note": "Tencent Hunyuan community license; verify project scale terms before shipping.",
        },
    }


def write_route_manifest(out_dir: Path, manifest: dict[str, Any], image: Path, qa_extra: dict[str, Any] | None = None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "source").mkdir(exist_ok=True)
    if image.exists():
        shutil.copyfile(image, out_dir / "source" / image.name)
    (out_dir / "prop.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    qa = {
        "schema": "hunyuan3d_route_qa.v1",
        "ok": True,
        "status": manifest["generation_status"],
        "image_exists": image.exists(),
        "wrote_manifest": True,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if qa_extra:
        qa.update(qa_extra)
    (out_dir / "qa.json").write_text(json.dumps(qa, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=Path)
    ap.add_argument("--id", required=True)
    ap.add_argument("--family", default="hero_prop")
    ap.add_argument("--render-class", default="hero_prop",
                    choices=("hero_prop", "scene_prop", "scatter_multimesh"))
    ap.add_argument("--collision", default="convex")
    ap.add_argument("--target-tris", type=int, default=8000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    ap.add_argument("--run-model", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--host", default="http://127.0.0.1:8188")
    ap.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    ap.add_argument("--output-node", default="3")
    ap.add_argument("--out-root", type=Path, default=DEFAULT_ROUTE_OUT)
    ap.add_argument("--publish", action="store_true",
                    help="Publish actual CUDA output to world/props/library/<id>.")
    args = ap.parse_args()

    if not args.image.exists():
        print(f"[hunyuan3d_route] missing image: {args.image}", file=sys.stderr)
        return 1
    if args.run_model and args.device != "cuda":
        print("[hunyuan3d_route] --run-model requires --device cuda", file=sys.stderr)
        return 2

    dry_run = args.dry_run or args.device == "cpu" or not args.run_model
    out_dir = (PUBLISH_LIBRARY if args.publish and not dry_run else args.out_root) / args.id
    manifest = prop_manifest(
        prop_id=args.id,
        image=args.image,
        family=args.family,
        render_class=args.render_class,
        collision=args.collision,
        target_tris=args.target_tris,
        status="dry_run" if dry_run else "generated_pending_postprocess",
        workflow=args.workflow,
        output_node=args.output_node,
        seed=args.seed,
    )

    overrides = {
        "1.inputs.image": args.image.name,
        "2.inputs.seed": args.seed,
        "2.inputs.target_faces": args.target_tris,
    }
    runner = ComfyRunner(args.host)
    if dry_run:
        plan = runner.run(
            workflow_path=args.workflow,
            overrides=overrides,
            output_node_ids=[args.output_node],
            dry_run=True,
        )
        write_route_manifest(out_dir, manifest, args.image, {"comfy_plan": asdict(plan)})
        print(f"[hunyuan3d_route] dry-run manifest -> {out_dir / 'prop.json'}")
        print(f"[hunyuan3d_route] workflow_nodes={plan.node_count} output_node={args.output_node}; no ComfyUI call")
        return 0

    try:
        comfy_name = runner.upload_image(args.image, name=f"{args.id}_{args.image.name}")
        overrides["1.inputs.image"] = comfy_name
        result = runner.run(
            workflow_path=args.workflow,
            overrides=overrides,
            output_node_ids=[args.output_node],
            out_dir=out_dir,
            dry_run=False,
            validate_nodes=True,
            timeout_s=1800.0,
            poll_s=2.0,
        )
    except (ComfyError, OSError) as exc:
        print(f"[hunyuan3d_route] failed: {exc}", file=sys.stderr)
        return 1

    write_route_manifest(out_dir, manifest, args.image, {"comfy_result": asdict(result)})
    print(f"[hunyuan3d_route] Comfy outputs -> {out_dir}")
    print("[hunyuan3d_route] next: preprocess/lod_chain/collision/billboard/export_godot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
