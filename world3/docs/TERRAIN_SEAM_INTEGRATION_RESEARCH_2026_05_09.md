# Terrain Seam Integration Research - 2026-05-09

## Why This Exists

The repeated-source 2x2/3x3 review made one thing clear: forcing a finite
OpenTopo crop to wrap is the wrong production proof. The correct production
problem is not "make this image tile." It is terrain seam integration:
generating a controlled integration band where height, normals, material
weights, macro color, valid masks, and feature layers agree.

Ground texture transitions in M1/M2 worked because they were mostly 2D material
weight problems. Terrain stacks are harder. A terrain seam carries landform
shape, drainage, roads/washes, orthophoto macro features, material weights,
source validity, and mesh continuity. If those layers are solved separately,
the join can pass one view and fail another.

## Working Terminology

- Terrain seam integration: the whole process of making adjacent terrain
  sources meet without a visible break.
- Integration band: a generated/solved world-space strip around the boundary.
- Heightfield seam solver: the part that makes elevation, slope, normals, and
  mesh samples continuous across the integration band.
- Material/source solver: the part that blends or regenerates material weights,
  macro albedo, detail textures, and valid-source masks.
- Seam path selection: choosing where the least-visible join should pass when
  overlapping source data exists.
- Seam patch synthesis: generating missing terrain/color/material data when
  there is no real neighboring coverage.

## Research Takeaways

Image/texture research gives useful tools, but not a complete terrain answer:

- Poisson/gradient-domain blending is useful for solving smooth transitions
  from boundary constraints. For terrain, the analogous operation is solving a
  heightfield band that preserves local gradients instead of simply blurring
  two heights together.
- Graph-cut texture synthesis and image quilting both treat seams as paths
  chosen through compatible regions, not hard straight borders. That applies to
  terrain when we have overlapping source patches or variant candidates.
- Example-based terrain synthesis from DEM data supports the long-term
  direction: use real elevation examples as source patches and constraints,
  then synthesize plausible terrain instead of repeating one crop.

Production terrain tools point to the same layered model:

- Houdini heightfields are explicitly layer/mask based. Height, masks, erosion,
  and material attributes are separate layers that can be composed and
  regenerated.
- Unreal landscape workflows also separate sculpt/edit layers, material layer
  blends, and runtime virtual texture/material caching. The key lesson is that
  terrain composition is layered and cached, not a single wrapped bitmap.
- Large-terrain rendering systems such as geometry clipmaps solve continuity at
  streaming/LOD boundaries with transition regions. That is a rendering/LOD
  cousin of our data-boundary problem: boundaries need explicit treatment.

## Production Contract

Each terrain source should be treated as a data bundle, not a texture:

- height;
- source macro albedo/orthophoto;
- valid-source mask;
- material weights;
- normals/slope/curvature;
- feature layers such as washes, roads, ridges, vegetation density, and water;
- provenance and quality state.

Adjacent bundles should meet through a generated integration band:

1. Normalize projection, scale, resolution, origin, and vertical units.
2. Classify the boundary: same-source diagnostic, overlapping real neighbors,
   non-overlapping real neighbors, or procedural extension.
3. Build compatibility fields from height delta, slope delta, normal delta,
   color delta, material class, valid mask, and feature layers.
4. If overlap exists, choose a low-cost seam path through compatible regions.
5. Solve the heightfield band from boundary constraints, preserving plausible
   gradients and avoiding hard cliffs, stair steps, or blurred ramps.
6. Generate a continuous mesh from the solved heightfield or emit a seam mesh
   that shares edge samples with both sides.
7. Solve material weights and source macro color separately from height, using
   the same integration-band mask but not assuming the same operation is correct
   for every layer.
8. Rebuild normals, optional erosion/drainage detail, and detail-material
   masks after height integration.
9. Cache the result as a seam artifact with manifest, provenance, QA metrics,
   and view-mode captures.

## QA Gates

A seam/integration proof should fail if any of these are visible or measurable:

- hard height wall or stair-step at the boundary;
- normal/slope discontinuity visible in 3D lighting;
- orthophoto box, ghost strip, or repeated landmark;
- material weight pop in walk, iso, or topdown;
- invalid source pixels rendered as fake terrain;
- road/wash/cliff features smeared across the band with no plausible geometry;
- debug repeat tile accepted as production evidence.

