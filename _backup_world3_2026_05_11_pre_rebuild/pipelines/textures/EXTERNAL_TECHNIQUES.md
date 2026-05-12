# External Techniques — Tileable PBR Texture Generation

A snapshot of the state of the art outside our pipeline, as surveyed
on **2026-05-07**. Purpose: figure out what techniques other people
have converged on, what we're already doing right, what's worth
trying, and what's a dead end so we don't waste time re-discovering it.

This doc is a **snapshot**, not a runbook. Findings here are dated.
If a technique gets adopted, it migrates into PIPELINE.md / TOOLS.md /
TEXTURE_RND.md as appropriate, and this doc becomes the historical
record of why we tried it.

---

## TL;DR

**We're already doing the canonical thing.** Offset-and-inpaint
("offset+heal" in our codebase) is the consensus technique for making
FLUX-class diffusion models produce tileable output, since circular
padding doesn't work for DiT architectures. Several open-source repos
implement variations of the same algorithm. Our pipeline matches the
state of the art; the recent A.2 sweep failures (snow lace, leaf
litter lattice) are *prompt* problems, not pipeline problems.

**Worth trying** (in order of expected payoff):

1. Cookbook updates from material-specific prompt patterns surfaced
   in the survey (mineral-naming, "PBR/albedo" anchor terms, dropping
   directional cues — supports our existing A.3 plan).
2. Variation-and-stitch (cprimozic): generate 4 variants of the same
   prompt+seed, blend into one tile. Different from our current
   variant-best-pick — this *combines* variants instead of choosing
   one. Could rescue lattice-prone categories.
3. CHORD model as A/B against StableMaterials for the texture→PBR
   step. Different backbone, recent (ICCV 2025).

**Dead ends** (do not pursue): see "Did not pan out" section below.

---

## Methods of survey

- **WebSearch** for "FLUX seamless tileable", "FLUX PBR texture",
  "FLUX 2 klein prompt", related material-specific terms
- **WebFetch** on civitai workflows, openart workflows, GitHub repos,
  research-paper project pages, blog write-ups
- **Reddit was a bust** — `site:reddit.com` searches returned no
  results, and direct fetches of Reddit are blocked at our access
  level. PLAN.md A.5 flagged this would happen. Workaround: rely on
  curated sources (civitai/HF/GitHub) which return content reliably.

The doc set here is what we found in roughly two hours of structured
search. There is more out there — Discord servers, paywalled
tutorials, video walkthroughs — that we didn't explore.

---

## Techniques table

Quick-scan summary. Detailed write-ups in the sections below.

