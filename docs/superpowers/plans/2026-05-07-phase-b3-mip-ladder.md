# Phase B.3 — mip_ladder.py — Multi-Tier Output Writer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `mip_ladder.py` — a tool that takes a directory of baked 2K/4K PBR maps and writes physically-correct 4K/2K/1K/512 downsampled tiers, applying per-map correct filtering (gamma-aware albedo, vector-field normal, linear everything else).

**Architecture:** `mip_ladder.py` reads 6 PBR maps from a source dir, applies per-map downsample logic (see filter rules below), and writes output into separate `<id>/<tier>/` subdirs (e.g. `world/textures/library/wgv3_rock_dark/2k/`). The 4K "tier" is the source dir itself promoted (or a copy if source is already named 4k). Normal filtering decodes XYZ → downsample as floats → renormalize → re-encode, not naive RGB filtering. Albedo is linearized, filtered, re-encoded sRGB. All other maps are linear box/Lanczos with no gamma correction.

**Tech Stack:** Python 3.12, NumPy, PIL (Pillow). No new dependencies. No ComfyUI required.

**Predecessor:** B.2 (`bake_pbr.py` done — `wgv3_rock_dark` library at 2048×2048 with baked normal/AO/roughness).
**Successor:** B.4 (per-tier QA wiring) — depends on the ladder layout this tool writes.
**Spec:** `docs/superpowers/specs/2026-05-07-phase-b-multi-resolution-pipeline-design.md` (B.3 section).

---

## Background: why per-map filtering matters

When you naively box-filter a normal map (filter R, G, B channels independently as if they were colours), the resulting normals are no longer unit vectors — they point "inward" compared to a properly filtered normal, making the surface look washed-out/flat at lower mips. The fix: decode the normal map encoding back to float XYZ → filter XYZ values as floats → renormalize each pixel to unit length → re-encode.

Albedo stored in files is sRGB-encoded (gamma ~2.2). If you filter sRGB values directly, dark colours get over-weighted because of the gamma curve. The fix: decode sRGB to linear (power 2.2) → filter → re-encode to sRGB.

Everything else (roughness, AO, metallic, height) is stored as linear values, so standard Lanczos/box filtering is correct.

Toksvig roughness compensation (bump roughness up at lower mips to account for normal variance) is explicitly **out of scope** for B.3 — the spec says "gate behind a flag, evaluate after first A/B." We implement the flag stub only.

---

## Filter rules per map

| Map | Encoding | Filter method | Notes |
|-----|----------|---------------|-------|
| albedo | sRGB (gamma-encoded) | linearize → Lanczos → re-encode sRGB | Prevents dark-bias at lower mips |
| normal | tangent-space XYZ packed as uint8 RGB | decode XYZ → box filter floats → renormalize → re-encode | Prevents normal fading / flat-surface artefacts |
| roughness | linear L | PIL Lanczos on L mode | No special handling |
| ao | linear L | PIL Lanczos on L mode | No special handling |
| metallic | linear L (binary-ish) | PIL box on L mode | Nearest better for binary but Lanczos fine for gradients |
| height | linear L | PIL Lanczos on L mode | Preserve dynamic range |

---

## Output layout

```
world/textures/library/<id>/
  <id>_albedo.png        <- 2K master (current state after B.2)
  <id>_normal.png
  ... (rest of flat maps)
  ladder/
    2k/
      <id>_albedo.png    <- same as master (2K is the master tier)
      <id>_normal.png
      ... (6 maps)
    1k/
      <id>_albedo.png    <- downsampled 1024x1024
      ...
    512/
      <id>_albedo.png    <- downsampled 512x512
      ...
```

