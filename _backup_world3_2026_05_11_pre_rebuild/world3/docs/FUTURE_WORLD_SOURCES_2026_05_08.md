# Future World Sources — 2026-05-08

**Status**: forward-looking, not in scope. M1–M5 owns current iteration.
This doc is a queued-options register for "what could feed the world3
pipeline next, after the current iteration closes."

Tracks captured here:

- **Track A**: alternative heightmap / world sources that plug into the
  existing terrain pipeline (NLCD land-cover, bathymetry, planetary
  DEMs, sketch-to-heightmap, fantasy world generators, photo+depth,
  gaussian splat capture).
- **Track B**: explorable interiors / structures (castle interiors,
  building insides). Different pipeline shape — not heightmap-based.
  Belongs adjacent to props/POI work but worth pre-planning.
- **Track D** (added 2026-05-10): astronomical data sources — real
  stellar catalogs, nebula imagery, cosmic-structure data. Used the
  same way M19-M24 uses real DEMs: extract statistical signatures,
  generate new "real-but-not-Earth" instances. Feeds VFX/spells (all
  modes), scatter density (iso/topdown), sky+clouds (walk only),
  fantasy ground textures (composes with M22 patch seeding), and
  strategic-map decoration (topdown).

(Track C lives in a sibling doc:
[`FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md`](FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md)
— procedural structure generators for trees/crystals/scree/ripples that
don't fit the heightmap mold.)

No track starts work today. This is the "shape of the option" so
when the orchestrator picks one up after the current M-chain closes,
the design space is already mapped.

---

## Track A: alternative terrain/world sources

The world3 terrain pipeline today has one source class (real DEM via
OpenTopo). Adding source classes broadens what kinds of worlds the
system can render without rewriting anything below the heightmap +
meta.json + kit-binding contract.

The pipeline shape that already works:

```
source → heightmap.png + meta.json → Terrain.gd mesh + kit material
                                  → optional splat masks (after M4)
                                  → runtime scene
```

Each new source plugs in at the top and inherits everything below for
free. That's the value.

### A1. NLCD / Copernicus land-cover (HIGH VALUE)

**What**: USGS National Land Cover Database (USA, 30m) and Copernicus
Global Land Cover (worldwide, 100m) classify every pixel as forest /
grass / shrub / urban / water / desert / wetland / tundra / cropland.
Free, global, in standard GeoTIFF.

**Why high value for world3**:
- Direct splat-mask input for M4. Every real-DEM region currently
  needs manual kit assignment; NLCD gives you per-pixel ground truth
  for free.
- The land-cover classes map cleanly onto kit slots / material
  classes. forest → grass + dirt + leaf-litter mix; desert → sand +
  rock; tundra → moss + rock + ice. The mapping is small.
- Combines with the M2 transition library: every NLCD class boundary
  is a transition pair the system has to handle, so NLCD tells you
  which transitions actually appear in real geography (vs. all
  N×(N-1)/2 hypothetical pairs).

**Pipeline shape**:
- New tool `pipelines/terrain/fetch_nlcd.py` — pulls NLCD/Copernicus
  raster for a bbox.
- Resample to match the DEM's grid + size.
- Write `landcover.png` (palette-indexed) + `landcover_legend.json`
  next to `heightmap.png` in the same region bundle.
- M4 splat shader consumes `landcover.png` directly as splat weights.

**Cost / scope**: small. Cache + fetch + resample. ~half session for
the tool, plus a session to wire into the shader once M4 lands.

**Sources**:
- USA: USGS NLCD (`https://www.mrlc.gov/`) — 30m, 2021 most recent.
  Free, no key needed.
- Worldwide: Copernicus Global Land Cover (`https://land.copernicus.eu/`)
  — 100m. Also ESA WorldCover (10m, recent — check license).

**Risks**:
- Class taxonomy doesn't perfectly match world3's kits. Need a
  small mapping table.
- Resolution mismatch (DEM at 1-30m, NLCD at 30m, ESA WorldCover at
  10m). Resample aware of this.

### A2. Bathymetry + coastal blend (MEDIUM-HIGH VALUE)

**What**: GEBCO global gridded bathymetry. Free, ~15 arc-second
(~450m at equator, finer near coasts), covers the whole ocean. Already
accessible through OpenTopo's `GEBCOIceTopo` dataset.

**Why valuable**:
- Extends world3 from "terrain" to "world" — coastlines, islands,
  beaches, continental shelf, sea floor. None of these work today
  because we only fetch above-sea-level DEMs.
- Different material domain: sand, surf zone, kelp, deep sea floor,
  coral. Forces a new kit type ("aquatic kit") which exposes any
  Earth-land-only assumptions in the shader.
- Combines with NLCD: NLCD has a "water" class, bathymetry tells you
  what's *below* that water.

**Pipeline shape**:
- Fetch DEM (above-sea) AND bathy (below-sea) for the same bbox.
- Stitch at the 0m sea level into one combined heightmap.
- New kit slots: deep_water / shelf / shore / surf / beach. Handle in
  shader via height-band rules with sea-level offset in meta.json.
- Optional: water surface as a separate mesh + shader pass at Y=0.

**Cost / scope**: medium. The fetching is small (already in OpenTopo
toolkit); the shader work is the meat. Aquatic kit is a fresh design
job (~half session per kit).

**Risks**:
- Sea-level reference frame mismatches between DEM and bathy datasets.
- Water rendering is a whole shader topic of its own; the first pass
  should treat it as "flat blue plane" not "real water shader."

### A3. Planetary DEMs — Mars / Moon / Mercury (HIGH VARIETY VALUE)

**What**: USGS Astrogeology + NASA PDS publish DEMs for non-Earth
bodies in standard GeoTIFF. Mars: HRSC mosaic (50m), MOLA (463m),
HiRISE DTMs (1m for selected sites). Moon: SLDEM (60m global),
LOLA (5m near poles). Free, well-documented.

**Why interesting**:
- Instant alien/sci-fi content with REAL geology — Olympus Mons,
  Valles Marineris, lunar mare, polar ice caps.
- Forces non-Earth material design. A "Mars kit" has dust + basalt
  + iron-oxide rock + polar ice; no green, no water (unless you do
  ancient-Mars). Tests whether the kit + slot system is biome-agnostic
  or has hidden Earth assumptions.
- Sets up entire game genres (Mars colony sim, lunar exploration)
  with real reference data.

**Pipeline shape**:
- New fetch tool (or extend OpenTopo tool with a `--source` flag).
- Heightmap conversion — same pipeline as OpenTopo DEM. CRS handling
  matters (Mars uses areocentric, Moon uses selenocentric — projection
  libraries handle this).
- Per-body kits: `mars_basalt`, `mars_dust`, `mars_polar_ice`,
  `lunar_mare`, `lunar_highlands`, etc.

**Cost / scope**: medium. Fetcher is small; CRS conversion needs
testing; the kit authoring is the time sink (~1-2 sessions per body
to get a believable kit set).

**Risks**:
- Coordinate systems are unfamiliar; first run may need debugging.
- Some PDS data is in non-GeoTIFF formats (PDS3 IMG, ISIS cube) —
  may need a conversion step.
- HiRISE 1m data is huge; fetching is bandwidth-bound.

### A4. Sketch-to-heightmap (ORTHOGONAL DIRECTION)

**What**: User draws a rough map (continents, mountain ranges, rivers
as lines or paint strokes). A model converts the sketch into a
plausible heightmap that respects the user's intent.

**Why interesting**:
- Direct path into the **Source: fantasy** axis — currently empty.
- Lets the user say "I want THIS world layout" instead of finding a
  real place that looks like it.
- Pairs with M5+ work: fantasy worlds need biome assignment too;
  feed the sketch-derived heightmap through the same NLCD-style
  splat layer (with rule-driven biome assignment instead of measured).

**Pipeline shape**:
- Input: sketch PNG (user-drawn or AI-generated map).
- Convert to control signal (depth gradient, ridgelines, river
  network).
- Either: (a) use a ControlNet-style model to generate a heightmap
  from the sketch, OR (b) write a procedural pipeline that converts
  sketch features into noise-domain warps + ridgelines + erosion.
- Output: same `heightmap.png` + `meta.json` shape as OpenTopo.

**Cost / scope**: medium-large. Real research papers exist; expect to
spend time evaluating which approach works (ML-based vs. procedural
+ flow simulation). Budget 1-2 sessions for a first prototype, more
if the model approach needs training data.

**Risks**:
- Sketch-to-heightmap quality varies wildly; first results may not
  read like good terrain.
- ML models may need GPU memory we want to keep for ComfyUI.

**Worker fit**: this is real-data-pipeline-flavored work. Could be a
worker handoff once the architectural approach is settled.

### A5. Fantasy world generators (Azgaar / WorldEngine) (HIGH BREADTH VALUE)

**What**: Open-source procedural world generators that simulate plate
tectonics → continents → climate → biomes → rivers → political
boundaries. Azgaar's Fantasy Map Generator runs in browser, exports
JSON/SVG. WorldEngine is Python + headless. Both free.

**Why valuable**:
- Gives you *whole worlds* with biomes, rivers, climate, civs —
  not just heightmaps. Most of M1–M5's biome-assignment problem is
  solved for free by their climate sim.
- Plays directly into the fantasy-biome roadmap: each generator's
  biome class becomes a kit reference.
- The generators output at world scale (continents); world3 then
  picks regions out of that world for actual playable terrain.
  Cleanly nested.

**Pipeline shape**:
- Run Azgaar / WorldEngine; export world JSON.
- Parser converts world output → heightmap PNG (per region) +
  biome mask + river mask + climate metadata.
- Region picker — given a generated world, the user / system picks
  a 4km bbox to render at terrain resolution.
- Kit assignment: generator's biome class → world3 kit (mapping
  table).

