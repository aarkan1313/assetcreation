# Next-Session Prompt

Copy/paste this as the opening message in a fresh session. It contains the
minimum context to pick up where this session left off.

---

## Session opener

You are picking up `world3` in `D:/assets/world3` as the single-stream
orchestrator. The user asked this chat to keep worker/orchestrator work
consolidated for now.

The project framing matters: `world3` and `assets` are a pipeline/workflow
creation set. Current content is primarily workflow-validation material for
AAA-quality pipelines; production promotion is a separate review.

Repo-level data inventory is now centralized in `docs/MASTER_DATA_CATALOG.md`
and `world3/data_catalog.json`. Re-run
`python pipelines/terrain/build_master_catalog.py` whenever new DEMs, stacks,
or texture sets land.

Read first:

1. `world3/docs/WORLD3_STATE_2026_05_08.md`
2. `world3/docs/PLAN.md`
3. `world3/docs/WORKFLOW_SNAPSHOT_2026_05_08.md`
4. `world3/docs/M2_TRANSITION_MATERIAL_PROTOTYPE.md`
5. `world3/docs/PHASE_F_CHUNK_SIZE_SWEEP.md`
6. `world3/docs/M4_SPLAT_SHADER_PROTOTYPE.md`
7. `world3/docs/M4_CHUNK_MATERIAL_CONTRACT.md`
8. `world3/docs/M6_RUNTIME_HARDENING.md`
9. `world3/docs/M7_M12_NEAR_ROADMAP.md`
10. `world3/docs/M7_BOUNDARY_RUNTIME_INTEGRATION.md`
11. `world3/docs/M1_M7_VISUAL_AUDIT_PLAN_2026_05_08.md`
12. `world3/docs/M1_M7_VISUAL_AUDIT_2026_05_08.md`
13. `world3/docs/M1_M7_VISION_GAP_REVIEW_2026_05_08.md`
14. `world3/docs/M1_M7_VISUAL_REMEDIATION_PLAN_2026_05_08.md`
15. `world3/docs/SOURCE_STACK_RUNTIME_REMEDIATION_2026_05_08.md`
16. `world3/docs/SOURCE_STACK_VALID_AREA_POLICY_2026_05_08.md`
17. `world3/docs/M1_M7_ORGANIC_TEXTURE_REPAIR_2026_05_08.md`
18. `world3/docs/COMFYUI_TEXTURE_WORKFLOW_INVENTORY_2026_05_08.md`
19. `world3/docs/M8_COMFYUI_TEXTURE_REGEN_PASS_2026_05_08.md`
20. `world3/docs/M8_COMFYUI_TERRAIN_CONTEXT_REVIEW_2026_05_08.md`
21. `world3/docs/M8_COMFYUI_CANDIDATE_NOISE_AUDIT.md`
22. `world3/docs/M8_GRASS_REGEN_ATTEMPTS_REVIEW_2026_05_08.md`
23. `world3/docs/M8_GRASS_VISUAL_VETO_AUDIT.md`
24. `world3/docs/M1_M7_WORKFLOW_VALIDATION_RUN_2026_05_08.md`
25. `world3/docs/M1_M7_REFINEMENT_MAP_2026_05_08.md`
26. `world3/docs/M4_SOURCE_STACK_CONTEXT_REVIEW_2026_05_08.md`
27. `world3/docs/M3_SOURCE_STACK_SEAM_REVIEW_2026_05_08.md`
28. `world3/docs/M5_SOURCE_STACK_WALK_REVIEW_2026_05_08.md`
29. `world3/docs/M6_SOURCE_STACK_RUNTIME_REVIEW_2026_05_08.md`
30. `world3/docs/M7_SOURCE_STACK_BOUNDARY_REVIEW_2026_05_08.md`
31. `world3/docs/M7_TRANSITION_MASK_METRICS_2026_05_08.md`
32. `world3/docs/M8_ORGANIC_REGEN_QUEUE_STATUS_2026_05_08.md`
33. `world3/docs/REVIEW_SCENE_AUTO_TOUR_2026_05_08.md`
34. `world3/docs/SOURCE_REPEAT_POLICY_2026_05_09.md`
35. `world3/docs/TERRAIN_SEAM_INTEGRATION_RESEARCH_2026_05_09.md`
36. `world3/docs/M10_TERRAIN_SEAM_INTEGRATION_PROOF_2026_05_09.md`

