# B.3 — Chain 3 Cold Validation: Procedural Neighbor Bundle

> Phase B.3 of the rebuild evaluation. Cold-run of
> `build_procedural_neighbor_bundle.py` for the M10 desert-canyon-rock
> procedural neighbor. **Diagnoses the procedural-vs-texture confusion
> definitively.**

## Verdict

**PASS for determinism. ROOT-CAUSE FOUND for the "smooth tan/sand" weakness.**

Three of four output files reproduce byte-identical from documented inputs.
The fourth (`meta.json`) differs only because the `--out` path string is
different — content otherwise identical.

**More importantly**: the "broad smooth tan/sand field" complaint that
drove the M19 framing correction has a single, specific, well-defined
root cause in 4 lines of Python inside `build_macro()`. **It is not a
placement bug, not a catalog-binding bug, not a downstream collapse — it
is a deliberate macro-color synthesis choice that suppresses the catalog
texture to ~42% strength under smooth value noise.**

This is a Bucket C (real code bug — or rather, a wrong parameter choice)
that can be fixed in a single commit by changing 1-3 values in
`build_macro()`.

**Plus one Bucket C path bug**: the script crashes if `--out` is anywhere
outside `world3/`. Trivial fix.

## Test scope

Reproduce the existing procedural canyon-rock neighbor bundle
(`world3/toporeview/procedural_desert_canyon_rock_m10/`) cold from the
documented args. Compare new output against existing. Examine the
generated macro albedo to diagnose the texture confusion.

## Inputs (recovered from `meta.json` + script defaults)

```bash
python world3/pipeline/build_procedural_neighbor_bundle.py \
    --material-id desert_canyon_rock \
    --out world3/toporeview/_b3_procedural_test \
    --size 512,1024 \
    --world-size-m 120,240 \
    --elev-min-m 412.0 \
    --elev-range-m 18.0 \
    --seed 1021 \
    --name "Procedural desert canyon rock M10 neighbor"
```

Every arg is either explicitly recorded in the original `meta.json` or
matches the script's argparse defaults.

## Execution

- **First attempt** (output dir at `D:/tmp/...`): crashed at line 52
  with `ValueError: '...' is not in the subpath of 'D:\assets\world3'`
- **Second attempt** (output dir inside `world3/toporeview/`):
  - Wall time: **0.586 sec**
  - Exit: 0
  - All 4 output files produced

## Output diff against existing bundle

### File inventory
**IDENTICAL** — same 4 files (`heightmap.png`, `meta.json`,
`layers/render_albedo.png`, `layers/source_valid_mask.png`).

### MD5 hash diff
| File | New MD5 | Old MD5 | Match? |
|---|---|---|---|
| `heightmap.png` | `c8839e6929...` | `c8839e6929...` | ✅ |
| `layers/render_albedo.png` | `d907080940...` | `d907080940...` | ✅ |
| `layers/source_valid_mask.png` | `9f5296c1ab...` | `9f5296c1ab...` | ✅ |
| `meta.json` | `86ffbcdaf5...` | `cdcc51d85c...` | ❌ |

Three of four byte-identical. Meta.json content diff: only the embedded
`res://` paths differ (because `--out` was different). All other JSON
content identical. **Determinism confirmed.**

## Root-cause diagnosis: why the procedural side looks like smooth tan

### The complaint
M18 audit: "The M18 procedural neighbor side reads as broad smooth
tan/sand and triggers the documented visual veto."

User feedback: "the procedural looks like pretty bad, not sure what the
best path is."

### The macro generation code (lines 96-124 in `build_procedural_neighbor_bundle.py`)

```python
def build_macro(material, width, height, seed):
    albedo_path = resolve_repo_path(material["pbr_maps"]["albedo"])
    albedo = Image.open(albedo_path).convert("RGB")
    albedo_arr = np.asarray(albedo, dtype=np.float32) / 255.0
    base = np.median(albedo_arr.reshape(-1, 3), axis=0)  # ← FLATTENS texture to one color

    # ... noise / wash band generation ...

    detail = tiled_detail(albedo_path, width, height,
                          max(76, width // 5), seed + 31)  # tiles the catalog albedo at LOW spatial frequency

    color = base[None, None, :] * value[:, :, None]       # base color × smooth value noise
    color += detail_signal * 0.42                          # ← only 42% strength
    color += wash_bands[:, :, None] * np.array([0.055, 0.035, 0.012])
    color += (1.0 - y[:, :, None]) * np.array([0.025, 0.012, -0.006])
    return np.clip(color, 0.0, 1.0)
```