**Cost / scope**: small for ingest, medium-large for full integration.
The parser is straightforward; the design question is "what does it
mean to render at 4km region scale a slice of a generator that thinks
in continents?" Resolution scaling is interesting.

**Risks**:
- Generator world scale (planet-wide) vs. world3 region scale (km)
  — need a sensible "zoom-in to region" function.
- Generator biome taxonomies don't match world3's kits. Mapping is
  small but lossy.

### A6. Real-photo + depth estimation (CHEAP NOVELTY)

**What**: Take a single satellite image, aerial photo, fantasy painting,
or game screenshot. Run through a depth-estimation model (MiDaS,
Marigold, DepthAnythingv2 — all free, all run on consumer GPUs).
Output: a plausible heightmap.

**Why interesting**:
- Lets you ingest non-DEM imagery as terrain. Movie matte paintings,
  Magic the Gathering land art, Skyrim concept art → heightmap.
- Quality varies wildly but the pipeline shape is clean.
- Combines well with the sketch-to-heightmap path (A4) — same
  conversion, different input.

**Cost / scope**: small. The models exist; integration is mostly
inference + post-processing.

**Risks**:
- Depth estimation isn't height — image-space depth ≠ real-world
  elevation. Output needs interpretation.
- Won't tile or stitch cleanly across multiple images.

