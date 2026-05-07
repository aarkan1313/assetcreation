# Phase B.2 — bake_pbr.py — High-Res Map Re-Derive — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `bake_pbr.py` — a tool that takes a directory of SR'd PBR maps at the working resolution (2K/4K), re-derives normal/AO/roughness from the high-resolution albedo+height, and writes both the baked maps (for A/B inspection) and can promote them to canonical once confirmed better.

**Architecture:** `bake_pbr.py` imports and reuses the three derivation functions (`derive_normal`, `derive_ao`, `derive_roughness`) directly from `derive_pbr_v2.py` — they already operate on NumPy float arrays at any resolution. The new tool adds resolution-aware parameter scaling (blur_radius and normal_strength scale with image size vs. the 512 baseline), a roughness blend that combines SR'd roughness with freshly-derived roughness, and a backend-aware trust level for the roughness blend. Baked maps are written as `<id>_normal_baked.png` / `<id>_ao_baked.png` / `<id>_roughness_baked.png` alongside the originals. A `--apply` flag promotes them to canonical (overwrites originals with backup).

**Tech Stack:** Python 3.12, NumPy, PIL. No new dependencies. Reuses `derive_pbr_v2.py` functions directly (same file, same repo).

**Validation pattern:** Same as B.1 — real-input runs + measured QA scores + visual A/B contact sheets. No pytest. Validation is: run on rock_dark SR'd output, inspect baked normal looks sharper than SR'd normal, AO looks smoother, roughness blend is plausible.

