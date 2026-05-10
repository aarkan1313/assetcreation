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

R6 source-stack rerenders now cover M3-M7:

- M3: `M3_SOURCE_STACK_SEAM_REVIEW_2026_05_08.md`
- M4: `M4_SOURCE_STACK_CONTEXT_REVIEW_2026_05_08.md`
- M5: `M5_SOURCE_STACK_WALK_REVIEW_2026_05_08.md`
- M6: `M6_SOURCE_STACK_RUNTIME_REVIEW_2026_05_08.md`
- M7: `M7_SOURCE_STACK_BOUNDARY_REVIEW_2026_05_08.md`
- M7 mask QA: `M7_TRANSITION_MASK_METRICS_2026_05_08.md`

This gives the workflow a credible source-stack visual baseline and moves the
old finite-chunk/debug captures into engineering diagnostics. It still does not
make M7 production-visual closed.

Vision target: `M1_M7_VISION_GAP_REVIEW_2026_05_08.md` sets visual closure at
about 70 percent of the best stacked photo/topo OpenTopo reference quality.
Current M1-M7 runtime captures are below that bar and should be treated as
debug/plumbing evidence.

Visual caveat: M7 should not be treated as final terrain-art quality. The
source-stack same-source control is cleaner but subtle; the desert-to-grassland
stress case still exposes the known noisy grass/organic source-material issue.
The same-source transition mask now has a quantitative QA pass. M8 can continue
as source-material cleanup, but M7 visual closure still needs cross-material
stress with its own mask metrics and view parity.

Deliverables:

- Per-chunk boundary mask generation from `world3/jobs/biome_transition_rules.json`.
- Runtime material-pair selection for the active transition.
- Shader input path that uses generated masks instead of manual strip-center
  uniforms.
- Walk-scene capture crossing an automatic biome/material boundary.
- Metrics added to the same budget table as M5/M6.
- Same-source transition-mask QA for coverage and chunk-edge continuity.

Exit:

- A streamed walk capture shows an automatically placed transition strip with
  no manual shader-position knobs.
- Boundary assets are selected from rules/catalog IDs, not hardcoded in a scene.
- Workflow exit is met.
- Visual exit is partially remediated. Source-stack control evidence exists,
  same-source mask QA passes, but final visual closure remains open.

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

Source-stack valid-area update: the runtime source-stack bridge now uses
OpenTopo valid masks for source macro contribution and edge-bleeds invalid
macro pixels before save. Current/Comfy grassland source-stack captures were
rerendered under this contract. Evidence:
`SOURCE_STACK_VALID_AREA_POLICY_2026_05_08.md`.

Second regeneration target update: `grass` produced several strict grade-A
outputs, but visual review rejected them for landmark blotches, pale/boxy sod
forms, bright patch islands, or individual plant objects. This exposed a
workflow rule: organic ComfyUI candidates need a visual landmark/object veto
before sidecar staging, even after seam/PBR QA passes. Evidence:
`M8_GRASS_REGEN_ATTEMPTS_REVIEW_2026_05_08.md`. Advisory helper:
`world3/pipeline/audit_comfy_visual_veto.py`.

Queue status update: `M8_ORGANIC_REGEN_QUEUE_STATUS_2026_05_08.md` is the
current execution board. It records five blockers: one sidecar candidate needing
M4/M7 runtime trials (`grassland_grass`), one visual reject (`grass`), and three
untested queue items (`temperate_forest_grass`, `tundra_moss`,
`tundra_lichen`).

2026-05-09 generator-diversity update: the texture lane now has a first
multi-model bakeoff artifact in
`../../pipelines/textures/DIVERSITY_COMPARE_2026_05_09.md`, with harness
`../../pipelines/textures/diversity_compare.py`. M8 should use FLUX.2-klein as
the canonical reference lane, AuraFlow v0.3 as an active diversity lane, and SD
3.5 Large as an active experimental photoreal lane. Qwen-Image is parked for
ground textures, and Chroma1-HD is rejected for this phase. Future M8 candidates
should be generated in batches with model-specific prompts/settings, then
promoted only after visual veto and terrain-context review.

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

## M10 - Terrain Seam Integration And Cross-Source Blending

**Goal**: make real-source OpenTopo materials, neighboring real-source terrain,
and procedural kit materials meet through one terrain integration contract.

Current state: the catalog includes both sources, and the unified shader can
approximate OpenTopo detail behavior, but source-to-source style bridging is
not solved.

