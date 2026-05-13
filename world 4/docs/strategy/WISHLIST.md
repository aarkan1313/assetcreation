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

## Stochastic ground texturing (kill the visible-tile-repeat)

> Sibling of the vegetation entry below. Both attack the same root
> problem — "same content repeats N times reads as fake" — but at
> different scales. Decoration adds *local* variety (moss patches,
> rocks); stochastic texturing adds *regional* variety (the ground
> itself doesn't visibly repeat). The AAA path needs both.

### The problem

Today the texture pipeline produces one PBR set per prompt. Lay
that across 100 m² of terrain at 8 m tile size and you see the same
specific lichen blob 12-15 times. Internally each tile is seamless,
but the *content* repeats. At distance the eye snaps onto the
repeat instantly — kills the "real terrain" illusion.

Real AAA solves this. The wizard game (or any W4 consumer) will
hit this wall the moment it ships a scene larger than ~20 m. We
should fix it before that pressure, while the foundation is still
under our hands.

### The AAA architecture (full vision — pick MVP slice when promoted)

Three architectures stacked, each a real possible MVP on its own:

- **MVP-floor**: Layer 1 + Layer 3 only (siblings + per-tile picks).
  Cheapest. Visible repeat reduced from "12 copies in view" to "4
  copies in view" + smoother regional gradient.
- **MVP-good**: Layer 1 + Layer 2 + Layer 3 (siblings + stochastic
  UV + per-tile picks). What's outlined below in the layered
  section.
- **AAA-target**: replace Layer 1's "N siblings" with the
  "Building-block composition" architecture in the next section
  below. True per-tile uniqueness via procedural composition of
  AI-generated layered blocks. Heavier upfront, scales infinitely.

The three-layer approach is the staging ground for the AAA-target —
build the runtime infrastructure (stochastic UV, per-tile selection,
splat integration) on the simpler sibling case first. Once that's
stable, swap the sibling Texture2DArray for the procedurally-composed
per-tile Texture2DArray and we're at AAA.

#### Layer 1 — Sibling variants per slot (content-level variety)

Each material slot has **N siblings** (start with 4, can grow to 8).
All siblings of one slot share:

- Palette (per-channel statistics within tight tolerance)
- Category / surface character (all "mossy slate", not "mossy slate"
  + "polished granite")
- Edge statistics (so adjacent siblings tile cleanly against each
  other — no visible discontinuity at sibling-to-sibling boundaries)

But each sibling has different *specific* content — different moss
positions, different crack patterns, different debris distribution.

The texture pipeline already generates 4 variants per prompt
(`variants/v0-v3_albedo.png`). Currently we throw 3 away. The
sibling system instead *keeps all 4*, runs a palette-lock + edge-
match pass to constrain them into a coherent family, and ships
them as a Texture2DArray slot.

#### Layer 2 — Stochastic UV sampling (per-sibling variety)

Within each sibling, the shader samples the texture at **3 different
UV offsets per surface point**, blended by world-position noise.
Each sample is rotated by a random angle (also from world-position
noise). The result is that any single sibling produces ~12 visually
distinct "presentations" depending on where in the world the sample
lands.

Classic technique (Heitz & Neyret 2018, "Procedural Stochastic
Texturing"). Cheap at runtime, dramatic visual improvement against
repeat-spotting.

#### Layer 3 — Per-tile sibling selection (regional variety)

Each tile in the world (or each chunk at the resolution Layer 2
operates at) picks one of the N siblings based on a hash of its
world position + maybe altitude/slope. So even before stochastic UV
sampling, the *base content* of tile A is different from tile B.

Combined effect: 4 siblings × 12 effective UV-sampling presentations
= ~48 effective visual variants. Plus splat-blended biome boundaries
(Axis 6) on top.

### AAA-target: Building-block composition (replaces Layer 1 at the top)

The sibling approach above is good but bounded — N variants is
finite, and the same N tile the whole world. AAA terrain goes
further: **every tile in the world is mathematically unique**, but
all tiles share a palette and surface character.

The trick: don't generate "siblings." Generate **layered building
blocks** that the runtime composes per-tile.

#### Per slot, generate ~5-7 single-purpose layers

For (e.g.) alpine mid:
- `base.png` — the dominant dry slate surface
- `wet.png` — wet variant (sample where wetness > threshold)
- `moss.png` — moss-on-slate overlay (RGBA — alpha is moss coverage)
- `lichen.png` — lichen overlay (RGBA)
- `cracks.png` — crack detail (grayscale overlay)
- `debris.png` — loose fragment scatter (RGBA)

All blocks palette-locked to a per-slot palette spec at generation
time. Some are full RGB, some are single-channel — total storage is
close to the same as 4-sibling but each layer is single-purpose so
it's *more* useful at runtime.

#### Procedural composer (bake-time Python, runtime Texture2DArray)

For each tile in the world (or each baked chunk):

1. Sample world-position noises: `(moss_d, wet, crack_d, debris_d)`
   per tile coords + biome-region context
2. Compose albedo by layering blocks:
   ```
   final = mix(base, wet, wetness)
   final = mix(final, moss.rgb,   moss.a   * moss_d)
   final = mix(final, lichen.rgb, lichen.a * lichen_d)
   final += cracks * crack_density * 0.3
   final += debris.rgb * debris.a * debris_d
   ```
3. Similar composition for normal / roughness / AO (each block ships
   the four PBR maps)
4. Output a per-tile PBR set baked into a Texture2DArray slot

Every tile gets unique noise inputs → every tile is mathematically
unique. Palette stays coherent because all blocks share their AI-
generation palette. Decoration density is just one of the input
noises — moss density, wetness, crack density all behave like axes
of regional variation.

#### Regional variety layer (replaces Layer 3's per-tile selection)

At biome-region scale (say every 200m), the composer picks **which
block-set library** to use. Region 1: "alpine wet"; region 2:
"alpine dry"; region 3: "alpine ancient with heavy lichen". Same
composer, different inputs. Inside any one region, every tile is
unique via per-tile noise.

Total per biome: 3-5 region libraries × ~6 blocks × 4 PBR maps =
~80 baked textures per biome. Five biomes = ~400 baked textures.
Storage scales sub-linearly with world size (the world's
per-tile composition consumes those 400 textures × ∞ tile-compositions).

#### Hard problems unique to this approach

1. **FLUX doesn't generate isolated layers well.** Prompts like
   "isolated moss patches on transparent background" produce poor
   alpha masks. We'd likely need a two-step:
   a. Generate full-scene textures from FLUX
   b. SAM-segment the output into layer alphas (moss-mask, lichen-
      mask, crack-mask)
   c. Save each layer as RGBA with the alpha from segmentation
   This is a real new pipeline subsystem.
2. **Palette-lock-across-blocks** is harder than palette-lock-
   across-siblings because each block is *supposed* to differ from
   the others (wet vs dry should look different) but within a
   constrained gamut.
3. **Composition rules per biome are art-direction work.** "Alpine
   has wet-noise at frequency X, moss appears above elevation Y,
   crack density follows slope-noise at scale Z" — these need to
   be designed and tuned per biome. Real artist hours unless we
   develop a procedural-art LLM agent for it (interesting cross-cut
   with LLM-drivability).

#### Cost estimate when promoted

- **Block-generation pipeline** (FLUX → SAM-segment → RGBA layers):
  2-3 sessions
- **Palette-lock-per-block spec + tooling**: 1-2 sessions
- **Procedural composer** (Python, bake-time): 2-3 sessions
- **Per-tile baked Texture2DArray builder**: 1 session
- **Per-region library selection**: 1-2 sessions, touches renderers
- **Authoring composition rules for first biome**: 2-3 sessions
  (the art-direction loop)

Total: **~10-14 sessions for first biome**, ~3-4 sessions per
additional biome after the pipeline exists.

### What each layer costs

| Layer | Storage cost | Runtime cost | Author cost |
|---|---|---|---|
| 1 — Siblings | N× per slot (4×=20MB, 8×=40MB) | 1 array lookup vs 1 single | Palette-lock pass + edge-match pass per family |
| 2 — Stochastic UV | 0 | 3× texture samples per fragment + 1 noise lookup | Shader work, one-time |
| 3 — Tile selection | 0 (uses Layer 1's array) | 1 hash, 1 branch (or texture lookup) | None — automatic from Layer 1 + a noise map |

Storage is the biggest cost. 8 siblings × 4 maps × 1024² × 5 biomes
× 3 slots = ~2.5 GB textures total. Doable but worth the math.

### How the texture pipeline changes

Today: `tx_pipeline` generates 4 variants, picks 1 winner, ships it.

New: `tx_pipeline` generates N variants, runs `palette_lock_family()`
to constrain them into a tight palette match, runs `edge_match_pass()`
to make sure each pair tiles cleanly, ships all N as a Texture2DArray
slot (or N maps × 4 PBR channels into a slot dir).

New module: `pipeline/textures/tx_family.py`. Takes a directory of
N variant outputs, produces a palette-locked + edge-matched family.

### Open questions to resolve at promotion time

1. **How many siblings per slot?** 4 is the floor (no benefit
   below). 8 starts to add real cost without proportional benefit
   for mid-range views. Probably 4 default, configurable per slot.

2. **Palette-lock implementation.** Easiest: extract palette from
   one "anchor" variant, recolor others to match within tolerance.
   Harder but better: joint optimization across all N variants to
   land on a shared palette without any one being "the truth."

3. **Edge-match implementation.** Easiest: only allow siblings to
   tile against themselves (each tile picks ONE sibling for its
   whole area, no within-tile variation). Harder: actual Wang-tile
   edge matching so any two siblings tile cleanly. The AAA games
   typically pick the easy version and rely on the stochastic UV
   layer to hide it.

4. **Tile-selection noise scale.** Pick siblings at the scale of
   tiles (every 8m), at sub-tile scale (every 2m), or at a custom
   "biome patch" scale (every 50m for big-picture variation +
   stochastic UV for fine variation)?

5. **Integration with Axis 6 (biome splat).** Splat already handles
   biome boundaries via Texture2DArray. Siblings could be another
   axis of the same array (biome × sibling = NxM layers), or a
   separate array. Probably separate, because biome selection is
   per-fragment and sibling selection is per-region.

6. **Does this kill decoration's job, or work alongside it?**
   Decoration adds *meshes* (rocks, plants, debris). Stochastic
   texturing adds *2D content variety*. They solve different
   scales — decoration is the local visual interest, stochastic
   is the regional. Both needed.

### Why now (or at least, why scoped now)

The current 5-biome × 3-slot foundation will look "fake" the moment
we test it at scale_v2's 4 km × 4 km. We're about to put real
effort into clipmap rendering (Axis 1 Path 2). Without stochastic
texturing, that 4km world will read as "the same texture 1000 times."

This entry exists so when we hit that wall — and we will — the path
forward is laid out and we don't have to figure it out under
pressure.

### Scope estimate when promoted

- **Palette-lock + edge-match pass** in tx_pipeline: 1-2 sessions.
- **Sibling-aware Texture2DArray builder + per-tile selection
  shader work**: 2-3 sessions, requires touching ScaleWorld AND
  ClipmapWorld renderers.
- **Stochastic UV sampling shader pass**: 1 session.
- **Re-running diversity batches with family output**: ~1 day of
  GPU time per biome (8 siblings vs 4 variants).
- **Validation + tuning**: 1-2 sessions.

Total: ~6-10 working sessions when picked up. Less if we skip the
stochastic UV layer and rely on per-tile sibling selection alone
(but then the visual win is smaller).

## Vegetation + organic-asset system (Axis 5 deep-dive parking)

The decoration axis as it stands says "vegetation, rocks, scatter,
density maps per biome." That's the right shape but it hides a hard
sub-problem: **species-correct, variant-rich, high-quality 3D
vegetation that scales to thousands of instances.** Captured here
because it deserves its own multi-session project once we get to it.

### The visual ambition

When you look at the conifer chart (red spruce vs sitka vs giant
sequoia vs welwitschia), each species has a distinct silhouette,
crown shape, branch structure, bark color, needle density. We want
W4 to render each correctly **and** show variation between individual
trees of the same species (no two spruces identical) **and** support
hundreds of them in view at once. This is the hard problem.

### Why "just TRELLIS each species" fails by itself

1. **Trunks come out great, leaves don't.** Diffusion-to-3D models
   handle thin geometry badly. Needles, fronds, welwitschia's long
   leaves typically blob, fuse, or vanish during the mesh extraction.
2. **No variation.** One TRELLIS pass = one mesh = every tree in the
   forest is a clone.
3. **Not game-ready.** TRELLIS outputs are dense, awkwardly-UV'd,
   no LODs, no shader bindings.

### What "SpeciesNet" was shorthand for

I made up the term — there's no off-the-shelf product called that.
What I meant: parametric tree generators where you author per-species
parameters (trunk taper, branch angle, leaf-cluster type) and the
generator builds *N* unique trees from those rules. Real-world examples:
**SpeedTree**, **The Grove 3D**, **Blender's MTree / Sapling
add-on**, **Houdini procedural trees**. Each can produce 100 variations
of "spruce" from one rule set. Variation is free; species-correctness
needs artist tuning per species.

### W4-shaped approach (the long arc)

A vegetation system that handles all the above is realistically a
year-scale project on its own. Here's how it factors:

1. **Trunk pipeline** — TRELLIS / image-to-3D for the trunk + main
   branches per species. Cleanup + decimate to game-ready
   trunk LOD chain.
2. **Foliage pipeline** — separate problem. Two approaches:
   - **AI-generated leaf-cluster textures** + procedural placement
     on branch tips (cluster meshes get billboarded at distance).
     Quality comes from leaf-cluster textures being species-correct.
   - **Per-species leaf geometry presets** authored once. Less AI,
     more art.
3. **Variation system** — parametric *over the trunk + foliage
   primitives*. Per-instance: trunk lean, height multiplier,
   branch-rotation seed, foliage density, color variation seed,
   age (sapling/mature/dying), damage state. Each instance picks
   from a shared species kit at runtime.
4. **Placement system** — density maps per biome × species, slope/
   altitude/moisture constraints, Poisson-disk distribution,
   wind-shadow + clearings. Authored at biome level, runtime fast
   via GPU instancing.
5. **LOD ladder + impostors** — 4 tiers, see below. The 1000+ trees
   in view problem is solved with billboards + a single atlas draw
   call, not with mesh.

### The 4-LOD ladder (explicit)

| Tier | Distance | Geometry | Per-instance cost |
|---|---|---|---|
| Hero | 0–5m | Full mesh ~20k polys, real foliage geometry or dense leaf-cards | High; player-noticeable assets only |
| Mid | 5–30m | ~5k polys, simplified trunk, billboard-cluster canopy | Moderate |
| Low | 30–150m | ~500 polys low-poly trunk + single billboard canopy | Low |
| Distant | 150m+ | **2 crossed billboards** through the vertical axis, 4 triangles total | Trivial; entire forest costs less than one hero tree |

### Distant tier — 2 crossed billboards (the standard AAA trick)

Two alpha-cutout quads sharing the vertical axis, rotated 90° from
each other. From any horizontal viewing angle you see at least one
near-face-on (canopy visible) and at least one near-edge-on (gives
the tree visible thickness). Worst case is exactly 45° between the
quads — both face the camera at 45°, but still reads as a 3D tree.

**Strictly better than single-billboard** at trivial extra cost:
- Same texture, used twice; one alpha PNG per species
- 4 triangles per instance vs 2 — meaningless cost difference
- No "spinning to face camera" giveaway
- Random Y-axis rotation per instance gives cheap variety

The transition from Low → Distant is the visible-fall-off threshold;
fog/haze (Tier 1 roadmap item) helps mask it.

### Distant-tier impostor generation pipeline

Reuse the existing W4 texture pipeline; don't build a dedicated
impostor baker.

1. **Source image** — either (a) TRELLIS render of the hero mesh
   from the canonical front-orthographic angle, or (b) a real
   photograph of the species at known scale.
2. **Alpha cutout** — run SAM (Segment Anything) on the source to
   produce a tight alpha mask. The texture pipeline can already
   shell out to SAM if we wire it in (the AAA-target compositor
   in the stochastic-texturing entry needs SAM segmentation too,
   so this is shared infra).
3. **Color cleanup** — chroma-key + small dilate-erode to clean
   the alpha edge, optionally a slight inner-blur for soft edges.
4. **PBR maps** — distant-tier impostors don't need full PBR.
   Albedo alone is fine; optionally a flat normal pointing up so
   lighting matches the world's directional light direction.
5. **Output** — one ~512² or 1024² PNG per species. ~1MB compressed.
   100 species = ~100MB. Manageable storage even for a large catalog.

### Important: this pipeline generalizes WAY beyond trees

The 2-crossed-billboards + alpha-PNG-from-W4-texture-pipeline pattern
works for **any cylindrically-symmetric or mostly-distance-viewed
asset**. When implementing distant-tier infrastructure, name it
generically ("ImpostorBillboard") not "TreeBillboard", because the
same pipeline serves:

- **Plants** — flowers, ferns, succulents, tall grass tufts
- **Bushes / shrubs**
- **Cacti / agaves**
- **Mushrooms / fungi**
- **Crystals + alien geological growths**
- **Totems / monoliths / standing stones**
- **Stalagmites / stalactites** (in caves)
- **Fence posts / signposts / gravestones / lampposts**
- **Distant decorative rocks** (the bigger ones; small rocks still
  use mesh because the player sees them up close)
- **Coral / kelp / underwater organic growths**

What it fails for: anything with a strong front/back asymmetry
(faces, statues, crafted objects with a "front side"), anything
wider than tall (sprawling vines, fallen logs), and anything that
benefits visibly from realtime self-shadowing.

When the vegetation system gets promoted, design the impostor layer
generically and bring trees in as the first consumer, not as the
only consumer. Future-us will thank present-us for it.

### Scope creep direction (this is the fun part)

Once the system handles trees, it generalizes to:
- **Plants** — flowers, ferns, succulents, mosses
- **Grass** — using imposter-shells or geometry-shader fields
- **Rocks + boulders** — TRELLIS works much better for rocks than
  trees (thick geometry, no thin parts); variation per instance via
  rotation/scale/material-tint
- **Crystals** — repetitive geometric organic-like assets; great fit
  for parametric variation
- **Coral, fungi, alien plants** — anything organic + repetitious
  + benefits-from-variation

Every one of these wants the same variation system + placement
system + LOD chain. Trees just happen to be the hardest sub-case
because of thin foliage geometry.

### Honest cost estimate

Building this *right* (system that scales to N species + N
instance-types and produces visibly varied + species-correct output
at AAA distance) is **6-12 months of focused work** for one person.
But it factors cleanly:

- **Trunk-only MVP** (trees with cylindrical placeholder canopy)
  could land in a few weeks. Looks bad up close, fine at distance.
- **MVP + canopy billboards** (per-species billboard sheet, no
  variation) adds a few more weeks. Looks great at distance, OK
  close up.
- **MVP + parametric trunk variation** (each tree slightly different
  trunk shape) adds another few weeks. Now the forest reads as a
  forest, not a clone army.
- **AI-generated species-correct foliage clusters** — the hard part.
  This is where most of the time goes.

### Decision recommendation

When this gets promoted to Axis 5 deep-work, **start with rocks +
crystals** as the warm-up. TRELLIS handles them well, variation is
easy (rotate/scale/tint), and the placement + LOD pipeline gets
built on the easier asset class first. Trees come second once
placement + variation infrastructure is mature.

### Open questions to revisit

- **Is per-instance shader variation enough?** (tint, lean, foliage
  density via vertex push) Or do we need actual mesh variation
  per instance? Most AAA games use shader-only variation for grass
  + small plants; mesh variation for hero trees only.
- **How much foliage AI generation is we want to invest in?** The
  more art-time-saved by AI, the more constraint there is on the
  output quality. Hand-authored leaf clusters look better but
  scale poorly. Probably a per-priority-species decision.
- **What's the "lowest LOD" target?** A welwitschia-from-1km should
  still look like welwitschia. That's an impostor + per-species
  silhouette atlas, not "tree.png".
- **Wind animation system.** Shared uniform across all instances?
  Per-cluster phase offset? Real-time response to gameplay (wand
  spells in the wizard game)?

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