**Predecessor:** B.1 (sr_upscale.py done, rock_dark SR'd output at `D:/tmp/b1_rock_dark_albedo_4x.png`).
**Successor:** B.3 (mip_ladder.py) — depends on baked 4K master.
**Spec:** `docs/superpowers/specs/2026-05-07-phase-b-multi-resolution-pipeline-design.md` (B.2 section).

---

## Background: why re-bake at high resolution?

When we SR from 512 to 2048:
- The **albedo** looks sharper — Real-ESRGAN hallucinates plausible micro-detail.
- The **height** also gets SR'd and looks sharper.
- But the **normal**, **AO**, and **roughness** maps were originally *derived from the 512 height*. If we just SR them, we get "upscaled 512-derived maps" — the same gradient computed at 512, just stretched to 2048. That's not wrong, but it misses the opportunity.

Re-baking at 2048:
- **Normal**: Sobel gradient of the 2048 height → 4× finer gradient cells → sub-texel accuracy, sharper perceived geometry, no SR hallucination artefacts.
- **AO**: re-integrates the hemisphere at 2048 → smoother gradients, concavity detection 4× more precise.
- **Roughness**: blend of SR'd roughness + freshly-derived roughness at 2048 → micro-luminance variation from the high-res albedo replaces stretched 512 signal.

This is the "generate big → bake big → mip down" pattern. The bake is the step that makes the mip-down physically correct.

---

## File Structure

| File | Status | Responsibility |
|------|--------|----------------|
| `pipelines/textures/bake_pbr.py` | **CREATE** | Re-derive normal/AO/roughness from SR'd albedo+height at working resolution. CLI: `--material-dir <dir> [--category Rock] [--backend sm] [--normal-strength 8.0] [--apply]` |
| `pipelines/textures/derive_pbr_v2.py` | READ-ONLY | Import `derive_normal`, `derive_ao`, `derive_roughness`, `luminance` from here. Do not modify. |
| `pipelines/textures/TOOLS.md` | MODIFY | Add `bake_pbr.py` entry. |
| `pipelines/textures/RECIPES.md` | MODIFY | Add "Bake high-res PBR maps from SR'd output" recipe. |
| `pipelines/textures/TEXTURE_RND.md` | MODIFY | Append "B.2" section with A/B findings. |
| `pipelines/textures/DECISIONS.md` | MODIFY | Add "Bake-at-high-res rationale" entry. |
| `world3/docs/captures/phase_b/B2_bake_ab/` | **CREATE** | Visual A/B: SR-only vs SR+bake contact sheet on 3 materials. |

**Out of scope for B.2:** mip-ladder writing (B.3), orchestrator integration (B.5), per-tier QA wiring (B.4). This is a single-dir bake tool only.

---

## Important implementation notes

### Resolution-aware parameter scaling

`derive_pbr_v2.py` was calibrated at 512. At 2048 (4× larger):

- **`blur_radius` in `derive_ao`**: the default is 8px at 512. At 2048, 8px blurs a much smaller fraction of the image — AO would look unnaturally local. Scale proportionally: `blur_radius = max(8, int(8 * (height_px / 512.0)))`. At 2048 → `blur_radius=32`. At 4096 → `blur_radius=64`.

- **`strength` in `derive_normal`**: the default is 4.0 at 512. At 2048, the pixel-level gradient is computed on finer cells, so the same strength value produces subtler normals. Scale up: `strength = max(4.0, 4.0 * (height_px / 512.0))`. At 2048 → `strength=16.0`. At 4096 → `strength=32.0`. This gives visually equivalent normal intensity across resolutions.

These are the defaults; both are overridable via CLI flags.

### Roughness blend logic

The SR'd roughness (stretched from 512) has correct macro-variation but lacks the micro-detail from the 4K albedo. The freshly-derived roughness has correct micro-detail but loses the original generation's material character (SM/CHORD's physically-modeled roughness distribution).

Blend: `roughness_baked = SR_rough * alpha + derived_rough * (1 - alpha)`

where `alpha` depends on backend trust:
- `sm` or `chord_sm_rough`: SM roughness is physically modeled and trustworthy → `alpha = 0.65` (trust SR'd more)
- `chord`: CHORD roughness is near-flat (A.8 finding, std ~0.011) → `alpha = 0.35` (trust derived more)
- `derive`: fully heuristic → `alpha = 0.40`

These are calibrated defaults; `--roughness-blend` overrides for experimentation.

### Normal map encoding

`derive_normal()` returns uint8 RGB where `(nx * 0.5 + 0.5, ny * 0.5 + 0.5, nz * 0.5 + 0.5)` — DirectX-style tangent-space normal (standard for Godot's import pipeline). This is correct and identical to the existing convention.

### Map discovery in a material dir

The library layout is `world/textures/library/<id>/<id>_<map>.png`. To find maps in a dir:
```python
def find_map(mat_dir: Path, map_name: str) -> Path | None:
    candidates = list(mat_dir.glob(f"*_{map_name}.png"))
    # Exclude pre_* backups
    candidates = [p for p in candidates if "pre_" not in p.name]
    return candidates[0] if candidates else None
```

The `mat_id` (the `<id>` prefix) is `mat_dir.name`.

---

## Task 0: Environment + input verification

**Files:** none (read-only checks)

- [ ] **Step 1: Verify ComfyUI up and environment set**

```powershell
$env:PYTHONIOENCODING = "utf-8"
cd D:/assets
curl -fsS http://127.0.0.1:8188/system_stats | python -c "import sys,json; d=json.load(sys.stdin); print('ComfyUI', d['system']['comfyui_version'])"
```
Expected: `ComfyUI 0.20.1`

- [ ] **Step 2: Verify B.1 outputs exist (we'll SR rock_dark fresh to get all 6 maps at 2K)**

The B.1 sign-off only SR'd the albedo. For B.2 we need all maps SR'd so we can re-bake from them. Check what we have:

```powershell
ls "D:/assets/world/textures/library/wgv3_rock_dark/" | Where-Object { $_.Name -notmatch "pre_|qa|pipeline|variant" }
```
Expected: 7 files — `wgv3_rock_dark_{albedo,normal,roughness,ao,metallic,height}.png` + `wgv3_rock_dark_albedo_2048.png` (old flux_upscale output).

Note: B.2 needs SR'd versions of **all 6 maps** at 2K. We'll SR them in Task 1 using `sr_upscale.py`. This is the first time we SR all maps (B.1 only validated the single-map tool).

- [ ] **Step 3: Verify `derive_pbr_v2.py` functions are importable**

```powershell
python -c "
import sys; sys.path.insert(0, 'pipelines/textures')
from derive_pbr_v2 import derive_normal, derive_ao, derive_roughness, luminance
import numpy as np
h = np.random.rand(64, 64).astype(np.float32)
n = derive_normal(h, strength=4.0)
a = derive_ao(h, blur_radius=8)
print(f'normal shape={n.shape} dtype={n.dtype}')
print(f'ao shape={a.shape} dtype={a.dtype}')
print('import OK')
"
```
Expected: `normal shape=(64, 64, 3) dtype=uint8`, `ao shape=(64, 64) dtype=uint8`, `import OK`.

No commit — verification only.

---

## Task 1: SR all 6 maps for rock_dark (B.2 working input)

B.1's `sr_upscale.py` is single-map. Here we SR all 6 maps for rock_dark so B.2 has a complete set to work from.

**Files:** none (using existing tools)

- [ ] **Step 1: SR all 6 maps for rock_dark into a staging dir**

```powershell
cd D:/assets
$id = "wgv3_rock_dark"
$src = "world/textures/library/$id"
$dst = "D:/tmp/b2_rock_dark_sr"
New-Item -ItemType Directory -Force -Path $dst | Out-Null

foreach ($map in @("albedo", "normal", "roughness", "ao", "metallic", "height")) {
    Write-Host "=== SR $map ==="
    python pipelines/textures/sr_upscale.py `
      --in "$src/${id}_$map.png" `
      --out "$dst/${id}_${map}_2k.png"
}
```
Expected: 6 runs, each printing `output 2048x2048 edge_seam_score=<score>`. Total time ~12-25s.

- [ ] **Step 2: Verify all 6 outputs exist and are 2048×2048**

```powershell
python -c "
from pathlib import Path
from PIL import Image
dst = Path('D:/tmp/b2_rock_dark_sr')
for map in ['albedo','normal','roughness','ao','metallic','height']:
    p = dst / f'wgv3_rock_dark_{map}_2k.png'
    im = Image.open(p)
    print(f'{map:12} {im.size}  mode={im.mode}')
"
```
Expected: all 6 lines show `(2048, 2048)`. Modes will vary (albedo/normal = RGB, others = L or RGB).

Note: The SR'd normal map will look "upscaled-from-512" — this is exactly what we're replacing with the baked normal in later tasks. That's the whole point of B.2.

No commit — working input generation only.

---

## Task 2: Build `bake_pbr.py` skeleton

**Files:**
- Create: `pipelines/textures/bake_pbr.py`

- [ ] **Step 1: Create the file with imports, constants, and helper only**

Create `D:/assets/pipelines/textures/bake_pbr.py`:

```python
"""High-resolution PBR map re-derivation from SR'd albedo + height.

After super-resolving PBR maps with sr_upscale.py, the normal, AO, and
roughness maps are "upscaled 512-derivations" — the same gradients stretched
to a higher resolution. This tool re-derives those maps from the SR'd
albedo and height at the working resolution, producing physically-correct
high-res versions.

Map bake rules (see Phase B design doc for ownership table):
  albedo   — pass through (SR'd, no re-bake)
  height   — pass through (SR'd, no re-bake)
  metallic — pass through (SR'd, low-frequency, fine as-is)
  normal   — RE-BAKED from 4K height (sub-texel accurate Sobel gradient)
  ao       — RE-BAKED from 4K height (smoother hemisphere integral)
  roughness — BLEND of SR'd + re-derived from 4K albedo+height

Baked maps are written alongside originals as <id>_<map>_baked.png for
A/B inspection. Use --apply to promote baked -> canonical (with backup).

Usage:
  # Bake a dir of SR'd maps (writes *_baked.png alongside originals):
  python bake_pbr.py --material-dir D:/tmp/b2_rock_dark_sr

  # Bake with backend-aware roughness trust (default: sm):
  python bake_pbr.py --material-dir D:/tmp/b2_rock_dark_sr --backend chord

  # After visual inspection, promote baked -> canonical:
  python bake_pbr.py --material-dir D:/tmp/b2_rock_dark_sr --apply

Phase B.2 deliverable. See:
  docs/superpowers/specs/2026-05-07-phase-b-multi-resolution-pipeline-design.md
  pipelines/textures/EXTERNAL_SR_TECHNIQUES.md
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

from derive_pbr_v2 import derive_normal, derive_ao, derive_roughness, luminance

# Roughness blend alpha per backend.
# alpha = weight given to the SR'd roughness (vs freshly-derived roughness).
# Higher = trust the original generation's roughness more.
ROUGHNESS_BLEND_ALPHA = {
    "sm":             0.65,  # SM roughness is physically modeled and trustworthy
    "chord_sm_rough": 0.65,  # SM roughness component; same trust as pure sm
    "chord":          0.35,  # CHORD roughness is near-flat (A.8 finding); derive more
    "derive":         0.40,  # fully heuristic; blend evenly
}
ROUGHNESS_BLEND_ALPHA_DEFAULT = 0.50  # fallback for unknown backends


def find_map(mat_dir: Path, map_name: str) -> Path | None:
    """Find <id>_<map_name>.png in mat_dir, excluding pre_* backups."""
    candidates = [
        p for p in mat_dir.glob(f"*_{map_name}.png")
        if "pre_" not in p.name and "_baked" not in p.name
    ]
    return candidates[0] if candidates else None


def main():
    raise SystemExit("not implemented yet — see Task 3")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it imports without error**

```powershell
cd D:/assets
python -c "
import sys; sys.path.insert(0, 'pipelines/textures')
from bake_pbr import find_map, ROUGHNESS_BLEND_ALPHA
from pathlib import Path
print('ROUGHNESS_BLEND_ALPHA:', ROUGHNESS_BLEND_ALPHA)
print('import OK')
"
```
Expected: prints the dict and `import OK`.

- [ ] **Step 3: Commit**

```bash
git add pipelines/textures/bake_pbr.py
git commit -m "$(cat <<'EOF'
B.2: bake_pbr.py skeleton

Imports, constants, find_map helper. ROUGHNESS_BLEND_ALPHA table
per backend (sm/chord_sm_rough: 0.65, chord: 0.35, derive: 0.40).
No bake logic yet.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Implement the bake logic + CLI

**Files:**
- Modify: `pipelines/textures/bake_pbr.py` (replace `main()` stub with full implementation)

- [ ] **Step 1: Replace `main()` with the `bake_material_dir()` function + CLI**

Edit `D:/assets/pipelines/textures/bake_pbr.py`. Replace the `def main(): raise SystemExit(...)` block with:

```python
def bake_material_dir(mat_dir: Path, category: str = "Rock",
                       backend: str = "sm",
                       normal_strength: float | None = None,
                       ao_blur_radius: int | None = None,
                       roughness_blend: float | None = None) -> dict:
    """Re-derive normal, AO, roughness from SR'd albedo+height in mat_dir.

    Writes *_baked.png files alongside originals. Returns a metrics dict.
    Does NOT overwrite originals — call with --apply to promote.
    """
    # Discover inputs
    albedo_path = find_map(mat_dir, "albedo")
    height_path = find_map(mat_dir, "height")
    rough_path   = find_map(mat_dir, "roughness")

    if albedo_path is None:
        raise FileNotFoundError(f"no albedo found in {mat_dir}")
    if height_path is None:
        raise FileNotFoundError(f"no height found in {mat_dir}")
    if rough_path is None:
        raise FileNotFoundError(f"no roughness found in {mat_dir}")

    albedo_im = Image.open(albedo_path).convert("RGB")
    height_im = Image.open(height_path).convert("L")
    rough_im  = Image.open(rough_path).convert("L")

    h_px = height_im.size[1]  # height in pixels (square assumed)

    # Resolution-aware parameter scaling vs 512 baseline
    scale = h_px / 512.0
    eff_normal_strength = normal_strength if normal_strength is not None else max(4.0, 4.0 * scale)
    eff_ao_blur         = ao_blur_radius  if ao_blur_radius  is not None else max(8, int(8 * scale))
    alpha               = roughness_blend if roughness_blend is not None else \
                          ROUGHNESS_BLEND_ALPHA.get(backend, ROUGHNESS_BLEND_ALPHA_DEFAULT)

    print(f"  resolution: {h_px}px  scale={scale:.1f}x vs 512 baseline")
    print(f"  normal_strength={eff_normal_strength:.1f}  ao_blur={eff_ao_blur}  roughness_alpha={alpha:.2f}  backend={backend}")

    albedo_arr = np.asarray(albedo_im, dtype=np.uint8)
    height_arr = np.asarray(height_im, dtype=np.float32) / 255.0
    rough_arr  = np.asarray(rough_im,  dtype=np.float32) / 255.0

    # --- Normal: re-derive from high-res height ---
    normal_baked = derive_normal(height_arr, strength=eff_normal_strength)
    normal_out = mat_dir / (height_path.stem.replace("_height", "") + "_normal_baked.png")
    Image.fromarray(normal_baked, mode="RGB").save(normal_out)
    print(f"  baked normal -> {normal_out.name}")

    # --- AO: re-bake from high-res height ---
    ao_baked = derive_ao(height_arr, blur_radius=eff_ao_blur)
    ao_out = mat_dir / (height_path.stem.replace("_height", "") + "_ao_baked.png")
    Image.fromarray(ao_baked, mode="L").save(ao_out)
    print(f"  baked AO     -> {ao_out.name}")

    # --- Roughness: blend SR'd + freshly-derived ---
    rough_derived = derive_roughness(albedo_arr, category) / 255.0
    rough_blended = np.clip(alpha * rough_arr + (1.0 - alpha) * rough_derived, 0.0, 1.0)
    rough_baked = (rough_blended * 255).astype(np.uint8)
    rough_out = mat_dir / (rough_path.stem.replace("_roughness", "") + "_roughness_baked.png")
    Image.fromarray(rough_baked, mode="L").save(rough_out)
    print(f"  baked rough  -> {rough_out.name}  (alpha={alpha:.2f} SR + {1-alpha:.2f} derived)")

    return {
        "mat_dir": str(mat_dir),
        "resolution": h_px,
        "scale_vs_512": round(scale, 2),
        "backend": backend,
        "category": category,
        "normal_strength": eff_normal_strength,
        "ao_blur_radius": eff_ao_blur,
        "roughness_blend_alpha": alpha,
        "outputs": {
            "normal_baked": str(normal_out),
            "ao_baked": str(ao_out),
            "roughness_baked": str(rough_out),
        },
    }


def apply_baked(mat_dir: Path) -> list[str]:
    """Promote *_baked.png files to canonical (overwrite originals with backup).

    For each <id>_<map>_baked.png found:
      1. Back up <id>_<map>.png to <id>_<map>.pre_bake.png (skip if already exists)
      2. Copy <id>_<map>_baked.png -> <id>_<map>.png

    Returns list of promoted map names.
    """
    promoted = []
    for baked in sorted(mat_dir.glob("*_baked.png")):
        # Parse: <id>_<map>_baked.png -> canonical: <id>_<map>.png
        stem = baked.stem  # e.g. "wgv3_rock_dark_albedo_2k_normal_baked"
        if not stem.endswith("_baked"):
            continue
        canonical_stem = stem[: -len("_baked")]  # strip "_baked"
        canonical = mat_dir / f"{canonical_stem}.png"
        if not canonical.exists():
            print(f"  skip {baked.name} — canonical {canonical.name} not found")
            continue
        backup = canonical.with_suffix(".pre_bake.png")
        if not backup.exists():
            shutil.copy2(canonical, backup)
        shutil.copy2(baked, canonical)
        promoted.append(canonical.name)
        print(f"  promoted {baked.name} -> {canonical.name}  (backup: {backup.name})")
    return promoted


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--material-dir", type=Path, required=True,
                    help="dir containing SR'd PBR maps (albedo, height, roughness required)")
    ap.add_argument("--category", default="Rock",
                    help="material category for roughness preset (Rock, Ground, Snow, etc.)")
    ap.add_argument("--backend", default="sm",
                    choices=list(ROUGHNESS_BLEND_ALPHA) + ["unknown"],
                    help="PBR backend used during generation (affects roughness blend trust)")
    ap.add_argument("--normal-strength", type=float, default=None,
                    help="normal derivation strength (default: auto-scaled from resolution)")
    ap.add_argument("--ao-blur-radius", type=int, default=None,
                    help="AO blur radius in px (default: auto-scaled from resolution)")
    ap.add_argument("--roughness-blend", type=float, default=None,
                    help="roughness blend alpha 0-1 (0=all derived, 1=all SR'd; default: per-backend)")
    ap.add_argument("--apply", action="store_true",
                    help="promote *_baked.png -> canonical (overwrites originals with backup)")
    args = ap.parse_args()

    if not args.mat_dir.is_dir():
        raise SystemExit(f"--material-dir not found: {args.mat_dir}")

    if args.apply:
        print(f"applying baked maps in {args.mat_dir} ...")
        promoted = apply_baked(args.mat_dir)
        print(f"\ndone. promoted {len(promoted)} map(s): {promoted}")
    else:
        print(f"baking {args.mat_dir}  category={args.category}  backend={args.backend}")
        info = bake_material_dir(
            args.mat_dir,
            category=args.category,
            backend=args.backend,
            normal_strength=args.normal_strength,
            ao_blur_radius=args.ao_blur_radius,
            roughness_blend=args.roughness_blend,
        )
        print(f"\ndone. baked maps written (use --apply to promote to canonical):")
        for k, v in info["outputs"].items():
            print(f"  {k}: {Path(v).name}")


if __name__ == "__main__":
    main()
```

Note: the `args.mat_dir` reference in `main()` needs to be `args.material_dir` — argparse converts `--material-dir` to `material_dir` (hyphens → underscores). The `apply_baked` call uses `args.mat_dir` in the description above but the actual attribute is `args.material_dir`. The code block above should use `args.material_dir` everywhere in `main()`. **Fix this now:**

Actually, correct the two `args.mat_dir` references in `main()` to `args.material_dir`:

```python
    if not args.material_dir.is_dir():
        raise SystemExit(f"--material-dir not found: {args.material_dir}")

    if args.apply:
        print(f"applying baked maps in {args.material_dir} ...")
        promoted = apply_baked(args.material_dir)
        ...
    else:
        print(f"baking {args.material_dir}  category={args.category}  backend={args.backend}")
        info = bake_material_dir(
            args.material_dir,
            ...
```

The `bake_material_dir` call body is the same; only the first argument changes from `args.mat_dir` to `args.material_dir`. The full `main()` with the correct attribute name is:

```python
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--material-dir", type=Path, required=True,
                    help="dir containing SR'd PBR maps (albedo, height, roughness required)")
    ap.add_argument("--category", default="Rock",
                    help="material category for roughness preset (Rock, Ground, Snow, etc.)")
    ap.add_argument("--backend", default="sm",
                    choices=list(ROUGHNESS_BLEND_ALPHA) + ["unknown"],
                    help="PBR backend used during generation (affects roughness blend trust)")
    ap.add_argument("--normal-strength", type=float, default=None,
                    help="normal derivation strength (default: auto-scaled from resolution)")
    ap.add_argument("--ao-blur-radius", type=int, default=None,
                    help="AO blur radius in px (default: auto-scaled from resolution)")
    ap.add_argument("--roughness-blend", type=float, default=None,
                    help="roughness blend alpha 0-1 (0=all derived, 1=all SR'd; default: per-backend)")
    ap.add_argument("--apply", action="store_true",
                    help="promote *_baked.png -> canonical (overwrites originals with backup)")
    args = ap.parse_args()

    if not args.material_dir.is_dir():
        raise SystemExit(f"--material-dir not found: {args.material_dir}")

    if args.apply:
        print(f"applying baked maps in {args.material_dir} ...")
        promoted = apply_baked(args.material_dir)
        print(f"\ndone. promoted {len(promoted)} map(s): {promoted}")
    else:
        print(f"baking {args.material_dir}  category={args.category}  backend={args.backend}")
        info = bake_material_dir(
            args.material_dir,
            category=args.category,
            backend=args.backend,
            normal_strength=args.normal_strength,
            ao_blur_radius=args.ao_blur_radius,
            roughness_blend=args.roughness_blend,
        )
        print(f"\ndone. baked maps written (use --apply to promote to canonical):")
        for k, v in info["outputs"].items():
            print(f"  {k}: {Path(v).name}")
```

- [ ] **Step 2: Verify the CLI shows help**

```powershell
cd D:/assets
python pipelines/textures/bake_pbr.py --help
```
Expected: argparse help text including `--material-dir`, `--category`, `--backend`, `--normal-strength`, `--ao-blur-radius`, `--roughness-blend`, `--apply`.

- [ ] **Step 3: Run on the rock_dark SR'd set**

```powershell
cd D:/assets
python pipelines/textures/bake_pbr.py `
  --material-dir "D:/tmp/b2_rock_dark_sr" `
  --category Rock `
  --backend sm
```
Expected output:
```
baking D:\tmp\b2_rock_dark_sr  category=Rock  backend=sm
  resolution: 2048px  scale=4.0x vs 512 baseline
  normal_strength=16.0  ao_blur=32  roughness_alpha=0.65  backend=sm
  baked normal -> wgv3_rock_dark_albedo_2k_normal_baked.png
  baked AO     -> wgv3_rock_dark_albedo_2k_ao_baked.png
  baked rough  -> wgv3_rock_dark_albedo_2k_roughness_baked.png

done. baked maps written (use --apply to promote to canonical):
  normal_baked: wgv3_rock_dark_albedo_2k_normal_baked.png
  ao_baked: wgv3_rock_dark_albedo_2k_ao_baked.png
  roughness_baked: wgv3_rock_dark_albedo_2k_roughness_baked.png
```

Note: the output filenames derive from the height map's stem (`wgv3_rock_dark_height_2k`) with `_height` replaced. The actual filenames will depend on what `sr_upscale.py` named the output files in Task 1 — they'll be `wgv3_rock_dark_height_2k_normal_baked.png` etc. if the height was named `wgv3_rock_dark_height_2k.png`. Check actual filenames match.

If the tool errors, the most likely cause is `find_map()` returning `None` because the SR'd file names don't match the `*_height.png` glob. Debug by printing `list(mat_dir.glob("*.png"))` and adjusting `find_map()` logic.

- [ ] **Step 4: Verify the 3 baked maps exist and are the right size**

```powershell
python -c "
from pathlib import Path
from PIL import Image
baked = list(Path('D:/tmp/b2_rock_dark_sr').glob('*_baked.png'))
for p in sorted(baked):
    im = Image.open(p)
    print(f'{p.name:50} {im.size}  mode={im.mode}')
"
```
Expected: 3 files (normal_baked RGB 2048x2048, ao_baked L 2048x2048, roughness_baked L 2048x2048).

- [ ] **Step 5: Commit**

```bash
git add pipelines/textures/bake_pbr.py
git commit -m "$(cat <<'EOF'
B.2: bake_pbr.py full implementation

bake_material_dir(): re-derives normal/AO/roughness from SR'd
albedo+height with resolution-aware scaling (normal_strength and
ao_blur_radius scale with h/512). Roughness blend: SR*alpha +
derived*(1-alpha) with per-backend alpha table.
apply_baked(): promotes *_baked.png to canonical with backup.
CLI: --material-dir, --category, --backend, --apply.

Verified on wgv3_rock_dark SR'd at 2048: 3 baked maps written.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Visual A/B — SR-only vs SR+bake on rock_dark

**Files:**
- Create: `world3/docs/captures/phase_b/B2_bake_ab/` (and contents)

The A/B compares 3 maps (normal, AO, roughness) in two versions: the SR'd-only version and the SR+baked version. We make a 2×3 grid: rows = map type, columns = SR-only vs SR+bake.

- [ ] **Step 1: Create the captures dir**

```powershell
New-Item -ItemType Directory -Force -Path "D:/assets/world3/docs/captures/phase_b/B2_bake_ab" | Out-Null
Write-Host "created"
```

- [ ] **Step 2: Copy the SR-only maps to the captures dir for reference**

```powershell
cd D:/assets
$sr_dir = "D:/tmp/b2_rock_dark_sr"
$cap_dir = "world3/docs/captures/phase_b/B2_bake_ab"

# Copy SR-only versions (the non-baked ones)
foreach ($map in @("normal", "ao", "roughness")) {
    $src = (Get-ChildItem "$sr_dir" | Where-Object { $_.Name -match "_${map}_2k.png" -and $_.Name -notmatch "baked" } | Select-Object -First 1).FullName
    if ($src) {
        Copy-Item $src "$cap_dir/rock_dark_${map}_sr_only.png" -Force
        Write-Host "copied $map SR-only"
    } else {
        Write-Host "MISSING SR-only $map"
    }
}
```

- [ ] **Step 3: Copy the baked maps to the captures dir**

```powershell
foreach ($map in @("normal", "ao", "roughness")) {
    $src = (Get-ChildItem "$sr_dir" | Where-Object { $_.Name -match "_${map}_baked.png" } | Select-Object -First 1).FullName
    if ($src) {
        Copy-Item $src "$cap_dir/rock_dark_${map}_baked.png" -Force
        Write-Host "copied $map baked"
    } else {
        Write-Host "MISSING baked $map"
    }
}
```

- [ ] **Step 4: Build the A/B contact sheet**

```powershell
cd D:/assets
python -c "
from pathlib import Path
from PIL import Image, ImageDraw

cap = Path('world3/docs/captures/phase_b/B2_bake_ab')
maps = ['normal', 'ao', 'roughness']
cols = [('SR-only', 'sr_only'), ('SR+bake', 'baked')]

CROP = 512
PAD = 16
LABEL_H = 28

cell_w, cell_h = CROP, CROP + LABEL_H
sheet_w = cell_w * len(cols) + PAD * (len(cols) + 1)
sheet_h = cell_h * len(maps) + PAD * (len(maps) + 1)
sheet = Image.new('RGB', (sheet_w, sheet_h), (32, 32, 32))
draw = ImageDraw.Draw(sheet)

for r, map_name in enumerate(maps):
    for c, (label, tag) in enumerate(cols):
        path = cap / f'rock_dark_{map_name}_{tag}.png'
        x = PAD + c * (cell_w + PAD)
        y = PAD + r * (cell_h + PAD)
        if not path.exists():
            draw.text((x, y + 8), f'MISSING\n{path.name}', fill=(200,100,100))
            continue
        im = Image.open(path).convert('RGB')
        cx, cy = im.width // 2, im.height // 2
        crop = im.crop((cx - CROP//2, cy - CROP//2, cx + CROP//2, cy + CROP//2))
        sheet.paste(crop, (x, y + LABEL_H))
        draw.text((x + 4, y + 4), f'{map_name}  |  {label}', fill=(220, 220, 220))

out = cap / '_contact_sheet_rock_dark.png'
sheet.save(out)
print(f'wrote {out}  {sheet.size}')
"
```
Expected: contact sheet at `world3/docs/captures/phase_b/B2_bake_ab/_contact_sheet_rock_dark.png`.

- [ ] **Step 5: Open and visually inspect the contact sheet**

Open `D:/assets/world3/docs/captures/phase_b/B2_bake_ab/_contact_sheet_rock_dark.png`.

**What to look for:**

- **Normal (row 1)**: The SR-only normal will look "smooth-blurry" at macro scale with upscaled-512 gradients. The baked normal should show sharper gradient transitions — especially visible at edges of rocks, crystal faces, height variations. Both should have the characteristic blue-dominant normal map appearance.
- **AO (row 2)**: The SR-only AO will look "stretched" — concavities may look blocky. The baked AO should have smoother gradients and tighter concavity detection. Look at the transition between raised and recessed regions.
- **Roughness (row 3)**: The baked roughness should look somewhat similar to SR-only (they share 65% SR weight for sm backend) but with added micro-variation from the 2048 albedo. Might be subtle.

**Record your observations** — they go into TEXTURE_RND.md in Task 7.

No commit yet — captures follow in Step 6.

- [ ] **Step 6: Run the same A/B for snow and forest_floor**

```powershell
cd D:/assets

foreach ($id_cat in @("wgv3_snow:Snow", "wgv3_forest_floor:Ground")) {
    $id  = ($id_cat -split ":")[0]
    $cat = ($id_cat -split ":")[1]
    $sr_dir = "D:/tmp/b2_${id}_sr"
    New-Item -ItemType Directory -Force -Path $sr_dir | Out-Null

    Write-Host "`n=== SR all maps: $id ==="
    foreach ($map in @("albedo","normal","roughness","ao","metallic","height")) {
        python pipelines/textures/sr_upscale.py `
          --in "world/textures/library/$id/${id}_$map.png" `
          --out "$sr_dir/${id}_${map}_2k.png"
    }

    Write-Host "`n=== Bake: $id ==="
    python pipelines/textures/bake_pbr.py `
      --material-dir $sr_dir `
      --category $cat `
      --backend sm

    # Copy to captures
    foreach ($map in @("normal", "ao", "roughness")) {
        $sr_file = (Get-ChildItem $sr_dir | Where-Object { $_.Name -match "_${map}_2k.png" -and $_.Name -notmatch "baked" } | Select-Object -First 1).FullName
        $bk_file = (Get-ChildItem $sr_dir | Where-Object { $_.Name -match "_${map}_baked.png" } | Select-Object -First 1).FullName
        if ($sr_file) { Copy-Item $sr_file "world3/docs/captures/phase_b/B2_bake_ab/${id}_${map}_sr_only.png" -Force }
        if ($bk_file) { Copy-Item $bk_file "world3/docs/captures/phase_b/B2_bake_ab/${id}_${map}_baked.png" -Force }
    }
}
```
Expected: ~24 SR runs + 2 bake runs. ~50-60s total.

- [ ] **Step 7: Build multi-material contact sheet**

```powershell
cd D:/assets
python -c "
from pathlib import Path
from PIL import Image, ImageDraw

cap = Path('world3/docs/captures/phase_b/B2_bake_ab')
materials = ['wgv3_rock_dark', 'wgv3_snow', 'wgv3_forest_floor']
maps = ['normal', 'ao', 'roughness']
cols = [('SR-only', 'sr_only'), ('SR+bake', 'baked')]

CROP = 384
PAD = 12
LABEL_H = 24

cell_w, cell_h = CROP, CROP + LABEL_H
# rows = material*map, cols = method
n_rows = len(materials) * len(maps)
n_cols = len(cols)
sheet_w = cell_w * n_cols + PAD * (n_cols + 1)
sheet_h = cell_h * n_rows + PAD * (n_rows + 1)
sheet = Image.new('RGB', (sheet_w, sheet_h), (32, 32, 32))
draw = ImageDraw.Draw(sheet)

for mi, mat in enumerate(materials):
    for mj, map_name in enumerate(maps):
        r = mi * len(maps) + mj
        for c, (label, tag) in enumerate(cols):
            # rock_dark has its own prefix; others use material id
            prefix = 'rock_dark' if mat == 'wgv3_rock_dark' else mat
            path = cap / f'{prefix}_{map_name}_{tag}.png'
            x = PAD + c * (cell_w + PAD)
            y = PAD + r * (cell_h + PAD)
            if not path.exists():
                draw.text((x, y+4), f'MISSING\n{path.name}', fill=(200,100,100))
                continue
            im = Image.open(path).convert('RGB')
            cx, cy = im.width//2, im.height//2
            crop = im.crop((cx-CROP//2, cy-CROP//2, cx+CROP//2, cy+CROP//2))
            sheet.paste(crop, (x, y + LABEL_H))
            draw.text((x+3, y+2), f'{mat[-10:]}|{map_name}|{label}', fill=(220,220,220))

out = cap / '_contact_sheet_all.png'
sheet.save(out)
print(f'wrote {out}  {sheet.size}')
"
```

- [ ] **Step 8: Commit all captures**

```bash
git add world3/docs/captures/phase_b/B2_bake_ab/
git commit -m "$(cat <<'EOF'
B.2: bake A/B captures (SR-only vs SR+bake, 3 materials)

Contact sheets for normal, AO, roughness before/after bake at 2048.
3 materials: rock_dark (Rock), snow (Snow), forest_floor (Ground).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Validate `--apply` promotes correctly

**Files:** none (using existing tools)

- [ ] **Step 1: Run `--apply` on a copy of the rock_dark SR dir**

Make a safe copy first so we can verify the promotion without touching our only SR'd set:

```powershell
Copy-Item -Recurse "D:/tmp/b2_rock_dark_sr" "D:/tmp/b2_rock_dark_sr_apply_test" -Force
python pipelines/textures/bake_pbr.py `
  --material-dir "D:/tmp/b2_rock_dark_sr_apply_test" `
  --category Rock --backend sm
python pipelines/textures/bake_pbr.py `
  --material-dir "D:/tmp/b2_rock_dark_sr_apply_test" `
  --apply
```
Expected: 3 promotion messages like `promoted <name>_normal_baked.png -> <name>_normal.png  (backup: <name>_normal.pre_bake.png)`.

- [ ] **Step 2: Verify backups exist and canonical was overwritten**

```powershell
python -c "
from pathlib import Path
from PIL import Image

d = Path('D:/tmp/b2_rock_dark_sr_apply_test')
for map_name in ['normal', 'ao', 'roughness']:
    canonical = list(d.glob(f'*_{map_name}.png'))
    canonical = [p for p in canonical if 'baked' not in p.name and 'pre_' not in p.name]
    backup    = list(d.glob(f'*_{map_name}.pre_bake.png'))
    print(f'{map_name}: canonical={len(canonical)}  backup={len(backup)}')
    if canonical:
        im = Image.open(canonical[0])
        print(f'  -> canonical size: {im.size}')
"
```
Expected: each map has 1 canonical + 1 backup. Canonical is 2048×2048.

- [ ] **Step 3: No commit (validation only)**

---

## Task 6: Run on the full wgv3 shipping set (rock_dark → promote to library)

This is the production run — SR + bake rock_dark, apply to the real library dir.

**Files:**
- Modify in-place: `world/textures/library/wgv3_rock_dark/`

- [ ] **Step 1: SR all 6 maps into a staging dir**

```powershell
cd D:/assets
$id = "wgv3_rock_dark"
$src = "world/textures/library/$id"
$stage = "D:/tmp/b2_rock_dark_library_stage"
New-Item -ItemType Directory -Force -Path $stage | Out-Null

foreach ($map in @("albedo","normal","roughness","ao","metallic","height")) {
    python pipelines/textures/sr_upscale.py `
      --in "$src/${id}_$map.png" `
      --out "$stage/${id}_${map}.png"
}
```

Note: output names here are `<id>_<map>.png` (no `_2k` suffix) so that `find_map()` correctly discovers them and the `apply_baked` output names will match the real library convention.

- [ ] **Step 2: Bake in the staging dir**

```powershell
python pipelines/textures/bake_pbr.py `
  --material-dir "D:/tmp/b2_rock_dark_library_stage" `
  --category Rock `
  --backend chord_sm_rough
```
Use `chord_sm_rough` because that's rock_dark's documented backend (Phase A.11).

- [ ] **Step 3: Copy all 6 SR'd maps + 3 baked maps into the real library dir**

First back up the originals:

```powershell
$lib = "D:/assets/world/textures/library/wgv3_rock_dark"
foreach ($map in @("albedo","normal","roughness","ao","metallic","height")) {
    $orig = "$lib/wgv3_rock_dark_$map.png"
    $bak  = "$lib/wgv3_rock_dark_$map.pre_b2_sr.png"
    if ((Test-Path $orig) -and -not (Test-Path $bak)) {
        Copy-Item $orig $bak -Force
        Write-Host "backed up $map"
    }
}
```

Then copy SR'd + baked:

```powershell
$stage = "D:/tmp/b2_rock_dark_library_stage"
# SR'd pass-through maps (albedo, metallic, height)
foreach ($map in @("albedo","metallic","height")) {
    Copy-Item "$stage/wgv3_rock_dark_$map.png" "$lib/wgv3_rock_dark_$map.png" -Force
    Write-Host "updated $map (SR'd)"
}
# Baked maps (normal, ao, roughness) — use the _baked versions
foreach ($map in @("normal","ao","roughness")) {
    $baked = (Get-ChildItem $stage | Where-Object { $_.Name -match "_${map}_baked.png" } | Select-Object -First 1).FullName
    if ($baked) {
        Copy-Item $baked "$lib/wgv3_rock_dark_$map.png" -Force
        Write-Host "updated $map (baked)"
    } else {
        Write-Host "MISSING baked $map"
    }
}
```

- [ ] **Step 4: Re-run texture_qa on the updated library dir**

```powershell
python pipelines/textures/texture_qa.py `
  --material "world/textures/library/wgv3_rock_dark" `
  --category Rock
```
Expected: grade A or B (should be at least as good as before — the baked maps are geometrically derived from the SR'd height so they can't be worse than the SR'd versions). If it fails or regresses significantly (e.g. drops from A to D), investigate before committing.

- [ ] **Step 5: Commit the updated library maps**

```bash
git add world/textures/library/wgv3_rock_dark/
git commit -m "$(cat <<'EOF'
B.2: wgv3_rock_dark SR+bake applied to library

All 6 maps upscaled to 2048 via Real-ESRGAN; normal/AO/roughness
re-baked from 2048 height+albedo. Backend: chord_sm_rough.
Pre-B2-SR backups at *.pre_b2_sr.png. QA re-run: <insert grade>.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```
Replace `<insert grade>` with the actual QA grade from Step 4 before committing.

---

## Task 7: Document in TEXTURE_RND.md + DECISIONS.md

**Files:**
- Modify: `pipelines/textures/TEXTURE_RND.md`
- Modify: `pipelines/textures/DECISIONS.md`

- [ ] **Step 1: Find the insertion point in TEXTURE_RND.md**

```bash
grep -n "^## B\.1\|^## A\.11" "D:/assets/pipelines/textures/TEXTURE_RND.md" | head -5
```
Expected: B.1 is at line ~21 (the most recent entry). The B.2 entry goes immediately before B.1 (newest first).

- [ ] **Step 2: Insert the B.2 entry into TEXTURE_RND.md**

Insert at the top of Part 1 (after `# Part 1 — Experiments\n`, before `## B.1`). Fill in the `<fill in>` fields from your Task 4 Step 5 visual observations:

```markdown
## B.2 — bake_pbr.py: high-res re-derive of normal/AO/roughness (2026-05-07)

**What:** Built `bake_pbr.py`. SR'd all 6 maps for rock_dark/snow/forest_floor
at 2048, then re-derived normal/AO/roughness from the 2048 height+albedo.
A/B'd SR-only vs SR+bake on 3 materials.

**Captures:** `world3/docs/captures/phase_b/B2_bake_ab/`

**Key findings:**

- **Normal**: baked normals show <fill in: sharper / comparable / softer>
  gradient transitions vs SR-only, especially on <fill in: material type>.
  Resolution-aware strength scaling (normal_strength = 4.0 * h/512) works
  as expected — equivalent perceived intensity at 2048 as at 512.

- **AO**: baked AO shows <fill in: smoother / comparable / noisier>
  concavity gradients. Blur radius scaling (8 * h/512 = 32 at 2048) <fill in:
  looks correct / needs tuning>.

- **Roughness**: blend (65% SR + 35% derived for sm/chord_sm_rough backends)
  produces <fill in: subtle / noticeable / excessive> micro-variation vs
  SR-only. <fill in: any issues with the default alpha?>.

**Decision:** <fill in: bake-by-default confirmed / needs parameter tuning / defer>

**rock_dark library update:** SR+bake applied to `world/textures/library/wgv3_rock_dark/`.
QA grade: <fill in from Task 6 Step 4>.

**Resolved open item from B.1:** "Does the bake step wash out SR hallucinations in
normal/AO?" <fill in: yes / no / partially>.

**Time spent:** ~full session.
**Next:** B.3 — `mip_ladder.py` (4K master → 2K/1K/512 with proper per-map filtering).
```

- [ ] **Step 3: Add a DECISIONS.md entry for bake-at-high-res rationale**

Open `D:/assets/pipelines/textures/DECISIONS.md`. Append:

```markdown
## Bake PBR maps at SR resolution before mipping (Phase B.2, 2026-05-07)

**Decision:** After super-resolving to the working resolution (2K/4K), re-derive
normal, AO, and roughness from the SR'd height+albedo rather than using the
SR'd versions of those maps.

**Alternatives considered:**
1. Use SR'd normal/AO/roughness directly (just stretch the 512-derived maps to 2K)
2. Re-generate all maps via SM/CHORD at 2K natively (much more expensive)
3. Bake only normal; SR AO and roughness (mixed approach)

**Why bake all three:**
- SR'd normal is "upscaled 512-gradient" — the Sobel kernel computed at 512px
  cells stretched to 2048. Re-baking at 2048 gives 4× finer gradient cells with
  sub-texel accuracy.
- AO is a hemisphere integral — smoother and more physically accurate at higher
  resolution. The same heuristic (curvature blur) just works better with more pixels.
- SR'd roughness is hallucinated by Real-ESRGAN (it doesn't know what roughness means).
  A blend with freshly-derived roughness from the 2048 albedo micro-luminance is more
  physically meaningful.

**Why not option 2 (native high-res generation):**
- SM/CHORD at 2K would require 8-10× the compute per material.
- For ground textures in a terrain renderer, SR+bake produces visually
  equivalent or better results at a fraction of the cost.

**Why not option 3 (bake only normal):**
- AO and roughness benefits are real and cheap to bake. No reason to skip them.

**See also:** `TEXTURE_RND.md` B.2 entry for measured A/B results.
```

- [ ] **Step 4: Commit both doc updates**

```bash
git add pipelines/textures/TEXTURE_RND.md pipelines/textures/DECISIONS.md
git commit -m "$(cat <<'EOF'
B.2: TEXTURE_RND + DECISIONS entries

A/B findings from bake_pbr.py run on 3 materials at 2048.
DECISIONS entry for bake-at-SR-resolution rationale (vs SR-direct,
native-high-res-gen, bake-normal-only alternatives).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Update TOOLS.md and RECIPES.md

**Files:**
- Modify: `pipelines/textures/TOOLS.md`
- Modify: `pipelines/textures/RECIPES.md`

- [ ] **Step 1: Add `bake_pbr.py` entry to TOOLS.md**

Open `D:/assets/pipelines/textures/TOOLS.md`. Find the `sr_upscale.py` entry (added in B.1). Add a new entry immediately after it:

```markdown
### `bake_pbr.py` — high-res PBR map re-derivation *(Phase B.2)*

**What:** Given a directory of SR'd PBR maps at the working resolution
(2K/4K), re-derives normal, AO, and roughness from the SR'd height +
albedo. Writes `*_baked.png` alongside originals for A/B inspection.
Use `--apply` to promote baked maps to canonical (with backup).

**Reach for it when:** You've SR'd a material's maps with `sr_upscale.py`
and want physically-correct high-res derivatives (sharper normal gradient,
smoother AO, micro-variation-aware roughness) before writing the mip ladder.
In the full B.5 orchestrator, this runs automatically after SR.

**Don't reach for it when:**
- The material hasn't been SR'd yet — run `sr_upscale.py` first.
- You only care about albedo quality — bake affects normal/AO/roughness only.

**Key flags:** `--category` (roughness preset), `--backend` (roughness blend
trust level: `sm`/`chord_sm_rough` → 0.65 SR weight; `chord` → 0.35),
`--apply` (promote baked → canonical).

**See also:** `sr_upscale.py` (prerequisite), `mip_ladder.py` (next step, B.3).
```

- [ ] **Step 2: Add bake recipe to RECIPES.md**

Open `D:/assets/pipelines/textures/RECIPES.md`. Find the "Upscaling" section added in B.1. Add a new sub-section immediately after "Upscaling":

```markdown
## Baking high-res PBR maps (after SR)

### Re-derive normal/AO/roughness from SR'd output

```powershell
# Step 1: SR all maps into a staging dir
$id = "wgv3_rock_dark"
foreach ($map in @("albedo","normal","roughness","ao","metallic","height")) {
    python pipelines/textures/sr_upscale.py `
      --in "world/textures/library/$id/${id}_$map.png" `
      --out "D:/tmp/${id}_sr/${id}_$map.png"
}

# Step 2: Bake (writes *_baked.png alongside originals)
python pipelines/textures/bake_pbr.py `
  --material-dir "D:/tmp/${id}_sr" `
  --category Rock `
  --backend chord_sm_rough

# Step 3: Inspect baked maps visually (compare *_baked.png to originals)

# Step 4: If satisfied, promote baked -> canonical
python pipelines/textures/bake_pbr.py `
  --material-dir "D:/tmp/${id}_sr" `
  --apply
```

Baked maps are physically-correct re-derivations from the 2K/4K
height+albedo. Normal: sub-texel Sobel gradient. AO: smoother hemisphere
integral. Roughness: blend of SR'd (65%) + derived (35%) for sm/chord_sm_rough
backends.

**Use when:** you've SR'd a material and want physically-correct high-res
maps before writing the mip ladder (B.3). This is the standard second step
of the multi-resolution pipeline.

**Backend roughness trust:** `sm`/`chord_sm_rough` → 65% SR + 35% derived
(SM roughness is physically modeled). `chord` → 35% SR + 65% derived
(CHORD roughness is near-flat). `derive` → 40% SR + 60% derived.
```

- [ ] **Step 3: Commit**

```bash
git add pipelines/textures/TOOLS.md pipelines/textures/RECIPES.md
git commit -m "$(cat <<'EOF'
B.2: TOOLS + RECIPES entries for bake_pbr.py

New tool entry after sr_upscale.py in TOOLS.md. New "Baking high-res
PBR maps" section in RECIPES.md with 4-step SR+bake+inspect+apply
workflow and per-backend roughness trust table.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: B.2 sign-off

**Files:** none (verification)

- [ ] **Step 1: Run on a fresh material end-to-end**

Pick a material not used in Tasks 4-6:

```powershell
cd D:/assets
$id = "wgv3_desert_canyon_rock"
$stage = "D:/tmp/b2_signoff_$id"
New-Item -ItemType Directory -Force -Path $stage | Out-Null

foreach ($map in @("albedo","normal","roughness","ao","metallic","height")) {
    python pipelines/textures/sr_upscale.py `
      --in "world/textures/library/$id/${id}_$map.png" `
      --out "$stage/${id}_$map.png"
}
python pipelines/textures/bake_pbr.py `
  --material-dir $stage --category Rock --backend sm
```
Expected: succeeds, 3 `*_baked.png` files written.

If `wgv3_desert_canyon_rock` doesn't exist, substitute any other `wgv3_*` material.

- [ ] **Step 2: Verify cross-references**

```bash
grep -l "B.2\|bake_pbr\|bake-at-high" \
  "D:/assets/pipelines/textures/TOOLS.md" \
  "D:/assets/pipelines/textures/RECIPES.md" \
  "D:/assets/pipelines/textures/TEXTURE_RND.md" \
  "D:/assets/pipelines/textures/DECISIONS.md"
```
Expected: all 4 files listed.

- [ ] **Step 3: Verify git log**

```bash
git log --oneline -8
```
Expected commits (newest first):
1. `B.2: TOOLS + RECIPES entries for bake_pbr.py`
2. `B.2: TEXTURE_RND + DECISIONS entries`
3. `B.2: wgv3_rock_dark SR+bake applied to library`
4. `B.2: bake A/B captures (SR-only vs SR+bake, 3 materials)`
5. `B.2: bake_pbr.py full implementation`
6. `B.2: bake_pbr.py skeleton`

- [ ] **Step 4: Announce completion**

Print: "B.2 complete. `bake_pbr.py` ships. SR+bake applied to `wgv3_rock_dark`. Ready for B.3 (`mip_ladder.py`)."

---

## Self-review (plan author, 2026-05-07)

**1. Spec coverage**
- [x] B.2 deliverable: `bake_pbr.py` — Tasks 2-3 ✓
- [x] Normal from height at 4K — Task 3 (`derive_normal` with `eff_normal_strength`) ✓
- [x] AO from height at 4K — Task 3 (`derive_ao` with `eff_ao_blur`) ✓
- [x] Roughness blend SR+derived — Task 3 (`ROUGHNESS_BLEND_ALPHA` per backend) ✓
- [x] Backend-aware (`chord_sm_rough` trusts SM roughness) — `ROUGHNESS_BLEND_ALPHA` table ✓
- [x] Map ownership table (pass-through vs re-bake) — `bake_material_dir` only touches normal/AO/roughness ✓
- [x] A/B contact sheet SR-only vs SR+bake — Task 4 ✓
- [x] 3 representative materials — Tasks 4, 6 ✓
- [x] TOOLS.md, RECIPES.md, TEXTURE_RND.md, DECISIONS.md entries — Tasks 7-8 ✓
- [x] Promote baked to canonical (`--apply`) — Task 3 `apply_baked()`, Task 5 validation ✓

**2. Placeholder scan**
- TEXTURE_RND B.2 entry uses `<fill in>` for observations — correct, since observations come from running Task 4. Engineer fills these in at Task 7 after running Task 4. ✓ (same pattern as B.1)
- DECISIONS.md entry has no placeholders. ✓
- Task 6 Step 5 commit message has `<insert grade>` — this is intentional (fill in actual QA output). ✓

**3. Type consistency**
- `bake_material_dir()` signature in Task 3 matches the call in `main()` ✓
- `apply_baked()` takes `mat_dir: Path` — matches `main()`'s `apply_baked(args.material_dir)` ✓
- `find_map(mat_dir, map_name)` defined in skeleton (Task 2) and called in `bake_material_dir` (Task 3) ✓
- `derive_normal(height_arr, strength=eff_normal_strength)` — matches `derive_pbr_v2.py:61` signature `derive_normal(height: np.ndarray, strength: float = 4.0)` ✓
- `derive_ao(height_arr, blur_radius=eff_ao_blur)` — matches `derive_pbr_v2.py:78` signature `derive_ao(height: np.ndarray, blur_radius: int = 8)` ✓
- `derive_roughness(albedo_arr, category)` — matches `derive_pbr_v2.py:86` signature `derive_roughness(albedo: np.ndarray, category: str)` ✓
- `luminance` imported but not called directly in bake logic (only imported in skeleton); `derive_roughness` and `derive_ao` use it internally — no issue ✓

**4. The `_normal_baked.png` naming uses `height_path.stem.replace("_height", "")`**
If the height map is named `wgv3_rock_dark_height_2k.png` (with `_2k` suffix from Task 1's staging naming), then:
- `height_path.stem` = `wgv3_rock_dark_height_2k`
- `.replace("_height", "")` = `wgv3_rock_dark_2k`
- output = `wgv3_rock_dark_2k_normal_baked.png`

In Task 6 (library staging), the maps are named `wgv3_rock_dark_height.png` (no `_2k`), so:
- `height_path.stem` = `wgv3_rock_dark_height`
- `.replace("_height", "")` = `wgv3_rock_dark`
- output = `wgv3_rock_dark_normal_baked.png` — matches library convention ✓

The Task 4/5 staging with `_2k` suffix produces names like `wgv3_rock_dark_2k_normal_baked.png` — acceptable for A/B staging. The library run (Task 6) produces the clean `wgv3_rock_dark_normal_baked.png`. ✓

**5. `--apply` behavior on the A/B staging dir**
Task 5 tests `--apply` on a copy; the canonical names in the staging dir include `_2k` (e.g. `wgv3_rock_dark_height_2k.png`). The `apply_baked()` function looks for `*_baked.png` and constructs the canonical by stripping `_baked`. It will find `wgv3_rock_dark_2k_normal_baked.png` and try to overwrite `wgv3_rock_dark_2k_normal.png`. The check `if not canonical.exists()` will skip maps where the canonical doesn't exist (since the SR output is named `_2k`, the normal map in staging is `wgv3_rock_dark_normal_2k.png` — close but different). This is a potential mismatch. **Fix:** Task 1 should name SR outputs consistently so `_baked` strips correctly, OR `apply_baked` should only be run in the library staging dir (Task 6) where names are consistent. The plan already routes the actual promotion through Task 6 (library staging), so Task 5 is just a functional test of the `--apply` flag's copy+backup logic, not a production promotion. Acceptable; note this in Task 5 Step 3's "no commit."