### Track A summary

If I were picking the next-after-M1–M5 source-axis project, ranked:

1. **NLCD/Copernicus land-cover** — highest leverage. Force-multiplier
   on the M4 splat shader + M2 transitions. Small implementation cost.
2. **Fantasy world generators (Azgaar)** — fills the fantasy axis with
   minimal code. Probably highest "looks dramatic" payoff.
3. **Bathymetry + coastal** — extends domain meaningfully; medium cost.
4. **Planetary DEMs** — high variety value; medium cost; great for
   stress-testing the kit system.
5. **Sketch-to-heightmap** — orthogonal direction; uncertain quality.
6. **Photo + depth** — cheap experiment; uncertain payoff.
7. **Gaussian splat capture (A8, added 2026-05-11)** — asset capture
   technique for hero props / texture-reference enhancement, not a
   primary heightmap source. Smaller scope than A1-A6 but composable
   with the FLUX texture lane and M22 patch seeding.

NLCD is the technical winner. Azgaar is the breadth winner. Both pair
nicely with M4 splat work, so consider sequencing one of them after
M4 lands.

### A8. Gaussian splat capture (added 2026-05-11)

**What**: phone/camera video → 3D Gaussian Splatting reconstruction
(via gsplat or original INRIA codebase) → mesh export (via SuGaR) →
world3 catalog ingest. Used as an **asset capture method**, not a
render method. Same role as OpenTopo orthophotos but for ground-level
and mid-scale features that orthophotos can't capture well: real
rock formations, real moss patches, real cliff faces, real tree
bark, real architectural ruins.

**Why queued, not promoted**:
- Splats are a *capture* technique; downstream pipeline still consumes
  meshes + textures + masks via the bundle contract.
- Composes with the existing texture pipeline as an enhanced reference
  source: multi-view-consistent anchors for FLUX img2img (stronger
  than the single-photo `--reference-image` mode from A.10).
- Composes with M22 patch seeding: captured topology → procedural
  seed for hero locations.
- Could feed the operability G7 POI/landmark layer.

**Tooling state (2026-05-11)**: real and working on consumer hardware.
- 3D Gaussian Splatting (INRIA original) — mature, slow training
- gsplat (UC Berkeley) — faster training, cleaner Python API
- SuGaR — splat → mesh conversion
- Polycam / Luma / Postshot — consumer-grade splat capture from phone video
- ComfyUI doesn't have first-class splat support yet (some custom nodes
  exist but immature)

**Where it would slot**:
- **Texture lane**: alternate reference source for FLUX img2img. Pairs
  with the FLUX 2 9B + dev bakeoff currently staged. Multi-view
  consistency = stronger anchor pull than single-photo references.
- **Hero props / POI**: split-out asset capture path for unique
  landmark assets the M19-M24 procedural lane can't generate.
- **M22 patch seeding** (long-term): captured real topology as a
  procedural seed for hero locations.

**Pipeline shape** (if pursued):
1. `pipelines/splat/capture.py` — record reference video, validate frame coverage
2. `pipelines/splat/train.py` — train splat via gsplat
3. `pipelines/splat/to_mesh.py` — convert via SuGaR
4. `pipelines/splat/ingest.py` — wrap output in world3 contract bundle
5. Optional: `pipelines/splat/to_reference.py` — emit multi-view render
   set for FLUX img2img anchor

