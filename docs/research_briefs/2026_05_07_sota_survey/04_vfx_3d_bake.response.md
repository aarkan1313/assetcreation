# 2026 SOTA Survey Response — VFX 3D Bake Pipeline

Date: 2026-05-07
Hardware: RTX 5090 Laptop (Blackwell sm_120, 24 GB), Win11 native, Py 3.11/3.12, CUDA 12.8+
Scope: pre-baked PNG flipbooks for Godot. Not Houdini, not real-time particles, not shader VFX.

Top-line: **most of your deferred GPU plan needs revising.** Taichi went into maintenance mode in 2024. PhiFlow is alive but small-team. NVIDIA Warp is the actual SOTA winner here. ML video gen is mostly demo-ware for game flipbooks. Your CPU bakers are honestly fine for the 16-32 frame flipbook use case — the real bottleneck is content authoring, not sim throughput.

---

## Q1 — Is the deferred Taichi/Warp/PhiFlow/LiquidFun plan still 2026-current?

**No, partly stale.** Here is the 2026 reality per tool:

- **Taichi** — *demote / drop.* Discussion #8506 on the official repo confirms development effectively halted around mid-2024; the team pivoted to a commercial GenAI product. Latest PyPI is 1.7.4, in maintenance/bugfix mode. It still works, but you do not want to write new bakers against a frozen DSL in 2026.
- **NVIDIA Warp** — *promote to primary.* Actively shipping (v1.13.0 May 2025; v1.11.1+ already validated on RTX 5090 / sm_120 / CUDA 12.9 per Isaac Lab issue #4951). Native Windows wheels (`pip install warp-lang`), Python 3.10+, BSD-3 licensed. This is the one tool in your deferred list that is unambiguously alive and Blackwell-ready.
- **PhiFlow** — *keep optional.* PyPI 3.4.0 was released Aug 2025 (the GitHub Releases tab is misleadingly stale; PyPI is the source of truth). Apache-2.0, JAX/PyTorch backends. Healthy but small team. Differentiable PDE focus is overkill for game flipbooks.
- **LiquidFun** — *drop.* Google archived this years ago; it has not had a meaningful update since 2017 and is C++ Box2D-flavored, not Python-native.

**Recommendation:** Replace the deferred plan with a single Warp-based baker. The combo "Warp for kernels + numpy/Pillow for I/O + your existing manifest schema" gives you everything Taichi promised, on a stack that is current and Blackwell-validated.

Sources: [Taichi #8506](https://github.com/taichi-dev/taichi/discussions/8506), [Warp releases](https://github.com/NVIDIA/warp/releases), [IsaacLab #4951 confirms sm_120](https://github.com/isaac-sim/IsaacLab/issues/4951), [PhiFlow PyPI](https://pypi.org/project/phiflow/).

---

## Q2 — 2026 SOTA for game-engine smoke/fluid baking (16-32 frame flipbooks)?

Honest answer: **for 16-32 frame flipbooks at game-engine resolution (≤512²), nothing beats semi-Lagrangian on the wallclock-vs-quality curve.** The reason "Houdini Pyro" looks better than your `baker_smoke_field.py` is not the solver — it is (a) higher grid resolution (256³+ vs your 64²), (b) curl-noise turbulence injection, (c) good shading. All three are addable to your existing CPU baker without changing solver class.

That said, if you want a real GPU upgrade, the ranked options:

1. **NVIDIA Warp + grid-MAC solver (port your semi-Lagrangian to `@wp.kernel`).** Same algorithm, 100-300x faster, lets you push to 256³ comfortably and run multiple variants in parallel. BSD-3, Win native, sm_120 confirmed. This is the realistic upgrade path.
2. **Blender 4.x Mantaflow headless** (`blender --background --python bake.py`). Free, batch-able. Quality is "Houdini-lite". The catch: cache writes are slow, Mantaflow internals have known crash bugs on Win baking, and headless GPU baking on Blender is hit-and-miss. Good for "1-2 hero plumes" not for batch 50 effects.
3. **Genesis (genesis-world)** has SPH/MPM solvers and Win support, latest v0.4.6 April 2026. But it is robotics-first; no flipbook output path. You would be writing your own renderer on top. Not worth the integration cost for game flipbooks.

**Recommendation:** Port your 2D semi-Lagrangian to Warp at 128×128×128 and add curl-noise turbulence. The visible quality jump from "thin numpy plume" to "thick volumetric plume with detail" comes from resolution + turbulence, not from a fancier solver.

Sources: [Warp on GitHub](https://github.com/NVIDIA/warp), [Genesis v0.4.6](https://github.com/Genesis-Embodied-AI/Genesis), [Mantaflow crash bug](https://devtalk.blender.org/t/consistent-crashes-when-baking-mantaflow-simulations-exception-access-violation/19183).

---

## Q3 — ML-driven VFX / diffusion text-to-VFX flipbooks in 2026?

**Skeptical answer: do not adopt for production game-engine baking.** Here is the honest landscape:

- **Sora 2 was discontinued April 2026.** OpenAI pulled it. Veo 3.1 / Runway Gen-4.5 / Kling 3.0 / Luma Ray3 are the working text-to-video models. All are SaaS, none output transparent-background sprite sheets, all produce video clips that look like video clips — not tileable flipbooks with clean alpha.
- **AnimateDiff + ComfyUI** is the open-source path. It runs on a 5090 (24 GB is plenty; needs ~12 GB). It does produce 16-frame outputs natively. **But** the outputs are RGB photographic, not alpha-matted; you need a separate matting pass (RMBG-2.0 / BiRefNet) and the temporal consistency of mattes is the actual hard problem. Output looks like "AI video", not like a hand-tuned sprite-sheet fireball.
- **Scenario.com / Layer.ai** are pitching "VFX generation" but in practice their VFX output is 2D concept frames, not baked physics flipbooks. Closed source, per-seat SaaS. Layer.ai's "300+ models" pitch is genuinely useful for asset *concepting*, not for replacing a sim baker.

**The brutal truth:** you have 18 of 24 spell-grid effects that are palette-swap recolors. Diffusion models will *not* fix that — they will just give you 24 different-looking but uncontrolled effects with bad alpha mattes that don't tile, don't loop, and don't match an art direction. The fix for palette-swap blandness is **better hand-authored params** + **a few hero hand-tuned sims**, not generative AI.

**Recommendation:** Skip diffusion for flipbook baking in 2026. *Optional*: keep AnimateDiff + BiRefNet matting in a separate `pipelines/vfx_concept/` folder for *concept frames only* (mood boards, "what should this spell look like") that feed into hand-authored effect.json. Do not put diffusion on the bake path.

Sources: [Sora discontinuation](https://openai.com/index/sora-2/), [AnimateDiff](https://github.com/guoyww/AnimateDiff), [Layer.ai vs Scenario](https://www.layer.ai/vs/scenario).

---

## Q4 — 3D mesh fracture for destruction VFX (GLB in → N variants out)?

Three real options:

1. **Blender Cell Fracture (bundled extension) via headless Python.** Free, works in Blender 4.2 LTS+, scriptable as `bpy.ops.object.add_fracture_cell_objects(...)`. Run via `blender --background --python fracture.py --input prop.glb --seeds 0..N`. Output is N variants of disconnected mesh, exportable back to GLB. This is your realistic answer.
2. **`scorpion81/blender-fracture` (Fracture Modifier branch)** — community fork with the proper FM constraints system. Not in mainline Blender. Higher fidelity for "pre-broken with constraints" workflow. More install pain (custom Blender build).
3. **`pyvoro` / `pyvoro-mmalahe` + `trimesh`** for a pure-Python Voronoi-on-mesh path. Lightweight, no Blender dependency, easy to batch. Less polished output (no inner-face material handling, no convex-decomposition cleanup) but simplest pipeline.

For your "GLB in, N variants out for runtime instantiation", option 1 is the right answer: Blender is already in your stack, Cell Fracture is maintained (active extension, Feb 2026 docs/tutorials still being published), and the headless pipeline is well-trodden.

**Recommendation:** Build `pipelines/vfx/baker_fracture3d.py` as a thin Python wrapper around `blender --background` calling Cell Fracture with seeded params. Output: `fragments_<seed>.glb` + a manifest. License: GPL on Blender side does not infect your output assets.

Sources: [Cell Fracture extension](https://extensions.blender.org/add-ons/cell-fracture/), [scorpion81 fork](https://github.com/scorpion81/blender-fracture).

---

## Q5 — Volumetric fog tooling (clouds, fog banks, weather → Godot `shader_type fog`)?

Your numpy 3D-noise → slice-atlas approach is honestly fine for the use case. Upgrades that justify themselves:

1. **OpenVDB + pyopenvdb** for authoring. Industry-standard sparse-volume format, Python bindings, can ingest free VDB cloud packs (PixelLab, JangaFX VDB Clouds) and resample to your Godot Texture3D atlas. License: MPL-2.0, fully open. Useful when you want "real cloud" not "noise blob".
2. **NanoVDB** (the GPU-renderable cousin of OpenVDB, header-only) for runtime rendering, but Godot does not consume NanoVDB natively, so this is bake-time only — sample VDB into a 3D texture and write Godot's expected slice-atlas. There is active 2025/2026 work on NanoVDB → Unity volumetric clouds; the same pattern ports to Godot trivially.
3. **TileableVolumeNoise / Schneider-Vos cloud noise** (the *Nubis*/Horizon Zero Dawn paper). Straight numpy port, ~200 lines. Produces visibly better cloud shapes than plain Perlin at zero install cost. This is where I would actually invest the day of work.

**Honest comparison vs your current numpy fog:** OpenVDB is overkill for "fog haze in a spell". For "cloud bank for a weather system" it is genuinely better — you get authentic cumulus shapes. For your 7 existing volumetric fog effects, none would visibly improve from OpenVDB; all would visibly improve from Schneider-Vos noise.

**Recommendation:** Add Schneider-Vos cloud noise to `baker_volumetric_fog.py` (cheap win). Defer OpenVDB until you have an explicit "weather system / cloud bank" effect class on the roadmap.

Sources: [OpenVDB](https://www.openvdb.org/about/), [pyopenvdb](https://www.openvdb.org/documentation/doxygen/python.html), Nubis cloud-rendering paper (Schneider/Vos, GDC 2015 — still SOTA for game clouds).

---

## Q6 — VFX authoring beyond hand-written effect.json?

The honest answer: **the bottleneck is not the JSON syntax, it is the parameter-space exploration.** Three approaches:

1. **LLM-driven param synth (your existing pattern, just better-prompted).** Build `pipelines/vfx/author_llm.py`: feeds a small Pydantic schema + 3-shot examples of your best hand-tuned effects to Claude/GPT, takes a description ("dark crackling necrotic mist with green sparks"), returns effect.json. This already works — the only missing piece is a tight schema doc + curated few-shot examples. Fastest path, ~1 day.
2. **Param-space search (`optuna` / `nevergrad`).** Define a "judge" — could be a tiny CLIP-similarity score against a reference image, or just "max variance across frames + matches color palette". Run 100 trials, pick the best. Genuinely useful for the "all 18 effects look the same" problem because it forces variation. Open-source, Python-native.
3. **Node-graph authoring (Layer.ai-style)** — out of scope unless you want to build a UI. Skip.

**Recommendation:** Build option 1 first (a `effect_from_description.py` LLM tool with strong few-shot priming). If after 30 generated effects they still look samey, layer optuna on top to optimize for visual diversity against a curated reference set. Don't build a node graph editor — that is months of work for a single-user pipeline.

---

## Q7 — Audio-VFX sync: 2026 standard for "VFX with embedded audio as one asset"?

There is no industry-wide standard for "PNG flipbook + audio as one file". The two real options:

1. **USD (Universal Scene Description)** — actually adopted in 2026 across Maya/Blender/UE/Unity. USD supports timed audio attributes via the `UsdMedia.SpatialAudio` schema. Overkill for your use case (and Godot's USD support is nascent), but if you wanted "one shipped asset", a `.usdz` package containing flipbook texture refs + audio + timeline is the genuine 2026 answer.
2. **Your existing `manifest.json` with `audio_cues` frame-indexed triggers** is honestly the right pattern for Godot-native shipping. The only upgrade I would make: add an *optional* `audio_clip` field that points to an OGG file co-located in the effect directory, and let Godot's SpriteFrames runtime auto-fire it on frame 0. That gets you "ships as one folder" — not one file, but functionally one asset.

Skip USD here. The cost (USD tooling, .usdz packaging, Godot USD plugin maturity) does not pay back for a single-engine target. If you ever need to ship effects to a non-Godot consumer, revisit.

**Recommendation:** Extend your existing `manifest.json` schema with `audio_clip` + `audio_volume_db` + `audio_pitch_jitter` fields. Stay with the folder-as-asset convention.

Sources: [USD pipeline 2026](https://cgaxis.com/usd-pipeline-2026-universal-scene-description-adoption/).

---

## Verdict on the deferred GPU plan

**Replace it.** The current `GPU_BACKENDS_PLAN.md` is half-stale: Taichi is in maintenance mode, LiquidFun is dead, PhiFlow is overkill, only Warp survives.

Rewrite the plan to be Warp-only, with this scope:

1. `baker_warp_particle.py` — port `baker_particle_cpu.py` integrator to `@wp.kernel`. Same effect.json schema. Validate visual parity ±1% pixel diff. ~1-2 days. Win: 100x throughput, enables 100k-particle effects that aren't feasible on CPU.
2. `baker_warp_smoke.py` — port semi-Lagrangian to Warp at 128³ with curl-noise turbulence. ~3-5 days. Win: visibly thicker, more detailed plumes (the real quality jump comes from resolution + turbulence, not solver class).
3. *Defer Warp fracture/SPH.* Use Blender Cell Fracture for 3D fracture (Q4) and stay with numpy + Schneider-Vos noise for fog (Q5).

**Pre-flight check before starting:** verify `pip install warp-lang` on your Win11 + Py 3.12 + CUDA 12.8 setup actually initializes on sm_120 with the canonical `wp.init(); print(wp.get_devices())` test. As of v1.11.1+, this works per Isaac Lab issue #4951; if it does not, pin to v1.13.0 explicitly.

**The honest meta-finding:** your "18 of 24 effects are palette-swap recolors" problem is a content/authoring problem, not a sim-throughput problem. Even if Warp lands tomorrow, the next 18 effects will still be palette swaps unless you also build the LLM-driven authoring tool from Q6. Sequence Q6 *before* Q1 if you have to choose. The pipeline plumbing is already real; the content thinness is the actual blocker.
