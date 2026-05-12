// W4 anchor terrain shader — fresh, minimal version of the M11 5-slot pattern.
//
// Inputs:
//   - 5 material slots (grass / dirt / rock_light / rock_dark / snow), each
//     with albedo + normal + roughness + AO
//   - RGBA splat-weights texture: R=grass, G=dirt, B=rock_light, A=rock_dark.
//     Snow is the implicit remainder: max(0, 1 - R - G - B - A).
//   - Optional source_macro_albedo override: a baked per-pixel macro that
//     reflects the splat composition. When enabled, the macro is blended
//     against the slot mix by source_macro_strength.
//   - World-relative UVs for the macro (UV0 from the mesh, mapped through
//     source_world_size_m so the macro tiles per-bundle correctly).
//   - Slot textures use world-relative UVs scaled by world_uv_scale so they
//     don't stretch with chunk size.
//
// What's NOT in this shader (vs. W3's terrain_splat_unified.gdshader):
//   - No detail layer (anchor materials don't have detail PBR; future axis).
//   - No transition strip / boundary mask (no multi-biome in anchor).
//   - No seam blend / repeat policy (one bundle, one source, no streaming).
//   - No hex tiling (extra complexity; revisit if straight repeat looks bad).

shader_type spatial;
render_mode cull_back, depth_draw_opaque, specular_schlick_ggx;

// ----------------------------------------------------------------------
// Slot textures
// ----------------------------------------------------------------------

uniform sampler2D grass_albedo : source_color;
uniform sampler2D grass_normal : hint_normal;
uniform sampler2D grass_rough;
uniform sampler2D grass_ao : hint_default_white;

uniform sampler2D dirt_albedo : source_color;
uniform sampler2D dirt_normal : hint_normal;
uniform sampler2D dirt_rough;
uniform sampler2D dirt_ao : hint_default_white;

uniform sampler2D rock_light_albedo : source_color;
uniform sampler2D rock_light_normal : hint_normal;
uniform sampler2D rock_light_rough;
uniform sampler2D rock_light_ao : hint_default_white;

uniform sampler2D rock_dark_albedo : source_color;
uniform sampler2D rock_dark_normal : hint_normal;
uniform sampler2D rock_dark_rough;
uniform sampler2D rock_dark_ao : hint_default_white;

uniform sampler2D snow_albedo : source_color;
uniform sampler2D snow_normal : hint_normal;
uniform sampler2D snow_rough;
uniform sampler2D snow_ao : hint_default_white;

// ----------------------------------------------------------------------
// Splat
// ----------------------------------------------------------------------

uniform bool use_splat_weights = true;
uniform sampler2D splat_weights;
uniform float splat_weight_power : hint_range(0.25, 8.0) = 1.0;

// ----------------------------------------------------------------------
// Macro (baked per-pixel reference)
// ----------------------------------------------------------------------

uniform bool use_source_macro_albedo = false;
uniform sampler2D source_macro_albedo : source_color;
uniform bool use_source_macro_valid_mask = false;
uniform sampler2D source_macro_valid_mask;
uniform float source_macro_strength : hint_range(0.0, 1.0) = 0.84;
uniform vec2 source_world_size_m = vec2(256.0, 256.0);

// ----------------------------------------------------------------------
// Global params
// ----------------------------------------------------------------------

uniform float world_uv_scale = 0.05;  // 1m world → 0.05 UV units = 20m per texture repeat
uniform float roughness_strength : hint_range(0.0, 2.0) = 1.0;
uniform float roughness_floor : hint_range(0.04, 1.0) = 0.04;
uniform float specular_strength : hint_range(0.0, 1.0) = 0.0;
uniform float albedo_gain : hint_range(0.0, 1.5) = 0.95;
uniform float normal_strength : hint_range(0.0, 2.0) = 0.5;

// Varyings — world position + world normal passed to fragment
varying vec3 v_world_pos;
varying vec3 v_world_normal;

