# W4 Texture Pipeline — Findings + Diagnostic Record — 2026-05-12

> **Canonical "this is the W4 texture pipeline" doc:** `../features/textures.md`.
> This doc is the diagnostic record — *why* the pipeline is the way it
> is. For operational reference (how to use it, layout, commands), go
> to the features doc. This doc is kept so future-us understand the
> reasoning chain that led to the current defaults.

After the audit, two experiments, and a diagnostic chain that overturned
most of the audit's predictions, this is the locked-in W4 texture
pipeline. **The audit was wrong on every prediction except one** (pbr=sm
producing maps inconsistent with albedo at terrain distance). Each
wrong prediction taught us something concrete about why upstream's
pipeline was working.

## The pipeline as it ships (locked in `pipeline/textures/`)

```
prompt
  ↓
[Stage 1] tx_seamless        4-pass FLUX (text2img → offset → Flux2Scheduler heal → reverse)
[Stage 1] tx_variant_select  Generate N variants, rank by composite, keep all
  ↓
[Stage 2] delight            LAB-blur subtract, strength=0.4
  ↓
[Stage 3] tx_pbr_hybrid      SM tileable-pass (albedo only) + derive_pbr_v2 (PBR maps)
  ↓
[Stage 4] tx_seam_repair     Conditional PatchMatch (rarely triggers since hybrid cleans)
  ↓
[Stage 5] tx_qa              edge + junction + periodic + mip32_stdev + advisory tile_4x4
  ↓
manifest.json + canonical maps + variants/
```

**Defaults in `PipelineSettings`:**

```python
@dataclass
class PipelineSettings:
    size: int = 1024
    variants: int = 4
    heal_denoise: float = 0.35   # Flux2Scheduler ignores; informational
    heal_mode: str = "flux_heal"
    delight_strength: float = 0.4
    pbr_backend: str = "hybrid"   # 'hybrid' / 'derive' / 'sm'
    seam_repair: bool = True
    category: str = "Rock"
```

## The diagnostic chain (how we got here)

### Audit prediction → reality

