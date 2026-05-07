# world3 — Current Iteration Plan

**Phase A is done.** See [PLAN_phaseA_archived.md](PLAN_phaseA_archived.md)
for the closed-out checklist; ROADMAP.md "Phase A — DONE" for the
outcome summary.

> **Status: 2026-05-07 — between iterations.** This PLAN is
> intentionally short until we pick the next iteration. The candidates
> below are real options to choose from; the user picks one and this
> file gets rewritten with the actual scope.

## Candidate next iterations

Ranked by "smallest scope first" so each can land cleanly without
compounding risk.

### Option 1 — Phase A.7 polish: build the "richness" QA metric (small)

**Why it might be next**: Phase A surfaced 3 confirmed "smooth-A"
cases (sand seed 200, powder snow seed 100, canyon_rock
ground_level_lead). LESSONS L16 has flagged this since A.2; the
empirical case for adding a minimum-energy QA check is now strong.

**Scope**: Add a Laplacian-energy / local-variance threshold to
`texture_qa.py`. Calibrate on existing graded textures (look at
edge_mse vs Laplacian energy across our library). Add per-category
thresholds since uniform-roughness materials (snow) legitimately have
low spatial energy too.

**Estimate**: half a session. Mostly local code change; would
strengthen the gate against the failure mode we know exists.

**Deliverable**: a 4th gate axis (`richness`), updated
`PIPELINE.md`, calibration evidence in TEXTURE_RND Part 1.

### Option 2 — Phase B: upscaling research (medium)

**Why it might be next**: This is what ROADMAP.md calls "next." Many
of A.5's external-techniques pointers (CHORD, controlnet-inpaint
variants, Real-ESRGAN tile-aware) are upscaling-adjacent — we already
have context. Currently 512 throughout; close-walk and hero-material
use cases would benefit from 1K/2K.

**Scope**: Audit `flux_upscale.py`. Research alternatives (Real-ESRGAN,
SwinIR, BSRGAN, ComfyUI's upscaler ecosystem, tileable-aware SR).
Pick a 512→1K and a 512→2K path. Build/extend an upscaler that
handles all 5 PBR maps (normals need special handling). Per-tier QA.
Pick a flagship texture and produce the full ladder.

**Estimate**: 1-2 sessions. Research is the bulk; implementation is
constrained.

**Deliverable**: pipeline command that takes a 512 set → 1K or 2K
with all maps preserved and tiling intact. Documented policy: which
textures get which tier.

### Option 3 — OpenTopo branch work (medium-large)

**Why it might be next**: There's an active OpenTopo addendum in the
archived PLAN; planning docs exist for HD-review and 4-call USGS1m
plans. This is the orthogonal work-stream that ran alongside texture
R&D this phase.

**Scope**: per [OPENTOPO_TEXTURE_SCENE_ROADMAP.md](OPENTOPO_TEXTURE_SCENE_ROADMAP.md)
and [OPENTOPO_LARGE_4CALL_PLAN.md](OPENTOPO_LARGE_4CALL_PLAN.md).
Review HD/MAX single-tile scenes; identify close-up failure modes;
prototype baked ground textures from orthophoto/fused layers; run
the planned 4-call USGS1m test.

**Estimate**: 2-3 sessions. Large scope; mostly OpenTopo-side work
not texture-pipeline.

**Deliverable**: stitched USGS1m mosaic; baked PBR set from real
orthophoto data; documented decision about chunked-delivery vs.
single-texture for near-camera fidelity.

### Option 4 — Variation-and-stitch tool (small-medium)

**Why it might be next**: EXTERNAL_TECHNIQUES technique #5 — generate
N variants, *blend* them into one tile (instead of *picking* one).
Could rescue lattice-prone categories more cleanly than prompt
rewrites alone, and we have a working harness to test it.

**Scope**: New tool `variant_blend.py`. Takes N albedo PNGs sharing a
prompt, blends them with edge-aware boundaries (Voronoi-region or
feathered quadrant tiling). A/B against `variant_select.py` on the
A.2 lattice-prone seeds.

**Estimate**: half-to-full session. Self-contained tool work.

**Deliverable**: working tool, A/B comparison vs variant_select on
representative cases, decision about whether it's worth standardizing
into the default pipeline.

## How to commit to one

Pick one of the above (or propose a different scope). This file gets
rewritten with the chosen iteration's full task list, deliverables,
and exit criteria — same shape as the archived Phase A plan.

If a phase is *meaningfully* smaller than the others (option 1 is
maybe a half-session vs option 3's 2-3 sessions), it can be done as
"Phase A.7 polish" and folded back into Phase A's archive rather than
becoming its own iteration.
