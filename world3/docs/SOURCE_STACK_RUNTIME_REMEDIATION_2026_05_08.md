# Source-Stack Runtime Remediation

Date: 2026-05-08

## Purpose

This pass starts the M1-M7 visual remediation by moving runtime terrain review
toward a source-stack model. OpenTopo is the first control because its
photo/topo stacks are the current visual reference, but the runtime policy is
not OpenTopo-only:

- source-derived macro albedo anchors the terrain;
- generated/tileable materials from ComfyUI/`aaa_texture.py` are low-strength
  close detail only until promoted;
- procedural organic materials stay quarantined until terrain-context captures
  prove they do not damage the source read.

The target remains roughly 70 percent of the best stacked photo/topo OpenTopo
reference quality, not "nonblank runtime screenshot."

## Shipped Workflow Pieces

- Shader bridge: `shaders/terrain_splat_unified.gdshader` now has opt-in
  `source_macro_albedo` support.
- Builder: `pipeline/build_source_stack_runtime_review.py`.
- Capture helper: `scripts/CaptureSceneOnce.gd`.
- Runtime review scene: `scenes/capture_visual_remediation/source_stack_runtime_review.tscn`.
- Parity variants:
  - `source_stack_runtime_review_close.tscn`
  - `source_stack_runtime_review_topdown.tscn`
  - `source_stack_runtime_grass_repair_close.tscn`
  - `source_stack_runtime_grassland_repair_close.tscn`
- Quarantined candidate catalog:
  - `materials/catalog_repair_candidates.json`
- Organic repair generator:
  - `pipeline/repair_organic_materials.py`

## Generated Assets

Source-stack control:

- `textures/source_stack/gloss_scrub_source_stack/manifest.json`
- `textures/wgv3/terrain_source_stack_gloss_scrub_source_stack.tres`

Repair-candidate source stacks:

- `textures/source_stack/gloss_grass_repair_source_stack/manifest.json`
- `textures/wgv3/terrain_source_stack_gloss_grass_repair_source_stack.tres`
- `textures/source_stack/gloss_grassland_repair_source_stack/manifest.json`
- `textures/wgv3/terrain_source_stack_gloss_grassland_repair_source_stack.tres`

## Captures

Primary source-stack control:

- `docs/captures/visual_remediation/source_stack_runtime_review_mid.png`
- `docs/captures/visual_remediation/source_stack_runtime_review_close.png`
- `docs/captures/visual_remediation/source_stack_runtime_review_topdown.png`

Organic repair evidence:

- `docs/captures/visual_remediation/organic_repair_contact_sheet.png`
- `docs/captures/visual_remediation/source_stack_runtime_grass_repair_close.png`
- `docs/captures/visual_remediation/source_stack_runtime_grassland_repair_close.png`

## Visual Verdict

The source-stack control is the right direction. It immediately reads closer to
the strong OpenTopo reference captures because the real macro color, roads,
vegetation masses, and terrain strata carry the image. This is the first M1-M7
runtime capture family that can reasonably be discussed against the 70 percent
target.

It is not final art closure:

- source orthophoto highlights and tree blobs remain visible;
- the review footprint must avoid wrapped source edges until a proper valid-area
  clamp/crop policy is added;
- close view still needs a better physically grounded detail layer;
- this validates source-stack runtime workflow, not all biome transitions.

Organic repair candidates improved their numeric noise metrics, but the runtime
review showed the important caveat: repaired procedural organics should be
albedo-only and very low strength until they earn normal/detail use. They remain
`repair_candidate`, not canonical material promotions.

The next generated-texture repair pass should go through ComfyUI prompt/variant
regeneration first, then reuse this source-stack terrain review gate. The
inventory and candidate queue are tracked in
`COMFYUI_TEXTURE_WORKFLOW_INVENTORY_2026_05_08.md` and
`world3/jobs/comfy_texture_regen_candidates.json`.

## Roadmap Impact

- R2 control pair is still `scrub_sparse -> dry_wash`.
- R3 source-stack pivot is started and has a working runtime review bridge.
- R4 source-material repair is active, but not visually closed.
- ComfyUI/`aaa_texture.py` is now tracked as a peer texture-source lane for M8
  regeneration, not a secondary cleanup path.
- R5/R6/R7 remain pending: repaired M4 context, M5/M7 rerenders, and visual
  closure decision still need to happen after the source/detail policy is stable.

## Rebuild

```powershell
python world3/pipeline/repair_organic_materials.py
python world3/pipeline/build_source_stack_runtime_review.py --detail-material scrub_sparse --id gloss_scrub_source_stack
python world3/pipeline/build_source_stack_runtime_review.py --detail-material grass_repair_calm --id gloss_grass_repair_source_stack
python world3/pipeline/build_source_stack_runtime_review.py --detail-material grassland_grass_repair_calm --id gloss_grassland_repair_source_stack
```

Run a Godot import after new PNG outputs, then capture through
`scripts/CaptureSceneOnce.gd` using the visible/windowed Godot path documented in
`WORKFLOW.md`. The Windows headless SceneTree runner can hang or return blank
frames before imports complete.
