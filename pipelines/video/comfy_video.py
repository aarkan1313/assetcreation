"""ComfyUI video-generation lane for Wan 2.5/compatible workflows.

Default mode writes a plan JSON and does not contact ComfyUI. Real generation
is gated by:

  --device cuda --run-model

The generated video is intended as source for animated UI elements, VFX motion
reference, cinematic stingers, and NPC idle concepts. Use flipbook_extract.py
after a real run to convert frames into sprite sheets.
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


DEFAULT_WORKFLOW = ASSETS / "pipelines" / "_meta" / "comfy_workflows" / "wan_t2v_5s_720p.json"
VIDEO_ROOT = ASSETS / "video" / "runs"


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    frames = max(1, int(round(args.duration * args.fps)))
    return {
        "schema": "comfy_video.plan.v1",
        "id": args.id,
        "backend": "comfy_wan_video",
        "model": args.model,
        "license": "Apache-2.0 or compatible Wan model license; verify exact checkpoint before shipping.",
        "workflow": str(args.workflow),
        "host": args.host,
        "output_node": args.output_node,
        "prompt": args.prompt,
        "negative_prompt": args.negative_prompt,
        "seed": args.seed,
        "duration_s": args.duration,
        "fps": args.fps,
        "frames": frames,
        "width": args.width,
        "height": args.height,
        "steps": args.steps,
        "required_custom_nodes": ["ComfyUI-WanVideoWrapper or compatible Wan video nodes"],
        "overrides": {
            "1.inputs.prompt": args.prompt,
            "1.inputs.negative_prompt": args.negative_prompt,
            "2.inputs.model": args.model,
            "2.inputs.seed": args.seed,
            "2.inputs.steps": args.steps,
            "2.inputs.width": args.width,
            "2.inputs.height": args.height,
            "2.inputs.fps": args.fps,
            "2.inputs.frames": frames,
            "3.inputs.filename_prefix": args.id,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def write_plan(out_dir: Path, plan: dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "video_plan.json"
    path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--negative-prompt", default="text, watermark, logo, harsh flicker, low quality")
    ap.add_argument("--model", default="Wan-AI/Wan2.5-T2V")
    ap.add_argument("--duration", type=float, default=5.0)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    ap.add_argument("--run-model", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--host", default="http://127.0.0.1:8188")
    ap.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    ap.add_argument("--output-node", default="3")
    ap.add_argument("--out-root", type=Path, default=VIDEO_ROOT)
    args = ap.parse_args()

    if args.run_model and args.device != "cuda":
        print("[comfy_video] --run-model requires --device cuda", file=sys.stderr)
        return 2

    out_dir = args.out_root / args.id
    plan = build_plan(args)
    plan_path = write_plan(out_dir, plan)
    dry_run = args.dry_run or args.device == "cpu" or not args.run_model
    if dry_run:
        runner_plan = ComfyRunner(args.host).run(
            workflow_path=args.workflow,
            overrides=plan["overrides"],
            output_node_ids=[args.output_node],
            dry_run=True,
        )
        (out_dir / "comfy_runner_plan.json").write_text(
            json.dumps(asdict(runner_plan), indent=2),
            encoding="utf-8",
        )
        print(f"[comfy_video] dry-run plan -> {plan_path}")
        print(f"[comfy_video] workflow_nodes={runner_plan.node_count} frames={plan['frames']}; no ComfyUI call")
        return 0

    runner = ComfyRunner(args.host)
    try:
        result = runner.run(
            workflow_path=args.workflow,
            overrides=plan["overrides"],
            output_node_ids=[args.output_node],
            out_dir=out_dir / "_comfy_raw",
            dry_run=False,
            validate_nodes=True,
            timeout_s=3600.0,
            poll_s=3.0,
        )
    except (ComfyError, OSError) as exc:
        print(f"[comfy_video] failed: {exc}", file=sys.stderr)
        return 1
    if result.downloaded:
        src = Path(result.downloaded[0].local_path)
        final = out_dir / f"{args.id}{src.suffix or '.mp4'}"
        shutil.copyfile(src, final)
        plan["video_path"] = str(final)
    (out_dir / "comfy_result.json").write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
    (out_dir / "video_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"[comfy_video] outputs -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
