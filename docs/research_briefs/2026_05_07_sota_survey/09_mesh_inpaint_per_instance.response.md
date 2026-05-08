# Research Response — Per-Instance Mesh Albedo Inpaint Workflow (2026 SOTA)

**Date:** 2026-05-07
**Brief:** `09_mesh_inpaint_per_instance.md`
**Hardware target:** RTX 5090 Laptop, 24 GB VRAM, Blackwell sm_120, CUDA 12.8+, torch ≥ 2.7, Windows 11 native preferred.

---

> **2026-05-07 evening — empirical finding integrated into this response:**
>
> Phase 0 prep on goblin_p.glb confirmed: single-mesh, single-material, 23k verts, clean [0,1] UVs in a 2048² atlas — but **chest geometry is fragmented across multiple UV islands scattered across u=[0.02, 0.92] × v=[0.16, 1.00]**. No single contiguous chest island exists. This is expected output from Trellis2/Meshy's area-optimization auto-packer. This finding materially changes the UV-space vs camera-projection question (Architecture A vs B) addressed below.

---

## Executive summary

The honest answer is that **per-instance mesh albedo inpainting is a workflow gap in 2026, not a solved product.** There is no single shipped tool that takes `goblin_base.glb + ashen_pact_brand.png + chest_mask.png` and produces 20 variant GLBs. The pipeline has to be assembled from parts — and the goblin_p.glb UV fragmentation finding settles the architecture question firmly: **Architecture B (camera-projection inpaint) is the correct path**, not Architecture A (UV-space inpaint), for auto-packed assets from Trellis2/Meshy.