**Effort**: ~3-5 sessions for first-class ingest. Smaller if just used
as photoreference enhancement.

**Status**: queued. No active commitment. Revisit when:
- M14 FLUX 2 bakeoff completes and we know whether texture quality
  needs the photoreference upgrade
- M22 patch seeding lands and we know whether procedural hero
  topology needs a real-capture path
- A specific user asset (a real rock, a real ruin) needs ingestion

---

## Track B: explorable interiors / structures

This is fundamentally different from terrain. Terrain is heightmap +
material; interiors are mesh-walls + floor + ceiling + props +
gameplay flow. The world3 pipeline shape doesn't apply.

It belongs adjacent to props/POI pipelines (already noted as deferred
future scope in WORLD3_STATE_2026_05_08.md). But explorable interiors
are different from props — a prop is a single mesh; an interior is a
connected space with rooms, corridors, doors, lighting, story beats.

This section captures the design space without committing to scope.

### B1. The taxonomy: what counts as an "interior"

Distinct sub-categories with different pipeline shapes:

| Category | Examples | Scope | Generation difficulty |
|----------|----------|-------|------------------------|
| **Single-room enclosure** | Cave, hut, market stall, simple dungeon room | one mesh shell + props inside | low |
| **Building interior (small)** | House, shop, tavern (1-3 rooms) | room layout + walls + props | medium |
| **Building interior (large)** | Castle, manor, temple, dungeon | many rooms + corridors + multiple floors + connectivity | high |
| **Connected complex** | City quarter, ruined city, monastery + grounds | building + transitions + ambient | very high |
| **Vehicle interior** | Ship, train car, spaceship | shell + interior bays + props | medium |
| **Underground network** | Mines, sewers, tunnels, crypts | branching corridors + chambers | medium-high |

Different generators target different categories. A castle generator
is not a dungeon generator is not a house generator.

### B2. Pipeline shape (sketch)

```
intent: "small castle, 2 floors, throne room + servants quarters"
   ↓
floor-plan generator (rooms, doors, corridors as a graph)
   ↓
3D extrusion (walls + floor + ceiling per room; door cuts)
   ↓
material binding (wall texture per room type; floor; ceiling)
   ↓
prop placement (furniture; decoration; lighting; loot; NPCs)
   ↓
gameplay metadata (where the player can walk; doors that open;
                   triggers; quest hooks)
   ↓
runtime scene
```

Most of these stages have open-source / academic precedent:

- **Floor-plan generation**: Wave Function Collapse (WFC) is the
  standard approach. Maxim Gumin's WFC is open source; many game
  implementations exist (Caves of Qud, Townscaper, Bad North).
  Output is a tile-grid layout where adjacent tiles connect cleanly.
- **3D extrusion**: trivial once layout is fixed. Walls are quads
  between adjacent floor tiles where layout says "wall here."
- **Material binding**: the existing world3 kit/material system
  applies — interior gets its own kit class (`stone_castle_wall`,
  `wood_floor`, `tile_kitchen`).
- **Prop placement**: the existing props pipeline applies. Per-room
  prop probability tables (a kitchen has stove + table + cabinets +
  pots; a bedroom has bed + chair + chest).
- **Gameplay metadata**: navmesh + interactable markers + spawn
  points + lighting volumes. Standard Godot-side work; not generated.

### B3. Free/cheap generation tools worth surveying

For floor plans and procedural buildings:

- **WFC** (Wave Function Collapse) — algorithm, not a tool. Many
  reference implementations. Best for tile-based layouts.
- **DungeonDraft** ($20, one-time) — top-down map authoring. Not
  generative but good for hand-authored test inputs.
- **Bytehazard's room generators** — open source, simple recipes.
- **Watabou's One-Page Dungeon / City Generator** — browser tools,
  free, JSON export. Gives you a generated dungeon or city block
  layout that you can ingest.
- **3D building generators**: BuildingsGenerator (Houdini-ish, open),
  CityEngine Esri (commercial, free trial), Watabou's Medieval City.
- **AI generation**: DiffuScene (3D scene diffusion, research),
  HoloDeck (LLM-driven scene gen, research). Promising but not yet
  production-ready.
- **Game-engine plugins**: `Procedural Generator` plugins for Godot
  exist on the asset store; quality varies.

For mesh-level interior elements:

- **Modular kit assets**: Kenney (CC0), Synty (commercial bundles),
  KayKit (CC0/cheap). Pre-built modular tile sets for castles, ruins,
  cities, sci-fi corridors. Ingest as props with snap-points; layout
  generator places them on a grid.
- **Pre-baked complete interiors**: open-source UnrealEngine /
  Unity asset packs sometimes ship full buildings; you'd use them as
  hand-authored fallback / hero buildings, not generated content.

### B4. Integration with terrain pipeline

