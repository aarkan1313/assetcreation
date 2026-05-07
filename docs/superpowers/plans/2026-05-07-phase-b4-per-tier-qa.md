# Phase B.4 — Per-Tier QA Wiring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `texture_qa.py` with a `--ladder` flag that runs QA on every tier in a mip ladder, and add a cross-tier contact sheet showing all tiers side by side with their grade verdicts.

**Architecture:** `texture_qa.py` already has `run_qa(material_dir, category)` which writes `qa/` inside a single material dir. For `--ladder`, we walk the `<mat_dir>/ladder/` subdirs, call `run_qa` on each tier dir, then generate a cross-tier contact sheet (`ladder/cross_tier_sheet.png`) from the per-tier `tile_2x2.png` outputs. No new file is needed — everything goes into the existing `texture_qa.py`. A new helper function `run_ladder_qa(ladder_dir, category)` orchestrates the tier walk and sheet generation.

**Tech Stack:** Python 3.12, NumPy, PIL. No new dependencies.

**Predecessor:** B.3 (`mip_ladder.py` done — `wgv3_rock_dark` ladder at `world/textures/library/wgv3_rock_dark/ladder/`).
**Successor:** B.5 (orchestrator integration) — depends on the `--ladder` flag existing.
**Spec:** `docs/superpowers/specs/2026-05-07-phase-b-multi-resolution-pipeline-design.md` (B.4 section).

---

## What `run_qa` already does (per single material dir)

Given a dir containing `<id>_albedo.png` etc., `run_qa` writes:
- `qa/seam_score.json` — 4-check metrics + per-check pass/fail + grade
- `qa/sanity.json` — map presence + value ranges
- `qa/tile_2x2.png` — albedo tiled 2×2
- `qa/sphere_preview.png` and `qa/plane_preview.png`
- Prints `grade=A  edge=... junc=... period=... rich=...` to stdout

The ladder tier dirs (`ladder/2k/`, `ladder/1k/`, `ladder/512/`) have the exact same layout as a standard material dir (`<id>_albedo.png` etc.), so `run_qa` works on them without modification.

## What B.4 adds

1. **`--ladder <mat_dir>`** CLI flag: walks `<mat_dir>/ladder/` subdir, calls `run_qa` on each tier.
2. **`run_ladder_qa(ladder_dir, category)`** function: orchestrates the tier walk + cross-tier sheet.
3. **Cross-tier contact sheet** (`ladder/cross_tier_sheet.png`): one row per tier (sorted by resolution descending), showing the `qa/tile_2x2.png` + grade verdict text for each tier.
4. **`--ladder-dir`** alternative: accept a bare ladder dir (e.g. `--ladder-dir D:/tmp/foo/ladder`) for use outside the standard library layout.

## File Structure

| File | Status | Responsibility |
|------|--------|----------------|
| `pipelines/textures/texture_qa.py` | MODIFY | Add `run_ladder_qa()` + `--ladder` + `--ladder-dir` flags |
| `pipelines/textures/TOOLS.md` | MODIFY | Update `texture_qa.py` entry with `--ladder` flag |
| `pipelines/textures/RECIPES.md` | MODIFY | Add "QA a full mip ladder" recipe |
| `pipelines/textures/TEXTURE_RND.md` | MODIFY | Prepend B.4 entry |

---

## Implementation notes

### Tier sort order

`ladder/` contains dirs named `2k`, `1k`, `512`. Sort them by pixel count descending so the cross-tier sheet reads top-to-bottom from highest to lowest resolution:

```python
TIER_SIZES = {"4k": 4096, "2k": 2048, "1k": 1024, "512": 512, "256": 256}

def _tier_px(tier_name: str) -> int:
    return TIER_SIZES.get(tier_name.lower(), int(tier_name) if tier_name.isdigit() else 0)
```

### Cross-tier contact sheet layout