## Current status

Recent scoped commits:

- `6e31107` - `world3: add material catalog`
- `23933a3` - `world3: add chunk size sweep`
- `3a7317d` - `world3: start transition strip prototype`
- `116766f` - `world3: record transition visual review`
- `680b22c` - `world3: refresh workflow docs`
- `ae31568` - `world3: add transition review scoring`
- `a2cc5fc` - `world3: add transition boundary contract`
- `dfb2bdd` - `world3: checkpoint opentopo worktree`
- `edc9902` - `world3: tune transition boundary assets`
- `62c5736` - `world3: add splat shader prototype`
- `2bf0942` - `world3: add chunk splat material contract`
- `4db433a` - `world3: wire walk scene to splat streaming`
- `b74d109` - `world3: record m5 streaming budget`
- `1cc9fda` - `world3: close m1 m5 final audit`
- `0cc4349` - `world3: record final audit hash`
- `18d6bac` - `world3: harden streamed runtime`
- `0eddcc0` - `world3: add m7 boundary runtime masks`
- `c575823` - `world3: add visual remediation source stack`
- `2f342d0` - `world3: add comfy texture workflow inventory`
- `de95de3` - `world3: log first comfy m8 regen`
- `9d10702` - `world3: add comfy terrain context review`
- `a23c286` - `world3: log grass regen visual veto`
- `c57fdfa` - `world3: add comfy visual veto audit`
- `35f0ac8` - `world3: split m1 m7 visual validation`
- `daca50a` - `world3: add source stack m3 m5 visual refinements`
- `ff5411e` - `world3: add source stack m6 m7 refinements`

Active lane: M7 is a workflow pass but visual closure is paused. Continue the
M1-M7 remediation/M8 organic cleanup path. OpenTopo source stacks and
ComfyUI/`aaa_texture.py` generated textures are peer lanes: OpenTopo is the
current visual reference/control path; ComfyUI is the scalable material
regeneration path. Start with `world3/jobs/comfy_texture_regen_candidates.json`
and keep regenerated outputs quarantined until seam QA, Godot close/mid/far
terrain-context captures, and M4/M7 rerender trials pass.

OpenTopo/DEM data is not to be framed as "make one crop infinite." Use the
master catalog to pick source exemplars, mosaics, and coverage gaps. Long-term
procedural expansion should learn landform/material/vegetation/drainage rules
from many sources, then generate or stream compatible neighboring terrain.
Repeated-source 2x2/3x3 review is diagnostic only. It is allowed for
sample-space, shader, and chunk-boundary bugs, but not as visual closure.
Production-facing continuity now means terrain seam integration: a solved
world-space band for height, normals, material/source weights, macro color,
valid masks, and feature layers.

First M10 seam proofs exist: `build_terrain_seam_integration_proof.py` builds
overlap and nearby non-overlap Gloss Mountain seam artifacts.
`source_stack_seam_integration_tour.tscn` reviews the overlap proof;
`source_stack_seam_nonoverlap_tour.tscn` reviews the nearby non-overlap proof.
These validate the runtime/integration-band path, not full M10 closure.

M10 review launch/capture note: use explicit `--scene` wrapper launches, not the
older waited `--script _codex_render_runner.gd` path. The current seam review
scenes use a matte validation preset with dark neutral background, zero
specular, high roughness, lower exposure, and glow disabled.

First ComfyUI M8 result: `m8_grassland_grass_calm_v3` passed strict
`aaa_texture.py` QA, source-material noise audit, and the first terrain-context
candidate review. It is calmer than current `grassland_grass` under detail
stress, but still slightly pale/hazy, so it is sidecar-only and not promoted
yet.

