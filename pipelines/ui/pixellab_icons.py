"""PixelLab pixel-art icon generator (cloud).

Per `research/D_ui.md` §2: PixelLab is the dedicated 2026 winner for true
pixel-art icons (16/32/48/64 px native). Other models (SDXL pixel-art LoRAs)
generate "blurry images of pixel art" — they need an Aseprite-style snap-to-
grid + palette-reduce post-pass. PixelLab nails the style natively.

Mirrors `openai_icons.py` and `recraft_icons.py` exactly so the rest of the
pipeline doesn't care which backend produced the PNG. Output goes into the
same `manifest.json` schema with `backend=pixellab`, plus pixel-art-specific
fields: `pixel_size`, `palette_id`, `outline`.

Endpoint base:  https://api.pixellab.ai/v1
Generate:       POST /generate-image-pixflux  (text-to-pixel-art image)
Docs:           https://api.pixellab.ai/docs

This adapter is **plan-only by default** — `--plan-only` writes a deterministic
JSON of every parameter the API call will use, into
`ui/diffusion_plans/<stem>.pixellab_plan.json`. To actually call the API,
re-run with `--run`. Gated on `PIXELLAB_API_KEY`. The key is reserved in
CLOUD_KEYS.md but not active until a pixel-art region of TLTE exists.

PixelLab pricing (Nov 2025): ~$0.02/image at 64x64. Set `--max-cost-usd` to
cap a run; the adapter exits before any HTTP call when the projected total
would exceed the cap.

Style brief (passed implicitly with every prompt):
  centered single subject, native pixel art, no anti-aliasing, hard outline,
  limited palette, transparent background, reads clearly at native pixel size.

CLI:
  # Plan-only (no key needed; writes a JSON of every API param)
  python pixellab_icons.py --prompts ui/prompts.json --pixel-size 64 \\
        --plan-only

  # Real run (requires PIXELLAB_API_KEY + --max-cost-usd cap)
  python pixellab_icons.py --prompts ui/prompts.json --pixel-size 64 \\
        --run --max-cost-usd 1.50
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ASSETS = Path(r"D:\assets")
ICONS_DIR = ASSETS / "ui" / "icons"
PLAN_DIR = ASSETS / "ui" / "diffusion_plans"

ENDPOINT = "https://api.pixellab.ai/v1/generate-image-pixflux"

# Approx 2025-Q4 list price; checked at run-time only when --run + --max-cost-usd.
APPROX_USD_PER_IMAGE = {
    16: 0.005, 32: 0.010, 48: 0.015, 64: 0.020, 128: 0.040,
}

STYLE_BRIEF = (
    "native pixel art, hard outline, limited palette, transparent "
    "background, centered single subject, no anti-aliasing, reads clearly "
    "at native pixel resolution, no text, no signature"
)

DEFAULT_OUTLINE = "single color black outline"
DEFAULT_SHADING = "flat shading"
DEFAULT_VIEW = "side"


@dataclass
class PixellabPlan:
    icon_id: str
    prompt_user: str
    prompt_full: str
    pixel_size: int
    outline: str
    shading: str
    view: str
    palette_id: Optional[str]
    seed: Optional[int]
    style_id: Optional[str]
    transparent: bool
    model: str = "pixflux"
    endpoint: str = ENDPOINT
    backend: str = "pixellab"


# -------- Pre-flight ---------------------------------------------------


def _has_key() -> tuple[bool, str | None]:
    if not os.environ.get("PIXELLAB_API_KEY"):
        return False, "PIXELLAB_API_KEY not set"
    return True, None


def build_plan(icon_id: str, user_prompt: str, *,
               pixel_size: int = 64,
               outline: str = DEFAULT_OUTLINE,
               shading: str = DEFAULT_SHADING,
               view: str = DEFAULT_VIEW,
               palette_id: Optional[str] = None,
               seed: Optional[int] = None,
               style_id: Optional[str] = None,
               transparent: bool = True) -> PixellabPlan:
    """Compose the deterministic API plan for a single icon."""
    full = f"{user_prompt}. {STYLE_BRIEF}."
    if outline:
        full += f" {outline}."
    if shading:
        full += f" {shading}."
    if view:
        full += f" {view} view."
    return PixellabPlan(
        icon_id=icon_id,
        prompt_user=user_prompt,
        prompt_full=full,
        pixel_size=int(pixel_size),
        outline=outline,
        shading=shading,
        view=view,
        palette_id=palette_id,
        seed=seed,
        style_id=style_id,
        transparent=bool(transparent),
    )


def write_plan(plan: PixellabPlan, plan_dir: Path = PLAN_DIR) -> Path:
    plan_dir.mkdir(parents=True, exist_ok=True)
    out = plan_dir / f"{plan.icon_id}.pixellab_plan.json"
    out.write_text(json.dumps(asdict(plan), indent=2), encoding="utf-8")
    return out


def estimate_cost(plans: list[PixellabPlan]) -> float:
    return sum(APPROX_USD_PER_IMAGE.get(p.pixel_size, 0.05) for p in plans)


# -------- Real call ----------------------------------------------------


def generate_one(plan: PixellabPlan, *,
                 timeout_s: float = 60.0) -> bytes:
    """Hit the PixelLab API. Returns PNG bytes. Raises RuntimeError on fail.

    Per the published docs, the endpoint accepts JSON:
      {
        "description": "<prompt>",
        "image_size": {"width": N, "height": N},
        "outline": "single color black outline" | ... | "none",
        "shading": "flat shading" | ... | "none",
        "view": "side" | "front" | "low top-down" | ...,
        "no_background": true,
        "init_image_strength": 0,
        "negative_description": "...",
        "seed": 0,
        "style_id": "..."
      }
    Returns base64-encoded PNG in `image.base64`.
    """
    ok, reason = _has_key()
    if not ok:
        raise RuntimeError(f"pixellab_icons: {reason}")
    import requests  # type: ignore
    body: dict = {
        "description": plan.prompt_full,
        "image_size": {"width": plan.pixel_size, "height": plan.pixel_size},
        "outline": plan.outline or "none",
        "shading": plan.shading or "none",
        "view": plan.view or "side",
        "no_background": bool(plan.transparent),
        "negative_description": "anti-aliasing, smooth gradients, watermark, "
                                 "signature, blurry",
    }
    if plan.seed is not None:
        body["seed"] = int(plan.seed)
    if plan.style_id:
        body["style_id"] = plan.style_id
    headers = {
        "Authorization": f"Bearer {os.environ['PIXELLAB_API_KEY']}",
        "Content-Type": "application/json",
    }
    resp = requests.post(plan.endpoint, json=body, headers=headers,
                         timeout=timeout_s)
    if resp.status_code != 200:
        raise RuntimeError(
            f"pixellab_icons: HTTP {resp.status_code}: {resp.text[:300]}")
    payload = resp.json()
    img = payload.get("image") or {}
    b64 = img.get("base64") or img.get("data")
    if not b64:
        raise RuntimeError(
            f"pixellab_icons: no image bytes in response: {str(payload)[:200]}")
    return base64.b64decode(b64)


# -------- Manifest -----------------------------------------------------


def manifest_entry(plan: PixellabPlan, png_path: Path) -> dict:
    return {
        "id": plan.icon_id,
        "path": str(png_path.relative_to(ASSETS).as_posix())
                if png_path.is_absolute() and ASSETS in png_path.parents
                else str(png_path),
        "size_px": plan.pixel_size,
        "backend": "pixellab",
        "source": "pixellab.ai",
        "license": "PixelLab commercial; user owns generations",
        "attribution": None,
        "display_name": plan.icon_id.replace("ico_", "").replace("_", " ").title(),
        "semantic_tags": [],
        "rtl_mirror": False,
        "min_display_px": plan.pixel_size,
        "prompt": plan.prompt_user,
        "prompt_full": plan.prompt_full,
        "model": plan.model,
        "pixel_size": plan.pixel_size,
        "outline": plan.outline,
        "shading": plan.shading,
        "view": plan.view,
        "palette_id": plan.palette_id,
        "seed": plan.seed,
        "style_id": plan.style_id,
    }


# -------- CLI ----------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", type=Path, required=True,
                    help="JSON file: array of {id, prompt[, seed, palette_id, "
                         "view, outline, shading, style_id]}.")
    ap.add_argument("--out", type=Path, default=ICONS_DIR)
    ap.add_argument("--plan-dir", type=Path, default=PLAN_DIR)
    ap.add_argument("--pixel-size", type=int, default=64,
                    choices=[16, 32, 48, 64, 128])
    ap.add_argument("--style-id", type=str, default=None,
                    help="PixelLab character/style id to anchor a set of icons "
                         "to a consistent style. Optional.")
    ap.add_argument("--outline", default=DEFAULT_OUTLINE)
    ap.add_argument("--shading", default=DEFAULT_SHADING)
    ap.add_argument("--view", default=DEFAULT_VIEW,
                    choices=["side", "front", "low top-down", "high top-down"])
    ap.add_argument("--plan-only", action="store_true",
                    help="Write API-call plans to --plan-dir, do not call. Default.")
    ap.add_argument("--run", action="store_true",
                    help="Actually call the API. Requires PIXELLAB_API_KEY + "
                         "--max-cost-usd cap.")
    ap.add_argument("--max-cost-usd", type=float, default=None,
                    help="Refuse to --run if estimated cost exceeds this cap.")
    ap.add_argument("--throttle-s", type=float, default=0.5)
    args = ap.parse_args()

    if not args.prompts.exists():
        print(f"[pixellab_icons] ERROR: prompts file not found: {args.prompts}",
              file=sys.stderr)
        return 2
    raw = json.loads(args.prompts.read_text(encoding="utf-8"))
    items = raw["icons"] if isinstance(raw, dict) and "icons" in raw else raw
    if not isinstance(items, list) or not items:
        print(f"[pixellab_icons] ERROR: prompts file empty or wrong shape",
              file=sys.stderr)
        return 2

    # Build plans
    plans: list[PixellabPlan] = []
    for it in items:
        plans.append(build_plan(
            icon_id=it["id"],
            user_prompt=it["prompt"],
            pixel_size=int(it.get("pixel_size", args.pixel_size)),
            outline=it.get("outline", args.outline),
            shading=it.get("shading", args.shading),
            view=it.get("view", args.view),
            palette_id=it.get("palette_id"),
            seed=it.get("seed"),
            style_id=it.get("style_id", args.style_id),
        ))

    cost = estimate_cost(plans)
    print(f"[pixellab_icons] {len(plans)} plans built; "
          f"estimated cost ~ ${cost:.2f}")

    plans_written: list[Path] = []
    for p in plans:
        plans_written.append(write_plan(p, args.plan_dir))
    print(f"[pixellab_icons] plans -> {args.plan_dir} "
          f"({len(plans_written)} files)")

    if not args.run:
        # Default mode: plan-only.
        return 0

    # --run path: gates
    if args.max_cost_usd is None:
        print(f"[pixellab_icons] ERROR: --run requires --max-cost-usd cap "
              f"to avoid surprise spend (estimated ~ ${cost:.2f})",
              file=sys.stderr)
        return 2
    if cost > args.max_cost_usd:
        print(f"[pixellab_icons] ERROR: estimated ${cost:.2f} exceeds cap "
              f"--max-cost-usd ${args.max_cost_usd:.2f}; refuse to call.",
              file=sys.stderr)
        return 2
    ok, reason = _has_key()
    if not ok:
        print(f"[pixellab_icons] ERROR: {reason}", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {"set": "pixellab", "size": args.pixel_size, "icons": []}
    by_id = {e["id"]: e for e in manifest.get("icons", [])}

    for p in plans:
        png_path = args.out / f"{p.icon_id}.png"
        try:
            png_bytes = generate_one(p)
        except RuntimeError as e:
            print(f"[pixellab_icons] FAIL {p.icon_id}: {e}", file=sys.stderr)
            continue
        png_path.write_bytes(png_bytes)
        by_id[p.icon_id] = manifest_entry(p, png_path)
        print(f"[pixellab_icons] {p.icon_id:36s} -> {png_path}")
        if args.throttle_s > 0:
            time.sleep(args.throttle_s)

    manifest["icons"] = sorted(by_id.values(), key=lambda x: x["id"])
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[pixellab_icons] manifest -> {manifest_path} "
          f"(total {len(manifest['icons'])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