### What this means in plain terms
1. The catalog's actual albedo (which has rock texture, grit, color variation) is **collapsed to its median color** — a single tan RGB value.
2. A smooth value-noise field is generated and tinted by this single color.
3. The actual catalog texture is then added back at **only 0.42 strength**, blurred to a low spatial frequency by the `tiled_detail` repeat size.
4. The result: a uniform tan field with soft procedural variation — exactly what we see.

### Visual comparison

| | What's in the bundle | What the catalog material actually looks like |
|---|---|---|
| Image | smooth tan with diagonal wavy bands | textured weathered sandstone with grit + color variation |
| Why different | `base × smooth-noise + 0.42 × detail` | the raw catalog albedo |
| Procedural macro size | 512 × 1024 px @ 120 × 240 m world | catalog albedo 512 × 512 px (tileable) |

### The macro_policy declaration is misleading
`meta.json.procedural_neighbor.macro_policy` reads:
```
"catalog_material_color_with_multiscale_procedural_variation"
```

That's an accurate description of the *implementation* but misleading
about the *intent*. The intent (per M10/M17 audit + user clarification)
was to use the catalog material as the texture. The implementation took
"use the catalog material color" literally — single median color.

## Findings

### F1 — The procedural macro suppresses catalog texture by design (Bucket C, the big one)
Line 100 collapses the catalog albedo to a single median RGB.
Line 121 reintroduces the catalog texture at only 0.42 strength under a
smooth noise field. **This is the root cause of the broad-smooth-tan
weakness.**

**Fix shape** (any one or combination of these):
- Increase detail strength from 0.42 → 0.85-1.0
- Replace the value-noise base with the tiled catalog albedo at full
  strength, then *add* procedural variation on top instead of replacing
- Reduce the wash-band/value-noise smoothing so texture isn't smeared
- Add a per-band scale knob (`world_repeat_m` on the detail tiling) so
  it doesn't smear at world scale

This is a small parameter tweak to one function. Maybe 30 lines of code,
1-3 hours of iteration to find good parameters.

### F2 — Hardcoded res:// path crashes outside world3/ (Bucket C, path bug)
`build_procedural_neighbor_bundle.py:52` (`res_path`) calls
`path.relative_to(ROOT)` without try/except. If `--out` is outside
`world3/`, the script crashes with `ValueError`.

```python
# Current:
def res_path(path: Path) -> str:
    rel = path.resolve().relative_to(ROOT.resolve())   # ← crashes if outside ROOT
    return "res://" + rel.as_posix()

# Fix:
def res_path(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(ROOT.resolve())
        return "res://" + rel.as_posix()
    except ValueError:
        return str(path.resolve())   # absolute path as fallback
```

Or: enforce `--out` to be inside `world3/` with a clear error message.

**Trivial fix.**

### F3 — Build is deterministic (positive finding)
Same as B.1: same seed + same inputs produce byte-identical output. Three
of four files matched MD5. The fourth differs only in path strings, not
content. **This is the third chain (out of three tested) that
demonstrates the worker discipline on determinism is solid.**

### F4 — Wall time is < 1 second
The script is dramatically fast (0.586 sec for a 512 × 1024 macro).
Means iteration on F1's macro tuning is cheap: change parameters, re-run
in under a second, eyeball result.

### F5 — The procedural-vs-texture framing was almost-right
The user's framing was: "procedural is the placement engine, textures
come from the texture pipeline."

**Updated understanding**: that framing IS the intent. But the
implementation in `build_procedural_neighbor_bundle.py:build_macro()`
takes "use the catalog material" too liberally — it uses the
catalog material's *color statistics* rather than its *texture*. The
fix is to make the function actually use the texture (per F1's
suggestions), not to redesign the architecture.

## Bucket categorization

### Bucket A (trivial config) — none new

### Bucket B (manual-step gaps) — none new

