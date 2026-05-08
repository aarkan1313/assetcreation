# OpenTopo Texture, Scene, And High-Detail Roadmap

This plan extends the two OpenTopo pilots:

- Phase 1 proved same-product mosaics: several DEM calls can become one
  coherent terrain.
- Phase 2 proved fused stacks: height, orthophoto, NIR, point-cloud-derived
  canopy, hillshade, slope, and roughness can be aligned into one Godot scene.

The next question is not just "can we load the data?" It is "what can this
become?" There are three useful workflows.

## Workflow 1: Baked Ground Textures

Goal: turn real OpenTopo imagery and derived masks into reusable ground
materials.

Operational recipe:

```text
D:/assets/world3/docs/OPENTOPO_TILEABLE_REAL_TEXTURE_WORKFLOW.md
```

This is not a real-place map workflow. It treats orthophoto and fused layers as
source material for textures: dry wash, rocky slope, scrub, exposed soil,
chaparral floor, canyon rock, etc.

Inputs:

- Orthophoto RGB for real color structure.
- NIR/vegetation mask to separate plant-covered and bare areas.
- Slope, roughness, elevation, and hillshade to infer rock/soil form.
- Optional LAZ color/intensity/density as extra evidence.

Outputs:

- Seamless albedo tiles.
- Normal, roughness, height, and blend masks.
- Optional larger macro-texture atlases for terrain color variation.
- Provenance sidecars that say which real source crop was used.

Good for:

- Building grounded fantasy/game materials from real terrain.
- Feeding the existing texture pipeline with real-world source examples.
- Creating biome-specific kits without hand-inventing every material.

Not good for:

- Preserving exact geography.
- Close-range photogrammetry.
- Treating measured pixels as authoritative after tiling/inpainting/style work.

Updated direction after first visual review:

The first single-tile hex review is useful but not final. Some crops are
technically seamless yet still read wrong because noisy orthophoto structure is
repeated at the wrong scale. The next step is not heavier repair of one crop; it
is a multi-variant source-real atlas.

Material stack target:

```text
macro: full-map or large-crop real color, low frequency
meso: unlike real crop variants per material class
micro: cleaned close-detail normal/roughness/noise
```

First executable slice:

1. Pick one class, starting with `dry_wash`.
2. Select `8-16` sibling real crops from the same fused stack.
3. Repair each crop independently as `tileable_real`.
4. Build a mixed `16 x 16` Godot review grid.
5. Reject variants that create blocky color changes, repeated noisy motifs, or
   implausible scale.

Prototype:

1. Pick 4-6 crops from the Guadalupe Cypress fused stack:
   dry wash, rocky slope, scrub/vegetation patch, mixed bare soil, bright rock,
   and shadowed drainage if available.
2. Export each crop at fixed ground scales: 16 m, 32 m, 64 m, and 128 m.
3. Build tileable versions through the texture pipeline.
4. Derive PBR maps.
5. Compare:
   direct crop vs. seamless repaired crop vs. generated/stylized material.

## Workflow 2: Fused Real-Place Scenes And Maps

Goal: make viewable maps/scenes that preserve the actual place.

This is what Phase 2 currently demonstrates. The scene is not just a heightmap:
it has real color and real support layers.

Inputs:

- DTM/DEM as base ground.
- Orthophoto RGB as real-color reference or albedo.
- NIR/vegetation products as masks.
- LAZ-derived canopy/CHM and point-cloud color products.
- Slope, roughness, hillshade, and QA layers.

Outputs:

- Godot review scene.
- Heightmap plus aligned layer stack.
- Material masks for rock/soil/vegetation/wash/road/water when derivable.
- Optional vegetation/scatter maps.
- Audit report and stack manifest.

Good for:

- Real-world playable/test scenes.
- Terrain design reference.
- Orthophoto-driven material masks.
- Canopy and vegetation placement.

Not good for:

- Infinite zoom by itself. A single 1024 or 4096 texture over a large AOI will
  always fail at close range.
- Reusing the scene as a generic seamless material. That is Workflow 1.

Near-term improvements:

1. Add a better terrain material that can preserve orthophoto while using
   source-derived detail maps up close.
2. Use NDVI/CHM/canopy layers to place simple vegetation markers or instanced
   prototypes.
3. Add material-mask exports, not just debug overlays.
4. Keep orthophoto as a toggleable reference even when final rendering uses
   custom materials.

## Workflow 3: High-Detail Zoom And Chunked Delivery

Goal: find how far we can zoom in while staying high fidelity.

Workflow 3 uses the same source stack as Workflow 2, but solves a different
problem: delivery. It is about texture size, mesh density, chunking, LOD, and
streaming.

Current Phase 2 review limits:

```text
AOI:             1.6 km x 1.6 km
Texture export: 1024 x 1024
Texture scale:  1.56 m/px
Mesh:           256 subdivisions
Mesh spacing:   about 6.25 m/vertex
```

Source-data ceiling for Guadalupe Cypress:

```text
RGB orthophoto: about 0.066 m/px
NIR orthophoto: about 0.065 m/px
DTM:            1.0 m cell size
```

That means color can support much closer inspection than the current viewer.
Geometry is bounded by the 1 m DTM unless we derive surface detail from LAZ,
source-derived normal maps, or chunked higher-density meshes.

Single-tile texture ladder for the 1.6 km AOI:

