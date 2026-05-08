# Research Response — Props / Image-to-3D Pipeline (2026 SOTA)

Date: 2026-05-07
Brief: [03_props_image_to_3d.md](03_props_image_to_3d.md)
Current default: **microsoft/TRELLIS.2-4B** (local, RTX 5090 Laptop, 24 GB).

## TL;DR — should we change the default?

**No — keep TRELLIS.2-4B as the props default.** As of May 2026 there is no released open-weights model that decisively beats TRELLIS.2-4B on the props use case (clean-image → game-ready mesh + PBR). The 2026 picture is:

- **Trellis 3** does not exist. Microsoft has not announced a successor; the only "TRELLIS" releases since the CVPR'25 spotlight are TRELLIS.2 (4B) variants. Third-party domains like `trellis3d.net`/`trellis3d.co` are hostnamed marketing wrappers, not Microsoft releases.
- **Hunyuan3D-2.5** (Tencent, April 2025, 10B params dual-stage DiT+Paint) is the closest peer. It is competitive on geometry/texture in cloud demos, but the *open-source* weight drop is partial (geometry/lightweight variants on HuggingFace; full 2.5 stack ships through the Tencent cloud). Hunyuan3D-3.0 / 3.5 are referenced in marketing material (8K PBR, 2M tris) but I could not locate official Tencent open-weight releases as of today — treat those numbers as cloud-product claims, not local-install claims.
- **Rodin Gen-2** (Hyper3D, late 2025) is the only credible *quality* upgrade for hero props, with quad-mesh output at 18K/50K faces and BANG part-aware generation, but it is cloud-only.
- The 2026 release that *does* matter for our pipeline is **Tencent HY3D-Bench** (Feb 2026, 252K watertight meshes + 240K part-decomposed) — useful if we ever want to fine-tune.

The high-leverage upgrades for our pipeline this quarter are **not** swapping the generator; they are: (a) adding **PartGen / Hunyuan3D-Part** for part-aware variation, (b) replacing **DECIMATE COLLAPSE** with **meshoptimizer** in the LOD chain, and (c) building a **multi-image conditioning** path on top of TRELLIS.2 for procedural variants.

---

## Q1 — Has anything surpassed TRELLIS.2-4B in 2026?

**Short answer:** Not for our exact use case (single-image → game-ready mesh + 4K PBR, RTX 5090 local, MIT-style license). It's lateral at best from open-source peers, and Rodin Gen-2 trades quality for cloud-only access.

### Top 3 candidates

1. **TRELLIS.2-4B (microsoft, MIT)** — *still default*. O-Voxel sparse field-free latent + 4B flow-matching transformer; CVPR'25 spotlight; full PBR including transparency. Inference + weights public on HuggingFace.
2. **Hunyuan3D-2.5 (Tencent, 10B, partial open weights)** — Dual-stage Hunyuan3D-DiT (geometry) + Hunyuan3D-Paint (texture). +15% geometric precision and +20% texture fidelity vs Tripo 2 on Tencent's own benchmark; CLIP score 0.821. Geometry + lightweight + multiview variants are open at `tencent/Hunyuan3D-2` / `tencent/Hunyuan3D-2mini`. ComfyUI nodes via `kijai/ComfyUI-Hunyuan3DWrapper` and `niknah/ComfyUI-Hunyuan-3D-2`.
3. **Rodin Gen-2 (Hyper3D, cloud-only)** — 4× mesh-quality vs Gen-1, BANG recursive part generation, **quad-mesh** output at 18K/50K density, 2K PBR + beta HD normals, ~60 s on cloud. Fal/Scenario integrations exist; no open weights.

### Hardware/install fit (RTX 5090 / Win11)

