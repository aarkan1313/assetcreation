# World Biome Kit — Schema v1

**Goal:** one biome JSON that produces a coherent identity at three zoom levels —
world map (≤32 px), regional map (≤256 px), and local terrain (1024+ px) —
with clean transitions to neighbouring biomes.

## Why this exists

Past world-gen attempts failed at biome boundaries because:
- **Voronoi cells** → straight-line boundaries
- **Pure noise blending** → biomes smear into each other
- **No terrain awareness** → lava in mountain peaks, ice in valleys, etc.

This schema fixes all three by making biomes **shape themselves around
terrain features** (rivers, ridges, altitude, slope) rather than being
painted on top.

## Schema

```json
{
  "id": "lava_field",
  "display_name": "Cinder Plains",
  "category": "elemental_fire",

  "identity": {
    "world_color": [180, 60, 30],      // single dominant color for ≤32px world map dot
    "regional_palette": [               // 3-4 colors for medium-zoom hatching/shading
      [180, 50, 20], [240, 110, 40], [40, 20, 12], [120, 60, 30]
    ],
    "icon_glyph": "lava",               // optional symbol for world map (volcano, snowflake, crystal, tree)
    "ambient_hex": "#1a0a08"            // fog/sky tint at this biome
  },

  "terrain": {
    "height_bias": "low_with_local_peaks",   // see HEIGHT_BIAS table below
    "slope_tendency": "broken",              // smooth | broken | sharp | rolling
    "water_behaviour": "lava",               // water | lava | ice | mana | none
    "carve_features": ["lava_cracks", "ash_drifts"],   // see FEATURES table below
    "altitude_range": [0.10, 0.55],          // where in the global heightmap this biome can sit (0..1)
    "preferred_slope_range": [0.0, 0.45]     // min/max slope it likes
  },

  "transitions": {
    "anchor_to": ["river", "altitude_band"],  // what edge the biome respects
    "blend_neighbours": {                      // per-neighbour transition strategy
      "default": {"width_px": 18, "noise_strength": 0.35, "feature_priority": "ridges"},
      "ice_cavern": {"width_px": 4, "noise_strength": 0.05, "feature_priority": "ridges",
                       "intermediate_label": "scoured_basalt"},   // creates a transition zone
      "grassland": {"width_px": 30, "noise_strength": 0.4, "feature_priority": "rivers"},
      "mana_crystal": {"width_px": 12, "noise_strength": 0.15, "feature_priority": "ridges"}
    },
    "exclusion": ["ice_cavern"]   // never directly adjacent (force scoured_basalt between)
  },

  "texture_kit": "lava_field",          // → world/textures/library/<this>_*
  "decoration_kit": "lava_field",       // → art_lab/biomes/kits/<this>.json

  "world_map_priority": 8,              // higher = drawn on top of other biomes at world zoom
  "regional_glyph_density": 0.6,        // how busy the regional view should look (0..1)

  "season_variants": {                  // optional alternates
    "winter": {"world_color": [200, 90, 60], "ambient_hex": "#2a1010"}
  }
}
```

## HEIGHT_BIAS values

These steer where the biome wants to sit in the heightmap distribution. The
terrain bundle then re-shapes its histogram so the biome's pixels actually
end up where the bias says.

| Value | Effect |
|---|---|
| `flat_low` | wants altitude 0.05–0.30, low variance — like grassland or marsh |
| `low_with_local_peaks` | mostly low but with sparse small mounds — lava, ash plain, sandstone mesa |
| `mid_rolling` | altitude 0.30–0.55, smooth — rolling hills, savannah |
| `mid_broken` | altitude 0.30–0.60, high local variance — badlands |
| `high_smooth` | altitude 0.55–0.85, smooth — alpine meadow, plateau |
| `high_broken` | altitude 0.55–0.95, sharp — mountains, ice cliffs |
| `cavern` | sub-surface — ice cavern, crystal mine, lava tube (carve below the surface in dressing) |
| `floating` | local peaks above sea — mana crystal islands, sky shrines |

## FEATURES values

Per-biome carving operations applied AFTER the global heightmap is generated
but BEFORE biome label assignment. These are what make a biome *feel* like
itself instead of generic ground.

| Feature | Effect |
|---|---|
| `lava_cracks` | random fractal Voronoi cracks 0.5–2 m deep, hot rim |
| `ash_drifts` | low-frequency noise dunes oriented by wind direction |
| `ice_spires` | sparse vertical columns 5–20 m tall, sharp top |
| `ice_caverns` | sub-surface chambers with vault ceiling |
| `crystal_spikes` | clusters of angular spikes from anchor points |
| `mana_geysers` | small floating islands with crystal spires |
| `glassy_smooth` | macro-scale smoothing of high-freq noise (obsidian, glacier) |
| `cracked_dry` | hexagonal cracks at slope < 0.1 (mud cracks, dried mana lake) |
| `forest_canopy` | bias upward by 1–3 m where vegetation density is high |
| `ruin_terraces` | step-up terraces near landmark anchors (lost city) |

## Three-tier rendering

The same kit drives all three zooms:

### World view (≤32 px per biome cell)
- One pixel = `world_color` of the biome
- Optional `icon_glyph` overlaid for distinct types
- Transitions are NOT visible at this zoom — neighbours just snap to their cell color

### Regional view (32–256 px per biome cell)
- Solid fill from `regional_palette`
- Hatching/dotting at `regional_glyph_density` showing the biome's character
- Transitions visible: smooth band of intermediate hatching following terrain features

### Local view (1024+ px = playable terrain)
- Full PBR via `texture_kit` link
- Decoration scatter via `decoration_kit` link
- Transitions visible: actual blend of textures + scatter density gradient over the
  `transitions.blend_neighbours[<other>].width_px` window, following the
  `feature_priority` (rivers / ridges / altitude bands)

## Transition algorithm

For each pixel adjacent to a biome boundary:

1. Compute distance to nearest neighbour cell (by Euclidean from biome label image)
2. Look up the per-neighbour transition spec
3. If `feature_priority == rivers`, snap the boundary to the nearest river/flow line
4. If `feature_priority == ridges`, snap to nearest ridge (high curvature)
5. If `feature_priority == altitude_band`, snap to the nearest contour at the biomes' altitude crossover
6. Apply `noise_strength * fbm` jitter on the boundary
7. Within `width_px` of the boundary, mix biome A's textures with biome B's
   based on signed distance, clamped 0..1

Result: lava follows valley floors meeting grassland at the river edge. Ice
hugs north-facing slopes and never touches a warm valley. Mana crystals
cluster at landmark peaks and fade out into rocky exposure rather than lawn.

## File layout (per kit)

```
art_lab/biomes/world_kits/<biome_id>.json    # this schema
world/textures/library/<biome_id>_anchor/    # texture set keyed by biome_id
art_lab/biomes/kits/<biome_id>.json          # decoration kit (existing schema)
```
