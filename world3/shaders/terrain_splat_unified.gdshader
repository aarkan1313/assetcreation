// Unified terrain shader prototype for M4.
//
// Goals:
// - Keep the 5-slot height/slope fallback behavior from terrain_blend.gdshader.
// - Add an RGBA splat-weight texture path. The fifth slot is the remaining
//   weight: max(1 - rgba_sum, 0).
// - Carry the macro/detail material path from terrain_hex_detail.gdshader so a
//   finished OpenTopo material can be bound through this shader too.
//
// This is intentionally a fixed 5-slot prototype. Godot does not make dynamic
// sampler arrays pleasant, and the current catalog kits already resolve to the
// same 5 semantic slots.

shader_type spatial;
render_mode cull_back, depth_draw_opaque, specular_schlick_ggx;

uniform sampler2D grass_albedo : source_color;
uniform sampler2D grass_normal : hint_normal;
uniform sampler2D grass_rough;
uniform sampler2D grass_ao : hint_default_white;
uniform sampler2D grass_detail_albedo : source_color;
uniform sampler2D grass_detail_normal : hint_normal;
uniform sampler2D grass_detail_rough;

uniform sampler2D dirt_albedo : source_color;
uniform sampler2D dirt_normal : hint_normal;
uniform sampler2D dirt_rough;
uniform sampler2D dirt_ao : hint_default_white;
uniform sampler2D dirt_detail_albedo : source_color;
uniform sampler2D dirt_detail_normal : hint_normal;
uniform sampler2D dirt_detail_rough;

uniform sampler2D rock_light_albedo : source_color;
uniform sampler2D rock_light_normal : hint_normal;
uniform sampler2D rock_light_rough;
uniform sampler2D rock_light_ao : hint_default_white;
uniform sampler2D rock_light_detail_albedo : source_color;
uniform sampler2D rock_light_detail_normal : hint_normal;
uniform sampler2D rock_light_detail_rough;

uniform sampler2D rock_dark_albedo : source_color;
uniform sampler2D rock_dark_normal : hint_normal;
uniform sampler2D rock_dark_rough;
uniform sampler2D rock_dark_ao : hint_default_white;
uniform sampler2D rock_dark_detail_albedo : source_color;
uniform sampler2D rock_dark_detail_normal : hint_normal;
uniform sampler2D rock_dark_detail_rough;

uniform sampler2D snow_albedo : source_color;
uniform sampler2D snow_normal : hint_normal;
uniform sampler2D snow_rough;
uniform sampler2D snow_ao : hint_default_white;
uniform sampler2D snow_detail_albedo : source_color;
uniform sampler2D snow_detail_normal : hint_normal;
uniform sampler2D snow_detail_rough;

uniform bool use_splat_weights = false;
uniform sampler2D splat_weights;
uniform float splat_uv_scale = 1.0;
uniform float splat_weight_power : hint_range(0.25, 8.0) = 1.0;

uniform float world_uv_scale = 0.1;
uniform float hex_strength : hint_range(0.0, 1.0) = 1.0;
uniform float blend_sharpness : hint_range(1.0, 32.0) = 8.0;
uniform float roughness_strength : hint_range(0.0, 1.0) = 1.0;
uniform float normal_strength : hint_range(0.0, 2.0) = 1.0;

uniform float macro_scale = 80.0;
uniform float macro_value_strength : hint_range(0.0, 1.0) = 0.15;
uniform float macro_hue_strength : hint_range(0.0, 0.3) = 0.0;

uniform float detail_uv_scale_mult : hint_range(2.0, 32.0) = 8.0;
uniform float detail_albedo_strength : hint_range(0.0, 1.0) = 0.0;
uniform float detail_normal_strength : hint_range(0.0, 1.0) = 0.0;
uniform float detail_rough_strength : hint_range(0.0, 1.0) = 0.0;
uniform float detail_fade_start_m = 8.0;
uniform float detail_fade_end_m = 30.0;

uniform float elev_min_m = 0.0;
uniform float elev_range_m = 1.0;
uniform float slope_threshold : hint_range(0.0, 1.0) = 0.45;
uniform float slope_softness : hint_range(0.0, 0.5) = 0.15;
uniform float h_grass_dirt : hint_range(0.0, 1.0) = 0.20;
uniform float h_dirt_rockdark : hint_range(0.0, 1.0) = 0.55;
uniform float h_rockdark_snow : hint_range(0.0, 1.0) = 0.85;
uniform float h_band_softness : hint_range(0.01, 0.3) = 0.08;

