"""Build-only Trellis2 prop route.

The 5090 is busy, so this adapter is deliberately dry-run friendly. The CPU
path validates inputs and writes a prop_asset.v1-shaped manifest under
world/props/ai_routes/trellis2/<id>/ without importing or loading Trellis2.

Actual model loading is gated behind both:
  --device cuda
  --run-model

The CUDA path is scaffolded so the next chat can wire the local Trellis2 entry
point without rediscovering CLI parameters or output contracts.
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
DEFAULT_ROUTE_OUT = ASSETS / "world" / "props" / "ai_routes" / "trellis2"
PUBLISH_LIBRARY = ASSETS / "world" / "props" / "library"
TRELLIS2_ROOT = ASSETS / "animators" / "Trellis2"


def prop_manifest(
    *,
    prop_id: str,
    image: Path,
    family: str,
    render_class: str,
    collision: str,
    target_tris: int,
    status: str,
) -> dict[str, Any]:
    return {
        "schema": "prop_asset.v1",
        "id": prop_id,
        "family": family,
        "kit": "ai_hero_props",
        "source_method": "trellis2_local_image_to_3d",
        "source_image": str(image),
        "license": "project_input_plus_trellis2_output_review_required",
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
        "material_slots": ["generated_pbr"],
        "qa": "qa.json",
        "generation_status": status,
        "route": {
            "adapter": "pipelines/props/trellis2_route.py",
            "model_root": str(TRELLIS2_ROOT),
            "runtime_gate": "--device cuda --run-model",
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
        },
    }


class Trellis2Adapter:
    def __init__(self, root: Path = TRELLIS2_ROOT) -> None:
        self.root = root
        self.python = root / "venv" / "Scripts" / "python.exe"

    def available(self) -> bool:
        return self.root.exists() and self.python.exists()

    def generate(self, image: Path, out_glb: Path, *, seed: int, target_tris: int) -> None:
        """CUDA-only model call scaffold.

        The exact Trellis2 entry script varies by checkout. The adapter accepts
        TRELLIS2_PROP_CMD as an override so the next chat can point at the
        known-good local command without changing this contract.
        """
        cmd_template = os.environ.get("TRELLIS2_PROP_CMD")
        if not cmd_template:
            raise RuntimeError(
                "TRELLIS2_PROP_CMD is not set. Set it to the local Trellis2 image-to-3D command "
                "with placeholders {image}, {out_glb}, {seed}, {target_tris}."
            )
        cmd = cmd_template.format(
            image=str(image),
            out_glb=str(out_glb),
            seed=seed,
            target_tris=target_tris,
        )
        result = subprocess.run(cmd, shell=True)
        if result.returncode != 0:
            raise RuntimeError(f"Trellis2 command failed with exit {result.returncode}")
        if not out_glb.exists():
            raise RuntimeError(f"Trellis2 command did not produce {out_glb}")


def write_route_manifest(out_dir: Path, manifest: dict[str, Any], image: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "source").mkdir(exist_ok=True)
    if image.exists():
        shutil.copyfile(image, out_dir / "source" / image.name)
    (out_dir / "prop.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    qa = {
        "schema": "trellis2_route_qa.v1",
        "ok": True,
        "status": manifest["generation_status"],
        "image_exists": image.exists(),
        "wrote_manifest": True,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (out_dir / "qa.json").write_text(json.dumps(qa, indent=2), encoding="utf-8")


def _run_via_batch_runner(*, image: Path, out_dir: Path, preset: str) -> int:
    """Shell out to Trellis2's venv to run trellis2_batch.py for this single image.

    The route adapter (this file) lives in D:\\assets and is meant to be invoked
    from any python (orchestrators, tests, ComfyUI nodes). The actual model
    inference must run inside the Trellis2 venv. We bridge those by invoking
    that venv's python with `pipelines/props/trellis2_batch.py --concepts ...
    --preset ...`.
    """
    venv_py = TRELLIS2_ROOT / "venv" / "Scripts" / "python.exe"
    if not venv_py.exists():
        raise RuntimeError(f"Trellis2 venv python not found at {venv_py}")
    out_root = out_dir.parent
    cmd = [
        str(venv_py),
        str(ASSETS / "pipelines" / "props" / "trellis2_batch.py"),
        "--concepts", str(image),
        "--preset", preset,
        "--out-root", str(out_root),
    ]
    print(f"[trellis2_route] $ {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=Path)
    ap.add_argument("--id", required=True)
    ap.add_argument("--family", default="hero_prop")
    ap.add_argument("--render-class", default="hero_prop",
                    choices=("hero_prop", "scene_prop", "scatter_multimesh"))
    ap.add_argument("--collision", default="convex")
    ap.add_argument("--target-tris", type=int, default=8000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    ap.add_argument("--run-model", action="store_true",
                    help="Actually load/call Trellis2. Requires --device cuda.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Write manifest only. Default when --device cpu.")
    ap.add_argument("--out-root", type=Path, default=DEFAULT_ROUTE_OUT)
    ap.add_argument("--publish", action="store_true",
                    help="Publish actual CUDA output to world/props/library/<id>.")
    ap.add_argument("--preset", default=None,
                    help="Override the dispatcher-picked preset "
                         "(scatter / balanced / hero / hi_tex). When unset, the "
                         "dispatcher chooses based on render_class + has_fine_relief.")
    ap.add_argument("--has-fine-relief", action="store_true",
                    help="Hint to the dispatcher that the concept has carved/engraved detail.")
    ap.add_argument("--polycount-budget-ok", action="store_true",
                    help="Allow the dispatcher to escalate to the 'hero' preset (485k faces).")
    ap.add_argument("--legacy-cmd", action="store_true",
                    help="Use the legacy TRELLIS2_PROP_CMD env-var shell-out path. "
                         "Default is to call pipelines/props/trellis2_batch.py via the Trellis2 venv.")
    args = ap.parse_args()

    if not args.image.exists():
        print(f"[trellis2_route] missing image: {args.image}", file=sys.stderr)
        return 1

    dry_run = args.dry_run or args.device == "cpu" or not args.run_model
    if args.run_model and args.device != "cuda":
        print("[trellis2_route] --run-model requires --device cuda", file=sys.stderr)
        return 2

    # Resolve preset via the dispatcher if not explicitly overridden.
    if args.preset is None:
        # Ensure D:/assets is on sys.path so `pipelines.props.ai_route_dispatch` resolves
        # regardless of where this script is invoked from.
        if str(ASSETS) not in sys.path:
            sys.path.insert(0, str(ASSETS))
        try:
            from pipelines.props.ai_route_dispatch import pick_route, TRELLIS2_PRESETS
            # NB: don't pass prefer_route='trellis2' here. The dispatcher's
            # default IS Trellis2 (Phase 11A); leaving prefer_route=None lets it
            # apply render_class-aware preset selection (scatter / balanced / hero).
            decision = pick_route(
                args.render_class,
                has_fine_relief=args.has_fine_relief,
                hero_polycount_budget_ok=args.polycount_budget_ok,
            )
            if decision.route != "trellis2":
                # Sanity: this CLI is the trellis2_route, so override to trellis2 if
                # the dispatcher picked something else (e.g. caller's flags
                # accidentally triggered HY3D). Use the balanced preset as a safe default.
                print(f"[trellis2_route] dispatcher picked '{decision.route}' but this is "
                      f"the trellis2 route; falling back to TRELLIS2_PRESETS['balanced']",
                      file=sys.stderr)
                from pipelines.props.ai_route_dispatch import TRELLIS2_PRESETS as _T
                decision.settings = _T["balanced"]
            preset_name = next(
                (k for k, v in TRELLIS2_PRESETS.items() if v == decision.settings),
                "balanced",
            )
        except Exception as exc:
            print(f"[trellis2_route] dispatcher import failed ({exc}); using 'balanced'", file=sys.stderr)
            preset_name = "balanced"
    else:
        preset_name = args.preset

    out_dir = (PUBLISH_LIBRARY if args.publish and not dry_run else args.out_root) / args.id
    manifest = prop_manifest(
        prop_id=args.id,
        image=args.image,
        family=args.family,
        render_class=args.render_class,
        collision=args.collision,
        target_tris=args.target_tris,
        status="dry_run" if dry_run else "generated_pending_postprocess",
    )
    manifest["route"]["preset"] = preset_name

    if dry_run:
        write_route_manifest(out_dir, manifest, args.image)
        print(f"[trellis2_route] dry-run manifest -> {out_dir / 'prop.json'}")
        print(f"[trellis2_route] dispatcher preset: {preset_name}")
        print("[trellis2_route] no model import/load performed")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    out_glb = out_dir / "model_lod0.glb"

    if args.legacy_cmd:
        adapter = Trellis2Adapter()
        if not adapter.available():
            print(f"[trellis2_route] Trellis2 venv not found at {adapter.python}", file=sys.stderr)
            return 2
        adapter.generate(args.image, out_glb, seed=args.seed, target_tris=args.target_tris)
    else:
        rc = _run_via_batch_runner(image=args.image, out_dir=out_dir, preset=preset_name)
        if rc != 0:
            print(f"[trellis2_route] batch runner exit {rc}", file=sys.stderr)
            return rc
        if not out_glb.exists():
            print(f"[trellis2_route] batch runner produced no GLB at {out_glb}", file=sys.stderr)
            return 3

    write_route_manifest(out_dir, manifest, args.image)
    print(f"[trellis2_route] generated GLB -> {out_glb}  (preset={preset_name})")
    print("[trellis2_route] next: preprocess/lod_chain/collision/export_godot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

