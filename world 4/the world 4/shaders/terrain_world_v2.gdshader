// W4 unified terrain shader (Axis 6 transitions).
//
// Replaces terrain_scale_v1.gdshader. Same unshaded manual-lighting model
// (PITFALLS #3 mitigation: lit PBR pipeline produces black quads at scale,
// so we run unshaded and do our own lambertian + ambient math).
//
// Per-tile data path:
//   - splat (sampler2D, RGBA) defines up to 4 contributing biomes per fragment.
//   - splat_ground/mid/rock_indices (ivec4) pack (tier, layer) per slot per
//     channel. Per-slot addressing lets a biome span tiers (e.g. forest:
//     ground+rock hero, mid standard).
//   - Each int packs tier in bit 30 (0=standard, 1=hero) and layer in bits
//     0..29. A value of -1 means "channel empty, skip."
//
// Per fragment:
//   1. Sample splat at tile-local UV -> 4 weights, normalized to sum=1.
//   2. For each non-zero weight, read the channel's ground/mid/rock from
//      the appropriate tier array, do the within-biome slope blend, and
//      add to the weighted accumulator.
//   3. Apply lambertian + ambient lighting, luma floor, final clamp.

shader_type spatial;
render_mode unshaded, cull_back, depth_draw_opaque;

// Two-tier texture arrays
uniform sampler2DArray standard_albedo : source_color;
uniform sampler2DArray standard_normal : hint_normal;
uniform sampler2DArray standard_rough;
uniform sampler2DArray standard_ao : hint_default_white;
uniform sampler2DArray hero_albedo : source_color;
uniform sampler2DArray hero_normal : hint_normal;
uniform sampler2DArray hero_rough;
uniform sampler2DArray hero_ao : hint_default_white;

// Per-tile uniforms (set by ScaleWorld at material instantiation).
uniform sampler2D splat;
uniform ivec4 splat_ground_indices = ivec4(-1, -1, -1, -1);
uniform ivec4 splat_mid_indices    = ivec4(-1, -1, -1, -1);
uniform ivec4 splat_rock_indices   = ivec4(-1, -1, -1, -1);
uniform vec2  tile_origin_m = vec2(0.0, 0.0);
uniform float tile_size_m   = 256.0;

// Slope thresholds (within-biome ground/mid/rock blend, same as v1)
uniform float slope_ground_max : hint_range(0.0, 1.0) = 0.92;
uniform float slope_rock_max   : hint_range(0.0, 1.0) = 0.55;

uniform float world_uv_scale = 0.04;

// Albedo safety (PITFALLS #1)
uniform float albedo_luma_floor : hint_range(0.0, 0.4) = 0.08;
uniform float ao_floor          : hint_range(0.0, 1.0) = 0.72;

// In-shader sun (same as v1)
uniform vec3 sun_dir = vec3(0.30, 0.85, 0.43);
uniform vec3 sun_color : source_color = vec3(1.0, 0.96, 0.88);
uniform float sun_intensity : hint_range(0.0, 3.0) = 1.0;
uniform float lambert_floor : hint_range(0.0, 0.5) = 0.35;

uniform vec3 sky_tint    : source_color = vec3(0.78, 0.84, 0.92);
uniform vec3 ground_tint : source_color = vec3(0.58, 0.60, 0.55);
uniform float ambient_strength : hint_range(0.0, 2.0) = 0.45;

varying vec3 v_world_pos;
varying vec3 v_world_normal;

void vertex() {
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

vec3 luma_floor_v(vec3 color) {
	float lum = dot(color, vec3(0.2126, 0.7152, 0.0722));
	if (lum < albedo_luma_floor) {
		color += vec3(albedo_luma_floor - lum);
	}
	return clamp(color, vec3(0.0), vec3(1.0));
}

// Sample a single (tier, layer) tuple. Returns the albedo + AO for that
// slot only. uv is the world-UV (already scaled).
void sample_slot(int packed_idx, vec2 uv, out vec3 albedo_out, out float ao_out) {
	if (packed_idx < 0) {
		albedo_out = vec3(0.0);
		ao_out = 1.0;
		return;
	}
	int tier = (packed_idx >> 30) & 1;
	int layer = packed_idx & 0x3FFFFFFF;
	if (tier == 1) {
		albedo_out = luma_floor_v(texture(hero_albedo, vec3(uv, float(layer))).rgb);
		ao_out = texture(hero_ao, vec3(uv, float(layer))).r;
	} else {
		albedo_out = luma_floor_v(texture(standard_albedo, vec3(uv, float(layer))).rgb);
		ao_out = texture(standard_ao, vec3(uv, float(layer))).r;
	}
}

// Read one biome's contribution: sample its ground/mid/rock from
// (potentially different) tier arrays and blend by world-normal slope.
void sample_biome_channel(int ch, vec2 uv, float up,
                          out vec3 albedo_out, out float ao_out) {
	int g_idx = splat_ground_indices[ch];
	int m_idx = splat_mid_indices[ch];
	int r_idx = splat_rock_indices[ch];
	vec3 ga, ma, ra;
	float go, mo, ro;
	sample_slot(g_idx, uv, ga, go);
	sample_slot(m_idx, uv, ma, mo);
	sample_slot(r_idx, uv, ra, ro);
	float ground_w = smoothstep(slope_ground_max - 0.15, slope_ground_max, up);
	float rock_w   = 1.0 - smoothstep(slope_rock_max, slope_rock_max + 0.15, up);
	float mid_w    = max(0.0, 1.0 - ground_w - rock_w);
	float total    = max(ground_w + mid_w + rock_w, 1e-4);
	ground_w /= total; mid_w /= total; rock_w /= total;
	albedo_out = ga * ground_w + ma * mid_w + ra * rock_w;
	ao_out     = go * ground_w + mo * mid_w + ro * rock_w;
}

void fragment() {
	vec2 uv = v_world_pos.xz * world_uv_scale;
	vec3 wn = normalize(v_world_normal);
	float up = clamp(wn.y, 0.0, 1.0);

	vec2 splat_uv = (v_world_pos.xz - tile_origin_m) / tile_size_m;
	vec4 w = texture(splat, splat_uv);
	float wsum = max(w.r + w.g + w.b + w.a, 1e-4);
	w /= wsum;

	vec3 albedo = vec3(0.0);
	float ao = 0.0;
	for (int i = 0; i < 4; i++) {
		float wi = w[i];
		if (wi < 1e-3) {
			continue;
		}
		if (splat_ground_indices[i] < 0) {
			continue;
		}
		vec3 a_i;
		float ao_i;
		sample_biome_channel(i, uv, up, a_i, ao_i);
		albedo += a_i * wi;
		ao     += ao_i * wi;
	}
	ao = clamp(ao, ao_floor, 1.0);

	vec3 sun_n = normalize(sun_dir);
	float ndl = dot(wn, sun_n);
	float lambert = max(ndl, lambert_floor);
	vec3 direct = sun_color * lambert * sun_intensity;
	vec3 ambient_color = mix(ground_tint, sky_tint, up);
	vec3 ambient = ambient_color * ambient_strength;

	vec3 lit = albedo * ao * (direct + ambient);
	lit = luma_floor_v(lit);
	ALBEDO = lit;
}
