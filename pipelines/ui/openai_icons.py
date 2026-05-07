"""OpenAI Images (gpt-image-1) icon generator.

Gated on OPENAI_API_KEY. Falls back with a clear non-zero exit if missing.

Per `research/D_ui` (recommendation extracted from project notes): cloud route
for higher-quality icons; the local path uses `synth_icons.py`. We strongly
suggest passing a consistent style brief so all icons look like a coherent set.

Endpoint: POST https://api.openai.com/v1/images/generations
Docs:    https://platform.openai.com/docs/api-reference/images/create

Output: PNG files at the requested size, transparent background. Returns the
same manifest shape as `synth_icons.py` so the rest of the pipeline doesn't
care which backend produced the file.

CLI:
  python openai_icons.py --prompts prompts.json --size 1024 --out ui/icons
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Iterable

import requests


ENDPOINT = "https://api.openai.com/v1/images/generations"


STYLE_BRIEF = (
    "centered single subject, flat-shaded fantasy game icon, dark thin "
    "outline, muted earthy palette with one accent color, transparent "
    "background, no text, no watermark, no shadows on the background, "
    "the icon should read clearly at 64x64 px"
)


def _has_key() -> tuple[bool, str | None]:
    if not os.environ.get("OPENAI_API_KEY"):
        return False, "OPENAI_API_KEY not set"
    return True, None


def generate_one(prompt: str, size: int = 1024,
                 model: str = "gpt-image-1",
                 quality: str = "standard",
                 timeout_s: float = 90.0) -> bytes:
    """Returns the PNG bytes."""
    ok, reason = _has_key()
    if not ok:
        raise RuntimeError(f"openai_icons: {reason}")
    headers = {
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
        "Content-Type": "application/json",
    }
    full_prompt = f"{prompt}. {STYLE_BRIEF}"
    # gpt-image-1 supports 1024x1024, 1024x1536, 1536x1024 and "auto"
    s = "1024x1024" if size <= 1024 else f"{size}x{size}"
    payload = {
        "model": model,
        "prompt": full_prompt,
        "size": s,
        "n": 1,
        "background": "transparent",
        "quality": quality,
    }
    r = requests.post(ENDPOINT, json=payload, headers=headers, timeout=timeout_s)
    if r.status_code != 200:
        raise RuntimeError(f"openai_icons: HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    b64 = data["data"][0]["b64_json"]
    return base64.b64decode(b64)


def generate_batch(specs: Iterable[dict], out_dir: Path, size: int = 1024) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    icons = []
    for spec in specs:
        sid = spec["id"]
        prompt = spec["prompt"]
        png = generate_one(prompt, size)
        path = out_dir / f"{sid}.png"
        path.write_bytes(png)
        icons.append({
            "id": sid,
            "path": str(path.relative_to(Path(r"D:\assets")).as_posix()),
            "size_px": size,
            "backend": "openai_images",
            "prompt": prompt,
        })
        print(f"[openai_icons] {sid:18s} -> {path}")
    return icons


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", type=Path, required=True,
                    help="JSON list of {id, prompt} objects.")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--out", type=Path, default=Path(r"D:\assets\ui\icons"))
    args = ap.parse_args()

    ok, reason = _has_key()
    if not ok:
        print(f"[openai_icons] SKIPPED: {reason}", file=sys.stderr)
        print("[openai_icons] Set OPENAI_API_KEY in user env to enable.",
              file=sys.stderr)
        return 2

    specs = json.loads(args.prompts.read_text(encoding="utf-8"))
    if not isinstance(specs, list):
        raise SystemExit("--prompts must be a JSON array of {id, prompt}")

    icons = generate_batch(specs, args.out, args.size)
    manifest = args.out / "manifest.json"
    manifest.write_text(json.dumps({
        "set": "openai",
        "size": args.size,
        "icons": icons,
    }, indent=2))
    print(f"[openai_icons] {len(icons)} icons -> {args.out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
