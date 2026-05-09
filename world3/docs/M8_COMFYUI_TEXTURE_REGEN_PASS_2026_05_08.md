# M8 ComfyUI Texture Regeneration Pass

Date: 2026-05-08

## Purpose

This is the first real M8 generated-texture repair pass after the M1-M7 visual
audit. The target is not "make a prettier flat tile." The target is to prove
that the ComfyUI/`aaa_texture.py` lane can repair a visual blocker through
prompt/variant/PBR workflow, then feed the same source-stack terrain review gate
as OpenTopo-derived materials.

## Candidate: `grassland_grass`

This material was chosen first because it directly polluted the M7
desert-to-grassland stress captures.

| Run | ID | Settings | Result | Visual Read |
|-----|----|----------|--------|-------------|
| v1 | `m8_grassland_grass_calm_v1` | strict, 6 variants, seed 42, original "low dry grass cover" prompt | Gate failed: grade C, edge and periodic failures, StableMaterials fell back due HF cache permissions | Still produced distinct grass tufts and object-like green clumps. Reject. |
| v2 | `m8_grassland_grass_calm_v2` | strict, 12 variants, heal 0.45, seed 43, same prompt | Gate failed: grade B, edge failure, roughness sanity failed after PBR fallback | Some metric improvement, but visually still tufted. Reject. |
| v3 | `m8_grassland_grass_calm_v3` | strict, 12 variants, heal 0.45, seed 44, revised hardpan/straw prompt, StableMaterials active | Gate passed: grade A, edge 0.0025, junction 0.98, period 13.7, sanity OK | Much calmer straw/hardpan read. Candidate only; needs terrain-context review. |

Output:

- `world/textures/library/m8_grassland_grass_calm_v3/`
- `world/textures/library/m8_grassland_grass_calm_v3/qa/tile_2x2.png`
- `world/textures/library/m8_grassland_grass_calm_v3/qa/blender_combo.png`

## Prompt Lesson

The failed prompts still used grass-language in a way FLUX interpreted as tufted
objects. For grassland terrain close detail, the better direction is:

```text
top-down orthographic photogrammetry texture of dry savanna hardpan soil with sparse flattened straw fibers and chopped dry grass fragments, continuous low ground material, mostly tan soil and muted straw, even overcast lighting, seamless PBR terrain texture, no green grass blades, no tufts, no radial clumps, no living plants, no perspective, no shadows
```

The key shift is away from "grass cover" and toward "hardpan soil plus flattened
straw fragments." That reduces radial clumps and green living-plant objects.

## Workflow Lesson

StableMaterials needed a writable dynamic-module cache. Do not set `HF_HOME` to
a fresh unwritable or empty root for this run. The successful command used:

```powershell
Remove-Item Env:HF_HOME -ErrorAction SilentlyContinue
$env:PYTHONIOENCODING = "utf-8"
$env:HF_MODULES_CACHE = "D:\assets\hf_modules"
python pipelines/textures/aaa_texture.py `
  --prompt "<prompt above>" `
  --id m8_grassland_grass_calm_v3 `
  --category Ground `
  --quality strict `
  --variants 12 `
  --heal-strength 0.45 `
  --seed-base 44 `
  --pbr-backend sm
```

## Terrain-Context Follow-Up

`m8_grassland_grass_calm_v3` has now passed the first terrain-context
candidate gate. Evidence:
`M8_COMFYUI_TERRAIN_CONTEXT_REVIEW_2026_05_08.md` and
`M8_COMFYUI_CANDIDATE_NOISE_AUDIT.md`.

Important nuance: the normal low-strength source-stack review shows no visible
regression because the OpenTopo source macro dominates. The detail-stress
review shows the real improvement: the candidate is much less tufted and less
yellow/wavy than current `grassland_grass`, but it is still slightly pale/hazy
when pushed. Keep it quarantined and use it in M4/M7 rerender trials; do not
promote it into the canonical catalog yet.

## Verdict

`m8_grassland_grass_calm_v3` is the first M8 ComfyUI candidate worth testing in
terrain context. It has now passed the first candidate terrain-context gate,
but it is not promoted into `world3/materials/catalog.json` yet.

Next required gates:

1. Stage as a sidecar candidate, not canonical `grassland_grass`.
2. Use it in M4/M7 rerender trials against the current `grassland_grass`.
3. Fix source-stack valid-area/clamp policy before broader review captures.
4. Promote only if terrain-context review beats the current material without
   introducing pale/white washout.
