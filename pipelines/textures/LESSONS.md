# Texture Pipeline — Lessons

What we know now that wasn't obvious before. Things future-us will
rediscover the hard way unless they're written down.

This is for the *texture* side specifically (FLUX → PBR set → QA
gate → consumer). Renderer lessons live with world3.

---

## L1 — A "passing" QA grade is meaningless without seeing the texture

The original pipeline graded textures as A/B/C/D and counted "passed
the gate" as proof of quality. Audit found that the underlying metric
only measured the outermost 1-pixel column, and **most "passing"
textures had visible defects 8+ pixels in.** Lattice artifacts. Healed-
but-still-visible center seams from the offset trick. The metric never
looked at any of it.

Takeaway: **always look at the actual `qa/tile_2x2.png` preview.** The
grade is one signal among several. Trust your eyes more than the
number for visual problems.

This drove the rewrite to three orthogonal checks (edge_continuity,
junction_visibility, periodic_artifact). Each measures a different
failure mode. They agree with the eye much better than the old single
MSE did. But they're still not perfect — a texture that grades A
mathematically can still look boring at scale (see L7).

## L2 — Repair output must overwrite the original

The old pipeline's `seam_repair.py` wrote its output to `<material>/
repaired/`. **Nothing copied those files back over the originals.**
Consumers (Godot, anything reading `<id>_albedo.png`) used the
unrepaired textures. The "repair" stage was visual theater for two
years.

Takeaway: when a stage transforms an asset, the transform must be
*visible to consumers* without manual intervention. Sidecar folders
("repaired/", "fixed/", "v2/") are anti-patterns. Either write back
in-place with a backup, or change the canonical filename and update
the manifest.

We chose write-back-with-backup (`<id>_<map>.pre_repair.png`).

## L3 — Stages that read a manifest must run after the manifest is written

Same root cause as L2 in a different shape. `seam_repair.py` used to
read `materials.jsonl` to find map filenames. The orchestrator ran
seam_repair *before* writing the manifest. Result: seam_repair always
failed `SystemExit("no manifest")` on first run; orchestrator caught
the error as "skipped: true" and moved on. **In two years of running,
repair never actually ran on a first-pass texture.**

Takeaway: minimize cross-stage dependencies. If a stage needs to know
where files are, let it discover them by filename convention, not by
reading a downstream manifest. Catalog/manifest writes belong at the
end of a pipeline, not in the middle.

## L4 — StableMaterials trains at 512; don't lie about resolution

The orchestrator passed `--size 1024` to SM. SM generates at its
training resolution (512) regardless. The script then LANCZOS-upscales
to 1024 and saves the file at 1024×1024 dimensions. **The maps
"claimed" 1024 but had only 512×512 worth of detail in them.**

Takeaway: don't insert silent up- or down-scales between stages
"because the consumer expects size X." Make the actual data resolution
explicit in the manifest. For our use (terrain at world_triplanar
0.05–0.1), 512 is plenty. Pretending it was 1024 just hid the fact
that it wasn't.

## L5 — Sanity checks need per-category exceptions

The original sanity check flagged **any** roughness map with std < 0.02
as "suspicious flat map." Snow legitimately has uniform roughness —
fresh snow's micro-roughness is the same across the whole tile. Same
for water, sand, polished metal. These categories failed the gate not
because they were broken but because the check didn't know about them.

Takeaway: any "this looks weird" rule should have a per-category
override. Added `UNIFORM_ROUGHNESS_OK_CATEGORIES = {Snow, Water, Sand,
Liquid}`. Same logic likely applies to other "suspicious" checks: a
metallic-flagged-high might be appropriate for the Metal category.

## L6 — Periodic-locality threshold isn't universal

Calibrated against our library:
- Real-photo PolyHaven sets: 8–17 (clean smooth spectrum)
- AI noise-like (loam, dirt, grass): 6–25 (some natural micro-pattern)
- Cobblestones (intentionally periodic): 80–613 (periodic by design)
- Lattice artifact: 40+ (broken)

Threshold 18 catches lattices but rejects cobble even when the cobble
is a clean tileable. A single global threshold *can't* be right
because "periodicity" is a goal for some materials and a flaw for
others.

Solution: per-category threshold table. Brick/Cobble/Tile = 80, Wood =
50, Rock = 25, Snow/Sand/Water = 18, Ground/Concrete = 22, Metal = 30.
Calibrated by hand against our library. Won't survive a much wider
material taxonomy without re-tuning.

## L7 — Tileable doesn't mean visually interesting at scale

A texture can be perfect grade-A (all three checks pass) and still
look like flat-shaded blocks when 1k copies are tiled across a
terrain. The fundamental issue: pixel-scale detail averages to mid-
grey at distance. Hex-tile sampling fixes the *period*; macro
variation noise fixes the *uniformity*. **Both are renderer-side
tricks that operate on an existing texture.**

Implication for the pipeline: don't chase grade-A periodic at the
expense of macro detail in the texture itself. A grade-B texture with
real internal variation is more valuable than a grade-A texture that's
visually flat. Currently we don't measure "visual richness at
distance" but we should — even a simple "albedo standard deviation
across the whole image" or a Laplacian-energy summary would catch the
"flat blob" failure mode.

## L8 — FLUX 2 klein has directional bias on structured prompts

Words like "ridges", "cracks", "lines", "stripes" all bias FLUX
toward producing parallel/repeating geometry. When that texture is
tiled, the parallel lines align across copies and produce a visible
lattice (e.g. `wgv3_rock_dark`'s diamond grid).

Takeaway: prompt away from words that imply a *direction*. Prefer
"weathered surface", "rough texture", "uneven small features" over
"deep cracks" or "horizontal striations". When directionality is
desired, expect to do extra work post-gen (heavier offset+heal,
multiple variants, hex-tile in the renderer).

A stretch goal: a "directionality" check (FFT power along the dominant
axis vs. the orthogonal) that flags textures with strong directional
bias before they reach the gate.

## L9 — One PBR set sampled at two scales beats one set sampled once

Iter 4 of the world3 shader stack samples each PBR set twice — at
macro UV (10m repeat) and detail UV (1.25m repeat) — and blends with
soft-light + RNM normal. The detail layer fades to nothing past 30m
camera distance.

The visual difference up close is dramatic. A "rock" texture sampled
once looks like a soft blob; sampled at two scales it has chunky
surface relief. **The same texture asset.** No new generation needed.

Implication: the texture pipeline doesn't need to produce both a
"macro" version and a "detail" version of every material. One good
authoritative tile, sampled twice in the shader, gives both. We may
later want a true "detail variant" PBR (smaller features, higher
contrast) for materials where multi-scale realism really matters
(stone walls, tree bark) — see step 3 of the texture preprocessing
review.

## L10 — Color cohesion is a biome-level concern, not a per-texture concern

The 5 wgv3 textures don't share a color palette: dirt is orange, grass
is bright green, rock_dark is grey, rock_light is tan, snow is white.
Looks reasonable in iter 5 (Tetons) because real Teton dirt *is*
orangey and real Teton grass *is* green. Won't look reasonable for an
"autumn forest" or "mars" or "tundra" biome.

Implication: a biome's textures need to be generated together, with
the pipeline aware of the palette constraint. `palette_lock.py` exists
but isn't wired into `aaa_texture.py`. Step 2 of the review wires it
up.

The right unit of generation is probably a "biome kit" (5 textures,
shared palette, shared environmental context in the prompt prefix),
not a single texture.

## L11 — `--no-gate` is a release-valve, not a habit

Whenever I find myself reaching for `--no-gate` more than once on the
same material, the gate is wrong, not the texture. snow flagging
sanity-ok=False was the canonical example: shipping with `--no-gate`
worked but obscured the real problem (the sanity check was over-broad
for naturally-uniform materials). Fixed L5 above.

Takeaway: track which materials needed `--no-gate` to ship. If the
list grows, that's a signal the gate needs adjusting, not that the
materials are bad.

---

## L12 — A "shared seed" doesn't actually share decisions when MSE varies per map

In multi-map seam repair, we want all maps (albedo, normal, roughness, ...)
to be patched from the *same* spatial source so they stay aligned. The
original code seeded the patch-search RNG identically per map and
believed that was enough. It wasn't: the RNG generates *candidate
locations*, but `find_best_patch` returns the one with the lowest MSE
against the target. Different maps have different pixel content, so they
minimize MSE on *different criteria*. Same candidates, different winners.

Result: albedo and normal get patched from spatially inconsistent source
regions. Looks fine on the albedo, looks misaligned on the normal map.

Fix (shipped): compute the patch plan once on the albedo, save the
chosen `(py, px)` per slot, replay those exact offsets on every other
map without re-searching.

Takeaway: shared randomness ≠ shared decisions when there's a content-
dependent selector downstream. If the rule is "do the same thing to all
of these," the operations have to be parameter-passed, not regenerated.

## L13 — Defensive shader gates can produce black holes at boundaries

`terrain_blend.gdshader` had `if (weight > 0.005) { sample(); }` for
each of 5 layers, intended as an optimization (skip near-zero
contributions). Combined with smoothstep-based weight computation, the
*post-normalization* weights always sum to 1, so this was theoretically
safe. But the gate threshold was carelessly large enough that a `==
0.005` weight (or similar edge case) could fall through, producing
`wsum=0` → divide → black pixel.

Fix: gate threshold dropped to `1e-4`, AND a guaranteed fallback (sample
rock_dark unconditionally) when wsum is below threshold. Costs at most
one extra sample per pathological pixel; defends against any future
weight-computation tweak.

Takeaway: when an optimization branch can leave the accumulator at
zero, the divide needs a meaningful fallback, not just an `if (sum < eps)
sum = 1.0` placeholder. The "1.0 default" produces a literal zero output.

## L14 — Reoriented Normal Mapping (RNM) requires tangent space

We blended detail normals over macro normals using
`reorient_normal(t, u) { t.z += 1.0; ... }`. Mathematically RNM
assumes both inputs are in tangent space where the surface normal is
+Z. We had world-space normals (post-triplanar), where +Z is the world
up direction, not the surface up direction.

For horizontal ground (world normal ≈ +Y) the RNM "happens to work"
because `t.z` is small and `t.z += 1.0` produces approximately correct
output. For cliffs and steep slopes (world normal far from +Y), RNM
distorts badly. The detail normal pulls toward world-Z instead of
surface-up, which on a vertical wall is sideways.

Fix (shipped): replaced with `normalize(mix(macro, detail, strength))`.
Less mathematically rich than RNM but consistent on all surface
orientations.

Better fix (deferred): derive a true surface tangent frame in the
shader from world-position partial derivatives (ddx/ddy of `wp`),
transform both normals into the tangent frame, apply RNM, transform
back. Adds ~10 lines of GPU work; produces visually crisper detail
(one of the iter4b captures showed RNM-misuse looking *more* detailed
because of the directional bias error — the safe mix is "correct but
less punchy").

Takeaway: the most-shared shader recipes (RNM, Schlick, etc.) come
with implicit assumptions about coordinate frames. Lifting them out of
their context produces visually plausible but physically wrong results.

## L15 — Catalog write order matters for downstream truth

Same root cause as L2/L3 (manifests/repair). The orchestrator's catalog
write happens at the *end* of `aaa_texture.py`. `palette_lock` then
runs *after* aaa_texture and modifies the albedo. Re-running QA after
the match writes a fresh `qa/summary.json`, but the catalog line is
already stale — it has the pre-match grade.

Any consumer reading `materials.jsonl` to filter "give me grade-A
textures for the alpine biome" gets the wrong answer. Worse, a texture
might genuinely *fail* the gate after the match (LAB shifts can move
edge_continuity above threshold) and the catalog still claims "passed."

Fix (shipped): `update_catalog_entry_from_qa()` in palette_lock reads
the post-match summary, finds the catalog line by id, and rewrites it.

Takeaway: any post-pipeline transformation must include a "tell the
truth about what you did" step. Bonus: a sanity test that the catalog
matches the latest qa/summary for every entry would catch this kind
of drift automatically.

## L16 — A grade-A texture can be visually featureless ("smooth A")

Observed in the A.2 sweep: sand at seed 200 graded A on all three
checks (edge 0.0004, junction 1.00, periodic 10.0) but is visually
nearly featureless — a flat orangey wash. It earned the A by being so
smooth that the metrics had nothing to fail on.

The three QA checks measure *defects*. They don't measure *content*:
- edge_continuity: do opposite edges match? (Featureless = trivially yes.)
- junction_visibility: does the seam region have more energy than the
  interior? (No energy anywhere = no relative excess = pass.)
- periodic_artifact: is there a sharp delta in the FFT spectrum?
  (Featureless = nearly flat spectrum = no sharp peaks = pass.)

A material with no detail passes all three. The metric is honest about
what it measures (no defects) and silent on what it doesn't (no
material identity, no visual richness, no "this looks like X").

**Implication for the pipeline**: grade A is a *necessary* condition
for shipping, not a *sufficient* one. The eye has to confirm the
material reads correctly. The biome_consistency.py check (introduced
2026-05-07) is a partial defense — it compares color distribution
against the kit's anchor — but it's also tunable and a featureless
"correct color" texture would still pass.

**Possible future check**: a "richness" metric — Laplacian energy or
local variance of the albedo, with a *minimum* threshold. Below some
energy threshold = "too smooth, probably featureless." Easy to
calibrate, easy to add. Logged as a candidate for Phase A.6 or B.

**Workaround for now**: visual review of the contact sheet in
EXPERIMENTS sweeps. The eye catches "this is too smooth" instantly.

## L17 — Our offset+heal seam algorithm matches the open-source canon

Confirmed during the 2026-05-07 external-techniques survey
([EXTERNAL_TECHNIQUES.md](EXTERNAL_TECHNIQUES.md)): the offset-image-
then-inpaint-the-cross algorithm we use in `flux_seamless.py` is the
same algorithm independently implemented in `sagieppel/transform-
image-into-seamless-tileable-texture-using-stable-diffusion-inpainting`,
`brick2face/seamless-tile-inpainting`, and `was-node-suite-comfyui`'s
"Inpaint seamless tiling preparation" node. It's not one of several
options — it's *the* canonical FLUX/DiT-compatible technique because
circular padding (the SDXL alternative) doesn't work on transformer
backbones.

**Implication**: when the pipeline produces a bad tile, the failure
is upstream (prompt, base model, seed luck) or in our parameterization
(heal_strength, mask shape) — *not* in the algorithm. Don't entertain
"replace the seam algorithm" as a hypothesis without strong evidence.
The algorithm is fine.

## L18 — FLUX 2 klein silently ignores cfg-based negative prompts

Discovered during the same survey: klein is a distilled model trained
to operate at `cfg=1.0`, and our `flux_seamless.py` workflow hardcodes
this. Negative prompts only affect generation when `cfg > 1` — the
classifier-free guidance path is what actually applies them. So at
cfg=1, klein silently ignores any negative prompt. Our cookbook
practice of phrasing exclusions positively *inside* the prompt
(`no debris, no objects`) is **not a workaround for missing negative-
prompt support** — it's the only thing that does anything. FLUX still
treats "no" as a token, but the effect is weaker and less predictable
than a real negative prompt would be.

**Implication 1**: don't waste time investigating "should we add a
negative prompt to the pipeline?" — it would be a no-op until we
raise cfg, and raising cfg degrades klein quality.

**Implication 2**: if we ever swap to FLUX.1 D or a non-distilled
model, we *should* revisit the prompt structure to use real negative
prompts. The cookbook's "no debris" patterns would migrate from the
positive prompt to a negative one.

## What we don't know yet (open questions)

- **Does palette_lock actually produce more cohesive biome sets?** Step
  2 is bringing it online. Need to compare a 5-texture biome generated
  with vs. without locking.
- **Is generating a separate "detail" PBR set worthwhile?** Right now
  we sample the same albedo at two scales. A purpose-built detail set
  would have features authored for fine viewing. Step 3 will tell us.
- **How should the gate behave when we're generating biome-mate
  textures?** A texture being "off-palette" should be a gate failure
  too. Currently no check for this.
- **Does the periodic threshold scale with image size?** Our textures
  are 512. If we generated at 1024, would the periodic numbers be
  comparable? Probably yes (FFT is dimensionally normalized) but worth
  a sanity check.
- **What's the actual GPU cost of the multi-set blend shader at
  4K?** Not measured. May matter when we go to multi-tile streaming.
