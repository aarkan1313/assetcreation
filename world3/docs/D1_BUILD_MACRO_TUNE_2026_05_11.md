# D.1 — `build_macro()` Parameter Tune

> Phase D.1 of the rebuild. Fixes the Bucket C-1 finding from Phase B.3:
> the "broad smooth tan/sand" visual veto that drove the M18 procedural
> neighbor to `conditional` status.

## Verdict

**FIXED.** Side-by-side comparison shows the new procedural macro reads as
real canyon-rock material with subtle organic variation, not as smooth
tan with diagonal wavy bands. M18 procedural-side visual veto cleared at
the macro-source level.

Comparison sheet: [`captures/review/d1_macro_tune_compare_sheet.png`](captures/review/d1_macro_tune_compare_sheet.png)

| Variant | Description | Verdict |
|---|---|---|
| v0 (baseline) | Pre-fix: catalog median color × smooth noise + 0.42 detail | smooth tan with diagonal bands; the veto |
| v1 (small tile) | Catalog texture at `width // 4` tile repeat | texture visible but tile-grid artifact |
| **v2 (large tile)** | **Catalog texture at `max_dim` tile repeat + low-amp organic wash** | **clean rock texture; no grid; subtle variation** |
| catalog reference | Raw catalog albedo for reference | reference baseline |

## Root cause (from B.3)

`build_procedural_neighbor_bundle.py:build_macro()` was constructing the
procedural macro as:

```
base = catalog_albedo.median_rgb         # COLLAPSE catalog to one color
value = 0.88 + 0.12*low + 0.055*med + 0.018*fine     # smooth noise field
color = base * value                     # smooth noise tinted by single color
color += catalog_texture_detail * 0.42   # actual texture at only 42%
color += diagonal_wash_bands             # parametric sin-based bands
```

The catalog's actual texture was being suppressed (42% strength, under
smooth value noise) in favor of a synthetic-looking smooth field with
diagonal bands. This was deliberate code; not a downstream bug.

## The fix

New `build_macro()` uses the catalog albedo **as** the texture, with
procedural variation modulating on top at low amplitudes:

```python
def build_macro(material, width, height, seed):
    albedo_path = resolve_repo_path(material["pbr_maps"]["albedo"])

    # Tile catalog texture at output's max dimension so grid artifact
    # is invisible (catalog repeats ~1-2× across macro, not ~32×).
    tile_repeat_px = max(width, height)
    base_texture = tiled_detail(albedo_path, width, height, tile_repeat_px, seed + 31)

    # Large-scale procedural variation (no parametric sin bands).
    low = smooth_noise(width, height, 220, seed + 11)
    med = smooth_noise(width, height,  72, seed + 17)
    wash_field = low * 0.6 + med * 0.4
    wash_signal = np.clip(wash_field - 0.45, 0, 1) * 1.4  # organic patches

    # Multiplicative ±6% value modulation (catalog stays dominant).
    value = 0.97 + low * 0.05 + med * 0.02
    color = base_texture * value[:, :, None]

    # Additive organic tints (low amplitude).
    color += wash_signal[..., None] * np.array([0.025, 0.015, 0.004])
    color += (1.0 - y[..., None]) * np.array([0.012, 0.006, -0.002])

    return np.clip(color, 0, 1)
```

Key changes vs old `build_macro()`:

1. **Catalog texture is the base, not a 42% additive overlay.** Median-color
   collapse removed.
2. **Tile repeat = `max(width, height)`** instead of `width // 4`. Catalog
   tiles ~1× across the macro, so the tile grid is invisible.
3. **Wash bands switched from parametric sin to noise-driven organic
   patches.** No more diagonal stripes.
4. **All procedural amplitudes reduced** (value ±6% vs ±15%, wash 2.5%
   vs 5.5%, vertical tint 1.2% vs 2.5%) so catalog reads dominantly.
5. **Removed `fine` noise channel.** Fine detail now comes from the
   catalog texture itself, not from smooth-noise.

## Downstream cascade

Changing `build_macro()` changes the byte-content of every procedural
macro generated. Affected artifacts:

### Directly affected
- `world3/toporeview/procedural_desert_canyon_rock_m10/layers/render_albedo.png` —
  regenerated as part of D.1
