# Plan — Axis 6 Texture Variety (Biome Kit Generation)

> The texture-generation plan for the 4 new biomes (alpine, desert,
> rocky highlands, wetland). Plan-stage only — execution happens in a
> separate session.
>
> Companion to `../strategy/BIOMES.md` (the biome list with palettes).
>
> Cost ballpark: ~48 texture maps generated. Real-ortho slots are
> minute-scale (script run, no model inference). ComfyUI slots are 1-2
> minutes each through the FLUX2-klein 9B stack on a 5090. Realistic
> total: 1-2 hours of pipeline time + iteration.

## What we're generating

4 biomes × 3 slots × 4 PBR maps = **48 texture maps**.

Each slot is one (albedo + normal + roughness + AO) bundle. All 4 maps
for a slot must come from the **same source/prompt** so they're
physically consistent.

Maps per slot:
- `albedo.png` — RGB color
- `normal.png` — tangent-space normal (RGB encoded XYZ)
- `roughness.png` — single-channel roughness 0..1
- `ao.png` — single-channel ambient occlusion 0..1

Resolution: **1024×1024** tileable (matches existing `anchor_v2` set).

## Per-biome texture spec

### Biome 2 — Alpine / snowy

| Slot | Source | Prompt sketch / source DEM | Priority |
|---|---|---|---|
| `ground` | ComfyUI (FLUX2-klein 9B) | "tileable seamless texture, fresh wind-packed snow surface, slight crystalline texture, no footprints, cold blue-white tones, overhead perspective, soft micro-relief" | high |
| `mid` | ComfyUI | "tileable seamless texture, mixed terrain - patchy lichen-spotted rock peeking through thin snow cover, cool grey-blue palette, overhead perspective, weathered" | high |
| `rock` | real-ortho | Source: a high-elevation USGS or alpine DEM tile with exposed dark slate. Run through W3's `_soft_composite` pipeline. | medium |

Palette lock: cool whites, light blue-greys, dark slate. Apply
`palette_lock.py` after generation so all three slots share the cold
palette.

### Biome 3 — Arid / desert

| Slot | Source | Prompt sketch / source DEM | Priority |
|---|---|---|---|
| `ground` | ComfyUI | "tileable seamless texture, fine warm desert sand, slight ripples, soft yellow-tan tones, overhead perspective, no debris" | high |
| `mid` | ComfyUI | "tileable seamless texture, dry desert ground with sparse dead scrub, sand-and-rock-fragment mix, warm orange-tan palette, overhead perspective" | high |
| `rock` | real-ortho | Source: USGS arid-region DEM tile with sandstone or weathered brown rock outcrops. | medium |

Palette lock: warm tans, oranges, weathered browns. Low saturation —
desert ground reads dusty, not vivid.

### Biome 4 — Rocky highlands / scree

| Slot | Source | Prompt sketch / source DEM | Priority |
|---|---|---|---|
| `ground` | real-ortho | Source: a talus/scree slope from a USGS mountain tile. Run through `_soft_composite`. | high |
| `mid` | ComfyUI | "tileable seamless texture, patchy moss and lichen on grey rock, mid-grey palette with sparse green accents, overhead perspective, weathered" | medium |
| `rock` | real-ortho | Source: weathered exposed bedrock. May be able to reuse anchor's `rocky_slope` directly — check if the palette is close enough. | high |

Palette lock: mid-greys, cool. Sparse green / yellow lichen accents.
If `rocky_slope` works as-is, this biome only needs 2 new slots × 4
maps = 8 textures.

### Biome 5 — Coastal wetland / marsh

| Slot | Source | Prompt sketch / source DEM | Priority |
|---|---|---|---|
| `ground` | ComfyUI | "tileable seamless texture, dark wet peat soil with sparse green moss patches, muted dark-brown palette, overhead perspective, slight wetness" | high |
| `mid` | ComfyUI | "tileable seamless texture, marsh ground with tall reed grass tufts, muted green and brown palette, overhead perspective, soft" | high |
| `rock` | ComfyUI | "tileable seamless texture, waterworn dark rounded rocks with moss cover, wet-rock palette of dark greys and greens, overhead perspective" | medium |

Palette lock: dark greens, muted browns, faded blue-greys. All slots
read damp.

## Source method tradeoffs

### Real-ortho (W3 `_soft_composite`)
**Pros:** authentic-looking, free of generation artifacts, tileable
output by construction.
**Cons:** can only generate what we have DEMs for. May not have the
specific palette we want.

Use for: rock textures, scree, weathered ground. The slots where
"looks real" matters more than "looks stylized."