- **TRELLIS.2-4B**: confirmed working in our pipeline (Phase 11). Native Windows venv path. CUDA 12.8 / torch ≥2.7 satisfied.
- **Hunyuan3D-2.5**: ComfyUI nodes target Win11 + CUDA 12.x. Texture/material stage may still need cloud (ComfyUI native support currently shape-only, per ComfyUI Wiki). Wrapper installs ship pre-built sparse ops — historically painful on Blackwell sm_120, verify before committing.
- **Rodin Gen-2**: cloud only (fal.ai, WaveSpeedAI, Scenario, Hyper3D direct API). Not relevant for local pipeline.

### License + cost

- TRELLIS.2: **MIT**, weights free.
- Hunyuan3D-2.5 open weights: **Tencent Hunyuan Community License** (commercial use allowed but with notification + region restrictions — review carefully if shipping a game).
- Rodin Gen-2: paid cloud, per-generation credits.

### Maturity (active in 2025/2026?)

- TRELLIS.2: actively maintained; training code committed by end of 2025; community ComfyUI integrations updated through Q1 2026.
- Hunyuan3D-2.5: April 2025 release, HY3D-Bench dataset Feb 2026 — Tencent is investing.
- Rodin Gen-2: actively shipping; Gen-2 is the current product.

### Honest comparison vs TRELLIS.2-4B

| Aspect | TRELLIS.2-4B (local) | Hunyuan3D-2.5 (open weights) | Rodin Gen-2 (cloud) |
|---|---|---|---|
| Mesh quality (props) | A | A- (slightly softer detail in our Phase 11 test) | A+ (quad topology) |
| PBR texture | Good 4K | Comparable | 2K (HD beta higher) |
| Speed (1 prop, RTX 5090) | ~30s `hi_tex` | similar | ~60s cloud |
| Local install on Blackwell | ✓ (Phase 11) | ✓ (geometry only); texture iffy | ✗ |
| ComfyUI integration | ✓ visualbruno/runcomfy | ✓ kijai | ✗ |
| License clean for game ship | MIT ✓ | Hunyuan Community (review) | paid |

**Verdict:** Lateral. Don't migrate. The TRELLIS.2 ecosystem is healthier on Windows + Blackwell + open license, and our Phase 11 test already showed it dominates on speed.

---

## Q2 — Higher-quality but slower for hero props?

**Yes — Rodin Gen-2 cloud is the right hero-only upgrade.** We are already using a cloud service (Meshy) for characters, so the operational pattern exists.

### Top 2 recommendations

1. **Rodin Gen-2 (Hyper3D)** — *recommended hero path*. Quad-mesh topology at 50K faces is genuinely better than TRELLIS.2's tri-soup output if a hero prop needs further sculpt/edit. BANG part-decomposition gives natural seams (e.g. obelisk base / shaft / cap as separate components). 60s on cloud, ~$0.50–1.50/gen depending on platform.
2. **TRELLIS.2-4B `hi_tex` + Hi3DGen normal-prior pass + manual cleanup** — *local hero path*. Hi3DGen (Stable-X, 2025) is a normal-estimation + normal-regularized latent diffusion preprocessor that pushes geometric detail. ComfyUI node available (`Stable-X/ComfyUI-Hi3DGen`). Stack as: image → Hi3DGen normal → TRELLIS.2 conditioned on normal. Slower (5–10 min) but stays local + MIT.

### Hardware/install fit

- Rodin Gen-2: zero local install; API call.
- Hi3DGen: PyTorch, ComfyUI node, Win11 friendly.

### License + cost

