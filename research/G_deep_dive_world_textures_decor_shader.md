# Deep Dive G - World, Decoration, UI, and Spell Shader Art Lab

Date: 2026-05-06  
Target: Godot 4.5 / C# asset factory, Windows + WSL2, Blender 5.1, Node 24, Python 3.12, RTX 5090 Laptop

## Executive recommendation

Do not build the spell/VFX shader pipeline around a claimed "AI shader generator." As of May 2026, the useful tools are either general LLMs that can write shader code when heavily constrained, web/Three.js products that do not emit a clean Godot pipeline, or node tools that generate procedural materials but still need authoring. The winning path is a first-party **Godot shader-template library with LLM parameterization**, plus a preview/bake harness and a reference importer for Shadertoy/GodotShaders/Material Maker examples.

For world maps, do not rely on image-only fantasy map generators. Build a vector/data map pipeline: height, coast, biomes, rivers, roads, settlements, political regions, labels, icons, and fog masks as separate layers. Use Mapgen4/WorldEngine/Azgaar as generators and references, but keep the canonical output in GeoJSON/JSON/SVG/PNG so Godot can render it and the LLM can inspect it.

For biome decoration, the right answer is a kit pipeline: textures + decals + prop variants + placement masks + scatter export. Use Blender Geometry Nodes for local variation and preview generation, Terrain3D/ProtonScatter for Godot placement, and CC0/API asset libraries plus Meshy/Trellis-style 3D generation only where scanned/free assets do not cover the need.

The concrete first-week build should be a "Magic/World Art Lab" that emits visual previews every time:

- `shader_id.gdshader`, a GIF/PNG preview, optional flipbook atlas, and a small `.tscn`.
- `world_map.json`, layered PNG/SVG previews, and Godot map scene data.
- `biome_kit.json`, prop GLBs/cards/decals, scatter masks, and placement JSON.
- `ui_theme.tres`, icon atlas, 9-slice panels, and sample HUD preview.

## Best candidates table

