// Slope + height multi-texture blend.
//
// Builds on terrain_hex.gdshader (hex-tile + macro variation). Adds a
// blend across 5 PBR sets selected by world-Y height (normalized) and
// surface slope (1 - dot(N, UP)).
//
// Layer rules (default, tunable):
//
//          slope ~0 (flat)              slope ~1 (steep)
//   y=0  ─ grass                ─       grass                   ─
//        │                       │                              │
//   y=0.25  dirt                  │      rock_light              │
//        │                       │                              │
//   y=0.6   rock_dark             │      rock_light              │
//        │                       │                              │
//   y=0.85  snow                  │      rock_light              │
//   y=1                           │                              │
//
// Slope wins above slope_threshold — bare rock_light shows through any
// height. Below, height drives the choice (grass low → dirt → rock_dark
// → snow high).
//
// Blends are smoothstep-windowed so transitions are continuous. Each
// layer's weight is computed once; layers with weight ~0 skip their
// texture sample entirely (early-out branch).
//
// Cost: at most 5 hex-triplanar samples per fragment. Practically much
// less because most fragments only have 1-2 non-zero layer weights.

shader_type spatial;
render_mode cull_back, depth_draw_opaque, specular_schlick_ggx;

// Per-layer PBR sets. ao is shared (cheap; AO is approximate anyway).
uniform sampler2D grass_albedo : source_color;
uniform sampler2D grass_normal : hint_normal;
uniform sampler2D grass_rough;

uniform sampler2D dirt_albedo : source_color;
uniform sampler2D dirt_normal : hint_normal;
uniform sampler2D dirt_rough;

uniform sampler2D rock_light_albedo : source_color;
uniform sampler2D rock_light_normal : hint_normal;
uniform sampler2D rock_light_rough;

uniform sampler2D rock_dark_albedo : source_color;
uniform sampler2D rock_dark_normal : hint_normal;
uniform sampler2D rock_dark_rough;

uniform sampler2D snow_albedo : source_color;
uniform sampler2D snow_normal : hint_normal;
uniform sampler2D snow_rough;

// Shared
uniform float world_uv_scale = 0.1;
uniform float hex_strength : hint_range(0.0, 1.0) = 1.0;
uniform float blend_sharpness : hint_range(1.0, 32.0) = 8.0;
uniform float normal_strength : hint_range(0.0, 2.0) = 1.0;

// Macro variation
uniform float macro_scale = 80.0;
uniform float macro_value_strength : hint_range(0.0, 1.0) = 0.15;

// Height + slope blend rules.
// `height_norm` = (world_y - elev_min) / elev_range, clamped 0..1.
// Set elev_min and elev_range from meta.json's elevation_min_m / elevation_range_m.
uniform float elev_min_m = 0.0;
uniform float elev_range_m = 1.0;

// Slope threshold: above this, rock_light dominates regardless of height.
// slope = 1 - max(N.y, 0)  ranges 0 (flat ground) to 1 (vertical cliff).
uniform float slope_threshold : hint_range(0.0, 1.0) = 0.45;
uniform float slope_softness : hint_range(0.0, 0.5) = 0.15;

// Height-band breakpoints. Values are in normalized height [0..1].
uniform float h_grass_dirt : hint_range(0.0, 1.0) = 0.20;
uniform float h_dirt_rockdark : hint_range(0.0, 1.0) = 0.55;
uniform float h_rockdark_snow : hint_range(0.0, 1.0) = 0.85;
uniform float h_band_softness : hint_range(0.01, 0.3) = 0.08;

// ---- helpers (hash, noise, hex-tile — same as terrain_hex) -----------

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

// ---- per-layer hex-triplanar sample ----------------------------------

struct LayerSample {
    vec3 albedo;
    vec3 normal;
    float rough;
};

LayerSample sample_layer(sampler2D albedo_tex, sampler2D normal_tex,
                          sampler2D rough_tex,
                          vec2 uv_x, vec2 uv_y, vec2 uv_z, vec3 weights, vec3 wn) {
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
    return s;
}

// ---- weight computation ---------------------------------------------

// Returns weights for {grass, dirt, rock_light, rock_dark, snow}, summing to 1.
void layer_weights(float h, float slope,
                    out float w_grass, out float w_dirt,
                    out float w_rl, out float w_rd, out float w_snow) {
    // Slope weight (rock_light wins when slope > threshold).
    float w_slope = smoothstep(slope_threshold - slope_softness,
                                slope_threshold + slope_softness, slope);

    // Height bands (mutually exclusive in the limit; smoothed at boundaries).
    // band_grass     = 1 below h_grass_dirt, fading out
    // band_dirt      = peak between h_grass_dirt and h_dirt_rockdark
    // band_rockdark  = peak between h_dirt_rockdark and h_rockdark_snow
    // band_snow      = 1 above h_rockdark_snow
    float gd = h_band_softness;
    float band_grass    = 1.0 - smoothstep(h_grass_dirt - gd, h_grass_dirt + gd, h);
    float band_snow     = smoothstep(h_rockdark_snow - gd, h_rockdark_snow + gd, h);
    float low_dirt  = smoothstep(h_grass_dirt - gd, h_grass_dirt + gd, h);
    float high_dirt = 1.0 - smoothstep(h_dirt_rockdark - gd, h_dirt_rockdark + gd, h);
    float band_dirt = low_dirt * high_dirt;
    float low_rd  = smoothstep(h_dirt_rockdark - gd, h_dirt_rockdark + gd, h);
    float high_rd = 1.0 - smoothstep(h_rockdark_snow - gd, h_rockdark_snow + gd, h);
    float band_rockdark = low_rd * high_rd;

    // Slope steals weight from the height-driven bands and gives it to rock_light.
    float keep = 1.0 - w_slope;
    w_grass = band_grass * keep;
    w_dirt  = band_dirt  * keep;
    w_rd    = band_rockdark * keep;
    w_snow  = band_snow  * keep;
    w_rl    = w_slope;

    // Normalize defensively (smoothsteps can underrun by a percent).
    float total = w_grass + w_dirt + w_rl + w_rd + w_snow + 1e-6;
    w_grass /= total; w_dirt /= total; w_rl /= total;
    w_rd /= total; w_snow /= total;
}

