"""Submit an image to Meshy image-to-3D, poll until done, download the GLB.

Usage:
    python meshy_image_to_3d.py <image_path> [--name NAME]

Output:
    D:\\assets\\meshy\\output\\<name>\\model.glb
    D:\\assets\\meshy\\output\\<name>\\task.json
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).parent
CONFIG = json.loads((ROOT / "config.json").read_text())
OUTPUT_DIR = ROOT / "output"


def image_to_data_uri(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    if mime not in ("image/png", "image/jpeg"):
        raise SystemExit(f"image must be PNG or JPG, got: {mime}")
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def submit(image_path: Path, overrides: dict | None = None) -> str:
    headers = {"Authorization": f"Bearer {CONFIG['api_key']}"}
    body = {
        "image_url": image_to_data_uri(image_path),
        **CONFIG["defaults"],
        **(overrides or {}),
    }
    r = requests.post(
        f"{CONFIG['base_url']}/openapi/v1/image-to-3d",
        headers=headers,
        json=body,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["result"]


def poll(task_id: str) -> dict:
    headers = {"Authorization": f"Bearer {CONFIG['api_key']}"}
    url = f"{CONFIG['base_url']}/openapi/v1/image-to-3d/{task_id}"
    last_progress = -1
    while True:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        task = r.json()
        status = task.get("status")
        progress = task.get("progress", 0)
        if progress != last_progress:
            print(f"  [{status}] {progress}%")
            last_progress = progress
        if status in ("SUCCEEDED", "FAILED", "CANCELED"):
            return task
        time.sleep(5)


def download_glb(task: dict, dest: Path) -> Path:
    glb_url = (task.get("model_urls") or {}).get("glb")
    if not glb_url:
        raise SystemExit(f"no glb in model_urls: {task.get('model_urls')}")
    r = requests.get(glb_url, timeout=120)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=Path)
    ap.add_argument("--name", help="output folder name (default: image stem)")
    ap.add_argument("--pose", choices=["t-pose", "a-pose", "none"], help="override pose_mode; 'none' clears it")
    ap.add_argument("--symmetry", choices=["off", "auto", "on"], help="override symmetry_mode")
    ap.add_argument("--texture-prompt", help="text guidance for texturing (max 600 chars)")
    args = ap.parse_args()

    if not args.image.exists():
        raise SystemExit(f"image not found: {args.image}")

    name = args.name or args.image.stem
    out_dir = OUTPUT_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)

    overrides = {}
    if args.pose is not None:
        overrides["pose_mode"] = "" if args.pose == "none" else args.pose
    if args.symmetry is not None:
        overrides["symmetry_mode"] = args.symmetry
    if args.texture_prompt:
        overrides["texture_prompt"] = args.texture_prompt

    print(f"submitting {args.image.name} as '{name}'...")
    if overrides:
        print(f"  overrides: {overrides}")
    task_id = submit(args.image, overrides)
    print(f"  task id: {task_id}")

    task = poll(task_id)
    (out_dir / "task.json").write_text(json.dumps(task, indent=2))

    if task.get("status") != "SUCCEEDED":
        print(f"task did not succeed: {task.get('status')}", file=sys.stderr)
        print(json.dumps(task.get("task_error") or {}, indent=2), file=sys.stderr)
        sys.exit(1)

    glb_path = download_glb(task, out_dir / "model.glb")
    credits = task.get("consumed_credits")
    print(f"downloaded: {glb_path}")
    if credits is not None:
        print(f"credits used: {credits}")
    print(str(glb_path))


if __name__ == "__main__":
    main()
