# Texture Pipeline

Generate a tileable PBR texture set from a prompt. Output goes to
`world/textures/library/<id>/`. End-to-end runtime: a few minutes per
texture on the RTX 5090.

This is the working contract after the 2026-05-07 fix pass. The
defects that made the previous version produce false-pass textures
are fixed and verified — see `world3/docs/TEXTURE_PIPELINE_FIX_PLAN.md`
for the audit and what changed.

## Run

Prereq: ComfyUI listening on `127.0.0.1:8188`.

```powershell
# Pre-flight (once per shell)
$env:OPENTOPOGRAPHY_API_KEY = [Environment]::GetEnvironmentVariable("OPENTOPOGRAPHY_API_KEY","User")
$env:PYTHONIOENCODING = "utf-8"

# Start ComfyUI in a separate terminal if it isn't already up:
& "D:\assets\animators\ComfyUI\venv\Scripts\python.exe" `
  "D:\assets\animators\ComfyUI\main.py" --listen 127.0.0.1 --port 8188

# Generate one texture
cd D:/assets
python pipelines/textures/aaa_texture.py `
  --prompt "rich brown dirt with small pebbles and fine debris, top-down photo, even lighting, photoreal" `
  --id wgv3_dirt `
  --category Ground `
  --quality default
```

Expected output:
```
DONE: D:\assets\world\textures\library\wgv3_dirt
  prompt:     'rich brown dirt with small pebbles ...'
  quality:    default
  variants:   4
  PBR method: sm
  size:       512x512 (flux at 512)
  grade:      A  edge=0.0009 junc=1.01 period=10.7
  gate:       PASS
