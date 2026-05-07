# Region configs (`region.config.v1`)

One `*.region.json` per playable region. Drives `region_pipeline_from_config.py`.
Pattern modeled on `meshy/batch_pipeline.py` jobs.json — declarative,
swap-able, batchable.

## Schema

```json
{
  "_schema": "region.config.v1",
  "id": "death_valley_basin",

  "source": {
    "kind": "opentopo" | "stitch" | "stac" | "synthetic",
    "preset": "bryce_hoodoo" | null,
    "bbox": [W, S, E, N] | null,
    "dataset": "USGS10m" | "COP30" | "ArcticDEM10m" | "LINZ1m_DTM" | ...,
    "bathymetry": false,
    "skip_dem": true
  },

  "style": { "name": "mythic", "strength": 1.3 },

  "biomes": ["forest", "grassland", "mana_crystal", "grassland"],

  "splat": { "mode": "gaussian" | "soft" | "hard" | "height_blend" },

  "shader": {
    "preset": "topdown" | "triplanar" | "hextile" | "heightblend",
    "triplanar": null
  },

  "terrain": {
    "size_m": null,
    "height_m": null,
    "mesh_subdiv": 256,
    "use_real_extents": false
  },

  "scatter": { "max_instances": 800 },
  "stage":   { "cam": "character", "walkable": true },

  "size": 1024,
  "seed": 7,
  "project": "C:\\Users\\josep\\test\\new-game-project",
  "quality": "default"
}
```

## Field reference

### `source`
DEM acquisition. `kind` picks the loader:
- `opentopo` — `import_dem.py`, with `preset` or `bbox` + `dataset`
- `stitch` — multi-tile region built by `tile_stitch.py`; same bbox + dataset
- `stac` — `fetch_regional_stac.py` for ArcticDEM / REMA / LINZ
- `synthetic` — pure procedural via `fastnoise_height.py` or `mesa_terrain.py`

`bathymetry: true` adds GEBCO seafloor merge under the land DEM (only
meaningful for kind=opentopo). `skip_dem: true` reuses an existing DEM
bundle in `pipelines/terrain/output/<id>/` — set this for cached regions.

### `style`
Fantasy-edit transform applied to the heightmap.
- `name`: `realistic` (passthrough), `exaggerated`, `terraced`, `sharpened`,
  `spired`, `floating`, `mythic`
- `strength`: scalar multiplier (0.5..2.0 typical; default 1.0)

### `biomes`
4-tuple in splat-channel order (R, G, B, A). Available biome ids in
`art_lab/biomes/biome_texture_registry.json`. Duplicates allowed (channels
fill from the world.json position, not registry).

### `splat`
- `gaussian` (1.6 px Gaussian blur on biome boundaries; soft default)
- `soft` (3.2 px; for atmospheric biome zones)
- `hard` (no blur; sharp 1-px boundaries)
- `height_blend` (RESERVED — currently same as `hard`; future heightblend shader will use packed alpha as height)

### `shader`
Picks a preset from `godot_pack/shaders/shader_registry.json`:
- `topdown` — pure top-down UV (default; cleanest for iso/topdown)
- `triplanar` — slope-aware top+cliff blend (best for first-person)
- `hextile` (RESERVED, falls back to topdown)
- `heightblend` (RESERVED)

`triplanar: null` uses the preset's default `triplanar_strength`. Set to a
float (0.0..1.0) to override.

### `terrain`
- `size_m: null` — use legacy 512m default UNLESS `use_real_extents=true`
- `height_m: null` — use legacy 64m default UNLESS `use_real_extents=true`
- `mesh_subdiv` — 256 (= 2m/quad on 512m plane), 512 (= 1m/quad)
- `use_real_extents: true` — read real bbox span + elev range from `dem_meta`.
  WARNING: scatter density, texture tile_meters, and camera framing are all
  calibrated for the legacy 512m diorama scale. Multi-km worlds at real
  scale produce visible mip blur and oversparse scatter. Set explicit
  `terrain.size_m` / `terrain.height_m` overrides for compromise scales.

### `scatter`
- `max_instances`: cap per asset type (keeps .tscn file size reasonable).
  Default 800.

### `stage`
- `cam`: `character` (~50m ARPG/Diablo framing; default) or `worldview`
  (whole-terrain satellite view; auto-scales with `terrain.size_m`)
- `walkable`: emit HeightMapShape3D collision + CharacterBody3D player

### top-level
- `size`: internal pipeline grid resolution (1024 default; 2048 for higher
  detail; 4096 for stitched regions)
- `seed`: RNG seed for biome paint + scatter placement
- `project`: target Godot project path
- `quality`: `fast` | `default` | `strict` — texture-gate threshold

## Examples

See `death_valley_basin.region.json` for a concrete example. Generate fresh
templates with:

```powershell
python pipelines\terrain\region_pipeline_from_config.py --template my_id > my_id.region.json
```

Validate without running:

```powershell
python pipelines\terrain\region_pipeline_from_config.py --config my_id.region.json --dry-run
```
