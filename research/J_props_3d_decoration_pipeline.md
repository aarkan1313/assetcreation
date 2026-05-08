# Props / 3D Decoration Pipeline: Second-Pass Plan

Date: 2026-05-06  
Project: `D:\assets`, Godot 4.5 / C# asset factory  
Scope: practical plan for prop, decoration, scatter, decal, and biome dressing asset creation after `G_deep_dive_world_textures_decor_shader.md`

## Executive Recommendation

Props are only superficially similar to the character pipeline. The existing character pipeline already solves an important part of the problem: image/text-to-3D acquisition, Blender cleanup, decimation, preview rendering, and GLB handling. Reuse those mechanics. But do not treat props as "characters without rigs." A prop pipeline needs kit coherence, variants, scale/origin discipline, collision proxies, LODs, billboards/impostors, scatter metadata, placement masks, thumbnails, and Godot scene export. Characters are usually individual hero assets. Props are families of hundreds of related assets that have to survive repetition.

The right plan is a **prop kit factory**, not a generic "make one GLB" script.

Use three source lanes, with a strong local-first bias:

1. **Blender procedural generators first** for scatter and common kit pieces: rocks, pebbles, grass cards, bushes, moss tufts, mushrooms, roots, crystals, ruin blocks, debris, bones, planks, cave clutter, and simple camp props. This is the best path for repeatable, controllable, cheap, LLM-driven output.
2. **Local/open AI 3D generation second** for hard-to-model individual props, hero props, unusual silhouettes, and concept exploration. TRELLIS.2, Hunyuan3D 2.1, and Stable Fast 3D are the candidates worth testing first. Every generated mesh must go through normalization, QA, LOD, thumbnail, and license/provenance manifest.
3. **CC0 asset libraries third** as seed kits and quality references. Kenney, Quaternius, ambientCG, and Poly Haven are useful, but not all APIs have the same commercial automation terms. These are best used as imported exemplars and kit fillers, not as an untracked scrape pile.

Cloud 3D APIs such as Meshy, Tripo, and Rodin should be treated as optional bake-off baselines or emergency fallbacks, not as required infrastructure. The target pipeline can be local.

The immediate build should upgrade `pipelines/props/generate_props.py` into an asset-kit pipeline that emits:

```text
world/props/library/<prop_id>/
  prop.json
  source/
  model_lod0.glb
  model_lod1.glb
  model_lod2.glb
  collision.glb
  billboard.png
  thumbnail.png
  preview_turntable/
  materials/
  godot/<prop_id>.tscn
  qa.json

art_lab/props/kits/<kit_id>.json
art_lab/props/output/<kit_id>/
  gallery.html
  kit_manifest.json
  godot/
```

The first concrete target should be the existing `mossy_highland_ruins` kit. The biome compiler already asks for `rock_cluster_small`, `rock_cluster_medium`, `fern_clump`, `moss_tuft`, `mushroom_cluster`, `fallen_log`, `ruin_block`, and `ruin_pillar`; the prop library should provide those assets with variants and placement metadata.

## Current Local State

The local project has useful groundwork:

- `pipelines/props/generate_props.py` chains Meshy generation and existing `meshy/preprocess.py`, then writes one GLB and a small `meta.json`.
- `art_lab/biomes/tools/dress_biome.py` already compiles biome kits into masks, `scatter.csv`, `decals.csv`, preview PNG, and a Godot placement recipe.
- `art_lab/biomes/kits/mossy_highland_ruins.json` already defines the first desired scatter/decal set.
- `world/props/input_images` and `world/props/output` exist, but `world/props/output` is still empty.

The gap is not "can we generate a prop?" The gap is "can we generate a coherent, repeatable, engine-ready prop **kit** that the dressing compiler can consume?"

Current `generate_props.py` is a useful acquisition wrapper, but it is not enough because it lacks:

- variants per asset family;
- normalized scale/origin/bounding boxes;
- material simplification and texture-map conventions;
- LOD0/LOD1/LOD2;
- collision proxies;
- billboard/impostor output;
- thumbnails and turntable previews;
- scatter metadata: footprint radius, slope tolerance, density class, collision policy, render mode;
- Godot `.tscn` export;
- kit-level gallery and QA report.

## Candidate Table