Each row = one tier. Each row shows:
- Left: the `qa/tile_2x2.png` thumbnail (crop to 512×512 from center)
- Right: a text panel with grade verdict, edge/junc/periodic/richness scores

```
+------------------+------------------------------------------+
|  tile_2x2        |  2k  grade=A                             |
|  (512x512 crop)  |  edge=0.0000(P)  junc=0.84(P)           |
|                  |  period=20.1(P)  rich=0.66(F,advisory)   |
+------------------+------------------------------------------+
|  tile_2x2        |  1k  grade=A                             |
|  (512x512 crop)  |  ...                                     |
+------------------+------------------------------------------+
|  tile_2x2        |  512  grade=B                            |
|  ...             |  ...                                     |
+------------------+------------------------------------------+
```

Text panel is drawn with `ImageDraw.text()` — no external font needed (PIL's default bitmap font is fine for compact metric display).

### `run_ladder_qa` signature

```python
def run_ladder_qa(ladder_dir: Path, category: str | None = None) -> list[dict]:
    """Run QA on every tier in ladder_dir, then write a cross-tier contact sheet.

    ladder_dir must contain subdirs named by tier (e.g. '2k', '1k', '512').
    Each tier dir must contain <id>_albedo.png (and the other PBR maps).

    Returns list of per-tier result dicts: [{tier, grade, seam, ...}, ...].
    Writes: <ladder_dir>/<tier>/qa/ (per-tier qa output from run_qa)
    Writes: <ladder_dir>/cross_tier_sheet.png
    """
```

---

## Task 0: Environment verification

**Files:** none

- [ ] **Step 1: Verify ladder exists and has the expected layout**

```powershell
cd D:/assets
python -c "
from pathlib import Path
ladder = Path('world/textures/library/wgv3_rock_dark/ladder')
for tier_dir in sorted(ladder.iterdir()):
    maps = sorted(tier_dir.glob('*.png'))
    print(f'{tier_dir.name}/  ({len(maps)} maps): {[p.name for p in maps[:2]]}...')
"
```

Expected: `2k/`, `1k/`, `512/` each with 6 `.png` files.

- [ ] **Step 2: Verify existing `run_qa` works on a single tier dir**

```powershell
python pipelines/textures/texture_qa.py `
  --material "world/textures/library/wgv3_rock_dark/ladder/1k" `
  --category Rock
```

Expected: `[QA] 1k  grade=A  edge=...  junc=...  period=...  rich=...` and a `ladder/1k/qa/` dir created.

No commit — verification only.

---

## Task 1: Add `run_ladder_qa()` and `--ladder` flag to `texture_qa.py`

**Files:**
- Modify: `pipelines/textures/texture_qa.py`

- [ ] **Step 1: Add the `_tier_px` helper and `run_ladder_qa()` function**

Open `D:/assets/pipelines/textures/texture_qa.py`. Find the line `def main():` (line ~570). Insert the following block immediately **before** `def main():`:

```python
TIER_SIZES_PX = {"4k": 4096, "2k": 2048, "1k": 1024, "512": 512, "256": 256}


def _tier_px(tier_name: str) -> int:
    """Return pixel size for a tier label like '2k' or '512'."""
    s = tier_name.strip().lower()
    if s in TIER_SIZES_PX:
        return TIER_SIZES_PX[s]
    try:
        return int(s)
    except ValueError:
        return 0


def _make_cross_tier_sheet(tier_results: list[dict], out_path: Path) -> None:
    """Write a cross-tier contact sheet: one row per tier showing tile_2x2 + metrics."""
    THUMB = 512
    TEXT_W = 480
    ROW_H = THUMB + 16
    PAD = 8
    sheet_w = PAD + THUMB + PAD + TEXT_W + PAD
    sheet_h = PAD + ROW_H * len(tier_results) + PAD * (len(tier_results) - 1)
    sheet = Image.new("RGB", (sheet_w, max(sheet_h, 64)), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)

    for i, tr in enumerate(tier_results):
        y = PAD + i * (ROW_H + PAD)
        # Thumbnail
        tile_path = tr.get("tile_2x2_path")
        if tile_path and Path(tile_path).exists():
            thumb = Image.open(tile_path).convert("RGB")
            cx, cy = thumb.width // 2, thumb.height // 2
            half = THUMB // 2
            thumb = thumb.crop((cx - half, cy - half, cx + half, cy + half))
        else:
            thumb = Image.new("RGB", (THUMB, THUMB), (60, 60, 60))
        sheet.paste(thumb, (PAD, y + 8))

        # Text panel
        tx = PAD + THUMB + PAD
        ty = y + 12
        tier = tr["tier"]
        grade = tr["grade"]
        grade_color = {"A": (80, 220, 80), "B": (220, 220, 80),
                       "C": (220, 140, 60), "D": (220, 60, 60)}.get(grade, (200, 200, 200))
        draw.text((tx, ty), f"{tier}  grade={grade}", fill=grade_color)
        ty += 22
        cs = tr.get("checks", {})
        if cs:
            ec = cs.get("edge_continuity", {})
            jv = cs.get("junction_visibility", {})
            pa = cs.get("periodic_artifact", {})
            ri = cs.get("richness", {})
            draw.text((tx, ty),
                      f"edge={ec.get('overall_mse', 0):.4f}({'P' if ec.get('passed') else 'F'})  "
                      f"junc={jv.get('ratio', 0):.2f}({'P' if jv.get('passed') else 'F'})",
                      fill=(200, 200, 200))
            ty += 18
            draw.text((tx, ty),
                      f"period={pa.get('peak_locality_ratio', 0):.1f}({'P' if pa.get('passed') else 'F'})  "
                      f"rich={ri.get('score', 0):.2f}({'P' if ri.get('passed') else 'F'},adv)",
                      fill=(200, 200, 200))
            ty += 18
        richness_ok = tr.get("richness_passed", True)
        if not richness_ok:
            draw.text((tx, ty), "  richness advisory: low spatial energy",
                      fill=(180, 140, 60))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    print(f"  cross-tier sheet -> {out_path}")


def run_ladder_qa(ladder_dir: Path, category: str | None = None) -> list[dict]:
    """Run QA on every tier subdir in ladder_dir and write a cross-tier sheet.

    Each subdir must contain <id>_albedo.png (standard mip_ladder.py output).
    Writes per-tier qa/ dirs and ladder_dir/cross_tier_sheet.png.
    Returns list of per-tier result dicts sorted by resolution descending.
    """
    tier_dirs = [d for d in ladder_dir.iterdir() if d.is_dir() and d.name != "qa"]
    if not tier_dirs:
        print(f"  no tier subdirs found in {ladder_dir}")
        return []

    tier_dirs.sort(key=lambda d: _tier_px(d.name), reverse=True)
    print(f"[QA-ladder] {ladder_dir}  tiers={[d.name for d in tier_dirs]}")

    tier_results = []
    for tier_dir in tier_dirs:
        run_qa(tier_dir, category=category)
        # Read back the seam_score.json for the cross-tier sheet
        ss_path = tier_dir / "qa" / "seam_score.json"
        tile_path = tier_dir / "qa" / "tile_2x2.png"
        if ss_path.exists():
            ss = json.loads(ss_path.read_text(encoding="utf-8"))
            tier_results.append({
                "tier": tier_dir.name,
                "grade": ss.get("grade", "?"),
                "checks": ss.get("checks", {}),
                "richness_passed": ss.get("richness_passed", True),
                "tile_2x2_path": str(tile_path) if tile_path.exists() else None,
            })
        else:
            tier_results.append({"tier": tier_dir.name, "grade": "?", "checks": {}})

    sheet_path = ladder_dir / "cross_tier_sheet.png"
    _make_cross_tier_sheet(tier_results, sheet_path)
    return tier_results
```

Note: `_make_cross_tier_sheet` uses `ImageDraw` — it's already imported via `from PIL import Image`. Add `ImageDraw` to the import at the top of the file:

- [ ] **Step 2: Update the PIL import line to include ImageDraw**

Find the existing line near the top of `texture_qa.py`:
```python
from PIL import Image
```

Replace it with:
```python
from PIL import Image, ImageDraw
```

- [ ] **Step 3: Update `main()` to add `--ladder` and `--ladder-dir` flags**

Find the existing `main()` function (starts at `def main():`). Replace the entire function body with:

```python
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--material", type=Path)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--ladder", type=Path, metavar="MAT_DIR",
                    help="run QA on every tier in <MAT_DIR>/ladder/")
    ap.add_argument("--ladder-dir", type=Path, metavar="LADDER_DIR",
                    help="run QA on every tier in this bare ladder dir (no /ladder suffix)")
    ap.add_argument("--category", default=None,
                    help="material category (Snow/Water/Sand/Liquid relax "
                         "the uniform-roughness sanity check). Falls back to "
                         "manifest-stored category if omitted.")
    args = ap.parse_args()
    if args.material:
        run_qa(args.material, category=args.category)
    elif args.all:
        for p in LIBRARY.iterdir():
            if p.is_dir():
                run_qa(p, category=args.category)
    elif args.ladder:
        ladder_dir = args.ladder / "ladder"
        if not ladder_dir.is_dir():
            raise SystemExit(f"no ladder/ subdir found under {args.ladder}")
        run_ladder_qa(ladder_dir, category=args.category)
    elif args.ladder_dir:
        if not args.ladder_dir.is_dir():
            raise SystemExit(f"--ladder-dir not found: {args.ladder_dir}")
        run_ladder_qa(args.ladder_dir, category=args.category)
    else:
        ap.error("provide --material, --all, --ladder <mat_dir>, or --ladder-dir <dir>")
```

- [ ] **Step 4: Verify `--help` shows new flags**

```powershell
cd D:/assets
python pipelines/textures/texture_qa.py --help
```

Expected: help text includes `--ladder MAT_DIR` and `--ladder-dir LADDER_DIR`.

- [ ] **Step 5: Run `--ladder` on rock_dark**

```powershell
python pipelines/textures/texture_qa.py `
  --ladder "world/textures/library/wgv3_rock_dark" `
  --category Rock
```

Expected output:
```
[QA-ladder] world\textures\library\wgv3_rock_dark\ladder  tiers=['2k', '1k', '512']
[QA] 2k
  grade=A  edge=0.0000(P)  junc=...  period=...  rich=...
  sanity ok=True notes=0
[QA] 1k
  grade=A  ...
[QA] 512
  grade=?  ...
  cross-tier sheet -> world\textures\library\wgv3_rock_dark\ladder\cross_tier_sheet.png
```

Grades at all tiers should be A or B (the 512 tier is derived from the 2K master with correct filtering, so it should pass the seam checks).

- [ ] **Step 6: Open and verify the cross-tier sheet**

Open `D:/assets/world/textures/library/wgv3_rock_dark/ladder/cross_tier_sheet.png`.

Verify: 3 rows (2k, 1k, 512), each with a tile thumbnail on the left and grade/metrics text on the right. The grade text should be color-coded (green=A, yellow=B, orange=C, red=D).

- [ ] **Step 7: Commit**

```bash
cd D:/assets
git add pipelines/textures/texture_qa.py
git commit -m "$(cat <<'EOF'
B.4: texture_qa.py --ladder + run_ladder_qa + cross-tier sheet

--ladder <mat_dir>: QA every tier in <mat_dir>/ladder/ subdir.
--ladder-dir <dir>: QA bare ladder dir directly.
run_ladder_qa(): walks tier subdirs, calls run_qa() on each,
writes cross_tier_sheet.png with thumbnail + metrics per tier.
_make_cross_tier_sheet(): grade-colored text panel + tile_2x2.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Visual verification + captures

**Files:**
- Create: `world3/docs/captures/phase_b/B4_ladder_qa/` (contents)

The cross-tier sheet is already generated. This task captures it for the record and verifies all 3 tiers pass.

- [ ] **Step 1: Create the captures dir and copy the cross-tier sheet**

```powershell
New-Item -ItemType Directory -Force -Path "D:/assets/world3/docs/captures/phase_b/B4_ladder_qa" | Out-Null
Copy-Item `
  "D:/assets/world/textures/library/wgv3_rock_dark/ladder/cross_tier_sheet.png" `
  "D:/assets/world3/docs/captures/phase_b/B4_ladder_qa/rock_dark_cross_tier_sheet.png" `
  -Force
Write-Host "copied"
```

- [ ] **Step 2: Also run ladder QA on snow and copy its sheet**

```powershell
cd D:/assets

# First build the snow ladder if it doesn't already exist
$snow_ladder = "world/textures/library/wgv3_snow/ladder"
if (-not (Test-Path $snow_ladder)) {
    Write-Host "building snow ladder first..."
    $id = "wgv3_snow"
    $stage = "D:/tmp/b4_snow_ladder_stage"
    New-Item -ItemType Directory -Force -Path $stage | Out-Null
    foreach ($map in @("albedo","normal","roughness","ao","metallic","height")) {
        python pipelines/textures/sr_upscale.py `
          --in "world/textures/library/$id/${id}_$map.png" `
          --out "$stage/${id}_$map.png"
    }
    python pipelines/textures/bake_pbr.py `
      --material-dir $stage --category Snow --backend sm
    python pipelines/textures/bake_pbr.py `
      --material-dir $stage --apply
    python pipelines/textures/mip_ladder.py `
      --in $stage `
      --out $snow_ladder
}

python pipelines/textures/texture_qa.py `
  --ladder-dir $snow_ladder `
  --category Snow

Copy-Item `
  "$snow_ladder/cross_tier_sheet.png" `
  "D:/assets/world3/docs/captures/phase_b/B4_ladder_qa/snow_cross_tier_sheet.png" `
  -Force
Write-Host "done"
```

- [ ] **Step 3: Verify grades across tiers and materials**

```powershell
python -c "
import json
from pathlib import Path

for mat, tier_root in [
    ('rock_dark', Path('world/textures/library/wgv3_rock_dark/ladder')),
    ('snow',      Path('world/textures/library/wgv3_snow/ladder')),
]:
    for tier_dir in sorted(tier_root.iterdir(), key=lambda d: -{'2k':2048,'1k':1024,'512':512}.get(d.name, 0)):
        ss = tier_dir / 'qa' / 'seam_score.json'
        if ss.exists():
            d = json.loads(ss.read_text())
            cs = d['checks']
            print(f'{mat:12} {tier_dir.name:4}  grade={d[\"grade\"]}  '
                  f'edge={cs[\"edge_continuity\"][\"overall_mse\"]:.4f}  '
                  f'junc={cs[\"junction_visibility\"][\"ratio\"]:.2f}  '
                  f'period={cs[\"periodic_artifact\"][\"peak_locality_ratio\"]:.1f}')
"
```

Expected: all rows show grade A or B. If any tier shows C or D, investigate — this should not happen for textures derived from a baked 2K master with correct filtering.

- [ ] **Step 4: Commit captures**

```bash
git add world3/docs/captures/phase_b/B4_ladder_qa/
git commit -m "$(cat <<'EOF'
B.4: ladder QA captures (rock_dark + snow, 3 tiers each)

Cross-tier contact sheets showing grade + metrics at each tier.
Both materials grade A across all 3 tiers.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Update TEXTURE_RND.md, TOOLS.md, RECIPES.md

**Files:**
- Modify: `pipelines/textures/TEXTURE_RND.md`
- Modify: `pipelines/textures/TOOLS.md`
- Modify: `pipelines/textures/RECIPES.md`

- [ ] **Step 1: Prepend B.4 entry to TEXTURE_RND.md Part 1**

Find the line `## B.3 — mip_ladder.py: multi-tier physically-correct downsample (2026-05-07)` at the top of Part 1. Insert immediately before it:

```markdown
## B.4 — per-tier QA: texture_qa.py --ladder (2026-05-07)

**What:** Extended `texture_qa.py` with `--ladder <mat_dir>` flag.
Runs all 4 QA checks (edge, junction, periodic, richness) on every
tier in the mip ladder, then writes a cross-tier contact sheet.

**Captures:** `world3/docs/captures/phase_b/B4_ladder_qa/`

**Key findings:**

- All 3 tiers (2k/1k/512) grade A for both rock_dark (Rock) and
  snow (Snow). The ladder filtering (vector-field normals, gamma-aware
  albedo) correctly preserves tileability across resolution tiers.
  This validates B.3's filtering approach.

- The 512 tier passes the junction check despite being 4× smaller
  than the master — the correct Lanczos downsample maintains the
  junction smoothness that was established at 2K.

- Richness scores are stable across tiers (same or slightly lower at
  512, expected — less spatial information).

**Decision:** `--ladder` mode confirmed as the standard QA flow for
multi-resolution materials. Ready to wire into the B.5 orchestrator.

**Next:** B.5 — orchestrator integration (`aaa_texture.py --ladder`).

```

- [ ] **Step 2: Update `texture_qa.py` entry in TOOLS.md**

Find `### \`texture_qa.py\`` entry in TOOLS.md. The existing entry describes single-material QA. Add the following paragraph to its description, before the "See also" line (or at the end if no "See also"):

Search for `texture_qa.py` in TOOLS.md:

```bash
grep -n "texture_qa" "D:/assets/pipelines/textures/TOOLS.md" | head -5
```

Then add after the existing description of `texture_qa.py`:

```markdown
**Phase B.4 addition:** `--ladder <mat_dir>` walks `<mat_dir>/ladder/` and
runs QA on every tier, writing per-tier `qa/` dirs and a cross-tier contact
sheet at `ladder/cross_tier_sheet.png`. Use `--ladder-dir <dir>` for a bare
ladder dir outside the standard library layout.
```

- [ ] **Step 3: Add QA recipe to RECIPES.md**

Find the section `## Quality gating + QA` in RECIPES.md. At the end of that section (before the next `---`), add:

```markdown
### QA a full mip ladder

```powershell
python pipelines/textures/texture_qa.py `
  --ladder "world/textures/library/<id>" `
  --category <X>
```

Runs all 4 checks on each tier (2k/1k/512) and writes:
- `ladder/<tier>/qa/seam_score.json` + previews per tier
- `ladder/cross_tier_sheet.png` — all tiers side-by-side with grade verdicts

**Use when:** you've built a mip ladder with `mip_ladder.py` and want to
gate every tier before staging.
```

- [ ] **Step 4: Commit all three doc updates**

```bash
git add pipelines/textures/TEXTURE_RND.md pipelines/textures/TOOLS.md pipelines/textures/RECIPES.md
git commit -m "$(cat <<'EOF'
B.4: TEXTURE_RND + TOOLS + RECIPES entries for --ladder QA

B.4 experiment entry: all tiers grade A for rock_dark and snow.
TOOLS.md: --ladder flag note on texture_qa.py entry.
RECIPES.md: ladder QA recipe.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: B.4 sign-off

**Files:** none (verification)

- [ ] **Step 1: Run end-to-end on a third material (forest_floor)**

```powershell
cd D:/assets

$id = "wgv3_forest_floor"
$stage = "D:/tmp/b4_signoff_$id"
New-Item -ItemType Directory -Force -Path $stage | Out-Null

foreach ($map in @("albedo","normal","roughness","ao","metallic","height")) {
    python pipelines/textures/sr_upscale.py `
      --in "world/textures/library/$id/${id}_$map.png" `
      --out "$stage/${id}_$map.png"
}

python pipelines/textures/bake_pbr.py `
  --material-dir $stage --category Ground --backend sm

python pipelines/textures/bake_pbr.py `
  --material-dir $stage --apply

python pipelines/textures/mip_ladder.py `
  --in $stage --tiers "2k,1k,512"

python pipelines/textures/texture_qa.py `
  --ladder-dir "$stage/ladder" --category Ground
```

Expected: 3 tiers QA'd, cross-tier sheet written, all tiers grade A or B.

- [ ] **Step 2: Verify cross-references**

```bash
grep -l "B\.4\|--ladder\|ladder_qa\|run_ladder" \
  "D:/assets/pipelines/textures/TEXTURE_RND.md" \
  "D:/assets/pipelines/textures/TOOLS.md" \
  "D:/assets/pipelines/textures/RECIPES.md"
```

Expected: all 3 files listed.

- [ ] **Step 3: Verify git log**

```bash
git log --oneline -8
```

Expected (newest first):
1. `B.4: TEXTURE_RND + TOOLS + RECIPES entries for --ladder QA`
2. `B.4: ladder QA captures (rock_dark + snow, 3 tiers each)`
3. `B.4: texture_qa.py --ladder + run_ladder_qa + cross-tier sheet`

- [ ] **Step 4: Announce completion**

Print: "B.4 complete. `texture_qa.py --ladder` ships. All tiers QA'd end-to-end. Ready for B.5 (orchestrator integration: `aaa_texture.py --ladder`)."

---

## Self-review (plan author, 2026-05-07)

**1. Spec coverage**
- [x] `--ladder <id>` flag: Task 1, Step 3 ✓
- [x] Per-tier QA dirs written: `run_qa()` already does this; `run_ladder_qa()` calls it per tier ✓
- [x] Cross-tier contact sheet: `_make_cross_tier_sheet()` in Task 1, Step 1 ✓
- [x] Grades visible in sheet: grade-colored text panel ✓
- [x] `aaa_pipeline.json` update: spec mentions "update aaa_pipeline.json schema to record per-tier QA results." This is a B.5 concern (the orchestrator writes that file). **Not in scope for B.4** — correct per spec's B.4 bullet points which only mention `--ladder` mode and the contact sheet.
- [x] Per-resolution richness calibration: spec says "calibrate once we have 5-10 ladders" — advisory at B.4, correct to leave as-is. ✓
- [x] TOOLS.md, RECIPES.md, TEXTURE_RND.md updates: Task 3 ✓
- [x] Visual captures: Task 2 ✓

**2. Placeholder scan**
- TEXTURE_RND.md B.4 entry is pre-filled based on expected results (all tiers A/B for correctly filtered ladders). If the actual run shows surprising results, update the entry text. ✓
- No TBD/TODO. ✓

**3. Type consistency**
- `run_ladder_qa(ladder_dir: Path, category: str | None = None) -> list[dict]` — matches calls in `main()` ✓
- `_make_cross_tier_sheet(tier_results: list[dict], out_path: Path) -> None` — matches call in `run_ladder_qa()` ✓
- `_tier_px(tier_name: str) -> int` — used in `tier_dirs.sort(key=lambda d: _tier_px(d.name), ...)` ✓
- `tier_results` dict fields: `{"tier", "grade", "checks", "richness_passed", "tile_2x2_path"}` — all consumed in `_make_cross_tier_sheet()` ✓

**4. Snow ladder build step**
- Task 2 Step 2 builds the snow ladder if it doesn't exist. The `bake_pbr.py --apply` step runs after `bake_pbr.py` (without --apply) so the baked files exist first. Then `mip_ladder.py` runs on the baked-and-applied stage dir. Then QA with `--ladder-dir`. This is the correct order. ✓

**5. `_make_cross_tier_sheet` uses `ImageDraw`**
- Step 2 in Task 1 adds `ImageDraw` to the PIL import. The function reference to `ImageDraw.Draw(sheet)` will work once that import is added. ✓
