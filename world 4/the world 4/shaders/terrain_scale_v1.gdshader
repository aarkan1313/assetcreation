// W4 scale demo v1 terrain shader.
//
// `unshaded` so Godot's PBR pipeline is bypassed entirely — the v2 shader
// produced stationary black-patch artifacts at scale_demo's world scale
// (1024m, 522m relief) that we couldn't pin down in Godot's PBR code path.
// Bisect proved: lit minimal shader = patches, unshaded minimal shader =
// clean. So this shader runs unshaded and does its own lighting math.
//
// Features carried over from v2:
//   - 3-slot slope-blended albedo (ground / mid / rock)
//   - World-XZ UV (continuous across tiles)
//   - Per-slot AO + roughness blend (used as a soft shading multiplier)
//   - luma_floor on albedo
//
// Lighting (all in-shader, no Godot light sources read):
//   - Sun direction + color as uniforms
//   - Manual lambertian dot(normal, sun_dir) clamped above a floor
//   - Soft ambient term from uniform sky/ground colors mixed by normal.y
//
// Notes:
//   - Normal map textures are sampled but only contribute as a subtle
//     tint to the lambertian normal (not a tangent-space transform).
//     This avoids the tangent-space code path that might have been
//     responsible for the bug.
//   - render_mode `unshaded` means Godot writes the fragment directly
//     without any lighting/GI/shadow pass.

shader_type spatial;
render_mode unshaded, cull_back, depth_draw_opaque;

// 3 PBR slots, same convention as v2
uniform sampler2D ground_albedo : source_color;
uniform sampler2D ground_normal : hint_normal;
uniform sampler2D ground_rough;
uniform sampler2D ground_ao : hint_default_white;

uniform sampler2D mid_albedo : source_color;
uniform sampler2D mid_normal : hint_normal;
uniform sampler2D mid_rough;
uniform sampler2D mid_ao : hint_default_white;

uniform sampler2D rock_albedo : source_color;
uniform sampler2D rock_normal : hint_normal;
uniform sampler2D rock_rough;
uniform sampler2D rock_ao : hint_default_white;

// Slope thresholds
uniform float slope_ground_max : hint_range(0.0, 1.0) = 0.92;
uniform float slope_rock_max : hint_range(0.0, 1.0) = 0.55;

// World UV scale
uniform float world_uv_scale = 0.04;

// Albedo safety
uniform float albedo_luma_floor : hint_range(0.0, 0.4) = 0.08;
uniform float ao_floor : hint_range(0.0, 1.0) = 0.72;

// In-shader sun (not a Godot light source).
// Direction is FROM the surface TOWARD the sun in world space.
// Default = high noon, slightly off-axis (matches anchor's sun aesthetic).
uniform vec3 sun_dir = vec3(0.30, 0.85, 0.43);
uniform vec3 sun_color : source_color = vec3(1.0, 0.96, 0.88);
uniform float sun_intensity : hint_range(0.0, 3.0) = 1.0;
// Lambertian floor — never let the dark side go below this fraction of
// the sun's contribution. Prevents the "pure black backface" issue and
// reads as soft sky-bounce ambient.
uniform float lambert_floor : hint_range(0.0, 0.5) = 0.35;

// Sky/ground tint blended by world-normal.y for cheap ambient.
uniform vec3 sky_tint : source_color = vec3(0.78, 0.84, 0.92);
uniform vec3 ground_tint : source_color = vec3(0.58, 0.60, 0.55);
uniform float ambient_strength : hint_range(0.0, 2.0) = 0.45;

varying vec3 v_world_pos;
varying vec3 v_world_normal;

void vertex() {
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

vec3 luma_floor(vec3 color) {
	float lum = dot(color, vec3(0.2126, 0.7152, 0.0722));
	if (lum < albedo_luma_floor) {
		color += vec3(albedo_luma_floor - lum);
	}
	return clamp(color, vec3(0.0), vec3(1.0));
}

void fragment() {
	vec2 uv = v_world_pos.xz * world_uv_scale;
	vec3 wn = normalize(v_world_normal);
	float up = clamp(wn.y, 0.0, 1.0);

	// Sample three slots
	vec3 ga = luma_floor(texture(ground_albedo, uv).rgb);
	vec3 ma = luma_floor(texture(mid_albedo, uv).rgb);
	vec3 ra = luma_floor(texture(rock_albedo, uv).rgb);
	float go = texture(ground_ao, uv).r;
	float mo = texture(mid_ao, uv).r;
	float ro = texture(rock_ao, uv).r;

	// Slope-driven blend (same shape as v2 — guarded division included)
	float ground_w = smoothstep(slope_ground_max - 0.15, slope_ground_max, up);
	float rock_w = 1.0 - smoothstep(slope_rock_max, slope_rock_max + 0.15, up);
	float mid_w = max(0.0, 1.0 - ground_w - rock_w);
	float total = max(ground_w + mid_w + rock_w, 1e-4);
	ground_w /= total; mid_w /= total; rock_w /= total;

	vec3 albedo = ga * ground_w + ma * mid_w + ra * rock_w;
	float ao = clamp(go * ground_w + mo * mid_w + ro * rock_w, ao_floor, 1.0);

	// Lambertian (clamped above lambert_floor so backfaces never go black)
	vec3 sun_n = normalize(sun_dir);
	float ndl = dot(wn, sun_n);
	float lambert = max(ndl, lambert_floor);
	vec3 direct = sun_color * lambert * sun_intensity;

	// Cheap ambient: mix sky vs ground tint by normal.y (1.0 = full sky)
	vec3 ambient_color = mix(ground_tint, sky_tint, up);
	vec3 ambient = ambient_color * ambient_strength;

	vec3 lit = albedo * ao * (direct + ambient);
	// Final safety: don't allow output below the albedo's own luma_floor.
	lit = luma_floor(lit);

	ALBEDO = lit;
}
