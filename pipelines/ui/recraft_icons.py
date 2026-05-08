"""Recraft V3 icon generator.

Per research D §1: Recraft V3 is the strongest 2026 cloud option for set-style
consistency (explicit "icon" / "vector_illustration" image types, optional
style references via `style_id`, supports SVG output, cleanest commercial
license).

Gated on `RECRAFT_API_KEY`. Mirrors `openai_icons.py` shape exactly so the
rest of the pipeline (pack_atlas, export_godot, preview_grid) consumes its
output unchanged.

Endpoint: POST https://external.api.recraft.ai/v1/images/generations
Docs:    https://www.recraft.ai/docs

Output: PNG files at the requested size. If `--svg` is passed, the source
SVG is also saved to `ui/icons/svg/<id>.svg` and rasterized to PNG via the
freelib_ingest rasterizer chain (resvg-py preferred). The manifest entry
records both paths.

CLI:
  # Quick set-of-2 smoke test (requires RECRAFT_API_KEY)
  python recraft_icons.py --prompts ui/prompts.json --size 1024
  # Set-style consistency via style_id
  python recraft_icons.py --prompts ui/prompts.json --style-id <UUID>
  # SVG output (vector lane)
  python recraft_icons.py --prompts ui/prompts.json --style vector_illustration --svg
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

import requests

# Reuse the rasterizer chain we built for freelib (resvg-py / cairosvg / PIL).
sys.path.insert(0, str(Path(__file__).parent))
try:
    from freelib_ingest import rasterize as _svg_rasterize  # type: ignore
except Exception:  # noqa: BLE001 - svg fallback handled below
    _svg_rasterize = None


ENDPOINT = "https://external.api.recraft.ai/v1/images/generations"

ICONS_DIR = Path(r"D:\assets\ui\icons")
SVG_DIR = ICONS_DIR / "svg"

STYLE_BRIEF = (
    "centered single subject, fantasy game icon, dark thin outline, muted "
    "earthy palette with one accent color, transparent background, no text, "
    "no watermark, reads clearly at 64x64 px"
)


def _has_key() -> tuple[bool, str | None]:
    if not os.environ.get("RECRAFT_API_KEY"):
        return False, "RECRAFT_API_KEY not set"
    return True, None


def generate_one(prompt: str, *, size: int = 1024,
                 model: str = "recraftv3",
                 style: str = "icon",
                 substyle: str | None = None,
                 style_id: str | None = None,
                 svg: bool = False,
                 timeout_s: float = 90.0) -> dict:
    """Returns a dict with keys 'png' (bytes), optionally 'svg' (bytes), and
    'meta' (free-form dict from the API response)."""
    ok, reason = _has_key()
    if not ok:
        raise RuntimeError(f"recraft_icons: {reason}")
    headers = {
        "Authorization": f"Bearer {os.environ['RECRAFT_API_KEY']}",
        "Content-Type": "application/json",
    }
    full_prompt = f"{prompt}. {STYLE_BRIEF}"
    s_str = f"{size}x{size}"
    payload: dict = {
        "model": model,
        "prompt": full_prompt,
        "size": s_str,
        "n": 1,
        "response_format": "b64_json",
    }
    # Recraft uses `style` for high-level type, `substyle` for sub-style,
    # and `style_id` (UUID) for user-trained / pinned styles.
    if svg:
        # Vector lane: ask the model to return SVG. style must be a vector type.
        payload["style"] = style if style.startswith("vector") else "vector_illustration"
        # Recraft returns SVG via the same b64 channel for vector models.
    else:
        payload["style"] = style
    if substyle:
        payload["substyle"] = substyle
    if style_id:
        payload["style_id"] = style_id

    r = requests.post(ENDPOINT, json=payload, headers=headers, timeout=timeout_s)
    if r.status_code != 200:
        raise RuntimeError(f"recraft_icons: HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    item = data["data"][0]
    out: dict = {"meta": data}
    raw = base64.b64decode(item["b64_json"])
    if svg or raw[:200].lstrip().startswith(b"<svg"):
        out["svg"] = raw
        if _svg_rasterize is None:
            raise RuntimeError(
                "recraft_icons: SVG returned but no rasterizer available. "
                "pip install resvg-py.")
        out["png"] = _svg_rasterize(raw, size)
    else:
        out["png"] = raw
    return out


def generate_batch(specs: list[dict], out_dir: Path, *, size: int = 1024,
                   model: str = "recraftv3",
                   style: str = "icon",
                   substyle: str | None = None,
                   style_id: str | None = None,
                   svg: bool = False,
                   throttle_s: float = 0.5) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    if svg:
        SVG_DIR.mkdir(parents=True, exist_ok=True)
    icons = []
    for spec in specs:
        sid = spec["id"]
        prompt = spec["prompt"]
        result = generate_one(prompt, size=size, model=model, style=style,
                              substyle=substyle, style_id=style_id, svg=svg)
        png_path = out_dir / f"{sid}.png"
        png_path.write_bytes(result["png"])
        entry = {
            "id": sid,
            "path": str(png_path.relative_to(Path(r"D:\assets")).as_posix()),
            "size_px": size,
            "backend": f"recraft_{model.replace('-', '_')}",
            "model": model,
            "prompt": prompt,
            "style": style,
            "license": "Recraft commercial use (user owns generations)",
            "attribution": None,
        }
        if substyle:
            entry["substyle"] = substyle
        if style_id:
            entry["style_id"] = style_id
        if svg and "svg" in result:
            svg_path = SVG_DIR / f"{sid}.svg"
            svg_path.write_bytes(result["svg"])
            entry["svg_path"] = str(svg_path.relative_to(Path(r"D:\assets")).as_posix())
        icons.append(entry)
        print(f"[recraft_icons] {sid:24s} {style}{'+svg' if svg else ''} -> {png_path.name}")
        if throttle_s > 0:
            time.sleep(throttle_s)
    return icons


def merge_into_manifest(manifest_path: Path, new_icons: list[dict],
                        size: int) -> None:
    if manifest_path.exists():
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        m = {"set": "recraft", "size": size, "icons": []}
    by_id = {e["id"]: e for e in m.get("icons", [])}
    for e in new_icons:
        by_id[e["id"]] = e
    m["icons"] = sorted(by_id.values(), key=lambda x: x["id"])
    m["size"] = size
    manifest_path.write_text(json.dumps(m, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", type=Path, required=True,
                    help="JSON list of {id, prompt} objects.")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--style", default="icon",
                    choices=["icon", "vector_illustration", "digital_illustration",
                             "realistic_image"])
    ap.add_argument("--substyle", default=None,
                    help="Optional Recraft substyle (e.g. 'pixel_art', 'flat_art').")
    ap.add_argument("--style-id", default=None,
                    help="Optional Recraft style UUID for set-style consistency.")
    ap.add_argument("--svg", action="store_true",
                    help="Request SVG output (vector lane). PNG is rasterized via resvg-py.")
    ap.add_argument("--model", default="recraftv3",
                    choices=["recraftv3", "recraftv4", "recraftv4-pro-vector"],
                    help="Recraft model. recraftv3 (default; existing behavior). "
                         "recraftv4 (Feb 2026 ground-up rebuild, $0.04/raster, $0.08/vector, "
                         "explicit icon-grid logic + consistent stroke widths per brief #07). "
                         "recraftv4-pro-vector ($0.30/SVG, finest paths, recommended for "
                         "hero-icon pass per brief #07 — ~$9 for 30 hero icons). "
                         "Verify exact API model id via Recraft docs before run; this CLI "
                         "exposes the toggle but the API key gate still blocks unauthorized spend.")
    ap.add_argument("--out", type=Path, default=ICONS_DIR)
    ap.add_argument("--throttle", type=float, default=0.5,
                    help="Seconds to wait between API calls.")
    args = ap.parse_args()

    ok, reason = _has_key()
    if not ok:
        print(f"[recraft_icons] SKIPPED: {reason}", file=sys.stderr)
        print("[recraft_icons] Set RECRAFT_API_KEY in user env to enable. "
              "See CLOUD_KEYS.md.", file=sys.stderr)
        return 2

    specs = json.loads(args.prompts.read_text(encoding="utf-8"))
    if not isinstance(specs, list):
        raise SystemExit("--prompts must be a JSON array of {id, prompt}")

    icons = generate_batch(
        specs, args.out, size=args.size, model=args.model, style=args.style,
        substyle=args.substyle, style_id=args.style_id, svg=args.svg,
        throttle_s=args.throttle,
    )
    manifest = args.out / "manifest.json"
    merge_into_manifest(manifest, icons, size=args.size)
    print(f"[recraft_icons] {len(icons)} icons -> {args.out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
