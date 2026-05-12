# Feature — Texture Pipeline (prompt → PBR set)

> The W4-owned texture pipeline. Takes a text prompt + slot category,
> produces a clean tileable PBR set (albedo, normal, roughness, AO,
> height, metallic) ready to drop into a biome material binding.
> If code drifts from this doc, the code wins — file an update.
>
> For why-the-architecture see `../plans/TEXTURE_PIPELINE_FINDINGS_2026_05_12.md`.
> For artifact-debug lookup see `../reference/PITFALLS.md`.

## What this feature is

W4 owns its own texture pipeline at `pipeline/textures/` (the `tx_*`
modules). It replaces the shared infra at `D:/assets/pipelines/textures/`
for W4 use, while still reusing some of that infra's pure functions
(seamless FLUX generation, delight, derive_pbr_v2 helpers, the SM
backend wrapper).

The pipeline is designed for terrain textures viewed in three modes
simultaneously — 3D close-up, 2.5D oblique, top-down distance. Quality
bar is *terrain readability*, not isolated-square aesthetics.

## Pipeline shape

```
prompt
  ↓
[Stage 1] tx_seamless        4-pass FLUX (text2img → offset → heal → reverse)
[Stage 1] tx_variant_select  Generate N variants, rank by composite, keep all
  ↓
[Stage 2] delight            LAB-blur subtract @ strength 0.4
  ↓
[Stage 3] tx_pbr_hybrid      SM tileable pass (albedo only) + derive_pbr_v2 for PBR maps
  ↓
[Stage 4] tx_seam_repair     Conditional PatchMatch (rarely triggers)
  ↓
[Stage 5] tx_qa              4 gating checks + advisory metrics
  ↓
manifest.json + canonical maps + variants/
```

