# Biome Kits Build Notes — 2026-05-12

> Texture-generation session: 48 maps for 4 new biomes (alpine, desert,
> rocky highlands, wetland), the .tres emitter, and per-biome captures
> in scale_demo. Companion to `SCALE_BUILD_NOTES.md`.
>
> Plan executed against: `plans/AXIS6_TEXTURE_VARIETY_2026_05_11.md`.
> Handoff prompt: `docs/HANDOFF_2026_05_12_textures.md`.

## What got built

```
4 biomes × 3 slots × 4 maps = 48 texture maps
  ↓ aaa_texture.py (klein-9B FP8 + qwen_3_8b text encoder, --size 1024)
world/textures/library/w4_biome_<name>_<slot>/{albedo,normal,roughness,ao,...}.png
  ↓ generate_biome_kits.py (install step)
world 4/the world 4/materials/biome_<name>/<slot>/{albedo,normal,roughness,ao}.png
  ↓ write_material_tres_biomes.py
world 4/the world 4/worlds/scale_demo/biomes/material_<name>.tres  (×4)
  ↓ tools/capture_biomes.py (one capture per biome via material_override swap)
captures/biome_<name>_walk_2026_05_12.png  (×4)
```

The existing temperate-forest binding (`materials/anchor_v2/` +
`material_scale_v1.tres`) is unchanged and remains scale_demo's default.

## Slot inventory

| Biome | Slot | Source | Grade | Resolution |
|---|---|---|---|---|
| alpine | ground | ComfyUI klein-9B fp8 | A (e=0.0001, j=1.05, p=9.8) | 1024² |
| alpine | mid | ComfyUI klein-9B fp8 | A (e=0.0029, j=0.94, p=9.7) | 1024² |
| alpine | rock | ComfyUI klein-9B fp8 | A (e=0.0007, j=1.08, p=11.2) | 1024² |
| desert | ground | ComfyUI klein-9B fp8 | B (e=0.0001, j=0.97, p=20.0) | 1024² |
| desert | mid | ComfyUI klein-9B fp8 | A (e=0.0050, j=1.05, p=13.7) | 1024² |
| desert | rock | ComfyUI klein-9B fp8 | A (e=0.0002, j=1.06, p=8.0) | 1024² |
| rocky | ground | ComfyUI klein-9B fp8 | A (e=0.0007, j=1.04, p=11.2) | 1024² |
| rocky | mid | ComfyUI klein-9B fp8 | B (e=0.0109, j=1.10, p=9.9) | 1024² |
| rocky | rock | **reuse** anchor_v2/rocky_slope (real-ortho) | (anchor inherited) | 4096² |
| wetland | ground | ComfyUI klein-9B fp8 | A (e=0.0020, j=1.13, p=7.9) | 1024² |
| wetland | mid | ComfyUI klein-9B fp8 | B (e=0.0012, j=1.02, p=27.5) | 1024² |
| wetland | rock | ComfyUI klein-9B fp8 | A (e=0.0003, j=1.08, p=12.5) | 1024² |

All passed the texture_qa.py PBR gate (grade ≥ B + sanity_ok=True + 4+
core maps present).

## Decisions made during build

- **klein-9B over klein-4B.** The plan called for FLUX2-klein 9B and the
  stack is staged (`flux-2-klein-9b-fp8.safetensors` +
  `qwen_3_8b_fp8mixed.safetensors`). Required a small patch to
  `aaa_texture.py` to expose `--unet`/`--clip` passthrough to
  `variant_select.py` (it already exposed these to `flux_seamless.py`,
  but the aaa orchestrator hardcoded klein-4B defaults). Recorded in
  `aaa_pipeline.json` per slot as `unet:flux-2-klein-9b-fp8.safetensors`.

- **FP8 over NVFP4.** Per `FLUX2_KLEIN_9B_SETUP_2026_05_10.md`, NVFP4
  gives 2.5× speed but "some degrade in quality" vs BF16; FP8 is 1.7×
  speed with "almost same quality." Quality was the priority for these
  48 maps — could iterate later if needed. FP8 ran ~30-60s/slot through
  the full pipeline (4 variants × 2 passes + heal + SM PBR + QA).

