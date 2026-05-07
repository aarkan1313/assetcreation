"""DepthAnything-V2 + GeoWizard depth/normal helper.

Dry-run/default mode writes a plan JSON. Real mode is a ComfyUI workflow call
after custom nodes and GPU time are available.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ASSETS = Path(r"D:\assets")
sys.path.insert(0, str(ASSETS))

from pipelines._meta.comfy_runner import ComfyError, ComfyRunner  # noqa: E402


DEFAULT_WORKFLOW = ASSETS / "pipelines" / "_meta" / "comfy_workflows" / "depthanything_v2_normal.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--host", default="http://127.0.0.1:8188")
    ap.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    ap.add_argument("--depth-node", default="4")
    ap.add_argument("--normal-node", default="5")
    ap.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    ap.add_argument("--run-model", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    dry_run = args.dry_run or args.device == "cpu" or not args.run_model
    args.out_dir.mkdir(parents=True, exist_ok=True)
    plan_path = args.out_dir / "depth_normal_plan.json"
    plan = {
        "schema": "depth_normal.plan.v1",
        "backend": "comfy_depthanything_geowizard",
        "models": ["depth-anything/Depth-Anything-V2-Large-hf", "fuxiao0719/GeoWizard"],
        "input": str(args.input),
        "out_dir": str(args.out_dir),
        "workflow": str(args.workflow),
        "output_nodes": [args.depth_node, args.normal_node],
        "required_custom_nodes": ["ComfyUI-DepthAnythingV2", "GeoWizard normal/depth node pack"],
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if dry_run:
        runner_plan = ComfyRunner(args.host).run(
            workflow_path=args.workflow,
            overrides={"1.inputs.image": args.input.name},
            output_node_ids=[args.depth_node, args.normal_node],
            dry_run=True,
        )
        plan["comfy_runner_plan"] = asdict(runner_plan)
        plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        print(f"[depth_normal] dry-run plan -> {plan_path}")
        print(f"[depth_normal] workflow_nodes={runner_plan.node_count}; no ComfyUI call")
        return 0
    if not args.input.exists():
        print(f"[depth_normal] missing input: {args.input}", file=sys.stderr)
        return 1
    try:
        runner = ComfyRunner(args.host)
        comfy_name = runner.upload_image(args.input, name=f"phase9_depth_{args.input.name}")
        result = runner.run(
            workflow_path=args.workflow,
            overrides={
                "1.inputs.image": comfy_name,
                "4.inputs.filename_prefix": "depth",
                "5.inputs.filename_prefix": "normal",
            },
            output_node_ids=[args.depth_node, args.normal_node],
            out_dir=args.out_dir / "_comfy_raw",
            dry_run=False,
            validate_nodes=True,
            timeout_s=600.0,
            poll_s=1.5,
        )
    except (ComfyError, OSError) as exc:
        print(f"[depth_normal] failed: {exc}", file=sys.stderr)
        return 1
    plan["comfy_result"] = asdict(result)
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"[depth_normal] Comfy outputs -> {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
