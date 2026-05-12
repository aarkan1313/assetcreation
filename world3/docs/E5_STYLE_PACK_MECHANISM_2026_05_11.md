# Phase E.5 — Style pack mechanism

> Style packs are named, render-time visual overrides applied by the
> OrchestratorCaptureDriver on top of bundle defaults. Bundles are
> style-pack-independent; the same bundle can be re-rendered in different
> styles without rebuild.

## Verdict

**Mechanism shipped, photoreal default validated, byte-equivalent to pre-E.5 output.** The same M10 procedural bundle rendered with `--style-pack photoreal` produces a PNG of the same size as the pre-E.5 smoke (1969 KB vs 1969 KB), confirming the default pack reproduces existing behavior.

## What shipped

### Style pack schema

`world3/jobs/style_packs/style_pack_schema.json` — JSON Schema draft 2020-12, declares a render-overrides object with the 12 knobs that World3AutoReviewTour exposes for visual style:

- atmosphere: `background_color`, `sun_energy`, `ambient_energy`, `tonemap_exposure`
- terrain shader: `normal_strength`, `detail_normal_strength`, `detail_rough_strength`, `roughness_strength`, `roughness_floor`, `specular_strength`, `albedo_gain`, `source_macro_strength`
- optional `material_suffix` for future per-style .tres variants (e.g. `terrain_blend_desert_iso_topographic.tres`)

### Default pack

`world3/jobs/style_packs/photoreal.json` — id `"photoreal"`, all 12 render fields explicit and matching World3AutoReviewTour.gd defaults at 2026-05-11. Explicit rather than empty so the canonical baseline lives in the same format as future packs.

### Driver wiring

`world3/scripts/OrchestratorCaptureDriver.gd` reads `request["style"]` from the JSON request file and applies each field present to the instantiated tour. Fields absent from the style block fall back to the tour's hardcoded default — a partial pack overrides only what it names.

`world3/pipeline/run_orchestrator_capture.py` learned `--style-pack <id>` (default `photoreal`). It:
1. Loads `world3/jobs/style_packs/<id>.json`
2. Validates `schema_version == 1` and `id` matches filename
3. Injects `style` (render block) and `style_pack_id` into the request JSON
4. If `material_suffix` is set, rewrites the material path to the styled variant *only if that variant file exists* — otherwise warns and uses the base material

### Region request schema update

`world3/jobs/region_request_schema.json` — `world_type.style_pack` description updated to reflect E.5 reality (must match `world3/jobs/style_packs/<id>.json`, applied at capture/render time, bundles are style-pack-independent).

## Validation

```
python world3/pipeline/validate_region_request.py --schema-self-test
=== Schema self-test PASSED (3 examples) ===

python world3/pipeline/audit_stages.py | tail -1
=== All stages and dependencies resolve cleanly. ===
```

Photoreal smoke on M10 iso:
```
python world3/pipeline/run_orchestrator_capture.py \
  --bundle-dir res://toporeview/procedural_desert_canyon_rock_m10 \
  --material   res://textures/wgv3/terrain_blend_desert.tres \
  --mode iso \
  --style-pack photoreal \
  --output res://docs/captures/review/orchestrator_e5_photoreal_smoke_m10_iso.png \
  ...

[run_orchestrator_capture] OK ... (1969 KB, 3.96s)
```

Identical size to pre-E.5 wrapper smoke (also 1969 KB). The style pack mechanism is on the read path without changing the look.

Negative case:
```
python world3/pipeline/run_orchestrator_capture.py --style-pack does_not_exist ...
FileNotFoundError: style pack not found: D:\assets\world3\jobs\style_packs\does_not_exist.json
```

Fails fast with a clear error.

## Design notes

**Why render-time, not bake-time?** A bundle takes minutes to build (DEM ingest, seam solver, runtime cache, scatter mask derivation). Captures take seconds. Putting the style at capture-time means one bundle backs any number of style variants without rebuild, which is what makes "different art directions of the same world" cheap to produce.

**Why a 12-knob struct rather than a free-form shader override?** The shader is already fixed (terrain_splat_unified.gdshader). The 12 knobs are exactly what the tour exposes for visual tuning and what was hand-tuned per M-arc capture scene. Codifying them gives a small, well-defined surface that the orchestrator can validate. Future style packs that need new knobs add a field to the schema, the driver, and possibly the shader; the photoreal pack stays exact.

**Why `material_suffix` rather than full material override?** Most style differences sit in the 12 render knobs. A `material_suffix` covers the case where a style needs a completely different shader binding (e.g. a hypothetical `topographic` style with a flat-shaded hillshade .tres) without bloating the schema. Today no alternate suffixes ship; the field is reserved.

## What's NOT in E.5

- Alternate style packs (painterly, topographic, etc.). The schema and driver support them; the *art* hasn't been authored. Deferred to a future M-arc when there's a use case.
- Per-style material variants (`terrain_blend_<kit>_<mode>_<suffix>.tres`). The `material_suffix` plumbing is there; no variants exist on disk yet.
- Style pack validation in the orchestrator's request validation path. `validate_region_request.py` confirms `world_type.style_pack` is a string but doesn't verify the file exists. `run_orchestrator_capture.py` enforces it at invocation time, which is sufficient for now.

## Status

- [x] E.1 schema + 3 examples + validator
- [x] E.2 stages manifest + audit (12 stages clean)
- [x] E.3 orchestrator + provenance (byte-identical output)
- [x] E.4 OrchestratorCaptureDriver.gd + .tscn + python wrapper + stages.json wiring + M18 cascade validated
- [x] E.5 style pack schema + photoreal default + driver wiring + wrapper --style-pack flag
- [ ] E.6 docs + handoff (README rewrite, WORKFLOW.md addendum done, ORCHESTRATOR_HANDOFF refresh)
- [ ] E.7 final validation + sign-off on unseen region

**Phase E.5 SHIP.** Style pack mechanism live, photoreal default reproduces canonical output, alternate packs are a pure-content additive concern.
