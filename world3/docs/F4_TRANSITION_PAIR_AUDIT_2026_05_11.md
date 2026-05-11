# Phase F.4 — Catalog-time transition pair audit

> The high-leverage one. For every allowed biome-pair in a world
> plan, audit at catalog time whether the two biomes' primary
> materials will blend cleanly at a seam band. Verdict per pair
> with an actionable `recommended_action`: `palette_lock`,
> `regenerate`, `shader_blend_band`, or `none`. The starter 5×5
> plan's first audit landed **7 fails + 1 warn out of 8 pairs** —
> exactly the kind of finding F.4 is built to catch *before*
> 25 procedural bundles get built on a broken catalog.

## Verdict

**F.4 ships catalog-time transition diagnostics with actionable remediation guidance.** The audit catches blend-quality issues *before* compute is spent on a tiled world. Soft-gated into `world_plan_to_bundles.py` for now (surfaces summary, doesn't block emission) until catalog remediation work clears the existing fails — the starter catalog **fails 7 of 8 declared adjacency pairs**, which is the exact problem F.4 is supposed to identify and which deferred catalog work will fix.

## What shipped

### Audit script

**`world3/pipeline/audit_transition_pairs.py`** — argparse CLI taking a
world plan. For each pair in `adjacency_rules.allowed_pairs`:

1. Load each biome's `primary_material_id` albedo from `world3/textures/wgv3/<id>/albedo.png`
2. Tile each to `512×1024` (matches procedural bundle convention)
3. Compute four diagnostic metrics:

| Metric | What it measures | Caught by |
|---|---|---|
| `palette_delta_lab` | CIE Lab distance between median colors | Color-clash mismatches |
| `luminance_range_delta` | Diff of p95-p5 luminance ranges | Bright-vs-dark mismatches |
| `high_freq_energy_ratio` | Ratio of high-freq band energy (max/min) | Sharp-vs-smooth texture mismatch |
| `seam_band_internal_max_delta_rgb01` | Max RGB delta inside the simulated blend band | Runtime-visible seam |

4. Threshold each metric into pass/warn/fail. Map the dominant failing
   metric to a `recommended_action`:
   - `palette_lock` — palette mismatch dominates → cross-material palette work
   - `regenerate` — luminance range or frequency badly off → rebuild material
   - `shader_blend_band` — runtime-mitigatable wider seam band
   - `none` — pass

5. Write `world3/jobs/transition_audits/<plan_id>.json` with full
   diagnostic metrics + per-pair verdicts + action recommendations.

Flags:
- `--strict` — exit 1 if any pair fails
- `--json` — emit the audit doc to stdout in addition to file write

### Soft gate in plan-to-bundles iterator

`world_plan_to_bundles.py` now checks for a transition audit at
`world3/jobs/transition_audits/<plan_id>.json`. If present, the
iterator prints the summary (pass/warn/fail/error counts) and a
WARN message when fails exist, but **does not block emission**.

This is intentional: the existing catalog can't clear F.4 yet, and
gating the world build on a fresh-catalog audit would block all
current testing. Hard-gating is queued for F.4.1 (deferred) once
catalog remediation (F.5 + texture pipeline iteration) lands.

## Validation

### 5×5 starter plan — eight declared pairs

```
$ python world3/pipeline/audit_transition_pairs.py \
    world3/jobs/examples/world_plan_starter_5biome_procedural.json

  [FAIL] tundra            <-> grassland         action=palette_lock     (tundra_moss <-> grassland_grass)
  [FAIL] tundra            <-> alpine            action=regenerate       (tundra_moss <-> rock_dark)
  [FAIL] alpine            <-> grassland         action=regenerate       (rock_dark <-> grassland_grass)
  [FAIL] alpine            <-> temperate_forest  action=regenerate       (rock_dark <-> temperate_forest_grass)
  [WARN] alpine            <-> desert            action=palette_lock     (rock_dark <-> desert_canyon_rock)
  [FAIL] temperate_forest  <-> desert            action=shader_blend_band (temperate_forest_grass <-> desert_canyon_rock)
  [FAIL] temperate_forest  <-> tundra            action=shader_blend_band (temperate_forest_grass <-> tundra_moss)
  [FAIL] desert            <-> grassland         action=shader_blend_band (desert_canyon_rock <-> grassland_grass)

--- Summary ---
  pass=0 warn=1 fail=7 error=0
  written: world3\jobs\transition_audits\starter_5biome_procedural.json
```

**The single warning is alpine ↔ desert** — both are rocky materials,
relatively close in palette and frequency. That's a correct physical
intuition the audit landed on its own.

**The pattern of fails is also diagnostic-correct:**
- `rock_dark` (alpine) has high-frequency energy 6-9× higher than soft
  biomes (moss, grass) — F.4 flags this as `regenerate` because it's
  a fundamental material-character mismatch, not a runtime-mitigatable
  seam issue.
- Forest↔tundra and desert↔grassland fail on max-band-delta only —
  palette and frequency OK, just visible seam color steps. F.4 flags
  these as `shader_blend_band` (runtime mitigation is the cheapest fix).
- Tundra↔grassland fails on palette — `palette_lock` recommended.

This is exactly the actionable, per-pair, machine-readable verdict
F.4 was designed to produce.

### 2×2 single-biome plan — zero pairs to audit

```
$ python world3/pipeline/audit_transition_pairs.py \
    world3/jobs/examples/world_plan_starter_2x2_procedural.json

Plan: starter_2x2_procedural  (0 allowed pairs)
--- Summary ---
  pass=0 warn=0 fail=0 error=0
```

Graceful no-op when there are no cross-biome adjacencies.

### Strict mode

```
$ python world3/pipeline/audit_transition_pairs.py <5x5_plan> --strict
... (full output)
$ echo $?
1   # 7 fails caught the --strict gate

$ python world3/pipeline/audit_transition_pairs.py <5x5_plan>
... (same output)
$ echo $?
0   # non-strict default: audit is diagnostic, doesn't fail the run
```

### Soft gate in iterator

```
$ python world3/pipeline/world_plan_to_bundles.py <5x5_plan> --dry-run
...
--- Validating plan ---     [OK]
--- Transition audit (world3\jobs\transition_audits\starter_5biome_procedural.json) ---
  pass=0 warn=1 fail=7 error=0
  WARN: 7 pair(s) failed audit but emit proceeding (soft gate).
        Run audit_transition_pairs.py to see actionable remediation.
--- Dry run ---
  [tile [0, 4]] biome=tundra ...
```

The iterator surfaces the audit summary so anyone running F.3
sees the F.4 verdict in their normal output stream. No silent failure mode.

## What the F.4 results tell us about the catalog

The 7-fail-out-of-8 result is **not an F.4 bug**. It's an accurate
diagnosis: the Phase F starter catalog wasn't authored with
biome-pair-blend in mind. Each material was authored individually
through `aaa_texture.py` for tile quality, not for cross-material
coherence.

Three classes of remediation will land via F.5 (catalog requisition):

1. **Palette-lock work** for tundra↔grassland and alpine↔desert
   (the palette-dominant fails): use `pipelines/textures/palette_lock.py`
   on neighboring pairs to bring median colors within ~30 Lab.
2. **Material regeneration** for alpine: `rock_dark` is too
   high-frequency for the soft biomes adjacent to it. Either
   author a smoother alpine variant (e.g. `alpine_rock_weathered`)
   or accept alpine only neighbors rocky biomes (desert, future
   tundra_rock variants).
3. **Shader blend band widening** for the three runtime-mitigatable
   fails. This is the cheapest fix and is *G.3* / *G.5* shader work,
   not catalog work — the audit flags it as runtime-mitigatable
   precisely so we don't burn catalog cycles on it.

F.5 will read the F.4 audit and prioritize regen/palette-lock work
based on its `recommended_action` field. F.4 is the input to F.5's
plan; the two phases compose.

## Six-box LLM-drivability check

| Box | Status |
|---|---|
| Schema | ⚠️ Audit output has implicit schema embedded in the script; F.4.1 will formalize as `transition_audit_schema.json` if a consumer needs it. Today only the iterator reads it and only via `.get()` defaults, so schema-less is acceptable. |
| Validator | N/A — the audit is its own validator |
| Example | ✅ `world3/jobs/transition_audits/starter_5biome_procedural.json` + `starter_2x2_procedural.json` |
| Audit | ✅ the script IS the audit |
| Closure doc | ✅ this doc |
| Stages.json | N/A — F.4 runs at world-build time, not per-bundle stage time |

The "schema" box is the only soft one and is annotated as deferred-with-rationale.

## What's NOT in F.4

- **Hard gate in `world_plan_to_bundles.py`.** Soft-gated only.
  Hard gate (refuse to emit on any fail) is queued for F.4.1
  once the catalog can clear it.
- **Catalog-state-aware audit.** Today the audit reads the raw
  albedo for each material. If two materials share a base + a
  palette-locked variant, we'd want to audit the variant when
  it exists. The schema-less audit output makes this easy to add.
- **`transition_audit_schema.json`.** Deferred — only the iterator
  reads the audit today, and only optional fields. When F.5 starts
  consuming it for requisition prioritization, formalize.
- **Threshold tuning against real-world post-render captures.**
  Current thresholds (palette 30/60 Lab, lum range 0.30/0.55,
  HF ratio 2.5/5.0, seam band 0.15/0.30) are first-pass values.
  After F.6 in-context re-audit, we'll have empirical data to
  calibrate.

## Cross-references

- Parent phase: [PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md](PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md)
- Long-arc: [WORLD3_LONG_ARC_2026_05_11.md](WORLD3_LONG_ARC_2026_05_11.md)
- Previous: [F3_PLAN_TO_BUNDLES_ITERATOR_2026_05_11.md](F3_PLAN_TO_BUNDLES_ITERATOR_2026_05_11.md)
- Reads: world plan + `world3/textures/wgv3/<id>/albedo.png`
- Emits: `world3/jobs/transition_audits/<plan_id>.json`
- Feeds: F.5 catalog requisition (deferred prioritization logic)
- Influences: F.7 streaming director (knows which pairs need wider blend bands)

## Status

- [x] `audit_transition_pairs.py` script
- [x] Four diagnostic metrics computed per pair
- [x] Verdict mapping → recommended_action
- [x] `--strict` + `--json` flags
- [x] Audit JSON written to `world3/jobs/transition_audits/<plan_id>.json`
- [x] Soft gate in `world_plan_to_bundles.py` (surfaces summary)
- [x] Smoke on 5×5 plan: 7 fails + 1 warn correctly identified
- [x] Smoke on 2×2 plan: graceful 0-pair no-op
- [x] Closure doc (this doc)

**Phase F.4 SHIP.** Catalog-time transition diagnostics live and
actionable. F.5 (catalog demand deriver + requisition runner) is
next; it will consume F.4's audit to prioritize remediation work.
