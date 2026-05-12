# Stage 4.1 — Single-biome rendering proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the per-ring `sampler2DArray` + per-biome PBR `sampler2DArray` plumbing works end-to-end. ClipmapWorld generates a per-ring splat array (one R8 layer, hardcoded full weight) and binds a global ground-albedo PBR array containing alpine's albedo. Every ring renders as if alpine textured the whole world.

**Architecture:** Worker thread builds an N×N×1 splat buffer (always weight 1.0 for slot 0). Main thread converts each layer to an `Image`, stitches into a `Texture2DArray`, uploads to GPU. Shader gains `splat_array`, `pbr_ground_array`, `active_biomes_n`, `biome_pbr_slot` uniforms — fragment shader samples splat layer 0, multiplies by ground albedo at the matching PBR slot, writes `ALBEDO`. No biome culler, no morph for splat, no PBR generation (uses an existing alpine texture from scale_demo if available; falls back to a neutral debug color otherwise).

**Tech Stack:**
- GDScript 2 (Godot 4.5) — runtime
- GLSL (Godot gdshader dialect) — fragment shader changes
- No new Python deps; no new tests beyond a unit test on a small splat-buffer builder

---

## File Structure

**Modified files:**
- `the world 4/shaders/terrain_world_v3.gdshader` — add splat + PBR sampler2DArray uniforms, fragment loop. Vertex unchanged.
- `the world 4/scripts/ClipmapRing.gd` — add `set_splat_uniforms(splat_array, active_biomes_n, biome_pbr_slot)` method.
- `the world 4/scripts/ClipmapWorld.gd` — add splat array generation in `_compute_heightmap_floats` companion (`_compute_splat_floats`); build splat `Texture2DArray` in `_finalize_ring_upload`; load global PBR ground array in `_load_base_material`. Wire to ring uniforms.
- `the world 4/worlds/scale_v2/material_world_v3.tres` — defaults for new uniforms.

**Boundary discipline:** the splat builder and PBR loader are isolated helpers (one each). The shader changes are additive — existing morph + heightmap paths untouched. ClipmapRing stays a passive carrier of uniforms.

---

## Task 1: Shader — add splat + PBR uniforms (no fragment changes yet)

**Files:**
- Modify: `the world 4/shaders/terrain_world_v3.gdshader`

- [ ] **Step 1: Add new uniforms**

Find the existing uniform block (the morph section we added earlier):

```glsl
uniform sampler2D coarse_displacement : filter_linear, repeat_disable, hint_default_black;
uniform vec2 coarse_origin_m = vec2(0.0, 0.0);
uniform float coarse_extent_m = 1024.0;
uniform int coarse_texel_n = 128;
uniform float morph_band_m = 25.0;
uniform bool morph_enabled = true;
```

Append directly after `uniform bool morph_enabled`:

```glsl

// Stage 4.1 splat + biome PBR uniforms.
//
// splat_array: per-ring sampler2DArray, one R8 layer per active
//   biome in this ring. Layer index = "splat slot" (dense, 0..N-1).
//   Sampled with the same world-XZ → UV mapping as `displacement`.
// pbr_ground_array: GLOBAL sampler2DArray containing every loaded
//   biome's ground albedo. Layer index = "PBR slot" (global, shared
//   across rings).
// active_biomes_n: how many splat slots this ring uses.
// biome_pbr_slot: maps splat slot i → PBR slot. Length =
//   active_biomes_n, padded to MAX_BIOMES_PER_RING with -1.
// MAX_BIOMES_PER_RING: shader compile-time constant. The loop bound.

const int MAX_BIOMES_PER_RING = 16;

uniform sampler2DArray splat_array : filter_linear, repeat_disable;
uniform sampler2DArray pbr_ground_array : filter_linear, repeat_enable;
uniform int active_biomes_n = 0;
uniform int biome_pbr_slot[MAX_BIOMES_PER_RING];

// Tiling factor for the PBR ground albedo. The PBR texture has its
// own world-meters-per-tile scale; this uniform divides world XZ
// into that tile. Defaults to 1m / texel (assumes a 1024² tex covers
// 1024m, will tune per biome later).
uniform float pbr_tile_size_m = 4.0;
```

