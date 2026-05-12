# W4 Texture Pipeline Audit — 2026-05-12

> **HISTORICAL.** This is the audit document that started the texture
> pipeline rebuild. **Most of its predictions turned out wrong** — see
> `TEXTURE_PIPELINE_FINDINGS_2026_05_12.md` for what we actually
> learned. The canonical "this is the W4 texture pipeline" doc lives
> at `../features/textures.md`. This audit is kept as a record of
> reasoning, not as current guidance.

## Why this audit exists

The texture pipeline at `D:/assets/pipelines/textures/` was built for
the W3 / `aaa_texture.py` line of work — 512px source materials, mixed
categories, FLUX-1 / klein-4B-era prompt handling, hard-surface focus.
W4 now uses it for **terrain at 1024px on klein-9B**, viewed from three
camera modes at once (3D close-up, 2.5D oblique, top-down distance).
Different scale, different model, different consumer, different
quality bar.

We have been tuning knobs around the edges (thresholds, prompts,
filters) without ever asking whether the **architecture** is still
right. This audit walks each stage end-to-end and asks four questions:

1. What is the stage *for*?
2. Is the implementation modern, or 2-year-old conventional wisdom?
3. Is it necessary for W4 terrain at 1024px on klein-9B?
4. **W4 decision:** keep / fork / replace / delete?

## W4 quality bar (the thing we're actually optimizing for)

Terrain textures get viewed in three modes simultaneously:

| Mode      | Distance        | What kills it                              | What matters |
|-----------|-----------------|--------------------------------------------|--------------|
| 3D close  | 1–5m above surface | Stock-photo cinematic detail, baked shadows, "macro shot" framing | Even diffuse lighting, top-down framing, micro-detail consistent with prompt |
| 2.5D ang. | ~20m oblique     | Normal disagreement with albedo, weird PBR specular | PBR maps that match albedo's implied surface, plausible roughness response |
| Top-down  | 100–500m flat    | Periodic lattice fingerprints, hard tile boundaries, color clashes between adjacent tiles | True tileability, consistent per-biome palette, no large-scale repetition signature |

A single texture must perform on *all three*. This is a stricter bar
than the original pipeline targets (which scored seam-cleanness on a
single 1024² square in isolation).

## Pipeline as it is today

```
prompt
  ↓
STAGE 1: variant_select.py  (generate N seeds, pick lowest seam-score)
  ↓ (uses flux_seamless.py = 4-pass FLUX with TILE_PROMPT_SUFFIX)
STAGE 2: delight.py  (LAB large-blur subtract, strength=0.4)
  ↓
STAGE 3: PBR backend  (StableMaterials default; CHORD / derive_pbr_v2 alts)
  ↓
STAGE 4: seam_repair.py  (PatchMatch over offset cross — same trick FLUX already did)
  ↓
STAGE 5: texture_qa.py  (edge_continuity / junction_visibility / periodic_artifact)
  ↓
STAGE 5b: blender_preview.py  (optional)
  ↓
STAGE 6: quality gate
  ↓
STAGE 7: catalog
  ↓
STAGE 8: mip ladder (optional)
```

## Per-stage findings

### STAGE 1 — Variant generation + select (`variant_select.py` + `flux_seamless.py`)

**Purpose:** generate N seeds at same prompt, pick the "best." Currently
"best" means lowest `edge_seam_score` (L/R + T/B edge MSE).

**Modern?** The 4-pass flux_seamless (text2img → offset-shift → img2img heal → offset back) is industry-standard for tiling diffusion outputs. **Solid.** Keep.

**But:** the *selection metric* is wrong for our use case.
- We use seam-score to pick, then run seam-repair after, so the
  "best" seam was going to get repaired anyway. We're throwing away
  candidates that look better but have slightly worse pixel-edge
  seams — a metric the repair stage exists to fix.
- `flux_seamless` already includes seam-aware generation (TILE_PROMPT_SUFFIX
  + offset+heal pass). All 4 candidates already tile reasonably. The
  variation between them is *aesthetic*, not seam-quality. Picking
  by seam ranks them on a near-noise dimension.

**Known bug surfaced in code comments:** `Pass 3 heal pass with Flux2Scheduler silently ignores the denoise parameter`. So the
`--heal-strength 0.35` knob does nothing — every heal pass runs at
effectively full denoise=1.0. This means the heal pass may be the
*source* of the lattice fingerprint we see at 1024 (because full-denoise
heal can paint in a new pattern at the offset-cross frequency). Filed
in source as "TEXTURE_RND open question; potential future audit task."

