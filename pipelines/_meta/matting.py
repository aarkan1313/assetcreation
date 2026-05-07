"""BiRefNet matting helper.

Dry-run/default mode writes a plan JSON. Real execution can use a ComfyUI
workflow once the matching custom nodes are installed and the GPU is free.
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


DEFAULT_WORKFLOW = ASSETS / "pipelines" / "_meta" / "comfy_workflows" / "birefnet_remove_bg.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--backend", choices=("comfy",), default="comfy")
    ap.add_argument("--host", default="http://127.0.0.1:8188")
    ap.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    ap.add_argument("--output-node", default="3")
    ap.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    ap.add_argument("--run-model", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    dry_run = args.dry_run or args.device == "cpu" or not args.run_model
    plan = {
        "schema": "matting.plan.v1",
        "backend": "comfy_birefnet",
        "model": "ZhengPeng7/BiRefNet",
        "license": "review model card before shipping batch outputs",
        "input": str(args.input),
        "out": str(args.out),
        "workflow": str(args.workflow),
        "output_node": args.output_node,
        "required_custom_nodes": ["BiRefNet/RMBG ComfyUI matting node pack"],
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    plan_path = args.out.with_suffix(".matting_plan.json")
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        runner_plan = ComfyRunner(args.host).run(
            workflow_path=args.workflow,
            overrides={"1.inputs.image": args.input.name},
            output_node_ids=[args.output_node],
            dry_run=True,
        )
        plan["comfy_runner_plan"] = asdict(runner_plan)
        plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        print(f"[matting] dry-run plan -> {plan_path}")
        print(f"[matting] workflow_nodes={runner_plan.node_count}; no ComfyUI call")
        return 0
    if not args.input.exists():
        print(f"[matting] missing input: {args.input}", file=sys.stderr)
        return 1
    try:
        runner = ComfyRunner(args.host)
        comfy_name = runner.upload_image(args.input, name=f"phase9_matte_{args.input.name}")
        result = runner.run(
            workflow_path=args.workflow,
            overrides={"1.inputs.image": comfy_name, "3.inputs.filename_prefix": args.out.stem},
            output_node_ids=[args.output_node],
            out_dir=args.out.parent / "_comfy_raw" / args.out.stem,
            dry_run=False,
            validate_nodes=True,
            timeout_s=300.0,
            poll_s=1.0,
        )
    except (ComfyError, OSError) as exc:
        print(f"[matting] failed: {exc}", file=sys.stderr)
        return 1
    plan["comfy_result"] = asdict(result)
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"[matting] Comfy outputs -> {args.out.parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