2026-05-09 methodology correction: same-source repeated tiling is diagnostic
only. It can expose sampling and chunk bugs, but it is not a production visual
closure path. The production proof is a terrain seam integration band that
solves height, normals, material weights, source macro color, valid masks, and
feature layers together. Reference:
`TERRAIN_SEAM_INTEGRATION_RESEARCH_2026_05_09.md`.

2026-05-09 proof update: first- and second-rung terrain seam integration are
implemented for Gloss Mountain. Rung 1 uses overlapping source crops. Rung 2
uses nearby non-overlap crops with compatibility gating. Both emit runtime
height/macro bundles, manifests, metrics, and auto-tour review scenes. Evidence:
`M10_TERRAIN_SEAM_INTEGRATION_PROOF_2026_05_09.md`.

2026-05-09 cross-source validation: Rung 3 now has a different-source scanner
and an accepted Gloss-Guadalupe real-to-real proof. The geometry solve handles a
large vertical datum mismatch without creating a height wall, and the RGB solve
now correctly feathers source color bias instead of tinting the whole right
source. Topdown, iso, and 3D tour review passed live user visual acceptance.

2026-05-09 scanner/second-pair update: the compatibility scanner now has
artifact/fill/rectilinear visual-veto scoring, ranked preview offsets, and
optional fill-mask inputs. A Chuculay-Guadalupe second real-to-real proof
candidate now exists with metrics and topdown/iso/3D captures. Its numeric seam
quality is strong, but it remains pending live visual acceptance.

2026-05-09 second-pair visual review: Chuculay-Guadalupe is rejected as accepted
M10 visual evidence. The seam math passed, but live review flagged the desert
source macro as low quality/low resolution. Diagnostic review showed the problem
is already present in the Chuculay source crop: blurred orthophoto detail,
bright track/road content, and black/red speckle artifacts. The scanner now also
has explicit low-detail, chroma-spike, dark-speckle, dark-fraction,
bright-fraction, and rectilinear thresholds.

2026-05-09 real-to-procedural update: first real-to-procedural M10 workflow
proof now exists. `build_procedural_neighbor_bundle.py` emits a procedural
canyon-rock source-shaped bundle, and the existing terrain seam integration tool
solves it against the Gloss Mountain real-source crop. The proof passes
topdown/iso/medium workflow review without a height wall, invalid plateau, or
source box. It is not close-play AAA final; the procedural side still needs
better near-field PBR/detail and scatter.

Deliverables:

- A seam/integration-band artifact with solved height, normal/material weights,
  macro albedo, valid mask, manifest, and QA metrics.
- A mixed real/procedural test chunk or review grid.
- A real-to-real or offset-source seam proof before unlike-biome promotion.
- Transition rules for at least one real-to-procedural pair.
- Shader/material binding path that does not special-case real materials into
  a separate runtime.
- Capture and score comparison against hard adjacency.

Exit:

- One real-source terrain bundle and one neighboring/procedural bundle meet in
  the same runtime path without a height wall, orthophoto box, ghost strip,
  invalid fallback plateau, or jarring source-style break.

Current exit state: overlap and nearby non-overlap same-source proofs pass as
workflow/geometry evidence, and two different-source Gloss-Guadalupe proofs have
passed live visual review. Scanner veto hardening is implemented.
Chuculay-Guadalupe is kept as negative evidence for source-quality gating, not
as accepted proof. A first real-to-procedural Gloss-to-canyon-rock proof now
exists as accepted workflow evidence. The first unlike-biome promotion attempt
is rejected because it reads as a blended strip instead of an ecotone. M10 now
needs the layer/mask/ecotone workflow in
`M10_UNLIKE_BIOME_METHOD_REVIEW_2026_05_09.md`, using
`GAMEPLAY_VIEW_QUALITY_PLAN_2026_05_09.md` as the cross-cutting camera-band
quality contract.

2026-05-09 ecotone update: the runtime layer proof in
`M10_ECOTONE_LAYER_PROOF_2026_05_09.md` is now accepted as M10 unlike-biome
workflow evidence. It is a real workflow change from texture-to-texture blending
because it emits splat weights, source macro masks, material weights,
feature/scatter masks, and continuous height, then uses macro guidance as broad
landcover color rather than as the only transition contract. It is not
production-final; better grassland source candidates and close gameplay detail
remain for later gates.

2026-05-10 scatter update: first mask-driven ecotone scatter is implemented in
`EcotoneScatterOverlay.gd` and enabled in
`source_stack_ecotone_layer_tour.tscn`. It places deterministic placeholder
shrubs, dry-grass clumps, and rocks from the existing masks, with topdown scatter
LOD-hidden to keep map review clean. This closes the first scatter-mask
population proof, but production vegetation/rock assets and distance bands
remain later gates.

