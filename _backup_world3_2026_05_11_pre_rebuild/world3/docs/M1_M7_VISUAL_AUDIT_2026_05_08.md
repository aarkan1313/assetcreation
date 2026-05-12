# M1-M7 Visual Audit

Date: 2026-05-08

## Verdict

M7 is **not complete as a visual milestone**.

The M7 runtime mask workflow is useful and measurable, but the visual evidence
does not meet the project quality bar. More importantly, M7 exposed earlier
milestones that were accepted as engineering proofs while their visual output
should have been labeled pipeline-only.

Do not start normal M8 roadmap work yet. First repair the visual truth state:
catalog labels, transition-pair promotion status, and the M4/M5/M7 visual target.

Follow-up vision severity review: `M1_M7_VISION_GAP_REVIEW_2026_05_08.md`.
That review sets the visual target at roughly 70 percent of the best stacked
photo/topo OpenTopo reference quality and classifies current M1-M7 terrain
captures as debug/runtime evidence, not near-miss art evidence.

## Classification Key

- `PASS`: acceptable for the current quality bar.
- `PIPELINE_ONLY`: useful workflow evidence, not production visual evidence.
- `REWORK`: blocks forward visual claims.
- `DEFER`: real issue, but not needed before the next correction pass.

## Audit Table

| Milestone | Visual Classification | Workflow Classification | Finding |
|-----------|----------------------|-------------------------|---------|
| M1 material catalog | REWORK | PASS | Catalog identity/provenance works, but at least one early validation label was too optimistic. `grass.close` has been corrected to `needs_review` after the M6 noise audit. |
| M2 transition strips | MIXED / PIPELINE_ONLY | PASS | Same-source `scrub_sparse -> dry_wash` is calm enough for workflow evidence. `desert_sand -> grassland_grass` and other organic-heavy pairs are not production-ready because the source textures dominate the transition. |
| M3 chunk-size sweep | PIPELINE_ONLY | PASS | The 256 m chunk decision is valid engineering evidence. The seam captures are not terrain-art quality evidence. |
| M4 unified splat shader | REWORK for visuals | PASS | Shader compatibility and splat plumbing work, but `splat_shader_review.png` is visibly blocky/posterized and should never be treated as a beauty pass. |
| M5 streamed walk scene | REWORK for visuals | PASS | Streaming works. Visuals show noisy/over-repeated close terrain and abrupt material reads. Contact sheet is useful diagnostics, not quality approval. |
| M6 runtime hardening | PIPELINE_ONLY / REWORK source materials | PASS | Cache/collision metrics are valid. The M6 source-material audit correctly flags the organic/grass issue, but downstream docs still need to treat those materials as blockers. |
| M7 automatic boundary masks | REWORK | PASS | Rule-driven masks, catalog pair selection, and metrics work. Visual result is not acceptable enough to close M7 as a visual milestone. |

## Root Causes

1. Some milestone exits used "nonblank capture + metrics" as enough evidence.
   That is valid for workflow, but insufficient for AAA visual quality.
2. Source materials, especially green/organic and grassland textures, were
   carried forward after being useful for pipeline validation.
3. M4 splat weights and material assignment are prototype/debug quality, so M5
   and M7 inherited noisy or blocky material context.
4. Transition strips were first judged in strip/grid review, not in convincing
   terrain context.
5. Docs correctly say "pipeline-validation material" in several places, but the
   roadmap still risked behaving as if the visuals were approved.

## Immediate Corrections

1. Treat M7 as `workflow pass / visual rework`.
2. Freeze forward roadmap progress until the visual audit corrections are
   complete.
3. Keep the M7 runtime mask code, but stop using the current M7 captures as
   quality evidence.
4. Update catalog validation so M6-flagged materials cannot masquerade as close
   view production candidates. Completed for the M6 flagged set: all ten now
   have `validated_views.close = needs_review`.
5. Define the next active work as a visual remediation pass, not "M8 starts":
   - repair source-material validation truth,
   - choose a small set of visually acceptable control materials,
   - regenerate or filter the organic/grass materials,
   - rerun M2/M4/M5/M7 captures against those repaired sources.

## Specific Findings

### M1

The catalog contract is sound: IDs, provenance, source class, PBR maps, and
shader binding are the right foundation. The failure is validation drift. The
base `grass` material was still labeled `close = ok` despite the later M6
green-organic speckle finding. That has been corrected in this audit.

M1 validation sync result: every material flagged by
`M6_SOURCE_MATERIAL_NOISE_AUDIT.md` now has `validated_views.close =
needs_review` in `world3/materials/catalog.json`. This includes
`grassland_dirt`, `grassland_grass`, `grass`, `temperate_forest_dirt`,
`grassland_rock_light`, `tundra_moss`, `tundra_lichen`,
`temperate_forest_rock_light`, `temperate_forest_snow`, and
`temperate_forest_grass`.

### M2

The transition builder is valuable, but pair quality varies sharply.

- `scrub_sparse -> dry_wash`: acceptable workflow control.
- `desert_sand -> grassland_grass`: not visually acceptable; grass texture is
  too synthetic/noisy and overwhelms the blend.
- `tundra_moss -> temperate_forest_grass`: suspect for the same organic-noise
  reason.

M2 should be documented as a transition-workflow pass, not a blanket transition
visual pass.

### M3

The chunk-size decision remains valid. The visuals are diagnostic only.

### M4

The unified shader compatibility proof is useful, especially the OpenTopo
reference-vs-unified capture. The splat terrain A/B is not a beauty pass:
large smeared regions, posterized boundaries, and debug-like material placement
make it pipeline-only.

### M5

Streaming is real and worth keeping. The visual stack is not ready. The walk
contact sheet shows terrain shape and chunk continuity, but close terrain
materials and material assignment do not meet the target.

### M6

Runtime cache and collision hardening are valid. The source-material noise audit
was the correct warning sign. It should have blocked treating organic-heavy
captures as visually good.

### M7

The automatic mask path is the right engineering direction:

- rules select material pairs,
- chunks build masks,
- shader samples masks through `UV2`,
- metrics capture mask cost.

But the visual exit fails. The same-source control is too subtle to prove a
hero-quality transition, and the biome stress case is visibly bad because it
inherits poor grassland source material and prototype material context.

## Next Active Work

Start a visual remediation pass before M8:

1. Pick one visually acceptable M2 control pair as the baseline.
2. Regenerate/filter the bad organic materials that poison M2/M5/M7.
3. Re-render M4/M5/M7 with repaired sources.
4. Only then decide whether M7 can close visually or whether it needs a second
   transition-placement pass.
