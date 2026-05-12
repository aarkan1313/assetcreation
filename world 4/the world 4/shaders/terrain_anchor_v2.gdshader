// W4 anchor v2 — simple slope-driven 3-slot terrain shader.
//
// Three texture slots, each a complete tileable PBR set (albedo, normal,
// roughness, AO):
//   - ground  : flat terrain (low slope)
//   - mid     : transitional surface (mid slope, blended in around 30-50 degrees)
//   - rock    : steep slopes (high slope)
//
// Blending is purely slope-driven (surface normal Y). No splat texture,
// no macro layer, no biplanar gymnastics. Each slot samples world-XZ UV
// so adjacent mesh chunks share continuous detail.
//
// Why simpler than v1: the v1 5-slot splat+macro pipeline produced a
// smeared wash because all 5 textures were similar and the macro was a
// synthetic procedural composite. v2 uses three visually-distinct
// textures (real ortho scrub + ortho rock + ComfyUI lichen) blended
// only by slope. The differences between slots will read clearly.
//
// Two of three slots are tileable PBR sets derived from real satellite
// orthophoto (W3's _soft_composite pipeline output). One is a ComfyUI-
// generated tileable. This is the "mix of real + ComfyUI" the user
// asked for, with both kinds of texture appearing in the rendered terrain.

shader_type spatial;
render_mode cull_back, depth_draw_opaque, specular_schlick_ggx;

// Three texture slots
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

// Slope thresholds (degrees converted to dot-product cutoffs at runtime).
// Surfaces with normal.y >= 0.95 (about 18 degrees from up) are pure ground.
// Surfaces with normal.y <= 0.55 (about 57 degrees from up) are pure rock.
// In between blends through "mid".
uniform float slope_ground_max : hint_range(0.0, 1.0) = 0.95;  // above this = pure ground
uniform float slope_rock_max : hint_range(0.0, 1.0) = 0.55;    // below this = pure rock

uniform float world_uv_scale = 0.04;  // 1m world = 0.04 UV → 25m per texture tile
uniform float normal_strength : hint_range(0.0, 2.0) = 0.2;
uniform float roughness_floor : hint_range(0.0, 1.0) = 0.5;
uniform float ao_floor : hint_range(0.0, 1.0) = 0.72;
uniform float albedo_luma_floor : hint_range(0.0, 0.4) = 0.08;

varying vec3 v_world_pos;
varying vec3 v_world_normal;

void vertex() {
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

vec3 unpack_normal(vec3 n) {
	return n * 2.0 - 1.0;
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
	float up = clamp(wn.y, 0.0, 1.0);  // 1.0 = flat ground, 0.0 = vertical cliff

	// Sample all three slots
	vec3 ga = luma_floor(texture(ground_albedo, uv).rgb);
	vec3 gn = unpack_normal(texture(ground_normal, uv).rgb);
	float gr = texture(ground_rough, uv).r;
	float go = texture(ground_ao, uv).r;

	vec3 ma = luma_floor(texture(mid_albedo, uv).rgb);
	vec3 mn = unpack_normal(texture(mid_normal, uv).rgb);
	float mr = texture(mid_rough, uv).r;
	float mo = texture(mid_ao, uv).r;

	vec3 ra = luma_floor(texture(rock_albedo, uv).rgb);
	vec3 rn = unpack_normal(texture(rock_normal, uv).rgb);
	float rr = texture(rock_rough, uv).r;
	float ro = texture(rock_ao, uv).r;

	// Two-stage blend: rock→mid→ground based on `up`.
	// CRITICAL: `total` can be near-zero (or negative due to floating point)
	// when smoothstep edges land in a weird zone, then divisions produce
	// NaN/Inf → NaN propagates to NORMAL_MAP → Godot renders the fragment
	// as solid black. This was the "black spots everywhere" bug. Guard the
	// divisor with max(total, 1e-4).
	float ground_w = smoothstep(slope_ground_max - 0.15, slope_ground_max, up);
	float rock_w = 1.0 - smoothstep(slope_rock_max, slope_rock_max + 0.15, up);
	float mid_w = max(0.0, 1.0 - ground_w - rock_w);
	float total = max(ground_w + mid_w + rock_w, 1e-4);
	ground_w /= total; mid_w /= total; rock_w /= total;

	vec3 albedo = ga * ground_w + ma * mid_w + ra * rock_w;

	// Normal blend: do NOT normalize the blended vector — it can sum to
	// near-zero when normals from three slots cancel out. Normalizing
	// zero-vector = NaN = black fragment. Just clamp and pass to Godot's
	// pipeline, which handles unnormalized normals gracefully.
	vec3 nrm = gn * ground_w + mn * mid_w + rn * rock_w;
	// Reduce the strength of the blended normal so it can't dominate the
	// mesh geometry normal — gives subtle bump instead of overwriting.
	nrm = mix(vec3(0.0, 0.0, 1.0), nrm, normal_strength);
	// Don't normalize — Godot normalizes internally. Manual normalize on
	// a near-zero vector caused the NaN black spots.

	float rough = gr * ground_w + mr * mid_w + rr * rock_w;
	float ao = go * ground_w + mo * mid_w + ro * rock_w;
	ao = clamp(ao, ao_floor, 1.0);

	// Final albedo safety clamp — ensures we never output negative or NaN
	// color which would also render black.
	albedo = luma_floor(albedo);

	ALBEDO = albedo;
	NORMAL_MAP = clamp(nrm * 0.5 + 0.5, vec3(0.0), vec3(1.0));
	ROUGHNESS = clamp(rough, 0.4, 1.0);
	AO = ao;
	SPECULAR = 0.2;
}