// ---- fragment ---------------------------------------------------------

void fragment() {
    vec3 wp = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
    vec3 wn = normalize((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz);

    // Triplanar UVs and weights (shared across all layers — same surface).
    vec2 uv_x = wp.zy * world_uv_scale;
    vec2 uv_y = wp.xz * world_uv_scale;
    vec2 uv_z = wp.xy * world_uv_scale;
    vec3 weights = triplanar_weights(wn);

    // Height (normalized) and slope.
    float h_norm = clamp((wp.y - elev_min_m) / max(elev_range_m, 1e-3), 0.0, 1.0);
    float slope = 1.0 - clamp(wn.y, 0.0, 1.0);

    float w_grass, w_dirt, w_rl, w_rd, w_snow;
    layer_weights(h_norm, slope, w_grass, w_dirt, w_rl, w_rd, w_snow);

    // Accumulator
    vec3 acc_albedo = vec3(0.0);
    vec3 acc_normal = vec3(0.0);
    float acc_rough = 0.0;
    float wsum = 0.0;

    // Each layer: skip near-zero weights to save GPU. Threshold is 1e-4 —
    // post-normalization weights summing to 1 across 5 layers means at
    // least one weight is >= 0.2, so this is purely an optimization.
    // Safe default fallback (rock_dark) below catches any pathological case.
    const float WEIGHT_EPS = 1e-4;
    if (w_grass > WEIGHT_EPS) {
        LayerSample s = sample_layer(grass_albedo, grass_normal, grass_rough,
                                      uv_x, uv_y, uv_z, weights, wn);
        acc_albedo += s.albedo * w_grass;
        acc_normal += s.normal * w_grass;
        acc_rough  += s.rough  * w_grass;
        wsum += w_grass;
    }
    if (w_dirt > WEIGHT_EPS) {
        LayerSample s = sample_layer(dirt_albedo, dirt_normal, dirt_rough,
                                      uv_x, uv_y, uv_z, weights, wn);
        acc_albedo += s.albedo * w_dirt;
        acc_normal += s.normal * w_dirt;
        acc_rough  += s.rough  * w_dirt;
        wsum += w_dirt;
    }
    if (w_rl > WEIGHT_EPS) {
        LayerSample s = sample_layer(rock_light_albedo, rock_light_normal, rock_light_rough,
                                      uv_x, uv_y, uv_z, weights, wn);
        acc_albedo += s.albedo * w_rl;
        acc_normal += s.normal * w_rl;
        acc_rough  += s.rough  * w_rl;
        wsum += w_rl;
    }
    if (w_rd > WEIGHT_EPS) {
        LayerSample s = sample_layer(rock_dark_albedo, rock_dark_normal, rock_dark_rough,
                                      uv_x, uv_y, uv_z, weights, wn);
        acc_albedo += s.albedo * w_rd;
        acc_normal += s.normal * w_rd;
        acc_rough  += s.rough  * w_rd;
        wsum += w_rd;
    }
    if (w_snow > WEIGHT_EPS) {
        LayerSample s = sample_layer(snow_albedo, snow_normal, snow_rough,
                                      uv_x, uv_y, uv_z, weights, wn);
        acc_albedo += s.albedo * w_snow;
        acc_normal += s.normal * w_snow;
        acc_rough  += s.rough  * w_snow;
        wsum += w_snow;
    }

    // If the weighted sum is somehow near-zero (would render black), fall
    // back to a guaranteed sample of rock_dark so we never produce a black
    // hole at layer-transition pixels. Costs at most one extra sample per
    // pathological pixel, zero cost otherwise.
    vec3 final_albedo;
    vec3 final_normal;
    float final_rough;
    if (wsum < 1e-4) {
        LayerSample fb = sample_layer(rock_dark_albedo, rock_dark_normal, rock_dark_rough,
                                       uv_x, uv_y, uv_z, weights, wn);
        final_albedo = fb.albedo;
        final_normal = fb.normal;
        final_rough  = fb.rough;
    } else {
        final_albedo = acc_albedo / wsum;
        final_normal = normalize(acc_normal);
        final_rough  = acc_rough / wsum;
    }

    // Macro variation (same as terrain_hex).
    if (macro_value_strength > 0.001) {
        float scale = 1.0 / max(macro_scale, 0.01);
        float n_signed = macro_noise(wp * scale) * 2.0 - 1.0;
        final_albedo *= 1.0 + n_signed * macro_value_strength;
        final_albedo = clamp(final_albedo, vec3(0.0), vec3(1.0));
    }

    ALBEDO = final_albedo;
    NORMAL = normalize((VIEW_MATRIX * vec4(final_normal, 0.0)).xyz);
    ROUGHNESS = clamp(final_rough, 0.04, 1.0);
    METALLIC = 0.0;
    AO = 1.0;  // skipping per-layer AO for now; can add later
}