The cleanest model:

- World3 terrain pipeline owns: heightmap + ground material + chunks.
- Interior pipeline owns: building meshes + interior layouts + props.
- The integration point is **POI markers in the terrain layer**.
  Each POI marker says "instance interior X here, with this rotation,
  this scale, this seed." Terrain doesn't care about the interior;
  interior doesn't care about terrain except for ground level + door
  alignment.
- A POI is placed by either:
  - User authoring (manual placement on a region map)
  - Procedural rules (Azgaar-style "place 3 castles per kingdom")
  - OSM data (real building footprints from OpenStreetMap if
    rendering real Earth)

### B5. What interiors share with terrain (architectural overlap)

Despite the different pipeline shape, several world3 concepts apply
directly:

- **Material catalog (M1)**: interior materials (wall textures, floor
  textures, props) all live in the same catalog. Just new entries.
- **Splat shader (M4)**: less applicable inside (interiors usually use
  per-mesh materials, not splat blends), but some interior surfaces
  could use it (cave floor with dust+rock+water mix).
- **Per-mode tuning (Phase E)**: interior in walk-mode wants different
  shader params than interior in iso-mode (different visibility, less
  macro tinting).
- **Transition materials (M2)**: doorway transitions (interior
  ↔ exterior, dungeon ↔ surface), stair transitions, threshold
  materials. Direct reuse of M2 mechanics.
- **Chunk streaming (M3)**: large interiors need their own streaming
  (a castle is bigger than a chunk). Conceptually similar to terrain
  streaming.

So the interior pipeline isn't a complete fork — it's a parallel track
that consumes the same material catalog + transition library + view
modes, with its own layout generator and prop integration.

### B6. Suggested sequence (if/when this kicks off)

NOT a roadmap — a pre-planning sketch. Don't pull this forward into
M1–M5.

1. **B-stage 0**: pick one sub-category as MVP. Suggest single-room
   enclosure (a cave or simple hut) — smallest viable interior, tests
   the pipeline shape end-to-end without overcommitting.
2. **B-stage 1**: ingest a free modular kit (Kenney medieval pack
   or similar). Wire as props in the existing props pipeline. Just
   placement, no generation yet.
3. **B-stage 2**: hand-author one example interior (e.g. tavern
   ground floor) using the kit. Validates lighting + navigation +
   integration with terrain POI markers.
4. **B-stage 3**: write a WFC-based floor-plan generator for the
   chosen sub-category. Output: tile layout JSON. Don't render yet.
5. **B-stage 4**: 3D extrusion + auto material binding from layout
   JSON to in-engine scene. First fully-procedural interior.
6. **B-stage 5**: prop placement rules per room type.
7. **B-stage 6+**: scale up to building / castle / dungeon. Each
   sub-category from B1 is its own follow-up.

Each stage is roughly one focused session. Total is sub-month if
nothing surprises us.

### B7. Open questions for whenever this kicks off

- Does the user want hand-authored hero interiors (1-2 great castles)
  or procedural variety (many decent dungeons)? Different sequencing.
- Are interiors intended to be persistent across sessions, or
  rebuilt each time the player enters? Affects save-state design.
- How much is the interior pipeline expected to share with the
  terrain pipeline architecturally vs. live as a sibling system?
  Recommendation: shared catalog + transitions + view modes,
  separate generators.
- Per-game knob: which sub-categories does each game need? An RTS
  doesn't need explorable interiors at all; a CRPG needs all of
  them.

### Track B summary

Explorable interiors are large enough scope they belong as their own
multi-session track, sequenced AFTER current terrain work
(M1–M5+). The current props pipeline can absorb single-mesh interior
work (caves, single-room enclosures) without architectural change;
the moment you want layouts + connectivity + multiple rooms, you
need a real layout generator (WFC or similar).

The right starter project is "ingest a CC0 modular medieval kit, wire
as props, hand-author one tavern interior, validate the integration
hooks (POI marker + door alignment + lighting)." That answers most of
the open architecture questions before committing to a full generator
investment.

---

## Cross-track integration notes

Both Track A and Track B benefit from work happening now in M1–M5.
Specifically:

- **Material catalog (M1)** absorbs new material classes from any
  source — NLCD-derived classes, planetary materials, interior
  materials. Catalog format should be source-agnostic. Verify M1's
  schema doesn't bake in "Earth-only" or "outdoor-only" assumptions.
- **Transition library (M2)** scales to interior thresholds (door,
  stair, surface↔underground) and extends to land↔water, cliff↔beach,
  outdoor↔interior. Keep the transition data model open enough for
  these.
- **Splat shader (M4)** is terrain-only by design today, but the
  unified shader work could absorb interior-floor splatting (cave
  floor with rock+dust+water mix). Don't over-design for this — but
  if M4 ends up with "N material slots blendable per pixel," it
  applies indoors too.