| Audit predicted | Reality | Why audit was wrong |
|---|---|---|
| `heal_denoise=0.35` honored cleans seams better than silent 1.0 | 0.35 honored leaves edge MSE>0.01; silent ignore (Flux2Scheduler) is correct | "Silently ignores denoise" doesn't mean "runs at denoise=1.0" — it means runs on klein's 4-step distilled schedule, which is mathematically different from BasicScheduler at denoise=1.0 |
| `delight=0.0` skip — prompt handles lighting | Delight matters but not for lighting reasons | (See below — delight wasn't doing the midline-fix work either) |
| `pbr=derive` swap → consistent-with-albedo PBR | True PBR-side but exposed a hidden bug | SM's `tileable=True` diffusion was *also* the midline-seam closer; removing it broke seam quality |
| `seam_repair=False` — "duplicate work with FLUX heal" | seam_repair fixes the WRAP edge (closes ratio 167→84) but doesn't fix the midline | Audit conflated wrap and midline; they're different seams from different ops |

### What was actually happening

The shipped texture (`materials/biome_alpine/ground/albedo.png`) had midline ratio 1.30/1.53 (clean). The new pipeline output had ratio 22.10/16.18 (catastrophic) despite all the same FLUX/delight/seam_repair stages.

**The single difference:** shipped used `pbr=sm` with `tileable=True`. SM runs a fresh tileable diffusion pass which incidentally regenerates the albedo as a clean tileable image. **SM was the seam closer the whole time** — silently, as a side effect of its actual job.

### The fix

`tx_pbr_hybrid.py`: use SM for the tileability pass (keep only its albedo, discard its derived PBR), then run `derive_pbr_v2` on the SM-cleaned albedo to produce maps that are mathematically consistent with the cleaned albedo.

This is honest engineering: name what SM is doing (tileability cleanup), keep that, discard what it's bad at (terrain-soft derived PBR), use the right tool for the rest.

## Validation: 5-prompt sanity run

Ran the new hybrid pipeline on 5 prompts spanning the failure space:

| id | grade | midline ratio | notes |
|---|---|---|---|
| snow_windpack    | A | 1.32 / 1.56 | matches shipped (1.30/1.53) |
| snow_old_drift   | C | 1.65 / 1.69 | midline clean; fails periodic (prompt is inherently periodic) |
| snow_mid_lichen  | A | 1.18 / 2.72 | borderline Y ratio but absolute MSE small |
| rock_dark_slate  | A | 1.29 / 1.92 | clean |
| rock_granite     | A | 1.50 / 1.90 | clean |

**Zero midline-seam failures across all 5 outputs.** Compare to the
broken pipeline's 16-22 ratios. The seam fix holds.

The one C grade is `snow_old_drift` and it's the grader doing its job
correctly — the prompt asks for a "dune shape" which IS a periodic
structure, so periodic_artifact correctly rejects it.

## Calibrated QA thresholds

After this session's empirical work, the `tx_qa` per-category
overrides (effective values):

| Category | periodic_artifact | mip32_stdev | Notes |
|---|---|---|---|
| Snow     | 13.0 | 6.0 | shipped reference at 7.14 |
| Sand     | 13.0 | 6.0 | same character as Snow |
| Mixed    | 13.0 | 10.0 | rocky+snow mids in alpine |
| Rock     | 25.0 | 8.0 | granite at 8.6 / dark slate at 13.5 both visually pass |
| Concrete | 25.0 | 8.0 | inherit Rock |

`tile_4x4_lattice` is computed but **advisory only** (calibration on
16 alpine grounds showed it doesn't separate good from bad better than
the single-image `periodic_artifact` does — too noisy to gate on).

## Module inventory

`pipeline/textures/`:

| Module | Purpose | Notes |
|---|---|---|
| `tx_seamless.py` | 4-pass FLUX | Heal uses Flux2Scheduler (matches upstream behavior that produces clean shipped output) |
| `tx_variant_select.py` | Generate N variants, composite-score | Keeps ALL variants on disk for review |
| `tx_pbr_hybrid.py` | **DEFAULT** PBR backend | SM tileable pass (albedo only) → derive_pbr_v2 for PBR maps |
| `tx_pbr_derive.py` | Heuristic-only backend | For fast iteration when seam fix not needed |
| `tx_pbr_sm.py` | Pure SM backend | Still available; fails mip32 on terrain-soft |
| `tx_seam_repair.py` | PatchMatch over offset cross | Mostly redundant now that hybrid cleans seams; keep as fallback |
| `tx_qa.py` | 4-check grader + palette advisory | Includes new W4-specific mip32_stdev |
| `tx_pipeline.py` | Orchestrator | Replaces aaa_texture.py for W4 |
| `experiment_audit_matrix.py` | 16-combo audit experiment | Run-history; kept for reproducibility |

## Stuff that's NOT in this pipeline (intentionally)

- **External seam_repair as default** — disabled because hybrid cleans
  the seam already. Stays as opt-in fallback.
- **Tile-4x4 as gating metric** — advisory only; too noisy.
- **The audit's 16-combo experiment outputs** — kept under
  `candidates/_pipeline_review/audit/` as historical record of how
  far off-base the audit was, but those outputs all have visible
  midline seams; don't promote any of them.

## Workflow record (what to actually do when generating textures)

### To run the full diversity batch on a biome

```bash
cd "D:/assets/world 4"
python pipeline/diversity_run.py --biome alpine
```

Defaults: hybrid backend, 4 variants per slot, 1024px, delight 0.4,
heal_denoise 0.35 (ignored by Flux2Scheduler), seam_repair on.

### To override one knob for a specific run

```bash
python pipeline/diversity_run.py --biome alpine --slots ground --variants 6
python pipeline/diversity_run.py --biome alpine --pbr-backend derive  # fast iter, no seam fix
```

### To run a single material outside the diversity batch

```bash
python pipeline/textures/tx_pipeline.py \
    --prompt "tileable seamless texture, ..." \
    --id my_test \
    --out-dir "D:/tmp/my_test" \
    --category Snow \
    --variants 4
```

### To re-render contact sheets after a batch

```bash
python pipeline/build_contact_sheet.py --biome alpine
python pipeline/build_contact_sheet.py --biome alpine --grade-filter B C D  # rejects only
```

### To run the audit experiment again (16-combo on windpack)

```bash
python pipeline/textures/experiment_audit_matrix.py
```

Already-completed combos are detected and skipped.

## Lessons learned

1. **Trust the shipped artifact.** When we have an existing
   visually-clean texture, comparing against it numerically (column
   MSE around midline) immediately diagnoses what's broken in the new
   pipeline. Should have done this before turning off SM.

2. **"Silently ignored" parameter ≠ "ran at 1.0".** When upstream said
   Flux2Scheduler ignores `denoise`, the audit interpreted it as
   "ran at full denoise." Actually it means "ran the distilled
   schedule which doesn't use a denoise parameter." A different
   computation entirely.

3. **Side effects matter more than intent.** SM's job is image-to-PBR.
   Its side effect (tileable albedo cleanup) was load-bearing.
   Removing it broke the pipeline in a way nobody knew SM was
   responsible for. **Document side effects, not just intent.**

4. **Audit predictions are hypotheses, not conclusions.** All four
   audit-proposed defaults were wrong. The audit was still useful —
   it forced the experiments that revealed the actual mechanism. But
   labeling audit recommendations as "decisions to lock in" was
   premature.

5. **Mid32_stdev is a more honest metric than tile_4x4** for the
   "vanishes at distance" failure mode. tile_4x4's signal is
   dominated by tile-boundary harmonics that exist regardless of
   content quality; mip32_stdev directly measures "is there content
   at this size."

## Revisit triggers

This pipeline locks in defaults that should hold for the alpine
diversity batch. Revisit if:

- A new biome's category needs different thresholds (probably
  Wetland — wet, low-frequency, may behave like Snow).
- We add a different FLUX checkpoint (klein-1B? other models?). The
  scheduler dance was klein-9B-specific.
- The visual quality of A-grade outputs starts diverging from the
  metric — recalibrate thresholds against new visual signal.
- A future texture model with built-in tileability replaces SM.
  At that point the hybrid pattern becomes unnecessary.
