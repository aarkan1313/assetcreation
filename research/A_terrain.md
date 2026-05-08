# Terrain & Worldgen SOTA Report

Compiled: 2026-05-06  
Target: Godot 4.5 / C# asset factory, RTX 5090 Laptop, WSL2 available

## Executive recommendation

Do not bet the terrain pipeline on a single "AI world generator" in 2026. The best practical stack is layered:

1. **Base elevation:** real DEM through OpenTopography/Mapzen/Mapbox, procedural synthesis through FastNoise2, or AI sketch seed through MESA.
2. **Geomorphology:** hydraulic/thermal erosion, flow accumulation, rivers, wetness, slope, and masks.
3. **Biome/material maps:** climate or simple temp/moisture model -> biome -> 4-channel splatmap, vegetation density, water mask, road/path mask.
4. **Godot integration:** Terrain3D as the primary runtime/editing target, with HeightMapShape3D as a fallback for simple collision-only terrain.

The starter kit should be **FastNoise2 or Python noise + Landlab + bmi-topography/OpenTopography + Terrain3D**, with **MESA** as an optional AI input mode and **WorldEngine or World Orogen** for world-scale maps. Gaea is the best commercial terrain authoring tool to evaluate later because it has real command-line build automation, but the first B+ pipeline can be built locally without buying a license.

## Tool and method survey

