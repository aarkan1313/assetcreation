// v2 biome terrain shader. Direct port of the v1 'topdown' shader's working
// pieces (cull_back + UV varying + ocean fallback + per-biome tile_meters)
// but stripped to albedo-only since v2 milestone 1 doesn't yet have
// normal/roughness PBR maps from FLUX. v1 source:
// godot_pack/shaders/biome_terrain.gdshader
//
// Bug history this fixes:
// - Black holes when splat samples to (0,0,0,0): the ocean_blend fallback now
//   blends to a fallback colour instead of multiplying albedo by zero.
// - Black holes from cull_disabled + back-facing slivers: cull_back is fine;
//   the displacement doesn't actually flip enough triangles to need disabled.
// - 'far away looks bad': fragment uses the v_uv varying from vertex stage,
//   not the built-in UV (which has known precision issues at km scale).

shader_type spatial;
render_mode cull_back, depth_draw_opaque;

uniform sampler2D heightmap : hint_default_white;
uniform sampler2D splat     : hint_default_black;

uniform sampler2D albedo_0 : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D albedo_1 : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D albedo_2 : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D albedo_3 : source_color, filter_linear_mipmap, repeat_enable;

uniform float terrain_size_m   : hint_range(16.0, 65536.0) = 35886.0;
uniform float terrain_size_z_m : hint_range(16.0, 65536.0) = 35886.0;
uniform float terrain_height_m : hint_range(1.0, 4096.0)   = 2055.0;

// per-biome tiling in metres. Vector4(R,G,B,A) matches the splat channel order.
uniform vec4 tile_meters = vec4(3.0, 3.0, 3.0, 3.0);

uniform float roughness_value : hint_range(0.0, 1.0) = 0.9;

// fallback colour for fragments where splat weights are all near-zero (e.g.
// floating-point UV drift outside [0,1] hitting hint_default_black). Without
// this, those fragments would render albedo=0=black.
uniform vec3  fallback_color : source_color = vec3(0.45, 0.40, 0.30);

// Debug visualisation. Set in material .tres to override ALBEDO with a
// pipeline-state probe. 0 = normal render. See fragment() for modes.
uniform int debug_mode : hint_range(0, 4) = 0;

varying vec2 v_uv;
varying vec3 v_world;

void vertex() {
	v_uv = UV;
	float h = texture(heightmap, UV).r;
	VERTEX.y += h * terrain_height_m;

	// Recompute the surface normal from the heightmap gradient so lighting
	// reads the displaced shape, not the original flat plane.
	float texel = 1.0 / float(textureSize(heightmap, 0).x);
	float hL = texture(heightmap, UV + vec2(-texel, 0.0)).r;
	float hR = texture(heightmap, UV + vec2( texel, 0.0)).r;
	float hD = texture(heightmap, UV + vec2(0.0, -texel)).r;
	float hU = texture(heightmap, UV + vec2(0.0,  texel)).r;
	float step_x = terrain_size_m   * texel;
	float step_z = terrain_size_z_m * texel;
	NORMAL = normalize(vec3(
		(hL - hR) * terrain_height_m,
		2.0 * (step_x + step_z) * 0.5,
		(hD - hU) * terrain_height_m
	));

	v_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	// Read raw splat weights. Detect the 'no biome painted' case before
	// normalising — that's the signal to fall back to fallback_color.
	vec4 w_raw = texture(splat, v_uv);
	float wsum_raw = w_raw.r + w_raw.g + w_raw.b + w_raw.a;
	float fallback_blend = 1.0 - clamp(wsum_raw * 8.0, 0.0, 1.0);
	vec4 w = w_raw / max(wsum_raw, 1e-4);

	// Per-biome tiled albedo lookup using world XZ for true real-world tiling.
	vec3 a0 = texture(albedo_0, v_world.xz / max(tile_meters.r, 0.01)).rgb;
	vec3 a1 = texture(albedo_1, v_world.xz / max(tile_meters.g, 0.01)).rgb;
	vec3 a2 = texture(albedo_2, v_world.xz / max(tile_meters.b, 0.01)).rgb;
	vec3 a3 = texture(albedo_3, v_world.xz / max(tile_meters.a, 0.01)).rgb;

	vec3 alb_biome = a0 * w.r + a1 * w.g + a2 * w.b + a3 * w.a;

	// Blend toward fallback colour where no biome is painted.
	vec3 final_color = mix(alb_biome, fallback_color, fallback_blend);

	// DEBUG MODE — set debug_mode > 0 to visualise pipeline state directly.
	//   1 = raw splat as RGB (R=desert, G=salt, B=rocky; A ignored)
	//   2 = wsum_raw as grayscale (white = full coverage, black = empty)
	//   3 = first FLUX albedo unblended (a0)
	//   4 = world XZ as RGB (R=normalized X, G=0, B=normalized Z)
	if (debug_mode == 1) {
		ALBEDO = w_raw.rgb;
	} else if (debug_mode == 2) {
		ALBEDO = vec3(wsum_raw);
	} else if (debug_mode == 3) {
		// Sample albedo_0 with UV directly (0..1 across mesh) so we see
		// exactly ONE tile of the FLUX texture stretched over the terrain.
		// If THIS shows the FLUX detail, the bug is in tile_uv math.
		// If THIS is also flat, the bug is in texture loading.
		ALBEDO = texture(albedo_0, v_uv).rgb;
	} else if (debug_mode == 4) {
		ALBEDO = vec3(
			fract(v_world.x / 1000.0),
			0.0,
			fract(v_world.z / 1000.0)
		);
	} else {
		ALBEDO = final_color;
	}
	ROUGHNESS = roughness_value;
	METALLIC  = 0.0;
}
