# M7-M12 Closure Audit - 2026-05-10

## Purpose

This audit checks whether the terrain foundation lane is strong enough to open
the deferred systems without pretending that workflow evidence is production
art.

The answer is: yes for planning and representative workflow work, no for
production promotion without the new promotion gate.

## Milestone Status

| Milestone | Status | Evidence | Residual Risk |
|-----------|--------|----------|---------------|
| M7 boundary runtime integration | Workflow pass, visual conditional | `M7_BOUNDARY_RUNTIME_INTEGRATION.md`, `M7_SOURCE_STACK_BOUNDARY_REVIEW_2026_05_08.md`, `M7_TRANSITION_MASK_METRICS_2026_05_08.md` | Cross-material stress still depends on source-material quality. |
| M8 organic source-material cleanup | Partially active, not closed | `M8_ORGANIC_REGEN_QUEUE_STATUS_2026_05_08.md`, `M8_COMFYUI_TERRAIN_CONTEXT_REVIEW_2026_05_08.md` | `m8_grassland_grass_calm_v3` is sidecar-only; close-play organic materials still need batch review. |
| M9 runtime performance/polish | Prototype evidence, not production perf closure | M5/M6 runner metrics and M12 runtime scene | No dedicated post-M12 interaction/hitch budget has been run. |
| M10 seam/cross-source/ecotone | Workflow accepted | `M10_TERRAIN_SEAM_INTEGRATION_PROOF_2026_05_09.md`, `M10_ECOTONE_LAYER_PROOF_2026_05_09.md` | Real-to-procedural and unlike-biome close play are conditional until richer detail/scatter exists. |
| M11 junction/corner | Representative workflow accepted | `M11_JUNCTION_LAYER_PROOF_2026_05_10.md`, `M11_FOURWAY_CORNER_PROOF_2026_05_10.md`, `M11_JUNCTION_CASE_MATRIX_2026_05_10.md` | T/L/island variants are future case-library work; placeholder scatter is not production. |
| M12 view-mode parity | Representative runtime workflow accepted after live review | `M12_VIEW_MODE_PARITY_AUDIT_2026_05_10.md`, `M12_RUNTIME_PARITY_PROOF_2026_05_10.md` | Bulk region gallery remains M16 follow-up; no production promotion is implied. |

## Foundation Gate

The foundation now demonstrates:

- chunked runtime terrain through `ChunkLoader`
- valid source-footprint clipping
- source macro + valid-mask runtime contribution
- runtime splat weights
- same-area close/medium/iso/topdown parity
- real-to-real, real-to-procedural, unlike-biome, and four-way junction workflow proofs

This is enough to open the post-parity lane. It is not enough to mark any
current terrain proof as production-promoted.

## Blockers Before Production Promotion

- Close-play material quality, especially organic/grass/ground detail.
- Placeholder scatter and feature meshes.
- Dedicated runtime interaction/performance pass after representative parity.
- Production promotion manifest and audit must stay current.

## Decision

Open the post-M12 roadmap, starting with production-promotion gates. The next
work should not be "add lots of content"; it should be "make promotion,
feature/scatter replacement, close-play material quality, and procedural
extraction auditable."