- **Chunks (M3+M5)** are designed for terrain. Interior streaming is
  a parallel problem. Don't try to make terrain chunks handle
  interiors; let interiors have their own streaming model that
  respects the same memory budget.

---

## Track D: astronomical data sources (added 2026-05-10)

The world3 pipeline's "real data → procedural derivative" thesis (used
in the M19-M24 hybrid procedural roadmap for terrain) extends naturally
to **astronomical data**. Real star catalogs, sky imagery, and nebula
data offer statistical signatures that procedural noise cannot
replicate from scratch.

The user-stated principle here matches the M19-M24 erosion approach:
**don't paste real data; extract its statistics; generate new
instances**. The Pillars of Creation should never appear in the game,
but a cloud field with the Pillars' fluid-dynamics fingerprint should
be everywhere it makes sense.

### View-mode applicability matrix

This is the constraint that shapes Track D differently from A/B/C:

| Mode | Sky | Clouds | VFX/spells | Scatter density | World/strategic map |
|---|---|---|---|---|---|
| Walk (3D) | high value | high value | high value | medium | n/a |
| Iso (2.5D) | low value (clipped) | low (shadows + tint only) | high value | high value | n/a |
| Topdown | none | none (or 2D tactical overlay) | high value | high value | high value |

Track D is **not** "astronomical sky for everything." It's:
- Real-derived **sky + clouds** for walk mode
- Real-derived **VFX/spell turbulence** for all modes
- Real-derived **density distributions** for scatter (iso/topdown)
- Real-derived **map decorations** for the strategic/world map tier

### D1. Nebula-statistics → procedural cloud/VFX field generator (PROMOTED — scheduled as M33)

> **Status update 2026-05-10**: Promoted from queued option to
> scheduled work as **M33 in the M25-M39 water+weather roadmap**.
> Becomes the source for the weather track's volumetric cloud
> system. See [`M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md`](M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md)
> M33 for the scheduled deliverables. The original spec below is
> retained as design context.

**What**: extract per-class statistical signatures from Hubble/JWST
nebula imagery — radial power spectrum, structure function, anisotropy,
density correlations — then synthesize new fluid-dynamics-plausible
cloud fields with matching statistics. Cluster into ~6 nebula classes
(HII region, planetary nebula, supernova remnant, dark molecular cloud,
reflection nebula, emission nebula); each class becomes a "signature."

**Why high value**:
- Plugs directly into SpellLab's "bake-once, react-cheap" runtime
  philosophy in `docs/plans/LONG_TERM_VISION.md`. Pre-bake six cloud
  signatures; runtime samples + advects them cheaply.
- Real nebula imagery captures **physically-driven turbulence** that
  Perlin/curl noise cannot. Shock fronts, Rayleigh-Taylor instabilities,
  bow shocks around bright sources — these are the shapes that make
  volumetric VFX look "real" instead of "noise."
- Applies in every view mode. Volumetric clouds in walk; cast-shadow
  fields in iso; flat tactical-readability overlays in topdown; spell
  particles everywhere.
- License-clean: NASA imagery (Hubble, JWST, Spitzer) is public domain
  with attribution courtesy.

**Pipeline shape**:
1. `pipelines/sky/fetch_nebula_corpus.py` — pulls FITS imagery from
   MAST archive at known angular scales.
2. `pipelines/sky/nebula_statistics.py` — radial power spectrum +
   structure function + curl/divergence stats per patch.
3. `pipelines/sky/nebula_class_clustering.py` — KMeans into ~6 classes.
4. `pipelines/sky/synthesize_cloud_field.py` — generates new cloud
   fields with matching class statistics. Outputs PNGs (2D) and 3D
   volume textures (4D EXR or per-slice PNG stack).
5. Hand off to: SpellLab effect baker; world3 sky shader; M15 scatter
   density masks.

**Effort**: 2-3 sessions for prototype; ~1 additional per applied class
once the generator works.

**Direct M-chain hookpoints**:
- **M14** close-play textures could pull cloud-class signatures for
  "fog patch" / "magical haze" close-play materials.
- **M15** scatter masks gain a "nebula-cluster" distribution option
  alongside Perlin and cosmic-web (D2 below).
- **M19-M24** hybrid procedural world gains a "skybox + cloud" layer
  that wasn't in the original M19-M24 scope.
- **SpellLab v2** baker gains nebula-statistics as a turbulence prior.

### D2. Stellar/cosmic-web density → scatter mask generator (HIGH LEVERAGE)

**What**: real galaxy distribution has a specific fractal character
(filaments, voids, walls) that Perlin underspecifies. Extract the
two-point correlation function from SDSS or Gaia density maps;
generate **new** density fields with matching correlation.

**Why high value**:
- Direct M15 input. Forest scatter density that clusters like real
  forests cluster (groves, thin strips, clearings) instead of uniform
  jitter. Settlement placement with filament-like topology. Cave
  network branching.