- **All 12 slots through ComfyUI, not real-ortho for rocks.** The plan
  called for the 4 rock slots (alpine, desert, rocky-ground, rocky-rock)
  to come from W3's `_soft_composite` pipeline. That pipeline requires
  paired orthophoto + DTM + canopy + NIR stacks (see
  `world3/docs/OPENTOPO_TILEABLE_REAL_TEXTURE_WORKFLOW.md`), which we
  only have for Guadalupe Cypress in Texas — not for alpine or desert
  regions. Fetching new OpenTopo stacks for high-altitude / arid areas
  is a session-scale piece of work in its own right.
  - Tactical deviation: generated 3 ComfyUI rock textures with prompts
    targeting "weathered dark slate" (alpine), "weathered brown
    sandstone" (desert), and "loose scree slope" (rocky-ground).
  - rocky-rock reuses `anchor_v2/rocky_slope` (per plan's explicit
    suggestion: "May be able to reuse anchor's rocky_slope directly").
  - **Backfill candidate**: real-ortho versions of alpine_rock and
    desert_rock once we have the source DEMs + orthophotos. The
    ComfyUI ones are visually plausible but not authentic.

- **Per-biome ambient tints in the .tres files.** Each biome gets
  slightly different `sky_tint`, `ground_tint`, and `sun_color` so the
  scene reads in its own atmosphere (cold for alpine, warm for desert,
  damp-cool for wetland, neutral for rocky). Subtle — the actual color
  comes from the textures. See `pipeline/write_material_tres_biomes.py`
  `BIOME_TINTS` for values.