Initial metrics:

- height delta at shared samples;
- slope and normal delta across the band;
- macro color delta after masking;
- valid-mask coverage;
- seam saliency from topdown, iso, and close 3D captures;
- no visible boxes/bands in a human visual pass.

## Roadmap Decision

Same-source repeated tiling stays useful as a diagnostic because it isolates
chunk streaming, shader binding, and sample-space bugs. It is not a visual
closure path.

The next production-relevant proof should be a small terrain seam integration
prototype:

- input: two source bundles, initially two nearby compatible crops or two
  deliberately offset crops from the same source;
- output: an integration-band artifact with solved height, normal/material
  weights, macro albedo, valid mask, and manifest;
- review scene: 2x2/side-by-side terrain using the seam artifact, with close
  3D, medium 3D, iso, topdown, and full-footprint passes;
- exit: no wall, no box, no ghost strip, and no fake plateau, while preserving
  plausible landform shape.

## First Implementation

Implemented 2026-05-09:

- proof doc: `M10_TERRAIN_SEAM_INTEGRATION_PROOF_2026_05_09.md`;
- generator: `world3/pipeline/build_terrain_seam_integration_proof.py`;
- review scene: `world3/scenes/review/source_stack_seam_integration_tour.tscn`.

This first rung uses overlapping same-source Gloss Mountain crops. It validates
the integration-band artifact and runtime path, not unlike-source synthesis.
The second rung now uses nearby non-overlap Gloss Mountain crops. It validates
crop compatibility gating, valid-mask repair, and the same runtime review path
without shared source pixels.

The third rung now has a first different-source implementation:

- scanner: `world3/pipeline/scan_terrain_seam_compatibility.py`;
- review scene: `world3/scenes/review/source_stack_cross_source_tour.tscn`;
- accepted proof: Gloss Mountain source stack into Guadalupe Cypress
  `phase2_fusion_max`.

This proof passed live visual review on 2026-05-09. The method lesson is that
scanner metrics are necessary but insufficient. Top numeric candidates can
contain landmarks, source-edge fill, or capture artifacts that would be
unacceptable in a production terrain workflow. Different-source terrain
promotion therefore requires both numeric compatibility and visual veto before
the output is accepted.

Scanner hardening is now implemented in
`world3/pipeline/scan_terrain_seam_compatibility.py`: optional fill/artifact
veto masks, rectilinear/low-detail visual-veto scoring, score filtering,
weighted candidate penalties, and ranked preview offsets. A second
Chuculay-Guadalupe real-to-real candidate was generated with captures. Live
review rejected it as accepted visual evidence because the Chuculay desert
source macro was already low quality before seam solving. This validates the
need for source-quality gates in addition to seam-compatibility metrics.

## Sources

- Poisson Image Editing, Perez/Gangnet/Blake, ACM TOG 2003:
  https://doi.org/10.1145/882262.882269
- Graphcut Textures: Image and Video Synthesis Using Graph Cuts, Kwatra et al.,
  ACM TOG 2003: https://doi.org/10.1145/882262.882264
- Image Quilting for Texture Synthesis and Transfer, Efros/Freeman, SIGGRAPH
  2001: https://people.eecs.berkeley.edu/~efros/research/quilting.html
- Terrain Synthesis from Digital Elevation Models, Zhou et al. project page:
  https://www.howardzzh.com/research/terrain/
- GPU Gems 2, Chapter 2, Terrain Rendering Using GPU-Based Geometry Clipmaps:
  https://developer.nvidia.com/gpugems/gpugems2/part-i-geometric-complexity/chapter-2-terrain-rendering-using-gpu-based-geometry
- Unreal Engine Runtime Virtual Texturing documentation:
  https://dev.epicgames.com/documentation/en-us/unreal-engine/runtime-virtual-texturing-in-unreal-engine
- Unreal Engine Landscape Edit Layers documentation:
  https://dev.epicgames.com/documentation/en-us/unreal-engine/landscape-edit-layers-in-unreal-engine
- SideFX Houdini HeightField documentation:
  https://www.sidefx.com/docs/houdini/nodes/sop/heightfield.html
