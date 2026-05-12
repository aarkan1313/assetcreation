// W4 unified terrain shader (Axis 6 transitions, v2).
//
// Replaces the per-tile splat path with a WORLD-SPANNING SPLAT ARRAY:
// one sampler2DArray with N layers, one per biome. Sampled at world XZ
// (no per-tile UVs), so adjacent tiles share splat pixels at their
// shared boundary by construction — no hard line possible at tile edges.
//
// Per fragment:
//   1. Sample each active biome's splat layer at the world UV.
//   2. For each biome with weight > eps:
//        - Look up that biome's (tier, layer) per-slot via the global
//          arrays (biome_ground/mid/rock_packed[i]).
//        - Sample the right Texture2DArray (standard or hero) for
//          albedo + AO at the layer.
//        - Apply within-biome slope blend (ground/mid/rock).
//   3. Weighted-sum the contributions.
//   4. Apply lighting (lambertian + ambient) — same unshaded model as
//      terrain_scale_v1 (PITFALLS #3).
//
// Per-slot tier/layer packing (`biome_*_packed[i]`):
//   tier in bit 30 (0=standard, 1=hero), raw array layer in bits 0..29.
//   -1 means slot empty (skip).
//
// Splat array: each layer is single-channel R8, world weights for one
// biome. ScaleWorld constructs this Texture2DArray at scene init from
// `worlds/<bundle>/world_splat/layer_<biome>.png` × N + manifest.json.

shader_type spatial;
render_mode unshaded, cull_back, depth_draw_opaque;

// Per-biome PBR arrays (2 resolution tiers × 4 maps).
uniform sampler2DArray standard_albedo : source_color;
uniform sampler2DArray standard_normal : hint_normal;
uniform sampler2DArray standard_rough;
uniform sampler2DArray standard_ao : hint_default_white;
uniform sampler2DArray hero_albedo : source_color;
uniform sampler2DArray hero_normal : hint_normal;
uniform sampler2DArray hero_rough;
uniform sampler2DArray hero_ao : hint_default_white;

// World splat: one layer per biome. ScaleWorld builds + binds at init.
// filter_linear so the splat interpolates smoothly between texels;
// repeat_disable so sampling outside [0..1] doesn't wrap.
uniform sampler2DArray world_splat : filter_linear, repeat_disable;

// Number of active biomes (loop bound). Set by ScaleWorld at init.
uniform int num_biomes = 0;

// Per-biome slot indirection. Fixed-size arrays sized for the engine cap
// (16 biomes per world; bump if needed).
//   biome_ground_packed[i] = pack(tier, layer) for biome i's ground slot.
// -1 means "this biome has no slot in this tier" (skip).
const int MAX_BIOMES = 16;
uniform int biome_ground_packed[MAX_BIOMES];
uniform int biome_mid_packed[MAX_BIOMES];
uniform int biome_rock_packed[MAX_BIOMES];

// World rect (in meters). Splat is sampled at
//   uv = (world_pos.xz - world_origin_m) / world_size_m
// where world_origin_m is the SW (min-x, min-z) corner.
uniform vec2 world_origin_m = vec2(-512.0, -512.0);
uniform float world_size_m = 1024.0;

// Slope thresholds (within-biome ground/mid/rock blend; same as v1)
uniform float slope_ground_max : hint_range(0.0, 1.0) = 0.92;
uniform float slope_rock_max   : hint_range(0.0, 1.0) = 0.55;

uniform float world_uv_scale = 0.04;

// Albedo safety (PITFALLS #1)
uniform float albedo_luma_floor : hint_range(0.0, 0.4) = 0.08;
uniform float ao_floor          : hint_range(0.0, 1.0) = 0.72;

// In-shader sun (same as terrain_scale_v1)
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

// Sample one (tier, layer) tuple → albedo + AO for that slot.
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

// Sample one biome's contribution (ground/mid/rock slope-blend).
void sample_biome(int biome_idx, vec2 uv, float up,
                  out vec3 albedo_out, out float ao_out) {
	int g_idx = biome_ground_packed[biome_idx];
	int m_idx = biome_mid_packed[biome_idx];
	int r_idx = biome_rock_packed[biome_idx];
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

	// Splat UV = world XZ -> [0..1] across the world rect.
	vec2 splat_uv = (v_world_pos.xz - world_origin_m) / world_size_m;

	// Accumulate biome contributions.
	vec3 albedo = vec3(0.0);
	float ao = 0.0;
	float wsum = 0.0;
	// Loop bound is num_biomes (set by ScaleWorld). Cap at MAX_BIOMES so
	// the GLSL compiler can unroll if it wants.
	for (int i = 0; i < MAX_BIOMES; i++) {
		if (i >= num_biomes) {
			break;
		}
		// One splat read per biome. Most fragments will have weight ~0
		// for most biomes (the splat is dominantly one-hot away from
		// biome boundaries).
		float w = texture(world_splat, vec3(splat_uv, float(i))).r;
		if (w < 1e-3) {
			continue;
		}
		vec3 a_i;
		float ao_i;
		sample_biome(i, uv, up, a_i, ao_i);
		albedo += a_i * w;
		ao     += ao_i * w;
		wsum   += w;
	}
	if (wsum > 1e-4) {
		albedo /= wsum;
		ao /= wsum;
	}
	ao = clamp(ao, ao_floor, 1.0);

	// Lambertian (clamped above lambert_floor)
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