```

## Quality presets

| Preset  | Variants | PBR backend | Min grade | Use when                   |
|---------|---------:|-------------|-----------|----------------------------|
| fast    | 2        | derive_pbr_v2 (heuristic) | C | quick iteration, idea testing |
| default | 4        | StableMaterials           | B | normal use                    |
| strict  | 6        | StableMaterials           | A | hero materials                |

`fast` skips the diffusion-based PBR (~1 min total). `default` and
`strict` invoke StableMaterials at its native 512 resolution (~2-3 min
total per texture).

## What happens inside

The orchestrator (`aaa_texture.py`) runs 7 stages:

1. **Variant generation** (`variant_select.py` → `flux_seamless.py`)
   Generates N FLUX 2 klein variants of the albedo at 512×512, each
   with the offset+heal seamless trick. Picks the best by edge MSE.
   Writes `<id>_albedo.png`.

2. **Delight** (`delight.py`)
   LAB-space large-blur subtract to flatten any baked-in lighting
   from the AI generation. Strength 0.3–0.5 by preset. Writes
   `<id>_albedo.pre_delight.png` as backup; updates the main albedo
   in-place.

3. **PBR estimation** — one of (override with `--pbr-backend`):
   - `stablematerials_image2pbr.py` (default/strict; `--pbr-backend sm`):
     diffusion model trained for tileable PBR; outputs aligned albedo/
     normal/roughness/metallic/height at 512 native. ~25s on 5090.
     **License: OpenRAIL (commercial OK).**
   - `chord_image2pbr.py` (`--pbr-backend chord`, opt-in): Ubisoft La
     Forge's CHORD model (SIGGRAPH Asia 2025). Outputs basecolor/
     normal/roughness/metalness at 1024 native, plus Poisson-derived
     height. ~30s on 5090. Beats SM on hard-edge geometry (rock,
     stone — sharper normals, cleaner heights, no center-bias bloom).
     **Loses on rock roughness** (CHORD's roughness is near-flat,
     fails existing sanity check on Rock category).
     **License: Ubisoft Machine Learning License (Research-Only
     Copyleft).** Requires `chord_v1.safetensors` (gated on HF) and
     a transformers 5.x compat patch in custom_nodes/ComfyUI-Chord/
     nodes.py — see TEXTURE_RND.md "A.8" entry.
   - `derive_pbr_v2.py` (fast; `--pbr-backend derive`): heuristic from
     albedo only — height from frequency split, normal from height
     sobel, AO from blurred curvature, roughness from category preset.

4. **Seam repair** (`seam_repair.py`)
   Self-contained (discovers maps by filename, no catalog
   dependency). Skips if albedo edge MSE is below threshold. When it
   runs, applies offset+quilt+offset to every map, keeping all maps
   spatially aligned. Backups originals as `<id>_<map>.pre_repair.png`.

5. **Texture QA** (`texture_qa.py`)
   Three orthogonal *defect* checks (count toward A/B/C/D grade) plus
   one *content-presence* check (advisory; printed but not graded).
   Each defect check must pass for grade A; 2 of 3 = B, 1 of 3 = C,
   0 of 3 = D.
   - **edge_continuity** — 1-pixel border MSE between opposite edges.
     Catches gross discontinuities. Pass: <0.005.
   - **junction_visibility** — Laplacian energy in the 2×2-tile seam
     region vs. interior. Catches healed-but-still-visible center
     seams. Pass: ratio <1.35.
   - **periodic_artifact** — FFT power spectrum. Finds the brightest
     localized peak anywhere outside DC, compares to its surrounding
     neighborhood. Catches lattices, FLUX center bias, and structured
     repetition. Pass: locality ratio < per-category threshold (table
     below; defaults to 18).
   - **richness** *(advisory; landed A.7 / 2026-05-07)* — content-
     presence check. Defends against the "smooth A" failure mode
     (LESSONS L16 — visually featureless texture that grades A on
     defects). Score: `0.5 * (luminance_entropy/5 +
     gradient_p99_normalized/0.4)`. Pass: score >= per-category
     threshold (Snow/Water/Liquid 0.45, Sand 0.80, others 0.83).
     **Currently advisory**: computed and logged on every QA run but
     NOT folded into the A/B/C/D grade. Promote to gate after a few
     sessions of watching it produce sensible scores.
   Writes `qa/seam_score.json`, `qa/summary.json`, `qa/tile_2x2.png`,
   `qa/sphere_preview.png`, `qa/plane_preview.png`, `qa/sanity.json`.

   **Per-category threshold overrides** (`CATEGORY_THRESHOLDS` in
   `texture_qa.py`): different materials have different fundamental
   tileability properties. Brick/Tile/Cobble are *intentionally*
   periodic; rocks have natural micro-repetition; snow/water/sand are
   genuinely uniform.

   | Category   | Periodic threshold | Richness threshold (advisory) |
   |------------|-------------------:|------------------------------:|
   | Brick      | 80                 | (uses default)                |
   | Cobble     | 80                 | (uses default)                |
   | Tile       | 80                 | (uses default)                |
   | Wood       | 50                 | (uses default)                |
   | Metal      | 30                 | 0.60 — polished narrow lum range |
   | Concrete   | 25                 | 0.83                          |
   | Foliage    | 25                 | 0.83                          |
   | Rock       | 25                 | 0.83                          |
   | Ground     | 22                 | 0.83                          |
   | Sand       | 18                 | 0.80                          |
   | Snow/Water/Liquid      | 18      | 0.45 — legit low spatial energy |
   | (default)  | 18                 | 0.83                          |

   **Sanity-check exceptions**: categories in
   `UNIFORM_ROUGHNESS_OK_CATEGORIES` (Snow, Water, Sand, Liquid) skip
   the "roughness has near-zero variance" check, since those materials
   have legitimately flat roughness.

6. **Blender PBR preview** (`blender_preview.py`, best-effort)
   Real CYCLES render of the texture on a sphere and a tilted plane
   under HDRI lighting. Optional — fails silently if Blender isn't
   installed at the expected path.

7. **Quality gate**
   Logical AND of:
   - seam grade ≥ preset's `min_grade`
   - sanity_ok (map ranges look sensible; expected maps present)
   - ≥4 of {albedo, normal, roughness, height} present
   Records per-failure reasons in `aaa_pipeline.json` under `gate.failures`.

8. **Catalog** (`world/textures/catalog/materials.jsonl`)
   Append a record with prompt, preset, all three seam check numbers,
   grade, gate verdict, and gate failures. One JSON line per texture.

## Output layout

Generation puts everything under `world/textures/library/<id>/`:

```
world/textures/library/<id>/
  <id>_albedo.png          # 512×512, sRGB
  <id>_normal.png          # 512×512, GL convention (Y+ up)
  <id>_roughness.png       # 512×512, linear
  <id>_metallic.png        # 512×512, linear
  <id>_height.png          # 512×512, linear, bicubic-friendly
  <id>_ao.png              # 512×512, linear (derived from height if SM)
  <id>_albedo.pre_delight.png      # delight backup
  <id>_<map>.pre_repair.png        # repair backup (only if repair ran)
  aaa_pipeline.json        # per-stage log + grade + gate verdict
  qa/
    seam_score.json        # raw three-check numbers
    summary.json           # compact + sanity notes
    tile_2x2.png           # albedo tiled 2×2 (visual seam check)
    sphere_preview.png     # albedo on synthetic lambert sphere
    plane_preview.png      # albedo on synthetic tilted plane
    sanity.json            # map range checks
    blender_sphere.png     # CYCLES PBR sphere render (optional)
    blender_plane.png      # CYCLES PBR plane render (optional)