void vertex() {
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

// ----------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------

vec3 unpack_normal(vec3 n) {
	return n * 2.0 - 1.0;
}

// Biplanar projection — blend horizontal (XZ) projection with the dominant
// vertical (XY or YZ) projection based on the surface normal. Kills the
// "stretched texture on cliff face" artifact you get from naive world-XZ UV.
// Returns interpolated albedo/normal/rough/ao via out params.
void sample_slot_biplanar(sampler2D albedo_tex, sampler2D normal_tex,
                           sampler2D rough_tex, sampler2D ao_tex,
                           vec3 world_pos, vec3 world_n, float uv_scale,
                           out vec3 albedo, out vec3 normal_local,
                           out float rough, out float ao) {
	// Two projections:
	// - Horizontal (XZ): flat ground, normal pointing up
	// - Vertical: pick XY or YZ based on which world-axis the slope faces.
	//   If |n.x| > |n.z| → face is X-aligned, use YZ (side projection from X).
	//   Else → face is Z-aligned, use XY.
	vec2 uv_xz = world_pos.xz * uv_scale;
	vec2 uv_vert;
	if (abs(world_n.x) > abs(world_n.z)) {
		uv_vert = world_pos.zy * uv_scale;
	} else {
		uv_vert = world_pos.xy * uv_scale;
	}

	// Blend weight: 1.0 = pure horizontal (flat ground), 0.0 = pure vertical
	// (cliff). Surface normal's Y component determines this directly.
	float horizontal_weight = clamp(abs(world_n.y), 0.0, 1.0);
	// Sharpen the transition so almost-flat ground still uses pure XZ
	horizontal_weight = smoothstep(0.3, 0.85, horizontal_weight);

	vec3 alb_h = texture(albedo_tex, uv_xz).rgb;
	vec3 alb_v = texture(albedo_tex, uv_vert).rgb;
	albedo = mix(alb_v, alb_h, horizontal_weight);

	vec3 norm_h = unpack_normal(texture(normal_tex, uv_xz).rgb);
	vec3 norm_v = unpack_normal(texture(normal_tex, uv_vert).rgb);
	normal_local = mix(norm_v, norm_h, horizontal_weight);

	float rough_h = texture(rough_tex, uv_xz).r;
	float rough_v = texture(rough_tex, uv_vert).r;
	rough = mix(rough_v, rough_h, horizontal_weight);

	float ao_h = texture(ao_tex, uv_xz).r;
	float ao_v = texture(ao_tex, uv_vert).r;
	ao = mix(ao_v, ao_h, horizontal_weight);
}

void fragment() {
	// Macro UV: world XZ mapped to 0..1 across the bundle's world size.
	// The terrain mesh is built centered on the world origin (verts span
	// -world_size/2 to +world_size/2). Without the +0.5 shift, fract() of
	// a negative world_x wraps mid-mesh and produces a visible UV seam
	// down the middle of the topdown view. Shift by 0.5 so UV=0 is at
	// the mesh's negative edge and UV=1 is at the positive edge.
	vec2 macro_uv = vec2(
		v_world_pos.x / source_world_size_m.x + 0.5,
		v_world_pos.z / source_world_size_m.y + 0.5
	);
	macro_uv = clamp(macro_uv, vec2(0.0), vec2(1.0));

	// Biplanar projection — pick the right UV per pixel based on the
	// surface normal. Flat ground uses world-XZ; steep slopes blend in
	// a vertical projection so the texture doesn't stretch.
	vec3 wn = normalize(v_world_normal);

	vec3 grass_a, grass_n; float grass_r, grass_o;
	sample_slot_biplanar(grass_albedo, grass_normal, grass_rough, grass_ao,
	                     v_world_pos, wn, world_uv_scale,
	                     grass_a, grass_n, grass_r, grass_o);

	vec3 dirt_a, dirt_n; float dirt_r, dirt_o;
	sample_slot_biplanar(dirt_albedo, dirt_normal, dirt_rough, dirt_ao,
	                     v_world_pos, wn, world_uv_scale,
	                     dirt_a, dirt_n, dirt_r, dirt_o);

	vec3 rl_a, rl_n; float rl_r, rl_o;
	sample_slot_biplanar(rock_light_albedo, rock_light_normal, rock_light_rough, rock_light_ao,
	                     v_world_pos, wn, world_uv_scale,
	                     rl_a, rl_n, rl_r, rl_o);

	vec3 rd_a, rd_n; float rd_r, rd_o;
	sample_slot_biplanar(rock_dark_albedo, rock_dark_normal, rock_dark_rough, rock_dark_ao,
	                     v_world_pos, wn, world_uv_scale,
	                     rd_a, rd_n, rd_r, rd_o);

	vec3 snow_a, snow_n; float snow_r, snow_o;
	sample_slot_biplanar(snow_albedo, snow_normal, snow_rough, snow_ao,
	                     v_world_pos, wn, world_uv_scale,
	                     snow_a, snow_n, snow_r, snow_o);

	// Compute slot weights from splat
	vec4 splat_rgba = vec4(0.25, 0.25, 0.25, 0.25);  // default fallback
	float snow_w = 0.0;
	if (use_splat_weights) {
		splat_rgba = texture(splat_weights, macro_uv);
		// Implicit snow = max(0, 1 - sum)
		float explicit_sum = splat_rgba.r + splat_rgba.g + splat_rgba.b + splat_rgba.a;
		snow_w = max(0.0, 1.0 - explicit_sum);
	}

	// Power-shape so dominant slot wins
	vec4 w_explicit = pow(max(splat_rgba, vec4(1e-5)), vec4(splat_weight_power));
	snow_w = pow(max(snow_w, 1e-5), splat_weight_power);
	float total = w_explicit.r + w_explicit.g + w_explicit.b + w_explicit.a + snow_w;
	w_explicit /= max(total, 1e-6);
	snow_w /= max(total, 1e-6);

	// Blend albedos
	vec3 albedo = grass_a * w_explicit.r
	            + dirt_a * w_explicit.g
	            + rl_a * w_explicit.b
	            + rd_a * w_explicit.a
	            + snow_a * snow_w;

	// Blend normals in tangent space, then mix toward flat (0,0,1) by
	// normal_strength. For anchor v1 normal_strength is low (<=0.3) so the
	// mesh-geometry normal dominates and per-pixel normal noise (the
	// "tiny shadow speckles" pattern from sampled normal maps with mixed
	// OpenGL/DirectX encodings) is suppressed.
	vec3 normal_local = grass_n * w_explicit.r
	                  + dirt_n * w_explicit.g
	                  + rl_n * w_explicit.b
	                  + rd_n * w_explicit.a
	                  + snow_n * snow_w;
	normal_local = normalize(mix(vec3(0.0, 0.0, 1.0), normal_local, normal_strength));

	// Blend roughness + AO
	float rough = grass_r * w_explicit.r
	            + dirt_r * w_explicit.g
	            + rl_r * w_explicit.b
	            + rd_r * w_explicit.a
	            + snow_r * snow_w;
	float ao = grass_o * w_explicit.r
	         + dirt_o * w_explicit.g
	         + rl_o * w_explicit.b
	         + rd_o * w_explicit.a
	         + snow_o * snow_w;
	// AO override: W3 sampled AO at full strength because their material
	// pipeline (terrain_hex_detail) ran through a soft-composite stage
	// that produced flatter AO. The temperate_forest_* materials we have
	// in W4 inherit raw AO maps with mins of 0.08-0.20 — deep cracks
	// baked into the texture. Blending these via the splat produces a
	// peppered black pattern across the terrain in editor view.
	//
	// For anchor v1: set AO = 1.0 (no per-pixel occlusion from the
	// texture). Let the mesh geometry + lighting handle shading. This
	// makes the texture detail readable as material variation rather
	// than as crack-shaped shadow. When axis 6 (textures) builds the
	// proper soft-composite workflow we can re-enable real AO.
	ao = 1.0;

	// Source macro override: mix the slot blend with the baked macro
	if (use_source_macro_albedo) {
		vec3 macro_albedo = texture(source_macro_albedo, macro_uv).rgb;
		float valid = 1.0;
		if (use_source_macro_valid_mask) {
			valid = texture(source_macro_valid_mask, macro_uv).r;
		}
		float mix_amount = source_macro_strength * valid;
		albedo = mix(albedo, macro_albedo, mix_amount);
	}

	// Apply gain + roughness floor + roughness strength
	albedo = clamp(albedo * albedo_gain, vec3(0.0), vec3(1.0));
	rough = clamp(rough * roughness_strength, roughness_floor, 1.0);

	ALBEDO = albedo;
	NORMAL_MAP = normal_local * 0.5 + 0.5;  // Godot expects 0..1 normalmap encoding
	ROUGHNESS = rough;
	AO = ao;
	SPECULAR = specular_strength;
}
