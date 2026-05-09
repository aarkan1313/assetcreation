# M7-M12 Near Roadmap

Date: 2026-05-08

This is the planning guardrail after M6. It turns the next six work areas into
explicit milestones so we do not keep pushing code blindly.

The goal is still a **pipeline/workflow creation set** capable of AAA-quality
terrain workflows. Current content remains workflow-validation material unless
it separately passes production promotion.

## Current Position

M1-M6 are done:

- M1: material catalog
- M2: transition strip workflow
- M3: chunk-size decision
- M4: unified splat shader prototype
- M5: streamed walk scene
- M6: runtime hardening for cache, collision, transition hook, and source QA

The next lane is not "add more stuff." It is to make the existing terrain
workflow automatic, robust, and view-mode consistent.

## Sequencing Rules

- Each milestone has an exit test and evidence capture before the next one
  becomes active.
- Docs update with the milestone, not after several milestones.
- We prefer one shared contract that walk, iso, and topdown can use with
  different view settings.
- Deferred systems stay deferred until this lane is complete: scatter,
  vegetation, props, buildings, POIs, fantasy biome expansion, and full
  procedural infinite-world generation.

## M7 - Biome-Boundary Runtime Integration

**Goal**: make M2 transition strips automatic in streamed runtime chunks.

Current state: the shader can sample a transition strip, but placement uses
manual review knobs (`transition_center_u`, `transition_width_u`).

2026-05-08 update: M7 pass 1 is complete for workflow/runtime validation.
`ChunkLoader.gd` now builds per-chunk transition masks from transition rules,
selects the rule's catalog material pair, binds the transition manifest assets,
and records mask-build metrics. Evidence:
`M7_BOUNDARY_RUNTIME_INTEGRATION.md`.

2026-05-08 visual audit update: `M1_M7_VISUAL_AUDIT_2026_05_08.md`
classifies M7 as workflow pass / visual rework. The automatic mask path stays,
but M7 is not visually closed. Do not start normal M8 work until the audit's
remediation items are completed or explicitly quarantined.

Remediation plan: `M1_M7_VISUAL_REMEDIATION_PLAN_2026_05_08.md`.
`scrub_sparse -> dry_wash` is the current control pair; `desert_sand ->
grassland_grass` remains a stress test until grassland source materials are
repaired.

Vision target: `M1_M7_VISION_GAP_REVIEW_2026_05_08.md` sets visual closure at
about 70 percent of the best stacked photo/topo OpenTopo reference quality.
Current M1-M7 runtime captures are below that bar and should be treated as
debug/plumbing evidence.

Visual caveat: M7 should not be treated as final terrain-art quality. The
same-source control is calm but subtle; the desert-to-grassland stress case
exposes the known noisy grass/organic source-material issue. Run
`M1_M7_VISUAL_AUDIT_2026_05_08.md` before starting M8.

Deliverables:

- Per-chunk boundary mask generation from `world3/jobs/biome_transition_rules.json`.
- Runtime material-pair selection for the active transition.
- Shader input path that uses generated masks instead of manual strip-center
  uniforms.
- Walk-scene capture crossing an automatic biome/material boundary.
- Metrics added to the same budget table as M5/M6.

Exit:

- A streamed walk capture shows an automatically placed transition strip with
  no manual shader-position knobs.
- Boundary assets are selected from rules/catalog IDs, not hardcoded in a scene.
- Workflow exit is met.
- Visual exit is failed/pending remediation. M7's current captures are
  diagnostics, not final asset approval.

## M8 - Organic Source-Material Cleanup

**Goal**: reduce the close-range grass/leaves/moss/lichen noise identified in
M6.

Current state: blocked by the M1-M7 visual audit. The transition workflow reads
well enough as a contract, but several source organic materials are too noisy
for production close-up use and have polluted M2/M5/M7 visual evidence.

2026-05-08 remediation start: deterministic repair candidates now exist for
the first five organic blockers, with metrics and before/after sheets recorded
in `M1_M7_ORGANIC_TEXTURE_REPAIR_2026_05_08.md`. Runtime review showed these
candidates are not ready for canonical promotion; keep them quarantined and
albedo-only/low-strength until terrain-context captures pass. The stronger
near-term baseline is the source-stack runtime bridge documented in
`SOURCE_STACK_RUNTIME_REMEDIATION_2026_05_08.md`.

2026-05-08 ComfyUI parity update: the generated texture lane is now explicitly
tracked through `COMFYUI_TEXTURE_WORKFLOW_INVENTORY_2026_05_08.md` and
`world3/jobs/comfy_texture_regen_candidates.json`. M8 should regenerate the five
priority organic blockers through ComfyUI/`aaa_texture.py` prompt and variant
control before relying on deterministic repair.