- Works in iso + topdown where scatter density patterns are most
  visible.
- The "cosmic web" 2-point correlation is famous in cosmology and
  well-characterized; implementation is a single Python script.

**Pipeline shape**:
1. `pipelines/scatter/cosmic_web_stats.py` — fit correlation function
   from public SDSS density maps.
2. `pipelines/scatter/cosmic_web_generator.py` — generate density
   fields with matching statistics.
3. Wire into the M15 scatter mask pipeline as one option among Perlin,
   Voronoi, cosmic-web.

**Effort**: ~2 sessions; pairs with M15.

### D3. Procedural night sky derived from real stellar statistics (WALK-MODE ONLY)

**What**: don't paste the HYG catalog into the skybox. Extract its
statistics (magnitude distribution, spectral-type distribution, density
gradient across the Milky Way band, double-star fraction) and
**synthesize a new star field** with matching statistics. Same feel as
real night sky — Milky Way band, magnitude distribution, cluster
density — but the specific constellations are unrecognizable.

**Why limited but real**:
- Walk-mode only. Iso/topdown don't show sky.
- Solves the "real-but-not-Earth" constraint cleanly: feels
  astronomically right without giving away "oh that's Sirius."
- Compact: HYG is a 71 MB CSV; the synthesis is shader-level.

**Pipeline shape**:
1. `pipelines/sky/stellar_statistics.py` — fit distributions from HYG
   v4.2 or AT-HYG v3.
2. `pipelines/sky/synthesize_starfield.py` — generate point-sprite or
   shader-input star field with matching stats + spectral coloring.
3. Output: cubemap or equirectangular skybox at multiple resolutions
   (per-mode-`.tres`-style — walk needs 4K, iso could downsize, topdown
   skip entirely).

**Effort**: 1-2 sessions. Mostly statistics fitting + a shader pass.

### D4. Spectral-type → blackbody color shader for stellar/magical glows (TINY, UNIVERSAL)

**What**: OBAFGKM stellar classification has a known blackbody
temperature → RGB color curve. Two lines of shader code map a "spell
class" or "magic source type" to a real spectroscopic color.

**Why useful**:
- Unifies spell color logic with a physical anchor. M-class red dwarf
  = fire ember. O-class blue supergiant = lightning. G-class yellow
  = healing/sun magic. Free narrative coherence.
- Same code in every view mode. Walk torch flicker, iso particle
  trail, topdown spell icon — all consistent.

**Effort**: half a session. Self-contained; doesn't depend on D1-D3.

### D5. Real-DEM + nebula-statistics combined → fantasy ground textures (HIGH LEVERAGE, M19-M24 ALIGNMENT)

**What**: combine real planetary DEMs (Mars/Moon — alien-feeling macro
shapes) with nebula-derived micro-turbulence statistics. Output:
ground textures that look like nothing on Earth but feel physically
coherent. Crystalline lava plains. Frozen methane lakes. Mana-storm
wastelands.

**Why this is the fantasy-biome unlock**:
- FLUX gives us "weird-but-Earth-like" because its training set is
  Earth. Mars heightmap + nebula turbulence statistics gives us
  "weird and not Earth-like, coherent at every scale."
- Pairs with **M22** (real-DEM patch seeding) in the M19-M24 plan.
  D5 is the M22 patch-seed source for fantasy biomes.
- Becomes the fourth **style pack** in M24 (photoreal /
  painterly / topographic / **alien-real**).

**Pipeline shape**:
1. Pull lunar/martian DEMs from USGS Astrogeology (already in Track A2
   list — planetary DEMs).
2. Run M19 spectral fitting on planetary patches → "alien macro
   signature."
3. Run D1 nebula-statistics → "alien micro signature."
4. Compose: macro from #2, micro detail from #3, M20 erosion to
   harmonize.
5. Hand off to M24 as the alien-real style pack.

**Effort**: 3-4 sessions. Depends on M19-M22 being live first
(planetary DEMs are also Track A item A2).

### D6. Strategic-map decorations from real astronomical imagery (LOW EFFORT, FLAVOR)