- `world3/toporeview/procedural_desert_canyon_rock_m10/heightmap.png` —
  byte-identical (heightmap code unchanged)

### Indirectly affected (rendered captures that consumed the old macro)
- M10 real-to-procedural seam-integration proof captures
- M18 representative slice captures (the ones that triggered the veto)
- Any M14 / M16 / M17 capture that included this region

### M13 promotion gate state
Entries in `world3/jobs/production_promotion_candidates.json` that
reference these bundles or captures now point to artifacts with new
content. **Specifically affected**:
- `m10_real_procedural_gloss_canyon` (cond)
- `m18_representative_slice_first_pass` (cond)

Action needed (not done in D.1; flagged for D.6 validation pass):
1. Re-render the M10 real-to-procedural seam-integration proof scene
2. Re-render the M18 representative slice scene
3. Visual review against the audit's "smooth tan/sand" criterion
4. Update gate entries if the veto is genuinely cleared
5. Add a note to the gate manifest pointing at D.1 as the macro-fix
   commit

## Confidence

**High** that the macro-level fix is correct:
- Catalog texture is now visibly present in the macro
- No tile-grid artifact at max_dim tile size
- No parametric stripe pattern
- Procedural variation reads as natural color shift, not as overlay

**Pending validation**:
- How does this render in the M18 representative slice scene? (D.6)
- Does the M10 seam-integration solver handle the new macro cleanly?
  (D.6)

These are deferred because re-rendering Godot scenes is a separate
manual step. The macro-source quality is verified; the runtime
integration will be verified in the D.6 validation pass.

## Performance impact

None. Build still completes in <1 sec. Same numpy + PIL operations,
different parameters.

## Implementation notes for future tuners

If the v2 result needs further iteration:

- **Macro looks too uniform**: increase `wash_signal` amplitude or add
  a third low-frequency noise channel
- **Macro looks too patchy**: reduce `wash_signal` threshold (line
  `np.clip(wash_field - 0.45, ...)`)
- **Tile grid visible again**: tile_repeat_px is already at `max_dim`;
  to reduce repetition further, use a non-grid blending (e.g.
  hex-tile sampler) — bigger code change
- **Wrong color**: catalog albedo determines color; check
  `materials/catalog.json` for the right material id
- **Adapt to other materials** (not just `desert_canyon_rock`): the
  tuning here was on rock. Different material types
  (grass / moss / sand) may want different amplitudes; consider per-
  category presets in a future iteration

## Cross-references

- B.3 root-cause diagnosis: [`B3_CHAIN3_VALIDATION_2026_05_11.md`](B3_CHAIN3_VALIDATION_2026_05_11.md)
- Phase C bucketing: [`PHASE_C_DIAGNOSIS_2026_05_11.md`](PHASE_C_DIAGNOSIS_2026_05_11.md)
- Phase plan: [`REBUILD_PLAN_PHASES_B_E_2026_05_11.md`](REBUILD_PLAN_PHASES_B_E_2026_05_11.md)
- Patched script: `world3/pipeline/build_procedural_neighbor_bundle.py` (function `build_macro` lines ~105-145)
- Affected bundle (regenerated): `world3/toporeview/procedural_desert_canyon_rock_m10/`
- Comparison sheet: `world3/docs/captures/review/d1_macro_tune_compare_sheet.png`
- Catalog material: `world3/textures/wgv3/desert_canyon_rock/albedo.png`
- M13 gate entries to re-review: `m10_real_procedural_gloss_canyon`, `m18_representative_slice_first_pass`

## Phase D.1 status

- [x] Read existing `build_macro()` and identified root cause
- [x] Wrote new `build_macro()` with catalog texture as base
- [x] v1 iteration (small tile) — too much grid artifact
- [x] v2 iteration (large tile + organic wash) — passed visual review
- [x] Regenerated actual M10 procedural neighbor bundle with new code
- [x] Verified determinism (re-run produces identical output)
- [x] Comparison sheet generated + saved
- [x] Documented fix + downstream cascade
- [ ] D.6: re-render Godot scenes that consumed old macro (deferred)
- [ ] D.6: update M13 gate entries (deferred)

**D.1 COMPLETE.** Cleanup of /d/tmp/d1_macro_tune/ can wait until D.6
validation, since the v0/v1/v2 outputs may be useful reference.