vec2 hash22(vec2 p) {
    p = vec2(dot(p, vec2(127.1, 311.7)),
             dot(p, vec2(269.5, 183.3)));
    return fract(sin(p) * 43758.5453) * 2.0 - 1.0;
}

float hash21(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float hash31(vec3 p) {
    p = fract(p * vec3(443.897, 441.423, 437.195));
    p += dot(p, p.yzx + 19.19);
    return fract((p.x + p.y) * p.z);
}

float value_noise_3d(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float n000 = hash31(i + vec3(0,0,0));
    float n100 = hash31(i + vec3(1,0,0));
    float n010 = hash31(i + vec3(0,1,0));
    float n110 = hash31(i + vec3(1,1,0));
    float n001 = hash31(i + vec3(0,0,1));
    float n101 = hash31(i + vec3(1,0,1));
    float n011 = hash31(i + vec3(0,1,1));
    float n111 = hash31(i + vec3(1,1,1));
    float nx00 = mix(n000, n100, f.x);
    float nx10 = mix(n010, n110, f.x);
    float nx01 = mix(n001, n101, f.x);
    float nx11 = mix(n011, n111, f.x);
    float nxy0 = mix(nx00, nx10, f.y);
    float nxy1 = mix(nx01, nx11, f.y);
    return mix(nxy0, nxy1, f.z);
}

float macro_noise(vec3 p) {
    float n = value_noise_3d(p);
    n += value_noise_3d(p * 2.13 + vec3(13.7, 7.4, 21.9)) * 0.5;
    return n / 1.5;
}

void hex_weights(vec2 uv, out vec2 c0, out vec2 c1, out vec2 c2,
                 out float w0, out float w1, out float w2) {
    const float K = 1.15470054;
    mat2 GRID_TO_SKEW = mat2(vec2(K, 0.0), vec2(-K * 0.5, K));
    vec2 skewed = GRID_TO_SKEW * uv;
    vec2 ip = floor(skewed);
    vec2 fp = skewed - ip;
    if (fp.x + fp.y < 1.0) {
        c0 = ip; c1 = ip + vec2(1.0, 0.0); c2 = ip + vec2(0.0, 1.0);
        w0 = 1.0 - fp.x - fp.y; w1 = fp.x; w2 = fp.y;
    } else {
        c0 = ip + vec2(1.0, 0.0); c1 = ip + vec2(0.0, 1.0); c2 = ip + vec2(1.0, 1.0);
        w0 = 1.0 - fp.y; w1 = 1.0 - fp.x; w2 = fp.x + fp.y - 1.0;
    }
}

vec4 sample_jittered(sampler2D tex, vec2 uv, vec2 cell) {
    vec2 jitter = hash22(cell) * 0.5;
    float rot = hash21(cell + 17.31) * 6.2831853;
    float c = cos(rot); float s = sin(rot);
    mat2 R = mat2(vec2(c, -s), vec2(s, c));
    return texture(tex, R * uv + jitter);
}

vec3 hex_sample_albedo(sampler2D tex, vec2 uv) {
    vec2 c0, c1, c2; float w0, w1, w2;
    hex_weights(uv, c0, c1, c2, w0, w1, w2);
    vec3 s0 = sample_jittered(tex, uv, c0).rgb;
    vec3 s1 = sample_jittered(tex, uv, c1).rgb;
    vec3 s2 = sample_jittered(tex, uv, c2).rgb;
    vec3 mean = (s0 + s1 + s2) / 3.0;
    vec3 d0 = s0 - mean; vec3 d1 = s1 - mean; vec3 d2 = s2 - mean;
    float ws = sqrt(w0 * w0 + w1 * w1 + w2 * w2);
    return mean + (w0 * d0 + w1 * d1 + w2 * d2) / max(ws, 1e-4);
}

vec3 hex_sample_rgb(sampler2D tex, vec2 uv) {
    vec2 c0, c1, c2; float w0, w1, w2;
    hex_weights(uv, c0, c1, c2, w0, w1, w2);
    vec3 s0 = sample_jittered(tex, uv, c0).rgb;
    vec3 s1 = sample_jittered(tex, uv, c1).rgb;
    vec3 s2 = sample_jittered(tex, uv, c2).rgb;
    return s0 * w0 + s1 * w1 + s2 * w2;
}

float hex_sample_r(sampler2D tex, vec2 uv) {
    vec2 c0, c1, c2; float w0, w1, w2;
    hex_weights(uv, c0, c1, c2, w0, w1, w2);
    float s0 = sample_jittered(tex, uv, c0).r;
    float s1 = sample_jittered(tex, uv, c1).r;
    float s2 = sample_jittered(tex, uv, c2).r;
    return s0 * w0 + s1 * w1 + s2 * w2;
}

vec3 maybe_hex_albedo(sampler2D tex, vec2 uv) {
    if (hex_strength <= 0.001) return texture(tex, uv).rgb;
    return mix(texture(tex, uv).rgb, hex_sample_albedo(tex, uv), hex_strength);
}

vec3 maybe_hex_rgb(sampler2D tex, vec2 uv) {
    if (hex_strength <= 0.001) return texture(tex, uv).rgb;
    return mix(texture(tex, uv).rgb, hex_sample_rgb(tex, uv), hex_strength);
}

float maybe_hex_r(sampler2D tex, vec2 uv) {
    if (hex_strength <= 0.001) return texture(tex, uv).r;
    return mix(texture(tex, uv).r, hex_sample_r(tex, uv), hex_strength);
}

vec3 triplanar_weights(vec3 n) {
    vec3 w = pow(abs(n), vec3(blend_sharpness));
    return w / (w.x + w.y + w.z + 1e-5);
}

vec3 soft_light(vec3 base, vec3 blend, float strength) {
    vec3 result = mix(
        base * (2.0 * blend),
        1.0 - 2.0 * (1.0 - base) * (1.0 - blend),
        step(0.5, blend)
    );
    return mix(base, result, strength);
}

vec3 reorient_normal_tangent(vec3 t, vec3 u) {
    t.z += 1.0;
    u.xy *= -1.0;
    return normalize(t * dot(t, u) - u * t.z);
}

vec3 blend_normal_world(vec3 world_pos, vec3 world_n,
                         vec3 macro_n, vec3 detail_n, float strength) {
    if (strength <= 0.001) return macro_n;
    vec3 dpdx = dFdx(world_pos);
    vec3 T = normalize(dpdx - world_n * dot(dpdx, world_n));
    if (length(dpdx) < 1e-6) {
        vec3 helper = abs(world_n.y) < 0.9 ? vec3(0, 1, 0) : vec3(1, 0, 0);
        T = normalize(cross(helper, world_n));
    }
    vec3 B = normalize(cross(world_n, T));
    mat3 tbn = mat3(T, B, world_n);
    mat3 tbn_inv = transpose(tbn);

    vec3 macro_t = tbn_inv * macro_n;
    vec3 detail_t = tbn_inv * detail_n;
    vec3 blended_t = reorient_normal_tangent(macro_t, detail_t);
    vec3 blended_w = tbn * blended_t;
    return normalize(mix(macro_n, blended_w, clamp(strength, 0.0, 1.0)));
}

struct LayerSample {
    vec3 albedo;
    vec3 normal;
    float rough;
    float ao;
};

LayerSample sample_layer(sampler2D albedo_tex, sampler2D normal_tex,
                          sampler2D rough_tex, sampler2D ao_tex,
                          vec2 uv_x, vec2 uv_y, vec2 uv_z,
                          vec3 weights, vec3 wn) {
    LayerSample s;
    vec3 a_x = maybe_hex_albedo(albedo_tex, uv_x);
    vec3 a_y = maybe_hex_albedo(albedo_tex, uv_y);
    vec3 a_z = maybe_hex_albedo(albedo_tex, uv_z);
    s.albedo = a_x * weights.x + a_y * weights.y + a_z * weights.z;

    vec3 n_x = maybe_hex_rgb(normal_tex, uv_x) * 2.0 - 1.0;
    vec3 n_y = maybe_hex_rgb(normal_tex, uv_y) * 2.0 - 1.0;
    vec3 n_z = maybe_hex_rgb(normal_tex, uv_z) * 2.0 - 1.0;
    n_x.xy *= normal_strength; n_y.xy *= normal_strength; n_z.xy *= normal_strength;
    s.normal = normalize(
        vec3(0.0, n_x.y, n_x.x) * weights.x +
        vec3(n_y.x, 0.0, n_y.y) * weights.y +
        vec3(n_z.x, n_z.y, 0.0) * weights.z +
        wn
    );

    float r_x = maybe_hex_r(rough_tex, uv_x);
    float r_y = maybe_hex_r(rough_tex, uv_y);
    float r_z = maybe_hex_r(rough_tex, uv_z);
    s.rough = r_x * weights.x + r_y * weights.y + r_z * weights.z;

    float ao_x = maybe_hex_r(ao_tex, uv_x);
    float ao_y = maybe_hex_r(ao_tex, uv_y);
    float ao_z = maybe_hex_r(ao_tex, uv_z);
    s.ao = ao_x * weights.x + ao_y * weights.y + ao_z * weights.z;
    return s;
}

LayerSample sample_detail_layer(sampler2D albedo_tex, sampler2D normal_tex,
                                 sampler2D rough_tex,
                                 vec2 uv_x, vec2 uv_y, vec2 uv_z,
                                 vec3 weights, vec3 wn) {
    LayerSample s;
    vec3 a_x = maybe_hex_albedo(albedo_tex, uv_x);
    vec3 a_y = maybe_hex_albedo(albedo_tex, uv_y);
    vec3 a_z = maybe_hex_albedo(albedo_tex, uv_z);
    s.albedo = a_x * weights.x + a_y * weights.y + a_z * weights.z;

    vec3 n_x = maybe_hex_rgb(normal_tex, uv_x) * 2.0 - 1.0;
    vec3 n_y = maybe_hex_rgb(normal_tex, uv_y) * 2.0 - 1.0;
    vec3 n_z = maybe_hex_rgb(normal_tex, uv_z) * 2.0 - 1.0;
    s.normal = normalize(
        vec3(0.0, n_x.y, n_x.x) * weights.x +
        vec3(n_y.x, 0.0, n_y.y) * weights.y +
        vec3(n_z.x, n_z.y, 0.0) * weights.z +
        wn
    );

    float r_x = maybe_hex_r(rough_tex, uv_x);
    float r_y = maybe_hex_r(rough_tex, uv_y);
    float r_z = maybe_hex_r(rough_tex, uv_z);
    s.rough = r_x * weights.x + r_y * weights.y + r_z * weights.z;
    s.ao = 1.0;
    return s;
}

void height_slope_weights(float h, float slope,
                          out float w_grass, out float w_dirt,
                          out float w_rl, out float w_rd,
                          out float w_snow) {
    float w_slope = smoothstep(slope_threshold - slope_softness,
                               slope_threshold + slope_softness, slope);
    float gd = h_band_softness;
    float band_grass = 1.0 - smoothstep(h_grass_dirt - gd, h_grass_dirt + gd, h);
    float band_snow = smoothstep(h_rockdark_snow - gd, h_rockdark_snow + gd, h);
    float low_dirt = smoothstep(h_grass_dirt - gd, h_grass_dirt + gd, h);
    float high_dirt = 1.0 - smoothstep(h_dirt_rockdark - gd, h_dirt_rockdark + gd, h);
    float band_dirt = low_dirt * high_dirt;
    float low_rd = smoothstep(h_dirt_rockdark - gd, h_dirt_rockdark + gd, h);
    float high_rd = 1.0 - smoothstep(h_rockdark_snow - gd, h_rockdark_snow + gd, h);
    float band_rockdark = low_rd * high_rd;

    float keep = 1.0 - w_slope;
    w_grass = band_grass * keep;
    w_dirt = band_dirt * keep;
    w_rl = w_slope;
    w_rd = band_rockdark * keep;
    w_snow = band_snow * keep;

    float total = w_grass + w_dirt + w_rl + w_rd + w_snow + 1e-6;
    w_grass /= total; w_dirt /= total; w_rl /= total;
    w_rd /= total; w_snow /= total;
}

void splat_layer_weights(vec2 uv,
                         out float w_grass, out float w_dirt,
                         out float w_rl, out float w_rd,
                         out float w_snow) {
    vec4 rgba = max(texture(splat_weights, fract(uv * splat_uv_scale)), vec4(0.0));
    w_grass = pow(rgba.r, splat_weight_power);
    w_dirt = pow(rgba.g, splat_weight_power);
    w_rl = pow(rgba.b, splat_weight_power);
    w_rd = pow(rgba.a, splat_weight_power);
    w_snow = pow(max(1.0 - rgba.r - rgba.g - rgba.b - rgba.a, 0.0), splat_weight_power);
    float total = w_grass + w_dirt + w_rl + w_rd + w_snow;
    if (total < 1e-5) {
        w_grass = 1.0; w_dirt = 0.0; w_rl = 0.0; w_rd = 0.0; w_snow = 0.0;
    } else {
        w_grass /= total; w_dirt /= total; w_rl /= total;
        w_rd /= total; w_snow /= total;
    }
}

void apply_sample(LayerSample s, float w,
                  inout vec3 acc_albedo, inout vec3 acc_normal,
                  inout float acc_rough, inout float acc_ao,
                  inout float wsum) {
    acc_albedo += s.albedo * w;
    acc_normal += s.normal * w;
    acc_rough += s.rough * w;
    acc_ao += s.ao * w;
    wsum += w;
}

void fragment() {
    vec3 wp = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
    vec3 wn = normalize((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz);

    vec2 uv_x = wp.zy * world_uv_scale;
    vec2 uv_y = wp.xz * world_uv_scale;
    vec2 uv_z = wp.xy * world_uv_scale;
    vec2 duv_x = uv_x * detail_uv_scale_mult;
    vec2 duv_y = uv_y * detail_uv_scale_mult;
    vec2 duv_z = uv_z * detail_uv_scale_mult;
    vec3 tri_w = triplanar_weights(wn);

    float h_norm = clamp((wp.y - elev_min_m) / max(elev_range_m, 1e-3), 0.0, 1.0);
    float slope = 1.0 - clamp(wn.y, 0.0, 1.0);

    float w_grass, w_dirt, w_rl, w_rd, w_snow;
    if (use_splat_weights) {
        splat_layer_weights(UV, w_grass, w_dirt, w_rl, w_rd, w_snow);
    } else {
        height_slope_weights(h_norm, slope, w_grass, w_dirt, w_rl, w_rd, w_snow);
    }

    const float WEIGHT_EPS = 1e-4;
    vec3 acc_albedo = vec3(0.0);
    vec3 acc_normal = vec3(0.0);
    float acc_rough = 0.0;
    float acc_ao = 0.0;
    float wsum = 0.0;

    if (w_grass > WEIGHT_EPS) {
        apply_sample(sample_layer(grass_albedo, grass_normal, grass_rough, grass_ao,
                                  uv_x, uv_y, uv_z, tri_w, wn), w_grass,
                     acc_albedo, acc_normal, acc_rough, acc_ao, wsum);
    }
    if (w_dirt > WEIGHT_EPS) {
        apply_sample(sample_layer(dirt_albedo, dirt_normal, dirt_rough, dirt_ao,
                                  uv_x, uv_y, uv_z, tri_w, wn), w_dirt,
                     acc_albedo, acc_normal, acc_rough, acc_ao, wsum);
    }
    if (w_rl > WEIGHT_EPS) {
        apply_sample(sample_layer(rock_light_albedo, rock_light_normal, rock_light_rough, rock_light_ao,
                                  uv_x, uv_y, uv_z, tri_w, wn), w_rl,
                     acc_albedo, acc_normal, acc_rough, acc_ao, wsum);
    }
    if (w_rd > WEIGHT_EPS) {
        apply_sample(sample_layer(rock_dark_albedo, rock_dark_normal, rock_dark_rough, rock_dark_ao,
                                  uv_x, uv_y, uv_z, tri_w, wn), w_rd,
                     acc_albedo, acc_normal, acc_rough, acc_ao, wsum);
    }
    if (w_snow > WEIGHT_EPS) {
        apply_sample(sample_layer(snow_albedo, snow_normal, snow_rough, snow_ao,
                                  uv_x, uv_y, uv_z, tri_w, wn), w_snow,
                     acc_albedo, acc_normal, acc_rough, acc_ao, wsum);
    }

    if (wsum < 1e-4) {
        apply_sample(sample_layer(rock_dark_albedo, rock_dark_normal, rock_dark_rough, rock_dark_ao,
                                  uv_x, uv_y, uv_z, tri_w, wn), 1.0,
                     acc_albedo, acc_normal, acc_rough, acc_ao, wsum);
    }

    vec3 macro_albedo = acc_albedo / wsum;
    vec3 macro_normal = normalize(acc_normal);
    float macro_rough = acc_rough / wsum;
    float ao = acc_ao / wsum;

    if (macro_value_strength > 0.001 || macro_hue_strength > 0.001) {
        float scale = 1.0 / max(macro_scale, 0.01);
        float n = macro_noise(wp * scale);
        float n_signed = n * 2.0 - 1.0;
        macro_albedo *= 1.0 + n_signed * macro_value_strength;
        if (macro_hue_strength > 0.001) {
            float n_r = macro_noise(wp * scale + vec3(11.3, 0.0, 0.0));
            float n_b = macro_noise(wp * scale + vec3(0.0, 0.0, 17.7));
            macro_albedo.r *= 1.0 + (n_r * 2.0 - 1.0) * macro_hue_strength;
            macro_albedo.b *= 1.0 + (n_b * 2.0 - 1.0) * macro_hue_strength;
        }
        macro_albedo = clamp(macro_albedo, vec3(0.0), vec3(1.0));
    }

    vec3 final_albedo = macro_albedo;
    vec3 final_normal = macro_normal;
    float final_rough = macro_rough;

    float view_dist = length(VIEW);
    float fade = 1.0 - smoothstep(detail_fade_start_m, detail_fade_end_m, view_dist);
    if (fade > 0.001 && (detail_albedo_strength > 0.001 || detail_normal_strength > 0.001 || detail_rough_strength > 0.001)) {
        vec3 detail_albedo = vec3(0.0);
        vec3 detail_normal = vec3(0.0);
        float detail_rough = 0.0;
        float detail_wsum = 0.0;
        float ignored_ao = 0.0;

        if (w_grass > WEIGHT_EPS) {
            apply_sample(sample_detail_layer(grass_detail_albedo, grass_detail_normal, grass_detail_rough,
                                             duv_x, duv_y, duv_z, tri_w, wn), w_grass,
                         detail_albedo, detail_normal, detail_rough, ignored_ao, detail_wsum);
        }
        if (w_dirt > WEIGHT_EPS) {
            apply_sample(sample_detail_layer(dirt_detail_albedo, dirt_detail_normal, dirt_detail_rough,
                                             duv_x, duv_y, duv_z, tri_w, wn), w_dirt,
                         detail_albedo, detail_normal, detail_rough, ignored_ao, detail_wsum);
        }
        if (w_rl > WEIGHT_EPS) {
            apply_sample(sample_detail_layer(rock_light_detail_albedo, rock_light_detail_normal, rock_light_detail_rough,
                                             duv_x, duv_y, duv_z, tri_w, wn), w_rl,
                         detail_albedo, detail_normal, detail_rough, ignored_ao, detail_wsum);
        }
        if (w_rd > WEIGHT_EPS) {
            apply_sample(sample_detail_layer(rock_dark_detail_albedo, rock_dark_detail_normal, rock_dark_detail_rough,
                                             duv_x, duv_y, duv_z, tri_w, wn), w_rd,
                         detail_albedo, detail_normal, detail_rough, ignored_ao, detail_wsum);
        }
        if (w_snow > WEIGHT_EPS) {
            apply_sample(sample_detail_layer(snow_detail_albedo, snow_detail_normal, snow_detail_rough,
                                             duv_x, duv_y, duv_z, tri_w, wn), w_snow,
                         detail_albedo, detail_normal, detail_rough, ignored_ao, detail_wsum);
        }

        if (detail_wsum > 1e-4) {
            detail_albedo /= detail_wsum;
            detail_normal = normalize(detail_normal);
            detail_rough /= detail_wsum;
            final_albedo = soft_light(macro_albedo, detail_albedo, detail_albedo_strength * fade);
            final_normal = blend_normal_world(wp, wn, macro_normal, detail_normal, detail_normal_strength * fade);
            final_rough = mix(macro_rough, mix(macro_rough, detail_rough, 0.5), detail_rough_strength * fade);
        }
    }

    final_rough = mix(0.5, final_rough, roughness_strength);

    ALBEDO = final_albedo;
    NORMAL = normalize((VIEW_MATRIX * vec4(final_normal, 0.0)).xyz);
    ROUGHNESS = clamp(final_rough, 0.04, 1.0);
    METALLIC = 0.0;
    AO = clamp(ao, 0.0, 1.0);
}
