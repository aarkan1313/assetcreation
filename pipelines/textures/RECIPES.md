# Texture Pipeline Recipes

Canonical commands for common tasks, organized by **what you want to
do** (not by what the pipeline is doing internally).

This is the operator's guide — quick lookup for the right invocation.
For *why* and *how*, see:
- [PIPELINE.md](PIPELINE.md) — runbook (stages, presets, failure modes)
- [TOOLS.md](TOOLS.md) — per-tool inventory
- [TEXTURE_RND.md](TEXTURE_RND.md) — experiment log + prompt cookbook
- [LESSONS.md](LESSONS.md) — surprises that bit us

---

## Prerequisites (every session)

```powershell
$env:PYTHONIOENCODING = "utf-8"
cd D:/assets

# Verify ComfyUI is running on 127.0.0.1:8188
curl -fsS http://127.0.0.1:8188/system_stats

# If down:
& "D:\assets\animators\ComfyUI\venv\Scripts\python.exe" `
  "D:\assets\animators\ComfyUI\main.py" --listen 127.0.0.1 --port 8188
```

---

## Generating textures

### Default ship-quality texture (most common case)

```powershell
python pipelines/textures/aaa_texture.py `
  --prompt "<cookbook prompt>" `
  --id <id> `
  --category <Ground|Rock|Snow|Sand|Foliage|...>
```

Uses StableMaterials for PBR. ~3-4 min on 5090. Targets grade B
minimum. Output at `world/textures/library/<id>/`.

**Use when**: you want a tileable PBR set for a known material with a
prompt from `TEXTURE_RND.md` Part 2 cookbook. This is the default
path; reach for it first.

### Hero-quality rock or hard-edge material

```powershell
python pipelines/textures/aaa_texture.py `
  --prompt "<cookbook prompt>" `
  --id <id> `
  --category Rock `
  --quality strict `
  --pbr-backend chord_sm_rough
```

Uses CHORD (sharp normals + clean heights, no center-bias bloom) plus
SM for roughness only (varied, physically plausible vs CHORD's
near-flat). ~5-6 min total. **Highest-quality rock recipe in the
pipeline.** Targets grade A.

**Use when**: a rock-class material is going close to the camera or
matters as a hero asset. Skip for sand/snow/water/liquid (uniform
roughness is correct there).

### Quick iteration / prompt-testing

```powershell
python pipelines/textures/aaa_texture.py `
  --prompt "<draft prompt>" `
  --id <test_id> `
  --quality fast
```

Skips StableMaterials; uses heuristic `derive_pbr_v2` for PBR. ~1
minute. Targets grade C minimum. **Don't ship this output.**

**Use when**: iterating on a prompt and you just need to see how the
albedo lands before committing to a full run.

### Reference-anchored generation (composite materials)

```powershell
python pipelines/textures/flux_seamless.py `
  --prompt "<text prompt>" `
  --id <id> `
  --reference-image <path/to/photo.png> `
  --reference-mode anchor `
  --reference-denoise 0.78
```

Anchors FLUX on a reference image at varying strength:
- `0.88` — subtle tint, mostly text-driven
- `0.78` — moderate hybrid, reference structure visible
- `0.70` — strong anchor, "X over Y" composite ("snow over leaves")
- `<0.65` — reference dominates, prompt mostly ignored

**Note**: this only generates the albedo. To get a full PBR set, run
`aaa_texture.py` against the resulting image (or wire it through
manually). Not yet exposed via `aaa_texture.py --reference-image`.

**Use when**: you have a real-world reference photo for material
accuracy, OR you want a composite "X on top of Y" effect, OR you
want to enforce kit cohesion by using one anchor across several
generations.

---

## Building biome kits

### Auto-generate a biome from scratch

```powershell
python pipelines/textures/kit_generator.py `
  --biome <biome_name>
```