Source-stack valid-area policy is now implemented for review materials:
`build_source_stack_runtime_review.py` writes `source_macro_valid_mask.png`,
edge-bleeds invalid macro pixels, and emits materials using
`source_macro_valid_mask`. The unified shader gates source macro contribution by
that mask. Current/Comfy grassland close/mid/topdown and detail-stress captures
were rerendered. Evidence:
`world3/docs/SOURCE_STACK_VALID_AREA_POLICY_2026_05_08.md`.

R6 has started with a source-stack M7 control rerender:
`world3/scenes/capture_phase_m7/boundary_runtime_source_stack_control.tscn` and
`world3/docs/captures/m7/boundary_runtime_source_stack_control.png`. This is
better than the old alpine debug context, but still diagnostic because it is a
one-chunk finite-footprint view with strong source-photo shadow content.

Fresh M1-M7 validation suite:
`world3/docs/captures/m1_m7_validation_2026_05_08/` and
`world3/docs/M1_M7_WORKFLOW_VALIDATION_RUN_2026_05_08.md`. Result: M1-M3 pass
as workflow evidence; M4-M6 are pipeline-pass/visual-rework; M7 remains
workflow-pass/visual-rework. The main visual sheet was tightened after user
review: bad finite-chunk/debug M3-M6/M7 proof captures are engineering
diagnostics only, not visual validation. Use
`world3/docs/M1_M7_REFINEMENT_MAP_2026_05_08.md` to refine each milestone.

M4 refinement has started with `world3/docs/M4_SOURCE_STACK_CONTEXT_REVIEW_2026_05_08.md`.
New scenes:
`world3/scenes/capture_phase_m4/source_stack_context_current_close.tscn` and
`world3/scenes/capture_phase_m4/source_stack_context_comfy_v3_close.tscn`.
New captures:
`world3/docs/captures/m4/source_stack_context_review.png`,
`source_stack_context_current_close.png`, and
`source_stack_context_comfy_v3_close.png`. These are the current M4 visual
baseline candidates; wider/topdown/iso review is still open.

M3 now has a visual-facing seam capture through the repaired M4 context:
`world3/scenes/capture_phase_f/chunk_256m_source_stack_visual_seam.tscn` and
`world3/docs/captures/phase_f/chunk_sweep/chunk_256m_source_stack_visual_seam.png`.
The old M3 sweep remains the technical truth; this new capture is for visual
validation only.

M5 now has a source-stack inspection rerender:
`world3/scenes/capture_phase_m5/walk_source_stack.tscn`,
`world3/docs/captures/m5/walk_source_stack_after_crossing.png`, and
`world3/docs/captures/m5/walk_source_stack_metrics.json`. The first horizon
walk camera exposed finite-footprint artifacts and should not be used as visual
evidence; keep the accepted inspection camera until a wider/far-field policy is
implemented.

M6 now has a collision-enabled source-stack rerender:
`world3/docs/captures/m6/walk_source_stack_collision.png` and
`world3/docs/captures/m6/walk_source_stack_collision_metrics.json`. It uses the
same inspection scene with streamed collision chunks enabled. M7 now has a
cleaner same-source source-stack control:
`world3/scenes/capture_phase_m7/boundary_runtime_source_stack_context.tscn` and
`world3/docs/captures/m7/boundary_runtime_source_stack_context.png`. M7 is
improved but not visually closed. The same-source transition mask now passes
coverage/edge-continuity QA in `world3/docs/M7_TRANSITION_MASK_METRICS_2026_05_08.md`;
cross-material stress and view parity remain open.

Second ComfyUI M8 target: `grass` produced strict grade-A outputs, but visual
review rejected them. `m8_grass_calm_v1` is the best failed direction; v2/v3
overcorrected into pale boxy sod or bright patch islands, and the v4
reference-anchor test created individual plant objects. Do not sidecar-stage
`grass` until a flat tile passes a visual landmark/object veto. Use
`world3/pipeline/audit_comfy_visual_veto.py` as an advisory helper only;
`needs_visual_review` is not a pass.

