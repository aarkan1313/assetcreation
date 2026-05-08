# Path 2 — Phase 0 Walkthrough (one-shot ComfyUI inpaint, goblin chest)

**Generated 2026-05-07 evening as the orchestrator handoff.** This is the artifact-prep doc for the [Path 2 inpainting design](../../docs/plans/PATH_2_INPAINT_DESIGN_2026_05_07.md) Phase 0 proof-of-concept. **No batch CLI yet, no automation, no `pipelines/character_inpaint/.venv` install** — that's Phase 1, gated on the brief #09 dispatch.

The goal of Phase 0 is **one experiment**: can FLUX.2 Inpaint + IP-Adapter, pointed at a hand-authored insignia and a chest UV mask, produce a recognizable insignia on the goblin's chest in albedo space? **The result of that single experiment determines whether Architecture A (UV-space) is viable or if we need Architecture B (camera-projection).**

## What's ready (you can move on it cold)

All inputs live at [pipelines/character_inpaint/phase_0_assets/](phase_0_assets/):

| File | What it is | Source |
|---|---|---|
| `goblin_p_albedo.jpg` | The goblin's existing albedo texture (2048², extracted from `meshy/preprocessed/goblin_p.glb`) | Embedded GLB image |
| `goblin_p_uv_layout.png` | The goblin's UV triangulation rendered onto a 2048² white canvas | Auto-generated 2026-05-07 |
| `goblin_p_chest_uv_heuristic.png` | Same UV layout with a red-tinted overlay showing **226 verts heuristically tagged as "front-facing upper torso"** by 3D bbox (NOT a finished mask) | Auto-generated 2026-05-07 |
| `insignia_ashen_pact_brand.png` | Placeholder Ashen Pact brand: red 3-lobe flame with charred ring, 256² RGBA | Auto-generated 2026-05-07 |

**The chest heuristic is a starting point, NOT a usable mask.** The 226-vert front-torso heuristic surfaces a critical Phase 0 finding before any inpaint has run: **chest geometry maps to UV islands scattered across roughly u=[0.02, 0.92] × v=[0.16, 1.00]** — i.e. the chest is **fragmented across multiple UV islands**, not one contiguous chest island. That is exactly the Architecture A failure mode the design doc warned about.

Implication: the chest mask has to be authored **per-island** by visually identifying which UV regions in `goblin_p_uv_layout.png` correspond to the chest. The `goblin_p_chest_uv_heuristic.png` overlay is a coarse hint — refine it manually in any image editor by reference to the source mesh in Blender (open `goblin_p.glb` and rotate the model while looking at the active UV).

## What you need to do at the keyboard (Phase 0 itself)

Total time estimate: 1-2 hours including dawdling. **No new installs needed.**

### Step 1 — refine the chest mask (15-30 min in your favorite paint tool)

Open `goblin_p_uv_layout.png` (or `goblin_p_chest_uv_heuristic.png` for the hint overlay) in Krita / Photoshop / GIMP. On a new layer:

1. Paint the **chest region in pure white** at full opacity. Aim for the front-torso UV islands; ignore back, arms, head, legs.
2. Everything else stays pure black (or fully transparent).
3. Save as `goblin_p_chest_mask.png` next to the existing assets.
4. Optional: use Blender to verify which UV island maps to chest. Open `goblin_p.glb` in Blender, switch to UV Editing workspace, select faces on the chest in the 3D view, and the UV editor will highlight which islands they project to.

The mask resolution should match the albedo (2048²). Hard edges are fine; the inpainter will dilate slightly anyway.

### Step 2 — open ComfyUI and assemble the graph

ComfyUI lives at: [animators/ComfyUI/](../../animators/ComfyUI/) (per the validated install). Start it the same way you've been running it for the FLUX.2 Klein 4B + Recraft icon work in [pipelines/ui/local_diffusion_icons.py](../ui/local_diffusion_icons.py).

The graph for Phase 0 is a stock **inpaint + IP-Adapter reference** workflow. Nodes you need:

```
[ Load Image (goblin_p_albedo.jpg) ] --pixels-->  [ VAE Encode (Inpaint) ]
[ Load Image (goblin_p_chest_mask.png) ] --mask--^

[ Load Image (insignia_ashen_pact_brand.png) ] --> [ IPAdapter Apply ]
                                                      |
[ Load Checkpoint (FLUX.2 Klein 4B) ] -model-> [ KSampler ] <-- positive/negative cond
                                                      |
                                              [ VAE Decode ]
                                                      |
                                              [ Save Image (variant_albedo.png) ]
```

**Critical knobs to set:**

