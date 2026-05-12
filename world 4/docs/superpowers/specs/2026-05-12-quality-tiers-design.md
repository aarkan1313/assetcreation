# Quality tiers — design

Status: approved 2026-05-12, ready to plan.

## Why

The W4 clipmap renderer (Axis 1 Path 2) will be one piece of a shipped game targeting the modal user GPU range of **GeForce 3060 → 5070 Ti** (and RX 6600 → RX 7800 XT). Right now Stage 3+ of the plan bakes in 5090-class defaults (256 grid_n × 4 rings ≈ 525k tris, per-vertex sync set_pixel, R32F everywhere). That works on a 5090 and degrades non-gracefully on a 3060.

Per project ethos (`world 4/CLAUDE.md`): **Quality ≥ Performance > everything else > time-to-ship.** This means perf budgeting is not a polish pass; it's a structural choice baked in from Stage 3 onward. Plus: the standard game-industry expectation is a user-pickable Quality preset.

This spec defines that system so Stage 3.2 onward can consume a typed config from day one, with no retrofit later.

## Scope

In: the renderer's exposed perf knobs — ring count, grid density, async behavior, texture formats, collision rings, splat density, shadow quality, update cadence. The resolver, the JSON config, both side ports (Python + GDScript), and the `ProjectSettings` integration that lets a user pick a tier.

Out: the per-platform launcher UI (separate later task), individual-knob "Custom" preset (deferred, but the architecture supports it cheaply — see Phase 2), tier-aware asset variants (separate concern, Axis 6 and Stage 4 will decide).

## The four tiers

| Knob | Low (iGPU) | Medium (1660) | **High (3060 — default)** | Ultra (5070 Ti+) |
|---|---|---|---|---|
| `ring_count` | 3 | 4 | 4 | 4 |
| `ring_grid_n` | 64 | 96 | 128 | 256 |
| `ring_grid_step_base_m` | 4.0 | 2.0 | 2.0 | 2.0 |
| `heightmap_format_inner` | `RF` | `RF` | `RF` | `RF` |
| `heightmap_format_outer` | `RH` | `RH` | `RH` | `RF` |
| `collision_rings` | 1 | 1 | 2 | 2 |
| `splat_texture_array_size` | 1024 | 2048 | 4096 | 4096 |
| `splat_resolution_per_ring_m` | 4.0 | 2.0 | 1.0 | 0.5 |
| `shadow_quality` | `off` | `low` | `high` | `high` |
| `update_interval_s` | 0.10 | 0.07 | 0.05 | 0.05 |

Approximate triangle budget (4 rings × 2 × n² tris):
- **Low**: ~25k tris  (3 rings only)
- **Medium**: ~74k tris
- **High**: ~131k tris
- **Ultra**: ~525k tris

### Knob semantics

- **`ring_count`**: number of nested clipmap rings (0 = innermost, N-1 = outermost).
- **`ring_grid_n`**: vertices per ring side. Triangle count grows as 2n².
- **`ring_grid_step_base_m`**: meters between adjacent verts in ring 0. Ring `i` step = `base × 2^i`.
- **`heightmap_format_inner` / `_outer`**: pixel format for ring-N's displacement texture. `RF` = Image.FORMAT_RF (32-bit float). `RH` = Image.FORMAT_RH (16-bit half). Inner rings (close, high detail) stay R32F at all tiers because the precision matters there.
- **`collision_rings`**: how many inner rings get a `HeightMapShape3D` collision proxy. The player typically only stays within ring 0; ring 1 helps if AI / projectiles travel further before despawn.
- **`splat_texture_array_size`**: edge length of per-biome PBR Texture2DArrays loaded for the world. Affects VRAM (16 maps × array² × 4 bytes / map).
- **`splat_resolution_per_ring_m`**: meters per splat-texel per ring. Smaller = sharper biome boundaries.
- **`shadow_quality`**: `off | low | high`. Wired in Stage 5+ when the lit shader replaces `unshaded`. Off and low are not yet implementable but the knob is reserved.
- **`update_interval_s`**: minimum seconds between ring-snap checks in `_process`. Lower = more responsive snap, more CPU.

## Architecture

### Data flow

```
ProjectSettings("world/quality_tier", "high")  ←─ user picks via launcher / main menu
                       │
                       ▼
      QualityTiers.get_current() : ConfigDict
                       │
       ┌───────────────┼───────────────────────────┐
       ▼                                           ▼
 GDScript consumers                          Python consumers
 - ClipmapWorld                              - build_clipmap_mesh_debug.py
 - ClipmapRing                               - build_splat_arrays.py (Stage 4)
 - WorldShadowRig (Stage 5+)                 - build_kernel_preview.py
```

### Single source of truth: JSON

**File:** `the world 4/config/quality_tiers.json`

Contains the table above as a dict-of-dicts:
```json
{
  "schema_version": 1,
  "default_tier": "high",
  "tiers": {
    "low":    { "ring_count": 3, "ring_grid_n": 64, ... },
    "medium": { "ring_count": 4, "ring_grid_n": 96, ... },
    "high":   { "ring_count": 4, "ring_grid_n": 128, ... },
    "ultra":  { "ring_count": 4, "ring_grid_n": 256, ... }
  }
}
```

