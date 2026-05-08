# world3 Workflow Snapshot - 2026-05-08

This is the compact record of the current world3 workflow after M1, M2, M3,
and M4 prototype pass 2.

## Framing

world3 and the broader `assets` repo are currently a **pipeline and workflow
creation set**. The assets are judged first as workflow-validation material for
AAA-quality pipelines, not as guaranteed production content.

That matters because it lets us separate:

- **Workflow success**: provenance, repeatability, QA captures, runtime inputs,
  and integration contracts are working.
- **Asset promotion**: a specific texture/material/transition is production
  candidate quality at the target camera ranges.

The current transition workflow is promising. The visible caveat from user
review is source texture noise in generated grass/leaves, which belongs to
material-generation QA rather than transition logic.

## Current Pipeline

1. **Material source**
   - Procedural/generated PBR materials from `pipelines/textures/`.
   - Real-source OpenTopo materials from the worker/OpenTopo path.
   - Future fantasy materials will use the same catalog contract.

2. **Catalog contract**
   - Human spec: `world3/materials/CATALOG.md`
   - Machine source of truth: `world3/materials/catalog.json`
   - Each entry carries canonical ID, source, provenance, scale, color family,
     PBR maps, shader binding, and validation state.

3. **Kit material generation**
   - `world3/jobs/biome_kits.json` references catalog material IDs.
   - `world3/pipeline/build_kit_materials.py` resolves catalog IDs into
     `terrain_blend_<kit>.tres`.
   - `pipelines/textures/emit_per_mode_materials.py` emits walk/iso/topdown
     mode variants.

4. **Transition prototype**
   - Tool: `pipelines/textures/build_transition_strip.py`
   - Inputs: two catalog IDs, or `world3/jobs/biome_transition_rules.json`.
   - Output: deterministic 6-8 repeat transition strips with PBR maps, mask,
     manifest, score hints, and hard-cut comparison capture.
   - Contract: transition strips are generated boundary assets referenced by
     biome/material rules, not base material catalog entries.
   - Tuning: rule-level knobs now adjust width, mask noise, albedo matching,
     local frequency dampening, roughness matching, and normal-energy dampening.
   - Review scene:
     `world3/scenes/capture_phase_m2/transition_strip_review.tscn`
   - Current pairs:
     - `desert_sand` -> `grassland_grass`
     - `scrub_sparse` -> `dry_wash`
     - `tundra_moss` -> `temperate_forest_grass`
     - `dry_wash` -> `desert_dry_brush`

5. **Chunk streaming evidence**
   - Loader: `world3/scripts/ChunkLoader.gd`
   - Sweep runner: `world3/scripts/ChunkSweepRunner.gd`
   - Scene: `world3/scenes/capture_phase_f/chunk_size_sweep.tscn`
   - Decision: 256 m synchronous base chunks at 8 m mesh spacing.
   - Evidence: `world3/docs/PHASE_F_CHUNK_SIZE_SWEEP.md`

6. **M4 splat shader prototype**
   - Shader: `world3/shaders/terrain_splat_unified.gdshader`
   - Builder: `world3/pipeline/build_m4_splat_prototype.py`
   - Chunk contract: `world3/jobs/m4_chunk_material_contract.json`
   - Output: fixed five-slot unified shader, alpine RGBA splat weights,
     height/slope fallback material, splat material, and OpenTopo single
     material compatibility.
   - Runtime hook: `ChunkLoader.gd` binds fresh weight maps via
     `splat_weights_path`.
   - Evidence: `world3/docs/M4_SPLAT_SHADER_PROTOTYPE.md` and
     `world3/docs/M4_CHUNK_MATERIAL_CONTRACT.md`

7. **Visual QA**
   - Region/gallery captures verify kit-level reads.
   - Transition comparison sheets verify hard cut vs transition strip.
   - `godot_transition_strip_review.png` verifies the transition index in a
     clean in-engine scene.
   - M4 captures verify terrain old-vs-splat and OpenTopo
     `terrain_hex_detail` vs unified shader compatibility.
   - M4 chunk capture verifies the 256 m `ChunkLoader` path can consume the
     unified splat material and runtime weight texture.
   - Godot review scenes are used for in-engine sanity, but some OpenTopo
     review harness files are still in preexisting worker dirt and should not
     be swept into unrelated commits.

## Current Quality Gates

- JSON and catalog references parse.
- Material PBR paths exist.
- Python tools compile.
- Godot import passes after `.tres`/PNG changes.
- Representative captures are nonblank and visually inspected.
- Transition manifests carry review metrics for hue/value, roughness, normal
  energy, visible frequency, and edge-delta improvement.
- M4 OpenTopo reference-vs-unified capture is visually close; sampled panel
  mean absolute RGB delta is about 5.3 / 255.
- M4 chunk-stream capture is nonblank through `ChunkLoader.splat_weights_path`;
  visible material-region blocking is accepted as prototype weight-map content.
- Architectural decisions are appended to docs before moving on.

## Open Work

- Reduce noisy grass/leaves at source texture generation/QA.
- M5: wire 256 m chunk streaming plus the fixed five-slot splat contract into
  `walk.tscn`.
- Later M4/M5 polish: formalize weight texture import/cache, material
  indirection, and boundary-strip sampling.

## Recent Commits

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
- `HEAD at handoff` - M4 chunk material contract
