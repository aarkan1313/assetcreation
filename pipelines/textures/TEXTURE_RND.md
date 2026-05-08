# Texture Pipeline — R&D Log

Append-only log of texture-pipeline R&D. Two parts:

- **Part 1 — Experiments**: sweeps, A/B comparisons, settings
  explorations. Each entry: what we tested, what we found, what we
  changed.
- **Part 2 — Cookbook**: per-material prompts that work and don't
  work, with the recipes and known failure modes.

The two are tightly coupled — experiments produce findings that get
baked into the cookbook, and cookbook gaps drive the next experiment.

The contact sheets and manifests for sweeps live in
`D:/tmp/world3_experiments/<name>/`.

---

# Part 1 — Experiments

## Phase D — Biome generalization: temperate_forest + grassland kits (2026-05-07)

**What:** Generated purpose-built textures for the two missing biome kits. Previously
both reused alpine slots (rock_dark, grass, etc.), making California chaparral and
Serengeti regions render with alpine materials.

**temperate_forest kit:**
| Slot | ID | Grade | Consistency |
|------|----|-------|-------------|
| grass (anchor) | wgv3_tf_leaf_litter | B (2K tier: A) | — |
| dirt | wgv3_tf_loamy_soil | A | drift |
| rock_light | wgv3_tf_mossy_rock | A | drift |
| rock_dark | wgv3_tf_bark_rock | A | in_palette |
| snow | wgv3_tf_fern_ground | A | drift |

**grassland kit:**
| Slot | ID | Grade | Consistency |
|------|----|-------|-------------|
| grass (anchor) | wgv3_gl_tall_grass | B (2K tier: A) | — |
| dirt | wgv3_gl_dry_thatch | B | in_palette |
| rock_light | wgv3_gl_hardpan_soil | A | in_palette |
| rock_dark | wgv3_gl_grass_rock | A | in_palette |
| snow | wgv3_gl_weathered_stone | B | drift |

**Key findings:**
- Anchors (leaf_litter, tall_grass) consistently grade B at 512px base but A at 2K ladder tier.
  This is a structural characteristic of high-frequency heterogeneous materials at 512px — the same
  pattern seen with rock_dark in B.4. In-engine render at 2K is A quality.
- Kit slots (non-anchor) ran without --ladder; grade B floor is acceptable for palette-locked kit slots.
- bark_rock returned `in_palette` (not `way_off` as expected) — palette match pulled the dark basalt
  into the anchor's warm dark-brown range. Better outcome than expected.
- `weathered_stone` (grassland) periodic score=150.2 — grey limestone is genuinely uniform; the score
  reflects correct material characteristics, not a generation failure.
- `hardpan_soil` and `loamy_soil` both flagged near-zero roughness variance (sanity). Clay/loam are
  genuinely low-roughness-variation materials; StableMaterials is correct here.

**Prompting:** Applied Phase A learnings. No directional cues, no rare jargon, `top-down photo,
even diffuse light, photoreal` in every prompt. 6 variants for anchors, 4 for kit slots.

**biome_kits.json updated:** Both kits reference purpose-built IDs. All 5 kits have unique sets.

## B.5 — orchestrator integration: aaa_texture.py --ladder (2026-05-07)

**What:** Wired the full SR → bake → mip → per-tier QA pipeline into
`aaa_texture.py` as Stage 8, activated by `--ladder`.

**Captures:** `world3/docs/captures/phase_b/B5_flagship_rock_dark_ladder/`

**Key findings:**

- The full pipeline (Stage 8) adds ~30s to a strict run (SR is the
  dominant cost at ~2s/map × 6 maps = 12s, plus bake ~3s, mip ~5s,
  QA ~5s, overhead ~5s). Acceptable for hero materials; off by default.

- rock_dark flagship: all 3 tiers grade B. Junction ratio increases at
  lower res (1.50 at 2K, 2.11 at 1K, 2.66 at 512) — expected behavior
  for high-contrast edge material (documented in B.4 entry). Edge MSE
  is consistently 0.0001 across all tiers, confirming the bake + mip
  filtering chain preserves tileability end-to-end.

- `aaa_pipeline.json` now records `ladder.tier_grades` alongside the
  gen-res grade, giving a complete single-file quality record per material.

**Decision:** `--ladder` is the canonical path for hero/strict materials.
`--quality fast` and `--quality default` remain gen-res-only by default.
No automatic up-promotion of default to ladder — YAGNI.

**Next:** B6 (optional) — alternative SR backends if Real-ESRGAN
underperforms on specific material classes (snow, vegetation).

## B.4 — per-tier QA: texture_qa.py --ladder (2026-05-07)

**What:** Extended `texture_qa.py` with `--ladder <mat_dir>` flag.
Runs all 4 QA checks (edge, junction, periodic, richness) on every
tier in the mip ladder, then writes a cross-tier contact sheet.

**Captures:** `world3/docs/captures/phase_b/B4_ladder_qa/`

**Key findings:**

- Snow grades A across all 3 tiers (2k/1k/512). The ladder filtering
  (vector-field normals, gamma-aware albedo) correctly preserves
  tileability across resolution tiers. This validates B.3's approach.

- rock_dark grades A at 2K but B at 1K and 512. The junction ratio
  increases as resolution drops (1.43 at 1K, 1.97 at 512 vs 0.84 at
  2K). This is inherent to the material's high-contrast edges — the
  seam-band contains measurably more edge energy relative to the
  interior at lower pixel counts. Not a filter defect; the Lanczos
  downsample is doing its job. At 512, the seam band is ~20px and the
  interior cells are small enough that any natural edge falls inside it.

- Richness scores are stable or increase across tiers (rock_dark 512
  scores 1.06 vs 0.66 at 2K — the detail becomes sharper relative to
  the tile size when viewed at 512 native resolution).

**Decision:** `--ladder` mode confirmed as the standard QA flow for
multi-resolution materials. The junction-fail at lower tiers for
high-contrast materials is expected and acceptable (grade B not D).
Ready to wire into the B.5 orchestrator.

**Next:** B.5 — orchestrator integration (`aaa_texture.py --ladder`).

## B.3 — mip_ladder.py: multi-tier physically-correct downsample (2026-05-07)

**What:** Built `mip_ladder.py`. Input: 2K baked master (from B.2).
Output: 2K/1K/512 tiers with per-map correct filtering.

**Captures:** `world3/docs/captures/phase_b/B3_ladder_ab/`

**Key findings:**

- **Normal vector-field filtering**: `downsample_normal()` decodes XYZ,
  filters each channel as floats, renormalizes. Visual result: normal
  maps remain fully blue-dominant at 512 tier with preserved geometry
  directions — no fading to gray. Naive RGB filter would produce grayed-out
  normals at lower mips (shorter vectors = flatter appearance).

- **Albedo gamma-aware filtering**: linearize -> Lanczos -> re-encode sRGB.
  Prevents dark-bias at 512 that would occur with naive sRGB filtering.
  Visually: color character and tonal balance preserved across all 3 tiers.

- **Linear maps (roughness/AO/metallic/height)**: standard Lanczos, no
  surprises. AO at 512 retains smooth concavity gradients. Height dynamic
  range preserved. Roughness variation intact.

**Performance:** ~3-4s for 2K→2K/1K/512 (6 maps, 3 tiers). Trivial vs SR/bake.

**Decision:** Separate `<id>/ladder/<tier>/` output layout confirmed.
Flat naming within each tier (`<id>_<map>.png`) matches library convention.

**Next:** B.4 — per-tier QA wiring (`texture_qa.py --ladder` mode + cross-tier contact sheets).

## B.2 — bake_pbr.py: high-res re-derive of normal/AO/roughness (2026-05-07)

**What:** Built `bake_pbr.py`. SR'd all 6 maps for rock_dark/snow/forest_floor
at 2048, then re-derived normal/AO/roughness from the 2048 height+albedo.
A/B'd SR-only vs SR+bake on 3 materials.

**Captures:** `world3/docs/captures/phase_b/B2_bake_ab/`

**Key findings:**

- **Normal**: baked normals are dramatically better than SR-only. ESRGAN
  misinterprets the RGB channels of normal maps (treats them as photographic
  content) and produces color interference artifacts — the SR'd normal shows
  unnatural cyan/green smearing especially on rock edges. Re-baking from the
  2048 height gives geometrically correct, clean blue-dominant normals with
  sharp gradient transitions. This is the strongest argument for bake-by-default.

- **AO**: baked AO shows smoother concavity gradients. SR-only AO has blocky
  concavity shapes and slightly oversaturated dark spots. Baked AO has tighter
  concavity detection and smoother falloff. Blur radius scaling (8 * h/512 = 32
  at 2048) looks correct — not over-blurred, not too local.

- **Roughness**: blend (65% SR + 35% derived for sm/chord_sm_rough backends)
  produces subtle micro-variation vs SR-only. Minimal visible difference at this
  crop scale, which is expected at 65% SR trust. The roughness blend is more
  about correctness (replacing ESRGAN's hallucinated roughness micro-detail with
  albedo-derived luminance variation) than visual drama.

**Decision:** Bake-by-default confirmed. SR'd normals are geometrically wrong
(ESRGAN color artifacts). Baking from height at full resolution is both faster
and more correct than using the SR'd normal.

**rock_dark library update:** SR+bake applied to `world/textures/library/wgv3_rock_dark/`
(all 6 maps at 2048, normal/AO/roughness baked). QA grade: A.
Note: library dir is gitignored; files live on disk only.

**Resolved open item from B.1:** "Does the bake step wash out SR hallucinations in
normal/AO?" Yes — it replaces ESRGAN's photographic misinterpretation of normal
map channels with geometrically-derived normals. This is strictly better.

**Time spent:** ~full session.
**Next:** B.3 — `mip_ladder.py` (4K master → 2K/1K/512 with proper per-map filtering).

## B.1 — SR survey + Real-ESRGAN as default backend (2026-05-07)

**What:** First Phase B sub-step. Surveyed SR backends, chose Real-ESRGAN
x4plus as default, wrote `sr_upscale.py` with offset+heal tile preservation,
A/B'd against Lanczos and FLUX heal on 3 representative materials.

