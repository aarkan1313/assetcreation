# Future World Sources — 2026-05-08

**Status**: forward-looking, not in scope. M1–M5 owns current iteration.
This doc is a queued-options register for "what could feed the world3
pipeline next, after the current iteration closes."

Two unrelated tracks captured here:

- **Track A**: alternative heightmap / world sources that plug into the
  existing terrain pipeline (NLCD land-cover, bathymetry, planetary
  DEMs, sketch-to-heightmap, fantasy world generators).
- **Track B**: explorable interiors / structures (castle interiors,
  building insides). Different pipeline shape — not heightmap-based.
  Belongs adjacent to props/POI work but worth pre-planning.

Neither track starts work today. This is the "shape of the option" so
when the orchestrator picks one up after M1–M5, the design space is
already mapped.

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

NLCD is the technical winner. Azgaar is the breadth winner. Both pair
nicely with M4 splat work, so consider sequencing one of them after
M4 lands.

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

## Status + next-decision pointer

This doc is **not a plan**. It's an option register.

When M1–M5 closes and the orchestrator asks "what next," this doc
gives a starting list:

- Track A: NLCD land-cover ingest (highest leverage; pairs with M4)
- Track A: bathymetry + coastal (extends domain; medium cost)
- Track A: planetary DEMs (variety + stress-test for kits)
- Track A: fantasy world generators (fills fantasy axis cheaply)
- Track B: explorable interiors (B-stage 0 — pick one sub-category)

User should pick the next direction; this doc is here to make the
picking easier.

---

## Change log

- **2026-05-08**: Initial draft. Two tracks (alternative world
  sources + explorable interiors). Forward-looking only; not in
  scope for current M1–M5.
