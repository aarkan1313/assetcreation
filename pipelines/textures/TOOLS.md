# Texture Pipeline — Tool Menu

Every script in this directory, what it does, when to reach for it.
Sorted by typical use frequency, not alphabetical.

The pipeline is **additive** — these are options you can mix-and-match.
Most workflows use a small subset; this doc is the menu of what exists.

## Daily-use tools

### `aaa_texture.py` — orchestrator
The main entry point. One command produces a full PBR set.
```powershell
python aaa_texture.py --prompt "..." --id name --category Ground --quality default
```
Stages: variant generation → delight → PBR estimation (StableMaterials)
→ seam repair → 3-check QA → optional Blender preview → multi-rule gate
→ catalog. See [PIPELINE.md](PIPELINE.md) for full mechanics.

### `palette_lock.py` — biome-cohesive kit generation
Generates several textures with shared color palette pulled from an
anchor texture. Used to build a biome kit (5 textures matching).
```powershell
python palette_lock.py --kit alpine_set --anchor wgv3_rock_dark `
  --add "moss boulder, top-down photo:wgv3_alpine_moss:Foliage" `
  --strength 0.6
```

### `texture_qa.py` — re-grade textures
Re-runs the 3-check QA + sanity check on existing texture(s). Useful
after manual edits or when QA thresholds change.
```powershell
python texture_qa.py --material world/textures/library/wgv3_dirt
python texture_qa.py --all  # re-grade everything
```

## Generation variants

### `detail_variant.py` — paired detail-layer texture
Generates a "detail variant" of an existing texture: smaller features,
higher contrast, palette-locked to the parent. Used for the macro+detail
shader pattern.
```powershell
python detail_variant.py --of wgv3_rock_dark --strength 0.5
```

### `high_pass_detail.py` — extract detail from existing albedo
Cheaper than `detail_variant.py` — no new generation. Pulls high-frequency
content out of an existing texture (Gaussian high-pass) into a separate
detail map, or sharpens the source in place. Useful when an existing
material is too soft, or as a procedural detail-layer source.
```powershell
# Detail-only output (grey-centered):
python high_pass_detail.py --in world/textures/library/wgv3_dirt --out detail.png
# Sharpen source in place:
python high_pass_detail.py --in <dir> --sharpen --gain 1.4
```

### `flux_seamless.py` — single FLUX generation with offset+heal
Lower-level than `aaa_texture.py`. Just an albedo, no PBR derivation.
Used internally by `variant_select.py` and exposed standalone for
experiments.

### `flux_upscale.py` — 2K/4K upscale preserving tiling
Two-stage bilinear → low-denoise FLUX img2img → reverse-offset.
Albedo-only. For hero materials only; standard pipeline ships at 512.

## Inputs from external sources

### `polyhaven_fetch.py`
Downloads a real-photo PBR set from PolyHaven. Reliable grade-A.
Use when AI generation isn't worth the iteration time (e.g.
"I just need a rock texture, not a *specific* rock texture").

### `ambientcg_fetch.py`
Same idea, AmbientCG source.

## Quality + repair

### `seam_repair.py` — fix tiling seams
Self-contained. Computes a repair plan once on the albedo, replays
across all maps for spatial alignment. Backups originals to
`*.pre_repair.png`. Has `--restore` to revert.
```powershell
python seam_repair.py --material <dir>
python seam_repair.py --material <dir> --restore  # undo
```

### `delight.py` — flatten baked-in lighting
LAB-space large-blur subtract. Removes shadow/highlight bias from AI
output. Already invoked by `aaa_texture.py`; rarely run standalone.

### `relock_palette.py` — re-palette-lock without regenerating
When you re-roll a kit's anchor and want existing kit members to
follow without spending compute on regeneration.
```powershell
python relock_palette.py --anchor wgv3_rock_dark --members wgv3_alpine_moss wgv3_alpine_scree --strength 0.6
```

## Diagnostics