- [ ] **Step 2: Parse-check**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "terrain_world_v3|error|parse|shader" | head -10
```

Expected: silent. (If there's a Godot 4.5 limitation on `uniform int[]` arrays, fall back to a `vec4` packed slot — but try the array first; Godot 4.5 supports it.)

- [ ] **Step 3: Verify scene still renders**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_clipmap_morph_on.tscn" 2>&1 | tail -5
```

Expected: `[capture] wrote ...`. Nothing visual changes yet — uniforms are declared but not read.

- [ ] **Step 4: Commit**

```bash
git -C "D:/assets" add "world 4/the world 4/shaders/terrain_world_v3.gdshader"
git -C "D:/assets" commit -m "stage4.1: 1. shader uniforms for splat + biome PBR arrays"
```

---

## Task 2: Shader — fragment-shader splat loop

**Files:**
- Modify: `the world 4/shaders/terrain_world_v3.gdshader`

- [ ] **Step 1: Replace the fragment `albedo` calculation**

Find the existing `fragment()`:

```glsl
void fragment() {
	// Per-fragment heightmap-derived normal. Smoother than
	// per-vertex normals interpolated across the triangle, especially
	// on outer rings where vertex density is low.
	vec3 world_normal = compute_normal(v_world_pos.xz);
	// MODEL_MATRIX here is a pure translation (ClipmapRing's
	// camera-snap), so world space == view-of-model space and we can
	// hand world_normal directly to the lighting pipeline.
	NORMAL = (VIEW_MATRIX * vec4(world_normal, 0.0)).xyz;

	vec3 albedo = base_albedo;
	if (show_debug_color) {
		int safe_ring = clamp(ring_index, 0, 3);
		albedo = mix(albedo, RING_COLORS[safe_ring], debug_color_strength);
	}
	ALBEDO = albedo;
	ROUGHNESS = base_roughness;
	METALLIC = base_metallic;
}
```

Replace with:

```glsl
// Sample this ring's albedo by summing per-biome contributions.
// uv_ring: same UV used for heightmap (per-ring, half-texel-offset).
// uv_pbr:  world_xz / pbr_tile_size_m, wraps via repeat_enable on the
//          PBR sampler — gives a tiling material at a fixed world scale.
vec3 sample_biome_albedo(vec2 world_xz) {
	float n = float(ring_texel_n);
	float extent_n = ring_extent_m * n / max(n - 1.0, 1.0);
	vec2 uv_ring = (world_xz - ring_origin_m) / extent_n + vec2(0.5 / n);
	vec2 uv_pbr = world_xz / pbr_tile_size_m;

	vec3 albedo = vec3(0.0);
	float total_w = 0.0;
	for (int i = 0; i < MAX_BIOMES_PER_RING; i++) {
		if (i >= active_biomes_n) {
			break;
		}
		int pbr_slot = biome_pbr_slot[i];
		if (pbr_slot < 0) {
			continue;
		}
		float w = texture(splat_array, vec3(uv_ring, float(i))).r;
		vec3 c = texture(pbr_ground_array, vec3(uv_pbr, float(pbr_slot))).rgb;
		albedo += w * c;
		total_w += w;
	}
	// If no biomes contributed (active_biomes_n == 0, or weights all
	// zero), fall back to base_albedo so we don't render pure black.
	if (total_w < 1e-4) {
		return base_albedo;
	}
	// Renormalize in case splat weights don't quite sum to 1.0.
	return albedo / max(total_w, 1e-4);
}

void fragment() {
	vec3 world_normal = compute_normal(v_world_pos.xz);
	NORMAL = (VIEW_MATRIX * vec4(world_normal, 0.0)).xyz;

	vec3 albedo = sample_biome_albedo(v_world_pos.xz);
	if (show_debug_color) {
		int safe_ring = clamp(ring_index, 0, 3);
		albedo = mix(albedo, RING_COLORS[safe_ring], debug_color_strength);
	}
	ALBEDO = albedo;
	ROUGHNESS = base_roughness;
	METALLIC = base_metallic;
}
```

- [ ] **Step 2: Parse-check**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "terrain_world_v3|error|parse|shader" | head -10
```

Expected: silent.

- [ ] **Step 3: Verify the scene still renders (will fall back to base_albedo since active_biomes_n=0)**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_clipmap_morph_on.tscn" 2>&1 | tail -5
```