**W4 decision: FORK.**
- Keep `flux_seamless.py` (the 4-pass generation).
- Replace `variant_select.py` with a W4 version that:
  - Keeps *all* variants by default (the "throwaway 3 of 4" pattern is wrong
    — they're valuable for human review and for the contact sheet).
  - Selects best by a *composite* score:
    `0.4 * (1 - seam_normalized) + 0.4 * (1 - periodic_normalized) + 0.2 * richness`
    Not seam-only. Periodic-locality matters more for terrain at distance.
  - Fixes the `honor_denoise=True` bug — actually run heal at 0.35
    instead of 1.0. The 1.0 heal is almost certainly what produces the
    klein-9B-at-1024 lattice fingerprint we keep seeing.

### STAGE 2 — De-lighting (`delight.py`)

**Purpose:** strip baked illumination from albedo so engine lighting
doesn't double up.

**Modern?** **No.** LAB → large-blur → subtract is a 2010s technique.
It treats *all* large-scale luminance variation as lighting, which
means it also flattens legitimate large-scale albedo variation (dunes,
patches, color gradients across the texture). This is the "v3 looks
better than canonical" failure mode the user noticed — delight
genuinely makes things flatter and uglier when the source isn't
actually over-shaded.

**Does W4 need it?** Half-no. `flux_seamless.py` already injects
`"even neutral diffuse lighting, no shadows, no highlights, no vignette"`
into every prompt. So FLUX outputs are *already* mostly flat-lit. Then
we delight them anyway, on top. We're fighting our own prompt.

**2026 alternatives:**
- **IC-Light (intrinsic image decomposition)** — Stable-Diffusion-based
  model that separates albedo from shading. Knows what's lighting vs.
  what's surface color. ~10s on a 5090.
- **DeLighter / UDM models** — purpose-built de-lighting nets.
- **Just trust the prompt + skip delight** — if the prompt already
  asks for flat lighting, delight is fighting a non-problem.

**W4 decision: REPLACE (with option to disable per-prompt).**
- Default for W4: **delight strength = 0.0** (skip). The prompt
  already handles it.
- Add a per-category override in the yaml (`delight: 0.3` for
  prompts that turn out cinematic anyway).
- Add an opt-in modern delighter (IC-Light) as a backend choice for
  cases where the source is unsalvageable. Not default; opt-in until
  benched.

### STAGE 3 — PBR estimation

**Backends in order of W4 fit:**

#### `derive_pbr_v2` (heuristic, no model)
**Pros:** zero divergence between albedo and derived maps; every map
is mathematically determined by the albedo, so they can't disagree.
Cheap, fast, predictable.

**Cons:** boring height/normal (just sobel-from-luma); roughness is
category-mean ± albedo-contrast (so flat).

**W4 fit:** **good for terrain at distance.** Top-down view at 100m+
mostly sees albedo + lighting interaction. Subtle PBR detail won't
read. Better to have consistent-with-albedo maps than over-detailed
maps that disagree.

#### `sm` (StableMaterials)
**Pros:** real diffusion-predicted PBR; rich micro-detail; varied
roughness.

**Cons:** trained on hard surfaces (rock, metal, concrete). Snow /
organic / soft materials get plausible-looking-but-wrong maps. SM
*invents* surface detail not present in the albedo — failure mode is
"albedo says smooth snow, normal map says sharp crystals." Especially
visible at 3D close-up view.

**W4 fit:** **risky for terrain.** Probably fine for rock-class
slots, harmful for snow / soft mid slots. Currently used as default
for `default` quality preset — wrong default for W4.

#### `chord` / `chord_sm_rough`
**Pros:** Ubisoft's CHORD model; trained on a broader material set;
hybrid mode replaces CHORD's near-flat roughness with SM's varied one.

**Cons:** requires ComfyUI custom nodes; one more dependency to
maintain; not benchmarked specifically for terrain.

**W4 fit:** unknown. Worth one experiment row.

**W4 decision: KEEP all three backends, change DEFAULT.**
- Default for `default` preset → `derive_pbr_v2` (was `sm`).
- `sm` opt-in via `--pbr-backend sm` for materials where the source
  has rich surface detail (rock slots, often).
- `chord_sm_rough` stays as a research option; do not default until
  a controlled experiment shows it beats derive_pbr_v2 on terrain
  metrics.

### STAGE 4 — Seam repair (`seam_repair.py`)

**Purpose:** offset-shift → PatchMatch over the visible cross → shift back.

**Modern?** PatchMatch is solid. The technique is fine.

**But:** **we're doing the same trick twice.** Pass 3 of
`flux_seamless.py` already does offset+img2img-heal+offset-back.
Then seam_repair does offset+PatchMatch+offset-back. The first uses
FLUX to repaint the seam cross; the second uses sampled patches.
Both are valid, but doing both *on the same output* means
patch-quilting over already-FLUX-healed regions. PatchMatch is good
at hiding seams in noise; it's *bad* at preserving long-range
structure the FLUX heal already put there.

**W4 decision: SIMPLIFY — make seam_repair conditional.**
- If FLUX heal pass succeeded (edge_seam_score < threshold), **skip
  seam_repair entirely.** Trust the FLUX result.
- Only fall back to PatchMatch repair when FLUX heal left a visible
  seam (rare in practice once heal-denoise is fixed).
- The current "always-run-repair" default is double work.

### STAGE 5 — QA (`texture_qa.py`)

**Purpose:** measure 4 metrics (edge_continuity, junction_visibility, periodic_artifact, richness), grade A–D.

**Modern?** Yes for what it measures. Three orthogonal checks +
per-category thresholds is sound design.

**But:** **all four metrics evaluate a single 1024² square in
isolation.** None of them simulate terrain viewing:
- A texture passes edge_continuity if its left edge matches its
  right edge. Says nothing about whether the texture *looks good*
  tiled across 5km.
- periodic_artifact catches a sharp FFT peak. Doesn't catch low-
  frequency cinematic structure (e.g. `old_drift`'s dune shape
  that reads as wave-on-loop when tiled).
- richness measures information density on the flat image. Doesn't
  measure whether the detail survives at distance / under
  bilinear filter / under mipmapping.

**Bugs/quirks already known:**
- Snow threshold was 18 → tightened to 13 (this session). Empirical
  calibration needed for other categories.
- Mid slots use category "Snow" even when their content is rock-with-
  snow — wrong category for the threshold. Should be "Rock" or a
  new "Mixed".

**W4 decision: EXTEND with terrain-aware metrics.**
- Keep all 4 existing checks.
- Add 3 new W4-specific checks:
  1. **`tile_4x4_lattice`** — render the texture 4×4 in memory and
     run periodic_artifact on the *mosaic*, not the source. Catches
     `old_drift`-style "looks fine alone but bad when tiled."
  2. **`mip_richness_decay`** — generate the 256/128/64/32px mip
     levels and measure how fast detail drops. If mip32 is nearly
     uniform grey, the texture won't read at distance.
  3. **`palette_lock`** — compute a 5-color palette from the albedo
     and store it. At biome promotion time, check that all candidate
     winners across a biome's 3 slots are palette-coherent (no
     wildly different greens between ground and mid).
