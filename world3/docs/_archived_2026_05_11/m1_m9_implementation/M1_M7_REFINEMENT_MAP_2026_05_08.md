# M1-M7 Refinement Map

Date: 2026-05-08

## Purpose

This is the plain-English map for what M1-M7 actually accomplished and how each
area should be refined. Treat M1-M7 as workflow proofs, not visual closure. The
main target remains a terrain/material pipeline that can reach roughly 70
percent of the best stacked photo/topo source quality before production
promotion.

## Milestone Summary

| Milestone | What It Did | What It Proves | Current Gap | Refinement Target |
|-----------|-------------|----------------|-------------|-------------------|
| M1 Material catalog | Created a catalog of material IDs, source classes, biome kits, and generated material references. | The rest of the terrain pipeline can reference materials through stable IDs instead of ad hoc file paths. | Catalog entries know too little about promotion state, visual risk, source role, and view-specific readiness. | Turn the catalog into a real asset registry: provenance, source lane, promotion state, close/mid/far QA, quarantine flags, and required maps. |
| M2 Transition materials | Built deterministic transition strips from catalog IDs and biome transition rules, then reviewed them in Godot. | Transitions can be generated and reviewed as data-driven assets, not hand-placed one-offs. | The strips are promising, but source texture noise can make good blends look bad. The review board is still diagnostic. | Keep same-source calm control pairs, add stronger seam/edge metrics, review source-stack transitions, and separate transition failure from bad input-material failure. |
| M3 Chunk sweep | Tested terrain chunk sizes and locked 256 m chunks at 8 m mesh spacing for the synchronous base path. | The engine has a practical initial chunk size with seam evidence and runtime budget awareness. | Old M3 evidence is engineering/debug quality. A source-stack visual seam capture now exists, but seam metrics are still technical. | Keep M3 mostly technical: seam tests, border stitching, height/splat alignment, view-mode parity, and future LOD/async chunk budgets. |
| M4 Splat shader | Added the unified terrain splat shader, RGBA splat weights, OpenTopo reference comparison, and chunk material contract. | Runtime terrain can bind multi-material terrain data through one shader/material path. | Old splat showcase context is diagnostic only. Close-view source-stack context now looks credible, but wider/topdown/iso review is not solved. | Continue M4 around source-stack macro terrain, valid-area masks, repaired detail materials, and review scenes that look like the intended pipeline. |
| M5 Walk streaming | Wired visible 256 m chunks into the walk scene, scripted chunk crossing, and captured streaming metrics. | The player can move through streamed terrain chunks with measurable chunk build/remove behavior. | Old walk capture inherits bad M4 context. Source-stack inspection capture now exists, but first-person/horizon framing still exposes finite-footprint artifacts. | Refine walk/iso/topdown framing, far-field policy, lighting, camera height, hitch budgets, and repeatability. |
| M6 Runtime hardening | Added runtime image caches, export-safe paths, streamed collision chunks, collision metrics, and transition runtime review hooks. | Runtime terrain data can be loaded from cache and collided against instead of depending on editor-only image imports. | Source-stack collision rerender exists; async/background build and collision LOD policy remain future hardening. | Add async/background build options, stricter cache manifests, collision LOD policy, profiling gates, and validation scenes that run under walk/iso/topdown. |
| M7 Boundary runtime | Generated per-chunk transition masks from biome rules and placed transitions automatically in runtime boundary scenes. Added source-stack control/context rerenders and same-source mask QA. | Boundary placement is now data-driven, measurable, and can run through runtime chunks instead of manual shader placement. | Same-source source-stack control is visually cleaner and has a mask-metrics pass, but cross-material stress and view parity remain open. | Add clean cross-material source-stack control pairs, rerun mask metrics per stress scene, and add walk/topdown/iso boundary reviews. |

## Refinement Principles

1. Split proof from promotion.
   Engineering diagnostics are allowed to look bad if they prove plumbing. Visual
   validation sheets should show the current quality target only.

   Current concrete example: the M3 chunk seam and M4 splat/chunk captures are
   valid workflow evidence, but the user correctly rejected them as visual
   evidence. Keep those in diagnostics until the source-stack M4 context is
   rebuilt.

2. Source-stack first, generated detail second.
   OpenTopo/source-stack terrain is the current visual control lane. ComfyUI and
   `aaa_texture.py` remain equally important as the scalable detail-material
   generation lane, but generated materials stay quarantined until terrain
   context review passes.

3. Diagnose failures by layer.
   A bad screenshot can come from bad material source, bad transition logic, bad
   shader binding, bad terrain framing, or bad runtime view setup. Refinement
   work should identify which layer failed before replacing systems.

4. Require view parity before closure.
   M4-M7 should eventually have close/walk, topdown, and iso captures. A workflow
   is not mature if it only looks credible from one camera.

## Refinement Order

1. M1 registry cleanup.
   Add enough metadata to distinguish canonical, sidecar, quarantined, and
   diagnostic materials.

2. M4 source-stack splat context.
   Replace the old prototype terrain context with source-stack macro color plus
   valid-mask-gated detail. Close-view v1 is captured; next is wider/topdown/iso
   framing without finite-footprint debug artifacts.

3. M5 source-stack walk rerender.
   Reuse the repaired M4 context in an actual walk/streaming scene and compare
   runtime metrics against the current M5 baseline.

4. M7 boundary rerender.
   Re-run automatic boundary placement over the repaired M4/M5 terrain context.
   Same-source source-stack control and mask metrics now exist; next M7 work is
   cross-material stress and view parity.

5. M2 transition refinement.
   Review same-source calm controls and cross-biome stress pairs after the source
   materials are no longer sabotaging the read.

6. M3/M6 technical hardening.
   Keep these as engineering foundations: seam/collision/cache/performance gates,
   then expose them through prettier review views only when useful. M3 now has a
   source-stack visual seam capture; next is quantitative seam discontinuity QA.

## Immediate Next Move

Do not continue treating the old M3-M6 debug screenshots as visual validation.
They belong in the engineering diagnostics contact sheet. The main visual pass
should refine M4/M5/M7 around the source-stack path, while M1/M2/M3/M6 get
targeted contract and QA improvements that support that visual lane. M7 now has
a same-source source-stack visual control plus quantitative transition-mask QA,
so the next practical roadmap move is M8 organic cleanup while cross-material M7
stress and view parity stay open.
