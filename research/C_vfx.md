# Assignment C - VFX Baking Lab / SpellLab v2

Date: 2026-05-06  
Scope: characterize the installed physics engines under `D:\spell lab\repo-lab`, identify 2026-primary tools, and recommend a content-first VFX authoring, baking, preview, and Godot export architecture.

## Executive Recommendation

The right rewrite is not "17 engines in a browser." It is a **VFX baking lab** with a stable artifact contract and a small set of primary backends. Most effects should be baked offline into flipbooks, particle timelines, vector fields, or shard transforms, then played cheaply in Godot 4.5. Runtime simulation should be rare and explicit.

Use this 2026 starter kit:

1. **Taichi** - primary custom simulator for 2D falling sand, heat/fire grids, MPM-ish material effects, waves, masks, and exportable PNG/JSON frames. It is Python-first, permissive, and already fits the local workflow.
2. **LiquidFun** - primary 2D gameplay-fluid reference for splashes, goo, acid, blood, blobs, and water projectiles. It is old, but it is still the closest installed engine to 2D Godot gameplay semantics.
3. **Newton + Warp** - primary high-end GPU/offline multiphysics lane. Newton is the 2026 add/keep because it is built on NVIDIA Warp/OpenUSD and reached Newton 1.0 GA in 2026; Warp stays the direct custom CUDA-kernel layer.
4. **PhiFlow** - primary smoke/vector-field lane for 2D density, wind, glyph-smoke, vortex, and flow-map outputs.

Keep **SPlisHSPlasH, PhysX, Mantaflow/Blender, and the first-party 2D fracture baker** as secondary specialists. Keep Sandspiel, The Powder Toy, GPU-Falling-Sand-CA, Sailfish, DiffTaichi, VoronoiShatter, Brax, MuJoCo, and JAX-MD mainly as references or narrow experiments.

Commercially, add **JangaFX EmberGen/LiquiGen/IlluGen** to the watch/test list. EmberGen and LiquiGen are exactly the artist-grade flipbook tools for fire/smoke/explosions/liquid; IlluGen is new and specifically targets game VFX assets like flowmaps, masks, flipbooks, UV distortions, and VFX meshes. They are GUI/subscription tools, so they are not the automated backbone, but they are the clearest 2026 quality bar.

## Local State

The old handoff understated progress. `D:\spell lab\repo-lab\README.md` and `ENGINE_ROADMAP.md` show that many engines have actual artifact demos, not just import tests: Newton MPM USD, Taichi sand, Warp blackhole particles, PhiFlow smoke, JAX-MD swarm, Genesis rubble, MuJoCo chain, Brax force curve, SPlisHSPlasH dam break, LiquidFun particle splash, PhysX rubble stack, Mantaflow grid fallback/runner, first-party Sand Lab, and a deterministic 2D fracture baker.

The problem is architectural: demos are not yet a shipping asset pipeline. The rewrite should move from "scenario runner" to "effect factory":

```text
D:\assets\vfx\catalog\<kind>\<effect_id>\
  effect.json
  manifest.json
  preview.png
  flipbook.png
  frames\frame_0000.png
  particles.json
  field.json
  fragments.json
  godot\effect.tscn
  notes.md
```

Every backend should only matter if it writes one of those artifacts.

## Per-Engine Disposition

