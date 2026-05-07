// Cheap stylized water for the biome terrain scenes (Godot 4.5 Forward+).
//
// Single flat plane at world Y = sea_level_m, covering the terrain footprint.
// Procedural noise normals scroll in two directions and stack for the wave
// shape. Depth-buffer-based shoreline fade gives soft edges where water meets
// terrain. Fresnel boosts reflectivity at grazing angles for that "looking
// across a lake" pop. No external textures, no compute, ~1 draw call.

shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, specular_schlick_ggx;

uniform vec4  shallow_color : source_color = vec4(0.20, 0.55, 0.65, 1.0);
uniform vec4  deep_color    : source_color = vec4(0.02, 0.08, 0.15, 1.0);
uniform float depth_fade_m  : hint_range(0.5, 64.0) = 8.0;
uniform float shore_softness: hint_range(0.05, 4.0) = 1.5;

uniform float wave_speed    : hint_range(0.0, 2.0) = 0.25;
uniform float wave_strength : hint_range(0.0, 1.0) = 0.35;
uniform float wave_scale    : hint_range(0.5, 16.0) = 4.0;

uniform float metallic_amt  : hint_range(0.0, 1.0) = 0.05;
uniform float roughness_amt : hint_range(0.0, 1.0) = 0.10;
uniform float fresnel_power : hint_range(0.5, 8.0)  = 4.0;
uniform float specular_amt  : hint_range(0.0, 1.0) = 0.65;

uniform sampler2D depth_tex : hint_depth_texture, filter_nearest;
uniform sampler2D screen_tex: hint_screen_texture, filter_linear_mipmap;

varying vec3 v_world;

// Cheap value noise — 2D
float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}
float vnoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float a = hash21(i);
    float b = hash21(i + vec2(1, 0));
    float c = hash21(i + vec2(0, 1));
    float d = hash21(i + vec2(1, 1));
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

// Stack two scrolling layers of noise to make a wave-ish height field.
float waves(vec2 uv, float t) {
    float a = vnoise(uv * wave_scale + vec2( t,  t * 0.7));
    float b = vnoise(uv * wave_scale * 2.1 + vec2(-t * 0.6, t * 0.9));
    return a * 0.6 + b * 0.4;
}

void vertex() {
    v_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
    float t = TIME * wave_speed;
    // Two scales of UV for big rolling swell + little chop on top.
    vec2 uv_big   = v_world.xz * 0.015;
    vec2 uv_small = v_world.xz * 0.080;

    float eps = 0.05;
    float h_big_0 = waves(uv_big,                          t);
    float h_big_x = waves(uv_big + vec2(eps, 0.0),         t);
    float h_big_z = waves(uv_big + vec2(0.0, eps),         t);
    float h_sml_0 = waves(uv_small,                        t * 1.7);
    float h_sml_x = waves(uv_small + vec2(eps, 0.0),       t * 1.7);
    float h_sml_z = waves(uv_small + vec2(0.0, eps),       t * 1.7);

    float gx = (h_big_0 - h_big_x) * 0.7 + (h_sml_0 - h_sml_x) * 0.3;
    float gz = (h_big_0 - h_big_z) * 0.7 + (h_sml_0 - h_sml_z) * 0.3;
    vec3 nrm = normalize(vec3(gx * wave_strength,
                              eps * 4.0,
                              gz * wave_strength));
    NORMAL = nrm;

    // Depth-buffer fade: distance from water surface to terrain underneath.
    float depth_raw = textureLod(depth_tex, SCREEN_UV, 0.0).x;
    vec4 ndc = vec4(SCREEN_UV * 2.0 - 1.0, depth_raw, 1.0);
    vec4 view_pos_h = INV_PROJECTION_MATRIX * ndc;
    vec3 view_pos = view_pos_h.xyz / view_pos_h.w;
    float scene_depth_view = -view_pos.z;
    float frag_depth_view  = -VERTEX.z;
    float water_depth = max(scene_depth_view - frag_depth_view, 0.0);

    // Smooth depth fade with smoothstep instead of a power curve. Pow curves
    // produce visible banding when stretched over >10m of water; smoothstep
    // over an explicit range gives a clean gradient.
    float depth_t = smoothstep(0.0, depth_fade_m * shore_softness, water_depth);

    vec3 col = mix(shallow_color.rgb, deep_color.rgb, depth_t);

    ALBEDO     = col;
    METALLIC   = metallic_amt;
    ROUGHNESS  = roughness_amt;
    SPECULAR   = specular_amt;

    // Manual fresnel boost at glancing angles using the world normal.
    float ndotv = clamp(dot(normalize(nrm), normalize(VIEW)), 0.0, 1.0);
    float fres = pow(1.0 - ndotv, fresnel_power);
    EMISSION = vec3(fres * 0.05);

    // Soft alpha at the shoreline so water doesn't z-fight terrain pixels:
    // mostly opaque, slightly translucent in the first metre to read as lapping.
    float shore_alpha = clamp(water_depth * 1.0, 0.4, 1.0);
    ALPHA = shore_alpha;
}
