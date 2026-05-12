# Biomes

> The five chosen biomes for W4's first multi-biome demo. Pinned
> 2026-05-11. Each entry covers palette, slot sources (real-ortho vs
> ComfyUI vs both), and what role the biome plays in the world.
>
> For the texture-generation plan see `../plans/AXIS6_TEXTURE_VARIETY.md`.

## Decision criteria

- **Earth-plausible adjacency.** Any two biomes from this list should
  be able to sit next to each other without reading as fantasy. No
  lunar maria next to lush wetland.
- **Visually distinct at a glance.** Warm vs cold, lush vs barren,
  soft vs sharp. The biome switch should feel real even on a thumbnail.
- **3-slot compatibility.** Each biome needs a `ground / mid / rock`
  PBR kit matching the `terrain_scale_v1.gdshader` slot contract.
- **Mixed source method.** Some slots come from real-ortho (W3's
  `_soft_composite` pipeline), some from ComfyUI generation. Real-ortho
  for slots where authenticity matters (ground textures the player sees
  up close); ComfyUI for stylized treatments (lichen, snow, weathered
  rock).
- **Earth-temperate-region focus.** The first 5 are temperate-to-cold,
  not tropical or extreme. Volcanic / lunar / badlands go in the
  parking lot.

## The five

### 1. Temperate forest  *(already exists)*
**Status:** shipped as the anchor + scale_demo default kit.
**Palette:** warm browns + greens + grey rock. Lichen accents.
**Where it fits:** mid-elevation, mid-latitude. Default biome.
**Slot sources:**
- `ground` = `scrub_dense` — real ortho (W3 `_soft_composite`)
- `mid` = `tundra_lichen` — ComfyUI generated
- `rock` = `rocky_slope` — real ortho

No new generation needed. This kit is the reference for what "shipped
biome" means.

### 2. Alpine / snowy
**Palette:** bright cold whites + cool greys + dark slate rock. Almost
no warm tones.
**Where it fits:** high elevation. The "rock + snow above tree line"
biome.
**Slot sources:**
- `ground` = fresh snow / wind-packed snow → ComfyUI
- `mid` = mixed snow + lichen-on-rock patches → ComfyUI
- `rock` = dark slate / cracked alpine rock → real ortho (mountain regions)

**Why it works visually:** the snow ground reads as the brightest
biome in the catalog. Adjacent to temperate forest it'd make a
realistic tree-line transition.

### 3. Arid / desert
**Palette:** warm sandy yellows + dry oranges + weathered brown rock.
Very low saturation.
**Where it fits:** low elevation, hot. The "dry valley floor" biome.
**Slot sources:**
- `ground` = fine sand / cracked dry earth → ComfyUI
- `mid` = scrub grass + rock fragments → ComfyUI
- `rock` = weathered sandstone / dry brown rock → real ortho (desert regions)

**Why it works visually:** warm palette opposes alpine's cool palette.
Earth-adjacent to scrub / rocky biomes.

### 4. Rocky highlands / scree
**Palette:** mid-grey rock + sparse moss + dust. Cool low-saturation.
**Where it fits:** steep upland, transitional between forest and
alpine. Lots of exposed rock.
**Slot sources:**
- `ground` = scree / loose rock fragments → real ortho (talus slopes)
- `mid` = patchy moss on rock → ComfyUI
- `rock` = weathered exposed bedrock → real ortho (same source as anchor's `rocky_slope`?)

**Why it works visually:** "rock-dominant" reading. Works as a
transition biome between temperate-forest and alpine. Earth-plausible
on any mountain.

### 5. Coastal wetland / marsh
**Palette:** muted greens + dark wet browns + faded blue-greys.
Wet-soil saturation.
**Where it fits:** low elevation, near water. The "valley bottom" biome.
**Slot sources:**
- `ground` = peat / wet soil → real ortho (marsh regions if available,
  otherwise ComfyUI)
- `mid` = reeds + grass tufts → ComfyUI
- `rock` = waterworn dark rock / mossy boulder → ComfyUI

**Why it works visually:** dark-and-damp palette opposes desert's
warm-and-dry. Earth-adjacent to temperate forest at lower elevations.
Hints at water that we'll integrate when the water shader matures.

## Why these five (and not others)

The five together span:
- **Two temperature axes:** alpine (cold) ↔ desert (hot), with
  temperate-forest in the middle
- **Two moisture axes:** wetland (wet) ↔ desert (dry), with
  temperate-forest in the middle
- **Two elevation axes:** alpine + rocky highlands (high) ↔ wetland
  (low), with temperate-forest mid
- **Variety of rock treatments:** dark slate (alpine), sandstone
  (desert), grey bedrock (highlands), waterworn (wetland)

So the biome adjacency graph is rich — many pairs of these can sit
next to each other and tell a real-world story.

## What's parked for now

- **Volcanic / basalt** — black ash, glowing crack details. Visually
  striking but needs lava/heat shaders to fully sell. Wishlist.
- **Tropical jungle** — dense overgrowth, bright greens. The 3-slot
  ground/mid/rock model doesn't capture jungle well (canopy is a
  fourth layer). Needs Axis 5 (decoration) integration first.
- **Badlands / red canyon** — striated orange/red rock. Beautiful but
  the layered striations want a special-purpose shader, not a generic
  ground/mid/rock kit. Wishlist.
- **Lunar / planetary** — different rules entirely (no soil moisture
  axis, no vegetation slot). Belongs in Axis 3 (Source kernelization)
  after Earth-biome work is done.

These can promote from the wishlist once the five above are working.

## Pipeline shape for the 4 new biomes

Each biome needs:
- 3 slots × 4 PBR maps = 12 texture files
- All 4 maps per slot from the same source/prompt (for physical
  consistency: albedo matches normal which matches roughness which
  matches AO)
- All 3 slots in a biome share a palette (use `palette_lock.py` from
  the FLUX2 stack)
- A new `material_<biome>.tres` binding (auto-generated by a script
  that mirrors `write_material_tres_scale_v1.py`)

4 biomes × 12 maps = 48 new texture maps total. See
`plans/AXIS6_TEXTURE_VARIETY.md` for the per-texture plan.

## Naming convention

- Folder: `materials/biome_<name>/<slot>/<map>.png`
  E.g. `materials/biome_alpine/ground/albedo.png`
- Existing temperate forest stays as `materials/anchor_v2/<slot>/` for
  backward compatibility with the anchor demo. We don't rename it.
- New biomes use the `biome_<name>` prefix to distinguish them from
  the legacy `anchor_v2` layout.

## Multi-biome assignment in scale_demo

Once the 4 new kits exist, scale_demo's 16 tiles get biome labels:

```
Z=3:  alpine    alpine    rocky    rocky
Z=2:  alpine    forest    forest   rocky
Z=1:  forest    forest    desert   desert
Z=0:  wetland   wetland   desert   desert
```

That's a rough sketch — actual layout chosen for visual interest +
plausible Earth adjacency. The TileTerrain reads the biome label from
its meta.json and ScaleWorld assigns the corresponding material
override at spawn time.

This is the v1 hard-border approach. Visible seams at biome boundaries
become the concrete reason to do Axis 6 (transition workflow).
