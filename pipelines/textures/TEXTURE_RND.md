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