First regeneration result: `m8_grassland_grass_calm_v3` passed strict
`aaa_texture.py` QA for the `grassland_grass` blocker and passed the first
terrain-context candidate gate. It is materially calmer than the current
texture under detail stress, but still slightly pale/hazy, so it remains
quarantined and is not canonically promoted. Evidence:
`M8_COMFYUI_TEXTURE_REGEN_PASS_2026_05_08.md` and
`M8_COMFYUI_TERRAIN_CONTEXT_REVIEW_2026_05_08.md`.

Deliverables:

- Regenerate or filter the highest-priority flagged materials from
  `M6_SOURCE_MATERIAL_NOISE_AUDIT`.
- Run the ComfyUI regeneration queue for the first five organic blockers and
  archive the resulting `aaa_texture.py` QA.
- Re-run the source-material noise audit and record before/after.
- Update catalog validation state for close/mid/far views.
- Capture close/mid review sheets for the repaired materials.

Exit:

- The priority organic materials no longer dominate close-range review with
  speckle or harsh micro-contrast.
- Regenerated ComfyUI candidates pass inventory, seam QA, and terrain-context
  close/mid/far review before M4/M7 rerender trials; canonical promotion
  requires those runtime rerenders to pass without washout.
- Remaining failures are explicitly labeled as pipeline-validation only.

## M9 - Runtime Performance And Interaction Polish

**Goal**: make streamed chunks feel stable in interactive use, not only in
scripted captures.

Current state: synchronous chunk and collision builds are measured and
acceptable for prototype evidence, but the worst update can spike around a
chunk rebuild.

Deliverables:

- Interactive review pass of `walk.tscn` with streamed collision enabled.
- If hitching is visible: async/background chunk mesh and collision build.
- Budget doc update for chunk radius, collision build, frame p95/p99, and worst
  update.
- Clear decision on whether 256 m chunks remain the near-field base after M7
  boundary masks.

Exit:

- Scripted and interactive walk review agree that chunk crossings are usable.
- Any remaining hitch risk has a measured threshold and next mitigation.

## M10 - Cross-Source Blending

**Goal**: make real-source OpenTopo materials and procedural kit materials
coexist through the same runtime contracts.

Current state: the catalog includes both sources, and the unified shader can
approximate OpenTopo detail behavior, but source-to-source style bridging is
not solved.

Deliverables:

- A mixed real/procedural test chunk or review grid.
- Transition rules for at least one real-to-procedural pair.
- Shader/material binding path that does not special-case real materials into
  a separate runtime.
- Capture and score comparison against hard adjacency.

Exit:

- One real-source material and one procedural biome material can meet in the
  same runtime path without a jarring source-style break.

## M11 - Corner And Junction Transitions

**Goal**: handle three-way or corner junctions after pairwise transitions work.

Current state: pairwise transitions are promising. Corner cases are known but
not yet built.

Deliverables:

- Define junction cases that can actually appear in chunks.
- Build a small review scene with at least one three-material junction.
- Decide whether junctions are authored as special assets, composed from
  pairwise strips, or generated as masks over the existing splat map.

Exit:

- One representative three-way boundary renders without a hard visual corner.
- The chosen junction strategy is documented before broader generation.

## M12 - View-Mode Parity

**Goal**: bring walk, iso, and topdown onto consistent material/chunk/QA
contracts while preserving mode-specific tuning.

Current state: walk is on the M6 streamed unified path. Iso/topdown/gallery
still mostly use older whole-kit materials and single-load scenes.

Deliverables:

- Shared material contract for walk/iso/topdown.
- Shared catalog/rule inputs across all view modes.
- Per-mode captures for the same location using the same source materials and
  boundary rules.
- Decide whether iso/topdown need streamed chunks now or only shared material
  generation.
- Update region gallery so it can show parity evidence, not only old kit
  variants.

Exit:

- Same terrain area can be reviewed in walk, iso, and topdown with matching
  source/material decisions and view-appropriate tuning.
- Any intentional differences are documented as view-mode knobs, not divergent
  pipelines.

## Deferred Until After M7-M12

These remain important, but starting them early would fragment the terrain
foundation:

- Vegetation scatter and ground decoration.
- Props, buildings, POIs, and collision-authoring beyond terrain.
- Fantasy biome expansion.
- Full procedural infinite-world extension.
- Production asset promotion pipeline.

The checkpoint for opening those systems is: chunk-to-chunk, biome-to-biome,
source-to-source, and walk/iso/topdown parity are all demonstrably working in
the same workflow.
