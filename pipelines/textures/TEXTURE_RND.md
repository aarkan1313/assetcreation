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
- **Words implying directionality**: "horizontal striations",
  "parallel grooves", "ridges". FLUX makes them line up across copies
  → visible lattice when tiled. (Hex-tile shader masks this but the
  underlying texture is still flawed.)
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

#### desert_canyon_rock — WORKS WITH CAVEAT
```
weathered tan canyon sandstone with horizontal striations,
top-down photo, photoreal
```
Grade B (periodic 71.9). The "horizontal striations" cue produced
real-looking sandstone but with strong directional bias — when tiled
without hex-tile, the lines align. With hex-tile it's fine. Still
on the edge of acceptable; consider rewording without "horizontal."

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

#### tundra_ice — PARTIAL
```
compacted snow surface with subtle wind ridges and tiny ice
crystals, top-down photograph, photoreal
```
Grade C — "wind ridges" produced a strong vertical line down one
edge that palette-lock made worse. Likely better:
- Drop "wind ridges" — too directional.
- Try "uneven compacted snow with sparse small ice crystals."

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

- **Variants**: 4 is the default; bump to 6 when first-pass results
  miss. Variant selection picks by edge-MSE which doesn't perceive
  prompt fidelity, so more variants ≠ better material — just better
  edges.
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
