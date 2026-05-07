// Macro + Detail PBR — AAA close-up + far-look material.
// Samples a macro material at coarse UV, mixes a detail material at fine UV.
// Detail normal blended via Reoriented Normal Mapping (RNM).
//
// Use case: terrain, walls, large props that need to look crisp 0-2m AND
// believable 5-30m. Standard PBR shader can't do both because tiling artifacts
// either get oversampled (too tile-y close) or wash out (mushy far).
//
// Plug this into a MeshInstance3D's material override. Paired data lives in
// world/textures/library/<macro>/detail_pair.json.
shader_type spatial;
render_mode cull_back, depth_draw_opaque, specular_schlick_ggx;

// ---- Macro sampling ----
uniform sampler2D macro_albedo : source_color;
uniform sampler2D macro_normal : hint_normal;
uniform sampler2D macro_roughness;
uniform sampler2D macro_metallic;
uniform sampler2D macro_height;
uniform sampler2D macro_ao : hint_default_white;
uniform float macro_uv_scale = 1.0;        // 1.0 = 1m repeat per world unit
uniform float macro_normal_strength = 1.0;

// ---- Detail sampling ----
uniform sampler2D detail_albedo : source_color;
uniform sampler2D detail_normal : hint_normal;
uniform sampler2D detail_roughness;
uniform float detail_uv_scale = 10.0;      // 10x macro frequency = 0.1m repeat
uniform float detail_albedo_strength : hint_range(0.0, 1.0) = 0.6;
uniform float detail_normal_strength : hint_range(0.0, 1.0) = 0.42;
uniform float detail_roughness_strength : hint_range(0.0, 1.0) = 0.5;

// ---- Distance fade (detail fades out beyond N meters) ----
uniform float detail_fade_start_m = 8.0;
uniform float detail_fade_end_m = 30.0;

vec3 reorient_normal(vec3 t, vec3 u) {
    // Reoriented Normal Mapping (Barré-Brisebois & Hill, GDC 2012).
    // t = base normal; u = detail normal. Both in tangent space, +Z out.
    t.z += 1.0;
    u.xy *= -1.0;
    return normalize(t * dot(t, u) - u * t.z);
}

vec3 soft_light(vec3 base, vec3 blend, float strength) {
    vec3 result = mix(
        base * (2.0 * blend),
        1.0 - 2.0 * (1.0 - base) * (1.0 - blend),
        step(0.5, blend)
    );
    return mix(base, result, strength);
}

void fragment() {
    // Camera distance for fade
    float dist = length(VIEW);
    float detail_fade = 1.0 - smoothstep(detail_fade_start_m, detail_fade_end_m, dist);

    vec2 uv_macro = UV * macro_uv_scale;
    vec2 uv_detail = UV * macro_uv_scale * detail_uv_scale;

    // Macro samples
    vec3 macro_a = texture(macro_albedo, uv_macro).rgb;
    vec3 macro_n = texture(macro_normal, uv_macro).rgb * 2.0 - 1.0;
    macro_n.xy *= macro_normal_strength;
    macro_n = normalize(macro_n);
    float macro_r = texture(macro_roughness, uv_macro).r;
    float macro_m = texture(macro_metallic, uv_macro).r;
    float macro_ao_v = texture(macro_ao, uv_macro).r;

    // Detail samples
    vec3 det_a = texture(detail_albedo, uv_detail).rgb;
    vec3 det_n = texture(detail_normal, uv_detail).rgb * 2.0 - 1.0;
    det_n.xy *= detail_normal_strength;
    det_n = normalize(det_n);
    float det_r = texture(detail_roughness, uv_detail).r;

    // Albedo: soft-light blend, faded by distance
    vec3 final_albedo = soft_light(macro_a, det_a, detail_albedo_strength * detail_fade);

    // Normal: RNM, faded
    vec3 fade_det_n = mix(vec3(0, 0, 1), det_n, detail_fade);
    vec3 final_normal = reorient_normal(macro_n, fade_det_n);

    // Roughness: blend with strength + fade
    float final_rough = mix(macro_r, mix(macro_r, det_r, 0.5), detail_roughness_strength * detail_fade);

    ALBEDO = final_albedo;
    NORMAL_MAP = final_normal * 0.5 + 0.5;
    NORMAL_MAP_DEPTH = 1.0;
    ROUGHNESS = clamp(final_rough, 0.04, 1.0);
    METALLIC = macro_m;
    AO = macro_ao_v;
}