| Export Size | Ground Detail | Use |
|---|---:|---|
| 1024 | 1.56 m/px | current overview/debug |
| 2048 | 0.78 m/px | light upgrade |
| 4096 | 0.39 m/px | first serious HD review |
| 8192 | 0.195 m/px | close-ish inspection, heavy |
| 16384 | 0.098 m/px | probably chunked only |
| source-native crop | about 0.066 m/px | chunked/streamed only |

Approximate uncompressed RGB memory per layer:

| Size | RGB8 Layer |
|---|---:|
| 1024 | 3 MB |
| 2048 | 12 MB |
| 4096 | 48 MB |
| 8192 | 192 MB |
| 16384 | 768 MB |

The 8192 single-tile test is useful, but it is not the final architecture.
Chunking becomes mandatory if we want several layers, larger AOIs, or close
walking.

Chunked prototype:

1. Split the 1.6 km Phase 2 AOI into `4 x 4` chunks of 400 m each.
2. Export each chunk at 2048 or 4096.
3. Keep height on the same canonical grid so chunk edges match.
4. Load only nearby chunks in Godot.
5. Use lower-resolution far chunks and high-resolution near chunks.
6. Validate seams in height, orthophoto, masks, and material blends.

## Relationship Between Workflows

Workflow 2 and Workflow 3 share data, but they are not the same decision.

- Workflow 2 answers: what layers belong together and what do they mean?
- Workflow 3 answers: how do we render those layers at useful close-range
  fidelity?

Workflow 1 is separate: it extracts reusable materials from the same evidence.

The likely end state combines all three:

1. Build a fused real-place stack.
2. Deliver it as chunks/LOD for close zoom.
3. Use baked real-ground materials or source-derived detail maps when close
   range exposes image limits. Keep any fantasy/stylized material as a separate
   art derivative, not source repair.

## Proposed Next Sprint

### Step 1: Phase 2 HD Single-Tile Review

Status: 4096 HD pass complete, 8192 max pass complete, and 16K RGB-only stress
layer complete.

Create a higher-detail review scene before building chunk streaming.

Deliverables:

- `toporeview/phase2_fusion_hd_review.tscn`
- `toporeview/phase2_fusion_hd/`
- 4096 exports for:
  - `orthophoto_rgb`
  - `orthophoto_nir_false`
  - `vegetation_ndvi_like`
  - `hillshade`
  - `slope_deg`
  - `roughness`
- Optional 8192 export for `orthophoto_rgb` only if memory behaves.
- Mesh test at 512 and 1024 subdivisions.
- Fixed screenshot set:
  - high overview
  - mid-altitude
  - close ground
  - steep slope
  - vegetated patch

Current audit:

```text
world3/docs/OPENTOPO_PHASE2_HD_REVIEW.md
world3/docs/OPENTOPO_PHASE2_MAX_REVIEW.md
world3/docs/OPENTOPO_LARGE_4CALL_PLAN.md
world3/docs/OPENTOPO_PHASE3_SMOKIES_4CALL_AUDIT.md
```

Questions to answer:

- At what camera height does 4096 stop looking good?
- Does 8192 materially improve the close view?
- Is the limiting factor texture resolution, mesh spacing, or lack of material
  micro-detail?

### Step 2: Baked Ground Texture Prototype

Use Phase 2 as texture source.

Status: first pilot complete; unlike-tile prototype has produced six current
soft-composite source-real material classes.
See:

```text
D:/assets/world3/docs/OPENTOPO_TILEABLE_TEXTURE_PILOT_AUDIT.md
D:/assets/world3/docs/OPENTOPO_TILEABLE_REAL_TEXTURE_WORKFLOW.md
```

Deliverables:

- Existing: 4-6 source material classes, `source/`, `tileable_real`, and
  `stylized_pixel` outputs, plus Godot comparison scene.
- Existing: `dry_wash` mixed-cell variant atlas scene for hard-switch QA.
- Existing: six `4096` `tileable_soft` composites for `bare_soil`,
  `bright_rock`, `dry_wash`, `rocky_slope`, `scrub_dense`, and `scrub_sparse`.
- Existing: `tileable_soft_composite_gallery.tscn` and labeled 2x2 material
  sheet for review.
- Next: close/mid/far scale notes so noisy crops are rejected even when seam QA
  passes.
- Next: reusable Godot material path that treats the real map as macro color,
  soft composites as meso material, and separate generated/filtered detail as
  close micro texture.

Questions to answer:

- Can real orthophoto crops become good tileable game textures?
- Do they need heavy delighting/shadow removal?
- Do generated/stylized variants beat direct repaired crops?
- Does a multi-variant source-real atlas read more natural than a single crop?
- How much color normalization is needed before unlike variants stop looking
  blocky?

### Step 3: Chunked HD Prototype

Only start after Step 1 tells us the useful target resolution.

Deliverables:

- 4 x 4 chunk export of the same 1.6 km AOI.
- Godot loader scene with nearby chunks.
- Seam validation for chunk edges.
- Memory/performance notes.

Questions to answer:

- What chunk size is practical: 256 m, 400 m, or 512 m?
- What per-chunk texture size is practical?
- How many chunks can stay loaded before frame or memory budget breaks?

## Quality Rules

- Every derived visual layer must record provenance.
- Synthetic fill, texture repair, and generated detail must be labeled as such.
- Measured layers and artistic layers must not be mixed without a manifest role.
- No-data gaps should be preserved first, then filled in an explicit later pass.
- Close-up screenshots are required; overview screenshots alone can hide failure.