| Candidate | Link | License | API/CLI status | Install difficulty | Godot fit | Last meaningful update |
|---|---|---:|---|---|---|---|
| First-party Godot shader template library | Internal build on Godot shader language docs | Project-owned | Full CLI once built; LLM edits JSON params and templates | Medium | Excellent; canonical `.gdshader` output | Build now |
| Material Maker 1.6 | [site](https://www.materialmaker.org/), [GitHub](https://github.com/RodZill4/material-maker), [export docs](https://rodzill4.github.io/material-maker/doc/export.html?highlight=unreal+5) | MIT | GUI plus command-line export; Godot/Unity/Unreal targets | Easy-medium | Very high for procedural textures, masks, dynamic unlit shaders | 1.6 Apr 2026; moved to Godot 4.5.1 |
| Godot Shaders | [library](https://godotshaders.com/), [license](https://godotshaders.com/license/) | Per shader: CC0, MIT, or GPLv3 | No strong API; scrape/RSS/reference only | Easy | Excellent examples, direct Godot syntax | Active 2026; Godot 4.5 shaders posted |
| Shadertoy API + Godot converter | [API/how-to](https://www.shadertoy.com/howto), [Godot GLSL conversion](https://docs.godotengine.org/en/stable/tutorials/shaders/converting_glsl_to_godot_shaders.html) | Per shader license | Official JSON API; conversion requires tooling | Medium | Good for fullscreen spell masks and SDFs after porting | API current; licenses per shader |
| JangaFX IlluGen | [official](https://jangafx.com/software/illugen) | Proprietary | GUI first; export textures/flipbooks/assets | Medium | High through exported masks, flowmaps, beam textures, flipbooks | Current 2026 VFX tool |
| Refract | [official](https://www.refract.build/) | Proprietary | Web app plus MCP/API access; exports embeds, PNG/WebM/MP4 | Easy | Low for runtime Godot; useful for shader concept stills/videos only | Active 2026 |
| MaterialX | [home](https://materialx.org/index.html), [GitHub](https://github.com/AcademySoftwareFoundation/MaterialX) | Apache-2.0 | C++/Python libraries; shader generation to GLSL/WGSL/OSL/MDL | Medium-hard | Indirect; better for material interchange than 2D spells | v1.39.4 Sep 2025 |
| Mapgen4 | [demo](https://www.redblobgames.com/maps/mapgen4/), [GitHub](https://github.com/redblobgames/mapgen4) | Apache-2.0 | TypeScript/Node build; browser preview; modifiable data | Medium | High for wilderness map layers, rivers, biomes | Page modified Apr 2026; repo active 2025 |
| Azgaar Fantasy Map Generator | [app](https://azgaar.github.io/Fantasy-Map-Generator/), [GitHub](https://github.com/Azgaar/Fantasy-Map-Generator) | Generated maps free/commercial; source license must be checked | GUI first; exports SVG, PNG, GeoJSON, JSON, tiles | Medium via headless browser | Very high as reference and data source for political maps | v1.110 Jan 2026 |
| Mapshaper | [docs](https://mapshaper.org/docs/), [command reference](https://mapshaper.org/docs/reference.html) | Open-source; verify repo license before vendoring | Excellent CLI for GeoJSON/SVG/TopoJSON | Easy | High for simplifying map layers and SVG export | Docs current 2026 |
| MapLibre/OpenMapTiles/tilemaker | [MapLibre](https://maplibre.org/), [OpenMapTiles](https://openmaptiles.org/), [tilemaker](https://tilemaker.org/) | Mixed open licenses; OSM attribution/ODbL applies | Strong CLI/data formats for vector tiles | Medium | Medium for Godot, high for HTML previews/offline maps | Active 2026 |
| WorldEngine / World Orogen / Gleba | [World Orogen](https://www.orogen.studio/), [Gleba](https://calandiel.itch.io/gleba) | Mixed; often GUI/freeware | WorldEngine CLI; Orogen/Gleba GUI or downloadable | Medium | Good for world climate/tectonic references, weak direct pipeline | Orogen active 2026; Gleba updated Apr 2026 |
| Blender Geometry Nodes | [manual](https://docs.blender.org/manual/en/5.0/modeling/geometry_nodes/introduction.html), [Python API](https://docs.blender.org/api/5.0/index.html), [CLI](https://docs.blender.org/manual/en/latest/advanced/command_line/index.html) | GPL for Blender; outputs project-owned | Excellent background Python/CLI automation | Easy; already installed | Excellent for prop variants, billboards, previews, GLB export | Blender 5.x docs current 2025/2026 |
| Terrain3D instancer | [docs](https://terrain3d.readthedocs.io/en/1.0/docs/instancer.html), [Asset Library](https://godotengine.org/asset-library/asset/3892) | MIT | Godot API; manual and code placement | Medium | Excellent for terrain + foliage; 4.5 compatibility must be tested | 1.0.1 Jun 2025 for Godot 4.4 |
| ProtonScatter | [GitHub](https://github.com/HungryProton/scatter) | MIT | Godot add-on; modifier stack, scene-driven | Easy-medium | High for non-destructive scene prop scatter | 4.0 Oct 2023; aging but still Godot 4 |
| HEGo Houdini Engine for Godot | [Asset Library](https://godotengine.org/asset-library/asset/4176), [docs](https://hego.readthedocs.io/en/latest/about/introduction.html) | MIT add-on; Houdini commercial license required | Scriptable Godot API to HDAs | Hard | Powerful, but not first-week material | Major update Mar 2026 |
| Meshy API | [text-to-3D docs](https://docs.meshy.ai/en/api/text-to-3d) | Commercial | Clean REST API; GLB/FBX/OBJ/STL/USDZ; PBR refine | Easy once keyed | High after Blender cleanup/LOD | Meshy-6 docs current 2026 |
| Recraft API for UI/icons | [API](https://www.recraft.ai/api), [docs](https://www.recraft.ai/docs/api-reference/getting-started), [V4](https://www.recraft.ai/docs/recraft-models/recraft-V4) | Commercial | Raster/vector generation, vectorization, background removal | Easy once keyed | High for icons/HUD art sources | Recraft V4 Feb 2026 |

## Deep dive: procedural/AI shader generation for spells

The honest answer: there is no Godot-compatible AI spell shader generator worth making the backbone of the asset factory. Refract is the closest "text to shader" product I found with a real current workflow: it can generate shaders/scenes from text, has MCP tools, supports custom GLSL, and exports still/video/embeds. But its product model is "nothing enters your codebase" and the output target is a hosted/custom Three.js embed. That is useful for concept previews, not for a Godot runtime pipeline.

Unity Muse Texture is useful for PBR texture generation, not spell shaders. Unity Shader Graph and Unreal materials are real production tools, but adopting either as the canonical authoring layer would add translation and licensing friction without solving Godot export. MaterialX is technically strong and now includes WGSL support, but it is a lookdev/material interchange standard. It is not a fast way to make 2D magic circles, portals, dissolve shields, shockwaves, beams, or canvas_item spell overlays.

Material Maker is the best practical external shader-adjacent tool. It is built on Godot, exports Godot materials, has GLSL-defined nodes, supports dynamic unlit materials and raymarching materials, and 1.5 restored CLI export while 1.6 moved the tool to Godot 4.5.1. For this project, Material Maker should be used for procedural noise masks, animated unlit VFX materials, generated gradients, packed channels, and reusable graph references. It should not replace hand-authored Godot spell shaders because the game needs predictable shader parameters and effects that can be created from natural language by an LLM.

Shadertoy is a huge reference reservoir. The official API returns shader JSON and assets, and Godot has official guidance for converting GLSL/Shadertoy code to Godot shader syntax. The risk is licensing and performance. Every Shadertoy shader carries its own license, multi-pass buffers may not port cleanly, and many impressive shaders are too expensive or screen-space-specific. Use Shadertoy as a searchable reference corpus and testbed, not as a copy-paste source. Godot Shaders is safer for immediate use because entries are already Godot code and the site labels licenses as CC0/MIT/GPLv3, but GPL entries should be excluded from commercial pipeline ingestion.

The recommended internal shader taxonomy:

- **Canvas spell masks:** magic circles, runes, portals, shockwaves, trails, screen distortions, dissolves. Target `canvas_item`.
- **Spatial spell materials:** force fields, shields, emissive crystals, energy weapons, world-space decals, water/lava surfaces. Target `spatial`.
- **Particle process shaders:** orbitals, sparks, embers, radial blasts, lightning particles, subemitters. Target Godot GPU particle shaders, which keep per-particle state across frames.
- **Baked shader flipbooks:** expensive fire/smoke/portal/raymarch effects rendered to 4x4 or 8x8 atlases.
- **Map/UI shaders:** fog of war, contour lines, region hover, parchment/watercolor treatment, minimap masks.

The core implementation should be a small shader DSL:

```json
{
  "id": "arcane_shield_ring",
  "target": "canvas_item",
  "template": "ring_field_2d",
  "params": {
    "palette": ["#54d7ff", "#a66cff", "#ffffff"],
    "radius": 0.42,
    "edge_width": 0.04,
    "noise_scale": 11.0,
    "rune_count": 12,
    "pulse_speed": 1.8,
    "distortion": 0.12
  },
  "outputs": ["gdshader", "preview_png", "flipbook", "godot_scene"]
}
```

The LLM should fill this JSON, not write unbounded shader code first. Templates can expose known-good functions: value noise, fbm, voronoi, SDF rings, polar coordinates, lightning segment distance, radial masks, dissolve thresholds, flowmap sampling, hue ramps, rim lighting, normal reconstruction, heat haze, refraction, and signed-distance glyph stamping. When the LLM writes custom code, it should do so inside a named include block with tests and a Godot compile step.

Preview is non-negotiable. A shader is only accepted if the lab creates a PNG contact sheet or short WebM/GIF from a Godot scene. For expensive effects, bake the preview frames into a flipbook atlas and metadata. This also lets the runtime choose: use the live shader when cheap and interactive, use the flipbook when the shader is costly or unstable across hardware.

## Deep dive: world map generation/rendering

The missing world-map problem is mostly data modeling, not terrain. A game map screen needs layered semantic data:

- coastlines, ocean/lakes, height bands, hillshade, contours;
- biomes/climate overlays;
- rivers, roads, trails, passes, bridges, ports;
- settlements, dungeons, ruins, landmarks, region icons;
- political regions, borders, faction influence, front lines;
- labels with priority and collision rules;
- fog-of-war/revealed masks, discovered icons, quest highlights.

Azgaar is the best fantasy political map generator to study and use as a reference. It exports SVG/PNG/tiles, GeoJSON for cells/routes/rivers/markers/zones, and JSON that can substitute for an API. It also handles cultures, states, burgs, labels, routes, rivers, and map styles. The problem is automation: it is a GUI/browser app with a messy but improving codebase. Use it through headless browser tests or manual reference exports, but do not make it the only source of truth.

Mapgen4 is the better codebase to adapt for a first procedural map layer. It is TypeScript, Apache-2.0, fast, paintable, and already models wilderness maps with elevation, rainfall, rivers, and biomes. It explicitly does not include towns, roads, nations, labels, or resources, which is fine: those are exactly the layers the asset factory should add. Mapgen4 can generate a believable base map, then Python/Node scripts can derive settlement candidates and routes.

WorldEngine remains useful for continent-scale climate/biome maps because it is CLI-driven and emits multiple world layers. World Orogen and Gleba are strong visual/scientific references for tectonics, climate, erosion, plants, and glaciers, but they are lower priority for this LLM-driven project unless export automation becomes clean. They answer "what should believable continents/climate look like?", not "how do we generate inspectable Godot map assets tonight?"

The proposed canonical world-map contract:

```text
world/maps/<map_id>/
  map.json                  # seed, projection, dimensions, style, layer paths
  layers/
    height.png
    biome.png
    water.geojson
    rivers.geojson
    roads.geojson
    regions.geojson
    settlements.json
    landmarks.json
    labels.json
    fog_mask.png
  previews/
    map_full.png
    map_biomes.png
    map_political.png
    map_roads_rivers.png
    map_fogged.png
  godot/
    world_map.tscn
    map_layers.tres
```

Generation recipe:

1. Base land/water/elevation from Mapgen4, WorldEngine, DEM, or hand-painted mask.
2. River graph from generated flow and water accumulation.
3. Biomes from elevation, latitude/temperature, rainfall/moisture.
4. Settlement candidates scored by water access, coast, flatness, biome fertility, road centrality, resource tags, and political constraints.
5. Political regions from weighted Voronoi seeded by capitals/faction origins, then clipped to coasts/rivers/mountains.
6. Roads from A*/least-cost paths over slope, river crossings, settlement importance, and biome cost.
7. Labels from priority classes; use simple simulated annealing/grid collision first, then Mapshaper/SVG cleanup.
8. Render to layered PNG/SVG for inspection and to Godot data for runtime.

For in-game rendering, start simple: static raster base map plus Godot vector overlays. Use `Polygon2D`/`Line2D` for borders, rivers, roads, and hover highlights; `Label` or pre-rendered text for labels; `Sprite2D`/atlas icons for settlements and quest markers; a mask texture for fog. If the map grows large, add tiled rendering or use MapLibre/OpenMapTiles style workflows for HTML previews and offline tiles, then rasterize into Godot-friendly chunks.

## Deep dive: textures + decorations + biome dressing

The prior texture report correctly chose CC0 libraries plus optional AI PBR generation. The deeper missing layer is **dressing**: what makes a biome feel inhabited, old, wet, windy, dangerous, sacred, or ruined. Textures alone do not solve that. A biome needs a kit:

- surface materials: ground, rock, mud, sand, snow, bark, moss, wet variants;
- decals: cracks, stains, puddles, scorch marks, moss patches, rune stains, footprints;
- scatter props: rocks, pebbles, grass clumps, shrubs, roots, mushrooms, bones, debris;
- hero props: ruins, camp props, shrines, logs, crates, caves, bridges;
- placement masks: slope, height, wetness, biome, distance to water, distance to road, path edge, shade, exposure;
- shader rules: wind sway, wetness darkening, snow cap, moss overlay, distance fade.

Blender Geometry Nodes is the best first procedural prop variation tool because it is already installed, scriptable, and outputs inspectable GLBs and renders. Build node groups or Python-generated meshes for:

- rock clusters from ico spheres/noise/displacement;
- grass cards and clumps from curves/cards with atlas materials;
- bushes from low-poly branch/leaf cards;
- ruin stones from bevelled cubes, fractured blocks, and moss decals;
- cave stalagmites, roots, bones, crystals, debris piles;
- billboard impostors and LOD meshes.

Generated AI 3D props are useful but should not be scattered raw. Meshy has a clean API with GLB output, lowpoly mode, PBR refine, auto-size, and texture de-lighting options. That makes it a good source for medium-detail hero props or hard-to-find decorations. But for scatter, AI meshes often have inconsistent scale, topology, UVs, collision, and silhouette quality. Every AI prop should pass through Blender cleanup: origin at bottom, scale normalization, decimation/LOD, material simplification, optional billboard render, thumbnail, collision proxy, and manifest.

For placement, use terrain outputs as masks. Terrain v2 should emit slope, height, water, wetness, biome, vegetation density, and road/path masks. The dressing compiler then converts a biome kit into placement candidates:

```json
{
  "biome": "mossy_highland_ruins",
  "materials": ["mossy_basalt", "wet_soil", "lichen_rock"],
  "decals": ["moss_patch_01", "mud_splash_02", "cracked_stone_03"],
  "scatter": [
    {"asset": "rock_cluster_small", "density": 0.8, "slope_max": 38, "avoid_roads_m": 1.5},
    {"asset": "fern_clump", "density": 0.5, "wetness_min": 0.35, "shade_min": 0.4},
    {"asset": "ruin_block", "density": 0.08, "near_landmark": "ruin"}
  ]
}
```

Terrain3D's instancer is the best Godot-side target for large terrain dressing. It supports meshes/cards/scenes, MultiMesh rendering, LOD up to 10, visibility ranges, hand painting and API placement. Its limitations matter: MultiMesh collision is not automatic, complex multi-mesh scenes need preparation, and the asset library build is for Godot 4.4, so 4.5 compatibility must be verified or built. ProtonScatter is useful for scene-specific non-destructive placement and arbitrary geometry, but its latest release is older. Use Terrain3D for terrain-scale foliage/rocks and ProtonScatter for authored scenes, caves, camps, ruins, and interiors.

Houdini/HEGo is powerful but not first. HEGo now bridges Houdini Engine into Godot with scriptable HDA nodes and Terrain3D features, but it requires a commercial Houdini license and is still a heavier dependency. Evaluate after Blender Geometry Nodes and Terrain3D prove the data contract.

## Brief UI/icons/theme catch-up

Recraft is the best current API candidate for generated game icons because it supports raster and vector generation, vectorization, background removal, style control, and V4 vector models released in February 2026. Use it for spell icons, item icons, faction crests, map markers, and HUD ornaments. Local ComfyUI/FLUX can be a fallback, but Recraft's vector output is more aligned with icon/HUD work.

Free sources: Game-icons.net is CC-BY 3.0 and excellent for placeholder-to-shipping icons if attribution is acceptable. Kenney UI packs are the CC0 baseline for immediate HUD/control assets. Lucide/Iconify are better for editor/tool UI, not fantasy item/spell icons.

Godot-side: `Theme.tres` should be generated with Button/Panel/Label/ProgressBar/Tooltip styles, atlas icons, fonts, colors, constants, and StyleBoxTexture references. Godot's Theme editor supports project-wide themes, and NinePatchRect/9-slice panels preserve corners while stretching or tiling edges. Build a small 9-slice generator that creates panel PNGs plus margin metadata. TexturePacker has a real command-line interface for atlas packing; a Python `rectpack` script is enough for free first pass, but TexturePacker is a solid paid upgrade.

## Test plan for top 5 candidates

1. **Godot shader template harness.** Generate five effects: arcane ring, fire dissolve, shield hit ripple, lightning beam, portal swirl. Success: `.gdshader`, parameter JSON, static PNG, 32-frame flipbook, and `.tscn` compile in Godot 4.5 with no errors.

2. **Material Maker 1.6.** Install/run CLI export on two procedural graphs: animated unlit magic mask and mossy stone PBR. Success: Godot `.tres`/PNG maps export, parameters documented, preview rendered, graph stored as source.

3. **Shadertoy/GodotShaders reference importer.** Pull 10 permissively licensed examples tagged fire/lightning/portal/noise, convert or wrap three into Godot. Success: license stored, compile result logged, preview contact sheet, rejected examples documented.

4. **Mapgen4 + Mapshaper world map slice.** Generate one 2048px continent/region map, derive rivers/biomes, add 12 settlements, 3 factions, roads, labels, and export GeoJSON/SVG/PNG. Success: layered preview and Godot scene with clickable regions/icons.

5. **Blender Geometry Nodes biome kit + Terrain3D/ProtonScatter.** Generate a mossy highland dressing kit with 6 rock variants, 4 grass/fern card clumps, 3 ruin blocks, 5 decals, and placement masks. Success: GLB/card/decal outputs, thumbnails, placement JSON, Godot scene showing scatter density controls.

## Proposed architecture for a "Magic/World Art Lab"

```text
art_lab/
  requests/
    *.json
  shaders/
    templates/
    generated/<shader_id>/
  maps/
    generators/
    generated/<map_id>/
  biomes/
    kits/<biome_id>/
  ui/
    icons/
    themes/
  tools/
    shader_compile_preview.py
    bake_flipbook.py
    map_generate.py
    biome_dress.py
    godot_export.py
    gallery.py
```

All tools should share one pattern: request JSON in, artifact folder out, preview required, manifest required, Godot export optional but expected. Godot should be used as the final compiler for Godot shaders and scenes. Blender should be used as the asset/variant baker. Node/Mapshaper should handle vector map data. Material Maker and Recraft are adapters behind the same manifest contract, not one-off manual workflows.

## Exact starter kit: 3-6 tools to adopt first

1. **First-party Godot shader template + preview/bake harness.** This is the foundation and answers the AI shader question directly.
2. **Material Maker 1.6.** Best external procedural material/mask graph tool with Godot-native roots and CLI export.
3. **Mapgen4 + Mapshaper.** Best scriptable wilderness map base plus vector cleanup/export.
4. **Blender Geometry Nodes.** Best local biome decoration and prop-variant generator.
5. **Terrain3D instancer, with ProtonScatter as scene fallback.** Best Godot placement targets.
6. **Recraft API.** Best UI/icon/vector catch-up path if API keys/costs are acceptable.

## Things to drop/avoid

- A standalone "AI shader generator" as the core dependency. It is not real enough for Godot shipping work.
- Blind Shadertoy copying. Use only license-checked references and performance-tested ports.
- Unity Shader Graph or Unreal materials as canonical authoring targets. They are translation sources at most.
- GUI-only fantasy map tools as the source of truth. Export from them, study them, but keep canonical map layers in JSON/GeoJSON/SVG/PNG.
- Raw AI 3D props in scatter fields. Always clean, scale, simplify, LOD, thumbnail, and validate.
- GPL code ingestion for game/runtime tools unless the whole licensing decision is intentional.
- Houdini/HEGo as first-week work. It is promising but too heavy before the local Blender/Godot path exists.

## Open questions and risks

- Does current Terrain3D build cleanly against Godot 4.5 on this machine, or do we need a source build/pin?
- Can Material Maker 1.6 CLI export dynamic unlit shaders cleanly for Godot 4.5, or only baked material maps?
- What exact license policy should the factory enforce for GodotShaders and Shadertoy examples: CC0/MIT only, or attribution-compatible licenses too?
- How much of the world map should be rasterized versus live vector in Godot? The right answer depends on target resolution and interactivity.
- Is Recraft acceptable as a paid cloud dependency for icons, or should UI start with Game-icons/Kenney plus local generation?
- Are generated map labels better as Godot `Label` nodes, pre-rendered text layers, or SVG-rasterized labels?
- Will thousands of scatter instances need collision, or can decoration collision be limited to hero props and blockers?

## Sources

- Godot shaders and rendering: [Godot particle shaders](https://docs.godotengine.org/en/4.5/tutorials/shaders/shader_reference/particle_shader.html), [CanvasItem shaders](https://docs.godotengine.org/en/4.5/tutorials/shaders/shader_reference/canvas_item_shader.html), [GLSL to Godot conversion](https://docs.godotengine.org/en/stable/tutorials/shaders/converting_glsl_to_godot_shaders.html), [Theme editor](https://docs.godotengine.org/en/4.5/tutorials/ui/gui_using_theme_editor.html), [NinePatchRect](https://docs.godotengine.org/en/4.4/classes/class_ninepatchrect.html)
- Shader/material tools: [Material Maker](https://www.materialmaker.org/), [Material Maker GitHub](https://github.com/RodZill4/material-maker), [Material Maker export docs](https://rodzill4.github.io/material-maker/doc/export.html?highlight=unreal+5), [Godot Shaders](https://godotshaders.com/), [Godot Shaders license](https://godotshaders.com/license/), [Shadertoy API](https://www.shadertoy.com/howto), [IlluGen](https://jangafx.com/software/illugen), [MaterialX](https://materialx.org/index.html), [MaterialX GitHub](https://github.com/AcademySoftwareFoundation/MaterialX), [Refract](https://www.refract.build/)
- World maps/GIS: [Azgaar app](https://azgaar.github.io/Fantasy-Map-Generator/), [Azgaar GitHub](https://github.com/Azgaar/Fantasy-Map-Generator), [Mapgen4](https://www.redblobgames.com/maps/mapgen4/), [Mapgen4 GitHub](https://github.com/redblobgames/mapgen4), [Mapshaper docs](https://mapshaper.org/docs/), [MapLibre](https://maplibre.org/), [OpenMapTiles](https://openmaptiles.org/), [tilemaker](https://tilemaker.org/), [World Orogen](https://www.orogen.studio/), [Gleba](https://calandiel.itch.io/gleba)
- Decoration/scatter: [Blender Geometry Nodes](https://docs.blender.org/manual/en/5.0/modeling/geometry_nodes/introduction.html), [Blender Python API](https://docs.blender.org/api/5.0/index.html), [Blender command line](https://docs.blender.org/manual/en/latest/advanced/command_line/index.html), [Terrain3D instancer](https://terrain3d.readthedocs.io/en/1.0/docs/instancer.html), [Terrain3D Asset Library](https://godotengine.org/asset-library/asset/3892), [ProtonScatter](https://github.com/HungryProton/scatter), [HEGo](https://hego.readthedocs.io/en/latest/about/introduction.html), [HEGo Asset Library](https://godotengine.org/asset-library/asset/4176), [Meshy API](https://docs.meshy.ai/en/api/text-to-3d)
- UI/icons: [Recraft API](https://www.recraft.ai/api), [Recraft API docs](https://www.recraft.ai/docs/api-reference/getting-started), [Recraft V4](https://www.recraft.ai/docs/recraft-models/recraft-V4), [Game-icons license](https://game-icons.net/about.html), [TexturePacker CLI](https://www.codeandweb.com/texturepacker/documentation/commandline)

## Adoption sequence: first week

1. **Day 1:** Build `art_lab/tools/shader_compile_preview.py` and five Godot shader templates: ring, beam, dissolve, shield ripple, portal swirl. Output `.gdshader`, `.tscn`, PNG contact sheet, and flipbook atlas.
2. **Day 2:** Add Material Maker adapter and a reference importer for CC0/MIT GodotShaders examples. Store license/provenance in manifests.
3. **Day 3:** Port Mapgen4 into a Node/Python map command that emits layered JSON/GeoJSON/PNG previews for one region map.
4. **Day 4:** Add settlements, roads, political Voronoi regions, labels, icons, and fog mask to the map contract; export a clickable Godot map scene.
5. **Day 5:** Build one biome dressing kit in Blender Geometry Nodes: rocks, grass cards, ruin blocks, moss decals, thumbnails, GLBs, and placement masks.
6. **Weekend:** Test Terrain3D 4.5 compatibility and ProtonScatter fallback, then wire the biome kit into a Godot preview scene with density sliders and screenshots.