### `biome_consistency.py` — does this texture fit the kit?
Compares a candidate albedo's LAB distribution + RGB histogram to an
anchor. Verdict: `in_palette` / `drift` / `way_off`. **Advisory**;
some kit slots (snow, contrast rocks) legitimately read `way_off`.
```powershell
python biome_consistency.py --kit desert
python biome_consistency.py --anchor desert_sand --candidate desert_dark_rock
```

### `make_test_texture.py`
Generates a synthetic test texture (checkerboard, noise, etc.) for
shader development. Use when iterating on a shader and you want
predictable input.

### `experiment.py` — sweep harness for R&D
Reproducible way to run a controlled sweep and collect a contact
sheet + JSONL manifest of grades. Three modes:
- **`seeds`** — same prompt × N seeds. "How seed-stable is this
  prompt?"
- **`prompts`** — prompt list × seed list. "Which phrasing wins?"
  Reads a JSON list of `{label, prompt}` entries.
- **`settings`** — single prompt + seed, sweep `--variants-list` and
  `--heal-list`. "Does bumping variants/heal help here?"

Output goes to `D:/tmp/world3_experiments/<name>/` with
`contact_sheet.png` (NxM grid of tile_2x2 thumbs with grade captions)
and `manifest.jsonl` (one row per run).

```powershell
# Same prompt × 3 seeds on snow
python experiment.py --name snow_seeds --mode seeds --category Snow `
  --prompt "fresh white snow with small dimples, top-down photo, ..." `
  --seeds 100 200 400

# Prompt comparison sweep
python experiment.py --name leaf_prompts --mode prompts --category Ground `
  --prompts-file prompts_a3/leaf_litter.json --seeds 100 200 400

# Settings: variants count
python experiment.py --name sand_variants --mode settings --category Ground `
  --prompt "<canonical sand prompt>" --seeds 100 --variants-list 4 6 8
```

Used heavily in Phase A.2 / A.3 / A.4 / A.6 sweeps — see TEXTURE_RND
Part 1 entries.

## Lower-level / specialty

### `derive_pbr_v2.py` — heuristic PBR (no model)
Albedo → height/normal/roughness/AO via deterministic image processing.
Used by the `fast` quality preset. Faster than StableMaterials but
visually flatter. Standalone use: testing PBR pipeline without GPU.

### `stablematerials_image2pbr.py` — diffusion-based PBR
The `default`/`strict` PBR backend. Runs in `mesa-env`. Don't invoke
directly; use `aaa_texture.py --quality default`.

### `chord_image2pbr.py` — alternative PBR backend (CHORD, Ubisoft, opt-in)
ComfyUI HTTP-API wrapper for the CHORD ComfyUI nodes (Ubisoft La
Forge, SIGGRAPH Asia 2025). Outputs 5 PBR maps + AO from a single
input albedo at 1024 native. **Beats StableMaterials on hard-edge
geometry** (sharper normals, cleaner heights, no center bias);
**loses on rock roughness** (near-flat output fails sanity).

**Setup**:
1. `git clone https://github.com/ubisoft/ComfyUI-Chord` into
   `D:/assets/animators/ComfyUI/custom_nodes/`
2. `pip install diffusers omegaconf imageio` in ComfyUI venv
3. Download `chord_v1.safetensors` from gated HF repo
   `Ubisoft/ubisoft-laforge-chord` (need HF account + access request),
   place in `D:/assets/animators/ComfyUI/models/checkpoints/`
4. Apply transformers 5.x compat patch to ComfyUI-Chord/nodes.py
   (strip `text_encoder.text_model.` → `text_encoder.` from state
   dict before `load_state_dict`). See TEXTURE_RND.md "A.8" entry
   for the diff.
5. Restart ComfyUI; verify nodes show up via
   `curl http://127.0.0.1:8188/object_info | grep Chord`

**Usage**:
```powershell
# Standalone
python chord_image2pbr.py --input <albedo>.png --out <dir> --id <name>

# Via orchestrator (recommended)
python aaa_texture.py --prompt "..." --id wgv3_X --pbr-backend chord
```

**License**: Ubisoft Machine Learning License (Research-Only Copyleft).
Fine for research/internal; flag for commercial.

**When to use**:
- Materials with strong hard-edge geometry (cracks, ridges, brick)
  where CHORD's sharper normals/heights matter
