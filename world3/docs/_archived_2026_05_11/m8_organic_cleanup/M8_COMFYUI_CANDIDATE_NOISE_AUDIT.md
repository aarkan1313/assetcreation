# M8 ComfyUI Candidate Noise Audit

Date: 2026-05-08

This audit reuses the M6 source-material noise metric against the first M8
ComfyUI regeneration candidate. It is a source-material QA pass, not a
transition or chunk-streaming failure.

| Material | Status | HF energy | Grad p95 | Green dom | Flags |
|----------|--------|-----------|----------|-----------|-------|
| `m8_grassland_grass_calm_v3` | ok | 0.037443 | 0.096886 | 0.000248 | - |

## Verdict

Flagged 0 of 1 audited green/organic materials.
`m8_grassland_grass_calm_v3` clears the high-frequency, micro-contrast, and
green-speckle thresholds that flagged the current `grassland_grass` material.
It still needs terrain-context promotion before replacing any canonical
material.