M8 queue board:
`world3/docs/M8_ORGANIC_REGEN_QUEUE_STATUS_2026_05_08.md` summarizes the five
priority organic blockers. Current state: `grassland_grass` has one sidecar
candidate needing M4/M7 runtime trials, `grass` is visually rejected after four
attempts, and `temperate_forest_grass`, `tundra_moss`, and `tundra_lichen` are
still untested queue items.

Representative review scene:
`world3/scenes/review/source_stack_auto_tour.tscn` runs an automatic tour through
close 3D, medium 3D, iso, topdown, controlled overview, and near-field sweep
views over the current source-stack/M8 sidecar workflow. Use it for quick mobile
remote-desktop validation before continuing the roadmap. True far/horizon views
are deliberately excluded from the default tour because they expose finite
footprint limits. Source-height repeat artifacts now have a runtime policy:
`ChunkLoader.gd` defaults to mirrored finite-source sampling, with legacy wrap
retained only for proven toroidal/seam-safe inputs.

Full-map moving review scene:
`world3/scenes/review/source_stack_full_map_fast_tour.tscn` traverses the valid
Gloss Mountain source footprint faster and wider. It uses `clip_to_source_bounds`
plus `source_macro_valid_mask` clipping, so missing source imagery is shown as
dataset boundary/empty background instead of fake beige terrain.

M1 is done:

- `world3/materials/CATALOG.md`
- `world3/materials/catalog.json`
- `world3/jobs/biome_kits.json` references catalog IDs.
- Kit material generation and representative renders were verified.

M3 is done:

- `world3/scripts/ChunkLoader.gd`
- `world3/scripts/ChunkSweepRunner.gd`
- `world3/scenes/capture_phase_f/chunk_size_sweep.tscn`
- 256 m is locked as the synchronous base chunk size at 8 m mesh spacing.

M2 is done for workflow/M4 input:

- `pipelines/textures/build_transition_strip.py` builds deterministic
  transition strips from catalog IDs and writes score hints into each manifest.
- Boundary rules live in `world3/jobs/biome_transition_rules.json`.
- Contract note: `world3/docs/M2_BOUNDARY_TRANSITION_CONTRACT.md`.
- Rule-level tuning has been applied for width, mask noise, albedo matching,
  frequency dampening, roughness matching, and normal-energy dampening.
- Four pairs were generated under `world3/textures/transitions/`.
- Comparison sheets live under `world3/docs/captures/transitions/`.
- Clean Godot scene:
  `world3/scenes/capture_phase_m2/transition_strip_review.tscn`
- In-engine capture:
  `world3/docs/captures/transitions/godot_transition_strip_review.png`
- User visual review: transitions are promising/good.
- Caveat: grass/leaves are too noisy for production. Track that as source
  texture quality/prompt QA, not transition workflow failure.

M4 prototype pass 2 is done:

- `world3/shaders/terrain_splat_unified.gdshader`
- `world3/pipeline/build_m4_splat_prototype.py`
- Generated alpine RGBA splat weights:
  `world3/textures/m4_splat/alpine_height_slope_weights_rgba.png`
- Generated materials:
  - `world3/textures/wgv3/terrain_splat_alpine.tres`
  - `world3/textures/wgv3/terrain_splat_alpine_fallback.tres`
  - `world3/textures/wgv3/terrain_splat_scrub_sparse_single.tres`
  - `world3/textures/wgv3/terrain_hex_detail_scrub_sparse_reference.tres`
- Captures:
  - `world3/docs/captures/m4/splat_shader_review.png`
  - `world3/docs/captures/m4/opentopo_unified_review.png`
  - `world3/docs/captures/m4/chunk_splat_stream_review.png`
- OpenTopo reference-vs-unified sampled panel delta is about 5.3 / 255.
- Chunk contract:
  - `world3/jobs/m4_chunk_material_contract.json`
  - `world3/docs/M4_CHUNK_MATERIAL_CONTRACT.md`
  - `ChunkLoader.gd` has `splat_weights_path` for dynamic runtime binding.