| Candidate | Best Use | License / Terms | API / CLI Status | Install Difficulty | Godot Fit | Last Meaningful Update / Current Signal |
|---|---|---:|---|---|---|---|
| Blender Python + Geometry Nodes | Procedural rocks, foliage cards, debris, ruin chunks, kit variants, thumbnails, LODs | GPL app, generated outputs are usable in project | Excellent CLI/headless Python | Already installed: Blender 5.1 | Excellent via GLB and scripted exports | Blender command-line docs current for 5.x; best local automation spine |
| Existing Meshy path | Optional cloud baseline/fallback for hero/medium props | Commercial API | Existing local scripts; official REST API supports GLB and PBR refine | Already partly wired | Good after cleanup | Useful for comparison, but not needed for the local core pipeline |
| TRELLIS.2 | High-fidelity image-to-3D with PBR, future local/cloud candidate | MIT for repo/model notes; dependencies vary | GitHub code; Linux + large GPU requirement | High locally; possible via hosted API | Good if GLB/PBR export works | GitHub states 4B model, PBR materials, 24GB+ GPU; likely WSL2-only local test |
| Hunyuan3D 2.1 | Open-source image/text-to-3D with PBR textures | Open-source repo; verify model terms before commercial use | Python/GitHub | Medium-high | Good after cleanup | June 2025 release claims full model weights/training code and PBR texture synthesis |
| Stable Fast 3D | Very fast single-image reconstruction, reference-to-mesh lane | Stability AI Community License | Python/GitHub, Hugging Face/API | Medium | Good for fast prototypes, less for final kits | Official repo highlights UV unwrapping, delighting, material prediction, game integration |
| Tripo / Tripo v3.1 / P1 | Cloud text/image/multiview-to-3D, PBR, smart low-poly | Commercial API | Good via third-party API gateways and official API positioning | Easy once keyed | Good after cleanup | 2026 API docs list GLB, PBR, quad, smart low-poly, face limits |
| Hyper3D Rodin | Cloud high-quality props, PBR, multiview, texture-only | Commercial API | Official async API | Easy once keyed | Good after cleanup | Gen-2 docs cite part generation, baked normals, HD textures, polygon control |
| Kenney | CC0 game-ready filler/placeholder kits, UI-adjacent props | CC0/public domain per official support | Manual/site downloads; no strong API | Easy | Good, stylized | 2026 support page confirms commercial use and no required attribution |
| Quaternius | CC0 low-poly kit assets, especially modular ruins/sci-fi/nature | CC0 per pack pages | Manual downloads, formats include glTF/FBX/OBJ/Blend | Easy | Strong; some packs include Godot source | 2024-2025 packs have Godot source options, optimized collisions in source kits |
| ambientCG | PBR textures and surfaces for props/decals | CC0 assets; API is hobbyist/educator oriented | Public API v1/v2/v3 | Easy | Strong for materials, not prop meshes | Docs explicitly provide API but warn reliability is not enterprise-grade |
| Poly Haven | High-quality CC0 models/textures/HDRIs; reference and import | CC0 assets, but API commercial usage needs custom license/sponsorship | Public API, User-Agent required | Easy, with API terms caveat | Strong for material/model references | API docs current and explicit about metadata/downloads |
| Terrain3D Instancer | Terrain-scale placement of many meshes/cards | MIT plugin | Godot addon/API | Medium; 4.5 compatibility must be tested | Excellent if compatible | Docs explain MultiMesh-based instancing and limitations |
| Godot MultiMeshInstance3D | Direct renderer target for scatter batches | MIT engine | Native C#/GDScript API | Already available | Required core target | Godot 4.5 docs describe high-instance rendering optimization |
| ProtonScatter / other Godot scatter addons | Authored scene/cave/camp scatter fallback | Usually MIT/varies by addon | Godot plugin, mostly editor-driven | Easy-medium | Useful for scene authoring; weaker for LLM automation | Still useful, but not primary contract |

## Recommended Pipeline

### 1. Canonical Prop Manifest

Every prop should have a `prop.json`. This is the object the LLM and tools reason about.