| Tool / method | Link | License | Last meaningful update | Requirements / sm_120 notes | What makes it different |
|---|---|---:|---|---|---|
| MESA terrain diffusion | [HF model](https://huggingface.co/NewtNewt/MESA), [paper](https://huggingface.co/papers/2504.07210), [dataset](https://huggingface.co/datasets/Major-TOM/Core-DEM) | Adobe model license; Core-DEM is CC-BY-SA-4.0 | Paper/model Apr 2025 | Python 3.11, Diffusers, Stable Diffusion 2.1 fine-tune, 4.6 GB weights. Use Torch cu128/cu130 for Blackwell. | The most concrete local text-to-terrain model: co-registered optical and DEM outputs from text prompts. |
| Terrain Diffusion | [HF paper](https://huggingface.co/papers/2512.08309) | Paper CC-BY-4.0 | Dec 2025 | Research paper; no verified production-ready repo found. | Claims seamless infinite diffusion terrain with random access, conceptually the closest AI successor to Perlin. |
| TerraFusion | [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2096579625000713), [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5338393) | Open-access paper, CC-BY | Accepted / published 2025 | Research; no easy local release verified. | Joint latent diffusion for paired heightmap and texture, useful idea for future texture pairing. |
| World Labs Marble / World API | [product](https://www.worldlabs.ai/), [docs](https://docs.worldlabs.ai/), [API announcement](https://www.worldlabs.ai/blog/announcing-the-world-api) | Proprietary cloud | Public API Jan 2026 | API/cloud workflow, exports downstream 3D worlds, not a heightmap-first tool. | Best current commercial "spatial world" generator; good for references, not a deterministic terrain pipeline. |
| Google DeepMind Genie 3 | [official blog](https://deepmind.google/blog/genie-3-a-new-frontier-for-world-models/), [model page](https://deepmind.google/models/genie/) | Proprietary / research prototype | Aug 2025 | Limited/experimental access; generates interactive view, not exportable game terrain. | SOTA interactive world model, but not an asset factory component yet. |
| FastNoise2 / FastNoiseLite | [FastNoise2](https://github.com/Auburn/FastNoise2), [FastNoiseLite](https://github.com/Auburn/FastNoiseLite) | MIT | FastNoise2 active Feb 2026; Lite repo active 2026, latest release Mar 2024 | CPU SIMD, C++17, Rust/C#/Java bindings; no CUDA issue. | Best local foundation for noise, domain warp, ridged/cellular/Worley style features. |
| Landlab | [GitHub](https://github.com/landlab/landlab), [PyPI](https://pypi.org/project/landlab/), [release notes](https://landlab.readthedocs.io/en/latest/about/changes.html) | MIT | 2.11.0 Apr 2026 | Python, NumPy/Cython; install via pip/conda; CPU. | Mature scientific toolkit for flow routing, stream power erosion, diffusion, hydrology, and terrain analysis. |
| soillib | [site](https://erosiv.studio/soillib), [metadata](https://repos.ecosyste.ms/hosts/GitHub/repositories/erosiv%2Fsoillib), [PyPI](https://pypi.org/project/soillib/) | LGPL-3.0 per repo metadata | PyPI 1.0.0 Aug 2024; repo updated late 2025/early 2026 | Linux first, C++23/Python bindings, GPU; Windows "coming soon." Test in WSL2. | Most interesting open GPU geomorphology library, but early and less battle-tested. |
| rainfall | [Go package](https://pkg.go.dev/github.com/setanarut/rainfall) | MIT | v1.1.2 May 2025 | Go library, CPU; easy to wrap as CLI. | Small particle hydraulic erosion implementation over heightfields. |
| SimpleHydrology | [GitHub](https://github.com/weigert/SimpleHydrology) | Open-source repo; verify license before embedding | Last visible activity 2023 | C++/OpenGL sample, not a clean library. | Nice reference for rivers/lakes/pools on generated terrain. |
| WorldEngine | [PyPI](https://pypi.org/project/worldengine/), [GitHub](https://github.com/Mindwerks/worldengine), [CLI docs](https://worldengine.readthedocs.io/en/latest/cli.html) | MIT | 0.20.0 Nov 2025 | Python 3.9-3.14, CLI, pyplatec/noise/protobuf; CPU. | End-to-end world-scale plates, rain shadows, erosion, humidity, Holdridge biomes, PNG outputs. |
| World Orogen | [site](https://www.orogen.studio/), [heightmap import](https://www.orogen.studio/import) | Free web tool; source/license not verified | Site active in 2026 | Browser GUI; exports equirectangular maps up to 65,536px. | Strong world-scale tectonics + climate + erosion preview; weak for headless automation. |
| Azgaar Fantasy Map Generator | [app](https://azgaar.github.io/Fantasy-Map-Generator/), [GitHub](https://github.com/Azgaar/Fantasy-Map-Generator) | Open source; generated maps allowed commercially; source license needs review | v1.110 Jan 2026 | Browser app; JSON/GeoJSON/SVG/PNG export; can run locally but GUI-heavy. | Best fantasy political/world map generator, not best playable height terrain. |
| Gaea | [CLI docs](https://docs.gaea.app/developers/automation/cli/command-line-automation.html), [CLI overview](https://docs.gaea.app/developers/automation/cli/index.html) | Proprietary paid/free tiers | Docs current 2026 | Windows GUI plus `Gaea.Swarm.exe` headless builds with seeds/variables. | Best commercial terrain authoring candidate because it is visually excellent and automatable. |
| Houdini HeightFields | [heightfield docs](https://www.sidefx.com/docs/houdini/heightfields/index.html), [terrain workflow](https://www.sidefx.com/docs/houdini/model/terrain_workflow.html) | Proprietary; Indie available | Houdini 21 docs current | Windows/Linux, `hython`/`hbatch` automation; learning curve high. | Production-grade procedural terrain, masks, scattering, erosion, but heavy for this user. |
| World Machine | [features](https://www.world-machine.com/features.php), [tiled export](https://www.world-machine.com/purchase.php?page=pro) | Proprietary | Active product docs | Windows GUI; tiled outputs and PBR/mask support; command automation docs less clean than Gaea. | Longstanding terrain tool, good outputs, less LLM-friendly than Gaea. |
| OpenTopography / bmi-topography | [OpenTopography API](https://opentopography.org/developers), [bmi-topography](https://bmi-topography.csdms.io/), [USGS 3DEP](https://www.usgs.gov/3DEP) | Free public datasets; USGS public domain, Copernicus terms apply | Copernicus DGED 2023_1 available Aug 2024; API current | Python/CLI, API key for many datasets, GeoTIFF output. | Best programmable real DEM source. |
| Mapbox Terrain-DEM/RGB | [docs](https://docs.mapbox.com/ja/data/tilesets/guides/access-elevation-data/), [Terrain-RGB](https://docs.mapbox.com/ja/data/tilesets/reference/mapbox-terrain-rgb-v1/) | Proprietary API/tiles; attribution required | Terrain-RGB no updates after Dec 2021; Terrain-DEM is updated path | HTTP tiles; decode RGB to meters; token required. | Convenient game-style tile API, but not the cleanest free bulk source. |
| Mapzen Terrain Tiles | [Mapzen docs/blog](https://www.mapzen.com/blog/terrain-tile-service), [AWS public dataset](https://aws.amazon.com/blogs/publicsector/announcing-terrain-tiles-on-aws-a-qa-with-mapzen/) | Open data tiles via AWS public dataset | Older but still useful | HTTP/S3 Terrarium PNG, GeoTIFF, HGT; no account for public S3 endpoints. | Good fallback global DEM tile source with simple decoding. |
| Terrain3D for Godot | [site](https://tokisan.com/terrain3d/), [GitHub](https://github.com/TokisanGames/Terrain3D), [docs](https://terrain3d.readthedocs.io/) | MIT | v1.0.1 Jun 2025; 1.1 docs visible | Godot 4 plugin/GDExtension; use current release or build for 4.5 if needed. | Best Godot terrain target: clipmaps, 32 texture sets, LOD, foliage instancing, import/export. |
| Godot HeightMapShape3D | [Godot latest docs](https://docs.godotengine.org/en/latest/classes/class_heightmapshape3d.html) | MIT engine | Godot docs current | Native collision shape, image-based loading. | Simple fallback collision layer; not a full terrain rendering/material system. |

## What is actually SOTA in 2026

The research frontier is diffusion/world models, but the production frontier is still procedural plus geomorphology. **MESA** is the only open-ish local AI terrain generator I would test now: it has weights, code, Hugging Face model card, and produces paired optical/DEM outputs. It is not yet a complete game terrain tool because outputs are small remote-sensing-style patches, prompt vocabulary is geographic, and the model license is Adobe-specific. **Terrain Diffusion** and **TerraFusion** are important to track, but they are research until a stable repo and install path exist.

World-model systems like **Marble** and **Genie 3** are impressive, but they generate navigable experiences or spatial scenes, not deterministic heightmaps, splatmaps, collision, erosion masks, or Godot resources. Use them for concept exploration and references only. They are not a replacement for the factory.

For a solo-dev, LLM-driven pipeline, the best-of-best practical stack is:

- **Base shape:** FastNoise2/FastNoiseLite, WorldEngine, OpenTopography, or MESA.
- **Erosion and analysis:** Landlab first, rainfall/simple particle erosion second, soillib as a GPU experiment.
- **World-scale maps:** WorldEngine for headless repeatable maps; World Orogen/Azgaar for visual/manual references.
- **Commercial quality option:** Gaea, because its Build Swarm can run from CLI with seed and variable files.
- **Engine target:** Terrain3D, because it already solves clipmap LOD, terrain materials, importing external heightmaps, and foliage instancing.

## Test plan for top candidates

### 1. OpenTopography + bmi-topography

Input: bounding box around a recognizable mountain region and a flat/plains region.  
Success: downloads GeoTIFF, normalizes to 16-bit PNG, produces hillshade preview, slope map, water/lowland mask, and Terrain3D import folder.  
Install time: 30-60 min including API key. First run: 2-10 min depending area size.  
Failure modes: API limits, vertical datum mismatch, nodata holes, DSM includes trees/buildings.  
ChatGPT inputs: good. The user can say "make a Utah canyon chunk"; the LLM can choose coordinates.

### 2. FastNoise2/Python procedural v2

Input: prompt-derived JSON preset: `alpine_valley`, `volcanic_island`, `canyon`, `marsh_delta`.  
Success: tileable 4x4 grid, 16-bit heightmaps, normal maps, slope maps, four splat channels, vegetation density, water mask, and contact sheet preview.  
Install time: 0-2 hr depending whether we use pure Python first or bind FastNoise2. First run: seconds-minutes.  
Failure modes: synthetic-looking terrain, bad tile boundaries, repeated noise artifacts.  
ChatGPT inputs: excellent. Presets can be natural-language generated, then serialized to JSON.

### 3. Landlab erosion/hydrology

Input: procedural mountain heightmap and one real DEM crop.  
Success: flow accumulation, drainage basins, river mask, eroded heightmap, sediment/wetness mask, before/after preview.  
Install time: 30-90 min in WSL or Windows Python. First run: 5-30 min for 1024-2048 maps.  
Failure modes: scientific defaults are not art defaults; parameters may create overcut rivers or washed-out relief.  
ChatGPT inputs: good once wrapped behind presets.

### 4. MESA

Input: 5 prompts such as "Sentinel-2 image of arid badlands and mesas in summer" and "alpine valley with snow and evergreen forest."  
Success: generate DEM plus optical preview, convert DEM to 16-bit heightmap, compare against procedural equivalent.  
Install time: 1-2 hr if Torch cu130 path is clean; longer if dependency pinning conflicts. First run: under 5 min on RTX 5090 after weights load.  
Failure modes: license, small patch size, remote-sensing look, poor controllability, no seamless tiling.  
ChatGPT inputs: good, but prompts should be geographic/satellite-style rather than fantasy prose.

### 5. Terrain3D import bundle

Input: outputs from tests 1-3.  
Success: Godot 4.5 scene/plugin loads height, splat/control map, texture set refs, and foliage mask without hand work; collision usable.  
Install time: 30-90 min if compatible binary exists; half-day if building GDExtension for 4.5.  
Failure modes: Godot 4.5 ABI/release mismatch, control map format details, texture channel packing mistakes.  
ChatGPT inputs: excellent. This should be a deterministic exporter command.

## End-to-end recipes

### Recipe A: local fantasy playable chunk

Natural-language brief -> JSON terrain preset -> FastNoise2/Python base height -> Landlab/rainfall erosion -> slope/height/wetness classifier -> splatmap RGBA -> vegetation density -> Terrain3D import folder.

This is the recommended first implementation because it is local, deterministic, cheap, and inspectable. It also maps directly onto the current `pipelines/terrain/generate_heightmap.py` script.

### Recipe B: real-world stylized chunk

Place prompt -> geocode/coordinate choice -> OpenTopography or Mapzen DEM -> crop/resample -> optional exaggeration and erosion cleanup -> stylized biome masks -> Terrain3D import.

Use this when the user asks for "Colorado alpine pass," "Appalachian ridge," or "Utah canyon" instead of abstract terrain.

### Recipe C: world-scale map to local chunks

WorldEngine seed -> global elevation/temperature/precipitation/biome PNGs -> pick region cells -> upsample local height -> add procedural detail and erosion -> export region/chunk metadata.

World Orogen can be used as a visual reference or manual heightmap source, but WorldEngine is more LLM-friendly because it has CLI and files.

### Recipe D: AI seed, procedural finish

MESA prompt -> DEM patch -> normalize/retile -> procedural detail pass -> Landlab erosion -> splat/biome export -> Terrain3D.

Use this only after the deterministic path works. AI terrain is best as a seed texture, not as final terrain.

### Recipe E: commercial quality pass

LLM writes Gaea variable JSON -> `Gaea.Swarm.exe` builds height/mask outputs -> local Python validates and packages -> Terrain3D import.

This is the likely highest visual ceiling, but should be evaluated after the free pipeline proves the asset contract.

## LLM and UX considerations

The pipeline should output a folder per terrain:

```text
world/terrain/<terrain_id>/
  height_16.png
  preview_hypsometric.png
  preview_hillshade.png
  normal.png
  splat_rgba.png
  biome.png
  vegetation_density.png
  water_mask.png
  flow.png
  terrain.json
  godot/
    terrain3d_import.json
    terrain_materials.tres
```

Everything must be previewable as PNG before Godot import. The user should never need to inspect raw arrays. Natural-language prompts should compile into a small terrain JSON schema with seed, terrain type, scale, erosion strength, biome palette, world coordinates if real-world, and export resolution.

Good CLI/Python interfaces: bmi-topography, OpenTopography REST, Landlab, WorldEngine, local Python, Gaea Build Swarm. GUI-heavy but still useful: World Orogen, Azgaar, World Machine, Houdini, Gaea graph authoring. Bad fit for now: Genie 3, Marble, one-off web demos that cannot export height/masks programmatically.

## Honest tradeoffs

- **AI is not yet the main terrain generator.** MESA is promising, but it is less controllable than procedural generation and weaker at game-ready metadata.
- **Scientific tools need art wrappers.** Landlab can be correct but ugly. We need curated presets and visual QA, not exposed scientific parameters.
- **Real DEM is excellent for believable terrain but not automatically fun.** It often needs exaggeration, playable flattening, path masks, and biome styling.
- **Terrain3D is the right Godot bet, but Godot 4.5 compatibility must be verified.** If binary releases lag 4.5, build from source or pin the game project to a supported 4.x version until Terrain3D updates.
- **Gaea has the best commercial automation story.** It is not local-open-source, but unlike many GUI tools it has a real headless build command.

## Starter kit and adoption order

### 1. Build Terrain v2 around Python + Landlab

Extend `pipelines/terrain/generate_heightmap.py` into a package that emits height, normal, splat, biome, vegetation, water, flow, and previews. Start with pure NumPy/noise if faster, then add FastNoise2 later if CPU speed becomes a bottleneck.

Estimated effort: 6-10 hours for a useful v2, 1-2 evenings for polish.

### 2. Add OpenTopography/bmi-topography real DEM importer

Make `terrain/import_dem.py` accept a bounding box or named preset and output the same bundle contract as procedural terrain.

Estimated effort: 3-5 hours plus API-key setup.

### 3. Add WorldEngine world-scale generator

Use WorldEngine for continent-scale elevation, climate, and biome source maps. Build a converter from its PNG/world outputs into the same local chunk schema.

Estimated effort: 4-8 hours.

### 4. Add Terrain3D Godot exporter

Package the terrain folder for Terrain3D import, with a fallback HeightMapShape3D collision recipe.

Estimated effort: 4-8 hours, with risk concentrated in Terrain3D 4.5 compatibility and control-map details.

### 5. Optional: test MESA and Gaea

MESA answers "can AI generate useful terrain seeds locally?" Gaea answers "do commercial terrain graphs justify becoming a premium backend?"

Estimated effort: MESA 2-4 hours; Gaea 2-6 hours if installed/licensed.

## Concrete decision

Start with **Python procedural + Landlab + OpenTopography + Terrain3D**. That gives local chunks, real-world chunks, erosion, masks, and Godot integration. Add **WorldEngine** for world maps. Treat **MESA** as an experiment, not a dependency. Track **Terrain Diffusion**, **TerraFusion**, **Marble**, and **Genie 3**, but do not block the factory on them.

This is the path most likely to reach character-pipeline-level decision quality quickly: deterministic, inspectable, scriptable, and directly useful in Godot.
