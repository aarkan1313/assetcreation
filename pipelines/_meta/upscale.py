"""Comfy/HAT-L upscale microtool.

This is the Phase 9-owned upscale helper. It does not edit
pipelines/textures/flux_upscale.py; the texture retrofit can call this helper
later from the texture lane.
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


DEFAULT_WORKFLOW = ASSETS / "pipelines" / "_meta" / "comfy_workflows" / "simple_image_upscale.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model-name", default="HAT-L_SRx4_ImageNet-pretrain.pth")
    ap.add_argument("--host", default="http://127.0.0.1:8188")
    ap.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    ap.add_argument("--output-node", default="4")
    ap.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    ap.add_argument("--run-model", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    dry_run = args.dry_run or args.device == "cpu" or not args.run_model
    plan = {
        "schema": "upscale_microtool.plan.v1",
        "backend": "comfy_hat_l_upscale",
        "model_name": args.model_name,
        "input": str(args.input),
        "out": str(args.out),
        "workflow": str(args.workflow),
        "output_node": args.output_node,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    plan_path = args.out.with_suffix(".upscale_plan.json")
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        runner_plan = ComfyRunner(args.host).run(
            workflow_path=args.workflow,
            overrides={"1.inputs.image": args.input.name, "2.inputs.model_name": args.model_name},
            output_node_ids=[args.output_node],
            dry_run=True,
        )
        plan["comfy_runner_plan"] = asdict(runner_plan)
        plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        print(f"[upscale] dry-run plan -> {plan_path}")
        print(f"[upscale] workflow_nodes={runner_plan.node_count}; no ComfyUI call")
        return 0
    if not args.input.exists():
        print(f"[upscale] missing input: {args.input}", file=sys.stderr)
        return 1
    try:
        runner = ComfyRunner(args.host)
        comfy_name = runner.upload_image(args.input, name=f"phase9_upscale_{args.input.name}")
        result = runner.run(
            workflow_path=args.workflow,
            overrides={
                "1.inputs.image": comfy_name,
                "2.inputs.model_name": args.model_name,
                "4.inputs.filename_prefix": args.out.stem,
            },
            output_node_ids=[args.output_node],
            out_dir=args.out.parent / "_comfy_raw" / args.out.stem,
            dry_run=False,
            validate_nodes=True,
            timeout_s=600.0,
            poll_s=1.5,
        )
    except (ComfyError, OSError) as exc:
        print(f"[upscale] failed: {exc}", file=sys.stderr)
        return 1
    plan["comfy_result"] = asdict(result)
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"[upscale] Comfy outputs -> {args.out.parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
