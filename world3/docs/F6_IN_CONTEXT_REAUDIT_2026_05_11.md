# Phase F.6 — In-context material re-audit

> Closes the audit loop: catalog (F.4 static metrics on tiled albedo)
> → runtime (F.6 metrics on rendered iso capture) → drift verdict.
> Each biome in a world plan gets re-captured through the E.4
> orchestrator capture driver and re-scored on the same metric basis
> so we can flag when **rendered output diverges from on-disk albedo**.

## Verdict

**F.6 ships the catalog→runtime audit bridge.** Catalog-time
diagnostics (F.4) measure what materials look like as flat
albedos. F.6 measures what they look like after shader + lighting
+ scatter + tour-camera framing. Drift between the two is its
own diagnostic — first audit on the 5×5 starter shows every biome
has measurable rendered drift (2 warn, 3 fail) because the
runtime stack legitimately transforms appearance.

## What shipped

### Audit script

**`world3/pipeline/audit_materials_in_context.py`** — argparse CLI
taking a plan. For each biome:

1. Find first tile in the F.3-built world map that uses this biome
2. Drive `run_orchestrator_capture.py` (E.4) on that tile in iso
   mode with the biome's `.tres` material + `photoreal` style pack
3. Load a center 512×512 patch from the captured PNG (avoids HUD
   overlay + framing edges)
4. Compute the same three F.4 metrics on the rendered patch:
   - `median_lab` (CIE Lab median color)
   - `luminance_range` (p95-p5 of luminance)
   - `high_freq_energy` (mean of 3x3 box-blur residual)
5. Compute the same metrics on the catalog albedo (raw `.png` from `world3/textures/wgv3/<id>/albedo.png`)
6. Classify drift:
   - `palette_drift_lab` ≥ 20 (warn) / ≥ 40 (fail)
   - `lum_range_drift` ≥ 0.2 (warn) / ≥ 0.4 (fail)
   - `high_freq_ratio` ≥ 2.0 (warn) / ≥ 4.0 (fail)

Output: `world3/jobs/in_context_audits/<plan_id>.json` with per-biome
catalog metrics, rendered metrics, verdict, and notes.

Flags:
- `--skip-render` — reuse existing in_context_*.png captures
- `--json` — emit doc to stdout

## Validation

```
$ python world3/pipeline/audit_materials_in_context.py \
    world3/jobs/examples/world_plan_starter_5biome_procedural.json

Plan: starter_5biome_procedural
Biomes: 5

  [WARN] tundra             (tundra_moss)              tile=[0, 4]
           - palette drift Lab=37.5
  [FAIL] alpine             (rock_dark)                tile=[1, 3]
           - palette drift Lab=79.1
           - luminance range drift=0.45
  [FAIL] grassland          (grassland_grass)          tile=[2, 4]
           - palette drift Lab=31.5
           - luminance range drift=0.46
           - high-freq energy ratio=4.59
  [WARN] temperate_forest   (temperate_forest_grass)   tile=[0, 2]
           - palette drift Lab=37.2
  [FAIL] desert             (desert_canyon_rock)       tile=[3, 1]
           - palette drift Lab=34.0
           - luminance range drift=0.32
           - high-freq energy ratio=5.15

--- Summary ---
  pass=0 warn=2 fail=3 error=0
```

All 5 biomes captured (5 PNGs under
`world3/docs/captures/review/in_context_starter_5biome_procedural_*_iso.png`),
all metrics computed, zero render errors.

The pattern of drift is itself the headline finding:
- **Palette drift is universal** (30-80 Lab) across every biome.
  The shader stack significantly transforms median color (lighting +
  tonemap exposure + ambient + scatter overlay).
- **Alpine drifts the most** (79 Lab) because `rock_dark` is a
  high-contrast material that the photoreal style's tonemapping
  pushes hard.
- **Tundra + temperate_forest pass on luminance + high-freq** — their
  soft materials translate to rendered output more cleanly than
  alpine's sharp-rock or grassland's high-detail.
- **Three fails are correctly classified by their dominant metric**:
  alpine = palette + lum, grassland = all three, desert = lum + hf.

This is not "the catalog is broken." It's "rendered output is a
function of catalog × runtime, and F.6 measures both." Thresholds
will tune as we accumulate more rendered observations.

## What the F.4+F.6 combination tells you

| Stage | Catches |
|---|---|
| F.4 | "These two materials don't blend cleanly" (palette/freq/lum mismatch between biomes) |
| F.6 | "This material looks different rendered than on disk" (catalog/runtime drift within one biome) |

Together they cover:
- Pre-build: F.4 catches catalog gaps that runtime can't fix
- Post-build: F.6 catches runtime drift that catalog audits miss
- Per-pair (F.4) + per-biome (F.6) views of the same catalog give
  two independent diagnostic axes

## Six-box LLM-drivability check

| Box | Status |
|---|---|
| Schema | ⚠️ Implicit in script (output JSON shape) — same precedent as F.4/F.5 |
| Validator | N/A — audit IS the validator |
| Example | ✅ `world3/jobs/in_context_audits/starter_5biome_procedural.json` + 5 capture PNGs |
| Audit | ✅ this script |
| Closure doc | ✅ this doc |
| Stages.json | N/A — plan-level tool |

## What's NOT in F.6

- **Adjacent-biome seam-band captures.** F.6 v1 only renders each
  biome's own iso view. Capturing the same material in adjacent
  biomes' seam-band views (F.6.1) is heavier and lands when seam
  framing is reliable enough to make the captures meaningful.
- **Multi-perspective re-audit.** F.6 only renders iso. Walk + topdown
  + 2.5D re-audits land in G.5 (per-mode quality bars at gate time).
- **Drift threshold calibration.** Current thresholds are first-pass
  values. After H.6 conformance suite gives a baseline, tune.
- **Schema formalization.** Same deferred precedent as F.4/F.5.
- **Reading drift into F.5 work_queue.** F.5a only consumes F.4
  results today. When F.6 is reliable, F.5a should also penalize
  materials with high rendered drift; deferred until thresholds tune.

## Cross-references

- Parent phase: [PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md](PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md)
- Long-arc: [WORLD3_LONG_ARC_2026_05_11.md](WORLD3_LONG_ARC_2026_05_11.md)
- Previous: [F5_CATALOG_REQUISITION_2026_05_11.md](F5_CATALOG_REQUISITION_2026_05_11.md)
- Reads: world plan + world_map.json + catalog albedos
- Drives: `run_orchestrator_capture.py` (E.4)
- Emits: `world3/jobs/in_context_audits/<plan_id>.json` + 5 capture PNGs

## Status

- [x] `audit_materials_in_context.py` script
- [x] Three drift metrics (palette / luminance range / HF energy ratio)
- [x] E.4 orchestrator capture driver integration
- [x] 5×5 smoke (5 biomes captured + scored, 0 errors)
- [x] `--skip-render` + `--json` flags
- [x] Audit JSON written to `world3/jobs/in_context_audits/`
- [x] Closure doc (this doc)

**Phase F.6 SHIP.** Catalog→runtime drift now measurable per biome.
F.7 (multi-bundle streaming director) is next — the big one.