- Per-biome / per-slot category override in the yaml. Stop hoping
  one category fits all.

### STAGE 5b — Blender preview

**Purpose:** real PBR lit-sphere render for review.

**W4 decision: KEEP as-is.** Useful for human review. Doesn't affect
gate. Already non-fatal if blender invocation fails.

### STAGE 6 — Quality gate

**Purpose:** combine grade + sanity + map-completeness into one PASS/FAIL.

**Modern?** Yes. Multi-check verdict is right.

**W4 decision: KEEP, but rethink defaults.**
- Default `min_grade` for diversity batches → C (not B). We want
  *all* candidates to surface for review/auto-rerank. The current
  hard B+ gate at default quality means borderline-good candidates
  get dropped on the floor when they could win after composite re-scoring.
- Gate decision moves to **after the new W4 tile-mosaic + mip-decay
  metrics**, not just the 4 single-image checks.

### STAGE 7 — Catalog

**Purpose:** append-only JSONL catalog of every shipped material.

**Modern?** Catalog as JSONL is fine. The data model (id / prompt /
maps / grades) is fine.

**But:** the catalog is in `D:/assets/world/textures/catalog/`, not
in W4. W4 candidates go into the catalog along with everything else.
This blurs "experimental candidate" with "shipped material."

**W4 decision: SPLIT.**
- W4 candidates → W4-owned `_index.json` per slot (this session's
  reorg already does this).
- Promotion (winner → biome material) → also write to the shared
  catalog, *flagged as W4-shipped*.
- Don't write *every* candidate to the shared catalog; only winners.