### ComfyUI (FLUX2-klein 9B stack)
**Pros:** any palette, any style, prompt-controllable. Memory entry
`flux2_klein_9b_setup.md` confirms the stack is ready.
**Cons:** can produce subtly non-tileable output; needs the `palette_lock.py`
pass to be biome-cohesive.

Use for: snow, sand, moss, lichen — slots where the "look" is stylized
or where no real DEM gives us the right palette.

## Critical prompt notes

From memory: `tile_prompt_poison_pill.md` — the phrase "tileable seamless
texture" is read by AuraFlow + FLUX correctly but mis-read by
Chroma/SD3.5/Qwen as the noun "tile" (the building material). FLUX2-klein
should handle it correctly. Validate the first generation per biome
before running the full slot.

Also from memory: `flux2_klein_9b_setup.md` — FLUX.2-klein needs
Qwen3-8B text encoder (Comfy-Org fp8mixed), NOT the qwen_3_4b used by
klein-4B.

## Validation pass per slot

After each slot's 4 maps generate:

1. **Near-black texel check** on albedo + AO. Per `PITFALLS.md` #1, any
   texel below 0.05 luminance will speckle without the shader's
   `luma_floor`. Run the Python helper from PITFALLS to scan p5
   luminance.
2. **Tileability check.** Manually tile the albedo 2×2 in an image
   viewer. Visible seams = re-prompt or accept and document.
3. **Palette match.** Compare to other slots in the biome. If they
   look like different lighting conditions, run `palette_lock.py`.
4. **Normal map sanity.** Open the normal map. Should be predominantly
   blue (Z-up tangent space). Pink/green dominant means it's encoded
   wrong.

## Execution order (separate session)

In priority order so the highest-impact slots ship first:

1. **Alpine ground (snow)** — most visually distinct from existing
   biomes. ComfyUI.
2. **Desert ground (sand)** — most visually distinct from snow,
   confirms the palette range. ComfyUI.
3. **Wetland ground (peat)** — third distinct ground treatment.
   ComfyUI.
4. **Rocky highlands ground (scree)** — real-ortho. Run `_soft_composite`.
5. **All four mid slots** — ComfyUI batch, palette-locked per-biome.
6. **All four rock slots** — mix of real-ortho (alpine, desert) and
   ComfyUI (wetland). Rocky-highlands may reuse anchor's `rocky_slope`.
7. **Validation pass on every slot.**

Stop after step 1 and screenshot the result in scale_demo. If the alpine
ground reads as alpine, the rest of the plan is on the right track. If
it doesn't, re-prompt before committing to a full batch.

## What this plan doesn't do

- **No transition / blending workflow.** That's Axis 6 proper. This
  plan only generates the slot kits.
- **No per-tile biome assignment in code.** That's Axis 2 wiring
  (separate session after the textures exist).
- **No water shader work.** Wetland biome hints at water but the
  shader integration is a separate item.
- **No tropical / volcanic / badlands.** Those are wishlist.

## Files to write during execution

The texture-generation session will produce:

```
materials/
  biome_alpine/
    ground/  {albedo,normal,roughness,ao}.png
    mid/     {albedo,normal,roughness,ao}.png
    rock/    {albedo,normal,roughness,ao}.png
  biome_desert/
    ground/  ...
    mid/     ...
    rock/    ...
  biome_rocky/
    ground/  ...
    mid/     ...
    rock/    ...    (may reuse anchor_v2/rocky_slope)
  biome_wetland/
    ground/  ...
    mid/     ...
    rock/    ...
```

Plus a Python emitter (extension of `write_material_tres_scale_v1.py`)
that produces one `.tres` per biome:
- `worlds/scale_demo/biomes/material_alpine.tres`
- `worlds/scale_demo/biomes/material_desert.tres`
- `worlds/scale_demo/biomes/material_rocky.tres`
- `worlds/scale_demo/biomes/material_wetland.tres`

The existing `material_scale_v1.tres` serves as the temperate-forest
biome.

## Cost recap

| Item | Estimate |
|---|---|
| 9 ComfyUI ground/mid slots × 4 maps × ~1-2 min/map | ~1 hour pipeline |
| 4 real-ortho rock slots via `_soft_composite` | ~10 min |
| Validation + re-prompts | ~30 min |
| `write_material_tres_biomes.py` emitter | ~15 min |
| **Total** | **~2 hours next session** |

After that the per-tile-biome wiring (Axis 2) is ~1 session. Soft
transitions (Axis 6) is the unknown — could be 1-3 sessions.