| Node | Param | Suggested value | Why |
|---|---|---|---|
| KSampler | denoise | 0.65 | low-denoise so existing albedo outside the mask is preserved |
| KSampler | cfg | 3.0–5.0 | low CFG to let IP-Adapter dominate (keeps insignia identity) |
| KSampler | steps | 30 | enough for FLUX.2 inpaint to converge |
| IPAdapter Apply | weight | 0.85–0.95 | high weight so the brand identity carries through |
| IPAdapter Apply | weight_type | "style" or "linear" | "style" first; if it loses identity, try "linear" |
| Positive prompt | | `"a faction emblem branded onto leather armor, weathered, cohesive with the surrounding texture"` | weak guidance; IP-Adapter is doing the heavy lifting |
| Negative prompt | | `"blurry, smudged, washed out, glowing, neon, double image"` | guard against the common inpaint failure modes |

### Step 3 — bake the modified albedo back into the GLB

Once you have a satisfying `variant_albedo.png`:

1. Open `goblin_p.glb` in Blender (`File → Import → glTF 2.0`).
2. In the Material panel, replace the base color image with `variant_albedo.png`.
3. `File → Export → glTF 2.0 (.glb)`, write to `pipelines/character_inpaint/phase_0_assets/variant_goblin_ashen_pact.glb`.

Or, faster: a Python one-liner that swaps the embedded image bytes in-place. (Skipping this for now — the manual Blender step is the cleanest visual confirmation.)

### Step 4 — judgment call (the Architecture A vs B decision)

Open `variant_goblin_ashen_pact.glb` in Blender or Godot and answer:

1. **Is the insignia recognizable on the chest in 3D?**
2. **Are there visible UV-seam tears across the brand?** (The fragmented-island finding above predicts this is likely.)
3. **Does the insignia "drape" wrong over chest curvature?** (UV-space inpaint is flat; real chest curvature isn't.)
4. **Is it good enough as a faction signal at gameplay-camera distance** (~5-10 m)?

**Decision matrix:**

- **Insignia recognizable + minimal seams + acceptable curvature drape** → Architecture A is viable. Brief #09 may still suggest improvements, but Phase 1 batch CLI can lean on FLUX.2 Inpaint + IP-Adapter as the core.
- **Insignia recognizable but seams/drape ruin it at distance** → Architecture B (camera-projection via Hunyuan3D-Paint 2.1) is needed. Phase 1 leans on Hunyuan, not FLUX.2 Inpaint.
- **Insignia not recognizable** → either IP-Adapter weight tuning is needed (try Step 2 again with different weights) OR FLUX.2 Inpaint isn't the right base. Brief #09's response will say.

Either way, **document the result** in this doc by editing the section below.

## Phase 0 result (fill in when done)

- [ ] Step 1 — chest mask authored: yes / no
- [ ] Step 2 — ComfyUI graph run: yes / no
- [ ] Step 3 — GLB rebaked: yes / no
- [ ] Step 4 — verdict: Architecture A viable / Architecture B needed / Phase 0 inconclusive
- [ ] One-line summary of what the variant looked like:

## Why the prep is non-trivial (the value this doc captures)

The orchestrator handoff prep (this doc + the auto-generated assets) front-loaded the steps that have specific gotchas:

1. **Identifying that goblin_p.glb has clean single-mesh single-material UVs** — confirmed; rules out a Phase 0 blocker where the test mesh has 5 UDIM tiles.
2. **Identifying chest UV fragmentation as a likely Architecture A failure mode** — surfaced before running the inpaint; reframes the Phase 0 question from "does it work?" to "given fragmentation, is it good enough?"
3. **Pre-rendered UV layout as the authoring canvas** — saves you from having to figure out how to render UVs yourself.
4. **Insignia placeholder pre-authored** — saves 30 min of doodling.

If brief #09 returns before you do Phase 0, the brief will likely refine Step 2's IP-Adapter weights / FLUX.2 inpaint strategy. **Phase 0 is still worth doing first** — the empirical answer to "does Architecture A work on a fragmented chest" is more useful than a generic 2026 SOTA recommendation.

## Files this prep created

```
pipelines/character_inpaint/
    PHASE_0_WALKTHROUGH.md             (this doc)
    phase_0_assets/
        goblin_p_albedo.jpg
        goblin_p_uv_layout.png
        goblin_p_chest_uv_heuristic.png
        insignia_ashen_pact_brand.png
```

**No `pipelines/character_inpaint/.venv` yet** — that's Phase 1. Phase 0 uses the existing ComfyUI install which already has FLUX.2 Klein 4B per brief #07 wiring. **No new installs were performed in this prep step.**
