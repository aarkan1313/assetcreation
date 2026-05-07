"""Extract an image sequence into a flipbook sprite sheet.

This is CPU-only. It expects a directory of already-extracted frames
(`frame_0001.png`, etc.). Video decoding is intentionally left to ffmpeg or the
Comfy video wrapper so this script stays small and deterministic.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def collect_frames(frames_dir: Path, pattern: str) -> list[Path]:
    frames = sorted(frames_dir.glob(pattern))
    return [p for p in frames if p.is_file()]


def dry_run(args: argparse.Namespace) -> int:
    frames = collect_frames(args.frames_dir, args.pattern) if args.frames_dir.exists() else []
    plan = {
        "schema": "flipbook_extract.plan.v1",
        "frames_dir": str(args.frames_dir),
        "pattern": args.pattern,
        "frame_count": len(frames),
        "cols": args.cols,
        "rows": math.ceil(len(frames) / args.cols) if frames and args.cols > 0 else 0,
        "out": str(args.out),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dry_run": True,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"[flipbook_extract] dry-run frames={len(frames)} -> {args.manifest}")
    return 0


def build_flipbook(args: argparse.Namespace) -> int:
    try:
        from PIL import Image
    except ImportError:
        print("[flipbook_extract] Pillow is required for real extraction; use --dry-run for planning")
        return 2

    frames = collect_frames(args.frames_dir, args.pattern)
    if not frames:
        print(f"[flipbook_extract] no frames found in {args.frames_dir} matching {args.pattern}")
        return 1

    images = [Image.open(path).convert("RGBA") for path in frames]
    width, height = images[0].size
    for path, img in zip(frames, images):
        if img.size != (width, height):
            print(f"[flipbook_extract] frame size mismatch: {path} {img.size} != {(width, height)}")
            return 1

    cols = args.cols if args.cols > 0 else math.ceil(math.sqrt(len(images)))
    rows = math.ceil(len(images) / cols)
    sheet = Image.new("RGBA", (cols * width, rows * height), (0, 0, 0, 0))
    for idx, img in enumerate(images):
        x = (idx % cols) * width
        y = (idx // cols) * height
        sheet.paste(img, (x, y))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.out)
    manifest = {
        "schema": "flipbook_extract.manifest.v1",
        "frames_dir": str(args.frames_dir),
        "pattern": args.pattern,
        "frame_count": len(frames),
        "frame_width": width,
        "frame_height": height,
        "cols": cols,
        "rows": rows,
        "sheet": str(args.out),
        "fps": args.fps,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[flipbook_extract] {len(frames)} frames -> {args.out} ({cols}x{rows})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames-dir", type=Path, required=True)
    ap.add_argument("--pattern", default="*.png")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, default=Path("flipbook_manifest.json"))
    ap.add_argument("--cols", type=int, default=0, help="0 = square-ish automatic layout")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.dry_run:
        return dry_run(args)
    return build_flipbook(args)


if __name__ == "__main__":
    raise SystemExit(main())