Highest-level tool: takes a biome name and auto-orchestrates a
palette-locked texture set via `palette_lock.py`. Picks prompts
either from an LLM-generated brief or from a JSON recipe.

### Manual palette-locked kit

```powershell
python pipelines/textures/aaa_texture.py --prompt "<anchor>" --id <kit>_anchor

python pipelines/textures/palette_lock.py `
  --kit <name> --anchor <kit>_anchor `
  --add "<prompt>:<id>:<Category>" `
  --add "<prompt>:<id>:<Category>" `
  --strength 0.6

python pipelines/textures/biome_consistency.py --kit <name>
```

Three-step manual kit build: anchor → palette-lock the rest →
verify cohesion.

### Re-roll an anchor and re-lock the kit to it

```powershell
python pipelines/textures/relock_palette.py `
  --anchor <new_anchor_id> `
  --members <id1> <id2> <id3> `
  --strength 0.6
```

**Use when**: you regenerated the anchor (it wasn't right) and want
the rest of the kit to follow without re-running each member.

---

## Rescuing problem materials

### Lattice-prone material (all variants share periodic artifacts)

```powershell
# 1. Generate variants with --keep-all so they're inspectable
python pipelines/textures/variant_select.py `
  --prompt "<prompt>" --id <id> --variants 4 --seed-base <N> `
  --keep-all

# 2. Blend them into one tile (sharpness=12 for rescue mode)
python pipelines/textures/variant_blend.py `
  --id <id> --variants 4 `
  --out world/textures/library/<id>_blend `
  --sharpness 12
```

**Use when**: prompt rewrites + seed changes haven't escaped the
lattice. Reduces severity (lower periodic_locality) at the cost of
slightly worse edges. Manual rescue, not the orchestrator default.
See TEXTURE_RND "A.9" for the trade-space.

### Texture has bad seams after generation

```powershell
python pipelines/textures/seam_repair.py `
  --material world/textures/library/<id> `
  --threshold 0.005 `
  --patch 64
```

In-place repair. Originals saved as `*.pre_repair.<ext>`.

### Repair pass made things worse

```powershell
python pipelines/textures/seam_repair.py `
  --material world/textures/library/<id> --restore
```

Copies all `*.pre_repair.<ext>` files back.

### Texture is too soft (don't want to regenerate)

```powershell
python pipelines/textures/high_pass_detail.py `
  --in world/textures/library/<id> --sharpen --gain 1.3
```

**Use when**: the prompt nailed the material but the result looks
muted. Cheap to undo (originals get backed up).

---

## Upscaling

### Upscale a single map (Real-ESRGAN, default)

```powershell
python pipelines/textures/sr_upscale.py `
  --in <path/to/map.png> `
  --out <path/to/map_4x.png>
```

4× super-resolution via ComfyUI's UpscaleModelLoader + Real-ESRGAN
x4plus. ~2s per 512→2048 map on 5090. Tile-preserving via
offset+heal trick.

**Use when:** you need any single tileable PNG (albedo, height, etc.)
upscaled to 4×. This is the default SR tool for the Phase B
multi-resolution pipeline.

### Upscale + heal pass (FLUX, for FLUX-style coherence)

```powershell
python pipelines/textures/flux_upscale.py `
  --input <path/to/albedo.png> `
  --output <path/to/albedo_2k.png> `
  --target 2048
```

Bilinear upscale + FLUX img2img low-denoise heal pass. Slower (~60-90s)
than Real-ESRGAN; produces "more FLUX-coherent" output that matches
generation style. Albedo only. Seam score ~0.00123 (coherence-focused).

**Use when:** you need a near-shipping albedo polished to recover FLUX
style after some other transformation. For multi-map SR, use
`sr_upscale.py` instead.

### Lanczos baseline (no-ComfyUI fallback)

```powershell
python pipelines/textures/upscale_biome_set.py `
  --set <set_id> --factor 4