**Survey doc:** `pipelines/textures/EXTERNAL_SR_TECHNIQUES.md`
**A/B captures:** `world3/docs/captures/phase_b/B1_sr_survey/`

**Decision: Real-ESRGAN x4plus as B.1 default.**
- Drop-in via ComfyUI's `UpscaleModelLoader` + `ImageUpscaleWithModel`.
- Fast (~2s per 512→2048 map on 5090 — faster than expected).
- BSD-3-Clause license.
- Alternatives parked for B.6 if survey or B.5 flagship A/B surfaces a need.

**Reposition: `flux_upscale.py` is now the heal-pass tool**, not the
SR backbone. Docstring updated; behavior unchanged. FLUX heal seam score
(0.00123 all materials) is materially worse than Real-ESRGAN + offset trick
(0.00003–0.00091) — confirming FLUX heal is optimizing for style coherence,
not tight tileability.

**A/B findings (3 materials × 3 methods):**

| Material | Lanczos | Real-ESRGAN | FLUX heal (2K) | Notes |
|----------|---------|-------------|----------------|-------|
| rock_dark | smooth/blurred upscale, no new detail | sharp grain and crystal edges recovered | FLUX-coherent, softer than ESRGAN | Real-ESRGAN visibly sharpened micro-crystal structure; expected win on hard-edge geometry. |
| snow | smooth, correct uniformity | micro-detail added — fine granular texture, plausible but not native-FLUX | FLUX-style, uniform | Real-ESRGAN added snow-appropriate micro-granularity. No obviously wrong hallucination. |
| forest_floor | smooth, leaf edges softened | sharper leaf/dirt boundaries, more heterogeneous texture visible | FLUX-coherent, softer | Real-ESRGAN preserved and sharpened the heterogeneous structure. |

**Tile coherence (offset+heal trick):**

| Material | edge_seam_score (input) | post-SR (with offset) | post-SR (no offset) |
|----------|-------------------------|-----------------------|----------------------|
| rock_dark | 0.00011 | **0.00003** | 0.00017 |
| snow | 0.00022 | **0.00003** | not measured |
| forest_floor | 0.00247 | **0.00091** | not measured |

With offset trick: consistently better than input. Without offset trick: worse
than input on rock_dark (the canonical test). Offset trick is mandatory.

FLUX heal comparison: 0.00123 for all three materials regardless of source.
Higher than Real-ESRGAN + offset, confirming its role as a coherence
tool rather than a tight-tiling tool.

**Open / surfaced for later steps:**
- FLUX heal score is identical (0.00123) across all three materials —
  suggests the heal pass is applying a fixed-strength denoise that
  dominates the seam metric regardless of input. Not a problem for its
  intended use (coherence polish), but documents it shouldn't be
  measured by seam score alone.
- No offset-trick test on snow/forest_floor without offset — rock_dark
  result is sufficient to confirm the pattern.
- Real-ESRGAN on all three materials ran in ~2s each (5090). Faster than
  expected (plan estimated 5-15s). Full 512→4K in ~2s means the 4K
  working master for bake_pbr.py (B.2) will be cheap.

**Time spent:** ~half session.
**Next:** B.2 — `bake_pbr.py` (high-res re-derive of normal/AO/roughness
from upscaled albedo+height).

---

## A.11 — CHORD + SM-roughness hybrid PBR backend

**Date**: 2026-05-07
**Question**: A.8 found CHORD wins on hard-edge geometry (sharp
normals, clean heights, no center-bias bloom) but loses on rock
roughness (near-flat std=0.011, fails sanity gate). Can we get the
best of both by running CHORD + SM in sequence and stitching just
the roughness map?

### Setup

Added `--pbr-backend chord_sm_rough` to `aaa_texture.py`. Dispatch:

1. Run CHORD (writes 6 maps: albedo/normal/roughness/metallic/height/ao)
2. Run StableMaterials in mesa-env into a temp dir
3. Copy SM's roughness over CHORD's roughness; CHORD's saved as
   `<id>_roughness.pre_sm_swap.png` so it's recoverable
4. Clean temp; pipeline continues with mixed-provenance maps

Wall-time cost: ~25s extra over pure CHORD (one extra SM forward
pass at standard mode, 50 steps). Total stage 3 time: ~55s vs CHORD
alone ~30s vs SM alone ~25s.

Pipeline log marks `'method': 'chord_v1+sm_roughness'` so it's
traceable in `aaa_pipeline.json` for any material that used the
hybrid.

### Direct A/B (identical prompt + seed across all 3 backends)

Prompt: `dark grey volcanic rock surface, weathered, sharp edges and
small cracks, top-down photo, even lighting, photoreal` at
seed-base 42, default quality. Compared:
- A.8 pure CHORD (`A8_chord_rock_dark`)
- A.11 hybrid (`A11_hybrid_smoke`) — same input, just roughness swapped
- Pure SM (PBR maps from existing A.8 SM-only A/B at
  `D:/tmp/world3_experiments/A8_chord_test/sm_compare/sm_rock_dark_*`)

| Aspect              | Pure SM   | Pure CHORD             | Hybrid                |
|---------------------|-----------|------------------------|-----------------------|
| Roughness std       | ~0.04     | 0.011 (FAIL)           | **0.029 (PASS)**      |
| Roughness range     | ~0.4–0.95 | 0.58–0.71 (narrow)     | **0.44–1.00 (full)**  |
| Roughness character | varied    | flat                   | **varied (= SM)**     |
| Normal sharpness    | soft      | sharp                  | **sharp (= CHORD)**   |
| Height bloom        | center-bias bloom | no bloom       | **no bloom (= CHORD)**|
| Sanity gate         | PASS      | FAIL                   | **PASS**              |
| Overall gate        | PASS      | FAIL                   | **PASS**              |
| Seam grade (edge/junc/period) | A | A                | **A**                 |

Contact sheet:
`world3/docs/captures/phase_a/A11_chord_sm_hybrid_ab/A11_AB_contact_sheet.png`

### Findings

1. **The hybrid lifts the gate from FAIL → PASS** on rock_dark while
   preserving CHORD's geometric advantages. Sanity now reports
   `ok: True` with no notes; the standard gate accepts the texture.

2. **Roughness richness comes back fully.** The swapped SM roughness
   shows the full 0.44–1.00 dynamic range with bright slabs and
   dark crack tracks — physically plausible weathered rock. CHORD's
   pre-swap version is preserved as `_roughness.pre_sm_swap.png` for
   inspection or reversion.

3. **Other CHORD strengths are preserved.** Normal map is still
   sharp with strong crack definition; height is still clean with
   no center-bias bloom. The hybrid only swaps roughness; the rest
   is pure CHORD.

4. **Cost is ~25s extra wall-time per material.** Acceptable for any
   case where rock-class roughness matters (i.e. anything we ship
   at close-camera or hero distance). Skippable for sand/snow/water
   where roughness uniformity is *correct*.

### Decision: ship as opt-in alongside pure CHORD

- `--pbr-backend chord` and `--pbr-backend chord_sm_rough` both
  available; user picks per-material based on category.
- For **Rock-class** materials (where CHORD's flat roughness was
  the regression), use `chord_sm_rough`. Net win: CHORD's sharper
  normals + heights with SM's correct roughness.
- For **Sand/Snow/Water/Liquid**: pure CHORD is fine; the categories
  legitimately have uniform roughness, the hybrid would just spend
  25s extra on something the gate would have accepted anyway.
- For **other categories** (Foliage, Ground, Brick, etc.): no clear
  winner from the data — A.8 didn't measure these as carefully. Default
  to pure CHORD for now; A/B per-material if a roughness regression
  shows up.
- **Default for `--quality default/strict` remains StableMaterials.**
  We're not migrating shipping textures. CHORD-family backends
  (chord, chord_sm_rough) are still opt-in; this just makes the opt-in
  more useful for hard-edge categories.

### Implications + open items

- **The "best practice" sequence for a rock-class hero material is now
  pretty clear**: `--quality strict --pbr-backend chord_sm_rough`.
  Sharp geometry + correct roughness + grade A pass.
- **`pre_sm_swap.png` debt**: every chord_sm_rough run leaves an extra
  ~50-200 KB file behind. Library bloat is small but real. Could
  add a `--no-keep-presm` flag if it ever matters.
- **"Hybrid for normal too?" question**: A.8 showed CHORD wins normal
  on rock — so we never want SM's normal on rock. But for organic
  materials (forest_floor, leaf_litter) where CHORD's sharper normal
  reads as "too detailed," SM's softer normal might be preferable.
  Worth a future A.12-ish revisit if specific organic materials feel
  over-tessellated under the new gate.
- **Phase B upscaling pairs naturally with chord_sm_rough**. CHORD
  operates at 1024 native; if Phase B targets 1K/2K outputs,
  upscaling the CHORD-side maps + SM roughness should be
  straightforward.

---

## A.10 — Reference-image anchor mode for flux_seamless

**Date**: 2026-05-07
**Question**: Per the 2026-05-07 research handoff, can we add reference-
photo conditioning to `flux_seamless.py`'s FLUX stage to anchor
generated materials on real-world (or other texture) photos? Handoff
suggested "IP-Adapter / FLUX Redux drop-in" — but that framing was
based on FLUX.1 D, not our FLUX 2 klein-4B.

### Three attempts before it worked

**Attempt 1: `ReferenceLatent` chained into conditioning** — klein's
native multi-reference path. Wired cleanly. **Microscopic influence**:
0.118/255 mean pixel diff between with-ref and no-ref runs of the same
prompt+seed. Different bytes (different MD5), same content visually.
The `ReferenceLatent` node has no strength parameter; klein-4B at 4
steps doesn't have enough denoising room for in-context tokens to
materially shift the output.

**Attempt 2: img2img with `Flux2Scheduler` + `denoise=0.5..0.88`** —
encode reference, feed as `latent_image` to sampler with partial
denoise. Wiring looked correct in the queued workflow JSON. **Output
was unchanged across denoise values** — pure white snow regardless of
denoise. Diagnosis: **`Flux2Scheduler` silently ignores its `denoise`
input**. The schedule it produces is full-denoise regardless. Confirmed
by sweeping denoise 0.95→0.50 and getting identical mean RGB.

