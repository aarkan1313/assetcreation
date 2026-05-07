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

**A.10 reference-anchor mode (opt-in, klein-native):** pass
`--reference-image <path> --reference-mode anchor
--reference-denoise 0.70-0.95` to anchor the FLUX generation on a
reference photo. The reference is auto-resized to `--size`,
VAE-encoded, fed as the sampler's starting latent at the specified
denoise strength. Lower denoise = stronger reference, less prompt
fidelity. Sweet spots:

- `0.88` — subtle tint; mostly text-driven
- `0.78` — moderate hybrid; reference structure visible
- `0.70` — strong anchor; reference structure embedded (e.g. snow
  prompt + forest_floor reference produces "fresh snow over leaf
  bed" composite)
- `<0.65` — reference dominates, prompt ~ignored

Anchor mode also opts the heal pass into `BasicScheduler` so the
pass-1 anchor signal isn't erased by the pass-3 repaint. Default
behavior (no reference) is unchanged. **Not yet exposed via
`aaa_texture.py`**; call `flux_seamless.py` directly for anchor mode.

`--reference-mode conditioning` (klein's native `ReferenceLatent`
node into the conditioning chain) was Attempt 1 in A.10 — produces
microscopic influence (klein-4B has too few denoising steps for
in-context tokens to materially shift output). Code path stays for
future iteration but advisory-only.

### `sr_upscale.py` — Real-ESRGAN single-map super-resolution *(Phase B.1)*

**What:** Drop-in 4× SR for any single tileable PNG (albedo, height,
normal, roughness, etc.) via ComfyUI's `UpscaleModelLoader` +
`ImageUpscaleWithModel` nodes with the Real-ESRGAN x4plus model.
Tile preservation via offset+heal trick. ~2s per 512→2048 on 5090.

**Reach for it when:** You need to upscale one map by 4×. Default SR
tool for the multi-resolution pipeline (Phase B.1+). For multi-map
PBR sets, use the orchestrator (`aaa_texture.py --ladder`, lands in B.5)
which composes this with `bake_pbr.py` and `mip_ladder.py`.

**Don't reach for it when:**
- You want FLUX-style coherence recovery — use `flux_upscale.py`
  (the heal-pass tool, not SR proper).
- ComfyUI isn't available — use `upscale_biome_set.py` (Lanczos
  baseline, no-install fallback).

**Output:** Single PNG at the upscaled resolution.

**See also:** `EXTERNAL_SR_TECHNIQUES.md` for the survey; B.2's
`bake_pbr.py` for what to do with the SR'd output.

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

**Key finding (B.2):** ESRGAN misinterprets normal map RGB channels as
photographic content and produces color interference artifacts. Re-baking
from height is geometrically correct and strictly better than SR'd normal.

**See also:** `sr_upscale.py` (prerequisite), `mip_ladder.py` (next step, B.3).
`DECISIONS.md` for bake-at-SR-resolution rationale.

### `flux_upscale.py` — FLUX img2img heal-pass tool *(repositioned Phase B.1)*

**Phase B.1 update (2026-05-07):** Repositioned as a heal-pass tool.
For SR proper, use `sr_upscale.py`. This tool recovers FLUX-style
coherence after generation or after Real-ESRGAN SR. Albedo-only.

Two-stage bilinear → low-denoise FLUX img2img → reverse-offset.
For hero materials. Seam score ~0.00123 (coherence-focused, not
tight-tiling focused — use Real-ESRGAN for tight tileability).

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

Also called by the A.11 hybrid backend (`--pbr-backend chord_sm_rough`)
to provide just the roughness map; CHORD provides the rest. See
TEXTURE_RND "A.11" entry for the hybrid rationale.

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

### `patina_adapter.py` — PATINA fal.ai PBR adapter (alternative backend)
fal.ai-hosted PATINA model — image-to-PBR + text-to-material. Returns
basecolor/normal/roughness/metalness/height like StableMaterials but
via a remote API instead of local diffusers. Set `FAL_KEY` env var
to use. **Not currently wired into `aaa_texture.py`'s `--pbr-backend`
flag.** Reference implementation in case CHORD or SM ever go down or
we want a fast cloud fallback.

### `comfy_generate.py` — direct FLUX 2 klein text-to-image
Lower-level than `flux_seamless.py` (no offset+heal seamless trick);
just calls ComfyUI's standard FLUX 2 klein 4B distilled text2img
workflow. Optionally pipes through `derive_pbr_v2`. Useful for
non-tileable use cases or for debugging FLUX behavior independent of
the seamless logic.

## Workflow / kit tools

### `kit_generator.py` — auto-generate a biome texture kit from a name
Higher-order tool: takes a biome name (e.g. `frozen_volcanic`) and
either an LLM-generated brief or a JSON recipe, then orchestrates
`palette_lock.py` to produce a complete cohesive PBR set. Canonical
"start a new biome from scratch" tool.

### `detail_pyramid.py` — macro + detail layer pair
Generates a paired (macro, detail) texture set for use with the
macro-detail shader stack (terrain_hex_detail). Macro is the material
identity at coarse UV; detail adds surface micro-variation at fine UV.

### `process_texture.py` — single-input image-to-Godot-PBR
Takes a source image (could be a real-world photo, a hand-painted
albedo, or any RGB) and produces a tileable Godot-ready PBR set. Less
configurable than `aaa_texture.py`; useful when you already have an
albedo and just want to derive maps + tile-fix it.

## world3-specific staging

### `biome_texture_bind.py` — wire biomes to library textures
For a world3 output: reads `art_lab/biomes/biome_texture_registry.json`
and ensures the AAA texture set for each biome present in the world
exists in `world/textures/library/`. Generation-on-demand for
worldgen runs.

### `pack_terrain3d.py` — Terrain3D channel-pack format
Re-packs a standard PBR set into Terrain3D's two-PNG layout:
`albedo_height.png` (RGB=albedo, A=height) and `normal_roughness.png`
(RGB=normal OpenGL+Y, A=roughness). Use when the consumer is the
Terrain3D Godot plugin rather than world3's own shader.

### `upscale_biome_set.py` — Lanczos upscale a biome
Quick quality lever 'B' for the worldgen workflow. PIL Lanczos —
not as sharp as Real-ESRGAN/SwinIR but a no-install baseline. **Phase
B candidate**: this is the placeholder a real upscaling pipeline
would replace.

## Diagnostics (extended)

### `macro_detail_preview.py` — Blender preview of macro+detail pair
Renders a macro+detail texture pair in Blender Cycles to validate
that the RNM-blend logic the Godot `macro_detail_v1.gdshader` does
produces the expected close-up read.

### `render_ma_mesh.py` — Blender render of a Material Anything mesh
After `material_anything_adapter.py` produces a textured mesh +
UV-space PBR maps, this renders it in Blender Cycles for visual
review. Companion to the broken-for-2D-textures MA path; only used
when MA is producing a hero mesh.

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