```

Pure PIL Lanczos upscale of every PBR map in a biome set. No model
required, no ComfyUI required. Quality is meaningfully worse than
Real-ESRGAN but works with no install. Backs up originals to
`_original_<map>.png`.

**Use when:** ComfyUI isn't available or you want a deterministic
quick-and-dirty upscale.

---

## Baking high-res PBR maps (after SR)

### Re-derive normal/AO/roughness from SR'd output

```powershell
# Step 1: SR all maps into a staging dir (library-style names — no _2k suffix)
$id = "wgv3_rock_dark"
New-Item -ItemType Directory -Force -Path "D:/tmp/${id}_sr" | Out-Null
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
height+albedo. Normal: sub-texel Sobel gradient (replaces ESRGAN's
color-corrupted SR'd normal). AO: smoother hemisphere integral.
Roughness: blend of SR'd (65%) + derived (35%) for sm/chord_sm_rough backends.

**Use when:** you've SR'd a material and want physically-correct high-res
maps before writing the mip ladder (B.3). This is the standard second step
of the multi-resolution pipeline.

**Backend roughness trust:** `sm`/`chord_sm_rough` → 65% SR + 35% derived
(SM roughness is physically modeled). `chord` → 35% SR + 65% derived
(CHORD roughness is near-flat). `derive` → 40% SR + 60% derived.

**Important:** Use library-style output names in the staging dir (no `_2k`
suffix in the filename) so that `bake_pbr.py`'s `find_map()` and `apply_baked()`
produce correctly-named outputs that match the library convention.

---

## Building the mip ladder (after bake)

### Write 2K/1K/512 tiers from a baked master

```powershell
# Full 3-step SR + bake + mip pipeline
$id = "wgv3_rock_dark"
New-Item -ItemType Directory -Force -Path "D:/tmp/${id}_sr" | Out-Null

# Step 1: SR all maps into staging dir (library-style names)
foreach ($map in @("albedo","normal","roughness","ao","metallic","height")) {
    python pipelines/textures/sr_upscale.py `
      --in "world/textures/library/$id/${id}_$map.png" `
      --out "D:/tmp/${id}_sr/${id}_$map.png"
}

# Step 2: Bake (promotes baked -> canonical in staging dir)
python pipelines/textures/bake_pbr.py `
  --material-dir "D:/tmp/${id}_sr" `
  --category Rock --backend chord_sm_rough --apply

# Step 3: Write ladder from baked master
python pipelines/textures/mip_ladder.py `
  --in "D:/tmp/${id}_sr" `
  --tiers "2k,1k,512"

# Output: D:/tmp/<id>_sr/ladder/2k/  1k/  512/
#   Each tier: 6 PBR maps at that resolution
```

Ladder output is at `<src>/ladder/<tier>/`. Each tier contains 6 PBR maps
with per-map correct filtering: normal (vector-field, no fading at lower tiers),
albedo (gamma-aware, no dark bias), others (linear Lanczos).

**Use when:** you want to ship a material at multiple resolution tiers
(e.g. 2K for hero views, 1K for standard terrain, 512 for distance).
This is the standard full multi-resolution pipeline.

**After B.5**, `aaa_texture.py --ladder` will run all three steps in one command.

---

## Quality gating + QA

### Re-grade an existing texture

```powershell
python pipelines/textures/texture_qa.py `
  --material world/textures/library/<id> `
  --category <X>
```

Re-runs the 4-check QA (edge / junction / periodic / richness-advisory)
and writes `qa/seam_score.json`, `qa/sanity.json`, `qa/tile_2x2.png`,
plus sphere/plane previews.

### Re-grade everything (after a metric update)

```powershell
python pipelines/textures/texture_qa.py --all
```

Walks every dir under `world/textures/library/` and refreshes the QA
output.

### QA a full mip ladder

```powershell
python pipelines/textures/texture_qa.py `
  --ladder "world/textures/library/<id>" `
  --category <X>
```

Runs all 4 checks on each tier (2k/1k/512) and writes:
- `ladder/<tier>/qa/seam_score.json` + previews per tier
- `ladder/cross_tier_sheet.png` — all tiers side-by-side with grade verdicts

Use `--ladder-dir <dir>` to point at a bare ladder dir outside the standard
library layout (e.g. a staging dir from `bake_pbr.py`).

**Use when:** you've built a mip ladder with `mip_ladder.py` and want to
gate every tier before staging.

### Verify a texture fits its biome kit

```powershell
python pipelines/textures/biome_consistency.py `
  --kit <kit_name> `
  --candidate <id>
```

Compares LAB distribution + RGB histogram against the kit anchor.
Verdict: `in_palette` / `drift` / `way_off`. Advisory; some slots
(snow, contrast rocks) legitimately read `way_off`.

---

## Detail layers + macro variation

### Generate a paired detail layer for an existing texture

```powershell
# Authored detail (separate FLUX run, ~3 min)
python pipelines/textures/detail_variant.py --of <id> --strength 0.5

# Procedural detail (free, instant — high-pass extraction)
python pipelines/textures/high_pass_detail.py --in world/textures/library/<id>
```

The first produces a *new* texture trained as a fine-detail companion;
the second derives a high-pass crop from the existing albedo.

### Generate a macro+detail pyramid from scratch

```powershell
python pipelines/textures/detail_pyramid.py --prompt "<material>"
```

Generates both layers in one shot for the macro+detail shader stack
(terrain_hex_detail).

---

## Sweeps + experiments

### Same-prompt × N seeds

```powershell
python pipelines/textures/experiment.py `
  --name <sweep_name> `
  --mode seeds --category <X> `
  --prompt "<prompt>" `
  --seeds 100 200 400
```

Output at `D:/tmp/world3_experiments/<sweep_name>/` with contact
sheet + manifest.

### Compare prompts (4 prompts × N seeds)

```powershell
python pipelines/textures/experiment.py `
  --name <sweep_name> `
  --mode prompts --category <X> `
  --prompts-file <prompts.json> `
  --seeds 100 200 400
```

JSON file is a list of `{label, prompt}` entries.

### Sweep settings (variants count, heal_strength)

```powershell
python pipelines/textures/experiment.py `
  --name <sweep_name> `
  --mode settings --category <X> `
  --prompt "<prompt>" --seeds 100 `
  --variants-list 4 6 8 `
  --heal-list 0.25 0.35 0.45
```

**Avoid seed 300** as a default — A.2 found it produces lattice
failures on most categories. Use 100/200/400.

---

## Staging into world3

After generating textures into `world/textures/library/<id>/`, stage
into the world3 Godot project:

```powershell
$SRC = "D:/assets/world/textures/library/<id>"
$DST = "D:/assets/world3/textures/wgv3/<name>"
foreach ($m in @("albedo","normal","roughness","metallic","height","ao")) {
  Copy-Item "$SRC/<id>_$m.png" "$DST/$m.png" -Force
}
Copy-Item "$SRC/qa/tile_2x2.png" "$DST/_tile_2x2.png" -Force

# Reimport so Godot picks up new files
& "C:/Godot/Godot_v4.5-stable_win64.exe" --path "D:/assets/world3" --headless --import
```

(See `world3/docs/WORKFLOW.md` Stage 4 for the full project-level
flow including material binding.)

---

## Choosing a PBR backend

Four backends available via `--pbr-backend`:

| Backend          | Speed | Quality      | Use when                                                |
|------------------|-------|--------------|---------------------------------------------------------|
| `derive`         | ~1 min | low (heuristic) | quick iteration, idea testing                       |
| `sm` (default)   | ~3 min | good        | normal use; default for `default`/`strict` presets       |
| `chord`          | ~3 min | sharp geometry, **flat roughness** | non-rock or where uniform roughness is correct |
| `chord_sm_rough` | ~5 min | best of both | hero rock-class materials                                |

Pure `chord` flunks the sanity gate on rock-class materials because
its roughness is too flat (std ~0.011). `chord_sm_rough` fixes that
by overwriting just the roughness with SM's. See TEXTURE_RND "A.8"
+ "A.11" for A/B evidence.

---

## Quick reference: PBR map provenance per backend

| Map         | derive             | sm          | chord       | chord_sm_rough |
|-------------|--------------------|-------------|-------------|----------------|
| albedo      | from delight pass  | SM          | CHORD       | CHORD          |
| normal      | sobel of height    | SM          | **CHORD**   | **CHORD**      |
| roughness   | category preset    | SM (rich)   | CHORD (flat) | **SM**        |
| metallic    | ~0                 | SM          | CHORD       | CHORD          |
| height      | freq split         | SM          | **CHORD** (Poisson) | **CHORD** |
| ao          | blur curvature     | derived from height | derived | derived |

Bold = "the strong choice for that map."

---

## Where files end up

```
world/textures/library/<id>/        # generation output
  <id>_<map>.png                    # 6 PBR maps
  <id>_<map>.pre_*.png              # delight / repair / palette / sm-swap backups
  aaa_pipeline.json                 # full pipeline log + grade verdict
  variant_select.json               # variant scores (which seed won)
  qa/                               # tile_2x2, sphere/plane previews, sanity, seam_score
    seam_score.json                 # per-axis pass/fail + thresholds applied
    sanity.json                     # map presence, value ranges, notes
    tile_2x2.png                    # albedo tiled 2x2 (visual seam check)
    sphere_preview.png
    plane_preview.png

world3/textures/wgv3/<name>/        # staged for Godot consumption
  albedo.png  normal.png  roughness.png  metallic.png  height.png  ao.png
  _tile_2x2.png            # 2x2 tile visual check
  _blender_plane.png       # CYCLES preview
  _blender_sphere.png
  material.tres            # StandardMaterial3D
  material_hex.tres        # ShaderMaterial (hex-tile + macro)

D:/tmp/world3_experiments/<name>/   # experiment.py outputs
  contact_sheet.png
  manifest.jsonl

world3/docs/captures/phase_a/       # tracked before/after evidence
  <material>_{before,after}/
  A8_chord_ab/                      # CHORD vs SM comparison
  A9_variant_blend_ab/              # variant_select vs variant_blend
  A10_reference_anchor/             # reference-anchor sweep
  A11_chord_sm_hybrid_ab/           # 3-backend roughness comparison
```

---

## Avoid

- **Avoid `--seed-base 300`** — A.2 sweep found it produces lattice
  failures on 4/5 representative materials. Use 100/200/400 or other
  arbitrary values.
- **Avoid `aerial photograph of [X] field`** as a prompt lead phrase
  — pulls FLUX into satellite-style sparse-objects-on-background
  output, not surface texture (A.3).
- **Avoid directional words** (`ridges`, `striations`, `bands`,
  `wind ripples` for non-sand) — produce visible lattice when tiled
  (A.3, A.6, project-wide rule in TEXTURE_RND Part 2 anatomy).
- **Avoid concurrent `experiment.py` runs with the same `--name`**
  — race-condition each other through shared library paths
  (LESSONS L19).

---

## See also

- [PIPELINE.md](PIPELINE.md) — pipeline runbook (stages, presets, gate logic)
- [TOOLS.md](TOOLS.md) — per-tool inventory
- [TEXTURE_RND.md](TEXTURE_RND.md) — Part 1: experiment log; Part 2: prompt cookbook
- [LESSONS.md](LESSONS.md) — surprises and "why the obvious thing was wrong"
- [EXTERNAL_TECHNIQUES.md](EXTERNAL_TECHNIQUES.md) — survey of external tileable-PBR work (snapshot, 2026-05-07)
- [`world3/docs/WORKFLOW.md`](../../world3/docs/WORKFLOW.md) — project-level workflow (DEM → render)
