# Alpine Diversity Batch — 2026-05-12

Parallel-track exploration kicked off while Axis 1 Path 2 work continues
in another chat. The goal is **prompt-space exploration**, not shipping:
generate ~50 alpine materials, eyeball the pool, pick the best 3 (one
per slot) to replace the current `biome_alpine` kit.

## What's running

- **Driver:** `pipeline/diversity_alpine.py` (51 prompts total)
- **Model stack:** klein-9B FP8 + qwen_3_8b (matches `generate_biome_kits.py`)
- **Settings:** `--quality default` → 4 variants, seam-B+ target,
  StableMaterials PBR backend, 1024px FLUX → 512px PBR delivery
- **--no-gate:** failures still ship so we can review marginal cases
- **Output:** `D:/assets/world/textures/library/w4_alpine_div_<NN>_<slot>_<tag>/`

## Prompt distribution

| Slot   | Count | Theme                                            |
|--------|-------|--------------------------------------------------|
| ground | 16    | snow types: powder, windpack, firn, hoar, drift, icy crust, melt patches, sastrugi, glacial blue, dusty old |
| mid    | 21    | lichen-rock-snow mixes, scree+snow, frost-heaved soil, alpine grass, permafrost, snowmelt |
| rock   | 14    | dark slate, granite, basalt, quartz veins, schist, frost-shattered, glacial polish, verglas |

51 materials × ~90s each on klein-9B FP8 ≈ ~75 min wall clock.

## Review workflow (when batch finishes)

1. `cd D:/assets/world/textures/library/`
2. For each `w4_alpine_div_*` folder, open `qa/` thumbnails (sphere +
   plane previews + seam grade) to judge:
   - **Tileability** — does the seam grade pass B (overall < 0.005)?
   - **Palette fidelity** — does it actually read as alpine, not generic?
   - **PBR consistency** — albedo / normal / roughness agree?
   - **Variety vs current kit** — does it bring something the
     current `biome_alpine/<slot>/` doesn't already have?
3. Pick **1 winner per slot**. Promote it:
   ```
   cp .../w4_alpine_div_<NN>_<slot>_<tag>_<map>.png \
      "D:/assets/world 4/the world 4/materials/biome_alpine/<slot>/<map>.png"
   ```
   for `albedo, normal, roughness, ao`.
4. Rebuild the biome arrays + relaunch the editor to verify.

## What this batch teaches us (regardless of which wins)

- **Which prompt knobs actually matter for FLUX2-klein at this scale.**
  Are descriptors like "wind-packed" / "sastrugi" doing visible work,
  or does klein collapse them all to generic-snow?
- **How sensitive `mid` is to prompt phrasing.** The mid slot is the
  hardest because it's the biome's character. 21 variants gives us
  signal on whether the current `mixed terrain - patchy lichen-spotted
  rock peeking through thin snow cover` prompt is actually optimal.
- **Whether StableMaterials handles snow PBR.** SM is trained mostly
  on hard surfaces (rock, metal). 16 snow grounds tests how it handles
  soft/translucent materials at scale.

## Re-run / resume

`already_have()` skip-detects completed materials. Safe to ctrl-C and
re-run; it picks up from the first missing slot. For a single material:

```
python pipeline/diversity_alpine.py --only ground_fresh_powder
```
