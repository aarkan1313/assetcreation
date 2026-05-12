# M1-M7 Vision Gap Review

Date: 2026-05-08

Reviewer: Codex vision pass over the actual capture PNGs.

## Target Bar

Set the visual closure bar at roughly **70 percent of the best stacked
photo/topo OpenTopo output**, not at "nonblank runtime capture."

Reference captures:

- `docs/captures/opentopo/godot_gloss_mountain_textured_master.png`
- `docs/captures/opentopo/godot_phase2_fusion_max.png`
- `docs/captures/opentopo/opentopo_master_stack_final_comparison.png`

These references are not perfect, but they have qualities the M1-M7 runtime
captures mostly lack:

- Terrain color is anchored to real source imagery or source-derived layers.
- Macro patterns follow landform instead of arbitrary texture repeats.
- Detail density is plausible for the camera distance.
- The viewer reads "place/terrain" before reading "material test."

Current M1-M7 terrain visuals are mostly far below that bar. Many captures read
as debug visualization or material plumbing evidence.

## Severity Summary

| Area | Visual Score Vs Target | Verdict |
|------|------------------------|---------|
| M1 kit/material visuals | 15-35 percent | Source material and scale rework. |
| M2 transition strips | 20-55 percent | Algorithm useful, source-dependent, not terrain-proof. |
| M3 chunk visuals | 20-40 percent | Engineering proof only. |
| M4 splat visuals | 10-25 percent | Debug/prototype, not art evidence. |
| M5 walk visuals | 10-30 percent | Runtime path works, visual target fails. |
| M6 runtime visuals | 15-30 percent | Cache/collision proof only. |
| M7 boundary visuals | 10-25 percent | Runtime mask proof only. |

The only capture family near the intended direction is the OpenTopo real-source
material and stacked terrain work. The current procedural runtime path should be
judged as infrastructure, not visual quality.

## Specific Visual Gaps

### M1 Material / Kit Gaps

Representative captures:

- `docs/captures/phase_e/alpine_walk.png`
- `docs/captures/phase_e/alpine_iso.png`
- `docs/captures/phase_e_gallery/des_mojave_usa/iso.png`
- `docs/captures/phase_e_gallery/med_california_chaparral/iso.png`
- `docs/captures/phase_e_gallery/tgs_serengeti_tanzania/topdown.png`

Findings:

- Alpine walk is blown out and noisy. It reads as white texture noise, not snow
  or alpine ground.
- Alpine iso has harsh white/green/tan bands and neon grass. Material zones do
  not feel terrain-authored.
- Mojave iso is a toy-like single tan sheet with weak surface variation.
- Chaparral iso has heavy high-frequency speckle over the whole mountain.
- Serengeti topdown is a uniform yellow noise field with little landform read.

Gap: M1 catalog identity is useful, but the catalog's material candidates are
not good enough for visual closure. The core missing layer is source-real macro
anchoring plus camera-specific scale control.

### M2 Transition Gaps

Representative captures:

- `docs/captures/transitions/godot_transition_strip_review.png`
- `docs/captures/transitions/desert_sand__grassland_grass_hard_vs_transition.png`
- `docs/captures/transitions/scrub_sparse__dry_wash_hard_vs_transition.png`
- `docs/captures/transitions/tundra_moss__temperate_forest_grass_hard_vs_transition.png`

Findings:

- The transition algorithm can soften a boundary when both inputs are already
  quiet and compatible.
- `scrub_sparse -> dry_wash` is the best control, but it is low-contrast and
  still only a flat material-strip proof.
- `desert_sand -> grassland_grass` fails visually. The grass source looks like
  stylized straw/hair and dominates the image.
- `tundra_moss -> temperate_forest_grass` fails visually. The leaves are
  discrete repeated objects, not terrain material at runtime scale.

Gap: M2 needs terrain-context review using promoted source materials. The
transition strip builder is not the main failure; bad source materials and bad
scale are.

### M3 Chunk Gaps

Representative captures:

- `docs/captures/phase_f/chunk_sweep/chunk_256m_seam.png`
- `docs/captures/phase_f/tetons_2x2_topdown.png`

Findings:

- M3 remains valid as an engineering decision.
- The visual captures are not art evidence. The 2x2 topdown has obvious
  repeated tile structure and quadrant seams.
- The seam screenshots are diagnostics and should stay out of visual closure.

Gap: chunk QA needs separate labels for geometry seam correctness, material seam
correctness, and terrain-art quality.

### M4 Splat Gaps

Representative captures:

- `docs/captures/m4/splat_shader_review.png`
- `docs/captures/m4/chunk_splat_stream_review.png`
- `docs/captures/m4/opentopo_unified_review.png`

Findings:

- `splat_shader_review.png` is posterized and blocky. It reads as a weight-map
  debug view, not terrain.
- `chunk_splat_stream_review.png` shows large rectangular material/chunk
  discontinuities.
- `opentopo_unified_review.png` is useful shader-compatibility evidence, but it
  is a flat material panel, not a terrain-quality pass.

Gap: M4 needs a better splat source. Height/slope procedural weights are not
enough. Use source-derived macro masks or OpenTopo-style layer evidence before
visual rerender.

### M5 Walk Gaps

Representative captures:

- `docs/captures/m5/walk_chunk_splat_smoke.png`
- `docs/captures/m5/walk_long_contact_sheet.png`
- `docs/captures/m5/walk_long_frames/walk_long_0600.png`

Findings:

- The runtime path works, but close terrain is visually poor.
- Brown material appears as oversized scratches/twigs pasted across slopes.
- Grass close-up is extremely bad: over-saturated, object-like, and tiled in
  rectangular chunks.
- Chunk/material rectangle boundaries are visible in multiple frames.

Gap: walk mode needs its own near-field material system. The current splat
texture and material repeats are incompatible with close camera review.

### M6 Runtime Gaps

Representative captures:

- `docs/captures/m6/walk_stream_collision_cache.png`
- `docs/captures/m6/transition_runtime_review.png`

Findings:

- M6 is a valid cache/collision proof.
- The walk visual still looks like a flat debug terrain with weak landform
  detail and material wash.
- The transition-runtime review is a shader-hook proof only; it has broad
  artificial bands and no convincing terrain context.

Gap: runtime hardening should not imply visual hardening. Keep metrics, reject
visual promotion.

### M7 Boundary Gaps

Representative captures:

- `docs/captures/m7/boundary_runtime_review.png`
- `docs/captures/m7/boundary_runtime_biome_stress.png`
- `docs/captures/m7/boundary_walk_after_crossing.png`

Findings:

- The same-source boundary is so subtle and flat that it does not prove a
  production transition.
- The biome stress capture is a horizontal two-zone material debug image, with
  visible speckle/noise and no terrain believability.
- The walk boundary capture is nearly featureless and still has debug-rectangle
  reads.

Gap: M7 validates rule-driven mask plumbing only. It does not validate terrain
transition quality.

## Root Gap

The failed visual path is not a single bug. It is a pipeline gap:

1. Procedural tile materials are being asked to stand in for source-ground truth.
2. Splat masks are generated from simple height/slope/debug logic instead of
   credible macro source layers.
3. Walk/iso/topdown are not yet visually equivalent review surfaces.
4. Captures were allowed to pass as "visual evidence" when they were really
   runtime/debug evidence.

## Revised Goal

Before visual closure, a terrain milestone should produce a capture that reaches
about 70 percent of the OpenTopo stacked reference quality:

- Real or source-derived macro color.
- Landform-following material distribution.
- No visible debug rectangles or chunk material blocks.
- No stylized object-texture repeats at walk scale.
- Camera-specific texture scale that does not collapse into speckle/noise.

## Recommended Correction

Do not try to tune the current debug captures into shape. The next correction
should pivot the runtime material path toward the OpenTopo stack principles:

1. Use source-derived macro albedo/color as the base visual layer.
2. Use procedural/tileable materials as detail overlays, not the whole terrain
   identity.
3. Use OpenTopo finished materials as the control materials for M2/M4/M7.
4. Keep `scrub_sparse -> dry_wash` as the first transition control.
5. Quarantine grass/leaf/straw materials until regenerated or replaced.
6. Rerender M4/M5/M7 only after the material source stack is changed.
