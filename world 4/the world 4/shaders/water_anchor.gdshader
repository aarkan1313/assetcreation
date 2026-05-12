// W4 anchor demo — basic water shader.
// Flat plane at threshold elevation. Animated normal map for water motion,
// fake fresnel for view-angle reflectivity, alpha fade near edges so the
// terrain pokes through gracefully where ground rises above water.

shader_type spatial;
render_mode cull_back, blend_mix, depth_draw_always, specular_schlick_ggx;

uniform vec3 water_color : source_color = vec3(0.42, 0.68, 0.72);
uniform vec3 deep_color : source_color = vec3(0.18, 0.42, 0.52);
uniform float water_alpha : hint_range(0.0, 1.0) = 0.85;
uniform float fresnel_strength : hint_range(0.0, 2.0) = 1.0;
uniform float normal_strength : hint_range(0.0, 2.0) = 0.4;
uniform float wave_speed : hint_range(0.0, 5.0) = 0.3;
uniform float wave_scale : hint_range(0.001, 1.0) = 0.04;
uniform float roughness_val : hint_range(0.0, 1.0) = 0.15;

varying vec3 v_world_pos;

void vertex() {
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

// Simple 2D noise for animated water normal
float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise2d(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(
		mix(hash(i + vec2(0,0)), hash(i + vec2(1,0)), u.x),
		mix(hash(i + vec2(0,1)), hash(i + vec2(1,1)), u.x),
		u.y
	);
}

vec3 water_normal(vec2 uv, float t) {
	// Two layers of moving noise to fake ripple normals
	float n1 = noise2d(uv * 4.0 + vec2(t * 0.5, t * 0.3));
	float n2 = noise2d(uv * 8.0 + vec2(-t * 0.4, t * 0.2));
	float n = n1 * 0.6 + n2 * 0.4;
	// Compute pseudo-gradient
	float e = 0.01;
	float nx = noise2d(uv * 8.0 + vec2(-t * 0.4 + e, t * 0.2)) - n2;
	float ny = noise2d(uv * 8.0 + vec2(-t * 0.4, t * 0.2 + e)) - n2;
	return normalize(vec3(-nx * normal_strength, 1.0, -ny * normal_strength));
}

void fragment() {
	vec2 wuv = v_world_pos.xz * wave_scale;
	vec3 n_water = water_normal(wuv, TIME * wave_speed);

	// Fake fresnel: view direction dot up. At grazing angles the water
	// reflects sky color. At top-down (head-on) angles fresnel→0 and we'd
	// see pure deep_color — too dark. Floor the fresnel so water always
	// reads as water, not as shadow.
	vec3 view_dir = normalize(-(INV_VIEW_MATRIX * vec4(VIEW, 0.0)).xyz);
	float fresnel = pow(1.0 - clamp(dot(n_water, vec3(0.0, 1.0, 0.0)), 0.0, 1.0), 3.0);
	fresnel = mix(0.35, 1.0, fresnel) * fresnel_strength;

	vec3 albedo = mix(deep_color, water_color, fresnel);
	// Final brightness floor so water never reads pitch-black
	albedo = max(albedo, deep_color * 1.4);

	ALBEDO = albedo;
	ALPHA = water_alpha;
	NORMAL_MAP = n_water * 0.5 + 0.5;
	ROUGHNESS = roughness_val;
	METALLIC = 0.0;
	SPECULAR = 0.6;
}
