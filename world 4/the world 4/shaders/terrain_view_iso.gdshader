// W4 scale demo — iso view shader.
//
// Same 3-slot slope-blended albedo as terrain_scale_v1, but lighting is
// flatter and the lambertian curve is biased toward "form readability"
// rather than "physical realism." Designed to read as a 2.5D iso shot
// where the player sees big shapes at a glance, not fine slope cues.
//
// Differences from scale_v1:
//   - lambert_floor lifted (0.35 -> 0.55) so dark sides never read as
//     black voids
//   - sun_intensity dropped (1.0 -> 0.5) so highlights don't dominate
//   - ambient_strength raised so the silhouette has body
//   - A "form light" term added: a slight brighten on upward-facing
//     fragments using normal.y to push hills forward against valleys
//   - Unshaded (Pitfall #3) just like scale_v1.

shader_type spatial;
render_mode unshaded, cull_back, depth_draw_opaque;

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

uniform float slope_ground_max : hint_range(0.0, 1.0) = 0.92;
uniform float slope_rock_max : hint_range(0.0, 1.0) = 0.55;
uniform float world_uv_scale = 0.04;
uniform float albedo_luma_floor : hint_range(0.0, 0.4) = 0.08;
uniform float ao_floor : hint_range(0.0, 1.0) = 0.72;

uniform vec3 sun_dir = vec3(0.30, 0.85, 0.43);
uniform vec3 sun_color : source_color = vec3(1.0, 0.96, 0.88);
uniform float sun_intensity : hint_range(0.0, 3.0) = 0.5;
uniform float lambert_floor : hint_range(0.0, 0.9) = 0.55;

uniform vec3 sky_tint : source_color = vec3(0.80, 0.86, 0.94);
uniform vec3 ground_tint : source_color = vec3(0.62, 0.64, 0.58);
uniform float ambient_strength : hint_range(0.0, 2.0) = 0.65;

// Form light pushes upward-facing fragments brighter so the bigger
// shapes of the terrain pop in iso. 0 = no effect (matches walk shader).
uniform float form_light_strength : hint_range(0.0, 0.5) = 0.18;

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

	vec3 ga = luma_floor(texture(ground_albedo, uv).rgb);
	vec3 ma = luma_floor(texture(mid_albedo, uv).rgb);
	vec3 ra = luma_floor(texture(rock_albedo, uv).rgb);
	float go = texture(ground_ao, uv).r;
	float mo = texture(mid_ao, uv).r;
	float ro = texture(rock_ao, uv).r;

	float ground_w = smoothstep(slope_ground_max - 0.15, slope_ground_max, up);
	float rock_w = 1.0 - smoothstep(slope_rock_max, slope_rock_max + 0.15, up);
	float mid_w = max(0.0, 1.0 - ground_w - rock_w);
	float total = max(ground_w + mid_w + rock_w, 1e-4);
	ground_w /= total; mid_w /= total; rock_w /= total;

	vec3 albedo = ga * ground_w + ma * mid_w + ra * rock_w;
	float ao = clamp(go * ground_w + mo * mid_w + ro * rock_w, ao_floor, 1.0);

	vec3 sun_n = normalize(sun_dir);
	float ndl = dot(wn, sun_n);
	float lambert = max(ndl, lambert_floor);
	vec3 direct = sun_color * lambert * sun_intensity;

	vec3 ambient_color = mix(ground_tint, sky_tint, up);
	vec3 ambient = ambient_color * ambient_strength;

	// Form light: brighten upward-facing fragments to push hills forward.
	vec3 form_light = vec3(1.0) * up * form_light_strength;

	vec3 lit = albedo * ao * (direct + ambient + form_light);
	lit = luma_floor(lit);

	ALBEDO = lit;
}