```json
{
  "id": "rock_cluster_small_03",
  "family": "rock_cluster_small",
  "kit": "mossy_highland_ruins",
  "source_method": "blender_procedural",
  "source_prompt": "small mossy basalt rock cluster, highland ruin biome",
  "license": "project_generated",
  "scale_m": [1.2, 0.7, 1.0],
  "origin": "bottom_center",
  "footprint_radius_m": 0.75,
  "render_class": "scatter_multimesh",
  "collision": "none",
  "lods": [
    {"file": "model_lod0.glb", "max_distance_m": 25, "triangles": 1200},
    {"file": "model_lod1.glb", "max_distance_m": 60, "triangles": 450},
    {"file": "model_lod2.glb", "max_distance_m": 120, "triangles": 120}
  ],
  "billboard": "billboard.png",
  "thumbnail": "thumbnail.png",
  "placement_tags": ["rock", "slope_ok", "mossy", "ruin_edge"],
  "material_slots": ["basalt", "moss"],
  "qa": {
    "passed": true,
    "warnings": []
  }
}
```

The important bit is `render_class`. Not every prop should be instantiated the same way:

- `scatter_multimesh`: many non-colliding small assets, one mesh per family or variant bucket.
- `terrain3d_instance`: Terrain3D-managed foliage/rocks if 4.5 compatibility passes.
- `scene_prop`: medium props with collisions, scripts, multiple meshes, or interaction.
- `hero_prop`: expensive, unique, hand-reviewed.
- `decal`: projected texture, not mesh.
- `billboard_only`: distant grass/shrub/tree impostor.

### 2. Source Lanes

**Lane A: Blender procedural factories.**  
This should be the default for kit assets. Build small Python-driven factories:

- `make_rocks.py`: ico-sphere/cube-based rocks, bevels, displacement, moss material masks, clustered variants.
- `make_foliage_cards.py`: grass/fern/moss/mushroom cards from existing texture/decal assets, crossed planes or small clumps.
- `make_ruins.py`: modular stones, cracked blocks, broken pillars, arches, stairs, walls; grid-snapped variants.
- `make_debris.py`: planks, rubble, broken pottery, bones, ash piles, rope coils.
- `make_cave_details.py`: stalagmites, crystals, roots, wet stones, mineral streak decals.

Each factory should emit variants, not one asset. A single family command should create 6-20 variations with shared material grammar. This fights repetition better than AI singletons.

**Lane B: local/open AI 3D generation.**  
Use local/open models first. The order to test should be:

1. Existing local Trellis2 setup, because the repo is already present in the broader project inventory.
2. Hunyuan3D 2.1, because it is open, current, and explicitly focused on textured 3D asset generation.
3. Stable Fast 3D, because it is fast and useful for single-image reference reconstruction.
4. TRELLIS.2 if the WSL2/GPU requirements are acceptable.

AI should be used for:

- hero props: shrines, statues, portals, altars, chests, unique artifacts;
- medium props: tents, carts, campfires, signposts, ruined doors;
- concept exploration: generate 8 candidates, keep 1-2 for cleanup;
- reference-to-prop when an image exists.

Do not use AI as the source for thousands of scatter props. It creates inconsistent topology, scale, silhouette, UVs, and style. Use it to get shapes you would otherwise spend time modeling, then normalize the result. Cloud APIs remain optional baselines only; the production lane should work without Meshy.

**Lane C: CC0 library ingestion.**  
Use Kenney and Quaternius for game-ready low-poly kit coverage. Use ambientCG/Poly Haven mostly for materials, decals, scan references, and occasional high-quality prop meshes. Track license/source per asset even when CC0.

Poly Haven is attractive but its API has commercial automation caveats: the assets are CC0, but the API terms say commercial API usage requires a custom license/sponsorship and all requests need a unique User-Agent. That means: do not silently build a commercial scraper around it. Use manual downloads, local snapshots, or get permission if API integration becomes core.

### 3. Normalization and QA

All source lanes feed the same Blender normalizer:

1. Import GLB/FBX/OBJ/Blend.
2. Apply transforms.
3. Set origin to bottom-center unless explicitly interactive.
4. Normalize real-world scale.
5. Merge or split meshes according to render class.
6. Simplify material slots and pack textures.
7. Generate LOD0/1/2.
8. Generate collision proxy if needed.
9. Render thumbnail and 8-angle turntable.
10. Render billboard/impostor for distant use.
11. Write `prop.json` and `qa.json`.