- **Skipped `palette_lock.py`.** The plan suggested running palette_lock
  per biome for cohesion. Each biome's 3 slots came from prompts that
  already specify the palette explicitly ("cool grey-blue", "warm
  orange-tan", etc.), so the cohesion is in the prompts. The captures
  bear this out — each biome reads cohesive. palette_lock remains
  available as a fallback if any biome drifts in future regenerations.

## Pitfalls hit / avoided

- **Pitfall #1 (texture-driven speckle)**: validation pass scanned all
  24 albedo+AO maps for p5 luminance. Two slots have albedo p5 below
  0.05 (`biome_wetland/ground` at 0.043, several others between
  0.05-0.15). The shader's `albedo_luma_floor = 0.08` catches all of
  them — no shader changes needed. AO p5 is 0.569 or higher across all
  slots, well above the 0.05 threshold.

- **Normal map sanity**: 11 of 12 slots had blue-channel mean ≥ 200
  (predominantly upward-facing tangent-space normal). `biome_desert/rock`
  had B=188 — still B-dominant (B > R=126, B > G=135), just a punchier
  sandstone relief. Encoding is correct; no fix needed.

- **Pitfall #2 (LiDAR scan-line bleed-through)**: visible in the alpine
  and wetland captures where high-frequency texture meets the
  diagonally-striated heightmap regions. This is the same source DEM
  (`_source_1024.png`) used by scale_demo; the bands are inherited from
  the DEM and show up more strongly against bright (snow) or
  detail-heavy (reeds) textures. Not a regression from this session —
  the bands were latent in scale_demo's existing captures, just less
  obvious against the temperate forest palette. Out of scope for this
  session.

- **Pitfall #3 (PBR black quads at scale)**: not hit. All biome
  materials use `terrain_scale_v1.gdshader` (unshaded with manual
  lighting), inherited from `material_scale_v1.tres`.

## Files written / changed

New code:
- `pipeline/generate_biome_kits.py` — batch driver for 10 ComfyUI slots
  with klein-9B (calls aaa_texture.py per slot, installs PBR maps into
  W4 materials/, supports `--only <slot_id>...` for partial reruns).
- `pipeline/write_material_tres_biomes.py` — emits 4 biome `.tres` files
  mirroring `write_material_tres_scale_v1.py` with per-biome tints.

Patched:
- `D:/assets/pipelines/textures/aaa_texture.py` — added optional
  `--unet`/`--clip` args + log-entry, passthrough to `variant_select.py`.
  Default behavior unchanged (klein-4B if flags omitted).

Generated textures (in `the world 4/materials/`):
- `biome_alpine/{ground,mid,rock}/{albedo,normal,roughness,ao}.png`
- `biome_desert/{ground,mid,rock}/{albedo,normal,roughness,ao}.png`
- `biome_rocky/{ground,mid,rock}/{albedo,normal,roughness,ao}.png`
- `biome_wetland/{ground,mid,rock}/{albedo,normal,roughness,ao}.png`

Generated materials (in `the world 4/worlds/scale_demo/biomes/`):
- `material_alpine.tres`
- `material_desert.tres`
- `material_rocky.tres`
- `material_wetland.tres`

Per-biome captures (in `the world 4/captures/`):
- `biome_alpine_walk_2026_05_12.png`
- `biome_desert_walk_2026_05_12.png`
- `biome_rocky_walk_2026_05_12.png`
- `biome_wetland_walk_2026_05_12.png`
- `checkpoint_alpine_ground_2026_05_12.png` (initial validation
  capture, alpine ground bound to test material with anchor mid+rock)

Source library staging (`D:/assets/world/textures/library/`):
- `w4_biome_<name>_<slot>/` per slot with the full PBR set, QA dir,
  Blender preview, `aaa_pipeline.json` log, `variant_select.json`.

Test/temporary material (kept for traceability):
- `the world 4/worlds/scale_demo/material_biome_alpine_ground_test.tres`
  — the initial alpine-ground-only test material. Safe to delete; the
  proper alpine binding now lives in `biomes/material_alpine.tres`.

## What this session did NOT do

(All explicit non-goals from the handoff.)

- **No per-tile biome assignment.** ScaleWorld still uses the single
  `material_override_path` from scale_demo.tscn. Wiring up per-tile
  biome labels + per-tile material assignment is Axis 2 proper and
  belongs in a separate session.
- **No soft-transition / Axis 6 proper.** Hard borders only; the
  per-biome captures use one biome material across all 16 tiles. The
  seam problem will surface once Axis 2 wires the per-tile assignment.
- **No tropical / volcanic / lunar / badlands biomes.** Those remain
  wishlist.
- **No real-ortho rock textures for alpine/desert.** Deferred — see the
  decisions list above.
- **No edits to `anchor_v2/` or `terrain_scale_v1.gdshader`.** The
  anchor regression baseline is intact.

## What unlocks now

- **Axis 2 proper.** Five `material_<biome>.tres` files exist
  (temperate forest = scale_v1; 4 new). ScaleWorld can read a biome
  label from each tile's `meta.json` and assign the matching material
  at spawn time. This is the next session's work.
- **Axis 6 (transition workflow).** Hard borders between biomes will
  produce visible seams once Axis 2 ships. Those seams are the concrete
  problem that the transition workflow needs to solve.

## Cost recap (vs plan estimate)

| Item | Plan estimate | Actual |
|---|---|---|
| 9 ComfyUI ground/mid slots | ~1 hour | ~10 min (klein-9B fp8 + aaa pipeline) |
| 3 ComfyUI rock slots (tactical sub) | n/a (planned real-ortho) | ~5 min |
| Real-ortho rock slots | ~10 min | DEFERRED |
| Validation + re-prompts | ~30 min | ~2 min (no re-prompts needed — all A/B grade) |
| `write_material_tres_biomes.py` emitter | ~15 min | ~10 min |
| Per-biome captures | not planned | ~5 min |
| **Total session pipeline time** | **~2 hours** | **~35 min pipeline + ~30 min review** |

Faster than planned because:
1. No re-prompts needed (klein-9B 4-variant best-pick + aaa QA gate
   caught everything at the first pass).
2. Real-ortho was deferred rather than executed.
3. The aaa pipeline at 1024² with FP8 ran ~30-60s/slot rather than the
   1-2min/slot rough estimate.
