# world3 — Current Iteration Plan

**Phase A is done.** See [PLAN_phaseA_archived.md](PLAN_phaseA_archived.md)
for the closed-out checklist. This iteration is **Phase A polish + new
backends → Phase B (upscaling)**, sequenced so each step's output
feeds the next without backtrack:

> **Operating principle**: build tools and workflow improvements
> before pushing more output through the pipeline. Each step
> strengthens the foundation so we don't have to redo work later.
>
> OpenTopo branch work continues in parallel under another worker;
> not in scope here.

## Status

| Step | What | Status |
|------|------|--------|
| A.7 | Richness QA metric (advisory) | **DONE** (b551203, 2026-05-07) |
| A.8 | CHORD opt-in PBR backend (per research handoff) | **DONE** (ee73ccd, 2026-05-07) |
| A.9 | Variant-blend tool | **NEXT** |
| A.10 | IP-Adapter / FLUX Redux on flux_seamless.py (handoff) | queued |
| A.11 | CHORD + SM-roughness hybrid (surfaced by A.8) | queued |
| Phase B | Upscaling + multi-resolution pipeline | queued |

## Sequencing rationale

- **A.7 first**: strengthens the gate every future sweep uses.
  Done — landed advisory mode so existing grades don't shift.
- **A.8 (CHORD)**: highest-leverage swap per research handoff. Done
  as opt-in (not default) — A/B showed CHORD wins on hard-edge
  geometry but loses on rock roughness. See DECISIONS for the
  "opt-in, don't migrate" rationale.
- **A.9 (variant-blend) next**: alternative *generation strategy* —
  combine N variants into one tile instead of picking one. Doing
  before upscaling means anything we upscale benefits from the
  better source albedo.
- **A.10 (IP-Adapter)**: reference-photo conditioning on flux_seamless.
  Adds a new input modality to FLUX. Out of scope for A.9; queued.
- **A.11 (CHORD + SM-roughness hybrid)**: surfaced by A.8's roughness
  regression finding. Take CHORD's albedo/normal/height/metallic + SM's
  roughness, stitch together. Half-session of plumbing. Queued.
- **Phase B (upscaling)**: consumes the above improvements.

## A.9 — Variant-blend tool (NEXT)

**Why**: EXTERNAL_TECHNIQUES technique #5. Current `variant_select.py`
generates N candidates and picks the best one by edge-MSE. Variant-blend
would generate N candidates and *combine* them into a single tile via
edge-aware boundaries. Could rescue lattice-prone categories more cleanly
than prompt rewrites alone.

**Scope**:
- New tool `variant_blend.py`. Takes N albedo PNGs sharing a prompt;
  blends them with edge-aware boundaries (feathered-quadrant or
  Voronoi-region tiling). Each output region comes from one input
  variant; boundaries are feathered or guided by image structure to
  avoid visible seams.
- A/B against `variant_select.py` on the A.2 lattice-prone seeds
  (grass seed 100/300, leaf_litter seed 300).
- Decision after A/B: standardize as a new mode in the pipeline,
  keep as a manual rescue tool, or drop.

**Deliverables**:
- Working `pipelines/textures/variant_blend.py`.
- A/B comparison contact sheet under
  `world3/docs/captures/phase_a/A9_variant_blend_ab/`.
- TEXTURE_RND.md "A.9" entry with findings.
- TOOLS.md entry.
- Cookbook update if it changes a default.

**Exit**: tool works on the harness, A/B evidence supports a clear
decision (use it / don't use it / use it for specific categories).

**Estimate**: half-to-full session.

## A.10 — IP-Adapter / FLUX Redux (queued)

Per 2026-05-07 research handoff. Reference-photo conditioning on
flux_seamless.py's FLUX stage. Drop-in to existing pipeline; would
let us condition FLUX on real-world photos for material accuracy.

Defer until A.9 lands. Need to research IP-Adapter / FLUX Redux
install (ComfyUI nodes, model weights, gating).

## A.11 — CHORD + SM-roughness hybrid (queued)

Surfaced by A.8 A/B: CHORD wins normals + height on hard-edge rock,
SM wins roughness. A hybrid run = CHORD for everything except
roughness, run SM separately for roughness only, stitch. ~25s extra
per material; could give us best-of-both for rock-class materials.

Defer until A.9 lands. Cheap once we get to it.

## Phase B — Upscaling + multi-resolution pipeline (queued)

**Scope** (per ROADMAP):
- Audit `flux_upscale.py`.
- Research alternatives (Real-ESRGAN, SwinIR, BSRGAN, ComfyUI's
  upscaler ecosystem, tileable-aware SR).
- Pick a 512→1K and a 512→2K path.
- Build/extend an upscaler that handles all 5 PBR maps; normals
  need special handling (don't blur — bicubic or normal-aware SR).
- Per-tier QA using the post-A.7 gate (so smooth-A failures get
  caught at every resolution tier).
- Pick a flagship texture (probably wgv3_rock_dark with the new CHORD
  height) and produce the full ladder.

**Exit**: see ROADMAP.md Phase B exit criteria.

**Estimate**: 1-2 sessions.

## Out of scope for this iteration

- OpenTopo branch (another worker handles).
- Hero-mesh lane / Hunyuan3D-Paint (handoff decision #3 — user said
  "we'll see"; not opening yet).
- New shader features.
- New biome kits.
- Multi-tile streaming.

## After this iteration

Phase C (iso/topdown scale review) per ROADMAP. Camera framing work,
not texture work.

## OpenTopo Branch Status — 2026-05-07

OpenTopo work is active alongside the texture iteration.

Completed:

- Phase 2 max Guadalupe Cypress fused stack at 8192 plus 16K RGB
  stress layer.
- Phase 3 Smokies `USGS1m` 4-call fetch, streaming mosaic, validation,
  and Godot review scene.

Current OpenTopo docs:

```text
docs/OPENTOPO_PHASE2_MAX_REVIEW.md
docs/OPENTOPO_LARGE_4CALL_PLAN.md
docs/OPENTOPO_PHASE3_SMOKIES_4CALL_AUDIT.md
```

Next OpenTopo step: overlap point-cloud/color/canopy sources onto the
Smokies height mosaic, then split into chunks for close-up fidelity.