The key non-obvious thing: **Stage 3 is hybrid by design**. StableMaterials
produces a tileable albedo (its `tileable=True` diffusion is what closes
the midline seam that FLUX's 4-pass heal leaves behind); we discard SM's
derived PBR maps and use `derive_pbr_v2` to build height/normal/roughness/AO
from the SM-cleaned albedo. This gives us SM's tileability without SM's
"soft-everything" PBR.

## How to use it

### Run the full diversity batch on a biome

```bash
cd "D:/assets/world 4"
python pipeline/diversity_run.py --biome alpine
```

Reads `pipeline/biomes/alpine.yaml`, generates every slot × candidate,
writes to `the world 4/candidates/<biome>/<slot>/<NN>_<tag>/`. Per-slot
`_index.json` tracks grade + status. Per-candidate `manifest.json`
records every pipeline stage. Builds contact sheets for review.

### Run a single material

```bash
python pipeline/textures/tx_pipeline.py \
    --prompt "tileable seamless texture, fresh wind-packed snow, overhead perspective" \
    --id my_test \
    --out-dir "D:/tmp/my_test" \
    --category Snow \
    --variants 4
```

### Build / rebuild contact sheets

```bash
python pipeline/build_contact_sheet.py --biome alpine
python pipeline/build_contact_sheet.py --biome alpine --grade-filter B C D  # rejects only
```

### Surface flagged candidates for review

```bash
python pipeline/diversity_review.py --biome alpine
```

Lists every below-A candidate with metric breakdown + reason. Cross-check
against the contact sheets to confirm the grader agrees with your eye.

## Defaults (locked 2026-05-12)

In `tx_pipeline.PipelineSettings`:

```python
size = 1024
variants = 4
heal_denoise = 0.35       # Flux2Scheduler ignores; informational
heal_mode = "flux_heal"
delight_strength = 0.4
pbr_backend = "hybrid"
seam_repair = True
```

These came from a 16-combo audit experiment + diagnostic chain
documented in `../plans/TEXTURE_PIPELINE_FINDINGS_2026_05_12.md`.
Don't change them without re-running the validation set.

## QA grading

`tx_qa.py` runs 5 checks; **4 of them gate the A-D grade**, 1 is advisory:

| Check                | Gating | What it measures                                                 |
|----------------------|--------|------------------------------------------------------------------|
| `edge_continuity`    | yes    | 1-pixel wrap-edge MSE                                            |
| `junction_visibility`| yes    | LoG energy at 2x2 tile seam vs interior                          |
| `periodic_artifact`  | yes    | FFT peak-locality (sharp lattice signature)                      |
| `mip32_stdev`        | yes    | luminance stdev at 32px mip (does it vanish at terrain distance?)|
| `richness`           | advisory | Content presence; SM-output legitimately low                    |
| `tile_4x4_lattice`   | advisory | 4x4 mosaic periodic check (too noisy to gate on)              |

Grades: A = all 4 gate-checks pass, B = 3 pass, C = 2, D = ≤1.

Per-category thresholds in `tx_qa.W4_CATEGORY_OVERRIDES`. Calibration
notes for each threshold live in that file's comments.

## Layout

```
pipeline/
  textures/                          ← W4-owned texture pipeline
    tx_seamless.py                   ← 4-pass FLUX
    tx_variant_select.py             ← composite-score ranking
    tx_pbr_hybrid.py                 ← DEFAULT PBR backend
    tx_pbr_derive.py                 ← alt: heuristic-only
    tx_pbr_sm.py                     ← alt: pure StableMaterials
    tx_seam_repair.py                ← PatchMatch fallback (rarely triggers)
    tx_qa.py                         ← grading + advisory metrics
    tx_pipeline.py                   ← orchestrator
    experiment_audit_matrix.py       ← reproducibility of audit experiment
    README.md                        ← code-side quick reference
  biomes/
    alpine.yaml                      ← per-biome prompt set
    desert.yaml                      ← (not yet created)
    ...
  diversity_run.py                   ← biome × slot × candidate driver
  diversity_review.py                ← surface below-A candidates
  diversity_migrate.py               ← one-shot migration tool (used once)
  build_contact_sheet.py             ← per-slot grid review

the world 4/
  candidates/<biome>/<slot>/<NN>_<tag>/
    albedo.png  normal.png  roughness.png  ao.png  height.png  metallic.png
    qa.json
    manifest.json
    prompt.txt
    variants/                        ← all N raw FLUX outputs
      v0_albedo.png  v1_albedo.png  ...
      ranking.json
  candidates/<biome>/<slot>/_index.json
  candidates/<biome>/<slot>/_contact_sheet.png
  materials/biome_<biome>/<slot>/    ← winners get promoted here
```

## Promotion flow (candidate → biome material)

The diversity batch produces *candidates*. Promotion to a shipped biome
material is a manual review step:

1. Open `candidates/<biome>/<slot>/_contact_sheet.png` — review the
   pool visually.
2. (Optional) `python pipeline/diversity_review.py --biome <biome>` to
   list every below-A candidate with reasons. Spot-check.
3. Pick one candidate per slot.
4. Copy `albedo/normal/roughness/ao.png` into
   `the world 4/materials/biome_<biome>/<slot>/`.
5. Rebuild biome arrays in scale_demo and verify in editor.

(There isn't a `promote_candidate.py` script yet — manual copy is fine
for now. Build it if we end up promoting often.)

## What's intentionally not here

- **External seam_repair as default.** Disabled because hybrid cleans
  the seam already. Stays as opt-in fallback.
- **`tile_4x4_lattice` as a gating metric.** Calibration showed it's
  too noisy — single-image `periodic_artifact` separates good from bad
  better.
- **Writes to the shared catalog** (`D:/assets/world/textures/catalog/`).
  W4 owns its own indices. Promotion is the boundary where catalog
  writes would happen — not implemented yet.

## Revisit triggers

This pipeline locks defaults for the alpine biome work. Revisit when:

- A new biome category needs different QA thresholds (wetland probably
  behaves like Snow).
- A new FLUX checkpoint replaces klein-9B. The scheduler dance is
  klein-9B-specific.
- Visual quality of A-grade outputs starts diverging from the metric
  — recalibrate thresholds against fresh visual signal.
- A future texture model with built-in tileability replaces SM. At
  that point the hybrid pattern becomes unnecessary.