Expected: capture writes; visual identical to before (base_albedo brown).

- [ ] **Step 4: Commit**

```bash
git -C "D:/assets" add "world 4/the world 4/shaders/terrain_world_v3.gdshader"
git -C "D:/assets" commit -m "stage4.1: 2. fragment-shader splat loop (defaults to base_albedo)"
```

---

## Task 3: ClipmapRing — `set_splat_uniforms` API

**Files:**
- Modify: `the world 4/scripts/ClipmapRing.gd`

- [ ] **Step 1: Add the API**

Find the existing `set_coarse_uniforms` method (added in morph zones). Below it, add:

```gdscript


# Stage 4.1+: splat + biome PBR uniforms. ClipmapWorld calls this
# whenever the ring's heightmap regenerates (the splat regenerates
# at the same cadence and uses the same world XZ origin).
#
# `splat_tex` is a Texture2DArray with one R8 layer per active biome.
# `biome_pbr_slot` is an Array[int] of length active_biomes_n; pads
# to MAX_BIOMES_PER_RING (= 16) with -1 so the shader can ignore
# unused slots. The pad happens here, not at the call site.
const MAX_BIOMES_PER_RING := 16


func set_splat_uniforms(splat_tex: Texture2DArray, active_biomes_n: int,
						biome_pbr_slot: Array[int]) -> void:
	var mat := _get_shader_material()
	if mat == null:
		return
	if splat_tex != null:
		mat.set_shader_parameter("splat_array", splat_tex)
	mat.set_shader_parameter("active_biomes_n", active_biomes_n)
	# Pad to fixed length so the shader's fixed-size array uniform
	# always receives valid data; -1 in unused slots is the sentinel.
	var padded: Array[int] = []
	for i in range(MAX_BIOMES_PER_RING):
		padded.append(biome_pbr_slot[i] if i < biome_pbr_slot.size() else -1)
	mat.set_shader_parameter("biome_pbr_slot", padded)
```

- [ ] **Step 2: Parse-check**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "ClipmapRing|error|parse" | head -10
```

Expected: silent (or just the script-registration line).

- [ ] **Step 3: Commit**

```bash
git -C "D:/assets" add "world 4/the world 4/scripts/ClipmapRing.gd"
git -C "D:/assets" commit -m "stage4.1: 3. ClipmapRing.set_splat_uniforms() API"
```

---

## Task 4: ClipmapWorld — splat float-buffer builder

**Files:**
- Modify: `the world 4/scripts/ClipmapWorld.gd`

This task adds a pure helper that produces a Stage-4.1-style splat buffer (single biome, full weight). No GPU work yet.

- [ ] **Step 1: Add the helper function**

Find the existing `_compute_heightmap_floats` in `ClipmapWorld.gd`. Directly below it, add:

```gdscript


# Stage 4.1: build a single-biome splat buffer. Always returns one
# R8 layer of width × height × 1 packed as PackedByteArray, where
# every byte = 255 (full weight for slot 0). Multi-biome generation
# lands in Stage 4.2 via the biome culler.
#
# Same n × step shape as the heightmap so the splat sampler aligns
# with the displacement sampler exactly.
func _compute_splat_bytes_single_biome(n: int) -> PackedByteArray:
	var bytes := PackedByteArray()
	bytes.resize(n * n)
	for i in range(n * n):
		bytes[i] = 255
	return bytes
```

- [ ] **Step 2: Parse-check**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "ClipmapWorld|error|parse" | head -10
```

Expected: silent.

- [ ] **Step 3: Commit**

```bash
git -C "D:/assets" add "world 4/the world 4/scripts/ClipmapWorld.gd"
git -C "D:/assets" commit -m "stage4.1: 4. ClipmapWorld._compute_splat_bytes_single_biome helper"
```

---

## Task 5: ClipmapWorld — load global PBR ground array

**Files:**
- Modify: `the world 4/scripts/ClipmapWorld.gd`

The PBR ground array is loaded once at `_ready` (or `_load_base_material`) and lives for the session. v1 supports 1 biome ("alpine") loaded from a known location, falling back to a debug color if missing.

- [ ] **Step 1: Add member state + loader**

Find the existing member declarations (the block with `_ring_count`, `_ring_grid_n`, etc). Add at the bottom of that block:

```gdscript

# Stage 4.1: per-biome PBR ground albedo array (global, all rings
# share it). Index = "PBR slot" — same name space the shader's
# biome_pbr_slot[] uniform refers to. Built once at _ready.
var _pbr_ground_array: Texture2DArray = null
var _biome_pbr_slot_by_name: Dictionary = {}  # String -> int
```

Now find `_load_base_material()`. Directly below it, add:

```gdscript


# Stage 4.1: load every biome's ground/albedo.png into a single
# global Texture2DArray. Records the layer index per biome in
# _biome_pbr_slot_by_name. v1 scans only for biomes named in the
# catalog. Missing files get a magenta debug color.
func _load_pbr_ground_array() -> void:
	if _catalog.is_empty():
		push_error("ClipmapWorld: _load_pbr_ground_array before catalog loaded")
		return
	var biome_dicts: Array = _catalog.get("biomes", [])
	if biome_dicts.is_empty():
		return
	# Load each biome's ground albedo as an Image. Use the first
	# successfully-loaded one to determine the array's edge size; all
	# subsequent ones must match (resize policy is "first wins" v1).
	var images: Array = []
	var edge: int = 0
	for b in biome_dicts:
		var biome_name: String = b["name"]
		var kit_dir: String = b.get("kit_dir", "")
		# Try the catalog-specified kit_dir first, then a known fallback
		# location used by Axis 6.
		var candidates: Array[String] = [
			"res://" + kit_dir + "/ground/albedo.png",
			"res://worlds/scale_demo/biomes/" + biome_name + "/ground/albedo.png",
		]
		var img: Image = null
		for path in candidates:
			if ResourceLoader.exists(path):
				var tex := load(path)
				if tex is Texture2D:
					img = tex.get_image()
					if img != null:
						break
		if img == null:
			push_warning("ClipmapWorld: no ground/albedo.png for biome %s, using debug magenta" % biome_name)
			img = Image.create(256, 256, false, Image.FORMAT_RGBA8)
			img.fill(Color(1.0, 0.0, 1.0, 1.0))
		if edge == 0:
			edge = img.get_width()
		elif img.get_width() != edge or img.get_height() != edge:
			# Resize to match first-loaded for v1 simplicity.
			img.resize(edge, edge, Image.INTERPOLATE_LANCZOS)
		# Texture2DArray requires every layer the same format.
		img.convert(Image.FORMAT_RGBA8)
		_biome_pbr_slot_by_name[biome_name] = images.size()
		images.append(img)
	if images.is_empty():
		push_error("ClipmapWorld: no biome images loaded")
		return
	_pbr_ground_array = Texture2DArray.new()
	var err: int = _pbr_ground_array.create_from_images(images)
	if err != OK:
		push_error("ClipmapWorld: Texture2DArray.create_from_images failed: %d" % err)
		_pbr_ground_array = null
		return
	print("[ClipmapWorld] loaded %d biome PBR ground textures (%dx%d)" % [
		images.size(), edge, edge])
```

- [ ] **Step 2: Call the loader in `_ready`**

Find:

```gdscript
func _ready() -> void:
	_resolve_config()
	_load_catalog_and_composer()
	_load_base_material()
	_spawn_rings()
```

Change to:

```gdscript
func _ready() -> void:
	_resolve_config()
	_load_catalog_and_composer()
	_load_base_material()
	_load_pbr_ground_array()
	_spawn_rings()
```