QA gates should be deterministic:

- bounding box within expected category range;
- origin near ground;
- triangle budget by render class;
- texture dimensions and map presence;
- no missing materials;
- no NaN transforms;
- GLB re-import succeeds;
- thumbnail nonblank;
- collision only on approved classes;
- license/provenance present.

Visual scoring can be LLM-assisted, but not OCR-based. Use rendered contact-sheet images and compare variants by silhouette, material cohesion, recognizability, and repetition risk. The human review queue should contain only the best few assets from each family.

### 4. Godot Export Strategy

Godot 4.5 should receive two kinds of output:

1. Individual prop scenes:

```text
godot_pack/props/<prop_id>/<prop_id>.tscn
godot_pack/props/<prop_id>/model_lod0.glb
godot_pack/props/<prop_id>/materials/*.tres
```

2. Kit placement bundles:

```text
godot_pack/biomes/<kit_id>/
  kit_manifest.json
  scatter_recipe.json
  decals_recipe.json
  props/<prop_id>.tscn
```

`MultiMeshInstance3D` is the direct fallback target because Godot 4.5 documents it as the native path for rendering many instances of the same mesh. But MultiMesh has real limitations: no per-instance collision, coarse culling, and awkward LOD if one enormous MultiMesh covers too much area. The local exporter should chunk MultiMeshes by terrain region and asset family.

Terrain3D is still the best higher-level target for terrain-scale foliage/rocks if it works cleanly with the project’s Godot 4.5 target. Its docs are honest about limitations: MultiMesh instances do not get individual CPU collision and the system must mitigate culling by splitting regions. Treat Terrain3D as the target for huge decorative scatter and direct Godot MultiMesh as the guaranteed fallback.

Scene-specific placement, caves, camps, interiors, ruins, and interactable props should not be forced through Terrain3D. Use `.tscn` scenes with normal `MeshInstance3D`, static bodies, decals, lights, and scripts.

## Proposed Local Tools

Add a new local package under `art_lab/props/`:

```text
art_lab/props/
  kits/
    mossy_highland_ruins.props.json
  recipes/
    rock_cluster_small.recipe.json
    fern_clump.recipe.json
    ruin_block.recipe.json
  tools/
    prop_make_blender.py
    prop_import_ai.py
    prop_normalize.py
    prop_lod_collision.py
    prop_thumbnail.py
    prop_pack_kit.py
    prop_gallery.py
    prop_godot_export.py
    prop_review_queue.py
```

Keep `pipelines/props/generate_props.py` as a compatibility wrapper, but stop making it the center of the system. A better split:

- `prop_make_blender.py`: procedural generation from recipes.
- `prop_import_ai.py`: local/open 3D generator import adapter, with optional Meshy/Tripo/Rodin baseline hooks kept isolated.
- `prop_normalize.py`: one common Blender cleanup path.
- `prop_pack_kit.py`: resolves all family variants needed by a biome kit.
- `prop_godot_export.py`: exports prop scenes and scatter recipes.
- `prop_gallery.py`: HTML/PNG review page.

The LLM-facing interface should be recipe JSON, not raw Blender Python. Example:

```json
{
  "family": "ruin_block",
  "kit": "mossy_highland_ruins",
  "count": 8,
  "generator": "blender_ruin_block_v1",
  "style": {
    "stone": "dark basalt",
    "age": "ancient chipped",
    "overgrowth": "moss and lichen",
    "silhouette": "broken square block"
  },
  "budgets": {
    "lod0_tris_max": 1800,
    "lod1_tris_max": 700,
    "lod2_tris_max": 180
  },
  "placement": {
    "render_class": "scatter_multimesh",
    "collision": "none",
    "slope_max": 0.65,
    "footprint_radius_m": [0.4, 1.2]
  }
}
```

## Test Plan for Top Candidates

1. **Blender procedural kit smoke test**
   - Generate 6 small rocks, 4 medium rocks, 6 moss tufts, 4 fern clumps, 3 mushroom clusters, 4 ruin blocks, 2 broken pillars, and 2 fallen logs.
   - Output GLB, LODs, thumbnails, billboards, and `prop.json`.
   - Pass if all re-import into Blender, thumbnails are nonblank, and triangle budgets pass.