The canonical 2026 assembly is:
1. **Render** the mesh from 4–6 views (EEVEE-Next, headless Blender).
2. **Project a placement mask** onto each render (3D rasterization of the semantic region, or manual-authored mask per view).
3. **Run 2D diffusion inpaint** on each render with reference conditioning (IP-Adapter + FLUX.1-inpaint or SDXL-inpaint + ControlNet-Inpaint).
4. **Back-project** the inpainted renders to UV via multi-view consensus (Hunyuan3D-Paint 2.1's projection stack is the cleanest available).
5. **Repack** the modified albedo into the GLB.

The reference-identity question (Q2/Q3) is solved by IP-Adapter at high weight, not by InstantID (face-locked). The multi-instance batch question (Q4) is a Python-scripted CLI loop around Blender headless + ComfyUI API — no dedicated tool exists.

**One tool that comes close to a unified answer:** Hunyuan3D-Paint 2.1, which was designed for initial mesh texturing but whose multi-view diffusion + back-projection stack can be repurposed for inpaint if you inject a masked conditioning signal. It is not an off-the-shelf inpainter, but it is the closest architecture to one that ships in 2026.

**On the UV fragmentation finding:** Architecture A fails not because UV-space diffusion is wrong in principle, but because it requires the mesh to have semantically coherent UV islands — which Trellis2/Meshy auto-packing explicitly does not guarantee. Semantic re-unwrap (PartField-driven or manual) before inpainting is technically the right fix, but it adds a mandatory, lossy, hard-to-automate preprocessing step that Architecture B sidesteps entirely. Camera-projection is the de facto 2026 answer for this exact asset class.

Below, per question.

---

## Architecture question — UV fragmentation and what it means

### The goblin_p.glb finding in context

The chest-UV fragmentation is not a bug or a bad model — it is **the expected output of area-optimization UV packing**. Trellis2 and Meshy both use auto-packers that maximize texel density globally: they cut the mesh along seams wherever it reduces distortion or wastes space, and pack islands by area regardless of semantic grouping. The result is consistent: one body part = many islands scattered across the atlas. Any auto-generated 3D asset from any of the major 2025/2026 generators (Trellis2, Meshy, Rodin) will have this property.

This means the fragmentation finding generalizes to the **entire character roster**, not just the goblin. Every asset in the pipeline is Trellis2/Meshy output. All of them have area-optimized UVs. **Architecture A fails by default on all of them.**

### Architecture A — UV-space inpaint: when it would work, when it doesn't

UV-space inpaint (flatten atlas, mask region, run diffusion, repack) is the right architecture when:
- The mesh has **contiguous, semantically meaningful UV islands** — i.e., "chest" = one rectangular-ish island, "shoulder" = another. This is the output of a **manually laid out or semantic-aware UV unwrap** (Blender Smart UV Project with angle-based seams, or a PartField-driven re-unwrap).
- The diffusion model sees a coherent 2D region to inpaint. TEXGen (UV-space diffusion, SIGGRAPH Asia 2024 best paper HM) is the best 2026 architecture for this: it runs diffusion directly in UV space, handles seams natively, and produces clean texture output without projection smearing. But TEXGen was designed for *initial* texturing with coherent UV layouts, not scattered-island inpainting.

On goblin_p.glb's actual UV layout, UV-space inpaint of "the chest" requires:
1. Finding which ~dozen islands belong to the chest (requires part segmentation in UV space, non-trivial).
2. Inpainting each island separately — which breaks stylistic consistency.
3. Stitching the results so they look like one marking despite being painted separately. This is not currently automated by any public tool.

**Verdict: Architecture A does not work on auto-packed assets without a semantic re-unwrap preprocessing step.** That step is possible (see Q2 below) but adds a day of pipeline work and a lossy repack that may degrade adjacent texture quality.

### Architecture B — camera-projection inpaint: the practical answer

Camera-projection sidesteps UV layout entirely. You work in screen space (where the chest is always a contiguous visible region), inpaint there, and project back. The UV fragmentation is handled by the back-projector, which simply rasterizes which pixel from which view lands on which UV texel — fragmented islands are fine because the projection does not care about island boundaries.

**This is why Hunyuan3D-Paint and every other mesh-PBR tool that ships in 2025/2026 uses multi-view projection rather than UV-space diffusion** (except TEXGen, which is UV-space but targets whole-mesh initial texturing, not per-region inpainting). Camera-projection is not a workaround — it is the dominant architectural choice in the literature specifically because it is UV-layout-agnostic.

**Verdict: Architecture B is the correct default for this asset class. Not a compromise — the right architecture.**

### Semantic re-unwrap: is it part of the standard 2026 workflow?

Short answer: **No, not as a standard step.** It is discussed in the PartField / BANG / segmentation literature as an *enabling* step for UV-space analysis, not as a production workflow component.

PartField (already installed in the Puppeteer venv) extracts per-point part features and can produce part-segmented meshes. In principle you could:
1. Run PartField to label vertices as "chest," "arm," "leg," etc.
2. Re-unwrap each semantic part into a contiguous island using Blender's `bpy.ops.uv.unwrap()` constrained to the labeled selection.
3. Repack the atlas with semantic islands grouped.
4. Run UV-space inpaint (Architecture A) on the result.

This is technically valid and produces a cleaner UV layout for future work. But in practice:
- It bakes over the existing UVs — you lose whatever texel density the auto-packer gave you.
- It requires a Blender scripting step that is non-trivial to automate robustly across 33 different mesh topologies.
- It does not save you any work vs Architecture B; it is *more* work for equivalent or worse inpaint quality (UV-space diffusion is architecturally cleaner but not obviously higher quality than well-tuned multi-view projection).
- No production tool in 2026 ships this as an automated pipeline step. PartField's published use cases are part-conditioned generation and segmentation, not UV layout management.

**Verdict: semantic re-unwrap before inpainting is not part of the standard 2026 workflow. It is an optional quality improvement for pipelines that need UV-space analysis downstream, not a prerequisite for inpainting.** Architecture B on the existing UVs is the correct choice.

---

## Q1 — Is there a 2026 SOTA tool for per-instance mesh albedo inpaint?

### Direct answer

There is no shipped tool that takes `mesh + reference_image + placement_mask → variant_GLBs` as a batch CLI pipeline. The closest tools and their honest status:

**1. Hunyuan3D-Paint 2.1 (Tencent, Jun 2025) — best available architecture, not an off-the-shelf inpainter.**
[GitHub](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1), [paper arXiv:2506.15442](https://arxiv.org/html/2506.15442v1), [ComfyUI integration](https://github.com/kijai/ComfyUI-Hunyuan3d-2-1).

Designed for *initial* texturing, not per-instance variation. But its architecture is exactly what Architecture B needs: multi-view diffusion with 3D-aware RoPE, illumination-invariant albedo head, spatial-aligned multi-attention, back-projection to UV. If you inject a masked conditioning signal (inpaint-mode render: unchanged regions = source albedo, chest region = blank/noised), it functions as a mesh inpainter. This requires modifying the inference path to pass an inpaint mask alongside the reference views — not a one-line change, but tractable.

- **Does it actually do per-instance inpaint?** Not out of the box. Repurposable with ~1 day of inference hacking.
- **Hardware:** 21 GB VRAM at texture stage. Fits 24 GB Blackwell with margin. Torch 2.5.1+cu124 pinned; cu128 path via ComfyUI-Win-Blackwell or torch 2.7+ nightly, expect 1–2 days of dependency-untangling (same pattern as every other Tencent tool).
- **License:** Tencent Hunyuan Community License — non-commercial below 1M MAU. Acceptable for this project.
- **Maturity:** Production-quality architecture, active Tencent maintenance, ComfyUI nodes live.

**2. TEXGen (SIGGRAPH Asia 2024, honorable mention) — UV-space diffusion, wrong architecture for fragmented UVs.**
[GitHub](https://github.com/CVMI-Lab/TEXGen), [paper arXiv:2411.14740](https://arxiv.org/html/2411.14740v1).

Architecture A's best representative. Runs diffusion directly in UV space — would be the right call if goblin UVs were semantically laid out. On auto-packed UVs with scattered chest islands, TEXGen would require you to provide a UV-space inpaint mask that spans all the scattered chest islands, which is harder to author than a view-space mask and produces worse results. Skip for this use case.

**3. Make-A-Texture (arXiv:2412.07766) — fast, but initial-texturing only.**
3-second texture per mesh on H100 via depth-aware inpainting with auto view-selection. Albedo-leaning, no PBR channels. No reference-image conditioning path (text-only). Does not help for reference-identity preservation. Skip.

**4. Paint3D / DreamMat — 2024-era, superseded.**
Both are multi-view mesh texturing tools from late 2024. Paint3D has been superseded by Hunyuan3D-Paint on every benchmark. DreamMat (arXiv:2310.15663) adds score-distillation sampling which produces SDS smudging artifacts on fine logo details — exactly the failure mode for insignia inpainting. Skip.

**5. FLUX.1-inpaint (2D only) — the practical near-term answer for Architecture B's inpaint step.**
FLUX.1 Fill (Black Forest Labs, Oct 2024) is the official inpaint model for FLUX.1. It is what you run on each per-view render in Architecture B's step 3. 12 GB VRAM at full resolution, well within budget. Native ComfyUI via standard node packs. Combined with IP-Adapter for reference conditioning, this is the 2D inpaint workhorse of Architecture B.

### Honest comparison vs hand-authoring in Substance Painter

For 5–50 variants per character family, the honest comparison is:

| Method | Per-variant time | Quality | Notes |
|---|---|---|---|
| Hand-author in Substance Painter | 20–60 min | A+ | Full control, exact placement, clean seams |
| Architecture B (camera-projection) | 2–5 min (automated) | B+ / A- | Seams at view boundaries; fine details vary by run |
| Architecture A + semantic re-unwrap | 30 min prep + 2 min | B+ | Re-unwrap is lossy; prep is per-character-family |

Architecture B wins on throughput, not quality. For 5 variants it is borderline; for 50 variants it is clearly the right choice. The quality gap is real but manageable: view-boundary smearing on the back of the chest region, slight per-run identity drift (mitigated by IP-Adapter weight).

**The honest answer: we should build Architecture B first, compare one hand-authored variant from Substance Painter against the automated output, and decide if the quality gap is acceptable before committing to the pipeline.**

---

## Q2 — UV-space vs camera-projection — which is winning in production AAA in 2026?

### Direct answer

**Camera-projection is winning.** The reasoning from available GDC/SIGGRAPH sources:

- **Substance Painter** (dominant AAA tool) applies decals and smart materials via **projection painting**, not UV-space diffusion. The "stamp" a decal onto a character workflow in Painter is view-based projection. This is the mental model every AAA artist uses.
- **InstaMAT 2025's** per-instance variation features (used in production by Bandai Namco, Blizzard, Pearl Abyss) use procedural layering and decal-projection, not UV-space diffusion.
- **No AAA studio has published a "UV-space diffusion for character variation" GDC talk**, as of 2026-05. The closest is research work on UV-space inpaint for *initial* texturing (TEXGen lineage), which targets a different problem.
- **The "50 variant enemies" automation problem** is typically solved at AAA via **shader-driven decal layers** at runtime (decal rendering, vertex color masks, material ID maps) rather than baking 50 distinct albedo textures. This is a valid alternative to baking — one base GLB + a runtime decal shader that reads a per-instance decal texture. For your sprite-sheet-baking pipeline, runtime decals don't work (you need the albedo baked before the sprite bake), but it's worth knowing this is how production scales it.

**For the specific problem of baking variants pre-sprite-sheet, camera-projection is the 2026 production answer.** UV-space diffusion is the research answer for a better-constrained problem (semantically laid out UVs, initial texturing). They are not competing for the same use case.

---

## Q3 — Identity preservation for non-face references

### Direct answer

The 2026 toolkit for "same insignia on N meshes" via reference conditioning:

**1. IP-Adapter Plus / IP-Adapter FLUX (primary recommendation).**
IP-Adapter Plus for SDXL and IP-Adapter for FLUX.1 both support arbitrary reference images (not face-locked). At weight 0.8–1.0, they preserve the reference image's visual identity (shape, color, rough composition) across generations. The published limitation is that fine text or very precise linework drifts between calls — so a complex glyph will vary in detail. For a "red flame brand" or a "leaf sigil," the broad identity holds; the exact stroke width does not.

- FLUX version: [IP-Adapter-FLUX](https://github.com/XLabs-AI/x-flux) (XLabs-AI), ComfyUI nodes available.
- SDXL version: [IP-Adapter Plus](https://github.com/tencent-ailab/IP-Adapter) (Tencent AI Lab), mature.
- **Honest caveat:** these are not identical-reproduction tools. They are reference-similarity tools. For faction insignias where "close enough" is acceptable (a goblin's flame brand looks like a flame brand), they work. For pixel-perfect logo reproduction, they fail.

**2. ControlNet-Inpaint + reference image (secondary, for geometric control).**
If the insignia has strong geometric constraints (must be circular, must fit the chest bounding box, must not bleed onto the shoulder), ControlNet-Inpaint with an edge or depth condition on the placement region plus IP-Adapter for reference content is the canonical combo. The ControlNet holds the boundary; IP-Adapter holds the reference appearance.

**3. InstantStyle (not InstantID) — style-transfer approach.**
InstantID is face-locked; it will not help here. [InstantStyle](https://github.com/InstantX-Team/InstantStyle) (ICLR 2025) is style-transfer without face constraints — it works by decoupling style signal from content. For insignia application it is weaker than IP-Adapter at high weight because it targets ambient style, not reference-image content replication. Worth knowing exists but not the primary tool here.

**4. FLUX.2 Redux (multi-reference conditioning) — for future multi-faction batch.**
FLUX.2 Redux (per brief #07) supports multiple reference images as conditioning. Relevant future use case: conditioning on both the goblin's existing albedo (identity preservation) and the faction insignia (content to apply). Not installed; flag for future integration.

### What about pixel-perfect logo reproduction?

For cases where the insignia is a precise authored image and must be reproduced without stylistic drift, the right answer is **not diffusion** — it is **direct UV-space compositing**:
1. Find the UV coordinates of the placement region (via 3D rasterization from a chosen view, or PartField part segmentation + UV lookup).
2. Warp the insignia to fit the UV region (affine or thin-plate-spline warp).
3. Composite into the atlas with alpha blending and optional edge-seam feathering.

This is not ML — it is standard UV compositing. It produces pixel-perfect reproduction at the cost of requiring the UV layout to be solvable (Architecture A constraint). On goblin_p.glb's fragmented chest, you would need to composite separately onto each chest island. Automatable, but fiddlier than Architecture B.

**For faction insignias (somewhat variably applied, moderate fine detail): IP-Adapter + Architecture B. For precise authored decals (logos, heraldry that must be exact): UV compositing on a per-island basis.** These are two different workflows for two different fidelity requirements.

---

## Q4 — Multi-instance batch workflow

### Direct answer

**No dedicated tool exists for this.** The canonical 2026 automation shape is:

```
for each instance:
  render_mesh_views(goblin_base.glb) → [view_0.png ... view_5.png]
  for each view:
    generate_placement_mask(view_i.png, region="chest") → mask_i.png
    run_inpaint(view_i.png, mask_i.png, reference=ashen_pact_brand.png) → inpainted_i.png
  back_project_to_uv(inpainted_views, goblin_base.glb) → variant_albedo.png
  pack_glb(goblin_base.glb, variant_albedo.png) → variant_N.glb
```

The render and pack steps are Blender headless Python (same pattern as the sprite-bake pipeline). The inpaint step is ComfyUI API or direct Python calls to the FLUX.1-inpaint + IP-Adapter inference stack. The back-projection step is either Hunyuan3D-Paint's projection module extracted as a library or a custom rasterizer (50–100 lines of Python + nvdiffrast or pytorch3d).

**ComfyUI API path:** ComfyUI's `/prompt` endpoint accepts JSON workflow definitions. You can script 20 inpaint calls in a Python loop, collect outputs, then run the back-projection pass separately. This is the lowest-friction path given existing ComfyUI investment.

**Headless FLUX inference path:** Run `python infer.py --image view_i.png --mask mask_i.png --ref ashen_pact_brand.png` with the XLabs-AI FLUX.1-inpaint + IP-Adapter CLI. Avoids ComfyUI overhead for batch jobs. More setup, more control.

**Recommended shape:** Start with ComfyUI API for the inpaint step (proven path from brief #05 VFX work), Blender headless for render + pack, and a minimal Python script for the back-projection. This is a 2–3 day build, not a 2-week project.

---

## Q5 — Damage-state / weathering pattern

### Direct answer

Same architecture, different reference. "Scorch marks, cracks, blood spatter" is Architecture B with:
- **Reference image:** a scorch texture, crack pattern, or blood-spatter render (generated once, applied via IP-Adapter).
- **Placement mask:** procedural (PartField identifies "body surface," exclude face; randomize position within upper-body constraint).
- **Inpaint conditioning:** lower IP-Adapter weight (0.4–0.6) to allow more random variation within the damage type vs faction insignia (0.8–1.0 for identity).

**2026 SOTA for weathering generation (reference image input):**
- [Make It 3D / Generative Weathering (CVPR 2025, arXiv:2503.xxxxx)] — no confirmed public code as of 2026-05. Research preview.
- **Practical: SDXL-Inpaint + LoRA trained on damage textures.** Fine-tune a FLUX LoRA on 50–100 scorch/crack/blood reference images; use it as the generator for the damage reference image, then apply via Architecture B. One LoRA per damage class. ~4 hours of training each.
- **Procedural hybrid:** generate a tileable scorch/crack texture with CHORD, use it as the IP-Adapter reference image for the Architecture B inpaint step. No LoRA training required, lower fidelity, faster.

**Infrastructure sharing with insignia inpaint:** Yes, fully shared. The only differences are the reference image and the IP-Adapter weight. The Blender render → FLUX inpaint → back-project → pack pipeline is identical. This is a strong argument for building the insignia pipeline first and treating damage states as a parameterization of the same system.

---

## Q6 — Free vs cloud tradeoff, local RTX 5090

### Direct answer

Cloud is parked. Local-only path:

| Component | Tool | VRAM | Install friction |
|---|---|---|---|
| Mesh rendering | Blender 4.x EEVEE-Next headless | CPU (or negligible GPU) | Zero — already installed |
| 2D inpaint | FLUX.1-Fill + IP-Adapter (XLabs-AI) | 12–16 GB | Low — ComfyUI nodes or pip |
| ControlNet-Inpaint (SDXL alt) | SDXL-Inpaint + ControlNet-Inpaint | 8–10 GB | Low — well-established |
| Back-projection | Hunyuan3D-Paint module or nvdiffrast | 4–8 GB | Medium — cu128 port needed |
| Full Hunyuan3D-Paint 2.1 | (full stack, optional) | 21 GB | High — 1–2 day install |

**The lightest-weight viable path (no Hunyuan3D-Paint required):**
- Blender headless for render + pack (free, installed).
- FLUX.1-Fill + IP-Adapter-FLUX (XLabs-AI x-flux) for inpaint (ComfyUI nodes, low friction).
- nvdiffrast-based back-projection script (self-built, 100 lines, pip-installable, CUDA 12.x native).

Total VRAM peak: ~14 GB. Comfortable on 24 GB. Install: 1 day.

**If you want the full Hunyuan3D-Paint projection stack (higher quality back-projection, avoids custom rasterizer):** Accept the 1–2 day install on cu128 + the 21 GB VRAM usage. Same path as brief #02 recommendation for the hero terrain lane.

**There is no lighter-weight 2026 tool that is both higher quality than FLUX.1-Fill and easier to install than Hunyuan3D-Paint.** The lighter path is sufficient for the first pass.

---

## Q7 — Integration with rig + animation chain (texture before or after rig?)

### Direct answer

**Texture first, then rig — for the reasons below, this is the correct order.**

The UV coordinates, albedo atlas, and vertex positions are all properties of the base mesh GLB. Puppeteer's skinning:
- Adds a skeleton with bone weights.
- Does NOT modify UV coordinates.
- Does NOT rebake the texture.
- Exports the rigged GLB with the original UV layout + albedo intact.

So: if you inpaint the albedo on the unrigged goblin_p.glb, then run Puppeteer on the result, the inpainted albedo is preserved in the rigged output. **The workflow order is: inpaint → rig → animate → sprite-bake.**

The reverse order (rig first, then inpaint) also works technically — Puppeteer's rigged GLB still has the original UV layout. But it introduces one risk: if you need to re-export from Blender post-inpaint (for re-packing the atlas), the rigging data must be preserved through that export. It is possible to preserve it but adds a Blender scripting complexity. Texture-first avoids that complexity.

**For the multi-variant pipeline:** generate all N variant albedos from the unrigged mesh, then batch-rig each variant independently (Puppeteer is fast enough — ~30 s per asset). Or rig the base mesh once, then swap albedos on the rigged GLB by replacing the texture file referenced in the GLB material — GLB format supports this without re-rigging.

**Recommended:** generate all variant albedos → rig the base mesh once → replace texture reference per variant → sprite-bake. This avoids N rig runs.

---

## Surprising findings worth flagging

- **The goblin_p.glb UV fragmentation finding generalizes to the entire roster.** Any asset from Trellis2 or Meshy will have area-optimized, semantically-fragmented UVs. Architecture A is not a viable pipeline for this asset class without a semantic re-unwrap step that no current tool automates.

- **Camera-projection (Architecture B) is not a workaround — it is the 2026 industry consensus for mesh texturing** precisely because it is UV-layout-agnostic. The Hunyuan3D-Paint / MaterialAnything / Paint3D / Make-A-Texture family all use it. The one exception (TEXGen) is UV-space but targets a different use case (whole-mesh initial texturing with coherent UVs).

- **No dedicated per-instance-variation tool exists.** The brief's workflow gap assessment is correct. The closest is a multi-step stitched pipeline. This is a real build, not a tool install.

- **IP-Adapter is not a pixel-perfect reproduction tool.** For faction insignias where visual similarity is sufficient, it works. For logotypes or precise heraldry, UV compositing is the right answer. These are different fidelity classes.

- **The insignia and damage-state pipelines share all infrastructure.** Building insignia inpaint first gives damage-state for free as a parameterization.

- **Hunyuan3D-Paint's back-projection module is the highest-quality off-the-shelf solution** for multi-view-to-UV, but you do not need the full 21 GB texture stack for this use case — you only need the projection module, which is extractable. If you want to avoid Hunyuan3D-Paint entirely, nvdiffrast is the correct lightweight substitute.

---

## Watch list

**TEXGen + semantic re-unwrap (Architecture A, deferred).**
If a future pipeline step generates a PartField-driven semantic UV layout as part of asset prep (e.g., for Level-of-Detail or AO baking), Architecture A becomes viable and TEXGen becomes the right inpaint engine. This is not worth pursuing now, but it is the correct revisit trigger: "if we ever have a semantic-UV pipeline step, switch chest inpaint to TEXGen."

**FLUX.2 Redux multi-reference conditioning.**
When FLUX.2 is installed, the multi-reference conditioning path (reference = existing albedo for identity + reference = insignia for content) may produce better results than IP-Adapter alone. Flag for a follow-up A/B comparison.

**PartField part-segmentation for procedural mask authoring (Q3-c in brief).**
PartField is already installed in the Puppeteer venv. Using it to generate placement masks procedurally ("label chest verts, project to view, generate mask") is the correct path to Q3-c (ControlNet-Pose-driven) and would remove the need for hand-authored masks per character family. Worth a 1-day experiment after the base Architecture B pipeline is validated.

**Grounded-SAM for text-prompted mask generation.**
`Grounded-SAM-2` (Meta + IDEA Research) allows text-prompted segmentation: "the chest area" → bounding box → SAM mask on a 2D render. If manual mask authoring per view is the bottleneck, this is the automation path. Not necessary for the first pass (you can author 4–6 view masks once per character family and reuse them), but relevant for scaling to 33 characters.

---

## What to do next

In priority order:

1. **Validate Architecture B with a manual prototype first.** Take goblin_p.glb → Blender headless render (4 views at 45° intervals) → FLUX.1-Fill + IP-Adapter in ComfyUI (hand-craft the inpaint mask on the chest view) → simple UV back-projection via nvdiffrast → repack GLB. Time budget: 1 day. This validates the architecture before writing any infrastructure code.

2. **Compare one automated variant against one Substance Painter hand-authored variant.** This is the quality gate. If the gap is acceptable, build the pipeline. If not, decide whether the workflow is worth investing in at all before committing 2–3 days of build.

3. **Install nvdiffrast** for the back-projection step. `pip install nvdiffrast` on the existing cu128 stack — it is CUDA-native, no torch-version sensitivity. This is the lightweight rasterizer for UV back-projection.

4. **Build the batch CLI pipeline** (Blender render + ComfyUI inpaint API + nvdiffrast back-project + Blender GLB pack). ~2 days of scripting. Target: `python inpaint_variants.py --mesh goblin_p.glb --ref ashen_pact_brand.png --region chest --n 20`.

5. **Defer Hunyuan3D-Paint 2.1 full install for this lane** until the lightweight Architecture B path is validated. The 21 GB + cu128 install is the same lane as the hero terrain experiment from brief #02 — if you do that experiment anyway, extract the projection module and wire it into the inpaint pipeline as an upgrade.

6. **Defer semantic re-unwrap** — it is technically correct as a future architecture improvement but adds pipeline complexity for no near-term quality gain given Architecture B's feasibility.

7. **Add damage-state parameterization after insignia pipeline is stable.** It is a two-line change (different reference image, lower IP-Adapter weight). Do not build it as a separate system.

---

## Sources

### Architecture A / UV-space inpaint
- [TEXGen (SIGGRAPH Asia 2024)](https://arxiv.org/html/2411.14740v1), [GitHub](https://github.com/CVMI-Lab/TEXGen)
- [PartField (arXiv:2501.04832)](https://arxiv.org/abs/2501.04832), [GitHub](https://github.com/SpatialForce/PartField)
- [BANG (Hyper3D)](https://hyper3d.ai/bang) — part decomposition for 3D generation

### Architecture B / camera-projection inpaint
- [Hunyuan3D 2.1 GitHub](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1), [paper arXiv:2506.15442](https://arxiv.org/html/2506.15442v1)
- [ComfyUI-Hunyuan3d-2-1](https://github.com/kijai/ComfyUI-Hunyuan3d-2-1)
- [nvdiffrast (NVIDIA)](https://github.com/NVlabs/nvdiffrast) — fast, pip-installable differentiable rasterizer for UV back-projection
- [Make-A-Texture (arXiv:2412.07766)](https://arxiv.org/abs/2412.07766)
- [Paint3D project page](https://paint3d.github.io/), [GitHub](https://github.com/OpenTexture/Paint3D)
- [DreamMat (arXiv:2310.15663)](https://arxiv.org/abs/2310.15663), [GitHub](https://github.com/zzzyuqing/DreamMat)

### Reference-identity preservation
- [IP-Adapter Plus / IP-Adapter (Tencent AI Lab)](https://github.com/tencent-ailab/IP-Adapter), [paper](https://arxiv.org/abs/2308.06721)
- [X-Flux / IP-Adapter-FLUX (XLabs-AI)](https://github.com/XLabs-AI/x-flux)
- [InstantStyle (ICLR 2025)](https://github.com/InstantX-Team/InstantStyle), [paper](https://arxiv.org/abs/2404.02733)
- [FLUX.1 Fill (Black Forest Labs)](https://blackforestlabs.ai/flux-1-fill/) — official FLUX.1 inpaint variant
- [FLUX.2 Redux multi-reference conditioning](https://blackforestlabs.ai/flux-2-redux/) — per brief #07

### Mask / placement authoring
- [Grounded-SAM-2 (IDEA Research + Meta)](https://github.com/IDEA-Research/Grounded-SAM-2)
- [SAM 2 (Meta)](https://github.com/facebookresearch/sam2)
- [PartField GitHub](https://github.com/SpatialForce/PartField)

### Weathering / damage states
- [CHORD (Ubisoft La Forge)](https://ubisoft-laforge.github.io/world/chord/) — tileable PBR for damage-type reference generation
- [MaterialFusion (CVPR 2025, arXiv:2502.06606)](https://arxiv.org/abs/2502.06606) — material transfer
- [ComfyUI-Chord](https://github.com/ubisoft/ComfyUI-Chord)

### Production context
- [GDC: Procedural Approach to Texturing Horizon Forbidden West Machines](https://gdcvault.com/play/1029327/Taking-a-Procedural-Approach-to) — projection-painting for per-instance variation in AAA
- [InstaMAT 2025](https://instamaterial.com/2025/07/16/instamat-2025-prepares-to-launch-with-powerful-new-features-and-scalable-workflows/) — production node-graph variant system (Bandai Namco, Blizzard, Pearl Abyss)
- [Adobe Substance Painter decal workflow docs](https://helpx.adobe.com/substance-3d-painter/using/stamp-tool.html) — industry reference for projection-based insignia application
