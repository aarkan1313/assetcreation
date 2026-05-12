# world3 — Iteration Plan (Phase A) — ARCHIVED

> **Status: archived 2026-05-07** — Phase A completed in this session.
> Exit criteria all met; see ROADMAP.md "Phase A — DONE" entry for the
> full checklist with outcomes. Findings live in
> `pipelines/textures/TEXTURE_RND.md` (Part 1: A.2/A.3/A.4/A.6 sweeps;
> Part 2: cookbook updates), `pipelines/textures/LESSONS.md` (L17/L18/L19),
> and `pipelines/textures/EXTERNAL_TECHNIQUES.md`.
>
> Current iteration plan is in [PLAN.md](PLAN.md).

---

Roadmap v2 starts here. Phase A is **texture quality + prompt R&D** —
mostly experiments and observations rather than new features. Goal is
to measurably improve texture-pipeline first-pass success rate from
~70% to ~80%+ through better prompts, better settings, and at least
one new technique adopted from external research.

This phase isn't about new code (much). It's about *understanding* the
tools we have. Outputs are documents and revised prompts more than
shippable features.

## Operating tempo for this phase

Each "experiment" is a constrained sweep:
- Variable: one thing (prompt phrasing OR seed OR variants count OR
  heal_strength OR delight strength)
- Fixed: everything else
- Output: a contact sheet (10 thumbnails laid out in a grid) + grade
  table + one-line subjective ranking

We run sweeps, look at outputs, write down observations, repeat. No
"big-bang" rebuild of the pipeline.

## Tasks (in order)

### A.1 — Build the experiment harness

Need: a reproducible way to run "same prompt × N seeds" and end up
with one PNG showing the result grid + a manifest of grades. The
texture pipeline can run an --id with --seed-base N, but we don't
have a "sweep" wrapper.

**Deliverable**: `pipelines/textures/experiment.py` that:
- Takes a name, a prompt, a list of seeds, and any aaa_texture
  arg overrides
- Runs aaa_texture for each seed (skipping --no-gate so we see real
  grades)
- Collects each result's albedo + tile_2x2 + grade from the manifest
- Composes a contact sheet PNG: NxM grid of (tile_2x2, grade caption)
- Writes a JSONL manifest: one row per run with prompt, seed, grade,
  metric numbers
- Target output: `D:/tmp/world3_experiments/<name>/` with
  `contact_sheet.png` + `manifest.jsonl`

**Estimate**: 30-60 min. Single Python script + one wrapper around
subprocess.

### A.2 — Same-prompt sweep × 5 materials

Pick 5 representative material types: sand, smooth-rock, grass,
fresh-snow, leaf-litter. For each, our current best prompt + 10 seeds
+ 4 variants each.

**Deliverable**: 5 contact sheets in
`world3/docs/captures/phase_a/same_prompt_sweep/<material>/`. Plus a
short writeup: "sand is grade A 8/10 times; rock is 3/10; grass is..."

**Estimate**: ~30 min generation + 30 min review. (Each sweep is
4 variants × 10 seeds × ~30s SM = 20 min generation per material. We
parallelize where possible.)

Wait — that's actually 10 *full pipeline runs* per material × 5
materials = 50 textures × 4-5 min each = 4 hours of compute. Too
much. Smaller version:

**Revised**: 5 seeds per material instead of 10. 25 textures total. 
~2 hours of compute, can run in background.

### A.3 — Prompt-permutation sweep on one hard case

Pick one consistently-difficult material (probably "sand" given the
recent failures). Hand-write 4 prompt variants:
1. Current cookbook winner
2. More minimal ("close-up sand, top-down photo")
3. More elaborate (extra material adjectives)
4. Different lead phrase ("aerial photograph of" vs "close-up of")

Run each variant × 4 seeds = 16 textures.

**Deliverable**: Prompt-comparison contact sheet + ranking. Update
PROMPT_COOKBOOK with the winning patterns.