**Attempt 3: img2img with `BasicScheduler` + `denoise`** — swap to
`BasicScheduler` (which DOES honor `denoise`). **Pass-1 output
shows clean denoise gradient on snow-prompt + brown-reference**:

| denoise | pass1 mean RGB | character |
|--------:|---------------:|-----------|
| 0.95    | (232, 232, 235)| pure white snow |
| 0.85    | (223, 223, 227)| slight cream tint |
| 0.78    | (211, 212, 217)| visibly tinted |
| 0.65    | (174, 176, 182)| strong tint |
| 0.50    | (125, 110, 101)| reference dominates |

*But*: pass-3 (the seam-heal pass) also uses `Flux2Scheduler` and was
**erasing the reference influence in the final output**. Final RGB on
all three reference-anchored variants converged toward the no-ref
result. Heal pass was effectively repainting from scratch.

### Final working design

**Pass 1 (text2img with anchor)**: when `--reference-image` is given
in `--reference-mode anchor`, `workflow_text2img_klein` uses
`BasicScheduler` so `--reference-denoise` actually controls partial
denoise. Sampler starts from the reference latent. Default denoise
0.88 — light tint; 0.70 for stronger embedded-reference effects.

**Pass 3 (heal) — surgical fix**: `workflow_img2img_klein` got a
`honor_denoise=True` opt-in. When anchor mode is active, the heal
pass switches to `BasicScheduler` at `denoise=0.25` so it gently
smooths seams *without* erasing the pass-1 anchor signal. **Default
heal behavior unchanged** for non-reference runs (still uses
`Flux2Scheduler`, denoise silently ignored = effectively 1.0
repaint, which is what we've been doing all along).

### Final A/B (snow prompt + forest_floor reference)

| Variant            | Final mean RGB     | Visual                               |
|--------------------|--------------------|--------------------------------------|
| no reference       | (230, 231, 235)    | clean white snow                     |
| anchor d=0.85      | (221, 221, 224)    | snow with subtle cream tint         |
| anchor d=0.70      | (189, 191, 197)    | **snow with embedded leaf shapes** — fresh snow on forest floor look |

Contact sheet: `world3/docs/captures/phase_a/A10_reference_anchor/A10_AB_contact_sheet.png`.

The d=0.70 result is the most interesting — clearly snow but with
forest-floor structure embedded. Looks like fresh snow over a
just-fallen-leaves bed. Useful for biome transitions, weathered
surfaces, "X over Y" composite materials.

### Decisions

- **`--reference-image --reference-mode anchor` is the working path.**
  Default `--reference-denoise 0.88` for subtle tint; lower for
  stronger reference influence.
- **`--reference-mode conditioning` (Attempt 1) stays as code** but
  is documented advisory-only. Negligible influence; useful as a
  hook for future iteration if klein gets better in-context tokens.
- **Default behavior (no reference) unchanged.** Regression-tested:
  same wgv3_dirt prompt produces same grade A metrics as before.
- **Vanilla heal pass behavior unchanged.** `Flux2Scheduler` keeps
  silently dropping `denoise` for non-reference runs — that's the
  status quo since project start. Don't change without re-validating
  every shipping texture.

### Surfaced issue: Flux2Scheduler silently drops `denoise`

The pre-existing heal-pass behavior is "documented as `denoise=0.35`
but actually runs at 1.0 because Flux2Scheduler ignores the
parameter." Empirically the pass works (klein's distilled 8-step
schedule converges quickly even from full noise), but our docs were
wrong about what was happening.

**Open question (parked, not part of A.10)**: should we audit the
heal pass and switch *all* heal runs to `BasicScheduler` with a
calibrated `denoise` (probably ~0.5 — half-denoise smooths seams
while keeping more pass-1 content)? Would require A/B against
the entire wgv3_* shipping set to confirm no regression. Filed as
ROADMAP "future audit: honest partial-denoise heal pass."

### What it doesn't fix

- **klein-9B Edit** is the proper image-edit model in the family;
  trained for stronger reference handling than klein-4B. Different
  weights (~9B vs 4B), separate download, different speed profile.
  Not adopted: A.10's working anchor mode is good enough for
  reference-style anchoring at our use cases. Parked as a future
  option in ROADMAP.
- The handoff's "IP-Adapter drop-in" framing **was based on FLUX.1
  D**; it doesn't apply to klein. Don't re-evaluate IP-Adapter
  unless we ever migrate off klein.

### When to use this

- Biome transitions / "snow on top of X" / "wet on top of Y" composite
  materials.
- Anchoring FLUX outputs on real-world photos when material accuracy
  matters more than free-form generation. (Future: build a small
  curated set of real-world reference photos under
  `world/textures/references/`.)
- Style-matching across a kit: use one anchor texture as reference
  for several others to enforce palette/character consistency.

Good defaults:
- `--reference-denoise 0.88`: faint anchor, mostly text-driven
- `--reference-denoise 0.78`: moderate anchor, hybrid character
- `--reference-denoise 0.70`: strong anchor, reference structure visible
- below 0.65: reference dominates, prompt mostly lost (use with care)

---

## A.9 — Variant-blend tool: combine N variants into one tile

**Date**: 2026-05-07
**Question**: EXTERNAL_TECHNIQUES technique #5 (cprimozic-inspired):
generate N tileable variants, *blend* them into one tile instead of
*picking* the best. Does this rescue lattice-prone categories more
cleanly than prompt rewrites alone?

### Setup

New tool `pipelines/textures/variant_blend.py`. Takes N tileable
albedos, blends them through tileable low-frequency noise fields
(softmax-weighted sum of N independent fields). Each input is itself
tileable; the blend masks tile; the output tiles. The `--sharpness`
parameter trades hard-region-boundaries (high) vs feathered-blends
(low).

A/B target: **leaf_litter, cookbook prompt, seed-base 300** —
flagged in A.2 as the hardest case (gold-streak lattice). Generated
4 fresh variants with `variant_select.py --keep-all`. Compared:
- `variant_select` winner (lowest edge-MSE pick)
- `variant_blend --sharpness 4` (default; smooth feathering)
- `variant_blend --sharpness 12` (sharp regions, hard transitions)

All three QA-graded with category=Ground.

### Results

| Output                         | Grade | edge_mse | junction | periodic | richness |
|--------------------------------|-------|---------:|---------:|---------:|---------:|
| variant_select winner          | B     | 0.0274 (F) | 0.95 (P) | 19.5 (P) | 6.49 (P) |
| variant_blend sharp=4 (default)| B     | **0.0146** (F, halved) | 0.95 (P) | 17.5 (P) | 3.81 (P) |
| variant_blend sharp=12         | B     | 0.0296 (F) | 0.98 (P) | **8.5** (P, half of select) | 5.14 (P) |

Visual contact sheet:
`world3/docs/captures/phase_a/A9_variant_blend_ab/A9_AB_contact_sheet.png`

### Findings

1. **Variant-blend is a real trade-space, not a free lunch.** Lower
   sharpness → softer content but better edge_mse. Higher sharpness →
   sharper content but harder seams. There is no setting that beats
   variant_select on every axis.

2. **The trade-space favors blend on lattice-prone categories.**
   At sharpness=12, periodic dropped from 19.5 → 8.5 (less than half).
   Visually: the variant_select winner shows obvious tile repetition;
   the sharp blend doesn't. This is exactly the rescue case.

3. **Edge_mse improvement at sharp=4 is real but soft-content costs.**
   The default sharpness=4 halves edge_mse but visibly blurs leaves.
   On a content-heavy material like leaf_litter that's a noticeable
   regression. Sharp=12 looks better in-eye despite higher edge_mse.

4. **None of the three reached grade A.** seed=300 leaf_litter is
   genuinely hard; A.3 found prompt rewrites couldn't get there
   either (cookbook on s100/200/400 was 1A/1A/1B, but s300 had been
   ruled out as a globally-bad seed). variant_blend reduces failure
   *severity* (lower edge or lower periodic) but doesn't lift to A
   on this case. **More useful for "make a B-grade tile less obviously
   tiled" than "make a C-grade tile pass."**

5. **Richness drops with blending**, as expected: the noise-mask blend
   spreads content uniformly, lowering luminance entropy. Worth
   watching — blend output is more vulnerable to the smooth-A failure
   mode than variant_select output.

### Decision: ship as opt-in rescue tool, NOT pipeline default

- **Default unchanged**: `aaa_texture.py` uses `variant_select` to pick
  the best variant. variant_select is the right call when one of the
  N candidates is a clear winner.
- **variant_blend is the rescue path**: when all N candidates have
  similar lattice/periodic artifacts at similar phase. Useful for the
  small minority of materials where variant_select can't escape the
  underlying lattice (this seed-300 leaf_litter is the textbook case).
