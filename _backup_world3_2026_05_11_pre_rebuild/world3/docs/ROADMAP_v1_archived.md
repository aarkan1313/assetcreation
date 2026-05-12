# world3 — Roadmap

What we're building, in phases. Each phase ends with something you can run and
look at. We don't move on until the current phase is solid.

The principle: **data and renderer stay decoupled**. A heightmap PNG + meta.json
is the only contract. Real DEM, cropped DEM, hand-edited DEM, kernel-generated
heightmap — all interchangeable. Everything downstream (mesh, material, scenes,
gameplay) works the same regardless of source.

---

## Phase 0 — MVP loop (DONE)

Real DEM → heightmap → Godot mesh → 3 view modes → headless capture.

- [x] DEM crop pipeline (`build_world.py`, supports `--center` + `--extent-km`)
- [x] Runtime mesh + heightmap collision
- [x] Iso, topdown, walk scenes with auto-framed cameras
- [x] Walker with fly/walk toggle
- [x] Headless screenshot capture
- [x] One tile (4 km Grand Teton)
- [x] One PBR texture (rock_light, triplanar)

## Phase 1 — Each scene looks good at its native scale (NOW)

Walk, iso, topdown are different *games*. They share data, not rendering.
Split into 1a (texture pipeline) and 1b (shader + scenes) after the texture
audit on 2026-05-07.

### Phase 1a — Texture pipeline

Bad textures sabotage any shader on top. Stabilize the existing
`pipelines/textures/aaa_texture.py` workflow first.

- [ ] Raise default QA gate to grade A (<0.003 seam MSE)
- [ ] Deploy StableMaterials for structured patterns (FLUX center-biases)
- [ ] Wire palette_lock + patina_adapter for biome cohesion
- [ ] Re-grade and replace any of the 5 staged sets that don't pass
- [ ] Document the workflow (`pipelines/textures/PIPELINE.md`)

### Phase 1b — Per-scene materials + shader

- [ ] Per-scene materials: each scene owns its tile size / tuning
- [ ] Slope+height blend shader using the 5 grade-A PBR sets
- [ ] Per-scene tuning of: ambient/sun, fog, tile UV scale, shadow distance
- [ ] One iteration on iso (target: looks like a place you'd play in 3/4 ortho)
- [ ] One iteration on topdown (target: looks like a strategy / map view)
- [ ] One iteration on walk (target: looks like FPV terrain)

Exit criteria: screenshots from all three modes that we'd be happy to put in
front of someone.

## Phase 2 — Multiple tiles, intentional variety (DONE 2026-05-07)

A library of 16 regions covering different landforms, all rendering
through the same world3 pipeline.

- [x] Region catalog: `world3/jobs/regions.json` indexes 16 sites × 72
      bundles (the OpenTopo workflow's output), tagged by landform.
- [x] `RegionLoader.gd` Godot script — picks a region+dataset and points
      Terrain at the correct heightmap.
- [x] `RegionGalleryCapture.gd` — iterates regions, captures iso+topdown
      per region. One-shot validation tool.
- [x] Validated on 5 representative regions (PNW Cascades, Mojave,
      Appalachians, Tibetan Plateau, Arctic Alaska). Each one renders
      with visibly distinct landform character.

Captures: `world3/docs/captures/phase2_region_gallery/`.

Lesson learned: a single biome kit (rock_dark + grass + snow + ...)
looks correct for alpine regions but visibly wrong for desert and
tundra (the slope+height shader fires "snow" anywhere above 85%
elevation regardless of climate). Per-region biome kits is the
natural next iteration.

## Phase 3 — DEM analyzer (statistical kernels)

Convert a real DEM into a small parameter pack ("kernel") that captures its
statistical signature: elevation distribution, slope distribution, ridge
spacing, drainage density, characteristic noise spectrum.

- [ ] Per-tile analyzer: read DEM → write `kernel.json`
- [ ] Reference kernels: one per tile in the Phase 2 library
- [ ] Side-by-side renderer: original DEM vs. its kernel's reconstruction (just
      for sanity; the kernel by itself isn't a generator yet)

Exit criteria: every reference tile has a kernel pack with consistent fields,
and we have an intuition for which kernel knobs matter.

## Phase 4 — Procedural generator (kernels → new heightmaps)

The kernel becomes input to a generator that emits new, original heightmaps at
arbitrary size with arbitrary RNG seeds. Same world3 pipeline renders the output
as if it were a real DEM.

- [ ] FBM + slope-shaping generator that consumes kernel params
- [ ] Optional erosion pass (thermal, hydraulic — both are well-understood)
- [ ] Compare: real Tetons tile vs. kernel-generated "Teton-style" tile, side
      by side in iso/topdown/walk
- [ ] Kernel mixing: 60% alpine + 40% mesa, smooth transitions

Exit criteria: a "kernel + seed" gives us a heightmap good enough to render and
walk on, and the family resemblance to its source DEM is recognizable.

## Phase 5 — Infinite world (chunked streaming)

The world is no longer one tile. The renderer asks "what's at world coord X,Z
at LOD N?" and gets a chunk back from either real DEM data or the kernel
generator. Camera streams in/out chunks as it moves.

- [ ] Chunked heightmap addressing (chunk(X, Z) = one tile)
- [ ] Per-view-mode chunk grid sizing (walk=256m, iso=4km, topdown=50km)
- [ ] LOD: distant chunks at lower mesh subdivision
- [ ] Camera-driven load/unload

Exit criteria: walk in any direction without hitting a wall; iso/topdown views
update as the camera moves over the world.

## Phase 6+ — Gameplay layers

Out of scope for the terrain pipeline; here for context.

- Biome regions (forest / desert / arctic) painted over the heightmap
- Water (lakes, rivers from drainage)
- Scatter (trees, rocks, props) driven by biome + slope
- Civilization layer (settlements, roads)
- Per-game adapters (turn an iso-rendered chunk into a Bastion-style tile sheet,
  etc.)

---

## Non-goals (deliberate)

- **Photoreal rendering.** We're aiming for "looks great in its style," not
  Unreal-Engine-photoscanned realism.
- **AAA-grade LOD.** A clipmap / mesh shader implementation is overkill for
  this stage. Tile streaming is enough.
- **Worldgen as a service.** This is a single-machine tool, run from the
  command line. No web UI, no API, no multiplayer state.
- **Re-using `worldgen_v2` / `pipelines/worldgen_v2/` code.** Clean break.
  Reference only.