| Technique                                    | Source                          | Applicability to our pipeline | Status              |
|----------------------------------------------|---------------------------------|------------------------------|---------------------|
| Offset-and-inpaint at boundaries             | sagieppel, was-node-suite, ours | **Already adopted**          | confirmed canonical |
| Circular padding in UNet/VAE                 | spinagon, lllyasviel/forge      | NOT compatible (FLUX/DiT)    | dead end            |
| Tiled Diffusion (CVPR 2025)                  | madaror/tiled-diffusion         | Unknown FLUX support; speculative | parked         |
| FLUX Seamless Texture LoRA (`smlstxtr`)      | civitai (model 900955)          | NOT compatible (FLUX.1, we use 2-klein) | dead end |
| Variation-and-stitch (4 variants → 1 tile)   | cprimozic blog                  | New approach — could try     | **try** (#2)        |
| Mineral-naming prompt pattern                | cprimozic blog                  | Cookbook addition            | **try** (#1)        |
| "PBR" / "albedo" / "flat lay" anchor terms   | nextdiffusion, openart guides   | Cookbook addition            | **try** (#1)        |
| Negative prompts (FLUX.1)                    | various                         | NOT applicable (klein cfg=1) | dead end for us     |
| CHORD model (texture → PBR)                  | RunComfy, ICCV 2025             | Possible StableMaterials A/B | **try** (#3)        |
| MaterialMVP (mesh-aware PBR)                 | ZebinHe/MaterialMVP             | Needs 3D mesh                | dead end            |
| DualMat (dual-path PBR)                      | DualMat ACM MM 2025             | No public code               | parked              |
| Hunyuan3D 2.1 PBR pipeline                   | Tencent                         | 3D-asset focused, not 2D tile | parked             |
| SViM3D (multi-view PBR from single image)    | HF paper 2510.08271             | Multi-view, not tile         | parked              |
| FLUX 2 klein "concrete subject" guide        | fal.ai blog                     | Inform prompt structure      | already aligned     |
| `flux_fill` / `controlnet-inpaint`           | alimama, SkalskiP               | High-strength inpaint        | speculative; A.4    |

---

## Detailed write-ups

### 1. Offset-and-inpaint (we already do this) ✅

The technique: take a generated texture, shift it by half its width
and height (so the original seams are now in the center), then mask
the new seam-cross and inpaint over it. The result tiles seamlessly
because the new edges are unmodified original-edge content, and the
formerly-jarring seam is now a model-blended interior.

**Implementations found:**
- [`sagieppel/transform-image-into-seamless-tileable-texture-using-stable-diffusion-inpainting`](https://github.com/sagieppel/transform-image-into-seamless-tileable-texture-using-stable-diffusion-inpainting)
  — exposes `prompt`, `strength`, `guidance_scale`, `impact` (blend
  weight), `width` (boundary region in pixels), `steps`. Uses SD
  inpaint backbone.
- [`brick2face/seamless-tile-inpainting`](https://github.com/brick2face/seamless-tile-inpainting) —
  same algorithm as an A1111 extension.
- [`was-node-suite-comfyui` "Inpaint seamless tiling preparation"](https://github.com/WASasquatch/was-node-suite-comfyui/discussions/181) —
  ComfyUI implementation.

**Our equivalent:** [`flux_seamless.py`](flux_seamless.py) — same
offset+heal idea, adapted for FLUX 2 klein's distilled-diffusion
specifics. The `tile_offset` + img2img-with-seam-mask pass is exactly
this technique.

**Lesson for us**: this is the *canonical* technique, not just one of
several. Our pipeline isn't behind here — it's at parity with what's
in the open ecosystem. Feel reassured about the architecture.

---

### 2. Circular padding (DEAD END for FLUX) ❌

The technique: replace the standard zero-padded convolutions in the
UNet and VAE with circular-padded ones, so the model "sees" the image
as if its edges were already connected. Output is inherently tileable
without post-processing.

**Why it's a dead end for us**: this requires modifying the model's
convolutional layers. It works for SD/SDXL because they're
convolution-heavy. It does *not* work for **FLUX or any DiT (Diffusion
Transformer) architecture** — the attention-based blocks don't have
the same padding hooks. There is an [active civitai bounty](https://civitai.com/bounties/5174/seamless-tiling-for-flux-comfy-workflow)
asking for a FLUX-compatible seamless tiling node, which had no
delivered workflow as of survey time.

We use FLUX 2 klein. So: skip this entirely.

**References:**
- [`spinagon/ComfyUI-seamless-tiling`](https://github.com/spinagon/ComfyUI-seamless-tiling) — SDXL-only.
- [SD WebUI Forge tiling discussion](https://github.com/lllyasviel/stable-diffusion-webui-forge/discussions/277) — confirmed broken with FLUX.

---

### 3. Tiled Diffusion (CVPR 2025) — PARKED 🔵

[madaror/tiled-diffusion](https://github.com/madaror/tiled-diffusion).
Paper claims support for self-tiling, many-to-many tile relationships,
texture synthesis, and 360° panorama generation. Looks impressive on
the [project page](https://madaror.github.io/tiled-diffusion.github.io/).

**Why parked, not adopted**: the project page doesn't say what
backbone it works with. The references are to SD-architecture work.
A FLUX/DiT port is not advertised. Adopting this would require either
(a) running it on SDXL and hoping the resulting style is usable — but
SDXL produces visibly worse photoreal terrain than FLUX 2 klein, that
was settled in the pipeline overhaul — or (b) doing a non-trivial
research port to FLUX, which is out of scope for this phase.

Revisit if a FLUX port lands or if we ever explore SDXL again.

---

### 4. FLUX Seamless Texture LoRA `smlstxtr` (DEAD END for us) ❌

[civitai model 900955](https://civitai.com/models/900955/flux-seamless-texture-lora).
Trigger word `smlstxtr`. Recommended prompt structure:
`smlstxtr, <prompt>, seamless texture`. **Trained against FLUX.1 D.**

**Why it's a dead end**: we use **FLUX.2 klein**, not FLUX.1. LoRAs
generally don't transfer across major-version base models. Loading a
FLUX.1 LoRA against klein would either silently produce garbage or
fail outright. There is no FLUX.2-klein-compatible seamless-texture
LoRA in the survey results — either nobody has trained one yet, or
it's not popular enough to surface.

If we ever revert to FLUX.1 (we won't — klein is much faster and
seam-acceptable for our use case), this becomes a candidate.

---

### 5. Variation-and-stitch (cprimozic) — TRY 🟢

From [cprimozic.net's "Generating 4K PBR Textures Using Stable
Diffusion XL"](https://cprimozic.net/notes/posts/generating-textures-for-3d-using-stable-diffusion/).
Workflow:

1. Generate one base texture with target prompt.
2. Use the WebUI's "variations" feature with strength 0.1–0.3 to
   produce ~12 stylistically-similar versions.
3. Pick 4 most cohesive ones.
4. Use a custom **seamless stitcher** tool (open source, linked from
   the post) that blends those 4 1K textures into a single 4K
   seamless tile.

The blend isn't a naive grid — it stitches them in a way that hides
the boundaries between source variations.

**Why it's interesting for us**: our current pipeline picks **one**
variant out of N (`variant_select.py`, by edge-MSE). Cprimozic's
approach **combines** N variants into one tile. For lattice-prone
materials (grass, leaf litter) this could break the periodicity that
single-image lattice generation produces — combining 4 differently-
patterned variants into one tile means no single periodic motif
dominates.

**Effort to try**: medium. We'd need a new tool — call it
`variant_blend.py` — that takes N albedo PNGs sharing a prompt and
blends them with edge-aware boundaries (Voronoi-region or feathered
quadrant tiling). Not trivial; ~1-2 hours of code + tuning. Defer
until we've confirmed prompt-only fixes (A.3) aren't enough.

**References to study**: [`camenduru/seamless`](https://github.com/camenduru/seamless),
[`carson-katri/dream-textures`](https://github.com/carson-katri/dream-textures) (Blender) —
both have stitching code we could reference.

---

### 6. Mineral / specific-substance prompt pattern — TRY 🟢

From cprimozic's working example:

```
top-down image of rough solid flat dark, rich slate rock.
interspersed with bright ((flecks)) of ((glinting)) metallic
spots like mica. high quality photograph, detailed, realistic
```

Note the pattern: **named minerals** (slate, mica) instead of abstract
adjectives. FLUX/SD have stronger latent associations with specific
substance names than with adjective phrases like "weathered grey
stone." (The `((double parens))` weight syntax is A1111-specific and
doesn't transfer to ComfyUI/our pipeline — but the *content* of that
prompt does.)

**For our cookbook**: where we have "weathered tan limestone rock" we
could try "weathered limestone with calcite veins and lichen patches."
For "dark grey volcanic rock" → "dark basalt with olivine grains and
fine vesicles." Names of specific minerals or geologic features pin
the model to known reference imagery.

**Implication for A.3 leaf_litter**: the handoff suggested "fallen
oak leaves and pine needles on dark soil" — that's the same pattern
(specific named species) and is likely the right move. **We were
already converging on this.**

---

### 7. "PBR" / "albedo" / "flat lay" / "studio lighting" — TRY 🟢

From multiple guides
([nextdiffusion](https://www.nextdiffusion.ai/tutorials/how-to-make-seamless-textures-with-ai-stable-diffusion),
[openart prompt collections](https://openart.ai/blog/post/stable-diffusion-prompts-for-texture)):

- Lead-phrase candidates besides "top-down photo": **"flat lay
  photograph of"**, **"orthographic top-down view of"**,
  **"photogrammetry albedo capture of"**, **"PBR diffuse map of"**.
- Lighting candidates: **"diffuse studio lighting"**, **"shadowless
  illumination"**, **"ambient occlusion lighting"**.

Currently our cookbook has converged on `top-down photo, even
lighting, photoreal`. These alternatives might give cleaner results
for materials where the current cue produces stylized output (snow's
"frosted glass" failure is exactly this kind of stylization escape
hatch). **Direct A.3 contribution: add at least one variant per
material that uses a different lead phrase + lighting cue.**

Risk: FLUX may not have strong training-set associations with
"PBR diffuse map" / "albedo capture" since those are
graphics-pipeline jargon, not photographer jargon. Could backfire.
That's exactly why A.3 should test it.

---

### 8. Negative prompts (NOT applicable for klein) ❌

Multiple sources mention negative prompts as critical for tileable
texture generation: exclude shadows, perspective, vignette, depth of
field, etc. Stable-diffusion-WebUI / SDXL workflows use these heavily.

**Why this doesn't apply to us:**

- FLUX.1 D **does not support negative prompts** at all (per Black
  Forest Labs docs).
- FLUX.2 klein has a `negative_prompt` parameter in the API, but it
  is honored only at `cfg > 1`. Klein is a distilled model designed
  to run at `cfg=1.0`, which is what our pipeline uses
  (`flux_seamless.py:108`, `cfg=1.0` is hardcoded into the workflow).
- Raising cfg on klein degrades output quality (it's been distilled
  for cfg=1, not for guidance scaling).

**Our existing approach is correct**: phrase exclusions positively
*inside the prompt* — `no debris, no objects` becomes part of the
positive description. FLUX honors these reasonably well, even though
"no" is technically a negation it doesn't formally process.

We could still **try** running our pipeline at cfg=2 with a
negative prompt, but it's risky — likely degrades the photoreal
quality we get at cfg=1. Not high priority.

---

### 9. CHORD model (texture → PBR) — TRY (later) 🟢

[CHORD ComfyUI workflow on RunComfy](https://www.runcomfy.com/comfyui-workflows/chord-model-workflow-in-comfyui-pbr-material-generation).
Two-stage: (1) z_image_turbo generates a tileable texture from
prompt; (2) CHORD takes that texture and produces base color, normal,
roughness, metalness, and a derived height map.

**Where this could fit in our pipeline**: as an alternative to
[StableMaterials](stablematerials_image2pbr.py) (the texture → PBR
step). If CHORD's PBR-decomposition is better than StableMaterials',
we could swap it in. We already produce a tileable albedo upstream
(via FLUX 2 klein + offset+heal); we could pipe that into CHORD's
**second** stage only.

**Effort to try**: install CHORD's ComfyUI graph (medium — may have
custom-node deps, model download), wire `aaa_texture.py` to call it
as an alternative to the SM stage, A/B against StableMaterials on 5
known-good materials.

**Risk**: CHORD is paired with z_image_turbo; its quality on FLUX
2-klein-generated textures (different style, color, noise
characteristics) is unknown. Could be that CHORD assumes a particular
input distribution.

**Defer until** we've squeezed the prompt-engineering wins out of A.3
+ A.4. PBR-step quality is downstream of albedo quality — fix the
upstream first.

---

### 10. Mesh-aware PBR (NOT applicable) ❌

[MaterialMVP](https://github.com/ZebinHe/MaterialMVP), DreamMat,
Hunyuan3D 2.1, SViM3D — all generate PBR materials *for a specific
3D mesh*, projecting view-consistent textures onto geometry. They
need a mesh as input.

**Why these don't apply to us**: world3 uses **2D tileable terrain
textures** sampled by shaders. We're not painting individual meshes;
we're producing 1K square tiles that get hex-tiled across a heightmap.
None of the mesh-aware techniques produce the right kind of output.

If world3 ever grows individual props (rocks, trees, structures) that
need their own surface materials, this category re-enters scope.

---

### 11. FLUX 2 klein prompt-construction guide — already aligned ✅

The [fal.ai FLUX 2 klein prompt guide](https://fal.ai/learn/devs/flux-2-klein-prompt-guide)
recommends a prompt order of: subject → environment → style → technical
details, with under-100-word total length and explicit lighting
specification.

Our cookbook (`TEXTURE_RND.md` Part 2 "Anatomy of a useful prompt")
already follows this order. **No change needed.** We're aligned.

One small clarification we can borrow: the fal.ai guide warns against
"conflicting aesthetics" (e.g., photorealistic + watercolor in the
same prompt). Our cookbook anti-patterns list could mention this
explicitly, since it's a failure mode that's easy to fall into when
prompt-engineering gets verbose.

---

### 12. FLUX inpainting models (`flux_fill`, controlnet-inpaint) — speculative

[`alimama-creative/FLUX.1-dev-Controlnet-Inpainting-Beta`](https://huggingface.co/alimama-creative/FLUX.1-dev-Controlnet-Inpainting-Beta)
and the [Flux Fill](https://stable-diffusion-art.com/flux1-fill-inpaint/)
model are dedicated inpainting variants of FLUX, trained for the
inpaint task specifically. The literature reports strength values of
0.85–1.0 work well *for these models* — much higher than what works
for vanilla FLUX (which "wasn't specially trained for inpainting").

**Implication for our heal_strength**: validates our 0.35 default
for the *current* pipeline (which uses vanilla klein img2img for the
heal pass). A future option is to swap the heal step to a dedicated
inpaint model — at which point the entire heal_strength range would
shift up. **This is a real candidate for A.4 settings sweep**: don't
just sweep heal_strength on the current model; consider whether a
different inpaint *model* gives us a better range.

Effort: medium-high. Requires wiring a new model into the seamless
pipeline. Defer unless A.4 with the current heal proves insufficient.

---

## Did not pan out (parked / dead ends, brief)

- **Reddit search** — anti-scraping returns no results. Switch to
  curated sources.
- **Circular padding** — DiT incompatible.
- **FLUX.1 LoRAs** — won't load against klein.
- **MaterialMVP / Hunyuan3D / SViM3D / DreamMat** — mesh-required.
- **DualMat** — paper-only, no public code as of survey.
- **Tiled Diffusion CVPR 2025** — FLUX support unconfirmed.
- **Negative prompts on klein** — disabled by cfg=1 distillation.

---

## Concrete recommendations for the next iteration

(These belong in PLAN.md / TEXTURE_RND.md when adopted; here for
synthesis only.)

**For A.3 (snow + leaf_litter prompt rewrites):**

1. Keep the variants the handoff already suggests — they align with
   surveyed best practices.
2. **Add one variant per material** that uses an alternate lead
   phrase from technique #7: "flat lay photograph of" or
   "photogrammetry albedo capture of" (snow), "orthographic top-down
   view of" (leaf litter).
3. **Use mineral/species naming** in at least one variant (technique
   #6): for snow, e.g. "fresh snow with ice crystal aggregates and
   firn texture"; for leaf litter, "fallen oak and beech leaves over
   loam soil with pine needles and twig fragments." This refines the
   handoff's suggestions slightly.

**For A.4 (settings sweep):**

1. Sweep heal_strength as planned (0.25 / 0.35 / 0.45) on
   leaf_litter — the lattice-prone material from A.2.
2. **Add an axis** considering whether `flux_fill` or
   `controlnet-inpaint` (technique #12) gives better high-strength
   heal results than vanilla img2img. Treat this as a "model swap"
   variant rather than a settings sweep — produce one pass with each
   inpaint model, compare against current. Out of scope if A.3 +
   plain heal sweep already lift the lattice-prone categories above
   threshold; in scope otherwise.

**For Phase B (or end of A):**

1. Build `variant_blend.py` (technique #5) — combine N variants into
   one tile. Could rescue lattice categories more cleanly than any
   prompt change.
2. Try CHORD as A/B for the texture → PBR step (technique #9).

---

## How to extend this doc

This is a **snapshot** doc. Don't append findings dated months apart —
write a new survey doc instead (e.g.,
`EXTERNAL_TECHNIQUES_2026Q3.md`) so each survey is self-contained and
dated.

If a technique listed here gets *adopted* into the pipeline, add a
one-line "**ADOPTED** YYYY-MM-DD: <short note>" line under that
technique's section, and migrate the operational details to
PIPELINE.md / TOOLS.md / TEXTURE_RND.md as appropriate.

If a technique listed here is *retired* (we tried it and it didn't
work), add "**RETIRED** YYYY-MM-DD: <reason>" and link to the
TEXTURE_RND.md entry that documents the failed experiment.