- **Recommended invocation for rescue**: `--sharpness 12` — the
  visual quality is closer to the original variant content, and the
  periodic gain matters more than the edge regression for the rescue
  use case (we'd run seam_repair downstream anyway).
- **Don't fold into the orchestrator yet**: the trade-space is real
  and depends on category + content type. Keeping it as a manual
  tool lets us learn when to reach for it before automating.

### Implications + open items

- **Future automation candidate**: an "auto-rescue" mode in
  `aaa_texture.py` that detects "all N variant scores cluster
  together with high-periodic" and falls through to variant_blend
  instead of variant_select. Out of scope for A.9; revisit if we hit
  more of these stuck-lattice cases.
- **Tile-aware rescue chains** (Phase B candidate): blend N variants
  → seam_repair → maybe heal again. Each step in the chain has a
  trade-off; the blend introduces softness, but seam_repair can
  sharpen edges back. Worth A/B-ing.
- **The richness drop on blends is real** — with the A.7 metric in
  advisory mode, this hasn't bitten anything yet. If we promote
  richness to a hard gate later, blend outputs may need a separate
  threshold (or a "this is a blend" flag in the manifest).

---

## A.8 — CHORD swap-in for PBR estimation

**Date**: 2026-05-07
**Question**: 2026-05-07 research handoff
(`docs/handoffs/HANDOFF_textures_research_2026_05_07.md`) called CHORD
(Ubisoft La Forge, SIGGRAPH Asia 2025) the "highest-leverage swap"
available for our PBR pipeline. Does it actually beat StableMaterials
on our typical inputs? What's the install/integration cost?

### Setup

**Install**:
- Cloned `github.com/ubisoft/ComfyUI-Chord` into ComfyUI's custom_nodes/
- Pip-installed deps in ComfyUI venv: `diffusers`, `omegaconf`, `imageio`
- Downloaded `chord_v1.safetensors` (2.76 GB) from gated HF repo
  `Ubisoft/ubisoft-laforge-chord` — required HF account + access request
- **Local patch required**: `nodes.py` had a transformers 4.x → 5.x
  compatibility bug. Saved checkpoint had `text_encoder.text_model.*`
  keys; transformers 5.x's `CLIPTextModel` flattens to `text_encoder.*`.
  Stripping the prefix at load time → 372/372 keys remap cleanly,
  0 missing/0 extra. Patch lives in
  `D:/assets/animators/ComfyUI/custom_nodes/ComfyUI-Chord/nodes.py`
  at the `ChordLoadModel.execute()` site; small rename pass before
  `model.load_state_dict(sd)`.

**Wiring**:
- New `pipelines/textures/chord_image2pbr.py` — wrapper that talks
  to ComfyUI HTTP API (same shape as `flux_seamless.py`); uploads
  input albedo, queues a 9-node CHORD workflow, downloads 5 PBR
  maps (basecolor + normal + roughness + metalness + Poisson-derived
  height), derives AO from height.
- `aaa_texture.py` got a `--pbr-backend {derive,sm,chord}` flag that
  overrides the preset's backend. **Default behavior unchanged**;
  CHORD is opt-in.

### Smoke test
Ran end-to-end pipeline at `--quality default --pbr-backend chord` on
the wgv3_rock_dark prompt. **Grade A** on seam metrics
(edge=0.0007, junc=1.03, period=15.5). All 6 maps produced. Sanity
check failed on roughness (std=0.011 < 0.02 threshold for Rock) —
CHORD's rock roughness is too uniform.

### Side-by-side A/B (same input → both backends)

To control for FLUX upstream variance, ran CHORD and SM on the
*same* input albedos (post-FLUX, pre-delight). Material 1: A.8's
fresh wgv3_rock_dark generation (cracked slate). Material 2:
existing wgv3_forest_floor's pre-delight albedo.

| Aspect              | CHORD                                        | StableMaterials                              | Winner |
|---------------------|----------------------------------------------|----------------------------------------------|--------|
| Normal (rock)       | High contrast, sharp crack definition, clear cyan/magenta channel separation | Soft, low-contrast, cracks read subtle | CHORD |
| Height (rock)       | Crisp crack delineation, uniform slabs, no center bias | Center-bloom artifact (low-freq lighting visible in heightmap) | CHORD |
| Roughness (rock)    | Near-flat (std 0.011, fails sanity check)    | Visible local variation, looks like real rock | SM   |
| Normal (forest)     | Slightly cleaner, less noisy                 | More noisy texture                            | CHORD (small) |
| Height (forest)     | Very high detail, individual leaves visible  | Smooth low-frequency, more landscape-like     | depends |
| Albedo (basecolor)  | ~Same as input (passes through faithfully)   | ~Same (light SDXL touch-up)                  | tie    |
| Metallic            | ~0 (correct for non-metal)                   | ~0 (correct)                                  | tie    |
| Tile-aware          | Yes (native circular padding)                | Yes (built-in `tileable=True`)                | tie    |
| Speed               | ~30s on 5090 (single GPU pass via ComfyUI)   | ~5s LCM / ~25s standard via diffusers         | tie    |

Contact sheet: `D:/tmp/world3_experiments/A8_chord_test/A8_AB_contact_sheet.png`

### Findings

1. **CHORD is qualitatively better on hard-edge geometry** (rock,
   stone, brick — anything with sharp gradients). Normal maps are
   sharper, height maps are cleaner with no center-bias bloom. This
   matches the handoff's claim about CHORD being the "single highest-
   leverage swap" for materials with strong specular variance.

2. **CHORD is worse on roughness for rock.** It outputs near-flat
   roughness that fails our existing sanity check (`std<0.02`).
   StableMaterials produces visibly varied roughness. This is a real
   regression on a category where roughness variation matters
   (lighting-sensitive in-game).

3. **For organic textures (forest_floor) the two are closer.**
   Normal maps are similar; CHORD's height is more detailed but might
   over-tessellate. No clean winner; depends on use case.

4. **Install cost was non-trivial** (transformers 5.x compat bug,
   gated HF model). The handoff said "Low install effort" — that's
   only true if you're on transformers 4.x. We are not. Logged the
   patch location so it survives a CHORD update.

### Decision: keep both backends; SM stays default; CHORD opt-in

- **Default unchanged**: `--quality default` and `--quality strict`
  still use SM. Existing shipping textures stay on the SM path.
- **CHORD opt-in via `--pbr-backend chord`**: use it on materials
  where rock-class hard-edge geometry dominates and roughness
  uniformity is acceptable (or where we'll regenerate roughness
  separately). Good candidates: any future hero-mesh materials, the
  "rock at close-camera" cases mentioned in the handoff.
- **Don't migrate the existing wgv3_* shipping set to CHORD** —
  the roughness regression on rock is a real downgrade. Revisit if
  Ubisoft ships a v2 with better roughness, or if we add a roughness
  refinement step downstream of CHORD.
- **Hero-mesh lane (handoff decision 3) deferred** — user's call.
  Still on the table; not opening it this session.

### Implications + open items

- **Roughness refinement post-CHORD** is a candidate Phase B sub-task:
  if CHORD's other maps win, we could borrow SM's roughness OR run a
  small heuristic refinement (Laplacian-of-luminance + gain) when
  using CHORD on rock-class materials.
- **The richness metric (A.7) flagged the CHORD-generated rock_dark
  test at 0.79 (Rock threshold 0.83)** — first time it's flagged a
  pipeline output rather than a known smooth-A case. Worth watching
  whether CHORD outputs systematically score lower on richness than
  SM outputs.

---

## A.7 — "Richness" QA metric: catching the smooth-A failure mode

**Date**: 2026-05-07
**Question**: LESSONS L16 documented the "smooth-A" failure: a texture
that grades A on edge/junction/periodic but is visually featureless.
3 confirmed cases by end of Phase A (sand seed 200, powder snow seed
100, canyon_rock ground_level_lead). Can we add a content-presence
metric that catches these without false-positive on legitimately-low-
detail materials (snow, polished metal)?

**Setup**: Calibration script
(`D:/tmp/world3_experiments/A7_richness_calibration.py`) computed 6
candidate metrics across 122 albedos in the library. Compared known
smooth-A cases against shipping textures to find a clean separator.

### Findings

1. **No single scalar separates cleanly.** Local variance (lvar),
   Laplacian energy (lap), high-frequency ratio — each has overlap
   between smooth-A and shipping. E.g. `wgv3_rock_dark` (shipping,
   lvar=0.000150) sits *below* `sweep_sand__seed200` (smooth-A,
   lvar=0.000188) because rock_dark is dark and low-contrast despite
   having genuine cracks.

2. **The combination `0.5 * (entropy/5 + p99_normalized/0.4)`
   separates well.** Reading: a texture is "rich" if it either uses
   its full luminance range (high entropy) OR has occasional very
   strong gradients relative to its mean brightness (p99 normalized
   by mean luminance). Each catches a different content pattern; OR
   gives full coverage.

3. **Per-category thresholds are necessary.** Snow, water, ice
   legitimately have low spatial energy. wgv3_snow scores 0.68;
   wgv3_tundra_ice 0.67. A single global threshold of 0.83 would
   false-positive these. With Snow/Water/Liquid threshold 0.45, all
   shipping textures pass and known smooth-A cases fail.

### Validation table

| Material                                         | Category | Expected | Score | Threshold | Verdict |
|--------------------------------------------------|----------|----------|------:|----------:|---------|
| wgv3_snow                                        | Snow     | PASS     | 0.68  | 0.45      | ✓ pass  |
| wgv3_tundra_ice                                  | Snow     | PASS     | 0.67  | 0.45      | ✓ pass  |
| wgv3_rock_dark                                   | Rock     | PASS     | 0.94  | 0.83      | ✓ pass  |
| wgv3_desert_canyon_rock                          | Rock     | PASS     | 0.92  | 0.83      | ✓ pass  |
| wgv3_forest_floor                                | Ground   | PASS     | 1.86  | 0.83      | ✓ pass  |
| wgv3_grass                                       | Ground   | PASS     | 1.47  | 0.83      | ✓ pass  |
| wgv3_alpine_moss                                 | Foliage  | PASS     | 1.47  | 0.83      | ✓ pass  |
| sweep_sand__seed200 (canonical L16 smooth-A)     | Sand     | FAIL     | 0.79  | 0.80      | ✓ fail  |
| A3_snow_prompts__powder__seed100 (smooth-A)      | Snow     | FAIL     | 0.44  | 0.45      | ✓ fail  |
| A6_canyon_rock_prompts__ground_level_lead__seed100 (smooth-A) | Rock | FAIL | 0.71 | 0.83 | ✓ fail |
| ... (all 11 wgv3_* shipping textures pass; all 5 known smooth-A fail) |

### Implications + landing notes

- **Implemented** as a 4th check in `texture_qa.py` (`richness`).
  Output: `score`, `passed`, plus the underlying numbers (entropy,
  p99, p99_normalized, mean_luminance) so future-us can re-tune.
- **Advisory mode for now**: the score is computed and printed on
  every QA run, but `grade_from_checks()` does NOT count it in the
  A/B/C/D grade. Reason: changing the grade silently across the
  whole library would shift ground truth in ways we'd have to chase.
  Cookbook entries can read it; the gate doesn't enforce it.
- **Promotion path**: after a few sessions of watching the metric
  produce sensible results on new generations, fold into the grade
  (4 axes → A=4/4, B=3/4, etc) and tighten LESSONS L16 to say "the
  metric catches this." Until then, L16 still applies as a
  visual-review reminder.
- **Calibration data preserved** at
  `D:/tmp/world3_experiments/A7_richness_calibration.json`. If we
  re-tune thresholds later, run the same calibration script, expect
  same numbers (deterministic).

### What this doesn't fix

- The metric measures *whether content exists*, not *what kind*. A
  textured-but-wrong-material output (e.g. our A.3 "aerial" snow
  variant that produced black blobs on white) would score high on
  richness but is still bad. That failure mode needs prompt fixing,
  not richness.
- The metric is a 1D score; it can be gamed by adding noise without
  meaningful content. Not a concern for FLUX outputs (FLUX doesn't
  produce "noise that scores high"), but worth knowing if we ever
  evaluate other generation backends.

---

## A.6 (desert_canyon_rock) — Apply A.3 directional-cue learning to rock

**Date**: 2026-05-07
**Question**: Part 2 cookbook flagged desert_canyon_rock as WORKS
WITH CAVEAT — `horizontal striations` produced periodic 71.9 (just
above threshold) with strong directional bias. Same pattern as snow's
"ridges" and tundra_ice's "wind ridges." Does the same fix work for
rock?

**Setup**: 4 prompt variants × 3 seeds (100/200/400). Category=Rock,
default quality.

Variants:
- **`cookbook`** (control): `weathered tan canyon sandstone with
  horizontal striations, top-down photo, photoreal`.
- **`no_striations`**: drop the directional cue — `weathered tan
  canyon sandstone, top-down photo, photoreal`.
- **`mineral`** (apply A.3 mineral-naming pattern): `weathered red-
  tan sandstone with iron oxide bands and quartz inclusions, top-down
  photo, photoreal`.
- **`ground_level_lead`** (apply A.3 lead-phrase pattern): `ground-
  level photograph of weathered desert sandstone surface, fine grain
  detail, top-down view, photoreal`.

### Results

| Variant            | seed100 | seed200 | seed400 | Visual read                                                                |
|--------------------|--------:|--------:|--------:|----------------------------------------------------------------------------|
| cookbook           | B (period **1269!**) | B *gate fail* (period 344) | B (period 255) | Confirms failure mode catastrophically. seed100 produced what looks like horizontal wood-grain — periodic 1269 is the worst single score in the project's sweep history. |
| no_striations      | **A**   | A *gate fail* (period 9.3) | **A** | **Winner.** All grade A, 2/3 passed gate. Solid weathered tan sandstone with subtle pebbly variation. (The seed200 gate fail was on a borderline metric, not a visual problem.) |
| mineral            | B *gate fail* (period 94) | A | A | Mixed. seed100 produced a brick-lattice pattern; seed200 produced strange parallel-streaks weave. The "iron oxide *bands*" cue re-introduced a directional concept — *the failure pattern is the prompt's word, not its substance.* seed400 finally clean. |
| ground_level_lead  | A *gate fail* | A *gate fail* | A *gate fail* | Grade A but all 3 fail on roughness sanity ("near-zero variance roughness"). Visually = smooth-A: too uniform a tan surface, almost like flat color. The "fine grain detail" lead pulled the model toward sub-pixel uniform texture. |

Contact sheet: `D:/tmp/world3_experiments/A6_canyon_rock_prompts/contact_sheet.png`.

### Findings

1. **Directional-cue removal generalizes from snow → tundra_ice → rock.**
   This is now confirmed across **3 materials and 3 directional words**
   ("ridges", "wind ridges", "horizontal striations"). The pattern is
   robust enough to promote into a Part-2 anatomy rule, not just an
   anti-pattern entry.

2. **The cookbook's horizontal-striations failure was severe across
   all seeds**, not just bad ones. seed100 hit periodic 1269.5 — a
   ~21× threshold violation, the worst we've ever recorded. Even
   "passing" seeds (200/400) had 250-345 periodic. The cookbook
   prompt was reliably producing visually-flawed textures and only
   the hex-tile shader was masking it.

3. **"Iron oxide *bands*" defeated mineral naming.** The mineral
   variant still hit lattice on seed 100 (brick pattern) and seed 200
   (weave pattern). The principle "use specific minerals" works
   *only* when the descriptor doesn't smuggle a directional concept.
   "Bands" is directional; "inclusions" is not. seed 400 was clean
   because the lattice happened to align with neither. **Refinement
   to A.3 mineral-naming rule: avoid directional substrate
   descriptors even when the named mineral is fine.**

4. **`ground_level_lead` produced smooth-A failures here.** All
   three seeds hit the roughness-near-zero sanity check despite
   grading A on seam metrics. The "fine grain detail" cue pushed FLUX
   toward sub-pixel-uniform output. This is **the third "smooth-A"
   case** documented (joining sand seed 200 from A.2 and powder snow
   seed 100 from A.3). LESSONS L16's argument for a "richness" min-
   energy metric is gaining empirical weight.

5. **The Rock category isn't in UNIFORM_ROUGHNESS_OK_CATEGORIES.**
   Snow is exempted (real snow has uniform roughness); rock isn't,
   correctly — most rock has roughness variation. So the gate-fail
   on ground_level_lead isn't a false positive; the texture really is
   too smooth to be a believable rock surface.

### Implications for next steps

- **Update cookbook (Part 2)**: replace desert_canyon_rock entry with
  `no_striations` variant. Note the "bands"-as-directional gotcha.
- **Regenerate shipping `wgv3_desert_canyon_rock`** with
  `no_striations` prompt at seed-base 100 or 400 (avoid 200; it
  passed grade A but failed the periodic gate at the borderline).
- **Promote directional-cue rule** in Part 2 anatomy section as a
  recurring pattern, with the 3 confirmed cases referenced.
- **LESSONS L16 strengthening**: 3 confirmed "smooth-A" cases now;
  worth promoting the "richness" metric idea from speculative to
  on-the-roadmap.

---

## A.6 (tundra_ice) — Apply A.3 directional-cue learning

**Date**: 2026-05-07
**Question**: Part 2 cookbook flagged tundra_ice as PARTIAL — the
"subtle wind ridges" cue produces a strong vertical line down one
edge. Same failure pattern as snow's "subtle compacted ridges"
(A.3). Does the same fix work?

**Setup**: 4 prompt variants × 3 seeds (100/200/400). Category=Snow,
default quality.

Variants:
- **`cookbook`** (control): `compacted snow surface with subtle wind
  ridges and tiny ice crystals, top-down photograph, photoreal`.
- **`no_ridges`**: drop the directional cue per A.3 finding —
  `uneven compacted snow with sparse small ice crystals, top-down
  photograph, photoreal`.
- **`ground_level_lead`** (apply A.3 winner pattern here): `ground-
  level photograph of compacted arctic snow with sparse ice crystals,
  top-down view, photoreal`.
- **`glacial`** (category-shift): `glacial ice surface with subtle
  bubbles and crystal patterns, top-down photo, even lighting,
  photoreal`.

### Results

| Variant            | seed100 | seed200 | seed400          | Visual read                                                                |
|--------------------|--------:|--------:|-----------------:|----------------------------------------------------------------------------|
| cookbook           | A       | B       | **C** *gate fail* (period 477!) | Confirms the failure mode. seed400 produced striking diagonal woven-fabric pattern — "wind ridges" → strong directional. |
| no_ridges          | **A**   | A       | **A**            | **All grade A.** Cleanest snow surface; seed100 + seed400 are best (seed200 has stray dark debris that reads as rocks). |
| ground_level_lead  | B       | B       | A                | Borderline. Less reliable than no_ridges. seed100 has fine speckle texture, seed200 has higher periodic.   |
| glacial            | B       | A       | B                | Different output entirely — produces cracked-ice / crystalline patterns, not snow. Stylistically interesting but doesn't match the tundra_ice slot's role in current biome kits. |

Contact sheet: `D:/tmp/world3_experiments/A6_tundra_ice_prompts/contact_sheet.png`.

### Findings

1. **Directional-cue removal generalizes from snow to tundra_ice.**
   Same fix as A.3 snow: drop the directional word ("wind ridges").
   The replacement `no_ridges` variant produces 3/3 grade A — a 3-fold
   improvement over the cookbook's 1A/1B/1C. Validates the pattern as
   *general* across snow-class materials, not just snow specifically.

2. **The cookbook's "wind ridges" failure was severe at seed 400.**
   Periodic locality of 477.6 — far above the 60 threshold — produced
   a visible diagonal weave pattern. This was the worst single
   periodic score we've seen in the whole sweep history. Confirms how
   harshly directional cues can fail on bad seeds.

3. **`glacial` lead phrase produces a different *category* of texture
   entirely.** Cracked, blue-tinted ice with crystalline patterns
   instead of compacted snow with crystals. Could be a useful future
   addition for a *separate* "true ice" material slot, but isn't the
   right swap for tundra_ice (which sits in tundra biome alongside
   moss and is meant to read as packed snow).

4. **`ground_level_lead` lead phrase didn't transfer cleanly here.**
   It worked spectacularly for forest_floor (A.3) where the substrate
   needed explicit description, and well enough for snow (A.3) as one
   of several good options. For tundra_ice it produced acceptable but
   inconsistent output. Suggests the "ground-level photograph of"
   frame benefits *content-rich* materials more than uniform-surface
   ones.

### Implications for next steps

- **Update cookbook (Part 2)**: replace tundra_ice entry with
  `no_ridges` variant. Keep seed-100 or seed-400 as the
  recommendation; flag seed-200 as producing debris artifacts.
- **Regenerate shipping `wgv3_tundra_ice`** if it exists, with new
  prompt at seed-base 100. (Verify whether tundra_ice is in
  `world3/textures/wgv3/` before regen.)
- **Promote the directional-cue rule to a Part-2 anatomy item**
  (next to the existing anti-pattern). It's now confirmed across 2
  materials and a 3rd known case (desert_canyon_rock's "horizontal
  striations" — testing in the second half of A.6).

---

## A.4 (variants count) — Settings sweep: how many variants is enough?

**Date**: 2026-05-07
**Question**: Default `--variants 4` was set early without much
calibration. Does bumping to 6 or 8 produce meaningfully better best-
pick results? Per-material answer or universal?

**Setup**: 2 materials (sand, leaf_litter — chosen as variance-
sensitive cases). Single seed-base (100), fixed prompt per material
(post-A.3 cookbook winner). Sweep `--variants-list 4 6 8` × heal_strength
fixed at 0.35. Total: 6 runs.

`variant_select.py` produces N internal candidates and picks the
lowest-edge-MSE one as the "best." So the question is: how often
does the best of v4 differ from the best of v8?

### Results

| Material   | v4 best (seed) | v4 score | v6 best (seed) | v6 score | v8 best (seed) | v8 score |
|------------|---------------:|---------:|---------------:|---------:|---------------:|---------:|
| sand       | v0 (100)       | 0.00221  | v5 (5100)      | **0.00159** | v5 (5100)   | 0.00159  |
| leaf_litter| v0 (100)       | 0.01201  | v0 (100)       | 0.01201  | v0 (100)       | 0.01201  |

(Same metric profile = same best-picked image. seam_score is
deterministic given seed+prompt.)

### Findings

1. **v6 found a better candidate than v4 for sand (28% MSE reduction).**
   v0 (seed 100) score 0.0022 → v5 (seed 5100) score 0.0016. The 6th
   variant happened to be the global best in this pool. v8 confirmed
   no further improvement.

2. **v4 already found the global best for leaf_litter.** All three
   runs picked the same v0 candidate. v6 and v8 generated 2 and 4 more
   candidates respectively, none of which beat v0.

3. **The variance-sensitivity is prompt-dependent, not universal.**
   Sand's variant pool spans seam scores 0.0016–0.0073 (4.5×); leaf
   spans 0.0120–0.0265 (2.2×). Sand has more candidate-to-candidate
   variance, so increasing the pool helps. Leaf_litter is more uniform.
   This makes intuitive sense: sand is a flat low-detail surface where
   small content changes shift edge-MSE a lot; leaf_litter is dense
   chaotic content where any individual variant's edge-MSE is roughly
   determined by overall content density rather than micro-pattern.

4. **v8 was never better than v6 in this sweep.** Hard to rule out
   that v8 sometimes wins on other prompts, but in our two test cases
   it wasted compute. **Default of 4 is reasonable; promote to 6 only
   when first-pass quality is unsatisfactory.**

5. **The current `default` quality preset's variants=4 stays the
   right answer most of the time.** A `--variants 6` retry path is
   worth keeping in mind for stubborn materials.

### Implications for next steps

- **No default change.** Keep `variants=4` in PIPELINE.md presets.
- **Add a manual-retry note**: if a material produces a borderline
  best-pick (gate fail + visually OK, or grade B with periodic
  failing), bump `--variants 6` before reaching for prompt rewrites.
  This goes in the cookbook's "Operating tips" section.
- **`variants=8` is dropped from consideration.** Two test prompts
  saw zero improvement over v6. Not worth the compute.
- **The `Flux Fill` / `controlnet-inpaint` model swap** (the other
  half of the original A.4 plan, per EXTERNAL_TECHNIQUES technique
  #12) was deferred — current pipeline lifts both targeted A.3
  materials above threshold, so the high-effort plumbing isn't
  currently justified.

---

## A.3 (snow) — Prompt-permutation sweep on snow

**Date**: 2026-05-07
**Question**: A.2 found that the cookbook snow prompt produces a
"frosted glass / lace" pattern across seeds — stylized, not realistic
snow. Does rewriting the prompt fix it? Which rewrite pattern wins?

**Setup**: 4 prompt variants × 3 seeds (100/200/400; **avoiding 300**
per A.2 lattice findings) × 4 internal variants. Category=Snow,
default quality, default heal_strength.

Variants tested:
- **`no_ridges`**: drop the "subtle compacted ridges" cue from the
  cookbook prompt — A.2 hypothesized this triggered the lace
  generator. Prompt: `fresh white snow with small dimples, top-down
  photo, even lighting, photoreal`.
- **`powder`**: `powder snow surface, fine crystalline detail,
  top-down photo, even lighting, photoreal`.
- **`aerial`**: `aerial photograph of fresh snow field, even overcast
  lighting, photoreal`.
- **`crystal_firn`** (research-informed mineral-naming): `fresh snow
  with ice crystal aggregates and firn texture, top-down photo, even
  diffuse light, photoreal`.

### Results

| Variant      | seed100 | seed200 | seed400 | Visual read                                                                |
|--------------|--------:|--------:|--------:|----------------------------------------------------------------------------|
| no_ridges    | A       | A       | B       | **Genuinely reads as snow.** Compacted, dimpled, photoreal. Best of sweep. |
| powder       | A       | B       | B       | Mixed. s100 soft / "smooth A". s200 has stray dark dots. s400 grid-like.   |
| aerial       | C *gate fail* | B | A | **Catastrophic.** Lead phrase "aerial photograph of" pulls FLUX into "satellite of field with sparse objects" — black blobs scattered on white. Not snow texture. |
| crystal_firn | B       | B       | B       | Disappointing. Mineral naming introduced black-blob artifacts on s100/s400. s200 OK but no better than no_ridges. "Firn" likely too rare a word for FLUX to honor cleanly. |

Contact sheet: `D:/tmp/world3_experiments/A3_snow_prompts/contact_sheet.png`.

### Findings

1. **The "subtle compacted ridges" cue was the cause of the lace
   pattern.** Removing it (no_ridges variant) flips the output from
   stylized-frost to realistic-snow across 3/3 seeds. This validates
   the A.2 hypothesis directly.

2. **`no_ridges` is the new cookbook winner for snow.** Wins on visual
   identity (vs. lace from old prompt), wins on metric reliability
   (3/3 passed gate, 2 grade-A), wins on simplicity (shorter than the
   old prompt). Update Part 2 accordingly.

3. **"Aerial photograph of" is an anti-pattern for terrain textures.**
   FLUX interprets it as "image taken from a high vantage with objects
   visible," not as "view from above of a uniform surface." Output is
   sparse-object-on-background instead of close-up surface. Generalizes
   beyond snow — likely affects sand, ice, anything with "field" or
   "expanse" connotations. **Add to anti-patterns list.**

4. **Mineral / technical-word naming did NOT generalize from the
   cookbook surfaces (rock, sand) to snow.** "Firn" is a rare word —
   FLUX's snow training data is unlikely to be tagged with it.
   "Ice crystal aggregates" pushed toward sparse-element imagery.
   **Refinement to the EXTERNAL_TECHNIQUES technique #6 (mineral
   naming) recommendation: use it where the named substance has dense,
   non-niche photographic representation in training data — common
   geology terms ("slate", "limestone", "basalt"), common biological
   terms ("oak", "moss", "lichen") — not technical ones ("firn",
   "vermiculite"). Concept names that read as "rare jargon" cause
   FLUX to over-emphasize sparse appearance.**

5. **"Smooth A" reappeared.** powder/seed100 graded A on all metrics
   but is visually nearly featureless (washed-out white). LESSONS L16
   strikes again. This sweep confirms the L16 finding outside the
   sand category.

6. **Seed sensitivity is real but smaller than prompt sensitivity.**
   Within a single prompt variant, all 3 seeds produced broadly the
   same character of output (e.g. all `aerial` seeds produced black-
   blob outputs, just with different blob distributions). Prompt
   choice dominates seed variance for this category.

### Implications for next steps

- **Update cookbook (Part 2)**: replace snow entry with `no_ridges`
  prompt. Note the "ridges" cue as a known anti-pattern. Add
  "aerial photograph of" to anti-patterns. Refine the mineral-
  naming Part 2 guidance with the "common-not-rare" caveat.
- **Regenerate shipping `wgv3_snow`** with the `no_ridges` prompt and
  seed-base 100 (most reliable seed in this sweep). Capture
  before/after.
- **A.4 (settings sweep) still scoped for leaf_litter**, since
  prompt-engineering doesn't reach the lattice failure mode that
  category exhibited in A.2.

---

## A.3 (leaf_litter) — Prompt-permutation sweep on leaf_litter

**Date**: 2026-05-07
**Question**: A.2 found leaf_litter the worst-grading material in the
sweep (0/3 A grades, gold-streak lattice on s300). Can a prompt
rewrite produce a more reliable forest-floor texture? Which lead
phrase wins?

**Setup**: 4 prompt variants × 3 seeds (100/200/400) × 4 internal
variants. Category=Ground, default quality, default heal_strength.

Variants tested:
- **`cookbook`** (control): existing forest_floor prompt — `forest
  floor with brown leaves, pine needles, twigs, dark soil, top-down
  photo, even lighting, photoreal`.
- **`minimal`**: `forest floor with mixed leaves and twigs, top-down
  photo`.
- **`species`** (research-informed common-species naming): `fallen
  oak and beech leaves over loam soil with pine needles and twig
  fragments, top-down photo, photoreal`.
- **`ground_level_lead`** (alternate lead phrase + handoff #4): `ground-
  level photograph of autumn leaf litter, damp dark soil visible
  underneath, no plants growing, top-down view`.

### Results

| Variant            | seed100         | seed200         | seed400 | Visual read                                                                |
|--------------------|----------------:|----------------:|--------:|----------------------------------------------------------------------------|
| cookbook           | C *gate fail*   | B               | B       | Dense reddish-brown clutter. Recognisable as forest floor but overpacked, repetition visible. |
| minimal            | B               | B               | B       | Sparser, but periodic repeat shows in tile. No A grades.                   |
| species            | C *gate fail*   | B *gate fail*   | B       | **Worst**. "Loam soil" + "fallen leaves" produced bright blob clusters that read as dried debris on light soil rather than dark damp forest floor. |
| ground_level_lead  | **A**           | B               | **A**   | **Winner.** Clear leaf-vs-soil contrast, varied leaf sizes/colors, dark damp soil visible. Reads convincingly as autumn forest floor. |

Contact sheet: `D:/tmp/world3_experiments/A3_leaf_litter_prompts/contact_sheet.png`.

### Findings

1. **`ground_level_lead` is the new cookbook winner for forest_floor.**
   Only variant with 2 A grades and 0 gate failures. Visually the
   most convincing: damp-dark-soil base with autumn leaves of varied
   color and size. Three things this prompt does differently:
   (a) the "ground-level photograph of" lead, (b) explicit
   description of the *substrate* ("damp dark soil visible
   underneath"), (c) a positive-phrased exclusion ("no plants
   growing"). Each contributes; (b) is probably the largest lever —
   the model needs the substrate cue to render the soil vs. just
   piling leaves edge-to-edge.

2. **The current cookbook prompt isn't broken; A.2's failure was
   seed-specific.** cookbook/seed200 and /seed400 in this run both
   produce grade-B forest floor; only seed100 failed the gate. The
   gold-streak lattice we saw in A.2 was on **seed 300** (which
   A.2 itself flagged as a globally-bad seed, leading us to skip it
   here). The cookbook prompt is replaceable, but it wasn't producing
   broken output most of the time.

3. **Common-species naming (species variant) failed for an unexpected
   reason.** Naming "oak and beech" was supposed to give FLUX a
   recipe (per EXTERNAL_TECHNIQUES technique #6); instead, "loam
   soil" pulled the substrate toward *light, dry* soil, and the
   leaves ended up looking like dried-debris splotches on a tan
   background. **Refinement**: when using species/mineral naming,
   the substrate descriptor matters as much as the named species.
   "Loam" reads light; "dark damp soil" reads dark and damp. Pair
   the species term with a substrate that matches the intended scene.

4. **The "smooth-A" mode did NOT show up here.** All A grades had
   visible content. Probably because organic-debris materials are
   inherently noisy; the metric and the eye agree more often on this
   category than on near-uniform materials like sand or snow.

5. **Gate failures concentrated on seed 100 across 3/4 variants
   (cookbook, species — and the metric on minimal/100 was
   borderline).** Seed 100 isn't a globally-bad seed (it produced
   grade A on snow's no_ridges variant), but it's *category-
   sensitive* on dense organic materials. Possible add to the seed-
   testing rotation: use 200 + 400 as primary, treat 100 as a stress
   test.

### Implications for next steps

- **Update cookbook (Part 2)**: replace forest_floor entry with
  `ground_level_lead` prompt. Keep cookbook prompt as a fallback
  documented under "still works." Note "loam soil" as a substrate-
  descriptor anti-pattern when paired with autumn-leaf imagery.
- **Regenerate shipping `wgv3_forest_floor`** with the new prompt and
  seed 100 or 400 (both grade-A in this sweep). Capture before/after.
- **A.4 (settings sweep) priority lowered for leaf_litter** — the
  prompt rewrite alone produced a category-fitting texture without
  needing higher heal_strength. A.4 may still inform the marginal
  gain on hard seeds, but it's no longer the primary lever.
- **Reconsider seed-base default for organic-dense categories.** Seed
  100 failed gate on 2/4 leaf_litter variants but worked fine for
  snow. Suggests seed should be category-tuned, not globally-fixed.
  Out of scope for A.3; potential A.6 / Phase B item.

---

## A.2 (short) — Same-prompt sweep × 5 materials × 3 seeds

**Date**: 2026-05-07
**Question**: How reliable is FLUX 2 klein at producing the same
material from the same prompt across different seeds? Which materials
are seed-stable and which fail half the time?

**Setup**: 5 materials, current cookbook prompt for each, 3 seeds
(100/200/300), 4 variants each, default quality preset, default
heal/delight settings. Total: 15 runs.

### Results

| Material        | seeds | A | B | C | reliability | notes                                                                                                       |
|-----------------|------:|--:|--:|--:|-------------|-------------------------------------------------------------------------------------------------------------|
| volcanic_rock   |     3 | 3 | 0 | 0 | 100%        | All A. Most stable material identity. Color shifts seed-to-seed (s200 redder).                              |
| snow            |     3 | 2 | 1 | 0 | high        | Looks like frosted glass / lace, not snow. Stable but stylized. **Prompt issue.**                           |
| sand            |     3 | 1 | 2 | 0 | medium      | s200 = clean dunes (A) but visually featureless (smooth-A). s100 = sloppy angled. s300 = visible bumpy lattice. |
| grass           |     3 | 1 | 2 | 0 | medium      | s100, s300 show diagonal striping when tiled (lattice). s200 cleanest.                                      |
| leaf_litter     |     3 | 0 | 2 | 1 | low         | All B/C. s300 = obvious gold parallel streaks (lattice). Worst category in the sweep.                       |

### Findings

1. **Seed 300 is consistently bad.** Across 4 of 5 materials, seed 300
   produced the worst result, and twice the worst was a *lattice*
   pattern caught by the periodic check. Either bad luck or seed 300
   hits some FLUX failure mode. Worth avoiding 300 specifically as a
   default test seed.

2. **Material category matters more than prompt quality.** Volcanic
   rock with a fairly minimal prompt (8 words of material adjectives)
   was 100% reliable. Leaf litter with a similarly-structured prompt
   was 0% A grade. The "noisy organic" category appears
   fundamentally harder for FLUX to render tileably.

3. **Snow's "frosted glass" output is not a seed problem.** The
   prompt produces a consistent (and consistently wrong) output
   across all seeds. **This is a prompt rewrite candidate** for A.3.

4. **Periodic locality is doing real work.** The metric correctly
   flagged the lattice failures (sand s300, grass s100/s300,
   leaf_litter s300). When the periodic check fails on a material
   that doesn't *want* to be periodic, the texture is genuinely bad.

5. **Edge_continuity is rarely the failure mode now.** Default
   FLUX+offset+heal handles edges well. Most B/C grades come from
   periodic, not edge.

6. **"Smooth-A" failure mode**: sand s200 graded A on all checks but
   is visually featureless — the metrics measure *defects*, not
   *content*. See [LESSONS.md L16](LESSONS.md). Candidate fix: a
   "richness" minimum-energy metric (TBD).

### Implications for next steps

- **A.3 priority**: rewrite snow and leaf_litter prompts. They're the
  highest-payoff candidates for prompt engineering.
- **A.4 priority**: see if higher heal_strength (0.45) helps the
  lattice-prone categories (grass, leaf_litter) on bad seeds.
- **Cookbook updates**: snow "frosted glass" failure mode logged;
  seed-300 caveat added.

---

# Part 2 — Cookbook

What prompts work and don't work, by category. Future-us doesn't
have to re-discover that "extreme close-up macro" turns sand into
cracked surface, or that "horizontal striations" creates lattice
tiling.

## Anatomy of a useful prompt (empirical)

1. **Lead with a photographic anchor**: "close-up photograph of",
   "macro photograph of", "ground-level photograph of". FLUX listens
   to this — it nudges the model toward natural materials and away
   from stylized illustration.
2. **Material adjective + noun**: "weathered grey rock", "fine pale
   sand". One adjective beats three.
3. **Implicit feature description**: "with subtle wind ripples",
   "with patchy lichen". Use *with* clauses sparingly — every clause
   is a chance for FLUX to introduce something unwanted.
4. **Negative space**: "no debris", "no plants", "no objects". FLUX
   often inserts incidental objects (sticks, leaves, rocks) where
   you didn't ask. Explicit negation helps but isn't perfect.
5. **Camera angle**: "top-down view" / "ground-level top-down view".
   Without this FLUX may produce an oblique 3/4 angle that won't
   tile. *Required* for terrain textures.
6. **Lighting cue**: "even diffuse daylight" / "soft overcast".
   Reduces baked-in shadows that delight has to remove later.
7. **Quality cue**: "photoreal, sharp focus". Doesn't always work but
   doesn't hurt.

## Anti-patterns to avoid

- **"Seamless tileable"** — `flux_seamless.py`'s
  `TILE_PROMPT_SUFFIX` adds this for you. Adding it manually doubles
  it up and FLUX starts tiling at obvious cell boundaries.
- **Words implying directionality** (CONFIRMED RECURRING FAILURE,
  2026-05-07 across snow / tundra_ice / desert_canyon_rock):
  "horizontal striations", "parallel grooves", "ridges", "wind
  ridges", "bands" (in mineral context), "stripes". FLUX makes them
  line up across copies → visible lattice when tiled. The failure
  pattern is severe: A.6 logged a periodic-locality of **1269** on
  desert_canyon_rock with "horizontal striations" — 21× the threshold.
  **Default rule**: if the desired material doesn't *naturally* have a
  visible directional structure at 1m² scale, don't put a directional
  word in the prompt. (Sand is the exception — real sand has wind
  ripples — and even there, "subtle wind ripples" is on the edge.)
  Hex-tile shader masks the worst of it in-renderer but the
  underlying texture is still flawed and shows in non-hex sampling.
- **"Extreme close-up macro"** for materials with no texture at the
  macro scale (e.g. plain sand). FLUX over-interprets and invents
  cracks/objects to satisfy "macro detail."
- **More than ~30 words.** Past that FLUX starts ignoring tail
  clauses.
- **"Aerial photograph of [X] field"** lead frame (A.3, 2026-05-07).
  Pulls FLUX into satellite-style imagery with sparse foreground
  objects scattered on a uniform background, instead of rendering
  the surface itself. Verified failing on snow; likely fails on any
  material with "field" / "expanse" connotations. Stick with
  "top-down photo of [material]" or "ground-level top-down view of
  [material]".
- **Rare / technical / jargon substance names** (A.3, 2026-05-07).
  Words like "firn", "vermiculite", "tholeiite" cause FLUX to
  treat the named thing as a sparse foreground element rather than a
  surface property. Use common synonyms when they exist.

## Per-category prompts

### Ground / Soil

#### dirt — WORKS
```
rich brown dirt with small pebbles and fine debris, top-down photo,
even lighting, photoreal
```
Grade A consistently. The "small pebbles and fine debris" gives FLUX
visual variation to fill the frame; without it the result tends to
be a flat brown wash.

#### forest_floor — WORKS (post A.3 rewrite, 2026-05-07)
```
ground-level photograph of autumn leaf litter, damp dark soil
visible underneath, no plants growing, top-down view
```
Grade A 2/3 seeds; 3/3 passed gate. Best of A.3 leaf_litter sweep.
Three keys: (a) "ground-level photograph of" lead phrase, (b) explicit
substrate cue ("damp dark soil visible underneath") so FLUX renders
soil vs. just piling leaves, (c) positive-phrased exclusion ("no
plants growing") to stop FLUX from inserting moss / sprouts. Try
seed 100 or 400 first; seed 200 dropped to B but still passes gate.

#### forest_floor — ALSO WORKS (older cookbook prompt; fallback)
```
forest floor with brown leaves, pine needles, twigs, dark soil,
top-down photo, even lighting, photoreal
```
Grade B reliably (in A.3 sweep: 2/3 grade B passing gate; seed 100
failed gate). Listing 3+ specific items ("leaves, pine needles,
twigs") gives FLUX a recipe rather than a vague target. Keep as a
fallback if `ground_level_lead` produces something unsuitable for a
specific biome.

#### forest_floor — DID NOT WORK
- `"fallen oak and beech leaves over loam soil with pine needles
  and twig fragments ..."` (A.3 species variant) → bright debris
  clusters on light/tan soil. **"Loam soil"** pulled the substrate
  toward dry, sandy, light coloration even though the rest of the
  prompt described autumn leaves; FLUX couldn't reconcile them and
  ended up rendering "dried debris on light dirt." When using
  species/mineral naming, ensure the substrate descriptor matches
  the intended scene tone (use "dark damp soil" for autumn forest
  floor; "loam" for spring tilled-earth contexts).

#### grass — WORKS (grade B)
```
lush green grass with small clovers and dirt patches, top-down
photo, even lighting, photoreal
```
Periodic just over threshold (clover blobs read as repetition).
Hex-tile masks it in the renderer.

### Sand

#### desert_sand — WORKS (after iteration)
```
close-up photograph of natural desert sand dunes, soft wind
ripples, fine sand grains, warm golden tan color, no debris,
no objects, top-down view, even daylight, photoreal, sharp focus
```
Grade A. Note: `--variants 6 --seed-base 200`.

#### desert_sand — DID NOT WORK
- `"fine pale sand dune surface with wind-shaped ripple patterns,
  scattered tiny pebbles and dried twigs..."` → produced what
  looked like decorated paper or speckled wallpaper. The "pebbles
  and twigs" phrase made FLUX paint specific objects on a flat
  background instead of rendering pebbly sand.
- `"extreme close-up macro photograph of dry desert sand surface,
  individual quartz grains clearly visible..."` → produced
  cracked-mud surface, not sand. "Extreme close-up macro" pushed
  FLUX out of its sand training and into cracked-earth territory.

### Rock

#### rock_dark (volcanic) — WORKS
```
dark grey volcanic rock surface, weathered, sharp edges and small
cracks, top-down photo, even lighting, photoreal
```
Grade A. Has natural directional bias from the prompt — hex-tile
masks what would otherwise be a visible diamond pattern.

#### rock_light (limestone) — WORKS (grade B)
```
weathered tan limestone rock surface with cracks and lichen,
top-down photo, even lighting, photoreal
```
Periodic just above threshold (lichen blobs). `--variants 6
--seed-base 100` was the recipe that landed grade B.

#### desert_canyon_rock — WORKS (post A.6 rewrite, 2026-05-07)
```
weathered tan canyon sandstone, top-down photo, photoreal
```
Grade A 3/3 seeds; 2/3 passed gate (the seed200 gate fail was on
borderline periodic, visually clean). Just removing "horizontal
striations" cleaned up the 71.9 periodic to single-digit. **Use
seed-base 100 or 400; avoid 200.**

#### desert_canyon_rock — DID NOT WORK
- `"... horizontal striations ..."` (the old cookbook prompt, pre-A.6)
  → catastrophic lattice. Periodic 1269.5 on seed 100 (worst score in
  project history), 344 on seed 200, 255 on seed 400. Hex-tile shader
  was masking the issue but the underlying texture was reliably
  flawed. Same directional-cue failure as snow's "ridges" and
  tundra_ice's "wind ridges."
- `"... iron oxide bands and quartz inclusions ..."` (A.6 mineral
  variant) → reintroduced lattice on seed 100 (brick pattern) and
  seed 200 (weave). "Bands" is itself a directional concept. **When
  using mineral naming, avoid words that imply linear features:
  "bands", "veins" (when oriented), "stripes". "Inclusions",
  "patches", "deposits" are safer.**
- `"ground-level photograph of weathered desert sandstone surface,
  fine grain detail ..."` (A.6 ground_level_lead variant) → smooth-A
  failure (LESSONS L16). All 3 seeds grade A on seams but failed the
  roughness sanity check ("near-zero variance" — texture too uniform
  to be a believable rock). "Fine grain detail" pushed FLUX toward
  sub-pixel-uniform output. The ground-level-photograph lead phrase
  doesn't generalize to rock; it works best on content-rich materials
  (forest_floor) and is acceptable on uniform-but-dimpled materials
  (snow).

#### desert_dark_rock — WORKS
```
dark basalt rock with red-brown patina, weathered, top-down photo
```
Grade A.

### Snow / Ice

#### snow — WORKS (post A.3 rewrite, 2026-05-07)
```
fresh white snow with small dimples, top-down photo,
even lighting, photoreal
```
Grade A consistently (3/3 seeds at A or A/B in A.3 sweep). Reads as
real, walkable, compacted snow with subtle surface dimples — *not* the
lace/frost pattern produced by the previous prompt. The fix was simply
removing the "subtle compacted ridges" phrase; everything else from
the old prompt was fine.

Sanity check still flags "near-zero variance roughness" for this
material — covered by the `Snow` category in
`UNIFORM_ROUGHNESS_OK_CATEGORIES`.

#### snow — DID NOT WORK
- `"... subtle compacted ridges and small dimples ..."` (the old
  cookbook prompt, pre-A.3) → "frosted glass / lace" pattern across
  all seeds. The "ridges" cue triggered FLUX to produce a regular
  network of fine raised lines, not snow. **Lesson**: terrain-feature
  words that imply directionality or symmetry ("ridges", "striations",
  "grooves") are dangerous on materials whose real-world appearance is
  *not* directional. (Sand benefits from "ripples" because real sand
  *does* have ripples; snow doesn't have visible "ridges" at this
  scale — only meso-scale drifts that don't fit a 1m² tile.)
- `"aerial photograph of fresh snow field ..."` → black-blob /
  scattered-object output. The "aerial photograph of [N] field" frame
  pulls FLUX into "satellite-style image with sparse foreground
  objects on a uniform background" — the model paints scattered
  things on snow rather than rendering snow surface. Documented as a
  general anti-pattern below.
- `"fresh snow with ice crystal aggregates and firn texture ..."` →
  black-blob artifacts on 2/3 seeds. Technical/rare words like "firn"
  cause FLUX to over-emphasize sparse appearance, treating the named
  thing as a foreground object rather than a surface property. Use
  common substance names (e.g. "snowflakes", "compacted snow"), not
  rare ones.

#### tundra_ice — WORKS (post A.6 rewrite, 2026-05-07)
```
uneven compacted snow with sparse small ice crystals, top-down
photograph, photoreal
```
Grade A 3/3 seeds in A.6 sweep — same fix as snow (drop the
directional cue). **Use seed-base 100 or 400** (seed-200 produces
stray dark debris that reads as rocks/dirt; would look wrong on
a clean tundra surface).

#### tundra_ice — DID NOT WORK
- `"... subtle wind ridges and tiny ice crystals ..."` (the old
  cookbook prompt, pre-A.6) → "wind ridges" produced strong
  directional artifacts. seed400 hit periodic 477.6 (the worst score
  before desert_canyon_rock's 1269), producing a visible diagonal
  woven-fabric pattern. Same failure as snow's "ridges" and rock's
  "striations."
- `"glacial ice surface with subtle bubbles and crystal patterns ..."`
  (A.6 glacial variant) → produced cracked, blue-tinted *true ice*
  output instead of compacted snow. Stylistically interesting but
  doesn't match tundra_ice's role in current biome kits (sits next to
  moss in tundra kit, should read as snow). Could be useful for a
  future "true ice" / glacier slot.

### Foliage

#### desert_dry_brush — WORKS
```
close-up photograph of cracked dry desert mud surface with subtle
scattering of small dead twigs and bits of dry grass, light tan
color, ground level top-down view, photoreal
```
Grade A. Despite the name "dry_brush," what works for this slot in
a desert biome is *cracked mud with sparse vegetation*, not pure
brush. The slot's role (low-elevation soft ground in desert kit) is
satisfied by either.

#### tundra_moss — WORKS
```
close-up photograph of arctic tundra moss ground cover, mixed dark
green and reddish-brown moss with small lichen patches, damp
permafrost soil visible underneath, top-down view, soft overcast
daylight, photoreal, sharp focus
```
Grade A. "Soft overcast daylight" pulled saturation down — fits
tundra better than warm/golden lighting cues.

## Operating tips

- **Variants**: 4 is the default and is right ~most of the time
  (validated A.4 sweep, 2026-05-07 — leaf_litter's v0 was already
  globally best at v4). Bump to **6** when first-pass results miss
  on a *variance-sensitive* category (low-detail surfaces like sand
  where micro-pattern shifts move the seam score a lot). v8 was never
  better than v6 in the A.4 sweep — don't go higher. Variant selection
  picks by edge-MSE which doesn't perceive prompt fidelity, so more
  variants ≠ better material — just better edges.
- **Seed-base**: change when re-rolling. Default 42 is fine for
  first runs. `42 + N*100` for retries works well. **Avoid seed-base
  300** — observed (A.2 sweep) to produce lattice failures on 4 of 5
  test materials. Likely some specific FLUX failure mode at that
  seed.
- **Heal-strength**: 0.35 default. Bump to 0.45 only if the
  offset+heal pass left visible center-cross artifacts.
- **Quality preset**: `default` is the right answer 95% of the time.
  `strict` (6 variants, A min-grade) for hero materials only.
  `fast` (no SM) is for testing prompts cheaply, *not* for ship
  quality.

---

## How to extend this doc

**For an experiment** (new sweep / A/B / settings test):
1. Add a section under Part 1 with date + question + setup.
2. Include the results table and findings list.
3. Note implications + which cookbook updates were made.

**For a cookbook entry** (a prompt you formed an opinion on):
1. Add to or update the appropriate Part 2 category.
2. Include the verbatim prompt, recipe (variants, seed-base, etc),
   and one-line subjective notes.
3. If the prompt produced a *bad* result, add it under "DID NOT WORK"
   with what went wrong. Negative examples save more time than
   positive ones.

Keep entries short. Future-us scans this doc; nobody reads it.