2. **Local/open AI prop acquisition test**
   - Generate 3 medium/hero props: `mossy ruin altar`, `weathered campsite chest`, `broken rune obelisk`.
   - Test existing Trellis2 first, then Hunyuan3D 2.1 or Stable Fast 3D.
   - Pass if the model produces real textured GLBs/meshes that Blender can normalize into LOD/collision/thumbnail outputs.

3. **Open local image-to-3D test**
   - Test whichever is most available locally first: current Trellis2 clone/import, Hunyuan3D 2.1, or Stable Fast 3D.
   - Use a clean image of one prop and compare output quality/time against the Blender procedural kit and the source reference.
   - Pass only if it produces a real GLB with materials that survives the same normalizer.

4. **CC0 kit import test**
   - Ingest one Quaternius or Kenney pack subset with explicit license metadata.
   - Normalize 10 props into `world/props/library`.
   - Pass if source/provenance is tracked and Godot preview scenes export.

5. **Biome dressing integration test**
   - Resolve every asset referenced by `mossy_highland_ruins.json`.
   - Run `dress_biome.py` on `smoketest_a` and `mythos_a`.
   - Export a Godot scene or recipe with one MultiMesh per asset family/chunk.
   - Pass if the HTML gallery shows: source props, placement masks, top-down scatter preview, and at least one 3D preview screenshot/render.

## First Kit: Mossy Highland Ruins

Build this first because the local biome compiler already expects it.

| Family | Source Lane | Variants | Render Class | Collision | Notes |
|---|---|---:|---|---|---|
| `rock_cluster_small` | Blender procedural | 8 | scatter_multimesh | none | Basalt + moss mask; varied silhouette |
| `rock_cluster_medium` | Blender procedural | 6 | scatter_multimesh / scene_prop | optional simple | Slightly larger, lower density |
| `fern_clump` | Blender procedural cards | 6 | scatter_multimesh | none | Needs wind shader compatibility |
| `moss_tuft` | Blender cards / texture decals | 8 | scatter_multimesh or decal | none | Very cheap; can be billboard/card |
| `mushroom_cluster` | Blender procedural | 5 | scatter_multimesh | none | Wet/shade placement |
| `fallen_log` | Blender procedural or AI | 4 | scene_prop | simple capsule/box | Larger, visible silhouette |
| `ruin_block` | Blender procedural + Quaternius reference | 8 | scatter_multimesh / scene_prop | optional | Core ruin detail |
| `ruin_pillar` | Blender procedural | 5 | scene_prop | simple convex | Some interactable/collidable variants |
| `moss_patch_01` | texture/decal pipeline | 6 decals | decal | none | Use existing texture tooling |
| `cracked_stone_03` | texture/decal pipeline | 6 decals | decal | none | Ground detail |
| `rune_stain_01` | shader/texture pipeline | 4 decals | decal | none | Link to magic/shader art style |

The target is not photoreal AAA hero modeling. The target is a coherent kit that looks good in repetition from gameplay camera distances and has enough variation that the terrain does not look stamped.

## Things to Drop or Avoid

- Do not make Meshy the backbone for scatter. It is too expensive and inconsistent for rocks, grass, mushrooms, and debris.
- Do not treat one generated GLB as "game-ready." It is source material until normalized, budgeted, previewed, and packaged.
- Do not use the character rigging/animation stack for props unless the prop is actually animated. Reuse preprocessing, not rig logic.
- Do not rely on GUI-only tools for canonical output. GUI tools are allowed for inspection and optional polish, but the source of truth should be JSON, GLB, PNG, and `.tscn` outputs.
- Do not import license-mixed marketplaces into the automatic pipeline without per-asset license fields. Sketchfab/OpenGameArt can be useful manually, but they are risky as automated sources because licenses vary.
- Do not scatter high-poly scans or AI hero meshes through MultiMesh.
- Do not assume Terrain3D solves collision. Use it for visual scatter first; use explicit scene props/static bodies for gameplay collision.
- Do not build Houdini/HEGo first. It may be excellent later, but Blender can generate the first kits with less setup and more controllability.

## Open Questions and Risks