- Known prototype caveat: fresh splat PNGs bind dynamically because a new
  unimported PNG is not loadable from `.tres` as a `Texture2D` in runtime
  Godot.

M5 is complete at prototype final form:

- `world3/scenes/walk.tscn` now uses visible 256 m `ChunkLoader.gd` chunks with:
  - `terrain_material = res://textures/wgv3/terrain_splat_alpine.tres`
  - `splat_weights_path = res://textures/m4_splat/alpine_height_slope_weights_rgba.png`
  - `chunk_size_m = 256`
  - `chunk_resolution_m = 8`
  - `view_radius_chunks = 1`
- The legacy single `Terrain.gd` is hidden; M6 defers its build and uses
  streamed chunk collision instead.
- The player spawn was lowered so smoke captures and interactive use start
  near the terrain instead of high in the sky.
- `ChunkLoader.gd` writes UVs with the same source fraction used for height
  sampling. The default is mirrored finite-source sampling, which prevents
  OpenTopo crop-edge height walls; legacy `_wrapped_fraction(...)` behavior is
  still available via `source_repeat_mode = "wrap"`.
- Static capture:
  `world3/docs/captures/m5/walk_chunk_splat_smoke.png`
- Scripted crossing runner:
  `world3/scripts/M5WalkStreamRunner.gd`
- Scripted crossing capture and metrics:
  - `world3/docs/captures/m5/walk_stream_after_crossing.png`
  - `world3/docs/captures/m5/walk_stream_smoke_metrics.json`
- Crossing result: 900 m along +Z, chunk path `[0,5] -> [0,9]`, 9 peak loaded
  chunks, 12 builds, 12 removals, 18.816 ms worst synchronous update.
- Long sampled walk review:
  - `world3/docs/captures/m5/walk_long_contact_sheet.png`
  - `world3/docs/captures/m5/walk_long_metrics.json`
- Long result: 1536 m along +Z, chunk path `[0,5] -> [0,11]`, 9 peak loaded
  chunks, 18 builds, 18 removals, 18.317 ms worst synchronous update.
- Evidence doc:
  `world3/docs/M5_WALK_SPLAT_STREAMING.md`
- Budget note:
  `world3/docs/M5_STREAMING_BUDGET.md`
- Final audit:
  `world3/docs/M1_M5_FINAL_AUDIT_2026_05_08.md`

M6 is complete for the primary walk/runtime hardening pass:

- Runtime image cache builder:
  `world3/pipeline/build_runtime_image_cache.py`
- Runtime loader:
  `world3/scripts/RuntimeImageCache.gd`
- Generated runtime caches:
  - `world3/runtime_cache/heightmap_rf32.json`
  - `world3/runtime_cache/heightmap_rf32.bin`
  - `world3/runtime_cache/alpine_splat_rgba8.json`
  - `world3/runtime_cache/alpine_splat_rgba8.bin`
- `walk.tscn` now uses export-safe height/splat cache paths and streamed
  collision chunks.
- `M5WalkStreamRunner.gd` records collision metrics and can rebuild after reset
  for clean measurement.
- `terrain_splat_unified.gdshader` has an opt-in transition-strip sampler.
- Runtime transition review scene:
  `world3/scenes/capture_phase_m6/transition_runtime_review.tscn`
- M6 captures:
  - `world3/docs/captures/m6/walk_stream_collision_cache.png`
  - `world3/docs/captures/m6/walk_stream_collision_cache_metrics.json`
  - `world3/docs/captures/m6/transition_runtime_review.png`
- M6 walk result: 900 m, 9 peak loaded chunks, 21 collision chunks built,
  60.433 ms total collision build time, 5.033 ms max collision build time,
  28.675 ms worst update, 4.594 ms p95 frame time.
- Source-material audit:
  `world3/docs/M6_SOURCE_MATERIAL_NOISE_AUDIT.md`
- Source QA result: 10 of 17 green/organic materials flagged. Treat grass/
  leaves noise as source-material production-promotion work, not transition
  workflow failure.

M7-M12 near roadmap is now explicit:

1. M7 boundary-runtime integration.
2. M8 organic source-material cleanup.
3. M9 runtime performance and interaction polish.
4. M10 terrain seam integration and cross-source blending. First overlap proof
   and nearby non-overlap proof exist; next is different-source.
5. M11 corner and junction transitions.
6. M12 walk/iso/topdown view-mode parity.

Deferred systems remain after this lane: scatter, vegetation, props, buildings,
POIs, fantasy biome expansion, full procedural infinite-world extension, and
production asset promotion.

M7 pass 1 is complete for workflow/runtime validation, but not visual
milestone closure:

- `ChunkLoader.gd` generates per-chunk transition masks from
  `world3/jobs/biome_transition_rules.json`.
- Boundary rules select catalog `from_material` / `to_material` IDs and
  transition manifests instead of scene-hardcoded shader placement.
- `terrain_splat_unified.gdshader` samples generated masks with
  `use_transition_mask`.
- Captures:
  - `world3/docs/captures/m7/boundary_runtime_review.png`
  - `world3/docs/captures/m7/boundary_runtime_biome_stress.png`
  - `world3/docs/captures/m7/boundary_walk_after_crossing.png`
  - `world3/docs/captures/m7/boundary_walk_metrics.json`
- Metrics: 9 peak loaded chunks, 12 chunks built, 6 transition masks built,
  83.454 ms total transition-mask build time, 14.142 ms max transition-mask
  build time, 26.599 ms worst update, 4.873 ms p95 frame time over 384 m.
- Visual audit result: `world3/docs/M1_M7_VISUAL_AUDIT_2026_05_08.md`
  classifies M7 as workflow pass / visual rework. The same-source control is
  calm but subtle; the biome stress case exposes known grassland/organic noise
  and prototype material-context issues.
- Vision gap review result:
  `world3/docs/M1_M7_VISION_GAP_REVIEW_2026_05_08.md` sets the target at about
  70 percent of the best stacked photo/topo OpenTopo reference quality. Current
  M1-M7 runtime captures are debug/plumbing evidence and are well below that
  target.

## Next best move

Continue visual remediation and M8 cleanup before treating M7 as visually
closed:

1. Use `world3/docs/M1_M7_VISUAL_AUDIT_2026_05_08.md` as the truth state.
2. Use `world3/docs/M1_M7_VISUAL_REMEDIATION_PLAN_2026_05_08.md` as the
   repair sequence. R1/R2 are done; R3 is started; R4 is active.
3. Use `scrub_sparse -> dry_wash` as the first M2/M7 control pair.
4. Use `SOURCE_STACK_RUNTIME_REMEDIATION_2026_05_08.md` as the current source
   stack bridge: source-derived macro color first, valid-mask gated, tileable
   detail second.
5. Keep deterministic organic repair candidates quarantined. They improved
   metrics, but runtime review showed they must stay albedo-only/low-strength
   until proven.
6. Use `m8_grassland_grass_calm_v3` only as a sidecar ComfyUI candidate in
   M4/M7 rerender trials. It passed the first candidate gate, not canonical
   promotion.
7. Continue `grass` from the darker v1 direction, but require visual veto before
   PBR/sidecar staging.
8. Repair M4 splat context, then rerender M5/M7 and decide whether M7 can close
   visually or needs a second visual-targeted boundary pass.
9. Keep streamed collision metrics active. If interactive play shows hitching,
   start async/background mesh+collision build.

## Operating reminders

- Godot binary: `C:/Godot/Godot_v4.5-stable_win64.exe`.
- Captures generally need visible/windowed Godot; headless capture can hang.
- After deploying or regenerating `.tres`/PNG assets, run Godot import:
  `Godot --path world3 --quiet --headless --editor --import`
- Use surgical `git add <path>`. The worktree has preexisting OpenTopo worker
  dirt; do not stage unrelated `OPENTOPO_*`, toporeview, or pipeline files.
- Be careful with old review utilities that still use direct image loading.
  The primary `walk.tscn` runtime path is cache-safe; migrate legacy capture
  scripts as touched.
