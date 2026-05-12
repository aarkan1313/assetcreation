// W4 anchor rebuild baseline.
// Stage 0 is intentionally boring: one opaque albedo texture, no normals,
// no AO, no roughness maps, no alpha, no discard. Add one texture/setting at
// a time from here.
shader_type spatial;
render_mode cull_disabled, depth_draw_opaque, unshaded;

uniform sampler2D ground_albedo : source_color, repeat_enable;
uniform sampler2D mid_albedo : source_color, repeat_enable;
uniform sampler2D rock_albedo : source_color, repeat_enable;

uniform int texture_stage : hint_enum("Ground only", "Mid only", "Rock only", "Slope blend") = 0;
uniform float world_uv_scale : hint_range(0.005, 0.2) = 0.04;
uniform float min_luma : hint_range(0.0, 0.35) = 0.07;
uniform float slope_tint_strength : hint_range(0.0, 0.5) = 0.08;
uniform float roughness_value : hint_range(0.0, 1.0) = 0.82;
uniform float specular_value : hint_range(0.0, 1.0) = 0.08;

varying vec3 v_world_pos;
varying vec3 v_world_normal;

void vertex() {
    v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

vec3 safe_albedo(sampler2D tex, vec2 uv) {
    vec3 c = texture(tex, uv).rgb;
    float lum = dot(c, vec3(0.2126, 0.7152, 0.0722));
    if (lum < min_luma) {
        c += vec3(min_luma - lum);
    }
    return clamp(c, vec3(0.0), vec3(1.0));
}

void fragment() {
    vec2 uv = v_world_pos.xz * world_uv_scale;
    vec3 ground = safe_albedo(ground_albedo, uv);
    vec3 mid = safe_albedo(mid_albedo, uv);
    vec3 rock = safe_albedo(rock_albedo, uv);

    vec3 wn = normalize(v_world_normal);
    float up = clamp(wn.y, 0.0, 1.0);
    float ground_w = smoothstep(0.78, 0.96, up);
    float rock_w = 1.0 - smoothstep(0.45, 0.72, up);
    float mid_w = max(0.0, 1.0 - ground_w - rock_w);
    float total = max(ground_w + mid_w + rock_w, 0.0001);
    ground_w /= total;
    mid_w /= total;
    rock_w /= total;

    vec3 albedo = ground;
    if (texture_stage == 1) {
        albedo = mid;
    } else if (texture_stage == 2) {
        albedo = rock;
    } else if (texture_stage == 3) {
        albedo = ground * ground_w + mid * mid_w + rock * rock_w;
    }

    // Small geometry-only tint so the single-texture baseline still reads as terrain.
    float slope = 1.0 - up;
    albedo *= mix(1.0, 0.78, slope * slope_tint_strength);

    ALBEDO = clamp(albedo, vec3(0.0), vec3(1.0));
    ROUGHNESS = roughness_value;
    SPECULAR = specular_value;
}