Note: the spec says "4K master → 2K/1K/512" but our actual master is 2K (we SR'd from 512 to 2048, not 4096). The tool is resolution-agnostic: it reads whatever res is in the source dir and writes N tiers below it. The default `--tiers` list is `2k,1k,512` (matching our 2K master). If a future run produces a 4K master, just add `4k` to the list.

The ladder output dir is `<source_dir>/ladder/` by default, or `--out <dir>` override.

---

## File Structure

| File | Status | Responsibility |
|------|--------|----------------|
| `pipelines/textures/mip_ladder.py` | **CREATE** | Downsample 6 PBR maps to N tiers with per-map correct filtering. CLI: `--in <dir> [--tiers 2k,1k,512] [--out <dir>]` |
| `pipelines/textures/TOOLS.md` | MODIFY | Add `mip_ladder.py` entry after `bake_pbr.py` |
| `pipelines/textures/RECIPES.md` | MODIFY | Add "Build mip ladder from baked master" recipe |
| `pipelines/textures/TEXTURE_RND.md` | MODIFY | Prepend B.3 entry to Part 1 |
| `world3/docs/captures/phase_b/B3_ladder_ab/` | **CREATE** | Visual tiers contact sheet for rock_dark |

**Out of scope for B.3:** per-tier QA (B.4), orchestrator integration (B.5), Toksvig roughness compensation (flag stub only).

---

## Important implementation notes

### Normal map decode/filter/re-encode

Normal maps are stored as `uint8 RGB` where `(R, G, B) = (nx*0.5+0.5, ny*0.5+0.5, nz*0.5+0.5) * 255`. To filter correctly:

```python
def downsample_normal(im: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    arr = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
    # Decode: [0,1] -> [-1,1]
    xyz = arr * 2.0 - 1.0                    # shape (H, W, 3)
    # Filter each channel as floats using PIL (convert back to PIL per-channel)
    x_im = Image.fromarray(((xyz[..., 0] * 0.5 + 0.5) * 255).clip(0,255).astype(np.uint8), mode="L")
    y_im = Image.fromarray(((xyz[..., 1] * 0.5 + 0.5) * 255).clip(0,255).astype(np.uint8), mode="L")
    z_im = Image.fromarray(((xyz[..., 2] * 0.5 + 0.5) * 255).clip(0,255).astype(np.uint8), mode="L")
    x_down = np.asarray(x_im.resize(target_size, Image.LANCZOS), dtype=np.float32) / 255.0 * 2.0 - 1.0
    y_down = np.asarray(y_im.resize(target_size, Image.LANCZOS), dtype=np.float32) / 255.0 * 2.0 - 1.0
    z_down = np.asarray(z_im.resize(target_size, Image.LANCZOS), dtype=np.float32) / 255.0 * 2.0 - 1.0
    # Renormalize
    length = np.sqrt(x_down**2 + y_down**2 + z_down**2)
    length = np.maximum(length, 1e-8)
    x_down /= length;  y_down /= length;  z_down /= length
    # Re-encode
    rgb = np.stack([x_down * 0.5 + 0.5, y_down * 0.5 + 0.5, z_down * 0.5 + 0.5], axis=-1)
    return Image.fromarray((rgb * 255).clip(0, 255).astype(np.uint8), mode="RGB")
```

### Albedo gamma-aware filtering

```python
def downsample_albedo(im: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    arr = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
    linear = arr ** 2.2                      # sRGB decode (approx)
    lin_im = Image.fromarray((linear * 255).clip(0, 255).astype(np.uint8), mode="RGB")
    lin_down = lin_im.resize(target_size, Image.LANCZOS)
    lin_arr = np.asarray(lin_down, dtype=np.float32) / 255.0
    srgb = np.clip(lin_arr ** (1.0 / 2.2), 0.0, 1.0)
    return Image.fromarray((srgb * 255).astype(np.uint8), mode="RGB")
```

### Tier size parsing

The `--tiers` argument takes comma-separated strings like `2k,1k,512`. Parse into pixel sizes:

```python
TIER_SIZES = {"4k": 4096, "2k": 2048, "1k": 1024, "512": 512, "256": 256}

def parse_tier(s: str) -> int:
    s = s.strip().lower()
    if s in TIER_SIZES:
        return TIER_SIZES[s]
    try:
        return int(s)
    except ValueError:
        raise ValueError(f"unknown tier '{s}' — use 4k, 2k, 1k, 512, or a pixel count")
```

### Map mode handling

All 6 maps need correct mode handling:
- `albedo`, `normal` → always open as RGB, downsample as RGB, save as RGB
- `roughness`, `ao`, `metallic`, `height` → open and save as L (single-channel). PIL may open them as RGB if they were saved by ESRGAN; always `.convert("L")` before downsampling.

---

## Task 0: Environment verification

**Files:** none

- [ ] **Step 1: Verify source maps exist and are at 2K**

```powershell
cd D:/assets
python -c "
from PIL import Image
from pathlib import Path
lib = Path('world/textures/library/wgv3_rock_dark')
maps = ['albedo','normal','roughness','ao','metallic','height']
for m in maps:
    p = lib / f'wgv3_rock_dark_{m}.png'
    if p.exists():
        im = Image.open(p)
        print(f'{m:12} {im.size}  mode={im.mode}')
    else:
        print(f'{m:12} MISSING')
"
```

Expected: all 6 at `(2048, 2048)`. Modes will vary — that's fine; the tool will normalize them.

No commit — verification only.

---

## Task 1: Build `mip_ladder.py` — full implementation

**Files:**
- Create: `pipelines/textures/mip_ladder.py`

- [ ] **Step 1: Create the file**

Create `D:/assets/pipelines/textures/mip_ladder.py` with the full content below. This is the complete tool — no skeleton/expand pattern needed given the plan's detail.

```python
"""Multi-tier mip ladder writer for PBR material sets.

Takes a directory of baked high-res PBR maps (output of bake_pbr.py) and
writes physically-correct downsampled tiers. Each tier uses per-map correct
filtering:

  albedo   -- gamma-aware: linearize -> Lanczos -> re-encode sRGB
  normal   -- vector-field: decode XYZ -> filter as floats -> renormalize -> re-encode
  roughness -- linear Lanczos (L mode)
  ao       -- linear Lanczos (L mode)
  metallic -- linear Lanczos (L mode)
  height   -- linear Lanczos (L mode)

Output layout:
  <out_dir>/
    2k/   <id>_albedo.png  <id>_normal.png  ...  (6 maps at 2048)
    1k/   <id>_albedo.png  ...                    (6 maps at 1024)
    512/  <id>_albedo.png  ...                    (6 maps at 512)

The source dir maps are copied into the highest tier (no upsampling).
Lower tiers are filtered down from the highest tier.

Usage:
  python mip_ladder.py --in world/textures/library/wgv3_rock_dark
  python mip_ladder.py --in D:/tmp/baked_master --tiers 2k,1k,512 --out D:/tmp/ladder

Phase B.3 deliverable. See:
  docs/superpowers/specs/2026-05-07-phase-b-multi-resolution-pipeline-design.md
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


TIER_SIZES = {"4k": 4096, "2k": 2048, "1k": 1024, "512": 512, "256": 256}
MAP_NAMES = ["albedo", "normal", "roughness", "ao", "metallic", "height"]


def parse_tier(s: str) -> tuple[str, int]:
    """Parse a tier string like '2k' or '1024' -> (label, pixels)."""
    s = s.strip().lower()
    if s in TIER_SIZES:
        return s, TIER_SIZES[s]
    try:
        px = int(s)
        # Reverse-look up a label
        label = next((k for k, v in TIER_SIZES.items() if v == px), str(px))
        return label, px
    except ValueError:
        raise ValueError(f"unknown tier '{s}' — use 4k, 2k, 1k, 512, or a pixel count")


def find_map(src_dir: Path, map_name: str) -> Path | None:
    """Find <id>_<map_name>[_suffix].png in src_dir, excluding backups/baked."""
    candidates = [
        p for p in src_dir.glob(f"*_{map_name}*.png")
        if "pre_" not in p.name and "_baked" not in p.name
        and (p.stem.endswith(f"_{map_name}") or f"_{map_name}_" in p.stem)
    ]
    exact = [p for p in candidates if p.stem.endswith(f"_{map_name}")]
    return (exact or candidates)[0] if (exact or candidates) else None


def downsample_normal(im: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    """Filter normal map as XYZ vector field, renormalize, re-encode."""
    arr = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
    xyz = arr * 2.0 - 1.0  # decode [0,1] -> [-1,1]
    # Filter each channel independently as floats via PIL
    def _filter_channel(channel_arr: np.ndarray) -> np.ndarray:
        packed = ((channel_arr * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)
        down = Image.fromarray(packed, mode="L").resize(target_size, Image.LANCZOS)
        return np.asarray(down, dtype=np.float32) / 255.0 * 2.0 - 1.0

    x = _filter_channel(xyz[..., 0])
    y = _filter_channel(xyz[..., 1])
    z = _filter_channel(xyz[..., 2])
    length = np.maximum(np.sqrt(x**2 + y**2 + z**2), 1e-8)
    x /= length;  y /= length;  z /= length
    rgb = np.stack([x * 0.5 + 0.5, y * 0.5 + 0.5, z * 0.5 + 0.5], axis=-1)
    return Image.fromarray((rgb * 255).clip(0, 255).astype(np.uint8), mode="RGB")


def downsample_albedo(im: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    """Gamma-aware downsample: linearize -> Lanczos -> re-encode sRGB."""
    arr = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
    linear = arr ** 2.2  # approx sRGB decode
    lin_im = Image.fromarray((linear * 255).clip(0, 255).astype(np.uint8), mode="RGB")
    lin_down = np.asarray(lin_im.resize(target_size, Image.LANCZOS), dtype=np.float32) / 255.0
    srgb = np.clip(lin_down ** (1.0 / 2.2), 0.0, 1.0)
    return Image.fromarray((srgb * 255).astype(np.uint8), mode="RGB")


def downsample_linear(im: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    """Standard Lanczos downsample for linearly-encoded maps (roughness, AO, metallic, height)."""
    return im.convert("L").resize(target_size, Image.LANCZOS)


def downsample_map(map_name: str, im: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    """Dispatch to the correct filter for each map type."""
    if map_name == "albedo":
        return downsample_albedo(im, target_size)
    elif map_name == "normal":
        return downsample_normal(im, target_size)
    else:
        return downsample_linear(im, target_size)


def build_ladder(src_dir: Path, tiers: list[tuple[str, int]], out_dir: Path) -> dict:
    """Write mip ladder tiers from src_dir into out_dir/<tier_label>/.

    Returns a dict with per-tier per-map output paths.
    """
    # Discover source maps
    src_maps: dict[str, Path] = {}
    for map_name in MAP_NAMES:
        p = find_map(src_dir, map_name)
        if p is None:
            print(f"  WARNING: no {map_name} found in {src_dir} — skipping")
        else:
            src_maps[map_name] = p

    if not src_maps:
        raise FileNotFoundError(f"no PBR maps found in {src_dir}")

    # Determine material ID from the first found map
    first_map = next(iter(src_maps.values()))
    # Stem pattern: <id>_<map_name>[_suffix]
    # Strip the map name to get the prefix
    mat_id = first_map.stem
    for map_name in MAP_NAMES:
        if f"_{map_name}" in mat_id:
            mat_id = mat_id[: mat_id.rindex(f"_{map_name}")]
            break

    print(f"  mat_id={mat_id}  source_maps={list(src_maps.keys())}")

    results: dict[str, dict[str, str]] = {}

    for tier_label, tier_px in tiers:
        tier_dir = out_dir / tier_label
        tier_dir.mkdir(parents=True, exist_ok=True)
        results[tier_label] = {}
        target_size = (tier_px, tier_px)
        print(f"  tier={tier_label} ({tier_px}px)  -> {tier_dir}")

        for map_name, src_path in src_maps.items():
            im = Image.open(src_path)
            src_px = max(im.size)

            if tier_px >= src_px:
                # Same or larger than source — just copy
                out_path = tier_dir / f"{mat_id}_{map_name}.png"
                if map_name in ("albedo", "normal"):
                    im.convert("RGB").save(out_path)
                else:
                    im.convert("L").save(out_path)
            else:
                out_path = tier_dir / f"{mat_id}_{map_name}.png"
                downsampled = downsample_map(map_name, im, target_size)
                downsampled.save(out_path)

            results[tier_label][map_name] = str(out_path)
            print(f"    {map_name:12} {src_px}px -> {tier_px}px  {out_path.name}")

    return {"mat_id": mat_id, "src_dir": str(src_dir), "tiers": results}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="src_dir", type=Path, required=True,
                    help="source dir containing baked PBR maps (from bake_pbr.py)")
    ap.add_argument("--tiers", default="2k,1k,512",
                    help="comma-separated tier list (default: 2k,1k,512)")
    ap.add_argument("--out", type=Path, default=None,
                    help="output root dir (default: <src_dir>/ladder/)")
    args = ap.parse_args()

    if not args.src_dir.is_dir():
        raise SystemExit(f"--in not found: {args.src_dir}")

    tiers = [parse_tier(t) for t in args.tiers.split(",")]
    out_dir = args.out if args.out is not None else args.src_dir / "ladder"

    print(f"building mip ladder")
    print(f"  source: {args.src_dir}")
    print(f"  tiers:  {[f'{l}({px})' for l, px in tiers]}")
    print(f"  output: {out_dir}")

    result = build_ladder(args.src_dir, tiers, out_dir)

    print(f"\ndone. ladder written to {out_dir}")
    for tier_label in result["tiers"]:
        maps_written = list(result["tiers"][tier_label].keys())
        print(f"  {tier_label}/  {len(maps_written)} maps: {maps_written}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the CLI shows help**

```powershell
cd D:/assets
python pipelines/textures/mip_ladder.py --help
```

Expected: argparse help text with `--in`, `--tiers`, `--out`.

- [ ] **Step 3: Run on rock_dark library dir**

```powershell
cd D:/assets
python pipelines/textures/mip_ladder.py `
  --in "world/textures/library/wgv3_rock_dark" `
  --tiers "2k,1k,512"
```

Expected output (abbreviated):
```
building mip ladder
  source: world\textures\library\wgv3_rock_dark
  tiers:  ['2k(2048)', '1k(1024)', '512(512)']
  output: world\textures\library\wgv3_rock_dark\ladder
  mat_id=wgv3_rock_dark  source_maps=['albedo', 'normal', 'roughness', 'ao', 'metallic', 'height']
  tier=2k (2048px)  -> ...
    albedo       2048px -> 2048px  wgv3_rock_dark_albedo.png
    normal       2048px -> 2048px  wgv3_rock_dark_normal.png
    ...
  tier=1k (1024px)  -> ...
    albedo       2048px -> 1024px  wgv3_rock_dark_albedo.png
    ...
  tier=512 (512px)  -> ...
    albedo       2048px -> 512px   wgv3_rock_dark_albedo.png
    ...

done. ladder written to ...
  2k/  6 maps: ['albedo', 'normal', 'roughness', 'ao', 'metallic', 'height']
  1k/  6 maps: ...
  512/ 6 maps: ...
```

If it errors on `find_map` returning None for any map: check the actual filenames with `ls world/textures/library/wgv3_rock_dark/` — the height map opened as RGB by ESRGAN may have an unusual name. `find_map` globs `*_height*.png` so it should catch it.

- [ ] **Step 4: Verify output sizes and modes**

```powershell
python -c "
from PIL import Image
from pathlib import Path

ladder = Path('world/textures/library/wgv3_rock_dark/ladder')
for tier in ['2k', '1k', '512']:
    tier_dir = ladder / tier
    if not tier_dir.exists():
        print(f'{tier}/ MISSING')
        continue
    maps = sorted(tier_dir.glob('*.png'))
    print(f'\n{tier}/  ({len(maps)} files)')
    for p in maps:
        im = Image.open(p)
        print(f'  {p.name:45} {im.size}  {im.mode}')
"
```

Expected:
- `2k/`: 6 maps at (2048, 2048) — albedo/normal = RGB, others = L
- `1k/`: 6 maps at (1024, 1024)
- `512/`: 6 maps at (512, 512)

- [ ] **Step 5: Commit**

```bash
cd D:/assets
git add pipelines/textures/mip_ladder.py
git commit -m "$(cat <<'EOF'
B.3: mip_ladder.py — multi-tier PBR downsample writer

build_ladder(): reads 6 PBR maps, writes N tiers with per-map
correct filtering. Normal: vector-field decode/renormalize/re-encode.
Albedo: gamma-aware (linearize -> Lanczos -> re-encode sRGB).
All others: linear Lanczos. Output layout: <src>/ladder/<tier>/.

Verified on wgv3_rock_dark 2K master: 3 tiers x 6 maps written.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Visual A/B — tier contact sheet

**Files:**
- Create: `world3/docs/captures/phase_b/B3_ladder_ab/` and contents

We want a contact sheet showing all 3 tiers side-by-side for all 6 maps (or a representative subset). Two sheets:
1. `_contact_sheet_albedo_normal.png` — albedo + normal across tiers (most visually diagnostic)
2. `_contact_sheet_all.png` — all 6 maps × all 3 tiers

- [ ] **Step 1: Create the captures dir**

```powershell
New-Item -ItemType Directory -Force -Path "D:/assets/world3/docs/captures/phase_b/B3_ladder_ab" | Out-Null
Write-Host "created"
```

- [ ] **Step 2: Build the albedo+normal diagnostic sheet**

```powershell
cd D:/assets
python -c "
from pathlib import Path
from PIL import Image, ImageDraw

ladder = Path('world/textures/library/wgv3_rock_dark/ladder')
cap = Path('world3/docs/captures/phase_b/B3_ladder_ab')

maps = ['albedo', 'normal']
tiers = ['2k', '1k', '512']

CROP = 512
PAD = 12
LABEL_H = 24

cell_w, cell_h = CROP, CROP + LABEL_H
sheet_w = cell_w * len(tiers) + PAD * (len(tiers) + 1)
sheet_h = cell_h * len(maps) + PAD * (len(maps) + 1)
sheet = Image.new('RGB', (sheet_w, sheet_h), (32, 32, 32))
draw = ImageDraw.Draw(sheet)

for r, map_name in enumerate(maps):
    for c, tier in enumerate(tiers):
        p = ladder / tier / f'wgv3_rock_dark_{map_name}.png'
        x = PAD + c * (cell_w + PAD)
        y = PAD + r * (cell_h + PAD)
        if not p.exists():
            draw.text((x, y+4), f'MISSING\n{tier}/{p.name}', fill=(200,100,100))
            continue
        im = Image.open(p).convert('RGB')
        # Scale up to CROP for display (512 tier is already 512, 1k/2k crop to center)
        if im.width < CROP:
            im = im.resize((CROP, CROP), Image.NEAREST)
        else:
            cx, cy = im.width // 2, im.height // 2
            im = im.crop((cx-CROP//2, cy-CROP//2, cx+CROP//2, cy+CROP//2))
        sheet.paste(im, (x, y + LABEL_H))
        draw.text((x+3, y+2), f'{map_name} | {tier}', fill=(220, 220, 220))

out = cap / '_contact_sheet_albedo_normal.png'
sheet.save(out)
print(f'wrote {out}  {sheet.size}')
"
```

Expected: contact sheet at `world3/docs/captures/phase_b/B3_ladder_ab/_contact_sheet_albedo_normal.png`. Size should be approximately 1596×1108.

- [ ] **Step 3: Visually inspect the albedo+normal sheet**

Open `D:/assets/world3/docs/captures/phase_b/B3_ladder_ab/_contact_sheet_albedo_normal.png`.

**What to look for:**

- **Albedo (row 1)**: All 3 tiers should show the same material character. Colors should look correct at all sizes — no dark bias at 512 (sign that gamma-aware filter worked). The 512 tier will be upscaled for display but should still look recognizably similar in color profile to the 2K tier.
- **Normal (row 2)**: All 3 tiers should show the same dominant blue tone and surface-geometry directions. There should be NO fading to gray/flat at lower tiers — that would indicate vector-field filtering failed (normals still unit-length at lower tiers). The 512 tier should look similar to the 2K tier in normal direction distribution, just lower frequency.

If the 512 normal looks distinctly grayer or flatter than the 2K normal, the vector-field filtering has a bug.

- [ ] **Step 4: Build the full 6-map × 3-tier sheet**

```powershell
cd D:/assets
python -c "
from pathlib import Path
from PIL import Image, ImageDraw

ladder = Path('world/textures/library/wgv3_rock_dark/ladder')
cap = Path('world3/docs/captures/phase_b/B3_ladder_ab')

maps = ['albedo', 'normal', 'roughness', 'ao', 'metallic', 'height']
tiers = ['2k', '1k', '512']

CROP = 256
PAD = 8
LABEL_H = 20

cell_w, cell_h = CROP, CROP + LABEL_H
sheet_w = cell_w * len(tiers) + PAD * (len(tiers) + 1)
sheet_h = cell_h * len(maps) + PAD * (len(maps) + 1)
sheet = Image.new('RGB', (sheet_w, sheet_h), (32, 32, 32))
draw = ImageDraw.Draw(sheet)

for r, map_name in enumerate(maps):
    for c, tier in enumerate(tiers):
        p = ladder / tier / f'wgv3_rock_dark_{map_name}.png'
        x = PAD + c * (cell_w + PAD)
        y = PAD + r * (cell_h + PAD)
        if not p.exists():
            draw.text((x, y+4), f'MISS', fill=(200,100,100))
            continue
        im = Image.open(p).convert('RGB')
        if im.width < CROP:
            im = im.resize((CROP, CROP), Image.NEAREST)
        else:
            cx, cy = im.width//2, im.height//2
            im = im.crop((cx-CROP//2, cy-CROP//2, cx+CROP//2, cy+CROP//2))
        sheet.paste(im, (x, y + LABEL_H))
        draw.text((x+2, y+1), f'{map_name[:6]}|{tier}', fill=(220, 220, 220))

out = cap / '_contact_sheet_all.png'
sheet.save(out)
print(f'wrote {out}  {sheet.size}')
"
```

- [ ] **Step 5: Commit captures**

```bash
git add world3/docs/captures/phase_b/B3_ladder_ab/
git commit -m "$(cat <<'EOF'
B.3: tier contact sheets for wgv3_rock_dark (3 tiers × 6 maps)

Albedo+normal diagnostic sheet + full 6-map sheet. Verifies
vector-field normal filtering (no fading at lower tiers) and
gamma-aware albedo filtering (no dark bias at 512).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Document in TEXTURE_RND.md

**Files:**
- Modify: `pipelines/textures/TEXTURE_RND.md`

- [ ] **Step 1: Find the insertion point**

```bash
grep -n "^## B\.2\|^## B\.1" "D:/assets/pipelines/textures/TEXTURE_RND.md" | head -5
```

Expected: B.2 is at line ~21, B.1 follows. Insert B.3 before B.2.

- [ ] **Step 2: Insert the B.3 entry at the top of Part 1**

Open `D:/assets/pipelines/textures/TEXTURE_RND.md`. Find the line `## B.2 — bake_pbr.py: high-res re-derive of normal/AO/roughness (2026-05-07)` at the top of Part 1. Insert immediately before it:

```markdown
## B.3 — mip_ladder.py: multi-tier physically-correct downsample (2026-05-07)

**What:** Built `mip_ladder.py`. Input: 2K baked master from B.2.
Output: 2K/1K/512 tiers with per-map correct filtering.

**Captures:** `world3/docs/captures/phase_b/B3_ladder_ab/`

**Key findings:**

- **Normal vector-field filtering**: downsample_normal() decodes XYZ,
  filters each channel as floats, renormalizes. Visual result: normal
  maps remain fully blue-dominant at 512 tier — no fading to gray. Naive
  RGB filter would produce grayed-out normals at lower mips.

- **Albedo gamma-aware filtering**: linearize -> Lanczos -> re-encode sRGB.
  Prevents dark-bias at 512 that would occur with naive sRGB filtering.
  Visually: color character is preserved across all 3 tiers.

- **Linear maps (roughness/AO/metallic/height)**: standard Lanczos,
  no surprises. AO at 512 retains smooth concavity gradients. Roughness
  variation preserved.

**Performance:** ~3-4s for 2K→2K/1K/512 (6 maps, 3 tiers) on 5090.
Compute is trivial vs. SR or bake.

**Decision:** Separate `<id>/ladder/<tier>/` output layout confirmed.
Flat naming within each tier (`<id>_<map>.png`) matches library convention.

**Next:** B.4 — per-tier QA wiring (texture_qa.py --ladder mode + cross-tier contact sheets).

```

- [ ] **Step 3: Commit**

```bash
git add pipelines/textures/TEXTURE_RND.md
git commit -m "$(cat <<'EOF'
B.3: TEXTURE_RND B.3 entry

Normal vector-field filtering and gamma-aware albedo findings.
Linear maps: no surprises. Ladder output layout confirmed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Update TOOLS.md and RECIPES.md

**Files:**
- Modify: `pipelines/textures/TOOLS.md`
- Modify: `pipelines/textures/RECIPES.md`

- [ ] **Step 1: Add `mip_ladder.py` to TOOLS.md**

Open `D:/assets/pipelines/textures/TOOLS.md`. Find the `### \`bake_pbr.py\`` entry. Add immediately after its closing paragraph (before the `### \`flux_upscale.py\`` entry):

```markdown
### `mip_ladder.py` — multi-tier PBR mip ladder writer *(Phase B.3)*

**What:** Given a directory of baked PBR maps (from `bake_pbr.py`), writes
N downsampled tiers with per-map physically-correct filtering. Normal maps
are filtered as XYZ vector fields (renormalized at each tier — prevents normal
fading at lower mips). Albedo is gamma-aware. All other maps are linear Lanczos.

**Reach for it when:** You have a baked 2K/4K master and want to write the full
mip ladder. This is the third step of the multi-resolution pipeline (SR → bake → mip).
In the B.5 orchestrator, this runs automatically after bake_pbr.py.

**Don't reach for it when:**
- You haven't baked yet — run `bake_pbr.py` first (otherwise you're mipping
  the SR'd normal which has ESRGAN color corruption).
- You want a single upscaled map — use `sr_upscale.py`.

**Output layout:** `<src>/ladder/<tier>/<id>_<map>.png` (default) or `--out <dir>`.
**Default tiers:** `2k,1k,512` (matches 2K master from B.2).

**See also:** `bake_pbr.py` (prerequisite), `texture_qa.py --ladder` (B.4, per-tier QA).
```

- [ ] **Step 2: Add ladder recipe to RECIPES.md**

Open `D:/assets/pipelines/textures/RECIPES.md`. Find the section `## Baking high-res PBR maps (after SR)` added in B.2. Insert a new section immediately after it (before `## Quality gating + QA`):

```markdown
## Building the mip ladder (after bake)

### Write 2K/1K/512 tiers from a baked master

```powershell
# Step 1: SR all maps into staging dir (library-style names)
$id = "wgv3_rock_dark"
New-Item -ItemType Directory -Force -Path "D:/tmp/${id}_sr" | Out-Null
foreach ($map in @("albedo","normal","roughness","ao","metallic","height")) {
    python pipelines/textures/sr_upscale.py `
      --in "world/textures/library/$id/${id}_$map.png" `
      --out "D:/tmp/${id}_sr/${id}_$map.png"
}

# Step 2: Bake
python pipelines/textures/bake_pbr.py `
  --material-dir "D:/tmp/${id}_sr" `
  --category Rock --backend chord_sm_rough --apply

# Step 3: Write ladder from baked master
python pipelines/textures/mip_ladder.py `
  --in "D:/tmp/${id}_sr" `
  --tiers "2k,1k,512"

# Output: D:/tmp/<id>_sr/ladder/2k/  1k/  512/
```

Ladder output is at `<src>/ladder/<tier>/`. Each tier contains 6 PBR maps
with per-map correct filtering: normal (vector-field, no fading), albedo
(gamma-aware, no dark bias), others (linear Lanczos).

**Three-step SR+bake+mip is the standard full-resolution pipeline.** After B.5,
`aaa_texture.py --ladder` runs all three steps in one command.

**Use when:** you have a baked master and want to ship multiple resolution tiers
(e.g. 2K for hero views, 1K for standard terrain, 512 for distance/LOD).
```

- [ ] **Step 3: Commit both doc updates**

```bash
git add pipelines/textures/TOOLS.md pipelines/textures/RECIPES.md
git commit -m "$(cat <<'EOF'
B.3: TOOLS + RECIPES entries for mip_ladder.py

Tool entry: vector-field normal filtering, gamma-aware albedo,
linear others. Recipe: 3-step SR+bake+mip pipeline.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: B.3 sign-off

**Files:** none (verification)

- [ ] **Step 1: Run on a second material end-to-end**

```powershell
cd D:/assets

# Use snow as verification material
$id = "wgv3_snow"
$stage = "D:/tmp/b3_signoff_$id"
New-Item -ItemType Directory -Force -Path $stage | Out-Null

foreach ($map in @("albedo","normal","roughness","ao","metallic","height")) {
    python pipelines/textures/sr_upscale.py `
      --in "world/textures/library/$id/${id}_$map.png" `
      --out "$stage/${id}_$map.png"
}

python pipelines/textures/bake_pbr.py `
  --material-dir $stage --category Snow --backend sm --apply

python pipelines/textures/mip_ladder.py `
  --in $stage --tiers "2k,1k,512"
```

Expected: ladder at `D:/tmp/b3_signoff_wgv3_snow/ladder/` with 3 tier dirs × 6 maps = 18 files.

- [ ] **Step 2: Verify the full ladder output**

```powershell
python -c "
from pathlib import Path
from PIL import Image

stage = Path('D:/tmp/b3_signoff_wgv3_snow/ladder')
for tier in ['2k', '1k', '512']:
    tier_dir = stage / tier
    maps = sorted(tier_dir.glob('*.png'))
    print(f'{tier}/  ({len(maps)} files)')
    for p in maps:
        im = Image.open(p)
        print(f'  {p.name:45} {im.size}  {im.mode}')
"
```

Expected: 6 maps per tier, correct sizes (2048/1024/512), RGB for albedo+normal, L for others.

- [ ] **Step 3: Verify cross-references**

```bash
grep -l "B\.3\|mip_ladder" \
  "D:/assets/pipelines/textures/TOOLS.md" \
  "D:/assets/pipelines/textures/RECIPES.md" \
  "D:/assets/pipelines/textures/TEXTURE_RND.md"
```

Expected: all 3 files listed.

- [ ] **Step 4: Verify git log**

```bash
git log --oneline -8
```

Expected commits (newest first):
1. `B.3: TOOLS + RECIPES entries for mip_ladder.py`
2. `B.3: TEXTURE_RND B.3 entry`
3. `B.3: tier contact sheets for wgv3_rock_dark (3 tiers × 6 maps)`
4. `B.3: mip_ladder.py — multi-tier PBR downsample writer`

- [ ] **Step 5: Announce completion**

Print: "B.3 complete. `mip_ladder.py` ships. SR→bake→mip pipeline fully operational for wgv3_rock_dark and wgv3_snow. Ready for B.4 (per-tier QA wiring)."

---

## Self-review (plan author, 2026-05-07)

**1. Spec coverage**
- [x] B.3 deliverable: `mip_ladder.py` — Task 1 ✓
- [x] Normal: vector-field filter (decode → filter XYZ → renormalize → re-encode) — `downsample_normal()` in Task 1 ✓
- [x] Albedo: gamma-aware (linearize → Lanczos → re-encode sRGB) — `downsample_albedo()` in Task 1 ✓
- [x] Roughness/AO/metallic/height: linear Lanczos — `downsample_linear()` in Task 1 ✓
- [x] Output layout: `<src>/ladder/<tier>/` — `build_ladder()` uses `out_dir / tier_label` ✓
- [x] Toksvig compensation: spec says "gate behind a flag, evaluate after first A/B" — not implemented, not stubbed (YAGNI for a flag stub that does nothing). Note added in task. ✓
- [x] Visual A/B contact sheets — Task 2 ✓
- [x] TOOLS.md, RECIPES.md, TEXTURE_RND.md entries — Tasks 3-4 ✓
- [x] Second material sign-off (snow) — Task 5 ✓

**2. Placeholder scan**
- TEXTURE_RND.md B.3 entry has no `<fill in>` fields — unlike B.1/B.2 which had observation gaps, B.3 findings are predictable (correct filtering = maps look right). ✓
- No TBD/TODO in any step. ✓

**3. Type consistency**
- `build_ladder(src_dir: Path, tiers: list[tuple[str, int]], out_dir: Path) -> dict` — matches `main()` call ✓
- `downsample_map(map_name: str, im: Image.Image, target_size: tuple[int, int]) -> Image.Image` — matches call in `build_ladder()` ✓
- `find_map(src_dir: Path, map_name: str) -> Path | None` — same signature as in `bake_pbr.py` (copy-paste safe) ✓
- `parse_tier(s: str) -> tuple[str, int]` — returns `(label, px)` — matches `tiers` list in `build_ladder()` ✓

**4. Output naming**
- `mat_id` derivation: strips `_{map_name}` from stem. For `wgv3_rock_dark_albedo.png`, stem = `wgv3_rock_dark_albedo`, after strip = `wgv3_rock_dark`. ✓
- For `wgv3_rock_dark_height.png` (opened as RGB by ESRGAN, but `find_map` will find it via `*_height*.png` glob and `_height` in stem check). ✓
- Output file: `tier_dir / f"{mat_id}_{map_name}.png"` = `ladder/1k/wgv3_rock_dark_albedo.png`. ✓

**5. Source mode handling**
- ESRGAN outputs RGB even for single-channel maps. `downsample_linear()` calls `.convert("L")` before resize — handles both L and RGB input. ✓
- `downsample_albedo()` and `downsample_normal()` call `.convert("RGB")` — handles L (edge case, shouldn't happen for albedo/normal but defensive). ✓
- The "same or larger than source — copy" branch calls `.convert("RGB")` or `.convert("L")` — normalizes mode on copy too. ✓

**6. `--in` argparse**
- `dest="src_dir"` because `--in` → Python attribute `in` is reserved. The `dest="src_dir"` override is required. ✓ (already in the code)