- Rodin Gen-2: paid (≈30 credits/gen on fal, similar to Meshy's image-to-3D 20–30 credits).
- Hi3DGen: open MIT-style; HuggingFace Space available.

### Maturity

- Rodin Gen-2: shipped late 2025, current.
- Hi3DGen: active 2025 paper + ComfyUI port.

### Honest comparison

Rodin Gen-2 quad output is the only thing on this list that is *visibly* better than TRELLIS.2 `hi_tex` for a hero, and only because of topology — pixel-quality is in the same ballpark. For an obelisk-style hero prop, Rodin's part decomposition would have given us a base/shaft/cap split for free; we'd recommend it for any hero that has obvious part structure (weapon = blade/guard/grip; building = walls/roof/door).

---

## Q3 — Specialized prop generators per category?

**Mostly no specialized models for *image-to-3D*; the specialization that exists is parametric (Sloyd) or part-aware (PartGen). Vegetation is the one category where general-purpose models still struggle.**

### Top 3 by category

1. **Architecture / ruins → PartGen + TRELLIS.2** — PartGen (Meta-style multi-view diffusion that segments → completes → reconstructs each part) is the right primitive for ruins where you want stones, columns, lintels as separable parts. Pair with TRELLIS.2 for the per-part generation.
2. **Vegetation / foliage → SpeedTree or The Grove (procedural)** — image-to-3D **does not produce** game-ready foliage as of 2026. All AI image-to-3D pipelines (TRELLIS.2, Hunyuan, Rodin) produce single watertight meshes that are useless for trees with leaf cards. SpeedTree (parametric) and The Grove 3D (Blender-native, simulates growth) remain SOTA for foliage that ships.
3. **Weapons / generic props → Sloyd.ai** — parametric generators with visual editing; clean topology, UVs, LODs out of the box. Useful when you want "one weapon family with knobs" rather than "this exact reference image." Not a TRELLIS replacement, a complement.

### Hardware/install fit

- PartGen: research-grade, Linux-leaning; expect work to run on Win11 native. ComfyUI port not yet mainstream.
- SpeedTree / The Grove: native Win11.
- Sloyd: cloud webapp + downloadable assets.

### License + cost

- PartGen: research code, MIT-ish.
- SpeedTree: per-seat license (SpeedTree Games Indie ≈ $19/mo).
- The Grove 3D: ~€115 one-time, Blender add-on.
- Sloyd: free tier + paid plans.

### Maturity

- PartGen: 2024–2025 papers; not yet productionized for end users.
- SpeedTree / The Grove: industry-standard; actively maintained.
- Sloyd: active product, 2026 alive.

### Honest comparison

There is no "weapon-specific image-to-3D model" worth chasing — TRELLIS.2 + a clean concept is already strong on weapons. The actual category gap is **foliage**, and that gap won't be closed by any 2026 image-to-3D generator I found; it requires a separate parametric tool. We should plan that into the worldgen v2 pipeline rather than waiting for image-to-3D to catch up.

---

## Q4 — 2026 SOTA for procedural prop variation?

**Three viable paths, ranked by effort:**

### Top 3 recommendations

1. **TRELLIS.2 multi-image conditioning + guidance_interval sweep** — *recommended; lowest effort*. The TRELLIS.2 ComfyUI fork (`visualbruno/ComfyUI-Trellis2`) exposes a `Trellis2MeshWithVoxelAdvancedGenerator` with `guidance_interval` control (early-vs-late image conditioning). Multi-image conditioning is implemented as a tuning-free fusion (see microsoft/TRELLIS.2 issue #77, opsiclear-admin/Trellis.2.multiview). Vary seed + guidance_interval + reference subset → N stylistically-coherent variants. This is the closest open analog to "ControlNet for 3D" we have today.
2. **PartGen part-swapping** — generate a base prop with PartGen, then re-roll individual parts to get variants (e.g. ruin_block with 4 different roof fragments). Higher effort, but produces *meaningful* variation rather than just noise.
3. **Sloyd parametric variants** — for any prop family where the variation is *known* (rock_small × N seeds), Sloyd's parametric generators are honestly more reliable than image-to-3D variation. Drop the AI for these.

### Hardware/install fit

All three viable on RTX 5090 / Win11. The TRELLIS.2 multi-image path uses our existing local install — minimal incremental cost.

### License + cost

TRELLIS.2 MIT free; PartGen research-MIT; Sloyd cloud.

### Honest comparison vs current `rock_small_a01..a04` displacement seeds

Our current displacement+z-squash+subdivision seeds are *fine* for rocks. For props that need *semantic* variation (different sword pommels, different ruin stones), TRELLIS.2 multi-image + guidance_interval is the clear upgrade path because we already own the model and runtime. Build a small `trellis2_variant.py` that wraps the advanced generator, sweeps `guidance_interval ∈ {0.3, 0.5, 0.7}` and `seed ∈ N`, and dedupes by mesh hash.

---

## Q5 — 7-stage postprocess: anything stale?

**Two real upgrades (worth doing), one watch item, rest is fine.**

### Recommendations

1. **Replace `DECIMATE COLLAPSE` with `meshoptimizer` for the LOD chain** — *recommended, real win*. zeux/meshoptimizer is the de-facto industry standard (used by glTF tools, Three.js, Bevy, Godot's own glTF importer in newer versions). Key advantage: when generating LOD chains, you use the previous LOD as input for the next, which produces *smoother visual transitions* and *better attribute preservation* than re-decimating from LOD0 each time. Blender Decimate is usable but produces worse silhouettes at aggressive simplification. Wrap meshoptimizer's `simplify` Python binding (or call the CLI `gltfpack`) in the LOD stage. Expect noticeably better LOD3 silhouettes for the 50k → 1k range.
2. **Audit CoACD for the 2026 quadric-primitive paper** — *watch item*. The Knodt et al. paper "Convex Primitive Decomposition for Collision Detection" (CGF 2026) reports lower Hausdorff/Chamfer distances and ~⅓ the byte size of CoACD/V-HACD outputs. No widely-adopted open release yet, so **stay on CoACD** but track reference implementation. CoACD also added `real metric mode` in 2026-04 (concavity threshold in meters) — useful if our props mix scales.
3. **Billboard baker — keep the custom one, but evaluate IMP / Amplify Impostors** — for distant tree/ruin LOD4 sprites, MaxRoetzler/IMP (Unity-targeted but the bake logic is portable) is the most-cited open billboard impostor baker. InstaLOD's Imposterize is the commercial gold-standard (overkill at our scale).

### Maturity

- meshoptimizer: industry standard, active.
- Knodt 2026 quadric paper: research-stage, no Godot/Blender bindings.
- CoACD: active (real-metric mode added 2026-04).
- IMP: maintained.

### Honest comparison

DECIMATE COLLAPSE → meshoptimizer is a low-risk, real-win swap. The CoACD swap is *not yet justified* — wait for a published reference impl. Billboards are fine.

---

## Q6 — Multi-prop batch generation tooling?

**Nothing existing replaces our `trellis2_batch.py`; the 2026 pattern is "shared style anchor + per-prop image".** The "give me 30 medieval weapons with style consistency" workflow does not have a one-click 2026 product I can recommend — it's a pipeline of (a) style-locked concept generation in 2D + (b) batch image-to-3D.

### Top 3 recommendations

1. **Keep `trellis2_batch.py` (model-load-once) + add Hunyuan3D-2mv for multiview** — our model-load-once batch runner is already correct architecture. The 2026 add is **Hunyuan3D-2mv** (multi-view variant) on the same batch runner for any prop where we have multiple reference views from a 2D generator.
2. **Front-load with Flux/SD3.5 + IPAdapter for style-locked concepts** — solve "style consistency across 30 weapons" *upstream* in 2D: generate 30 sketch images using a single style-anchor IPAdapter image, then feed each to TRELLIS.2 batch. The 3D-side variation is then noise; the style consistency comes from the 2D sheet.
3. **Sloyd for parametric prop families** — if the family is known (30 weapons in a kit), Sloyd's parametric output is more *consistent* than any AI batch because the parameters are explicit.

### Honest comparison

There is no 2026 tool that does "give me 30 medieval weapons with style consistency" end-to-end from a single sketch. The pattern that works is: **one style-anchor image → 2D sheet generation with style lock → batch image-to-3D**. This is a pipeline change, not a tool change.

---

## Q7 — Cloud vs local economics for props in 2026

**Local has won for props. Keep Meshy only for character pipeline.**

### Numbers (May 2026)

| Service | Cost / image-to-3D | Notes |
|---|---|---|
| Meshy 6 (cloud) | 20–30 credits, plans $20–$90/mo | Pro $20/mo = 1000 credits ≈ ~33 generations |
| Rodin Gen-2 (cloud) | ~30 credits/gen (fal) | Highest hero quality |
| Trellis-2 (cloud, trellis-2.com) | 35 credits/gen | Lateral to local |
| **TRELLIS.2-4B (local, RTX 5090)** | **~$0 marginal** | Phase 11 confirmed working |
| **Hunyuan3D-2.5 (local geometry, cloud texture)** | mostly $0 | Hybrid still painful |

### Hybrid recommendation

- **Scatter / library props** (rocks, ruins, weapons family) → **local TRELLIS.2-4B batch**. We already have it; marginal cost is electricity + 30s wallclock.
- **Hero props** (the obelisk, named items) → **Rodin Gen-2 cloud** for the quad-mesh + part-decomp output. Budget ~$1/hero × ≤50 hero props/year = trivial.
- **Characters** → keep Meshy (current 30 credits remaining is enough for spot fixes).

### Honest comparison

For props specifically, Meshy is no longer competitive with local TRELLIS.2 on either quality or cost. The cloud-vs-local question for *props* is settled in favor of local. Cloud only earns its keep where it offers something local can't — which today is Rodin Gen-2's quad topology + BANG part decomposition.

---

## Concrete recommendations to implement now

In rough priority order:

1. **Keep TRELLIS.2-4B as default props generator.** No migration.
2. **Replace DECIMATE COLLAPSE with meshoptimizer in the 4-tier LOD chain.** Real silhouette win at LOD2/LOD3. Wrap `gltfpack` or the Python binding.
3. **Add a TRELLIS.2 multi-image conditioning variant path** (`trellis2_variant.py`) for procedural variation of named prop families. Use `guidance_interval` + multi-reference image fusion from `visualbruno/ComfyUI-Trellis2` advanced generator.
4. **Add Rodin Gen-2 as an opt-in hero-prop route** behind a `--hero` flag on the props CLI. Cloud fallback when an asset is tagged hero in `prop.json`.
5. **Plan foliage outside image-to-3D.** Adopt SpeedTree or The Grove 3D for the worldgen v2 vegetation pass — image-to-3D will not solve this in 2026.
6. **Watch but don't adopt:** Knodt 2026 quadric convex decomposition, Hunyuan3D-3.0 open-weight release, any TRELLIS.3 announcement.

## Things to update post-research

Per the brief's "after response returns" section:

- `docs/pipeline_reviews/05_props.md` — add "2026 SOTA survey" subsection with the table above and the 6-item action list.
- `pipelines/props/README.md` — add the multi-image variation path and the meshoptimizer LOD swap to the planned-improvements list; add Rodin Gen-2 as documented hero-only fallback.

---

## Sources

### Generators
- [microsoft/TRELLIS.2 GitHub](https://github.com/microsoft/TRELLIS.2)
- [microsoft/TRELLIS.2-4B HuggingFace](https://huggingface.co/microsoft/TRELLIS.2-4B)
- [TRELLIS.2 project page](https://microsoft.github.io/TRELLIS.2/)
- [Microsoft Releases TRELLIS.2 — ComfyUI Wiki](https://comfyui-wiki.com/en/news/2025-12-18-microsoft-trellis2-3d-generation)
- [Tencent-Hunyuan/Hunyuan3D-2 GitHub](https://github.com/Tencent-Hunyuan/Hunyuan3D-2)
- [Tencent-Hunyuan/Hunyuan3D-2.1 GitHub](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1)
- [Hunyuan 3D-2.5 — Tencent](https://www.vset3d.com/hunyuan-3d-2-5-tencent-pushes-the-boundaries-of-3d-generation-with-ai/)
- [Hunyuan3D 2.5 paper (arXiv 2506.16504)](https://arxiv.org/abs/2506.16504)
- [Tencent-Hunyuan/HY3D-Bench](https://github.com/Tencent-Hunyuan/HY3D-Bench)
- [Rodin Gen-2 — Hyper3D](https://developer.hyper3d.ai/api-specification/rodin-generation-gen2)
- [Rodin Gen-2 review — gaga.art](https://gaga.art/blog/rodin-gen-2-review/)
- [VAST-AI-Research/TripoSG](https://github.com/VAST-AI-Research/TripoSG)
- [Hi3DGen project page](https://stable-x.github.io/Hi3DGen/)
- [Stable-X/ComfyUI-Hi3DGen](https://github.com/Stable-X/ComfyUI-Hi3DGen)
- [PartGen project page](https://silent-chen.github.io/PartGen/)
- [CSM Cube](https://3d.csm.ai/)
- [Sloyd.ai image-to-3D](https://www.sloyd.ai/image-to-3d)
- [Meshy 6 image-to-3D](https://wavespeed.ai/models/wavespeed-ai/meshy6/image-to-3d)
- [Meshy pricing](https://www.meshy.ai/pricing)

### Comparisons
- [Trellis 2 vs Meshy vs Hunyuan 3D comparison](https://trellis-2.com/blog/trellis-2-vs-meshy-vs-hunyuan-3d-comparison)
- [Best AI 3D Model Generators 2026 — TRELLIS vs Meshy vs Tripo vs Hitem3D](https://trellis2.app/blog/best-ai-3d-model-generator)
- [3D AI Pricing Comparison 2026 — Sloyd vs Meshy vs Tripo vs CSM vs Hyper3D](https://www.sloyd.ai/blog/3d-ai-price-comparison)
- [Best 3D Model Generation APIs in 2026 — 3DAI Studio](https://www.3daistudio.com/blog/best-3d-model-generation-apis-2026)

### ComfyUI integrations
- [kijai/ComfyUI-Hunyuan3DWrapper](https://github.com/kijai/ComfyUI-Hunyuan3DWrapper)
- [niknah/ComfyUI-Hunyuan-3D-2](https://github.com/niknah/ComfyUI-Hunyuan-3D-2)
- [ComfyUI Trellis2 Workflow — runcomfy](https://www.runcomfy.com/comfyui-workflows/comfyui-trellis2-workflow-advanced-structure-image-generation)
- [visualbruno/ComfyUI-Trellis2 multi-view 3D — DeepWiki](https://deepwiki.com/visualbruno/ComfyUI-Trellis2/3.3.5-multi-view-3d-generation)
- [TRELLIS.2 multi-image conditioning Space](https://huggingface.co/spaces/opsiclear-admin/Trellis.2.multiview)
- [microsoft/TRELLIS.2 issue #77 — multi-image input](https://github.com/microsoft/TRELLIS.2/issues/77)

### Postprocess
- [zeux/meshoptimizer](https://github.com/zeux/meshoptimizer)
- [InstaLOD](https://instalod.com/)
- [SarahWeiii/CoACD](https://github.com/SarahWeiii/CoACD)
- [CoACD project page](https://colin97.github.io/CoACD/)
- [Knodt et al. 2026 — Convex Primitive Decomposition (CGF)](https://onlinelibrary.wiley.com/doi/10.1111/cgf.70411)
- [MaxRoetzler/IMP — billboard impostor baker](https://github.com/MaxRoetzler/IMP)
- [InstaLOD Imposterize docs](https://docs.instalod.io/Products/InstaLOD_Studio/Mesh_Operations/Imposterize)

### Foliage / vegetation
- [SpeedTree](https://store.speedtree.com/)
- [The Grove 3D](https://www.thegrove3d.com/)
