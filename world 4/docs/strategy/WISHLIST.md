# Wishlist

> Cool ideas captured so they don't get lost. Each item is one line.
> Items promote to axes (see `AXES.md`) when they meet the three tests:
> significant enough to expand independently, don't fit cleanly into an
> existing axis, concrete enough to define a "next experiment."
>
> Items here are explicitly **parked**, not next-up. The anchor demo and
> existing 6 axes have priority. This is where good ideas sit so we don't
> forget them.

## Cross-cutting concerns (not axes, but pinned)

These affect every axis. Not active work, but kept visible so they get
considered each time an axis expands.

- **LLM-drivability** — every layer should be schema + validator +
  deterministic output, so an LLM can drive it without hand-holding.
  Goal: a sufficiently smart agent can author a world plan, run the
  pipeline, debug failures, and ship a world.
- **Modularity** — drop W4 into any Godot project; pick which pieces
  you want (just heightmaps? just textures? full streaming world?);
  the unused pieces don't load.
- **Quality + Performance + Organization** — see AXES.md principles.

## Major-system parking lot

Items significant enough to become their own axes eventually.

- **Climate** — precomputed climate zones from elevation + latitude
  + distance-from-water. Informs biome assignment, vegetation,
  weather patterns.
- **Weather** — runtime weather (rain, snow, wind) per region, possibly
  driven by climate. Visual + gameplay effect.
- **World map / local map split** — strategic-scale world map (1km
  view, abstracted), local map (player scale, fully rendered). Same
  data, different artifact shapes.
- **Auto-biome from DEM features** — rules infer biome assignments
  from elevation, slope, aspect, drainage instead of hand-authored
  per-tile assignment. Promotes "biome layout" from author burden to
  pipeline output.
- **Astro / moon / lunar / planetary sources** — extend axis 3 (source)
  to non-Earth DEMs. Crater fields, lunar maria, planetary bands. Same
  kernelization, different feature distributions.
- **Civilizations + POIs** — settlements, ruins, roads, landmarks
  placed by world-scale rules. Likely an axis 7 once decoration
  (axis 5) proves out.

## Axis 1 (Scale) follow-ups

These came up while shipping the first Scale expansion (1024m / 16-tile
demo) and were deliberately deferred. Some shipped subsequently — those
are crossed out.

- ~~**Async / threaded tile mesh build.**~~ Shipped 2026-05-11.
  `WorkerThreadPool` runs the vertex/normal math; only ~4ms finalize on
  main. Peak frame ms dropped 96 → 17.
- **Real-game world sizes (4km+ on a side, 256+ tiles).** Current demo
  proves the radius-paging mechanism on a 1024m / 16-tile world. A
  shipping game would have hundreds of tiles total and dozens visible.
  Requires: bigger DEM crops, bigger view_radius.
- **LOD rings.** Different mesh density per ring around the camera
  (innermost 1m, next 2m, far 4m+). Cuts steady-state vertex count
  dramatically. Interacts with the normal-stencil fix (Pitfall #4) —
  outer rings can use wider stencils for free. Half-session of work to
  do right (T-junction seams at ring boundaries are the trap).
- **View-radius vs visible-distance asymmetry.** At walk eye-height on
  a ridge, the player can see 1-2km. Current `view_radius_tiles=1` is
  smaller than the actual visible cone, so loading edges would be in-frame
  at any larger world. Bigger radius is part of the answer; LOD is the
  other part.

## Axis 4 (View) follow-ups

Shipped first expansion 2026-05-11 — three view shaders + per-view
material + per-view radius + WASD/scroll movement. These are polish
items, none blocking.

- **Topdown contour lines.** Draw a thin line every N meters of
  elevation in the topdown shader. Reads as map-style contour annotation.
- **Iso silhouette outline.** Subtle edge darkening at slope
  discontinuities (depth-buffer edge detect). Pops hills against valleys.
- **Per-view env tonemap.** Currently all views use FILMIC. Topdown
  might prefer LINEAR (map style); iso might want softer.
- **Headless topdown framing edge case.** The orthographic camera
  doesn't cleanly capture all 16 tiles in `--rendering-driver opengl3`
  captures — visible as an L-shaped crop. Appears correct in editor
  Forward+. Probably a Compatibility-renderer ortho-frustum quirk.
- **True multi-scale zoom (Crimson Desert style).** Smooth zoom from
  topdown all the way down to walk eye-level, with the shader/material
  morphing along the way. Stretch goal — see "Stretch goals" below.

## Stretch goals

Hard problems that may not be fully solvable but are worth attempting
when other axes are stable.

- **Smooth zoom from max height to ground level** — continuous zoom
  (1km → 5m) maintaining quality at every scale. Not just camera
  movement — actual LOD transitions, texture streaming, shader
  profile blends. Crimson-Desert-style view-swapping done well.
- **Cross-view consistency at game-play scale** — a feature visible at
  topdown looks like the same feature when you walk into it. River in
  the world map runs through the same valley in player view.
- **DEM-feature-driven splat** — replace height+slope splat with rules
  that read drainage, ridge proximity, aspect, etc. "Material X near
  drainage paths" instead of "material X at low elevation."

## Texture pipeline futures

Things related to axis 6 but not in its near-term scope.

- **Photoreal satellite blending** — mix OpenTopo satellite imagery
  with ComfyUI-generated textures via shaders to get "looks real but
  is stylized." Source layer for textures.
- **Style transfer from concept art** — feed a concept-art image to
  the texture pipeline, get back a PBR set that matches its palette
  and feel.
- **Per-tile texture variation** — same biome, slightly different
  texture per tile, to break tiling repetition. Could be palette
  shifts, could be different generations.
- **Biome-kit auto-generation** — given a biome name and a few prompts,
  produce the full 5-slot kit cohesively. Builds on `palette_lock.py`
  + `kit_generator.py`.

## Tooling + workflow ideas

Quality-of-life items for the human + LLM driving W4.

- **One-command "make me a world"** — pick a region, pick a style,
  run, walk in Godot. The end target of all the pipelines.
- **Live preview during texture generation** — watch the texture
  pipeline produce variants in real time, abort and re-prompt without
  full re-runs.
- **Heightmap painter** — manually edit a region of the heightmap
  (raise/lower/smooth) and have the rest of the pipeline reflow.
- **Cross-project drop-in kit** — a `world4_consumer.gd` and a few
  config files that let any Godot project pull a built W4 world.

## When something gets promoted

A wishlist item becomes an axis (or part of one) when:

1. We need it for current work (axis expansion is blocked without it)
2. We have a concrete idea of what the "next experiment" looks like
3. It doesn't fit cleanly inside any existing axis

When promotion happens, delete this file's entry, add the new axis
content to AXES.md (which means deleting and rewriting AXES.md per its
own rules).

## When something gets cut

A wishlist item gets cut when:

1. We tried it during an axis expansion and decided it's not worth
   pursuing
2. The idea is subsumed by something else we built
3. We re-evaluate and realize we don't actually want it

Cut items get deleted from this file outright. No "archive" section —
git history is the archive.

## Links

- `ANCHOR.md` — the floor that has to keep working
- `AXES.md` — the 6 active axes of expansion + principles
- W3 carry-forward inventory: `D:/assets/W4_KICKOFF_2026_05_11.md`