- **Godot 4.5 / Terrain3D compatibility:** Terrain3D is attractive, but the Asset Library release signals Godot 4.4 support. Verify before making it mandatory.
- **Style cohesion:** AI-generated props may look sharper, noisier, or more photoreal than procedural kit props. The review queue needs a "belongs in kit" score, not just a "looks good alone" score.
- **Collision budget:** We need a project rule: scatter props generally have no collision; medium props have simple collision; hero props can have authored collision.
- **LOD strategy:** Godot automatic mesh LOD may be enough for some imported meshes, but handmade LODs and billboards are still useful for vegetation and large scatter fields.
- **Material conventions:** The texture pipeline already has strong PBR outputs. Prop materials need the same normal orientation, ORM/channel-packing rules, and preview lighting.
- **API costs and keys:** Cloud services are optional. Meshy/Tripo/Rodin/3D AI Studio/fal add cost and privacy/licensing considerations, so they should be used only as comparison baselines after the local path works.
- **Local model VRAM:** RTX 5090 Laptop is strong, but TRELLIS.2 documents 24GB+ GPU requirements and Linux testing. WSL2 may work, but this is not a guaranteed first-week dependency.

## Adoption Sequence: What to Build First This Week

1. **Create the prop library contract.** Add `world/props/library/<prop_id>/prop.json`, `qa.json`, thumbnail, LOD, collision, and Godot scene conventions. This is the core decision.
2. **Build the Blender procedural prop factory v1.** Start with rocks, moss/fern cards, ruin blocks, and broken pillars. It should take recipe JSON and emit 20-40 assets for `mossy_highland_ruins`.
3. **Build the normalizer/thumbnailer once.** Import any GLB, normalize origin/scale/materials, generate LODs, collision, billboard, thumbnail, and QA.
4. **Pack the mossy highland kit.** Resolve every asset name in `art_lab/biomes/kits/mossy_highland_ruins.json` to real prop variants.
5. **Export a visual review gallery.** HTML page with contact sheets, prop metadata, placement masks, and a pass/fail list.
6. **Wire Godot export.** Start with direct `MultiMeshInstance3D` chunked by asset family as the reliable fallback. Then test Terrain3D instancer compatibility.
7. **Run one local AI bake-off.** Existing Trellis2 vs Hunyuan3D 2.1 vs Stable Fast 3D on three medium props. Keep Meshy/Tripo/Rodin out of the critical path unless local quality is unacceptable.

## Sources

- Local: `pipelines/props/generate_props.py`
- Local: `art_lab/biomes/tools/dress_biome.py`
- Local: `art_lab/biomes/kits/mossy_highland_ruins.json`
- Local: `research/G_deep_dive_world_textures_decor_shader.md`
- Godot 4.5 `MultiMeshInstance3D`: https://docs.godotengine.org/en/4.5/classes/class_multimeshinstance3d.html
- Godot visibility ranges / HLOD: https://docs.godotengine.org/en/latest/tutorials/3d/visibility_ranges.html
- Terrain3D instancer docs: https://terrain3d.readthedocs.io/en/0.9.3/docs/instancer.html
- Blender command line manual: https://docs.blender.org/manual/en/dev/advanced/command_line/index.html
- Meshy Text-to-3D API: https://docs.meshy.ai/en/api/text-to-3d
- Microsoft TRELLIS.2 GitHub: https://github.com/microsoft/TRELLIS.2
- Tencent Hunyuan3D 2.1 GitHub: https://github.com/tencent-hunyuan/hunyuan3d-2.1
- Stability AI Stable Fast 3D GitHub: https://github.com/Stability-AI/stable-fast-3d
- Hyper3D Rodin API overview: https://developer.hyper3d.ai/api-specification/overview
- Hyper3D texture generation API: https://developer.hyper3d.ai/api-specification/generate-texture
- Tripo API docs via 3D AI Studio: https://www.3daistudio.com/Platform/API/Documentation/3d-generation/tripo
- 3D AI Studio generation overview: https://www.3daistudio.com/Platform/API/Documentation/3d-generation
- Kenney support/license FAQ: https://kenney.nl/support
- Quaternius Modular Sci-Fi Megakit page: https://quaternius.com/packs/modularscifimegakit.html
- ambientCG docs/API: https://docs.ambientcg.com/ and https://docs.ambientcg.com/api/
- Poly Haven API terms summary: https://polyhaven.com/our-api
