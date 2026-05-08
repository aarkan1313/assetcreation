# Path 2 Design — Per-Instance Mesh Albedo Inpaint Workflow

**Status:** **Phase 1 pipeline executes, quality inconclusive (2026-05-07 night).** Full GPU pipeline runs without errors: Blender 5.1 headless → FLUX.1-Fill-dev-fp8 + FLUX.1-Redux-dev (ComfyUI) → nvdiffrast back-projection → GLB repack. Output `goblin_p_ashen_live.glb` produced (3.2 MB) but visually indistinguishable from source — faction mark not legible. Root cause unknown (redux_strength too low? mask too generic? back-projection coverage too sparse?). Next: tuning pass on redux_strength, prompt, and mask generation before declaring Phase 1 quality-passing.

_Initial design (pre-brief) preserved below for context. All open questions from the original design are now answered._

**Why this exists:** the faction system, damage states, tier markings, and per-instance variant variety all collapse to the same workflow problem: take one base textured mesh + a reference asset (insignia, decal, weathering) + a placement mask, produce N variants with the asset baked into the mesh's albedo. Brief #07 didn't surface this; it's the highest-value cross-pipeline gap.

## What we want to build

```
inputs:
  base_mesh.glb              (Trellis2 / Meshy output, PBR-textured)
  reference_asset.png        (the thing being inpainted — insignia, scorch, etc.)
  placement_mask.png         (where on the UV the asset goes)
  variant_seed               (per-instance noise so variants differ within constraints)

output:
  variant_mesh.glb           (same geometry + skinning, modified albedo)

batch CLI:
  inpaint_batch.py --mesh goblin_base.glb --reference ashen_pact_brand.png \
    --mask chest_mask.png --count 20 --seed-base 1000 --out variants/
```

## Architectural shape (pending brief #09 confirmation)

Two candidate architectures. The brief is asked to identify which is 2026 SOTA.

### Architecture A — UV-space inpainting

```
1. Unwrap mesh UVs (or accept existing UVs)
2. Composite placement_mask onto UV-space layer
3. Run 2D diffusion inpaint (FLUX.2 Inpaint + IP-Adapter pointed at reference) in UV space
4. Re-export mesh with modified albedo texture
```

**Pros:**
- Deterministic per-instance.
- Pixel-perfect placement.
- No multi-view consensus pain.
- Works with the existing GLB → unwrap → repack chain.

**Cons:**
- UV seams cut up the insignia if placement spans islands.
- Quality depends on UV layout; auto-unwrapped meshes can have weird island layouts.
- Doesn't see the 3D shape; insignia might "fold" weird around curvature.

**Tooling fit:** uses 2D diffusion + ControlNet-Inpaint that we already understand. Lightest install delta.

### Architecture B — Camera-projection inpainting

```
1. Render mesh from N angles (front, 3/4 left, 3/4 right, ...)
2. Composite placement_mask projected onto each render
3. Run 2D diffusion inpaint per render (per Architecture A's stack)
4. Project inpainted views back to UV space via multi-view consensus
5. Resolve seams between projections
```

**Pros:**
- Sees 3D context — insignia drapes correctly over curvature.
- Standard for Hunyuan3D-Paint 2.1 / Make-A-Texture / Paint3D approach.
- AAA standard for "tribal markings on a complex mesh."