- [ ] **Step 3: Parse-check + verify the log line appears**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | tail -3
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_clipmap_morph_on.tscn" 2>&1 | tail -8
```

Expected: capture log contains `[ClipmapWorld] loaded N biome PBR ground textures (XxX)`. N should be 2 (alpine + desert in current catalog). If the textures don't exist on disk, expect warnings about magenta fallback — that's fine for now.

- [ ] **Step 4: Commit**

```bash
git -C "D:/assets" add "world 4/the world 4/scripts/ClipmapWorld.gd"
git -C "D:/assets" commit -m "stage4.1: 5. ClipmapWorld loads global PBR ground array"
```

---

## Task 6: ClipmapWorld — build per-ring splat Texture2DArray + bind uniforms

**Files:**
- Modify: `the world 4/scripts/ClipmapWorld.gd`

This task wires Tasks 4 and 5 into `_finalize_ring_upload`. After the existing heightmap upload, build a 1-layer splat array (full weight) and push it + `active_biomes_n = 1` + `biome_pbr_slot = [<alpine's pbr slot>]` to the ring.

- [ ] **Step 1: Edit `_finalize_ring_upload`**

Find the existing function:

```gdscript
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
	# Morph plumbing: this ring's freshly-uploaded texture is the
	# COARSE input for ring (ring_index - 1). Push it. (If ring_index
	# is 0, no inner ring exists; skip.)
	if r.ring_index > 0:
		var inner: ClipmapRing = _rings[r.ring_index - 1]
		var inner_band_m: float = _morph_band_m_per_ring[r.ring_index - 1]
		inner.set_coarse_uniforms(
			tex, origin, extent, n, inner_band_m, not debug_disable_morph)
```

Add this code at the very end of the function (after the morph plumbing block):

```gdscript
	# Stage 4.1: build a single-layer splat Texture2DArray for this
	# ring (every texel = 1.0 weight to slot 0) and bind it + a
	# 1-element biome_pbr_slot pointing at "alpine" (or the first
	# loaded biome if alpine isn't present).
	if _pbr_ground_array != null and not _biome_pbr_slot_by_name.is_empty():
		var splat_bytes: PackedByteArray = _compute_splat_bytes_single_biome(n)
		var splat_img := Image.create_from_data(n, n, false, Image.FORMAT_R8, splat_bytes)
		var splat_array := Texture2DArray.new()
		var err: int = splat_array.create_from_images([splat_img])
		if err == OK:
			var first_biome: String = _first_loaded_biome_name()
			var first_pbr_slot: int = int(_biome_pbr_slot_by_name[first_biome])
			# Also bind the GLOBAL PBR array to the per-ring material's
			# uniform. (Setting the same texture on every per-ring
			# material is fine; they share GPU memory.)
			var mat: ShaderMaterial = _per_ring_shader_material(r)
			if mat != null:
				mat.set_shader_parameter("pbr_ground_array", _pbr_ground_array)
			r.set_splat_uniforms(splat_array, 1, [first_pbr_slot])
```

- [ ] **Step 2: Add `_first_loaded_biome_name` + `_per_ring_shader_material` helpers**

Find the end of `_finalize_ring_upload` (after the new Stage 4.1 block you just added). Below the function, add:

```gdscript


# Returns the first biome by catalog order that successfully loaded
# into the PBR array. Falls back to the catalog's first biome name
# if for some reason none loaded (the magenta-fallback path still
# registers a slot, so this rarely fails).
func _first_loaded_biome_name() -> String:
	var biomes_arr: Array = _catalog.get("biomes", [])
	for b in biomes_arr:
		var n: String = b["name"]
		if _biome_pbr_slot_by_name.has(n):
			return n
	# Fallback — shouldn't reach here in practice.
	return biomes_arr[0]["name"] if not biomes_arr.is_empty() else ""


# The ring's MeshInstance3D's material_override is the per-ring
# duplicate we built in _spawn_rings. ClipmapRing carries it
# internally; expose access via the same _get_shader_material
# pattern we use elsewhere.
func _per_ring_shader_material(r: ClipmapRing) -> ShaderMaterial:
	for child in r.get_children():
		if child is MeshInstance3D:
			var mi: MeshInstance3D = child
			if mi.material_override is ShaderMaterial:
				return mi.material_override
	return null
```

- [ ] **Step 3: Parse-check**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "ClipmapWorld|error|parse" | head -10
```

Expected: silent.

- [ ] **Step 4: Capture and inspect**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_clipmap_morph_on.tscn" 2>&1 | tail -8
```

Expected:
- log contains `[ClipmapWorld] loaded 2 biome PBR ground textures (XxX)`
- capture writes to `axis1_clipmap_morph_on_2026_05_12.png`
- the rendered image shows alpine's ground albedo tiling across the terrain (not the flat brown base_albedo anymore). If the texture loaded a magenta fallback, the world will be magenta — that's the path with no source image; expected if no alpine asset exists yet.

Read the capture file via the `Read` tool to verify visually.

- [ ] **Step 5: Commit**

```bash
git -C "D:/assets" add "world 4/the world 4/scripts/ClipmapWorld.gd" "world 4/the world 4/captures/axis1_clipmap_morph_on_2026_05_12.png"
git -C "D:/assets" commit -m "stage4.1: 6. ClipmapWorld builds per-ring splat + binds global PBR array"
```

---

## Task 7: material .tres — add new shader-parameter defaults

**Files:**
- Modify: `the world 4/worlds/scale_v2/material_world_v3.tres`

- [ ] **Step 1: Rewrite the material via Python helper**

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
shader_parameter/active_biomes_n = 0
shader_parameter/pbr_tile_size_m = 4.0
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

Expected output: `wrote material_world_v3.tres`.

(Note: we don't pre-populate `splat_array` / `pbr_ground_array` / `biome_pbr_slot` in the `.tres` — they get set at runtime by ClipmapWorld. `active_biomes_n=0` is the safe default so the shader's fallback returns `base_albedo` until uniforms get bound.)

- [ ] **Step 2: Verify the material still loads**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "material_world_v3|error|parse" | head -5
```

Expected: silent (no parse errors).

- [ ] **Step 3: Commit**

```bash
git -C "D:/assets" add "world 4/the world 4/worlds/scale_v2/material_world_v3.tres"
git -C "D:/assets" commit -m "stage4.1: 7. material defaults for splat/PBR uniforms"
```

---

## Task 8: A/B capture + editor verification

**Files:**
- Create: `the world 4/captures/axis1_clipmap_stage4_1_walk_2026_05_12.png`
- Create: `the world 4/captures/axis1_clipmap_stage4_1_topdown_2026_05_12.png`

- [ ] **Step 1: Walk capture**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_clipmap_morph_on.tscn" 2>&1 | tail -5
```

Then rename the capture to preserve a Stage-4.1 record:

```bash
"C:/Program Files/Python312/python.exe" -c "
import shutil
shutil.copy(
    r'D:/assets/world 4/the world 4/captures/axis1_clipmap_morph_on_2026_05_12.png',
    r'D:/assets/world 4/the world 4/captures/axis1_clipmap_stage4_1_walk_2026_05_12.png',
)
print('saved walk capture')
"
```

- [ ] **Step 2: Topdown capture**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_clipmap_morph_on_topdown.tscn" 2>&1 | tail -5
```

Then rename:

```bash
"C:/Program Files/Python312/python.exe" -c "
import shutil
shutil.copy(
    r'D:/assets/world 4/the world 4/captures/axis1_clipmap_morph_on_topdown_2026_05_12.png',
    r'D:/assets/world 4/the world 4/captures/axis1_clipmap_stage4_1_topdown_2026_05_12.png',
)
print('saved topdown capture')
"
```

- [ ] **Step 3: Read both captures**

Use the `Read` tool on:
- `D:/assets/world 4/the world 4/captures/axis1_clipmap_stage4_1_walk_2026_05_12.png`
- `D:/assets/world 4/the world 4/captures/axis1_clipmap_stage4_1_topdown_2026_05_12.png`

Expected outcomes (in order of decreasing happiness):
1. **Best case**: terrain visibly textured with alpine's ground albedo (visible rocky/icy detail at small scale, tiled across the world).
2. **OK case**: terrain visibly textured with magenta (debug fallback) — means the loader path works but the alpine source PNG isn't where the loader expected. Need to either generate the texture (Stage 4.5) or fix the path.
3. **Fail case**: terrain still flat brown — splat or PBR binding didn't take. Investigate using the diagnostic prints.

- [ ] **Step 4: Print the editor verification command for the user**

Per `workflows/verifying-visual-change.md`: do NOT background-launch the editor. Print this for the user:

> Run this in a terminal and walk around for 30 seconds to verify the per-biome shading is working:
>
> `"C:/Godot/Godot_v4.5-stable_win64.exe" --path "D:/assets/world 4/the world 4"`
>
> Open `scenes/clipmap_debug.tscn`, F6 to play, WASD around. Watch for:
> 1. **Terrain textured** (not flat brown) — the surface should show the alpine ground albedo tiled across the world.
> 2. **No new artifacts** at ring boundaries (the splat is single-biome full-weight on every ring, so no boundary mismatch is possible here).
> 3. **No crash on F6 stop** — the Stage 3.6 fix should still hold.
>
> Tell me what you see (including: is the texture alpine or magenta).

- [ ] **Step 5: Commit captures**

After the user reports back:

```bash
git -C "D:/assets" add "world 4/the world 4/captures/axis1_clipmap_stage4_1_walk_2026_05_12.png" "world 4/the world 4/captures/axis1_clipmap_stage4_1_topdown_2026_05_12.png"
git -C "D:/assets" commit -m "stage4.1: 8. A/B captures for single-biome shading proof"
```

---

## Task 9: Docs — STATE + (light) build-note

**Files:**
- Modify: `the world 4/docs/STATE.md`
- Create: `the world 4/docs/build-notes/STAGE4_1_BUILD_NOTES_2026_05_12.md`

- [ ] **Step 1: Update STATE.md**

Find the "Active work" section. Add a new line beneath the Stage 3.6 entry:

```markdown
- ✅ **Stage 4.1 — Single-biome rendering proof**: complete pending
  editor verification. Per-ring splat `sampler2DArray` (one layer,
  full weight) + global PBR ground `sampler2DArray` (one layer per
  catalog biome). Shader fragment loop samples splat × PBR; falls
  back to `base_albedo` when uniforms aren't bound or weights are
  zero. Proves the texture-array plumbing end-to-end. Stage 4.2
  (biome culler + multi-biome blending) is next. Build-note:
  `build-notes/STAGE4_1_BUILD_NOTES_2026_05_12.md`.
```

Update the test count line to reflect no new tests this stage (still 56). Then update the "Code inventory" Clipmap renderer line to note splat support:

Find:

```markdown
| Clipmap renderer | `scripts/ClipmapWorld.gd`, `scripts/ClipmapRing.gd`, `shaders/clipmap_debug.gdshader`, `shaders/terrain_world_v3.gdshader` | Stages 1+2+3 shipped. Donut meshes + skirts, camera-snap, async displacement via WorkerThreadPool, lit PBR shader with per-fragment normals, HeightMapShape3D collision on inner rings. |
```

Replace with:

```markdown
| Clipmap renderer | `scripts/ClipmapWorld.gd`, `scripts/ClipmapRing.gd`, `shaders/clipmap_debug.gdshader`, `shaders/terrain_world_v3.gdshader` | Stages 1+2+3+3.6+4.1 shipped. Donut meshes + skirts, camera-snap, async heightmap + splat via WorkerThreadPool, lit PBR shader with per-fragment normals + morph zones, single-biome rendering via per-ring splat + global PBR Texture2DArrays, HeightMapShape3D collision on inner rings. |
```

- [ ] **Step 2: Create the build-note**

Use the Write tool to create `the world 4/docs/build-notes/STAGE4_1_BUILD_NOTES_2026_05_12.md`:

```markdown
# Stage 4.1 — Single-biome rendering proof

> Proves the per-ring splat + global PBR ground texture-array
> plumbing works end-to-end. No biome variation yet (slot 0 only,
> full weight); biome culler + multi-biome blending lands in Stage
> 4.2. Shipped 2026-05-12 on `main`.

## What shipped

| Task | Component | Commit |
|---|---|---|
| 1 | Shader: splat + PBR uniforms | (see git log) |
| 2 | Shader: fragment splat loop with base_albedo fallback | (see git log) |
| 3 | ClipmapRing.set_splat_uniforms API | (see git log) |
| 4 | ClipmapWorld._compute_splat_bytes_single_biome helper | (see git log) |
| 5 | ClipmapWorld._load_pbr_ground_array (global Texture2DArray) | (see git log) |
| 6 | ClipmapWorld builds per-ring splat + binds PBR array | (see git log) |
| 7 | material_world_v3.tres adds new defaults | (see git log) |
| 8 | A/B captures + editor verification | (see git log) |

**Test count:** 56 → 56 (no new pytest; visual sign-off only).

## Architecture summary

```
ClipmapWorld._ready:
  _load_catalog_and_composer → catalog has N biomes
  _load_pbr_ground_array → loads each biome's
                            materials/biome_<name>/ground/albedo.png
                            into a single global Texture2DArray.
                            Missing → magenta fallback.
                            Records biome → PBR slot in
                            _biome_pbr_slot_by_name.

ClipmapWorld._finalize_ring_upload (per ring per regen):
  1. heightmap upload (Stage 3)
  2. morph plumbing (Stage 3.6)
  3. NEW: splat builder builds 1-layer R8 Texture2DArray (all 255)
  4. NEW: ring.set_splat_uniforms(splat_array, 1, [first_biome_slot])
  5. NEW: per-ring material gets the GLOBAL pbr_ground_array bound

Shader fragment:
  loop i in 0..active_biomes_n:
      w = splat_array[i] at uv_ring
      c = pbr_ground_array[biome_pbr_slot[i]] at uv_pbr (tiling)
      albedo += w * c
  fall back to base_albedo if total_w ≈ 0
```

## Plan deviations

None. Plan followed step-by-step.

## What's still missing (Stage 4.2+)

- **Biome culler**: every ring renders as if biome 0 dominates
  everywhere. Stage 4.2 samples KernelComposer.sample_biome_weights
  to build real per-biome splat layers.
- **Splat morph zones**: Stage 4.3.
- **Hysteresis**: Stage 4.4.
- **PBR texture generation**: Stage 4.5 runs `generate_biome_kits.py`
  for the 2 scale_v2 biomes. Without it, every biome is the same
  texture (or magenta).
- **mid + rock slot blending**: deferred past Stage 4.5.

## What's next

**Stage 4.2** — biome culler + multi-biome shader loop. The culler
runs in the worker (alongside heightmap regen), produces a per-ring
biome list, builds an N-layer splat. The shader loop already
iterates `active_biomes_n` so the changes are mostly CPU-side.
```

- [ ] **Step 3: Commit**

```bash
git -C "D:/assets" add "world 4/docs/STATE.md" "world 4/docs/build-notes/STAGE4_1_BUILD_NOTES_2026_05_12.md"
git -C "D:/assets" commit -m "stage4.1: 9. STATE refresh + build-note"
```

---

## Self-review notes

**Spec coverage** (against `superpowers/specs/2026-05-12-clipmap-splat-biomes-design.md`):
- ✅ "Stage 4.1 (single biome rendering)" — every task targets this scope.
- ✅ "Per-ring splat `sampler2DArray`" → Task 4 + Task 6.
- ✅ "Global PBR ground `Texture2DArray`" → Task 5.
- ✅ "Shader: fragment loop sampling splat × PBR" → Task 2.
- ✅ "Falls back to base_albedo when uniforms not bound" → Task 2 step 1 (`total_w < 1e-4`).
- ✅ "Missing biome → magenta fallback + warning" → Task 5 step 1.
- ✅ "biome_pbr_slot two-level indirection (splat slot → PBR slot)" → Task 3 step 1 + Task 6.
- Deferred to Stage 4.2: biome culler.
- Deferred to Stage 4.3: splat morph zone.
- Deferred to Stage 4.4: hysteresis.
- Deferred to Stage 4.5: PBR texture generation. (Captures may show magenta until 4.5 ships.)

**Placeholder scan:** none. Every step has exact paths, exact commands, exact expected outputs.

**Type consistency:**
- `set_splat_uniforms(splat_tex: Texture2DArray, active_biomes_n: int, biome_pbr_slot: Array[int])` — same signature in Task 3 (definition) and Task 6 (call site).
- `MAX_BIOMES_PER_RING = 16` is the shader constant (Task 1) and the GDScript constant (Task 3 step 1, in ClipmapRing). They must stay in sync; future Stage 4.2 work moves this to the quality-tier knob `max_biomes_per_ring` (spec already calls this out — Stage 4.2 will sync the names).
- `_biome_pbr_slot_by_name: Dictionary` (String → int) defined in Task 5, consumed in Task 6 via `int(_biome_pbr_slot_by_name[first_biome])`.

**Caveats called out in the plan body:**
- The capture in Task 8 may show magenta if alpine's `ground/albedo.png` doesn't exist on disk yet — that's expected, indicates we need to either fall back to scale_demo's existing biome assets (the loader tries) or wait for Stage 4.5's generation.
- The PBR `Texture2DArray` is set on every per-ring material instance, not as a global uniform. Godot 4.5 doesn't expose "set parameter on all materials sharing this shader" so the loop in Task 6 is fine but slightly redundant; future work could expose a singleton material reference.
