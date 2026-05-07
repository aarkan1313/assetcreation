"""Hero-prop concept image generator (OpenAI gpt-image-1 backend).

Generates a single 1024x1024 PNG suitable as the *input image* to image-to-3D
pipelines (Hunyuan3D-2.5 / Trellis2 / Meshy). The style brief is tuned for what
those models actually want:
  - single centered subject, fills 70-80% of frame
  - clean three-quarter ("hero") view at slight downward angle
  - solid white background (NOT transparent — diffusion-to-3D collapses on alpha edges)
  - even soft frontal+top lighting, no harsh shadows under the prop
  - matte / unlit reading so the model isn't fooled by baked highlights
  - no ground shadows, no text, no captions, no watermarks
  - no cropping at the silhouette edge

Gated on OPENAI_API_KEY. Falls back with a clear non-zero exit if missing.

CLI:
  # Single concept
  python concept_gen.py --id ruined_obelisk \
    --prompt "weathered stone obelisk, mossy cracks, glowing rune-etched faces, fantasy ARPG"

  # Batch from JSON (list of {id, prompt})
  python concept_gen.py --prompts D:/tmp/hero_concepts.json

Output:
  D:/assets/world/props/concepts/<id>/source.png
  D:/assets/world/props/concepts/<id>/concept.json   (prompt + provenance)
"""
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Iterable

import requests


ENDPOINT = "https://api.openai.com/v1/images/generations"
DEFAULT_OUT = Path(r"D:\assets\world\props\concepts")

STYLE_BRIEF = (
    "single centered subject filling 75 percent of the frame, three-quarter "
    "hero view at a slight downward angle, solid pure white background, "
    "even soft frontal-and-top studio lighting with no harsh shadows, "
    "matte unlit reading with subtle PBR detail, no ground plane, no shadow "
    "puddle, no text, no caption, no watermark, no logo, no border, "
    "subject silhouette stays well inside the frame with at least 8 percent "
    "padding on every side, photographic clarity, fantasy ARPG prop concept"
)


def _has_key() -> tuple[bool, str | None]:
    if not os.environ.get("OPENAI_API_KEY"):
        return False, "OPENAI_API_KEY not set"
    return True, None


def generate_one(prompt: str, *, size: int = 1024, model: str = "gpt-image-1",
                 quality: str = "high", timeout_s: float = 180.0) -> bytes:
    ok, reason = _has_key()
    if not ok:
        raise RuntimeError(f"concept_gen: {reason}")
    headers = {
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
        "Content-Type": "application/json",
    }
    s = f"{size}x{size}"
    full_prompt = f"{prompt}. {STYLE_BRIEF}"
    payload = {
        "model": model,
        "prompt": full_prompt,
        "size": s,
        "n": 1,
        "quality": quality,
        # Solid white background — NOT transparent. Image-to-3D models like
        # Hunyuan3D / Trellis collapse silhouettes on alpha edges; a flat white
        # bg gives them a clean matte to segment against.
        "background": "opaque",
    }
    r = requests.post(ENDPOINT, json=payload, headers=headers, timeout=timeout_s)
    if r.status_code != 200:
        raise RuntimeError(f"concept_gen: HTTP {r.status_code}: {r.text[:400]}")
    data = r.json()
    b64 = data["data"][0]["b64_json"]
    return base64.b64decode(b64)


def write_concept(prop_id: str, prompt: str, png: bytes, out_root: Path,
                  *, size: int, model: str, quality: str) -> Path:
    out_dir = out_root / prop_id
    out_dir.mkdir(parents=True, exist_ok=True)
    img_path = out_dir / "source.png"
    img_path.write_bytes(png)
    sha = hashlib.sha256(png).hexdigest()[:16]
    meta = {
        "schema": "prop_concept.v1",
        "id": prop_id,
        "prompt": prompt,
        "style_brief": STYLE_BRIEF,
        "backend": "openai_gpt-image-1",
        "model": model,
        "quality": quality,
        "size_px": size,
        "image": "source.png",
        "image_sha256_16": sha,
        "generated_at_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }
    (out_dir / "concept.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return img_path


def generate_batch(specs: Iterable[dict], out_root: Path, *, size: int,
                   model: str, quality: str) -> list[dict]:
    out_root.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    for spec in specs:
        prop_id = spec["id"]
        prompt = spec["prompt"]
        print(f"[concept_gen] generating {prop_id} ...")
        png = generate_one(prompt, size=size, model=model, quality=quality)
        path = write_concept(prop_id, prompt, png, out_root, size=size,
                             model=model, quality=quality)
        results.append({"id": prop_id, "path": str(path), "prompt": prompt})
        print(f"[concept_gen]   wrote {path} ({len(png)//1024} KB)")
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", help="Single concept id (with --prompt).")
    ap.add_argument("--prompt", help="Single concept prompt (with --id).")
    ap.add_argument("--prompts", type=Path,
                    help="JSON array of {id, prompt} for batch mode.")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--model", default="gpt-image-1")
    ap.add_argument("--quality", default="high",
                    help="low | medium | high (gpt-image-1).")
    args = ap.parse_args()

    ok, reason = _has_key()
    if not ok:
        print(f"[concept_gen] SKIPPED: {reason}", file=sys.stderr)
        print("[concept_gen] Set OPENAI_API_KEY in user env to enable.",
              file=sys.stderr)
        return 2

    if args.prompts:
        specs = json.loads(args.prompts.read_text(encoding="utf-8"))
        if not isinstance(specs, list):
            print("--prompts must be a JSON array of {id, prompt}", file=sys.stderr)
            return 2
    elif args.id and args.prompt:
        specs = [{"id": args.id, "prompt": args.prompt}]
    else:
        print("Provide either --id+--prompt or --prompts <file>", file=sys.stderr)
        return 2

    generate_batch(specs, args.out, size=args.size, model=args.model,
                   quality=args.quality)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