2026-05-10 scatter refinement: the proof now uses composite low-poly review
shapes and simple per-class visibility ranges. This improves the visual review
read, but it is still not a production scatter system. The remaining scatter
gate is an authored asset-library pass with biome density presets and gameplay
camera LOD.

## M11 - Corner And Junction Transitions

**Goal**: handle three-way or corner junctions after pairwise transitions work.

Current state: first representative three-way Y junction proof is accepted as
workflow evidence. `build_m11_junction_layer_proof.py` emits source/grassland/
canyon domain fields, runtime splat weights, a macro-guided source stack, and
feature/scatter masks. `source_stack_m11_junction_tour.tscn` reviews topdown,
iso, medium, and close views. A first four-way/corner proof is also accepted via
`build_m11_fourway_corner_proof.py` and
`source_stack_m11_fourway_corner_tour.tscn`, using photoreal source, current
grassland sidecar, controlled fantasy lava/basalt, and canyon rock.

2026-05-10 visual note: the accepted M11 pass uses the Zion master-stack terrain
texture as the canyon macro reference so the canyon branch survives gameplay
distance. Scatter exists as a deterministic mask-driven sidecar but defaults off
in the M11 tour because the current scatter meshes are placeholders.

Deliverables:

- Define junction cases that can actually appear in chunks.
- Build a small review scene with at least one three-material junction.
- Decide whether junctions are authored as special assets, composed from
  pairwise strips, or generated as masks over the existing splat map.
- Record the junction-case matrix so future T/L/island variants do not block M12.

Exit:

- One representative three-way boundary renders without a hard visual corner.
- The chosen junction strategy is documented before broader generation.
- Four-way/corner cases have at least one accepted proof before M12 parity is
  called complete.

2026-05-10 closure note: M11 has met the roadmap bar for moving to M12. The
remaining T-junction, L-corner, and island variants are future case-library work,
not blockers for view-mode parity.

## M12 - View-Mode Parity

**Goal**: bring walk, iso, and topdown onto consistent material/chunk/QA
contracts while preserving mode-specific tuning.

Current state: walk is on the M6 streamed unified path. Iso/topdown/gallery
still mostly use older whole-kit materials and single-load scenes.

2026-05-09 planning update: gameplay visual closure must be judged by actual
camera/zoom bands, not only by debug tours. Use
`GAMEPLAY_VIEW_QUALITY_PLAN_2026_05_09.md` to separate close, medium, iso, and
topdown acceptance requirements before promoting assets or workflows.

2026-05-10 audit/template update:
`M12_VIEW_MODE_PARITY_AUDIT_2026_05_10.md` inventories source-stack tour scenes
and capture bands. `source_stack_m12_parity_fourway_tour.tscn` now wraps the
accepted four-way proof with named close, medium, iso, and topdown camera bands.
Six workflows have complete close/medium/iso/topdown capture sets after the
runtime proof, and five use runtime splat weights.

2026-05-10 runtime parity update: representative true walk + gallery parity now
exists in `source_stack_m12_runtime_fourway_tour.tscn`, documented in
`M12_RUNTIME_PARITY_PROOF_2026_05_10.md`. The scene instantiates
`CharacterBody3D` + `Walker.gd` + streamed `ChunkLoader` chunks with collision
and uses the accepted four-way source/material/height/splat contract for close,
medium, iso, and topdown bands. The old bulk `RegionGalleryCapture.gd` remains
a legacy region screenshot tool; if the runtime parity proof passes live review,
that retrofit can move to follow-up work instead of blocking M12 closure.

Deliverables:

- Shared material contract for walk/iso/topdown.
- Shared catalog/rule inputs across all view modes.
- Per-mode captures for the same location using the same source materials and
  boundary rules.
- Decide whether iso/topdown need streamed chunks now or only shared material
  generation.
- Update region gallery so it can show parity evidence, not only old kit
  variants.
- Use the M12 parity scene/template as the control while bringing one true walk
  scene and one gallery/region view onto the same source/material/height/splat
  contract.

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

2026-05-10 closure audit: `M7_M12_CLOSURE_AUDIT_2026_05_10.md` records the
foundation status. The lane is strong enough to open post-parity planning, but
M8 close-play material quality, M9 production performance closure, and live M12
review remain conditional before any production promotion. The next roadmap is
`M13_M18_POST_PARITY_ROADMAP_2026_05_10.md`, starting with the M13 promotion
gate.