Both runtimes load this JSON. JSON not GDScript because Python tooling (asset builders) needs to know "what splat resolution should I bake for High?" without invoking Godot.

### GDScript resolver: `QualityTiers.gd`

```gdscript
class_name QualityTiers
extends RefCounted

const CONFIG_PATH := "res://config/quality_tiers.json"

# Loaded once at startup, cached for the session.
static var _resolved: Dictionary = {}
static var _current_tier: String = ""

static func get_current() -> Dictionary:
    if _resolved.is_empty():
        _resolved = _resolve(_current_tier_from_project_settings())
    return _resolved

static func _current_tier_from_project_settings() -> String:
    var t: String = ProjectSettings.get_setting("world/quality_tier", "")
    if t.is_empty():
        # Fall back to JSON's default_tier
        var cfg := _load_json()
        return cfg.get("default_tier", "high")
    return t

static func _resolve(tier: String) -> Dictionary:
    var cfg := _load_json()
    var tiers: Dictionary = cfg["tiers"]
    if not tiers.has(tier):
        push_error("QualityTiers: unknown tier %s, falling back to %s" % [tier, cfg["default_tier"]])
        tier = cfg["default_tier"]
    _current_tier = tier
    return tiers[tier].duplicate(true)
```

Consumers call `QualityTiers.get_current()` and read named keys. They never branch on the tier string.

### Python resolver: `pipeline/quality_tiers.py`

Same shape: `quality_tiers.get_current()` returns a dict. Reads `quality_tiers.json` relative to the project. Pipeline tools take an optional `--quality-tier` CLI arg that overrides the default, useful for "bake assets for all tiers in one run."

### `ProjectSettings` integration

A bootstrap autoload (added in implementation) reads the tier from a save file or from a command-line arg. For now, **the tier is set in the editor via `Project Settings → World → quality_tier`**, defaulting to `"high"`. A launcher UI is a separate concern.

## Phase 2: custom overrides (deferred, but cheap to add)

When we want a "Custom" preset later:

```gdscript
static func apply_overrides(overrides: Dictionary) -> void:
    var base := get_current()
    for k in overrides:
        base[k] = overrides[k]
    _resolved = base
```

No consumer changes. The override layer sits between the JSON resolver and the cache. UI side: a "Custom" tab in the launcher emits a dict of changed knobs.

This is explicitly part of the design — the architecture is set up for it, not retrofitted. **But shipping Phase 1 first.**

## Validation

Tests live in `tests/test_quality_tiers.py`:

1. **All tiers parse** — loading the JSON and resolving each tier returns a dict with every expected key.
2. **Schema check** — required keys present, numeric ranges sane (no negative grid_n etc).
3. **Defaults are reasonable** — `high` resolves to the documented mid-range (`ring_grid_n=128, ring_count=4`).
4. **Unknown tier falls back** — `_resolve("bogus")` returns the `default_tier`'s config with an error pushed.
5. **(Python only)** Pipeline tools that take `--quality-tier` honor it.

GDScript side: no unit-test framework, so `--import` parse check + a `tests/test_quality_tiers_gdscript_dump.gd` SceneTree script that dumps resolved values for each tier and a Python cross-impl test compares to the Python resolver's output (same pattern as the kernel cross-impl test).

## Open questions resolved

- **JSON vs GDScript-as-source-of-truth**: JSON. Pipeline needs it.
- **One-tier vs per-knob**: presets only (Phase 1). Custom is Phase 2.
- **Default**: `high` (3060-class is modal).
- **Hot-reload**: no. Tier is set at scene/app load, applied once. Changing tier = restart scene. (Cleaner for Stage 3+, can add later if needed.)
- **Async heightmap regen as a tier knob**: not a tier knob. Heightmap regen is always async in shipping builds. A debug-time `--sync-heightmap-regen` flag may exist to make hitches easier to diagnose, but it's not part of the user-facing tier config.

## Implementation order (will go into the writing-plans handoff)

1. `quality_tiers.json` (the table)
2. `tests/test_quality_tiers.py` (Python tests)
3. `pipeline/quality_tiers.py` (Python resolver)
4. `the world 4/scripts/QualityTiers.gd` (GDScript resolver)
5. `tests/test_quality_tiers_gdscript_dump.gd` + cross-impl test (mirror of kernel cross-impl)
6. Register the `ProjectSettings` key (in `project.godot`)
7. **Then** continue Stage 3.2 — terrain_world_v3 shader reads no tier values yet, but is positioned to.
8. Stage 3.3 wires `ClipmapWorld._ready` to read `QualityTiers.get_current()` and apply `ring_count`, `ring_grid_n`, `ring_grid_step_base_m`, `update_interval_s`, `heightmap_format_inner/outer`, etc.

After Stage 3, every subsequent stage's plan should be re-read with "and which tier knob does this consume" in mind.
