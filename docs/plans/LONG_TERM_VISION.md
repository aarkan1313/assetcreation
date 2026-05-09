# Long-Term Vision Notes

User-stated direction (2026-05-06). Not a roadmap of next steps — a captured direction
to keep in mind as we make near-term choices, so we don't paint ourselves into a corner.

## The look

- **Top-down but 2.5D / isometric**, Diablo-like rather than flat top-down
- AAA-grade environment art (player view, regional view, world map all coherent)
- Camera close enough that player sees real terrain detail + props + dynamic effects
- Camera far enough that you also see strategic context (rooms, neighbouring areas)

## The feel

- **Physics-interactive water / lava / wind that's also performant**
- Walls and buildings as first-class objects, not just decals on the heightmap
- Element interactions — water hits lava, fire spreads on wood, wind moves smoke,
  ice freezes water, mana crystals charge things they touch

## Implications for what we're building now

| Now | Long-term constraint |
|---|---|
| Heightmap-based terrain | Need to support **non-heightfield geometry** later (overhangs, caves, multi-floor buildings, archways). Heightmap is fine for the floor; walls/buildings live as separate meshes. |
| Flat-top-down camera assumption | Keep our terrain bundles producing **4-channel splatmaps + height** that work for any camera angle. Don't bake camera-angle assumptions into texture pixel art. |
| Static decoration scatter | **Reactive scatter** — grass that flattens under footsteps, ash that lifts in wind, snow that compacts under walking. Need scatter instances to be addressable individually, not baked into MultiMesh. |
| No physics yet | The 17 physics engines in `D:\spell lab\` need a "**bake-once, react-cheap**" philosophy. Pre-compute the expensive stuff (fluid sims, fracture patterns) offline; runtime just plays back + applies cheap reactive forces. Spell lab review in research/C is exactly this — the user already has that direction. |

## Element-interactive simulation strategy (when we tackle it)

Per research/C_vfx.md the right pattern is **bake-once flipbooks/particles/fields, runtime cheap**. Adapted to gameplay:

- **Water**: 2D height-field water with reactive ripples. Cheap. Runs on Godot's GPU compute. Heightfield wave equation.
- **Lava**: same as water but slower, hot-rim shader, cooled-into-rock interaction. Same compute, different params.
- **Wind**: vector field driven by Perlin noise + obstacle masks. Used to drive grass sway, smoke advection, particle drift. Bake the long-term flow; reactive turbulence local.
- **Fire**: cellular-automata grid on a grid of "fuel" tiles. Kept light by limiting the grid resolution (Diablo-area = 256×256 grid is plenty).
- **Ice**: a "freeze layer" overlay on water surfaces. Thickness state per tile.

All of these are lightweight 2D fields running at sub-game-loop tick. The physics
engines we have (Taichi, LiquidFun, PhiFlow, Newton+Warp) are mostly for **baking**
the high-quality reference / pre-computed effects, then we run cheap runtime
approximations that look right.

## Walls / buildings

Two parallel pipelines we'll need:

1. **Modular building kit** — wall/floor/door/window/roof tiles, parametrised by
   biome (cinder bricks for lava, ice blocks for cavern, crystal-faceted for mana,
   timber+thatch for grassland). Auto-snap on a grid. Style-locked by biome.
2. **Hero buildings** — unique landmarks (temples, towers, ruins) generated as
   complete meshes. Probably Meshy or a guided Trellis2 pass. Then preprocessed
   like characters, then placed via the world_biome_engine landmark anchors.

## What this means for near-term decisions

**Don't bake-in:**
- Camera angle assumptions in texture pixel art (avoid sprites that only work at one tilt)
- Heightmap-only world (need an overlay layer for walls/buildings/caves)
- Scatter instances baked into MultiMesh-only (need addressable scatter)

**Do bake-in:**
- Splatmap + biome label system (already have it — works for any camera)
- Texture kits keyed by biome ID (already have it — extends to building tile sets)
- Three-tier zoom output (already have it — already designed for Diablo-scale camera)

So the world_biome_engine we just built is **forward-compatible** with this vision.
The next pieces (in priority): macro_detail Godot demo (validates the close-up AAA
story holds), then walls/buildings kit pipeline, then runtime reactive water/lava/wind
when SpellLab v2 gets to "bake-once, react-cheap" phase.

## Concrete things to remember

- The 17 spell-lab engines are for **baking** reference simulations. Runtime uses cheap
  2D field approximations driven by the baked data.
- Performance budget for runtime fluids: ~256×256 fields tickling at 30 Hz. Anything
  more goes through baked paths.
- For 2.5D iso: terrain stays heightmap-based, but **anything taller than ~2 m gets
  a separate mesh/decal layer** so we can cull, occlude, and animate independently.

## Factory operations vision (added 2026-05-09)

Beyond the assets themselves, the **factory operations** direction (how
pipelines are operated):

> "Long term I want all the pipelines to be easy to understand and used by
> both LLM and human. Basically opens up a GUI / has a perfect command/API
> set. You select the target asset you are making, you select where you are
> at in the process. Then you just set stuff up with drop-downs or whatever's
> appropriate and each workflow, tool, pipeline, etc. is represented,
> configurable, and usable end to end."

Concretely: every pipeline gets a uniform contract — `run.py` entry point,
`config_schema.json` declared knobs, `stages.json` discoverable steps,
`smoke_test.py` end-to-end shape verification, `run.json` per-run
provenance. GUI = thin frontend over the same schema-driven backend the
LLM uses; no GUI-only or CLI-only logic.

Full description in `docs/plans/ROADMAP.md` § "Long-term direction
(2026-05-09)". Pipeline-specific gaps in the gaps queue immediately
below that section. Migration is per-pipeline when each gets touched;
not a rewrite, additive over existing scripts.

This is the operations side of the same coherence goal: just as the
in-game look needs to be coherent across regions/biomes/zooms, the
factory operations need to be coherent across pipelines so a single
human or single agent can drive the whole thing.
