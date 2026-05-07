# Ambience density autoload — Godot 4.5 setup

The audio v3 push added a per-zone density gameplay wire so that future
gameplay code can ramp ambience without coupling to the `BiomeAmbienceController`
directly. Three pieces:

1. **`AmbienceDensityAutoload.gd`** — singleton.
2. **`zone_overrides.json`** — data the singleton loads at startup.
3. **Optional 1-line patch in `BiomeAmbienceController.gd`** — registers
   itself with the autoload on `_ready()`.

## Step 1 — register the autoload

Open the Godot project. **Project → Project Settings → Globals (Autoload)**
and add:

| Path | Node Name |
|---|---|
| `res://audio/godot/ambience/AmbienceDensityAutoload.gd` | `AmbienceDensity` |

Set Enabled = on. Save the project. The singleton is now reachable from any
script as `AmbienceDensity.<member>`.

## Step 2 — controller registration (one line)

In `res://audio/godot/ambience/BiomeAmbienceController.gd`, add at the end
of `_ready()`:

```gdscript
if Engine.has_singleton("AmbienceDensity") or has_node("/root/AmbienceDensity"):
    get_node("/root/AmbienceDensity").register_controller(self)
```

(Or, if you'd rather poll: leave it out — the gameplay code can call
`AmbienceDensity.set_active_zone(...)` and you can react manually.)

## Step 3 — gameplay-side calls

When the player enters a trigger volume:

```gdscript
# in some Area3D body_entered handler
AmbienceDensity.set_active_zone("battle_arena")
```

Or programmatically, e.g. from a quest script that just opened a portal:

```gdscript
AmbienceDensity.set_zone("haunted_grove", 1.6, "forest")
AmbienceDensity.set_active_zone("haunted_grove")
```

## What's wired today

* The autoload script (`AmbienceDensityAutoload.gd`).
* The zone schema (`zone_overrides.json`) with 9 example zones covering all
  10 biomes the recipe knows about.
* The `BiomeAmbienceController` already exposes
  `density_multiplier: float = 1.0` and uses it when scheduling the
  Poisson timers. The autoload pushes new values into that field whenever
  `set_active_zone()` is called.

## What's NOT wired

* **Trigger volumes**. Gameplay code still has to know "the player is in
  zone X". The audio side has no way to know that without reaching into
  game state, which would be the wrong direction of coupling.
* **Per-stem density control**. Today density scales the wildlife AND
  distant Poisson rates uniformly. If you need to silence wildlife but
  keep distant events (e.g. quiet caves with rare crashes), extend
  `BiomeAmbienceController.gd` with separate `wildlife_density` and
  `distant_density` floats.
* **Smooth crossfades on density changes**. Density jumps are step
  changes today (the next Timer fire uses the new rate). For a smooth
  ramp, tween `density_multiplier` over a few seconds in the autoload.

## Testing

There is no headless smoke for this lane — you need the game running and
trigger volumes hit. Manual smoke:

1. Start the game with the `BiomeAmbienceController` instanced and biome
   set (e.g. `c.set_biome("forest")`).
2. Watch the wildlife event rate over ~30 seconds (visually, log the
   `_on_wildlife_tick` callback).
3. From a debugger console: `AmbienceDensity.set_zone("dbg_test", 4.0)` +
   `AmbienceDensity.set_active_zone("dbg_test")`.
4. Watch the rate quadruple over the next minute.