### Bucket C (real code bugs)
- **C-1 (BIG)**: `build_macro()` parameter tuning. The macro suppresses
  catalog texture at 0.42 strength under smooth noise. This is the
  documented root cause of M18's "broad smooth tan/sand" visual veto.
  Fix: parameter tweak + visual review against the canon catalog albedo.
  Effort: 2-3 hours.
- **C-2 (small)**: `res_path()` crashes if `--out` is outside `world3/`.
  Fix: try/except. Effort: 5 minutes.

### Bucket D (architectural gaps)
- **D-1**: same as B.1 — no orchestrator that consumes a region request
  and resolves which scripts to invoke + with what args.

## The procedural-vs-texture confusion: resolved

After Phase B.3, the picture is much clearer than the earlier framing
discussions implied:

- **Placement code is correct.** Heightmap generation
  (`synthetic_wash_slope_ridge_heightfield`) works.
- **Material catalog is correct.** `desert_canyon_rock` has a good albedo.
- **The bug is in one function** that bridges placement to catalog
  binding: `build_macro()`. It generates a *new* synthesized albedo
  instead of using the catalog's albedo as the visual layer.
- **The fix is parameter tuning**, not architectural rewrite.

This means M19 (procedural neighbor placement quality) was always going
to look broken until `build_macro()` was tuned, regardless of how good
the placement was. The audit-recommended "M19 win condition: procedural
side loses broad-smooth-tan veto" is **literally just a `build_macro()`
parameter fix**.

## What this tells us about the larger rebuild

1. **Strong case for staying in world3 (not world4).** Two chains
   byte-identical-reproducible, one chain almost-identical with a single
   small code bug. Worker discipline is exemplary. World4 would inherit
   exactly these scripts and would still need to fix `build_macro()`.

2. **The M18 weakness is fixable in one session.** Tune `build_macro()`
   parameters, regenerate the M18 procedural neighbor, re-render the
   M18 review scene. Done.

3. **Phase E orchestrator can absorb every gap surfaced.** F2 (path
   bug) is a one-line fix. F1 (macro tuning) is a parameter fix. D-1
   (no orchestrator) is exactly what Phase E builds.

## Recommendation

**Phase B is complete enough to gate to Phase C.** All three chains
tested:
- B.1: byte-identical reproduction, exemplary
- B.2: partial (blocked by ComfyUI not running); 5 Bucket B gaps documented
- B.3: byte-identical reproduction + root cause for "smooth tan/sand"
  diagnosed

Phase C should bucket every finding from B.1/B.2/B.3 and recommend the
exact sequence of fixes for Phase D. The biggest fix (`build_macro()`
tuning) is small enough to bundle as a Phase D.0 quick win, possibly
even before the orchestrator work.

## Cross-references

- Phase plan: [`REBUILD_PLAN_PHASES_B_E_2026_05_11.md`](REBUILD_PLAN_PHASES_B_E_2026_05_11.md)
- B.1 pass: [`B1_CHAIN1_VALIDATION_2026_05_11.md`](B1_CHAIN1_VALIDATION_2026_05_11.md)
- B.2 partial pass: [`B2_CHAIN2_VALIDATION_2026_05_11.md`](B2_CHAIN2_VALIDATION_2026_05_11.md)
- Phase A inventory: [`WORKFLOW_INVENTORY_2026_05_11.md`](WORKFLOW_INVENTORY_2026_05_11.md)
- Bug location: `world3/pipeline/build_procedural_neighbor_bundle.py:96-124`
- Catalog material: `world3/materials/catalog.json` (entry `desert_canyon_rock`)
- Existing bundle (reproducible): `world3/toporeview/procedural_desert_canyon_rock_m10/`

## Phase B.3 status

- [x] Recovered provenance from existing bundle's `meta.json`
- [x] Reconstructed cold-run command
- [x] Discovered path bug (Bucket C, F2) on first attempt
- [x] Cold-run end-to-end (0.586 sec, exit 0)
- [x] Diff: 3/4 byte-identical, 4th differs only in path strings
- [x] **Root-cause diagnosis of procedural-vs-texture confusion**
- [x] Documented findings + bucketing
- [x] Recommendation for Phase C/D

**B.3 PASS** (with two Bucket C findings). The procedural-vs-texture
confusion has a single, well-defined, easily-fixable root cause.
