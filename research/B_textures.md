# Assignment B - Tileable Textures and PBR Materials

Date: 2026-05-06  
Scope: best current pipeline for sourcing, generating, repairing, deriving, and exporting tileable PBR material sets for the existing `pipelines/textures` workflow and Godot/Terrain3D targets.

## Executive Recommendation

Do not treat "AI texture generation" as the whole answer. The 2026 best-of-breed texture stack is a material factory with provenance, deterministic quality checks, and optional AI stages where they actually beat classical processing. The recommended stack is:

1. **CC0 source of truth:** [ambientCG](https://docs.ambientcg.com/) as the default programmatic source, with [Poly Haven](https://polyhaven.com/our-api) as a curated secondary source. Both provide CC0 assets, real PBR maps, and metadata. ambientCG is easier for bulk search/download through its v2 API. Poly Haven has stronger curation and clean downloads, but its API terms require a unique User-Agent and commercial API usage needs custom permission.
2. **AI generator:** [PATINA material generation on fal.ai](https://fal.ai/models/fal-ai/patina/material/api) for PBR-native text-to-material output. It is the most directly aligned with the need because it returns seamless PBR maps, not just a pretty albedo. Local fallback is [ComfyUI](https://docs.comfy.org/) with FLUX.1 schnell/dev or SD3.5 workflows for albedo variations, then pass those images through a PBR estimator.
3. **PBR map estimator:** [PATINA image-to-maps](https://fal.ai/models/fal-ai/patina/api) is the most practical 2026 API option for converting an existing image into basecolor, normal, roughness, metalness, and height. For local research, test [Material Anything](https://xhuangcv.github.io/MaterialAnything/) / [3DTopia MaterialAnything](https://github.com/3DTopia/MaterialAnything), which released material estimator/refiner components in 2025 and is CVPR 2025-highlight research. Keep [Materialize](https://boundingboxsoftware.com/materialize/index.php) as the old-but-useful baseline/reference.
4. **Seamless repair:** implement deterministic PatchMatch/quilting-style edge repair plus multiband blending and seam metrics. AI tiling is useful for generation, but deterministic tile repair is cheaper, testable, and easier to run locally. Use Adobe Substance 3D Sampler's [Make it Tile](https://experienceleague.adobe.com/en/docs/substance-3d-sampler/using/filters/tools/make-it-tile) and Image to Material output as the quality bar, not as the first automated dependency.
5. **Engine export:** output both Godot `StandardMaterial3D`/`ORMMaterial3D` resources and Terrain3D channel-packed textures. Terrain3D expects two packed files per texture set: albedo RGB + height A, and normal RGB + roughness A, and supports up to 32 texture sets ([Terrain3D texture prep](https://terrain3d.readthedocs.io/en/latest/docs/texture_prep.html), [texture painting](https://terrain3d.readthedocs.io/en/stable/docs/texture_painting.html)).

The practical target is not "generate any texture from a prompt." It is: given a needed material name such as `mossy basalt cliff`, find the best CC0 candidate, score it for seams and map completeness, repair or regenerate only when needed, package it for Godot, and save provenance so later automation can trust the result.

## Current Local Pipeline Fit

`pipelines/textures/process_texture.py` is a useful baseline. It can take a source PNG, resize it, optionally make it seamless with an offset/blend trick, create an albedo map, derive a Sobel-style normal map, infer roughness/AO heuristically, and emit a Godot material resource. That is enough for a prototype, but not enough for "best of the best" visual quality.

The main gaps are:

- **No provenance or catalog ingestion.** There is no material manifest, license record, source URL, physical scale, category, or map completeness tracking.
- **Weak seamless algorithm.** Offset/blend hides borders by smearing content into the center. It is acceptable for noise-like stone, poor for bricks, tiles, wood planks, fabric, and anything with directional structure.
- **No de-lighting.** A photo with baked shadows/highlights becomes an albedo map with lighting artifacts. Roughness and normals then inherit those artifacts.
- **Heuristic PBR maps.** Sobel normals and luminance-derived roughness/AO are serviceable placeholders. They are not physically reliable.
- **No engine-specific packing.** Godot can use separate maps, but Terrain3D wants packed albedo+height and normal+roughness files for efficient terrain material sets.
- **No QA loop.** There should be a seam score, 2x2 tile preview, sphere/plane preview, normal orientation check, color-space check, and map sanity ranges before the asset is accepted.

The lowest-risk upgrade path is to keep the existing script but split it into stages: `ingest`, `normalize`, `seamfix`, `derive_maps`, `pack_godot`, and `preview_qa`.

## Tool Survey

| Tool / source | Role | License / automation | Why it matters | Caveat |
|---|---|---|---|---|
| [ambientCG API](https://docs.ambientcg.com/api/v2/) + [license](https://docs.ambientcg.com/license/) | Primary CC0 PBR library | CC0 assets; v2 API has `full_json`, `downloads_csv`, and download links | Best default downloader because it exposes metadata and downloadable files directly | Maintainer warns the API is hobbyist/educator oriented, not enterprise-stable |
| [Poly Haven API](https://polyhaven.com/our-api) + [license](https://polyhaven.com/license) | Curated CC0 textures | CC0 assets; public API includes assets, metadata, download URLs, hashes, file sizes | High trust, clean files, strong curation | API commercial usage requires custom permission/sponsorship; unique User-Agent required |
| [TextureCan](https://www.texturecan.com/terms/) | Manual CC0 fallback | CC0 terms, no attribution required | Good for specific material categories and procedural/SBSAR-style entries | No obvious first-class bulk API |
| [CGBookcase](https://www.cgbookcase.com/textures?category=All) | Manual CC0 fallback | CC0 PBR texture library | Useful extra coverage, often has full PBR sets | Automation is weak compared with ambientCG |
| [ShareTextures license](https://www.sharetextures.com/p/license) | Manual fallback only | Custom CC0-like license with restrictions | Good library, commercial use allowed | Explicitly disallows automated downloads and embedding direct downloads in third-party apps without permission |
| [PATINA image-to-maps](https://fal.ai/models/fal-ai/patina/api) | Cloud PBR estimator | Commercial API; generates basecolor, normal, roughness, metalness, height | Most practical current API for turning an image into maps | Paid/cloud dependency; outputs need validation |
| [PATINA text-to-material](https://fal.ai/models/fal-ai/patina/material/api) | Cloud AI material generator | Commercial API; tileable PBR material output | Best direct fit for prompt-to-seamless-PBR | Less controllable than curated scanned sources |
| [ComfyUI](https://github.com/comfy-org/ComfyUI) | Local generation backend | GPL app/backend; model licenses vary | Strong local graph runner/API for FLUX/SDXL/SD3.5 workflows | Not PBR-native; tileability and maps depend on workflow/custom nodes |
| [FLUX.1](https://github.com/black-forest-labs/flux) | Local/open-weight image generator | schnell is Apache 2.0; dev is non-commercial ([BFL dev terms](https://bfl.ai/legal/non-commercial-license-terms)) | Best local prompt-image family to test for albedo generation/variation | Needs tiling workflow; FLUX dev cannot be production/commercial without license |
| [Material Anything](https://github.com/3DTopia/MaterialAnything) | Local research PBR estimator/refiner | Research code; check repo license before product use | Strongest open research lead for material estimation/refinement on 3D objects and textures | Install/runtime risk; likely heavier than current pipeline |
| [Adobe Substance 3D Sampler Image to Material](https://experienceleague.adobe.com/en/docs/substance-3d-sampler/using/filters/tools/image-to-material) | Human/reference tool | Subscription GUI; includes AI-powered and B2M algorithms | Quality bar for de-lighting, normal/height/roughness generation, and artist review | Not ideal as headless automation dependency |
| [Materialize](https://boundingboxsoftware.com/materialize/index.php) | Local classic map generator | Open-source GPL v3 standalone | Great reference for deterministic map generation and seamless tiling behavior | Older GUI/Unity app; not 2026 SOTA |
| [GenPBR](https://genpbr.com/) / browser PBR generators | Quick comparator | Web/API claims vary | Good sanity comparison for heuristic maps | Trust, reproducibility, and licensing/terms need review before pipeline use |

## What Is Actually SOTA In 2026

The strongest 2026 answer separates **material acquisition** from **material invention**.

For acquisition, CC0 scanned/procedural libraries are still better than prompt generation for common terrain and environment materials. Rock, mud, gravel, bark, concrete, asphalt, leaves, plaster, brick, tiles, and cloth are already covered by high-quality PBR libraries. Generated textures are useful when the target art direction is unusual, when the needed combination is missing, or when a texture must match a custom biome/faction/style.

For PBR derivation, the state of the art has moved beyond single Sobel normals. PATINA is the most practical API I found for this pipeline because it is PBR-native: it predicts material maps rather than merely creating an RGB image. Material Anything and related 2025 research like MAGE/SuperMat show where local material estimation is going: diffusion or learned models with rendering losses, decomposed albedo/roughness/metalness/normal outputs, and refinement in UV/material space. However, research SOTA is not automatically production SOTA. The winning production path is to test those models behind a replaceable interface, not make the entire texture pipeline depend on one research repository.

For seamless tiling, the best production answer is still hybrid. Diffusion models can generate tileable output, and PATINA's material generator exposes tiling controls, but repaired textures need determinism. A PatchMatch/quilting approach can copy visually similar interior patches over the seam zones while preserving edge consistency. Add multiband blending to avoid hard transitions, and run the repair on all maps as a synchronized transform so albedo, normal, height, and roughness stay aligned. Use seam metrics to decide when to use the repair. This is much more reliable than always offset/blending everything.

For artist-grade single-image capture, Adobe Substance 3D Sampler remains the best commercial reference. Its Image to Material docs describe AI-powered map generation and de-lighting, and its Make it Tile docs describe a seam-covering process for turning non-tiling materials into tiling ones. It is not the right first automated backend, but it is a very good benchmark for "does our local/API output look credible?"

## Recommended Pipeline

### Stage 1: Catalog and Ingest

Create a material manifest under something like `world/textures/catalog/materials.jsonl`. Each record should include:

- `id`, `source`, `source_url`, `license`, `downloaded_at`
- `category`, `tags`, `physical_size_m`, `resolution`
- paths for `albedo`, `normal`, `roughness`, `height`, `ao`, `metallic`
- `seam_score`, `map_score`, `preview_path`, `accepted`

Default ingestion should query ambientCG using `/api/v2/full_json` or `/downloads_csv`, filter `type=Material`, and download only known categories needed by the game. Poly Haven should be second because of its API requirements and stronger commercial usage caveat. ShareTextures should not be scraped because its license page explicitly restricts automated downloads.

### Stage 2: Normalize

Normalize naming, resolution, color spaces, and map orientation:

- Albedo/basecolor stays sRGB.
- Normal/roughness/height/AO/metallic are linear data.
- Normal maps must be OpenGL +Y for Godot/Terrain3D unless explicitly converted.
- Resize maps together with high-quality filtering.
- Preserve exact seed/source metadata for generated outputs.

The script should reject suspicious map sets: inverted normals, roughness maps with almost no variance, metallic maps on non-metal categories, height maps with hard borders, and albedo maps with visible shadows.

### Stage 3: Seam Repair

Implement a tiered seamless strategy:

1. Run a seam score before touching anything: compare left/right and top/bottom edges over several bands, plus a 2x2 preview score after tiling.
2. If score is already good, do nothing.
3. For noise-like materials, current offset/blend is acceptable.
4. For structured materials, use PatchMatch/quilting seam zones: find patches inside the image that match both sides of the seam, paste in seam cover regions, and multiband blend.
5. Apply the same spatial operation to every map, not just albedo.
6. Re-score and keep original plus repaired variant.

Do not make diffusion the default seam fixer. Diffusion can change identity, scale, and feature alignment. Use it for regeneration or variation, not silent repair of a trusted scanned source.

### Stage 4: PBR Generation / Estimation

Use a three-tier PBR derivation stack:

1. **Known PBR sources:** if ambientCG/Poly Haven already supplies maps, trust those maps first after QA.
2. **Deterministic baseline:** improve the local script with Materialize-style operations: height from luminance/frequency separation, normals from height with configurable strength, AO from blurred height/curvature, roughness from category presets plus albedo contrast/saturation. This gives free, stable output for any texture.
3. **SOTA estimator:** call PATINA image-to-maps for candidate textures missing maps, and test Material Anything locally for high-value material categories. Keep both behind an interface that returns the same five-map bundle.

PATINA should be tested immediately because integration is small and the API is explicitly built for image-to-PBR. Material Anything should be tested as a research branch because it may eventually be the best local no-cloud estimator, but dependency and runtime risk are higher.

### Stage 5: Godot and Terrain Export

Export two formats:

- **General mesh material:** `.tres` using `StandardMaterial3D` or `ORMMaterial3D`. Godot docs note that `StandardMaterial3D` uses separate ambient occlusion, roughness, and metallic maps, while `ORMMaterial3D` uses a packed occlusion/roughness/metallic map. Generate both if cheap.
- **Terrain3D material set:** packed `albedo_height.png` and `normal_roughness.png`, matching Terrain3D's channel packing. This directly supports height blending and roughness on terrain.

Also generate a 2x2 tiled preview, a lit sphere preview, and a flat plane preview. The preview is not decoration; it is the automated QA artifact the LLM can inspect later.

## Test Plan for Top Candidates

Test on five categories because failures differ by structure:

1. `rock_noise`: granite/basalt, stochastic texture.
2. `ground_organic`: mud/leaf litter/moss, stochastic but color-complex.
3. `wood_directional`: planks or bark, directional structure.
4. `brick_grid`: regular manufactured pattern.
5. `metal_panel`: high roughness/metalness sensitivity.

For each category, create the following candidates:

- ambientCG/Poly Haven native PBR set.
- Current local pipeline output.
- Local deterministic v2 output.
- PATINA image-to-maps from albedo.
- PATINA text-to-material from prompt.
- Optional Material Anything output if install succeeds.
- Optional Substance Sampler manual reference for one representative asset.

Score them with:

- seam delta across edges and in 2x2 tiled preview,
- map completeness and expected range,
- normal consistency under OpenGL +Y,
- roughness plausibility under one fixed HDRI/light setup,
- Terrain3D packed import success,
- visual inspection at 1m, 5m, and 20m in Godot.

Acceptance rule: CC0 native PBR wins when available and visually clean. PATINA wins only if it improves map plausibility or fills missing maps without damaging identity. Diffusion-generated albedo wins only when the desired material is not available in the libraries.

## LLM and UX Layer

The LLM should not manually invent shader settings every time. It should operate through tool-like actions:

- `find_material("mossy basalt cliff", target="terrain3d", style_tags=["dark", "wet"])`
- `generate_material(prompt, maps=["basecolor","normal","roughness","height"], seamless=true)`
- `repair_seams(material_id, method="auto")`
- `pack_for_godot(material_id, target="terrain3d")`
- `show_preview(material_id, mode="2x2")`

The user-facing control should be a compact material browser: search, category filters, source/license badge, map completeness badges, seam score, accept/reject, and "make variant" action. Avoid a giant prompt box as the primary UI. The best workflow is browse-first, generate-only-when-needed.

## Integration Effort

Recommended order:

1. **ambientCG downloader + manifest:** 3-5 hours. Adds immediate value and avoids generating textures that already exist.
2. **Texture QA previews and seam score:** 3-6 hours. This makes the pipeline measurable.
3. **Deterministic map v2:** 4-8 hours. Improves local output without cloud or heavy models.
4. **Terrain3D packing:** 2-4 hours. Small, high-value export addition.
5. **PatchMatch/quilting seamless repair:** 4-10 hours depending quality target.
6. **PATINA adapter:** 2-4 hours once API key handling is decided.
7. **Material Anything local experiment:** 6-16 hours depending dependency friction and GPU.
8. **ComfyUI generator path:** 4-12 hours if ComfyUI is not already installed and working.

## Risks and Tradeoffs

- **License risk:** CC0 does not mean all APIs can be used commercially at scale. Poly Haven API usage and ShareTextures automation restrictions must be respected.
- **Cloud dependency:** PATINA is attractive because it is aligned to the job, but it introduces cost, key management, data upload, and availability risk.
- **AI map plausibility:** A generated normal or roughness map can look good and still be physically wrong. Always preview under controlled lighting.
- **Seam repair can destroy structure:** Bricks, tiles, planks, and fabrics need structure-aware repair. Simple blending is not enough.
- **Model churn:** 2026 models will keep changing. Keep adapters replaceable and store outputs/provenance, not just prompts.
- **Engine mismatch:** Godot, Terrain3D, Blender, and glTF differ in channel packing and normal conventions. Export presets should be explicit.

## Starter Kit

Use this as the first implementation slice:

- **One CC0 source:** ambientCG v2 API. It has the best balance of license clarity, metadata, and downloadable material sets.
- **One AI generator:** PATINA text-to-material. It is PBR-native and exposes seamless material outputs, which beats generic image generation for this exact job.
- **One PBR-map estimator:** PATINA image-to-maps first; Material Anything as the local research candidate once the basic pipeline is stable.
- **One seamless-fix algorithm:** PatchMatch/quilting seam-zone repair with multiband blending and automatic seam scoring.

That gives a strong 2026 pipeline without overcommitting to fragile research code: CC0 materials when possible, deterministic repair when needed, cloud AI only where it is materially better, and Godot/Terrain3D-ready exports every time.

## Sources

- ambientCG documentation and API: https://docs.ambientcg.com/, https://docs.ambientcg.com/api/v2/, https://docs.ambientcg.com/license/
- Poly Haven API and license: https://polyhaven.com/our-api, https://polyhaven.com/license
- PATINA image-to-maps and text-to-material: https://fal.ai/models/fal-ai/patina/api, https://fal.ai/models/fal-ai/patina/material/api
- ComfyUI docs and repository: https://docs.comfy.org/, https://github.com/comfy-org/ComfyUI
- FLUX official repository and license reference: https://github.com/black-forest-labs/flux, https://bfl.ai/legal/non-commercial-license-terms
- Material Anything project and code: https://xhuangcv.github.io/MaterialAnything/, https://github.com/3DTopia/MaterialAnything
- Adobe Substance 3D Sampler docs: https://experienceleague.adobe.com/en/docs/substance-3d-sampler/using/home, https://experienceleague.adobe.com/en/docs/substance-3d-sampler/using/filters/tools/image-to-material, https://experienceleague.adobe.com/en/docs/substance-3d-sampler/using/filters/tools/make-it-tile
- Terrain3D texture docs: https://terrain3d.readthedocs.io/en/latest/docs/texture_prep.html, https://terrain3d.readthedocs.io/en/stable/docs/texture_painting.html
- Godot material docs: https://docs.godotengine.org/en/latest/classes/class_standardmaterial3d.html, https://docs.godotengine.org/en/latest/tutorials/3d/standard_material_3d.html
- TextureCan, CGBookcase, ShareTextures: https://www.texturecan.com/terms/, https://www.cgbookcase.com/textures?category=All, https://www.sharetextures.com/p/license
- Materialize: https://boundingboxsoftware.com/materialize/index.php
