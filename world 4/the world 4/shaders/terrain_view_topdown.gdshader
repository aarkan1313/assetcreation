// W4 scale demo — topdown view shader.
//
// Designed to read as a 2D map, not lit terrain. No sun direction, no
// lambertian curve. Instead the shader does a hillshade-style modulation:
// the dot product between the surface normal and a fixed virtual sun
// becomes a brightness multiplier. That's how cartographers do relief
// shading on paper maps — it preserves shape information without the
// "this is a 3D scene" feeling.
//
// Optional sepia / topographic bias pushes the palette toward warm
// neutrals so it reads as "stylized" rather than "satellite photo with
// no shadows." Set sepia_amount = 0 to disable.
//
// Same slot blend as the walk/iso shaders so adjacent biomes still
// transition correctly. Unshaded (Pitfall #3).

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

// Hillshade params (cartographic relief shading).
// Sun is upper-left in screen space → light from -X, +Y, +Z direction.
// Azimuth and altitude are bakeable into a constant vector.
uniform vec3 hillshade_dir = vec3(-0.45, 0.78, 0.43);
uniform float hillshade_min : hint_range(0.0, 1.0) = 0.55;
uniform float hillshade_max : hint_range(0.0, 1.5) = 1.20;

// Sepia bias — push palette toward warm neutrals for "map style."
uniform float sepia_amount : hint_range(0.0, 1.0) = 0.25;
uniform vec3 sepia_color : source_color = vec3(0.96, 0.88, 0.74);

// Saturation gain to keep the map feeling lively after sepia mixing.
uniform float saturation : hint_range(0.0, 2.0) = 1.10;

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

	// Hillshade — cartographic relief shading. Dot product between the
	// surface normal and a fixed virtual sun, clamped to [min, max].
	// `min` keeps shadows readable (no black voids on the dark side);
	// `max` lets sun-facing slopes brighten slightly above 1.0 before
	// the final clamp.
	float hs_dot = dot(wn, normalize(hillshade_dir));
	float hillshade = clamp((hs_dot * 0.5 + 0.5), 0.0, 1.0);  // remap -1..1 → 0..1
	hillshade = mix(hillshade_min, hillshade_max, hillshade);

	vec3 lit = albedo * ao * hillshade;

	// Sepia bias toward warm neutrals.
	vec3 sepia_target = sepia_color * dot(lit, vec3(0.2126, 0.7152, 0.0722));
	lit = mix(lit, sepia_target, sepia_amount);

	// Saturation gain.
	float lum = dot(lit, vec3(0.2126, 0.7152, 0.0722));
	lit = mix(vec3(lum), lit, saturation);

	lit = luma_floor(lit);
	ALBEDO = lit;
}