```

### Staging into world3

For consumption by the world3 renderer, a curated subset of textures
is staged at `world3/textures/wgv3/<name>/` with a flat per-material
layout:

```
world3/textures/wgv3/<name>/
  albedo.png  normal.png  roughness.png  metallic.png  height.png  ao.png
  _tile_2x2.png            # tiled 2×2 albedo for visual review
  _blender_plane.png       # Blender CYCLES preview
  _blender_sphere.png
  material.tres            # StandardMaterial3D (baseline)
  material_hex.tres        # ShaderMaterial (hex-tile + macro variation)
```

The staging copy uses bare map names (`albedo.png` not `wgv3_dirt_albedo.png`)
so that material.tres bindings are name-agnostic. See
`world3/pipeline/build_kit_materials.py` for the per-kit
terrain_blend.tres generator.

## Common failure modes

| Symptom                          | Likely cause                                   | Fix                                     |
|----------------------------------|------------------------------------------------|-----------------------------------------|
| "gate FAIL: grade=C ..."         | Seam, lattice, or junction check failed        | Try `--seed-base <new>` or `--variants 8` |
| "gate FAIL: sanity: roughness has near-zero variance" | Material has naturally uniform roughness (e.g. snow) | Pass `--no-gate`; the texture is fine    |
| "no images from upscale heal"    | ComfyUI crashed or ran out of VRAM             | Restart ComfyUI; check `system_stats`   |
| "TimeoutError: prompt did not complete within 1200s" | FLUX took too long; usually means model misload | Check ComfyUI console; restart it       |
| Pipeline runs but output looks bad | FLUX went off-prompt for the material      | Reword prompt; avoid words that trigger model bias (e.g. "lattice", "grid") |

## Restoring an original

If a generated texture's repair pass made things worse (rare), restore
the pre-repair version:

```powershell
python pipelines/textures/seam_repair.py --material <library_dir> --restore
```

Copies all `*.pre_repair.<ext>` files back over their originals.

## Re-grading existing textures

When the QA metric is updated, re-run it across the library to refresh
all `qa/summary.json` files:

```powershell
python pipelines/textures/texture_qa.py --all
```

## Beyond a single texture: kits + detail variants

Two higher-level workflows wrap `aaa_texture.py`:

### `palette_lock.py` — biome-cohesive kit generation

When you generate textures independently they end up with mismatched
saturation/hue/contrast — the "this biome is three random materials"
look. `palette_lock.py` generates a kit of textures and palette-pulls
each toward an anchor texture's color distribution.

```powershell
python pipelines/textures/palette_lock.py `
  --kit alpine_set --anchor wgv3_rock_dark `
  --add "moss-covered boulder, top-down photo:wgv3_alpine_moss:Foliage" `
  --add "scree slope, top-down photo:wgv3_alpine_scree:Rock" `
  --strength 0.6
```

`--strength 0` = no palette change, 1.0 = full match (pulls both
textures into the anchor's exact color space). 0.6 keeps each
texture's character while unifying the family.

Output: each new texture has an `_albedo.pre_palette.png` backup,
plus a kit manifest at `art_lab/biomes/kits/<kit>_palette.json` that
records which materials belong to which kit. QA is re-run after the
match so the manifest reflects the final state.

### `detail_variant.py` — detail-layer companion texture

The macro+detail shader (world3) samples a PBR set at two UV scales.
A "detail variant" is a separate PBR set authored for the detail
scale: smaller features, higher contrast, same color family.

```powershell
python pipelines/textures/detail_variant.py --of wgv3_rock_dark --strength 0.5
```

Generates `wgv3_rock_dark_detail` with a category-aware
"close-up macro, fine grain" prompt suffix and a different seed,
then palette-matches to the parent. Tags the manifest with
`role: detail_variant` and `parent: <id>`.

## What's deliberately NOT in this pipeline

- **Material Anything image-to-PBR.** Broken for 2D textures (model
  needs multi-view 3D consolidation). Adapter exists but is unused.
- **Beyond 512.** StableMaterials trains at 512; LANCZOS-upscaling its
  output to 1024 doesn't add detail, just stretches. For terrain via
  triplanar, 512 is plenty.
- **Hex-tile or stochastic sampling.** That belongs in the renderer's
  shader, not the texture itself. See world3 Phase 1b.
- **patina_adapter.** Exists; not wired in. Useful when we want
  weathered/aged variants of clean materials.

## Tweaking individual stages

Each stage script can be run standalone for debugging:

```powershell
# Just the seam metric on an existing texture
python pipelines/textures/texture_qa.py --material world/textures/library/wgv3_dirt

# Just seam repair (skips threshold gate with --force)
python pipelines/textures/seam_repair.py --material world/textures/library/wgv3_dirt --force

# Just delight (output replaces albedo, with pre_delight backup)
python pipelines/textures/delight.py --material world/textures/library/wgv3_dirt --strength 0.5
```