**Taichi** - Keep as a primary. Taichi is a Python-embedded high-performance compute language for GPU/CPU kernels with physical simulation as a core use case ([docs](https://docs.taichi-lang.org/), [GitHub](https://github.com/taichi-dev/taichi)). Its latest public release line is v1.7.4 in 2025, so it is not the newest engine, but it is mature enough and ergonomic. It shines for custom grid/particle effects: sand, smoke-ish scalar fields, heat propagation, fire spread, simple MPM, rain-on-ground masks, erosion masks, and stylized waves. It fails when you want fully featured rigid-body scenes or artist-ready fluids without writing kernels.

**NVIDIA Warp** - Keep as a primary companion to Newton. Warp is a Python framework that JIT-compiles Python kernels to CPU/CUDA and supports differentiable simulation, geometry, FEM, SPH, waves, fluids, and optimization-style workloads ([docs](https://nvidia.github.io/warp/), [GitHub](https://github.com/nvidia/warp)). It is current and NVIDIA is still publishing 2026 Warp material. It shines for RTX 5090-local GPU particles, force fields, cloth-ish effects, black holes, vector field optimization, and custom solvers. It fails as a beginner-friendly content tool; every useful effect still needs engineering.

**Newton** - Add/keep as 2026 high-end backend. Newton is open-source, built on Warp and OpenUSD, developed by NVIDIA, Google DeepMind, and Disney Research under the Linux Foundation ([NVIDIA overview](https://developer.nvidia.com/newton-physics)). NVIDIA announced Newton 1.0 GA in March 2026 with a stable API, modular solvers, MuJoCo Warp, Kamino, deformables, iMPM granular material, SDF/hydroelastic contacts, and OpenUSD/Isaac integration ([blog](https://developer.nvidia.com/blog/newton-adds-contact-rich-manipulation-and-locomotion-capabilities-for-industrial-robotics/)). It is robotics-oriented, but for this lab it is the best modern "serious physics" reference for granular, cloth, cable, deformable, and USD exports. It is overkill for simple spell flipbooks.

**LiquidFun** - Keep as primary for 2D fluid timing. LiquidFun is Google's Box2D extension adding particle-based fluids and soft bodies to a 2D game physics engine ([site](https://google.github.io/liquidfun/index.html), [GitHub](https://github.com/google/liquidfun)). It is old and effectively archived, but the local build works and the mental model matches 2D gameplay. It shines for splashes, goo, acid, blood, soft blobs, and fluid-projectile timing. It fails for modern GPU scale, maintainability, and direct Godot integration unless wrapped through GDExtension or used offline.

**SPlisHSPlasH** - Keep as secondary water specialist. It is an MIT-licensed SPH simulator with state-of-the-art pressure solvers and VTK/Partio export ([site](https://splishsplash.physics-simulation.org/), [GitHub](https://github.com/InteractiveComputerGraphics/SPlisHSPlasH)). It shines for dam breaks, foam reference, splashes, viscous fluids, and "looks physically like water." It fails as a daily driver because it is C++/build-heavy and too detailed for many 2D spell needs.

**PhiFlow** - Keep as primary field/smoke backend. PhiFlow is a differentiable PDE/fluid framework from TUM/PBS ([GitHub](https://github.com/tum-pbs/PhiFlow)). It shines for 2D smoke density fields, advection/diffusion, vector fields, flowmaps, wind, target-shape smoke, and "make the smoke curl into a rune" experiments. It fails for particles, rigid bodies, and direct game runtime use. It should export `field.json`, density PNGs, flowmaps, and flipbooks.

**Mantaflow** - Keep, but route through Blender for production. Mantaflow is an open-source fluid simulation framework with C++ solver core and Python scene interface, and it is the basis for Blender fluids ([site](https://mantaflow.com/)). It shines for fire/smoke/liquid if the Blender route is acceptable. It fails locally as a standalone dependency unless the Python runner is stable. Use it when Blender batch renders can produce flipbooks or VDB intermediates.

**PhysX** - Keep as secondary rigid/debris backend. PhysX 5 is open-source and PhysX SDK 5.6 docs describe BSD3 CPU source and included Flow/Blast family direction ([docs](https://nvidia-omniverse.github.io/PhysX/physx/5.6.0/index.html), [developer page](https://developer.nvidia.com/physx-sdk)). It shines for 3D rigid piles, debris timing, stacks, joints, collisions, and possibly Flow/Blast-style references. For a 2D-leaning Godot game, it is not the first-line spell baker unless the effect is rubble or rigid fragments.

**GPU-Falling-Sand-CA** - Reference, not dependency. GPU cellular automata are the right runtime direction for falling sand, lava, acid, fire, and erosion, but the installed external repo should inform a first-party permissive implementation. The VFX Lab should own a simple grid update model and later port it to Godot compute shaders if runtime falling sand becomes necessary.

**Sandspiel** - Reference. Sandspiel is MIT-licensed Rust/WASM/WebGL falling-sand work ([GitHub](https://github.com/MaxBittker/sandspiel)). It is excellent for interaction design and material rules, and the local build works. It is not the shipping backend; the current first-party Sand Lab is the right direction.

**The Powder Toy** - Reference only. It is a deep falling-sand sandbox with air pressure, velocity, heat, electricity, and many material interactions, but it is GPL-3.0 ([GitHub](https://github.com/The-Powder-Toy/The-Powder-Toy)). Study behavior, never copy code into a proprietary/commercial game pipeline.

**DiffTaichi** - Reference only. DiffTaichi was important ICLR 2020 work and its examples are still useful for differentiable MPM/smoke/mass-spring patterns ([GitHub](https://github.com/taichi-dev/difftaichi)). The differentiable programming capability is now part of Taichi. Use it as a cookbook, not a backend.

**Sailfish** - Drop to historical reference. Sailfish is an LGPL Lattice Boltzmann Method GPU package from the 2014-era CUDA/OpenCL ecosystem ([GitHub](https://github.com/sailfish-team/sailfish), [paper](https://www.sciencedirect.com/science/article/abs/pii/S0010465514001520)). It is useful if someone wants to learn LBM, but it is not worth reviving for Godot VFX.

**MuJoCo** - Narrow reference. MuJoCo is a strong open-source physics engine for robotics, contact, articulated systems, cloth/rope/soft objects, and optimization ([site](https://mujoco.org/)). For this game, it is useful for chains, ropes, pendulums, traps, and constraints. It should not be a spell VFX primary because Newton/MuJoCo Warp covers the modern GPU direction better.

**Brax** - Drop as VFX backend. Brax is current as a JAX/RL library, but its own README warns that as of 0.13.0 only `brax/training` is actively maintained and physics users should use MJX or MuJoCo Warp instead ([GitHub](https://github.com/google/brax)). Keep the force-curve demo for tuning parameters; do not build VFX around Brax.

**JAX-MD** - Narrow special effects reference. JAX-MD is differentiable molecular dynamics ([GitHub](https://github.com/jax-md/jax-md)). It can make cool swarms, attraction fields, flocking-ish or molecular spell motifs. It is not a primary because it is too abstract and JAX-stack-heavy for asset baking.

**Genesis** - Watch, do not primary. Genesis is an Apache-2.0 universal/generative physics platform with frequent 2025-2026 releases ([PyPI](https://pypi.org/project/genesis-world/), [GitHub](https://github.com/Genesis-Embodied-AI/Genesis)). It is impressive and Pythonic, but robotics/embodied-AI oriented and heavy. Use it for one or two unified-sim experiments; do not make VFX Lab depend on it until it proves better than Newton/Warp for our artifacts.

**VoronoiShatter** - Reference, not primary. The local first-party `fracture2d_baker.py` is more relevant because it already exports `fragments.json`, `bodies.json`, and preview artifacts. The 2025 Godot VoronoiShatter plugin is useful for 3D mesh fracture reference, but the 2D-leaning game needs deterministic 2D shards first.

**First-party 2D Fracture** - Promote as a core module even though it is not one of the external engines. It is deterministic, already outputs Godot-friendly polygons/transforms, and directly supports breakable rocks, glass, shields, ice, pottery, and terrain chunks.

## Phenomenon Recipes

- **Fire/explosions/smoke:** PhiFlow for 2D density and vector fields; Taichi for heat/fire grids; Blender/Mantaflow or EmberGen for high-quality rendered flipbooks; export `flipbook.png`, `field.json`, and additive material presets.
- **Water/splash/goo/acid:** LiquidFun for 2D particle timing; SPlisHSPlasH for high-quality offline water; LiquiGen as commercial reference/add-on; export particles, masks, foam pass, and flipbook.
- **Sand/lava/material reactions:** Taichi first-party CA/MPM; Sandspiel and Powder Toy as behavior references; later port hot paths to Godot compute shader if runtime needed.
- **Destruction/debris:** first-party 2D fracture for game-ready shards; PhysX/Newton for 3D rubble timing reference; export fragments and replayable body transforms.
- **Swirls/black holes/magic fields:** Warp particles and PhiFlow vector fields; bake both particles and flowmaps so Godot particles can follow the look cheaply.
- **Lightning/beams/shockwaves:** mostly procedural Godot shaders/GPUParticles2D plus IlluGen-style masks/noises; physics engines are not needed except for debris secondary effects.

## VFX Lab v2 Architecture

Build one canonical authoring schema and let engines be replaceable workers:

```json
{
  "id": "acid_splash_small",
  "kind": "spell",
  "phenomenon": "liquid",
  "backend": "liquidfun",
  "fps": 30,
  "duration": 1.2,
  "bounds_px": [512, 512],
  "inputs": { "color": "#7cff40", "viscosity": 0.7, "impact": "arc" },
  "outputs": ["flipbook", "particles", "godot_scene"]
}
```

Pipeline stages:

1. **Author:** LLM writes/edits `effect.json` from natural language.
2. **Bake:** `bake.py effect.json` routes to `backends/<engine>_baker.py`.
3. **Normalize:** every backend writes common `manifest.json`, PNG frames, optional `particles.json`, `field.json`, `fragments.json`.
4. **Pack:** existing `pack_flipbook.py`-style code packs frames into spritesheets and metadata.
5. **Preview:** browser gallery shows animated flipbook, 2D canvas replay, bounds, fps, source settings, and warnings.
6. **Export:** Godot exporter writes `.tscn`, `.tres`, shader stubs, GPUParticles2D presets, collision/shard import data, and an optional C# loader.

Godot runtime should primarily use native `GPUParticles2D`, `ParticleProcessMaterial`, particle shaders, flipbook textures, CanvasItem shaders, and occasional shader-driven fields. Godot 4.5 supports 2D particle flipbooks and GPU particle shaders; particle shaders retain previous-frame data and are available for GPU particle nodes ([2D particles](https://docs.godotengine.org/en/4.5/tutorials/2d/particle_systems_2d.html), [particle shaders](https://docs.godotengine.org/en/4.5/tutorials/shaders/shader_reference/particle_shader.html)). For live simulation experiments, evaluate Godot compute shader helpers such as Compute Shader Plus/Fusion Compute and Godot liquid/fracture addons, but do not make them core until they survive profiling.

## Test Plan

Start with five acceptance demos:

1. **LiquidFun acid splash:** projectile hits wall/waterline; success is 30 fps flipbook, particle JSON, 512px preview, and Godot GPUParticles/AnimatedSprite scene.
2. **Taichi sand/fire:** falling sand pile ignites oil and produces smoke mask; success is deterministic seed replay and material stats per frame.
3. **PhiFlow smoke rune:** smoke curls into a simple glyph silhouette; success is density frames plus flowmap usable by a Godot shader.
4. **Newton/Warp magic crater:** particles/granular wedge collapses under radial force; success is USD/particles export plus top-down flipbook.
5. **Fracture shield break:** radial 2D shard breakup; success is `fragments.json`, `bodies.json`, transparent flipbook, and Godot `Polygon2D` import.

Estimated integration effort:

- Catalog/schema/bake contract: 4-8 hours.
- Preview/gallery and artifact validator: 6-12 hours.
- Taichi and LiquidFun production bakers: 1-2 days.
- PhiFlow and Warp/Newton bakers: 1-2 days.
- Godot exporter for flipbook/particles/fracture: 1-2 days.
- Commercial JangaFX evaluation: 2-4 hours if installed; longer if licensing/account setup is needed.

## Honest Tradeoffs

- A single "best physics engine" is the wrong goal. VFX needs specialized outputs, not one unified simulator.
- Baked flipbooks are the default because they are reliable, inspectable, and cheap in Godot.
- Runtime physics should be limited to gameplay-critical cases: small LiquidFun-like splashes, Godot particles, and maybe first-party CA/compute shader tiles.
- GPL projects are behavior references only.
- Commercial tools may beat local quality quickly, but GUI dependence makes them less LLM-friendly.
- Newton/Warp are genuinely 2026 SOTA for GPU simulation, but still engineering tools, not artist tools.

## Sources

- Local docs: `D:\spell lab\repo-lab\README.md`, `D:\spell lab\repo-lab\ENGINE_ROADMAP.md`, `D:\assets\../docs/plans/ROADMAP.md`
- Taichi: https://docs.taichi-lang.org/, https://github.com/taichi-dev/taichi
- NVIDIA Warp/Newton: https://nvidia.github.io/warp/, https://github.com/nvidia/warp, https://developer.nvidia.com/newton-physics, https://developer.nvidia.com/blog/newton-adds-contact-rich-manipulation-and-locomotion-capabilities-for-industrial-robotics/
- LiquidFun: https://google.github.io/liquidfun/index.html, https://github.com/google/liquidfun
- SPlisHSPlasH: https://splishsplash.physics-simulation.org/, https://github.com/InteractiveComputerGraphics/SPlisHSPlasH
- PhiFlow: https://github.com/tum-pbs/PhiFlow
- Mantaflow/Blender: https://mantaflow.com/
- PhysX: https://developer.nvidia.com/physx-sdk, https://nvidia-omniverse.github.io/PhysX/physx/5.6.0/index.html
- MuJoCo/Brax/JAX-MD/Genesis: https://mujoco.org/, https://github.com/google/brax, https://github.com/jax-md/jax-md, https://github.com/Genesis-Embodied-AI/Genesis
- Sandspiel / Powder Toy / DiffTaichi / Sailfish: https://github.com/MaxBittker/sandspiel, https://github.com/The-Powder-Toy/The-Powder-Toy, https://github.com/taichi-dev/difftaichi, https://github.com/sailfish-team/sailfish
- Godot particles: https://docs.godotengine.org/en/4.5/tutorials/2d/particle_systems_2d.html, https://docs.godotengine.org/en/4.5/tutorials/shaders/shader_reference/particle_shader.html
- JangaFX / Houdini references: https://jangafx.com/, https://docs.jangafx.com/, https://jangafx.com/software/illugen, https://www.sidefx.com/docs/houdini/nodes/out/labs--vertex_animation_textures-3.0.html