### STAGE 8 — Mip ladder

**Purpose:** SR → bake at high-res → downsample → per-tier QA. For
shipping materials at multiple resolutions.

**W4 decision: DEFER.** Not needed for the diversity-pool stage.
Run only on winners, post-promotion.

## Summary table — what we keep, fork, replace

| Stage             | Current state                  | W4 decision                                     |
|-------------------|--------------------------------|-------------------------------------------------|
| `flux_seamless`   | 4-pass FLUX, mostly works      | **KEEP**, fix `honor_denoise` bug (heal=0.35 actually)            |
| `variant_select`  | seam-min, throws away 3 of 4   | **FORK** — composite score, keep all, fix heal-denoise            |
| `delight`         | LAB blur-subtract @ 0.4        | **REPLACE** default → 0.0 skip; opt-in IC-Light backend           |
| `derive_pbr_v2`   | heuristic, deterministic       | **KEEP, promote to default** PBR backend                          |
| `stablematerials` | currently default              | **KEEP, demote** to opt-in for rock slots                         |
| `chord` / hybrid  | opt-in experiment              | **KEEP** as research option                                       |
| `seam_repair`     | PatchMatch, always-runs        | **SIMPLIFY** — only run when FLUX heal didn't fix the seam        |
| `texture_qa`      | 4 single-image checks          | **EXTEND** — add tile_4x4_lattice, mip_richness_decay, palette_lock |
| `blender_preview` | optional lit-sphere render     | **KEEP** as-is                                                    |
| `quality_gate`    | strict B+ at default           | **RELAX** to C for diversity-pool; new metrics fold in            |
| `catalog`         | shared with W3                 | **SPLIT** — candidates in W4 only; winners also write shared      |
| `mip_ladder`      | opt-in post-stage              | **DEFER** to post-promotion                                       |

## Concrete next experiment (the original "16-gen test")

With the audit findings, the experiment matrix is now sharper. Test
the 4 highest-leverage axes from the audit, not random hyperparameter
sweeps:

| Axis (from audit)                      | Value A (current default) | Value B (proposed W4 default) |
|----------------------------------------|---------------------------|-------------------------------|
| FLUX heal-pass denoise                 | 1.0 (silently)            | 0.35 (`honor_denoise=True`)   |
| Delight strength                       | 0.4                       | 0.0 (skip)                    |
| PBR backend                            | `sm` (StableMaterials)    | `derive_pbr_v2`               |
| Seam-repair always-runs                | always                    | conditional on FLUX-heal score |

2^4 = 16 combinations. Pick one representative prompt
(`alpine_ground/windpack`) — it's already A-grade so any *worsening*
of result tells us the axis matters. Output to
`candidates/_pipeline_review/audit/<combo>/`.

For each output: store the 4 maps + the QA report + render-at-distance
mip32 preview (so we can judge top-down view). Build a single
comparison sheet showing all 16 side-by-side.

**Spot-check protocol:** for each combo, write whether the result is
better/same/worse than the current canonical. Cross-tab against the
audit's predictions. Where audit and observation disagree, *audit was
wrong* — update this doc with what we learned.

## Stop signs (when to abort the experiment and re-plan)

- If `honor_denoise=True` heal pass produces *broken* output (visible
  edge mismatch, content drift), the silent-ignore-denoise bug was
  load-bearing. Revert that axis; investigate why before continuing.
- If `derive_pbr_v2` produces visibly worse 3D close-up renders than
  `sm` *across all 4 delight×repair combos*, terrain doesn't get to
  ignore PBR quality. Re-evaluate.
- If 4-of-4 combos at delight=0.0 look identical to delight=0.4, the
  prompt-level lighting really is doing the work and delight is dead
  code. Confirm; remove from pipeline.

## What's NOT in this audit (intentionally deferred)

- LoRA / DreamBooth fine-tuning of klein-9B on a curated terrain set.
  Big lever, big lift. Bring up only after defaults are locked in.
- 4K / 8K texture support (current ladder caps at 2k). Premature.
- New biome categories beyond {Rock, Snow, Sand, Ground, Foliage,
  Mixed}. Add as we add biomes.
- ComfyUI workflow rebuild (current text2img + img2img + offset is
  fine).

## Decision record

This audit was conducted 2026-05-12 during the W4 texture pipeline
review. Findings represent the current state of inherited W3 infra +
W4-specific consumer needs. **Revisit after the 16-gen experiment
ships and we have real data.**