- Future hero-mesh terrain (handoff decision 3)
- Future texture upscaling research (Phase B) — CHORD's tile-aware
  inference at 1024 native may pair well with SR strategies

**When NOT to use**:
- Rock-category materials where roughness variation matters (use SM
  default)
- Anywhere the existing shipping textures already pass — don't
  regenerate just because CHORD exists; SM is fine for our current
  shipping set

### `variant_select.py`
Generates N candidates and picks the best by edge-MSE seam score.
Internal to `aaa_texture.py`'s variant stage.

### `variant_blend.py` — combine N variants into one tile (rescue tool)
Sister to `variant_select.py`. Where select *picks* the best variant,
blend *combines* them through tileable noise-mask softmax weighting.
Output is itself tileable (each input is tileable; the masks tile;
the weighted sum tiles).

**When to use**: lattice-prone materials where all N candidates have
similar periodic artifacts at similar phase. Common case: seed-300
on dense organic materials (grass, leaf_litter) where prompt
rewrites alone can't escape the underlying lattice. variant_blend
shifts the dominant frequency by mixing inputs from different seeds.

**Knob: `--sharpness`** trades content-sharpness vs edge_mse.
- `sharpness=4` (default): smoother feathered transitions, lower
  edge_mse, but visibly softens content (regression on content-rich
  materials).
- `sharpness=12` (recommended for rescue): hard region boundaries,
  preserves variant content sharpness, much better periodic_locality,
  slightly worse edge_mse.

**A.9 A/B finding**: on leaf_litter seed-300 (textbook lattice case),
sharp=12 dropped periodic_locality from 19.5 → 8.5. Visually escapes
the obvious tile repetition that variant_select couldn't.

**Usage**:
```powershell
# After variant_select.py --keep-all has produced <id>_v0..<id>_v(N-1):
python variant_blend.py --id <id> --variants 4 \
  --out world/textures/library/<id>_blend --sharpness 12

# Or directly with explicit input list:
python variant_blend.py --inputs A.png B.png C.png D.png \
  --out blended.png --sharpness 12
```

**NOT in the orchestrator pipeline by default.** Manual rescue tool.
Reach for it when a material is stuck at grade B/C with periodic
failures and prompt rewrites haven't worked.

### `blender_preview.py` — CYCLES PBR preview render
Optional final stage. Renders the texture on a sphere and a tilted
plane under HDRI lighting. Best-effort; fails silently if Blender
isn't available.

## Don't use / known broken

### `material_anything_adapter.py`, `ma_image2pbr.py`
Material Anything's standalone image-to-PBR is broken for 2D textures.
The mesh-driven path works but isn't relevant to terrain.

### `palette_lock.py` (alone, without re-QA in pipeline)
Pre-fix-#5 code lived here. Now fixed but worth knowing the catalog
gets refreshed automatically.

## Workflow recipes

### "I want one texture, fast"
`aaa_texture.py --quality fast --prompt "..." --id ...`

### "I want one ship-quality texture"
`aaa_texture.py --prompt "..." --id ... --category <X>`. If output is
visually wrong (FLUX missed prompt), iterate the prompt — see
[PROMPT_COOKBOOK.md](PROMPT_COOKBOOK.md).

### "I want a 5-texture biome kit"
1. Pick an anchor concept. Generate it standalone.
2. `palette_lock.py --kit X --anchor X --add ...` for the rest.
3. `biome_consistency.py --kit X` to verify.

### "I have a kit but the anchor wasn't right; re-rolled it; want others to follow"
`relock_palette.py --anchor <new> --members <others> --strength 0.6`

### "An existing texture looks soft and I don't want to regenerate"
`high_pass_detail.py --in <dir> --sharpen --gain 1.3`

### "I want a detail-layer companion to an existing texture"
- Authored: `detail_variant.py --of <id>` (FLUX, ~3 minutes)
- Procedural: `high_pass_detail.py --in <dir>` (free, instant)

### "QA changed and I want to re-grade everything"
`texture_qa.py --all`

### "Repair pass made things worse"
`seam_repair.py --material <dir> --restore`