**What**: galactic-filament patterns as faction-territory borders;
constellation polygons (IAU's 88 official boundaries) as
ancient-surveyor reckoning lines; cluster/void shapes as biome-region
masks on the world map.

**Why low priority but worth listing**:
- Pure UI flavor; doesn't change asset generation.
- Topdown-only. Doesn't fight gameplay readability if used as
  decoration tier, not gameplay tier.
- Could be a single-session UI improvement when the world map gets
  built out.

**Effort**: 1 session, standalone.

### Cross-cutting: data corpus

| Source | What | License | Disk cost | Already in plan? |
|---|---|---|---|---|
| Hubble/JWST imagery (FITS) | Nebula source for D1, D5 | Public domain w/ attribution | ~5-10 GB curated corpus | NEW |
| HYG v4.2 stellar catalog | D3, D4 | CC-BY-SA 4.0 | 71 MB | NEW |
| Gaia DR3 (via astroquery) | D2, D3 | CC-BY 4.0 | Query-time only (no local cache needed) | NEW |
| SDSS galaxy density | D2, D6 | Non-commercial credit | ~1 GB | NEW |
| Mars/Moon DEMs (USGS Astrogeology) | D5 | Public domain | ~10 GB curated | **Already in Track A2** |
| NASA constellation polygons (IAU) | D6 | Public domain | <1 MB | NEW |

Pull cost is modest (~16-21 GB total if everything pulled). Most of D1
+ D2 + D3 can run on a 1-2 GB subset.

### Sequencing recommendation (if pursued)

1. **D1 nebula-statistics generator** — **PROMOTED TO M33** in the
   M25-M39 water+weather roadmap. Becomes the weather-track cloud
   source. No longer queued; scheduled.
2. **D4 spectral-color shader** — half-session win, unifies spell color
   logic. Can ship any time.
3. **D2 cosmic-web scatter masks** — pairs with M15.
4. **D3 procedural night sky** — when world3 walk-mode captures need
   atmospheric backdrops.
5. **D5 fantasy-ground textures** — gated on M19-M22 (the hybrid
   procedural infrastructure).
6. **D6 map decorations** — flavor pass, low priority.

After D1's promotion, the remaining D2-D6 stay queued and consumer-side
per `WORLD3_COMPLETION_BAR_2026_05_10.md`.

### Cross-cutting integration constraints

D1-D5 inherit the M1 catalog / M2 transition / M4 splat / M5 chunk
constraints. Specifically:

- **D1 cloud signatures** should emit as 2D + 3D texture data, with
  metadata declaring "class" so the M1 catalog can include
  `material_role: cloud_field` and `geometry_class: volumetric` (this
  was reserved as a future role in the Cross-cutting integration
  constraints section already).
- **D2 scatter density** must emit per-chunk so it composes with
  M3/M5 chunk format and M15 scatter masks.
- **D3 starfield** is whole-region (not chunked); ships as cubemap
  alongside the per-region `meta.json`.
- **D5 fantasy-ground textures** go through `aaa_texture.py` like any
  other material; their generation pathway is novel but their output
  contract is the same.

No new shader/material taxonomy needed. Track D rides on existing
infrastructure.

### Out-of-scope for Track D

- **Real-time astronomical simulation** (orbits, day/night, celestial
  events at game time). Different problem. If we want a "real sky over
  time," that's a separate sim system, not a Track D item.
- **Direct paste of real imagery** (Hubble panels as skybox texture).
  Violates the "real-but-not-Earth" principle. The whole Track is
  about derivative statistics, not reuse.
- **VR / planetarium-grade accuracy**. Astronomical precision isn't a
  goal; aesthetic plausibility is.

---

## Status + next-decision pointer

This doc is **not a plan**. It's an option register.

When M1–M5 closes (now: when M14-M18 closes) and the orchestrator asks
"what next," this doc gives a starting list:

- Track A: NLCD land-cover ingest (highest leverage; pairs with M4)
- Track A: bathymetry + coastal (extends domain; medium cost)
- Track A: planetary DEMs (variety + stress-test for kits; **also a
  D5 prerequisite**)
- Track A: fantasy world generators (fills fantasy axis cheaply)
- Track B: explorable interiors (B-stage 0 — pick one sub-category)
- **Track D: nebula-statistics → VFX/cloud generator (D1, highest
  leverage)**
- **Track D: spectral-color spell shader (D4, half-session win)**

User should pick the next direction; this doc is here to make the
picking easier.

---

## Change log

- **2026-05-08**: Initial draft. Two tracks (alternative world
  sources + explorable interiors). Forward-looking only; not in
  scope for current M1–M5.
- **2026-05-10**: Added Track D — astronomical data sources. Six
  items (D1-D6): nebula-statistics cloud/VFX generator (highest
  leverage), cosmic-web scatter density, procedural night sky,
  spectral-color spell shader, real-DEM+nebula fantasy ground
  textures (composes with M22), strategic-map decorations. Pattern
  matches the M19-M24 real-data-derived-procedural approach.
  Sequencing guide + view-mode applicability matrix included.
- **2026-05-10 (later)**: D1 promoted from queued option to
  scheduled work as **M33** in `M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md`
  (weather-track volumetric cloud source). D2-D6 remain queued.
- **2026-05-11**: Added Track A8 — Gaussian splat capture as asset
  capture technique (not heightmap source). Queued; composes with
  texture lane as multi-view-consistent reference for FLUX img2img +
  hero prop capture + long-term M22 patch seeding seed for hero
  locations. No active commitment.
