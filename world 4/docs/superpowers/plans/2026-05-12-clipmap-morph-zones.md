# Clipmap Morph Zones Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the visible elevation cliff at every clipmap-ring boundary by morphing each ring's heightmap toward the next-coarser ring's heightmap inside a thin band at the ring's outer edge.

**Architecture:** Two-texture blend in the vertex shader. Each non-outermost ring binds *both* its own displacement texture AND the next coarser ring's; the shader computes a `[0..1]` morph factor based on Chebyshev distance from ring center and `mix()`es the two heights. The fragment-shader normal computation morphs identically so lighting matches geometry. `ClipmapWorld._finalize_ring_upload` is extended so finalizing ring `i` also updates ring `i-1`'s coarse-side uniforms.

**Tech Stack:**
- GDScript 2 (Godot 4.5) — runtime
- GLSL (Godot's gdshader dialect) — vertex + fragment changes
- Python 3.12 + pytest — quality-tier knob test
- No new third-party deps

---

## File Structure

**Modified files:**
- `the world 4/config/quality_tiers.json` — new `morph_band_fraction` per tier.
- `pipeline/quality_tiers.py` — add `morph_band_fraction` to `KNOWN_KEYS`.
- `tests/test_quality_tiers.py` — extend `test_resolve_values_sane` to pin the new knob's range.
- `the world 4/shaders/terrain_world_v3.gdshader` — add coarse-sampler uniforms, morph factor, blend in `vertex()` and `compute_normal()`. Also fix the PITFALLS #8 half-texel UV offset that's currently missing.
- `the world 4/scripts/ClipmapRing.gd` — new `set_coarse_uniforms()` method that mirrors `set_ring_uniforms()` shape.
- `the world 4/scripts/ClipmapWorld.gd` — read `morph_band_fraction` at `_resolve_config`; compute per-ring `_morph_band_m`; in `_spawn_rings`, configure outermost ring to disable morph; in `_finalize_ring_upload`, also push this ring's data to ring `i-1`'s coarse uniforms.
- `the world 4/worlds/scale_v2/material_world_v3.tres` — add the new shader-parameter defaults.

**Boundary discipline:** the shader does morph math. ClipmapWorld plumbs the data. ClipmapRing is a passive carrier of uniforms. No ring branches on "am I the innermost / outermost" — the outermost ring just gets `morph_enabled = false` set externally.

---

## Task 1: Add `morph_band_fraction` quality-tier knob (test-first)

**Files:**
- Modify: `the world 4/config/quality_tiers.json`
- Modify: `pipeline/quality_tiers.py`
- Modify: `tests/test_quality_tiers.py`

- [ ] **Step 1: Add the failing test for the new key**

Edit `tests/test_quality_tiers.py`. Add this test below the existing `test_resolve_values_sane`:

```python
def test_morph_band_fraction_in_known_keys():
    """morph_band_fraction must be required across all tiers."""
    from quality_tiers import KNOWN_KEYS
    assert "morph_band_fraction" in KNOWN_KEYS


def test_morph_band_fraction_range():
    """morph_band_fraction is a float in (0, 0.5]; lower tiers wider."""
    fractions = {name: resolve(name)["morph_band_fraction"]
                 for name in ["low", "medium", "high", "ultra"]}
    for name, f in fractions.items():
        assert isinstance(f, float), f"{name}: {type(f).__name__}"
        assert 0.0 < f <= 0.5, f"{name}: {f} outside (0, 0.5]"
    # Sanity: low has the widest band (most averaging on weak hw),
    # ultra the narrowest.
    assert fractions["low"] >= fractions["medium"] >= fractions["high"] >= fractions["ultra"]
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
cd "D:/assets/world 4" && "C:/Program Files/Python312/python.exe" -m pytest tests/test_quality_tiers.py::test_morph_band_fraction_in_known_keys tests/test_quality_tiers.py::test_morph_band_fraction_range -v 2>&1 | tail -10
```

Expected: both FAIL.
- `test_morph_band_fraction_in_known_keys` — `assert "morph_band_fraction" in KNOWN_KEYS` is False because we haven't added the key.
- `test_morph_band_fraction_range` — `KeyError: 'morph_band_fraction'` because no tier has it yet.

- [ ] **Step 3: Add the key to JSON via Python helper**

Use the Python helper pattern (avoids the Write tool's UTF-16 trap on Windows):

```bash
"C:/Program Files/Python312/python.exe" -c "
import json
path = r'D:/assets/world 4/the world 4/config/quality_tiers.json'
cfg = json.loads(open(path, encoding='utf-8').read())
fractions = {'low': 0.20, 'medium': 0.12, 'high': 0.10, 'ultra': 0.08}
for tier, f in fractions.items():
    cfg['tiers'][tier]['morph_band_fraction'] = f
open(path, 'w', encoding='utf-8', newline='\n').write(json.dumps(cfg, indent=2) + '\n')
print('added morph_band_fraction to all 4 tiers:', fractions)
"
```

Expected output: `added morph_band_fraction to all 4 tiers: {'low': 0.2, 'medium': 0.12, 'high': 0.1, 'ultra': 0.08}`.

- [ ] **Step 4: Add the key to `KNOWN_KEYS` in the Python resolver**

In `pipeline/quality_tiers.py`, find the `KNOWN_KEYS` tuple:

```python
KNOWN_KEYS = (
    "ring_count",
    "ring_grid_n",
    "ring_grid_step_base_m",
    "heightmap_format_inner",
    "heightmap_format_outer",
    "collision_rings",
    "splat_texture_array_size",
    "splat_resolution_per_ring_m",
    "shadow_quality",
    "update_interval_s",
)
```

Add `"morph_band_fraction",` as the final entry:

```python
KNOWN_KEYS = (
    "ring_count",
    "ring_grid_n",
    "ring_grid_step_base_m",
    "heightmap_format_inner",
    "heightmap_format_outer",
    "collision_rings",
    "splat_texture_array_size",
    "splat_resolution_per_ring_m",
    "shadow_quality",
    "update_interval_s",
    "morph_band_fraction",
)
```

- [ ] **Step 5: Re-run tests, verify they pass**

```bash
cd "D:/assets/world 4" && "C:/Program Files/Python312/python.exe" -m pytest tests/test_quality_tiers.py -v 2>&1 | tail -15
```

Expected: all 10 tests pass (8 existing + 2 new).

- [ ] **Step 6: Re-run cross-impl test (the GDScript resolver must still agree)**

```bash
cd "D:/assets/world 4" && "C:/Program Files/Python312/python.exe" -m pytest tests/test_quality_tiers_cross_impl.py -v 2>&1 | tail -5
```

Expected: pass. The GDScript resolver loads the same JSON; adding a new float key to every tier doesn't change its behavior (no int coercion needed for floats).

- [ ] **Step 7: Commit**

```bash
git -C "D:/assets" add "world 4/the world 4/config/quality_tiers.json" "world 4/pipeline/quality_tiers.py" "world 4/tests/test_quality_tiers.py"
git -C "D:/assets" commit -m "morph: 1. morph_band_fraction tier knob (low=0.20 to ultra=0.08)"
```

---

## Task 2: Shader — coarse-heightmap sampler + half-texel UV fix

**Files:**
- Modify: `the world 4/shaders/terrain_world_v3.gdshader`

This task adds the coarse-side uniforms and helpers, fixes the missing `+ 0.5/n` half-texel offset on the existing `sample_height`, and adds `compute_morph_factor`. Vertex + fragment functions still use *only* the inner heightmap at this point — Task 3 wires the morph into the actual displacement. Splitting like this keeps each shader-touch reviewable.

- [ ] **Step 1: Add coarse-sampler uniforms**

In `the world 4/shaders/terrain_world_v3.gdshader`, find the existing uniform block:

```glsl
uniform sampler2D displacement : filter_linear, repeat_disable, hint_default_black;
uniform vec2 ring_origin_m = vec2(0.0, 0.0);
uniform float ring_extent_m = 512.0;
uniform int ring_texel_n = 128;
uniform int ring_index = 0;
```

Append these uniforms directly after `ring_index`:

```glsl

// Morph-zone uniforms (Stage 3.6+). The "coarse" texture is the
// next-coarser ring's heightmap; the inner ring blends its own
// heightmap toward it inside a band near its outer edge. The
// outermost ring has no coarser ring; ClipmapWorld sets
// `morph_enabled = false` on the outermost ring's per-ring material.
uniform sampler2D coarse_displacement : filter_linear, repeat_disable, hint_default_black;
uniform vec2 coarse_origin_m = vec2(0.0, 0.0);
uniform float coarse_extent_m = 1024.0;
uniform int coarse_texel_n = 128;
uniform float morph_band_m = 25.0;
uniform bool morph_enabled = true;
```

- [ ] **Step 2: Fix `sample_height` — add the missing half-texel offset (PITFALLS #8)**

Find:

```glsl
float sample_height(vec2 world_xz) {
	float n = float(ring_texel_n);
	// "extent_n" maps world XZ to UV such that vertex (i,j) lands at
	// the center of texel (i,j). See header note #2.
	float extent_n = ring_extent_m * n / max(n - 1.0, 1.0);
	vec2 uv = (world_xz - ring_origin_m) / extent_n;
	float h = texture(displacement, uv).r;
	if (isnan(h) || isinf(h)) {
		h = 0.0;
	}
	return h;
}
```

Replace the UV line so the half-texel offset is included:

```glsl
float sample_height(vec2 world_xz) {
	float n = float(ring_texel_n);
	// extent_n + (0.5 / n) maps world XZ to UV such that vertex (i,j)
	// lands at the center of texel (i,j). See PITFALLS #8 for why
	// the `+ 0.5/n` term is mandatory with filter_linear.
	float extent_n = ring_extent_m * n / max(n - 1.0, 1.0);
	vec2 uv = (world_xz - ring_origin_m) / extent_n + vec2(0.5 / n);
	float h = texture(displacement, uv).r;
	if (isnan(h) || isinf(h)) {
		h = 0.0;
	}
	return h;
}
```

- [ ] **Step 3: Add `sample_coarse_height`**

Add this function directly below `sample_height`:

```glsl
// Sample the next-coarser ring's heightmap at the same world XZ.
// Same shape as sample_height; differs only in the sampler + uniforms
// it reads. Used by vertex() for the morph blend.
float sample_coarse_height(vec2 world_xz) {
	float n = float(coarse_texel_n);
	float extent_n = coarse_extent_m * n / max(n - 1.0, 1.0);
	vec2 uv = (world_xz - coarse_origin_m) / extent_n + vec2(0.5 / n);
	float h = texture(coarse_displacement, uv).r;
	if (isnan(h) || isinf(h)) {
		h = 0.0;
	}
	return h;
}
```

- [ ] **Step 4: Add `compute_morph_factor`**

Add this function below `sample_coarse_height`:

```glsl
// Morph factor in [0, 1]. 0 inside the ring's safe interior;
// linearly ramps to 1 at the ring's outer edge over a band of
// `morph_band_m` meters. Uses Chebyshev (max-axis) distance from
// the ring's snap center to give square-shaped morph bands matching
// the square ring geometry.
float compute_morph_factor(vec2 world_xz) {
	vec2 center = ring_origin_m + vec2(ring_extent_m * 0.5);
	vec2 d_xz = abs(world_xz - center);
	float d = max(d_xz.x, d_xz.y);
	float R = ring_extent_m * 0.5;
	float band = max(morph_band_m, 1e-6);
	return clamp((d - (R - band)) / band, 0.0, 1.0);
}
```

- [ ] **Step 5: Parse-check via `--import`**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "terrain_world_v3|error|parse|shader" | head -10
```

Expected: no output (silent = clean). If you see `Parse Error` or `ERROR`, read the line number and fix the syntax before continuing.

- [ ] **Step 6: Confirm visual output is unchanged (sanity)**

The shader changes so far only **add** the half-texel offset to `sample_height`. The visual cliff should be slightly different but not yet fixed (morph isn't wired yet). Run a walk capture and confirm the scene still renders:

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_clipmap_debug.tscn" 2>&1 | tail -5
```

Expected: `[capture] wrote res://captures/axis1_clipmap_debug_2026_05_12.png`. The terrain should still render (no shader compile failure). Cliff still visible — that's expected; morph is Task 3.

- [ ] **Step 7: Commit**

```bash
git -C "D:/assets" add "world 4/the world 4/shaders/terrain_world_v3.gdshader" "world 4/the world 4/captures/axis1_clipmap_debug_2026_05_12.png"
git -C "D:/assets" commit -m "morph: 2. shader uniforms + helpers + half-texel UV fix (PITFALLS #8)"
```

---

## Task 3: Shader — wire morph into vertex() and compute_normal()

**Files:**
- Modify: `the world 4/shaders/terrain_world_v3.gdshader`

- [ ] **Step 1: Update `vertex()` to blend inner + coarse heights**

Find:

```glsl
void vertex() {
	vec3 model_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float h = sample_height(model_world.xz);
	// `+=`, not `=` — see header note #1.
	VERTEX.y += h;
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}
```

Replace with:

```glsl
void vertex() {
	vec3 model_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float h_inner = sample_height(model_world.xz);
	float h;
	if (morph_enabled) {
		float h_outer = sample_coarse_height(model_world.xz);
		float m = compute_morph_factor(model_world.xz);
		h = mix(h_inner, h_outer, m);
	} else {
		h = h_inner;
	}
	// `+=`, not `=` — preserves skirt depth (see PITFALLS #7).
	VERTEX.y += h;
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}
```

- [ ] **Step 2: Update `compute_normal()` to morph normals identically**

The fragment shader computes a per-pixel normal from heightmap finite differences. For lighting to match the morphed geometry, the normal must also morph. Find:

```glsl
vec3 compute_normal(vec2 world_xz) {
	float n = float(ring_texel_n);
	float texel_m = ring_extent_m / max(n - 1.0, 1.0);
	float hL = sample_height(world_xz - vec2(texel_m, 0.0));
	float hR = sample_height(world_xz + vec2(texel_m, 0.0));
	float hD = sample_height(world_xz - vec2(0.0, texel_m));
	float hU = sample_height(world_xz + vec2(0.0, texel_m));
	// Central differences: dH/dx ~ (hR - hL) / (2 * texel_m), same for z.
	float dhdx = (hR - hL) / (2.0 * texel_m);
	float dhdz = (hU - hD) / (2.0 * texel_m);
	return normalize(vec3(-dhdx, 1.0, -dhdz));
}
```

Replace with:

```glsl
vec3 compute_normal(vec2 world_xz) {
	float n = float(ring_texel_n);
	float texel_m = ring_extent_m / max(n - 1.0, 1.0);
	float hL = sample_height(world_xz - vec2(texel_m, 0.0));
	float hR = sample_height(world_xz + vec2(texel_m, 0.0));
	float hD = sample_height(world_xz - vec2(0.0, texel_m));
	float hU = sample_height(world_xz + vec2(0.0, texel_m));
	if (morph_enabled) {
		// Blend toward the coarse ring's local normal so lighting
		// matches the morphed geometry. Sample coarse heights at the
		// SAME texel_m offsets — coarse-texture finite-differencing
		// uses inner-ring spacing, which intentionally low-passes the
		// coarse normal (less aliasing than its own native step).
		float m = compute_morph_factor(world_xz);
		float cL = sample_coarse_height(world_xz - vec2(texel_m, 0.0));
		float cR = sample_coarse_height(world_xz + vec2(texel_m, 0.0));
		float cD = sample_coarse_height(world_xz - vec2(0.0, texel_m));
		float cU = sample_coarse_height(world_xz + vec2(0.0, texel_m));
		hL = mix(hL, cL, m);
		hR = mix(hR, cR, m);
		hD = mix(hD, cD, m);
		hU = mix(hU, cU, m);
	}
	float dhdx = (hR - hL) / (2.0 * texel_m);
	float dhdz = (hU - hD) / (2.0 * texel_m);
	return normalize(vec3(-dhdx, 1.0, -dhdz));
}
```

- [ ] **Step 3: Parse-check**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "terrain_world_v3|error|parse|shader" | head -10
```

Expected: silent.

- [ ] **Step 4: First-light capture**

At this point the shader can morph, but ClipmapWorld isn't yet binding the coarse uniforms — every ring sees `coarse_displacement` as a default-zero black texture, so the morph blend pulls heights toward 0 near boundaries. Captures will show **rings dipping toward Y=0 near their outer edge**. That's expected, ugly, and the next task fixes it. Snapshot it for the record:

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_clipmap_debug.tscn" 2>&1 | tail -5
```

Expected: capture writes successfully. The PNG will show distorted terrain near ring boundaries — confirms the shader IS sampling the coarse texture (which is currently empty).

- [ ] **Step 5: Commit**

```bash
git -C "D:/assets" add "world 4/the world 4/shaders/terrain_world_v3.gdshader"
git -C "D:/assets" commit -m "morph: 3. wire morph blend into vertex() + compute_normal()"
```

---

## Task 4: ClipmapRing — `set_coarse_uniforms` API

**Files:**
- Modify: `the world 4/scripts/ClipmapRing.gd`

- [ ] **Step 1: Add the new method**

In `the world 4/scripts/ClipmapRing.gd`, find the existing `set_ring_uniforms`:

```gdscript
# Stage 3+: per-ring shader uniforms. ClipmapWorld calls this each
# time the ring's snap position changes (which is also when the
# displacement texture is regenerated).
func set_ring_uniforms(origin_m: Vector2, extent_m: float, texel_n: int,
					   ring_idx: int) -> void:
	var mat := _get_shader_material()
	if mat == null:
		return
	mat.set_shader_parameter("ring_origin_m", origin_m)
	mat.set_shader_parameter("ring_extent_m", extent_m)
	mat.set_shader_parameter("ring_texel_n", texel_n)
	mat.set_shader_parameter("ring_index", ring_idx)
```

Add this method directly below it:

```gdscript


# Stage 3.6+: morph-zone uniforms describing the NEXT COARSER ring.
# ClipmapWorld calls this whenever the coarser ring's heightmap
# regenerates. The outermost ring's caller should pass
# `enable_morph = false` (with any other values) so its shader
# bypasses the blend.
func set_coarse_uniforms(coarse_tex: ImageTexture, coarse_origin_m: Vector2,
						 coarse_extent_m: float, coarse_texel_n: int,
						 morph_band_m: float, enable_morph: bool) -> void:
	var mat := _get_shader_material()
	if mat == null:
		return
	if coarse_tex != null:
		mat.set_shader_parameter("coarse_displacement", coarse_tex)
	mat.set_shader_parameter("coarse_origin_m", coarse_origin_m)
	mat.set_shader_parameter("coarse_extent_m", coarse_extent_m)
	mat.set_shader_parameter("coarse_texel_n", coarse_texel_n)
	mat.set_shader_parameter("morph_band_m", morph_band_m)
	mat.set_shader_parameter("morph_enabled", enable_morph)
```

- [ ] **Step 2: Parse-check**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "ClipmapRing|error|parse" | head -10
```

Expected: silent (or just the script-registration lines).

- [ ] **Step 3: Commit**

```bash
git -C "D:/assets" add "world 4/the world 4/scripts/ClipmapRing.gd"
git -C "D:/assets" commit -m "morph: 4. ClipmapRing.set_coarse_uniforms() API"
```

---

## Task 5: ClipmapWorld — plumb coarse uniforms in spawn + finalize

**Files:**
- Modify: `the world 4/scripts/ClipmapWorld.gd`

This task is the meat. ClipmapWorld:
1. Reads `morph_band_fraction` from the tier and stores per-ring `_morph_band_m_per_ring`.
2. At `_spawn_rings` time, on the outermost ring, calls `set_coarse_uniforms(..., enable_morph=false)` so the morph blend is bypassed (no coarser ring exists).
3. At `_finalize_ring_upload(ring i)` time, also updates ring `i-1`'s coarse-side uniforms (because ring i is *i-1*'s coarse). If `i == 0`, no inner ring exists; skip.

- [ ] **Step 1: Add the tier knob to `_resolve_config` + new state**

In `the world 4/scripts/ClipmapWorld.gd`, find the existing state declarations:

```gdscript
# Resolved at _ready, never changes during the session.
var _ring_count: int = 0
var _ring_grid_n: int = 0
var _ring_grid_step_base_m: float = 0.0
var _update_interval_s: float = 0.0
var _fmt_inner: String = "RF"
var _fmt_outer: String = "RH"
var _collision_rings: int = 1
```

Add below them:

```gdscript
var _morph_band_fraction: float = 0.10

# Per-ring morph band width in meters. Index = ring_index.
# Resolved once at _spawn_rings, used by _finalize_ring_upload to
# push uniforms into ring (i-1)'s coarse-side material slot.
var _morph_band_m_per_ring: Array[float] = []
```

Then find `_resolve_config`:

```gdscript
func _resolve_config() -> void:
	var qt: Dictionary = QualityTiers.get_current()
	_ring_count = override_ring_count if override_ring_count > 0 else int(qt["ring_count"])
	_ring_grid_n = override_ring_grid_n if override_ring_grid_n > 0 else int(qt["ring_grid_n"])
	_ring_grid_step_base_m = override_ring_grid_step_base_m if override_ring_grid_step_base_m > 0.0 else float(qt["ring_grid_step_base_m"])
	_update_interval_s = override_update_interval_s if override_update_interval_s > 0.0 else float(qt["update_interval_s"])
	_fmt_inner = String(qt["heightmap_format_inner"])
	_fmt_outer = String(qt["heightmap_format_outer"])
	_collision_rings = int(qt["collision_rings"])
	print("[ClipmapWorld] tier=%s rings=%d grid_n=%d step=%.1fm formats=%s/%s collision_rings=%d" % [
		qt.get("_tier", "?"), _ring_count, _ring_grid_n,
		_ring_grid_step_base_m, _fmt_inner, _fmt_outer, _collision_rings])
```

Replace with:

```gdscript
func _resolve_config() -> void:
	var qt: Dictionary = QualityTiers.get_current()
	_ring_count = override_ring_count if override_ring_count > 0 else int(qt["ring_count"])
	_ring_grid_n = override_ring_grid_n if override_ring_grid_n > 0 else int(qt["ring_grid_n"])
	_ring_grid_step_base_m = override_ring_grid_step_base_m if override_ring_grid_step_base_m > 0.0 else float(qt["ring_grid_step_base_m"])
	_update_interval_s = override_update_interval_s if override_update_interval_s > 0.0 else float(qt["update_interval_s"])
	_fmt_inner = String(qt["heightmap_format_inner"])
	_fmt_outer = String(qt["heightmap_format_outer"])
	_collision_rings = int(qt["collision_rings"])
	_morph_band_fraction = float(qt["morph_band_fraction"])
	print("[ClipmapWorld] tier=%s rings=%d grid_n=%d step=%.1fm formats=%s/%s collision_rings=%d morph_band=%.2f" % [
		qt.get("_tier", "?"), _ring_count, _ring_grid_n,
		_ring_grid_step_base_m, _fmt_inner, _fmt_outer, _collision_rings,
		_morph_band_fraction])
```

- [ ] **Step 2: Compute per-ring band width in `_spawn_rings`**

Find `_spawn_rings`. After the existing `for i in range(_ring_count):` loop (the one that creates each `ClipmapRing`), but BEFORE the "Force first heightmap eval" loop, the function already does:

```gdscript
	# Force first heightmap eval at world origin (rings will re-snap
	# to camera position on the first _process tick).
	for r in _rings:
		_refresh_ring_heightmap(r, Vector2.ZERO)
```

Insert this between the spawn loop and the eval loop:

```gdscript
	# Precompute each ring's morph band width in meters. The morph
	# happens INSIDE this ring's edge — so it's a fraction of THIS
	# ring's outer half-extent, not of the coarser ring.
	_morph_band_m_per_ring.clear()
	for ring_i in _rings:
		var half_extent: float = (float(ring_i.grid_n) - 1.0) * ring_i.grid_step_m * 0.5
		_morph_band_m_per_ring.append(half_extent * _morph_band_fraction)
	# The outermost ring has no coarser ring to blend toward. Disable
	# its morph blend up front; subsequent _finalize_ring_upload calls
	# won't touch its coarse-side uniforms again.
	var outermost_idx: int = _rings.size() - 1
	if outermost_idx >= 0:
		_rings[outermost_idx].set_coarse_uniforms(
			null, Vector2.ZERO, 1.0, 1, 0.0, false)
```

That call binds nothing to `coarse_displacement` (the shader's default
`hint_default_black` is fine since `morph_enabled = false` short-
circuits the sampler anyway).

- [ ] **Step 3: Push coarse uniforms from `_finalize_ring_upload`**

Find the existing `_finalize_ring_upload`:

```gdscript
# Main thread only. Owns GPU upload + per-ring shader uniforms.
# Bulk PackedByteArray → Image.create_from_data → ImageTexture is
# much faster than per-pixel set_pixel (which is what GDScript per-vert
# code paths default to).
func _finalize_ring_upload(r: ClipmapRing, ring_center: Vector2,
						   origin: Vector2, heights: PackedFloat32Array,
						   n: int, step: float) -> void:
	var extent: float = (float(n) - 1.0) * step
	# Heightmap format intent: tier knob is honored when GDScript gets a
	# float32→float16 helper. Until then, both inner and outer rings
	# store FORMAT_RF; the sampler reads .r as float either way so the
	# shader is correct. Tracked as a follow-up.
	var img := Image.create_from_data(n, n, false, Image.FORMAT_RF,
									  heights.to_byte_array())
	var tex: ImageTexture = ImageTexture.create_from_image(img)
	r.set_displacement_texture(tex)
	r.set_ring_uniforms(origin, extent, n, r.ring_index)
	# Update collision proxy if this ring has one. No-op if not.
	r.update_collision_heightmap(heights, n)
	# Position the ring's StaticBody3D (parent of CollisionShape3D)
	# at the ring's snap position so collision coordinates match the
	# rendered geometry. ClipmapRing's global_position is already at
	# ring_center, so the child collision sits there automatically.
```

Add this code immediately after `r.update_collision_heightmap(heights, n)`:

```gdscript
	# Morph plumbing: this ring's freshly-uploaded texture is the
	# COARSE input for ring (ring_index - 1). Push it. (If ring_index
	# is 0, no inner ring exists; skip.)
	if r.ring_index > 0:
		var inner: ClipmapRing = _rings[r.ring_index - 1]
		var inner_band_m: float = _morph_band_m_per_ring[r.ring_index - 1]
		inner.set_coarse_uniforms(
			tex, origin, extent, n, inner_band_m, true)
```

- [ ] **Step 4: Parse-check**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "ClipmapWorld|error|parse" | head -10
```

Expected: silent.

- [ ] **Step 5: Smoke-run — log line should include `morph_band=`**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_clipmap_debug.tscn" 2>&1 | tail -5
```

Expected: the log line now reads `[ClipmapWorld] tier=high rings=4 grid_n=128 step=2.0m formats=RF/RH collision_rings=2 morph_band=0.10`. The capture file writes successfully.

- [ ] **Step 6: Commit**

```bash
git -C "D:/assets" add "world 4/the world 4/scripts/ClipmapWorld.gd" "world 4/the world 4/captures/axis1_clipmap_debug_2026_05_12.png"
git -C "D:/assets" commit -m "morph: 5. ClipmapWorld plumbs coarse uniforms (spawn + finalize)"
```

---

## Task 6: Material .tres — add the new shader-parameter defaults

**Files:**
- Modify: `the world 4/worlds/scale_v2/material_world_v3.tres`

The shader compiles fine without explicit defaults in the .tres (uniforms have inline defaults). But adding them keeps the inspector sane and makes "morph off" a clean two-clicks-away debug state.

- [ ] **Step 1: Rewrite the material .tres via Python helper**

```bash
"C:/Program Files/Python312/python.exe" -c "
content = '''[gd_resource type=\"ShaderMaterial\" load_steps=2 format=3]

[ext_resource type=\"Shader\" path=\"res://shaders/terrain_world_v3.gdshader\" id=\"shader\"]

[resource]
shader = ExtResource(\"shader\")
shader_parameter/ring_origin_m = Vector2(0.0, 0.0)
shader_parameter/ring_extent_m = 512.0
shader_parameter/ring_texel_n = 128
shader_parameter/ring_index = 0
shader_parameter/coarse_origin_m = Vector2(0.0, 0.0)
shader_parameter/coarse_extent_m = 1024.0
shader_parameter/coarse_texel_n = 128
shader_parameter/morph_band_m = 25.0
shader_parameter/morph_enabled = true
shader_parameter/show_debug_color = false
shader_parameter/debug_color_strength = 0.5
shader_parameter/base_albedo = Color(0.55, 0.52, 0.48, 1.0)
shader_parameter/base_roughness = 0.85
shader_parameter/base_metallic = 0.0
'''
open(r'D:/assets/world 4/the world 4/worlds/scale_v2/material_world_v3.tres', 'w', encoding='utf-8', newline='\n').write(content)
print('wrote material_world_v3.tres')
"
```

Expected: `wrote material_world_v3.tres`.

- [ ] **Step 2: Verify Godot still accepts the material**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "material_world_v3|error|parse" | head -10
```

Expected: silent (no parse errors).

- [ ] **Step 3: Commit**

```bash
git -C "D:/assets" add "world 4/the world 4/worlds/scale_v2/material_world_v3.tres"
git -C "D:/assets" commit -m "morph: 6. material_world_v3.tres adds coarse + morph defaults"
```

---

## Task 7: A/B captures + visual sign-off

**Files:**
- Create: `the world 4/captures/axis1_clipmap_morph_off_2026_05_12.png`
- Create: `the world 4/captures/axis1_clipmap_morph_on_2026_05_12.png`
- Create: `the world 4/captures/axis1_clipmap_morph_off_topdown_2026_05_12.png`
- Create: `the world 4/captures/axis1_clipmap_morph_on_topdown_2026_05_12.png`

We want a side-by-side: cliff present (morph off) → cliff gone (morph on). Save both.

- [ ] **Step 1: Capture "morph off" walk + topdown**

Temporarily flip the material's `morph_enabled` to `false` via Python helper, then run both capture scenes:

```bash
"C:/Program Files/Python312/python.exe" -c "
p = r'D:/assets/world 4/the world 4/worlds/scale_v2/material_world_v3.tres'
text = open(p, encoding='utf-8').read()
text = text.replace('shader_parameter/morph_enabled = true', 'shader_parameter/morph_enabled = false')
open(p, 'w', encoding='utf-8', newline='\n').write(text)
print('morph_enabled = false')
"

"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | tail -2

"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_clipmap_debug.tscn" 2>&1 | tail -3

"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_clipmap_debug_topdown.tscn" 2>&1 | tail -3
```

Rename the captures so we have an "off" record:

```bash
"C:/Program Files/Python312/python.exe" -c "
import shutil
for src, dst in [
    (r'D:/assets/world 4/the world 4/captures/axis1_clipmap_debug_2026_05_12.png',
     r'D:/assets/world 4/the world 4/captures/axis1_clipmap_morph_off_2026_05_12.png'),
    (r'D:/assets/world 4/the world 4/captures/axis1_clipmap_debug_2026_05_12_topdown.png',
     r'D:/assets/world 4/the world 4/captures/axis1_clipmap_morph_off_topdown_2026_05_12.png'),
]:
    shutil.copy(src, dst)
    print('copied', src, '->', dst)
"
```

Inspect both PNGs (use the Read tool on the file paths). The cliff at ring boundaries should be visible.

- [ ] **Step 2: Capture "morph on"**

Flip the flag back:

```bash
"C:/Program Files/Python312/python.exe" -c "
p = r'D:/assets/world 4/the world 4/worlds/scale_v2/material_world_v3.tres'
text = open(p, encoding='utf-8').read()
text = text.replace('shader_parameter/morph_enabled = false', 'shader_parameter/morph_enabled = true')
open(p, 'w', encoding='utf-8', newline='\n').write(text)
print('morph_enabled = true')
"

"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | tail -2

"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_clipmap_debug.tscn" 2>&1 | tail -3

"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_clipmap_debug_topdown.tscn" 2>&1 | tail -3
```

Rename:

```bash
"C:/Program Files/Python312/python.exe" -c "
import shutil
for src, dst in [
    (r'D:/assets/world 4/the world 4/captures/axis1_clipmap_debug_2026_05_12.png',
     r'D:/assets/world 4/the world 4/captures/axis1_clipmap_morph_on_2026_05_12.png'),
    (r'D:/assets/world 4/the world 4/captures/axis1_clipmap_debug_2026_05_12_topdown.png',
     r'D:/assets/world 4/the world 4/captures/axis1_clipmap_morph_on_topdown_2026_05_12.png'),
]:
    shutil.copy(src, dst)
    print('copied', src, '->', dst)
"
```

Inspect both. The cliff at ring boundaries should be gone (or significantly reduced) in the morph-on captures.

- [ ] **Step 3: Print the editor verification command for the user**

Per `workflows/verifying-visual-change.md` + memory `editor_launch_workflow.md`, **do not background-launch the editor**. Print this for the user:

> Run this in a terminal and walk around the clipmap debug scene for 30 seconds to confirm the cliff is gone:
>
> `"C:/Godot/Godot_v4.5-stable_win64.exe" --path "D:/assets/world 4/the world 4"`
>
> Open `scenes/clipmap_debug.tscn`, F6 to play, WASD around. Watch for:
> 1. **No elevation cliff** at ring boundaries (the main thing we fixed)
> 2. **Smooth transitions** as you walk across boundaries (the morph band creates a thin smooth zone where heights blend)
> 3. **No new artifacts** at the morph band edges (if you see faceting, we'll swap linear→smoothstep)
>
> Tell me what you see.

Wait for the user's verdict.

- [ ] **Step 4: Commit captures**

After the user confirms the cliff is gone:

```bash
git -C "D:/assets" add "world 4/the world 4/captures/axis1_clipmap_morph_off_2026_05_12.png" "world 4/the world 4/captures/axis1_clipmap_morph_off_topdown_2026_05_12.png" "world 4/the world 4/captures/axis1_clipmap_morph_on_2026_05_12.png" "world 4/the world 4/captures/axis1_clipmap_morph_on_topdown_2026_05_12.png"
git -C "D:/assets" commit -m "morph: 7. A/B captures (cliff off → cliff on)"
```

---

## Task 8: PITFALLS + STATE + build-note

**Files:**
- Modify: `the world 4/docs/reference/PITFALLS.md`
- Modify: `the world 4/docs/STATE.md`
- Create: `the world 4/docs/build-notes/MORPH_ZONES_BUILD_NOTES_2026_05_12.md`

- [ ] **Step 1: Add PITFALLS #11 — missing morph zone**

In `the world 4/docs/reference/PITFALLS.md`, find the symptom matrix table (near the top, around line 14-25). Add a new row at the bottom:

```
| Elevation cliff at every clipmap ring boundary; persists with no other artifacts | **#11 — Clipmap without morph zones** |
```

Then find the end of "Pitfall #10" section. After its closing `---`, insert:

```markdown

## Pitfall #11 — Clipmap rendering without morph zones

### Symptom
- Visible elevation cliff / step at every ring boundary on a clipmap
  terrain renderer
- Cliff persists from any camera angle and any walking direction
- Cliff is stable (doesn't flicker) when the camera is still — it's
  a real geometric mismatch, not a timing bug
- More dramatic on outer rings (coarser grids alias the heightmap more)

### What's actually happening
Each clipmap ring stores its heightmap at its own grid resolution. Ring
0 at 2m grid captures fine kernel detail; ring 1 at 4m grid stores a
downsampled (effectively low-pass-filtered) version of the same world
heightfield. In the rings' overlap zone they sample the same world XZ
but their textures encode different values — ring 0 the fine truth,
ring 1 the blurred version.

The geometry has to be at *some* elevation, and the GPU's z-fight
arbitrarily picks one ring's fragment per pixel. Adjacent pixels can
land on different rings → visible step.

### Working fix
**Morph zones (geomorphing).** Each non-outermost ring's vertex shader
samples both this ring's heightmap AND the next coarser ring's, blends
them by a `[0..1]` factor that's 0 in the ring interior and ramps to 1
inside a thin band near the ring's outer edge:

```glsl
float h_inner = sample_height(world_xz);
float h_outer = sample_coarse_height(world_xz);
float m = compute_morph_factor(world_xz);   // band width tunable
float h = mix(h_inner, h_outer, m);
```

At the precise boundary, `m = 1` → inner ring's vertices displace
using the outer ring's heightmap, which is exactly what the outer ring
shows. Heights converge → cliff disappears.

Per-fragment normals must morph identically so lighting matches the
morphed geometry.

The morph band is a quality-tier knob (`morph_band_fraction`); wider on
low tiers (more averaging acceptable on weak hw), narrower on ultra.

### What this is NOT
Not the same as PITFALLS #8 (half-texel UV offset) — that's a sampling
alignment issue. The morph cliff exists even with #8 fixed because the
two rings' heightmaps genuinely encode different values.

Not the same as PITFALLS #6 (per-tile splat boundaries) — that was
RGBA color discontinuity in the tile-paging renderer; this is height
geometry in the clipmap renderer.

### How to recognize it next time
If you build a clipmap-style renderer with per-ring heightmaps and you
see boundary cliffs even after fixing UV alignment and async-latency
issues — you need morph zones.

---
```

- [ ] **Step 2: Update STATE.md**

Find the "Active work" section. Update the Stage 3 line:

```markdown
- ✅ **Stage 3 — Heightmap stack integration**: complete pending
  editor verification. `terrain_world_v3.gdshader` (lit PBR + per-
  fragment normals + half-texel UV correction). `ClipmapWorld` reads
  `QualityTiers.get_current()` and drives `KernelComposer` via
  `WorkerThreadPool` (async double-buffer with task-supersede on
  rapid snap changes). `HeightMapShape3D` collision on the inner
  `collision_rings` (tier knob). All deviations from plan documented
  in `build-notes/AXIS1_PATH2_STAGE3_BUILD_NOTES_2026_05_12.md`.
```

Insert below it:

```markdown
- ✅ **Stage 3.6 — Morph zones**: complete pending editor
  verification. Eliminates the elevation cliff at every ring boundary
  by sampling both this ring's heightmap and the next coarser ring's
  in the vertex shader, blending by Chebyshev distance from ring
  center. Per-fragment normals morph identically.
  `morph_band_fraction` tier knob (Low 0.20 → Ultra 0.08). Full
  writeup in `build-notes/MORPH_ZONES_BUILD_NOTES_2026_05_12.md`.
  Also fixes PITFALLS #8 (half-texel UV offset that was missing in
  v3 shader). Adds PITFALLS #11 (missing morph zone).
```

Also update the pitfall count near the bottom:

```markdown
See `reference/PITFALLS.md` for the canonical list with diagnosis +
fix per entry. Current count: **11 documented pitfall classes**:
```

(Was 10; bump to 11 because we're adding #11 in this task.)

- [ ] **Step 3: Write the build-note**

Create `the world 4/docs/build-notes/MORPH_ZONES_BUILD_NOTES_2026_05_12.md` via the Write tool with this content:

```markdown
# Morph zones — build notes

> Eliminates the elevation cliff at clipmap ring boundaries via
> two-texture heightmap blending in the vertex shader. Shipped
> 2026-05-12 on `main`.

## What shipped

| Task | Component | Commit |
|---|---|---|
| 1 | `morph_band_fraction` quality-tier knob + 2 unit tests | (see git log) |
| 2 | Shader uniforms + helpers (`sample_coarse_height`, `compute_morph_factor`); half-texel UV fix (PITFALLS #8) | (see git log) |
| 3 | Shader: morph blend in `vertex()` and `compute_normal()` | (see git log) |
| 4 | `ClipmapRing.set_coarse_uniforms()` API | (see git log) |
| 5 | `ClipmapWorld` plumbs coarse uniforms (spawn + finalize) | (see git log) |
| 6 | `material_world_v3.tres` defaults for new uniforms | (see git log) |
| 7 | A/B captures + visual sign-off | (see git log) |

**Test count:** 54 → 56 (2 new quality-tier tests).

**Visual delta:** see `captures/axis1_clipmap_morph_off_*.png` vs
`captures/axis1_clipmap_morph_on_*.png` for the A/B.

## The morph factor

Each non-outermost ring computes a per-fragment morph factor `m`:

```
center = ring_origin_m + ring_extent_m * 0.5
d = max(|world_xz - center|)          # Chebyshev
R = ring_extent_m * 0.5
band = ring_extent_m * 0.5 * morph_band_fraction
m = clamp((d - (R - band)) / band, 0.0, 1.0)
```

- `m = 0` in the ring's safe interior (`d < R - band`)
- `m = 1` at the ring's outer edge (`d = R`)
- Linear ramp between (not smoothstep — cheaper, visually
  indistinguishable for this band size)

Both vertex height AND fragment normal blend the same way:

```glsl
h = mix(h_inner, h_outer, m);
// for normals: mix each finite-difference sample identically
```

## Architecture diagram

```
Worker thread: _compute_heightmap_floats
                ↓ PackedFloat32Array
Main thread: _finalize_ring_upload(ring i)
                ├──> ring i: set_displacement_texture, set_ring_uniforms,
                │            update_collision_heightmap
                └──> ring (i - 1).set_coarse_uniforms(this ring's data, true)
                    (skipped if i == 0; no inner ring exists)

Outermost ring (i = ring_count - 1):
    set_coarse_uniforms(null, ZERO, 1.0, 1, 0.0, false)
    once at _spawn_rings; never touched again. morph_enabled = false
    short-circuits the blend.
```

## Plan deviations

None significant. The plan was followed step-by-step. Note that the
half-texel UV fix in Task 2 was an opportunistic correction —
PITFALLS #8 had documented the issue but the v3 shader was missing
the `+ 0.5/n` term in its UV calculation; corrected here as part of
touching the sampler.

## Lessons + new pitfalls

- **PITFALLS #11 added** — Clipmap without morph zones. Linked from
  the morph_band_fraction knob description for future readers.

## What's next

Stage 4 — clipmap splat + biome rendering. With cliffs eliminated,
biome-blending artifacts can be debugged independently.
```

- [ ] **Step 4: Commit**

```bash
git -C "D:/assets" add "world 4/docs/reference/PITFALLS.md" "world 4/docs/STATE.md" "world 4/docs/build-notes/MORPH_ZONES_BUILD_NOTES_2026_05_12.md"
git -C "D:/assets" commit -m "morph: 8. PITFALLS #11 + STATE refresh + build-note"
```

---

## Self-review notes

**Spec coverage:**
- ✅ "Add `morph_band_fraction` to JSON tier config, update `KNOWN_KEYS`" → Task 1
- ✅ "Shader: add morph uniforms + sample_coarse_height + compute_morph_factor" → Task 2
- ✅ "Update vertex() and compute_normal() to blend inner/coarse" → Task 3
- ✅ "Fix the half-texel offset (PITFALLS #8) while touching the sampler" → Task 2 step 2
- ✅ "ClipmapRing.set_ring_uniforms extended to also accept the coarse inputs (or new `set_coarse_uniforms`)" → Task 4 (chose the latter)
- ✅ "ClipmapWorld._finalize_ring_upload pushes this ring's data as the coarse-inputs of ring (i-1)" → Task 5 step 3
- ✅ "ClipmapWorld._spawn_rings reads morph_band_fraction from tier; sets morph_band_m on each ring; disables morph on the outermost ring" → Task 5 steps 1-2
- ✅ "Walk + topdown A/B captures. PITFALLS update for the new 'missing morph zone' entry." → Tasks 7 + 8
- ✅ "Build-note + STATE refresh" → Task 8

**Placeholder scan:** none. Every step has exact paths, complete code (including the surrounding context for `find / replace with`), and exact expected output.

**Type consistency check:**
- `set_coarse_uniforms(coarse_tex: ImageTexture, ...)` matches the calls in Task 5 step 2 (passes `null` for the outermost ring) and Task 5 step 3 (passes `tex: ImageTexture`).
- `morph_band_m` (float, meters) flows: tier JSON (`morph_band_fraction` fraction) → `_morph_band_fraction` field → per-ring `_morph_band_m_per_ring[i]` (multiplied by half-extent) → `set_coarse_uniforms(..., morph_band_m, ...)` → shader uniform `morph_band_m`. Consistent type and name everywhere it's referenced.
- `morph_enabled` is a bool everywhere.

**Out-of-scope items deferred:**
- Smoothstep variant of the morph factor (the spec said "if linear looks faceted, swap to smoothstep" — not implementing speculatively).
- Issue 3 dark hexes — explicitly deferred until after Stage 4 textures (per the user's call).
