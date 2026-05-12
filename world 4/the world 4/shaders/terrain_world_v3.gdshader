// W4 clipmap terrain shader (v3 — Axis 1 Path 2, Stage 3+).
//
// Vertex shader displaces from a per-ring `displacement` heightmap
// texture sampled at the vertex's world XZ. The shader is lit PBR
// from day one (project ethos: quality > performance > anything);
// Stage 4 will layer in biome splat + per-biome PBR Texture2DArrays.
//
// Per-ring uniforms (set by ClipmapWorld at material instantiation):
//   displacement:   per-ring heightmap (FORMAT_RF or FORMAT_RH; height in m)
//   ring_origin_m:  world XZ of the ring's lower-left corner (after camera-snap)
//   ring_extent_m:  ring side length in meters = (grid_n - 1) * grid_step
//   ring_texel_n:   resolution of the displacement texture (= grid_n)
//   ring_index:     0..N-1 (for debug coloring only)
//   show_debug_color: 1 = ring-color overlay on ALBEDO, 0 = plain diffuse
//   debug_color_strength: blend factor for the debug overlay (0..1)
//
// Key correctness details (each one bit me at least once):
//
// 1. VERTEX.y += h, NOT VERTEX.y = h.
//    Skirt verts arrive with VERTEX.y = -skirt_depth_m. Using `=`
//    clobbers the skirt depth and collapses skirts onto the surface.
//    See PITFALLS / Stage 2 fix.
//
// 2. Half-texel UV offset.
//    With filter_linear, UV (0,0) samples the CENTER of texel (0,0),
//    not its corner. Vertex (i,j) at world position
//    (origin.x + i*step, origin.z + j*step) needs UV
//    ((i + 0.5) / n, (j + 0.5) / n) = (world_xz - origin) / extent_n
//    where extent_n = ring_extent_m * n / (n-1).
//    Skipping this offset means rings disagree at shared boundaries
//    by half a texel.
//
// 3. NaN guard.
//    isnan(h) || isinf(h) → fall back to 0. Cheap insurance against
//    Image.create_from_data hiccups (FORMAT_RF padded incorrectly,
//    R16F overflow, etc).

shader_type spatial;
render_mode cull_back, depth_draw_opaque, diffuse_burley, specular_schlick_ggx;

uniform sampler2D displacement : filter_linear, repeat_disable, hint_default_black;
uniform vec2 ring_origin_m = vec2(0.0, 0.0);
uniform float ring_extent_m = 512.0;
uniform int ring_texel_n = 128;
uniform int ring_index = 0;

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

uniform bool show_debug_color = false;
uniform float debug_color_strength : hint_range(0.0, 1.0) = 0.5;

// Surface defaults. Stage 4 will replace these with per-biome PBR
// sampling driven by the splat.
uniform vec3 base_albedo : source_color = vec3(0.55, 0.52, 0.48);
uniform float base_roughness : hint_range(0.0, 1.0) = 0.85;
uniform float base_metallic : hint_range(0.0, 1.0) = 0.0;

const vec3 RING_COLORS[4] = vec3[4](
	vec3(0.9, 0.4, 0.3),
	vec3(0.4, 0.9, 0.3),
	vec3(0.3, 0.5, 0.9),
	vec3(0.9, 0.8, 0.3)
);

varying vec3 v_world_pos;


// Sample heightmap with NaN guard + half-texel-correct UV.
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


// Finite-difference normal from heightmap. Step is one ring texel in
// world meters; smaller step = more aliasing on flat ground, bigger
// step = under-resolved on steep slopes. One texel is the standard
// choice for clipmap displacement.
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