**Cons:**
- Multi-view consensus introduces smudging at view boundaries (same failure mode brief #02 flagged for MaterialAnything on terrain).
- Heavier compute; one inpaint becomes N inpaints.
- Needs reference identity preservation across views (each render-then-inpaint is its own diffusion call).

**Tooling fit:** Hunyuan3D-Paint 2.1 (queued install per brief #02 hero_mesh lane); could share infrastructure.

### Architecture C — Hybrid (placeholder)

Brief #09 may surface a hybrid: e.g. **UV-space inpainting using a 3D-aware diffusion** that knows the mesh shape during the 2D inpaint pass. **Open question — whether such a model exists in 2026.**

## Reference identity preservation

We need **the same insignia** applied to N goblins, not 20 different red flames. Toolkit:

- **IP-Adapter Plus / Style-only weight types** — proven 2D path
- **FLUX.2 Redux** — multi-reference image conditioning (per brief #07)
- **InstantStyle / InstantID** — face-locked, less applicable
- **ControlNet-Tile** — tile-based reference, too generic for logos

**Likely answer:** IP-Adapter at high weight (~0.9) + ControlNet-Inpaint with the placement mask + low CFG to preserve reference faithfully. **Brief #09 to confirm.**

**Open question:** does 2026 have a tool specifically designed for "insignia/logo inpaint with identity preservation," or do we stitch existing pieces?

## Placement mask authoring

Per-faction is fine (chest center). Per-instance variation harder. Three approaches:

1. **Hand-authored mask atlas per character family.** Designer authors `goblin_chest_mask.png`, `goblin_back_mask.png`, `goblin_shoulder_mask.png` once. Pipeline picks one per variant.
2. **Procedural mask generation from part segmentation.** PartField (already in Puppeteer venv) or BANG (Hyper3D) extracts body parts; pipeline picks "upper torso" region and randomizes within.
3. **Bone-driven placement.** Use the rigged skeleton to anchor placement in pose space ("on the right pectoral").

**Likely starting point:** approach 1 (hand-authored), graduating to approach 2 if variance gets repetitive. **Brief #09 to confirm best 2026 pattern.**

## Workflow ordering question

**Open question for brief #09:** does the texture inpaint happen before or after rigging?

- **Texture-first:** Trellis2 → inpaint → Puppeteer rigs the variant mesh. Cleaner pipeline (texture is final before rig).
- **Rig-first:** Trellis2 → Puppeteer → inpaint the rigged mesh's albedo. Allows pose-aware placement but risks rigging not preserving UV coords cleanly.

Puppeteer's skinning operates on geometry + bones, not albedo — so texture should be preserved across rigging. **But:** if rigging duplicates verts (per the SkinTokens pattern noted in INSTALL_MATRIX, where input 14807 verts → output 62833 because each bone-influenced vert duplicates per-bone weight), the UV correspondence might break. **Worth verifying empirically before committing the workflow.**

## Tooling that already exists in our project

| Tool | Status | Role in Path 2 |
|---|---|---|
| Trellis2 (props/characters) | ✅ generates PBR-textured GLB | Base mesh source |
| Puppeteer (animators) | ✅ rig + skin | Post-texture rigging |
| Hunyuan3D-Paint 2.1 | ⏳ queued for hero_mesh lane (brief #02) | Architecture B candidate |
| PartField (in Puppeteer venv) | ✅ installed | Mask authoring approach 2 |
| FLUX.2 Klein 4B (in UI lane) | ✅ plumbed (brief #07) | Architecture A 2D inpaint |
| IP-Adapter | ❌ not installed | Reference identity preservation |
| ControlNet-Inpaint / Mask | ❌ not installed | Both architectures need this |

**Tooling deltas to install (regardless of architecture A vs B):**
- IP-Adapter for FLUX.2
- ControlNet-Inpaint and/or ControlNet-Mask for FLUX.2
- For Architecture B: Hunyuan3D-Paint 2.1 (which is queued anyway for hero_mesh)
- For batch automation: a thin Python wrapper, probably ComfyUI API client + a CLI on top

## Where this lives in the project

Following the established lane pattern — this is its own pipeline lane, not a sub-feature of an existing one. Proposed:

```
pipelines/character_inpaint/        (new lane)
    .venv/                          (dedicated, isolated)
    inpaint_batch.py                (CLI entry point)
    architectures/
        uv_space.py                 (Architecture A)
        camera_projection.py        (Architecture B)
    masks/                          (hand-authored placement masks per character family)
        goblin/
            chest.png
            back.png
            shoulder.png
    references/                     (per-faction insignia assets)
        ashen_pact_brand.png
        verdant_compact_sigil.png
    variants/                       (output: per-instance GLBs)
```

**Sibling to existing lanes** — doesn't pollute `pipelines/props/` or `meshy/` or `animators/`.

## Skeleton implementation plan

Phased so each milestone produces a real artifact:

### Phase 0 — proof of concept (1 day, before brief #09)

- Hand-author one insignia PNG (red flame, simple shape, 256² with alpha)
- Hand-author one placement mask for `goblin_p.glb`'s chest region (or whichever existing test mesh)
- Run a SDXL/FLUX.2 Inpaint + IP-Adapter pass in **a UI tool (ComfyUI) one-shot**, no batch wrapper, no automation
- Visually confirm the insignia ends up on the goblin's chest
- **Decision point:** does Architecture A (UV-space) work convincingly or is the seam/curvature problem fatal?

### Phase 1 — minimum batch (after brief #09 returns)

- Stand up `pipelines/character_inpaint/.venv` per the isolated-venv pattern
- Build `inpaint_batch.py` CLI wrapping the Phase 0 workflow
- Run on N=5 variants of one goblin × one faction
- Confirm identity preservation across variants

### Phase 2 — production-shape

- Add Architecture B if Architecture A's quality is insufficient
- Add part-aware mask generation (PartField-driven, approach 2)
- Add CI integration: validation that variants are derived from base; provenance logging

### Phase 3 — generalize beyond factions

- Damage states (scorch, cracks, blood)
- Tier markings (gold trim, scars)
- Set-piece encounters

## Open questions for brief #09 to refine

1. Architecture A vs B — which is current 2026 SOTA for this exact use case?
2. Does a 2026 tool exist for "insignia inpaint with identity preservation," or stitch from IP-Adapter + ControlNet?
3. Workflow ordering: texture-first then rig, or rig-first then texture?
4. Part-aware mask generation: shipping tool exists in 2026?
5. Local-only path on RTX 5090 cu128 (cloud parked)?
6. License: anything we'd want to use that has commercial-restrictive licensing?

## Why this is high-leverage

- **Faction system gets real teeth** — per-instance insignia is the actually-cool faction signal
- **Damage states / weathering use the same workflow** — one infrastructure investment, multiple gameplay payoffs
- **Variant variety** — N goblins per pack feel different without authoring N fully-distinct assets
- **Tier markings** — elites and bosses get visible differentiation
- **Reusable across character + prop lanes** — same workflow, different asset categories

## Why this is risky

- 2026 SOTA may not have shipped a clean tool for this; we may stitch ComfyUI graphs and that's brittle
- Identity preservation across variants is non-trivial; current IP-Adapter + ControlNet stack works but needs tuning per asset
- UV seams (Architecture A) and multi-view smudging (Architecture B) are both real failure modes
- Phase 0 might reveal architecture choice is harder than expected

## What we don't know yet

Until brief #09 returns:
- Whether to invest in installing Hunyuan3D-Paint 2.1 first (brief #02 says yes for hero_mesh anyway)
- Whether IP-Adapter + ControlNet-Inpaint stack on FLUX.2 actually preserves reference identity well enough
- Whether part-aware mask generation has a 2026 turnkey tool or we hand-author masks

## Recommended next move

~~**Phase 0 (1 day, before brief #09 returns).** Run a one-shot ComfyUI inpaint on `goblin_p.glb` + a hand-authored insignia PNG + a hand-authored chest mask. **The result of that single experiment determines whether Architecture A (UV-space) is viable or we need Architecture B (camera-projection).** Cheaper than waiting for the brief; informs the brief's relevance window when it returns.~~

**Brief #09 returned — Architecture A is ruled out. Skipping Phase 0 entirely; building Phase 1 batch CLI against Architecture B directly.** See section below.

---

## Brief #09 verdict (2026-05-07 evening)

Full response: [`docs/research_briefs/2026_05_07_sota_survey/09_mesh_inpaint_per_instance.response.md`](../research_briefs/2026_05_07_sota_survey/09_mesh_inpaint_per_instance.response.md).

### Architecture decision: Architecture B confirmed, Architecture A ruled out

**Architecture A (UV-space inpaint) is dead for this asset class.** The goblin_p.glb UV fragmentation finding (chest geometry scattered across u=[0.02, 0.92] × v=[0.16, 1.00]) generalizes to **every asset in the pipeline** — Trellis2 and Meshy both use area-optimization UV packers that produce semantically-fragmented atlases by design. Architecture A cannot work on any of them without a semantic re-unwrap step that no 2026 tool automates.

**Architecture B (camera-projection) is confirmed as the correct default.** This is the 2026 industry consensus for the exact reason it is UV-layout-agnostic: render from N views, inpaint in screen-space (where "chest" is always a contiguous visible region), back-project to UV. The Hunyuan3D-Paint / Paint3D / Make-A-Texture family all use it. Not a workaround — the right architecture.

### Resolved open questions

| Q | Answer |
|---|---|
| Architecture A vs B | **B, definitively.** UV fragmentation rules out A for auto-packed assets. |
| 2026 dedicated tool? | **No off-the-shelf tool.** 3-step stitched pipeline: Blender render → FLUX.1-Fill + IP-Adapter inpaint → nvdiffrast back-project → repack GLB. |
| Reference identity preservation | **IP-Adapter Plus / IP-Adapter-FLUX at weight 0.8–1.0.** Not pixel-perfect (fine linework drifts), but sufficient for faction insignias. For pixel-perfect logos: UV compositing per-island (different workflow). |
| Workflow order: texture-first or rig-first? | **Texture first, then rig.** Puppeteer preserves UV + albedo through skinning. Smart pattern: generate all N variant albedos from the unrigged mesh → rig the base once → swap texture reference per variant in GLB. Avoids N rig runs. |
| Part-aware mask gen: turnkey tool? | **Grounded-SAM-2** for text-prompted view-space mask ("the chest area" → SAM mask on render). **PartField** (already installed in Puppeteer venv) for procedural UV-space part labels. Neither is mandatory for Phase 1 — hand-author 4–6 view masks once per character family, reuse across all instances. |
| Semantic re-unwrap needed? | **No.** Architecture B sidesteps UV layout entirely. Re-unwrap is a future optimization if Architecture A's TEXGen quality is ever needed, not a Phase 1 prerequisite. |
| Hunyuan3D-Paint 2.1 needed? | **Not for Phase 1.** nvdiffrast is the lightweight back-projector (`pip install nvdiffrast`, CUDA-native, no torch-version drama). Full Hunyuan3D-Paint is an upgrade path — its back-projection module is higher-quality but 21 GB + 1-2 day install. Defer until the brief #02 hero terrain experiment installs it anyway. |
| Insignia vs damage states: same pipeline? | **Yes, fully shared.** Same Blender render → FLUX inpaint → back-project → pack pipeline. Only differences: reference image and IP-Adapter weight (0.8–1.0 for insignia identity, 0.4–0.6 for random-within-damage-type weathering). |

### Confirmed Phase 1 pipeline shape

```
inputs:
  base_mesh.glb              (unrigged; goblin_p.glb for Phase 1 validation)
  reference_asset.png        (ashen_pact_brand.png from phase_0_assets/)
  region                     (str: "chest" — drives Grounded-SAM-2 or hand-authored mask)
  count                      (int: N variants)

pipeline per variant:
  1. Blender headless → render 4–6 views (EEVEE-Next, 512² or 1024²)
  2. Per view: generate placement mask (hand-authored once per char family, or SAM-2)
  3. Per view: FLUX.1-Fill + IP-Adapter-FLUX inpaint (ComfyUI API /prompt endpoint)
  4. nvdiffrast back-project: inpainted view pixels → UV texels → variant_albedo.png
  5. Blender repack: goblin_p.glb + variant_albedo.png → variant_N.glb (texture swap, no re-rig)

post-batch:
  6. Puppeteer rig on base mesh once → rigged_base.glb
  7. Per variant: swap albedo reference in rigged GLB (GLB material texture pointer update)
  8. Sprite-bake each rigged variant as usual

entry point:
  python pipelines/character_inpaint/inpaint_variants.py \
      --mesh meshy/preprocessed/goblin_p.glb \
      --ref pipelines/character_inpaint/phase_0_assets/insignia_ashen_pact_brand.png \
      --region chest \
      --count 5 \
      --out pipelines/character_inpaint/variants/
```

### Install delta for Phase 1

| Component | Install | Where | VRAM |
|---|---|---|---|
| nvdiffrast | `pip install nvdiffrast` | `pipelines/character_inpaint/.venv` | 4–8 GB (back-project) |
| FLUX.1-Fill ComfyUI nodes | Standard ComfyUI node pack (already in ComfyUI install) | ComfyUI | 12–16 GB (inpaint) |
| IP-Adapter-FLUX (XLabs-AI x-flux) | ComfyUI nodes or pip | `pipelines/character_inpaint/.venv` | (shared with FLUX.1-Fill) |
| Blender headless bpy | Already installed in `animators/Puppeteer/.venv` | Puppeteer venv or system Blender | CPU |

Total VRAM peak: ~14–16 GB. Comfortable on 24 GB.

**No Hunyuan3D-Paint 2.1 needed for Phase 1.** Deferred to Phase 2 as quality upgrade if nvdiffrast back-projection smearing is unacceptable.

### Updated phases

| Phase | What | Status |
|---|---|---|
| Phase 0 | One-shot ComfyUI PoC (Architecture A validation) | **Skipped — brief #09 ruled out Arch A before Phase 0 ran** |
| Phase 1 | `inpaint_variants.py` batch CLI (Architecture B, nvdiffrast back-project, ComfyUI API inpaint) | **Next — ready to build** |
| Phase 2 | Quality upgrade: replace nvdiffrast back-projector with Hunyuan3D-Paint projection module | Deferred — do if Phase 1 smearing is unacceptable |
| Phase 3 | Part-aware mask gen (Grounded-SAM-2 + PartField), damage-state parameterization | Deferred — Phase 1 uses hand-authored view masks |
| Phase 4 | Generalize beyond factions (damage states, tier markings, set-pieces) | Free — same pipeline, different reference + IP-Adapter weight |