**Estimate**: ~1 hour compute + 30 min writeup.

### A.4 — Settings sweep

Pick one stable prompt (a known-good one like wgv3_dirt's). Vary:
- variants: 4, 6, 8
- heal_strength: 0.25, 0.35, 0.45
- delight: 0.3, 0.4, 0.5

Full grid is 27 combinations × 1 prompt × 1 seed = 27 textures. Too
many. Pick **3 axes × 2 values each = 8 combinations** (a 2³ partial
design).

**Deliverable**: 8-cell contact sheet. Identify which axis matters
most. Update PIPELINE.md preset defaults if anything wins big.

**Estimate**: ~1 hour compute + 30 min review.

### A.5 — External research

**Not generation**, just reading. Spend ~2 sessions on:
- Reddit (r/StableDiffusion, r/comfyui, r/proceduralgeneration)
  searching for "tileable PBR", "seamless texture", "FLUX texture
  workflow"
- ComfyUI workflow shares (civitai, openart.ai) — find at least 2
  saved workflows that target tileable PBR and try them out
- GitHub: search "tileable diffusion" / "PBR generation"
- Hugging Face: any PBR-specific models beyond StableMaterials

**Deliverable**: `pipelines/textures/EXTERNAL_TECHNIQUES.md`
documenting what we found, with links and one-line summaries. At
least one technique adopted into our pipeline as a try-it-out.

**Estimate**: ~3-4 hours of reading + light experiments. The agent's
ability to search Reddit is iffy; mostly WebSearch + WebFetch on
known good URLs.

### A.6 — Apply learnings

Regenerate the 2-3 currently-weakest textures (likely tundra_ice,
desert_canyon_rock, anything else flagged) with the best patterns
from A.2-A.5. Measure: did first-pass quality improve?

**Deliverable**: regenerated textures, updated DECISIONS entry, and a
"before/after" comparison capture in
`world3/docs/captures/phase_a/before_after/`.

**Estimate**: 30-60 min.

## Out of scope this phase

- New shader features
- New biome kits beyond what we have (wait until Phase D)
- Multi-tile streaming
- Iso/topdown camera changes
- LOD

## Exit criteria

- `experiment.py` runs and produces useful contact sheets
- 5 same-prompt sweeps + 1 prompt-permutation sweep + 1 settings
  sweep, all archived
- `EXTERNAL_TECHNIQUES.md` exists with at least 5 documented
  approaches and one tried in our pipeline
- `PROMPT_COOKBOOK.md` doubled in length (more known-good patterns,
  more known-bad anti-patterns)
- 2-3 weakest textures regenerated and visibly improved

## After this iteration

Phase B (upscaling research) is the natural follow-on — many of the
external techniques in A.5 will involve upscaling, so we'll already
have context.

## OpenTopo Branch Addendum - 2026-05-07

The OpenTopo work is now a live exploratory branch alongside texture-pipeline
R&D. Current direction:

1. Review the generated Phase 2 HD/MAX single-tile scenes from Guadalupe
   Cypress at 4096, 8192, and 16K RGB-only stress scale.
2. Use that scene to find the close-up failure point: texture resolution, mesh
   spacing, missing material detail, or all three.
3. Prototype baked ground textures from the same orthophoto/fused layers.
4. If the HD single-tile test is promising, move to chunked delivery instead of
   trying to make one giant texture carry a whole map.
5. Run the planned 4-call `USGS1m` scale test after preflight validation, then
   layer point-cloud/color/canopy sources over the stitched height mosaic.

Planning doc:

```text
docs/OPENTOPO_TEXTURE_SCENE_ROADMAP.md
docs/OPENTOPO_PHASE2_HD_REVIEW.md
docs/OPENTOPO_PHASE2_MAX_REVIEW.md
docs/OPENTOPO_LARGE_4CALL_PLAN.md
```

This branch should keep following the OpenTopo documentation rule: every new
tool, workflow, scene, or generated stack gets a runbook/status update.
