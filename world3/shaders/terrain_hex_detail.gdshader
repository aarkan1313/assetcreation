// Hex-tile triplanar with macro+detail layering.
//
// Builds on terrain_hex.gdshader (which already has hex-tile and macro
// variation). This adds a *second* sample of the same PBR set at a
// different (smaller) UV period, blended on top to add high-frequency
// surface character that mip-fades to nothing at distance.
//
// Why this matters even though hex-tile already kills repetition:
//
//   Hex-tile breaks the visible period of one sample. But the texture
//   itself still has a single dominant scale: if it was authored at
//   "10m repeat" you can't see anything finer than ~1cm (1/512 of 10m
//   at 512 res), and you can't see anything coarser than 10m. Macro
//   variation noise adds coarse — this adds fine.
//
//   Sampled at 8x finer UV (1.25m repeat), the same texture supplies
//   "what would the surface look like up close" detail without any
//   new asset. At distance the detail mip-fades to grey and the macro
//   sample dominates. Up close it adds crispness.
//
//   For surfaces that need real distinct fine geometry (e.g. cobble
//   pavement where the seams matter), authored detail textures plug
//   into the same uniforms — just bind a different albedo/normal to
//   detail_*_tex.
//
// Reference: Reoriented Normal Mapping (Barré-Brisebois & Hill, GDC
// 2012) for the normal blend. Soft-light for the albedo blend (preserves
// macro tone). Distance fade pattern from
// art_lab/shaders/templates/macro_detail_v1.gdshader.
//
// Cost: ~doubles the per-pixel sample count vs. terrain_hex. With
// hex-tile (3 taps) on each of 4 maps × 3 triplanar projections × 2
// scales = 72 samples per fragment. Fine for terrain on a modern GPU.
//
// Uniforms (in addition to terrain_hex):
//   detail_albedo_tex / detail_normal_tex / detail_rough_tex / detail_ao_tex
//     — by default these can be the same as macro; bind different ones for
//       authored detail
//   detail_uv_scale_mult — multiplier on world_uv_scale for the detail
//                          sample. 8 means detail tiles 8x more often.
//   detail_*_strength    — per-channel blend strength
//   detail_fade_start_m  — camera distance where detail starts fading
//   detail_fade_end_m    — camera distance where detail is fully faded

shader_type spatial;
render_mode cull_back, depth_draw_opaque, specular_schlick_ggx;

// Macro PBR set
uniform sampler2D albedo_tex : source_color;
uniform sampler2D normal_tex : hint_normal;
uniform sampler2D rough_tex;
uniform sampler2D ao_tex : hint_default_white;

// Detail PBR set. Default usage: bind the same textures as macro.
uniform sampler2D detail_albedo_tex : source_color;
uniform sampler2D detail_normal_tex : hint_normal;
uniform sampler2D detail_rough_tex;

uniform float world_uv_scale = 0.1;
uniform float hex_strength : hint_range(0.0, 1.0) = 1.0;
uniform float blend_sharpness : hint_range(1.0, 32.0) = 8.0;
uniform float roughness_strength : hint_range(0.0, 1.0) = 1.0;
uniform float normal_strength : hint_range(0.0, 2.0) = 1.0;

// Macro variation (low-freq tint over the whole surface)
uniform float macro_scale = 80.0;
uniform float macro_value_strength : hint_range(0.0, 1.0) = 0.15;
uniform float macro_hue_strength : hint_range(0.0, 0.3) = 0.03;

// Macro+detail layering
uniform float detail_uv_scale_mult : hint_range(2.0, 32.0) = 8.0;
uniform float detail_albedo_strength : hint_range(0.0, 1.0) = 0.5;
uniform float detail_normal_strength : hint_range(0.0, 1.0) = 0.6;
uniform float detail_rough_strength : hint_range(0.0, 1.0) = 0.4;
uniform float detail_fade_start_m = 8.0;
uniform float detail_fade_end_m = 30.0;

// ---- helpers (same as terrain_hex) -----------------------------------

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
        c0 = ip + vec2(0.0, 0.0);
        c1 = ip + vec2(1.0, 0.0);
        c2 = ip + vec2(0.0, 1.0);
        w0 = 1.0 - fp.x - fp.y; w1 = fp.x; w2 = fp.y;
    } else {
        c0 = ip + vec2(1.0, 0.0);
        c1 = ip + vec2(0.0, 1.0);
        c2 = ip + vec2(1.0, 1.0);
        w0 = 1.0 - fp.y; w1 = 1.0 - fp.x; w2 = fp.x + fp.y - 1.0;
    }
}

vec4 sample_jittered(sampler2D tex, vec2 uv, vec2 cell) {
    vec2 jitter = hash22(cell) * 0.5;
    float rot = hash21(cell + 17.31) * 6.2831853;
    float c = cos(rot);
    float s = sin(rot);
    mat2 R = mat2(vec2(c, -s), vec2(s, c));
    vec2 sampled_uv = R * uv + jitter;
    return texture(tex, sampled_uv);
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

// ---- macro+detail blend helpers --------------------------------------

// Soft-light blend (photoshop). Preserves base tone while adding
// detail's lights/shadows. `strength` blends the result back to base.
vec3 soft_light(vec3 base, vec3 blend, float strength) {
    vec3 result = mix(
        base * (2.0 * blend),
        1.0 - 2.0 * (1.0 - base) * (1.0 - blend),
        step(0.5, blend)
    );
    return mix(base, result, strength);
}

// Reoriented Normal Mapping (Barré-Brisebois & Hill, GDC 2012). Requires
// tangent-space inputs where the surface normal is +Z.
//
// We have world-space normals here (post-triplanar). The simple version
// of "blend two world-space normals" was a normalized mix — correct on
// all orientations but visually flatter than real RNM.
//
// The right fix: build a tangent frame on the surface from screen-space
// derivatives of world position, project both normals into it, run RNM,
// project the result back. ~5 instructions over the simple mix.
//
// reorient_normal_tangent: pure tangent-space RNM (use after projecting in).
vec3 reorient_normal_tangent(vec3 t, vec3 u) {
    t.z += 1.0;
    u.xy *= -1.0;
    return normalize(t * dot(t, u) - u * t.z);
}

// blend_normal_world: blend two world-space normals via tangent-frame
// RNM. world_pos and world_n are the surface position/normal at this
// fragment; macro_n and detail_n are both world-space normalized
// vectors that have already been triplanar-blended onto wn.
//
// Construction of the tangent frame: dFdx/dFdy of world_pos give two
// screen-aligned tangent vectors on the surface. We orthonormalize to
// world_n: T is the dFdx component perpendicular to world_n, B is
// world_n × T. The matrix [T, B, world_n] is an orthonormal tangent
// basis where +Z is the surface up — exactly what RNM expects.
vec3 blend_normal_world(vec3 world_pos, vec3 world_n,
                         vec3 macro_n, vec3 detail_n, float strength) {
    if (strength <= 0.001) return world_n;
    vec3 dpdx = dFdx(world_pos);
    vec3 dpdy = dFdy(world_pos);
    vec3 T = normalize(dpdx - world_n * dot(dpdx, world_n));
    // Guard against degenerate dpdx (zero-area triangle, screen-aligned).
    if (length(dpdx) < 1e-6) {
        // Pick an arbitrary tangent: cross with world axis least parallel.
        vec3 helper = abs(world_n.y) < 0.9 ? vec3(0, 1, 0) : vec3(1, 0, 0);
        T = normalize(cross(helper, world_n));
    }
    vec3 B = normalize(cross(world_n, T));
    mat3 tbn = mat3(T, B, world_n);
    mat3 tbn_inv = transpose(tbn);  // orthonormal so inverse = transpose

    vec3 macro_t  = tbn_inv * macro_n;
    vec3 detail_t = tbn_inv * detail_n;
    vec3 blended_t = reorient_normal_tangent(macro_t, detail_t);
    vec3 blended_w = tbn * blended_t;
    return normalize(mix(world_n, blended_w, clamp(strength, 0.0, 1.0)));
}

// Sample a normal map through hex-tile, return decoded ±1 vector.
vec3 hex_sample_normal(sampler2D tex, vec2 uv) {
    return maybe_hex_rgb(tex, uv) * 2.0 - 1.0;
}

// ---- fragment ---------------------------------------------------------

void fragment() {
    vec3 wp = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
    vec3 wn = normalize((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz);

    // Triplanar UVs at macro scale
    vec2 uv_x = wp.zy * world_uv_scale;
    vec2 uv_y = wp.xz * world_uv_scale;
    vec2 uv_z = wp.xy * world_uv_scale;

    // And at detail scale (just multiplied in UV space)
    vec2 duv_x = uv_x * detail_uv_scale_mult;
    vec2 duv_y = uv_y * detail_uv_scale_mult;
    vec2 duv_z = uv_z * detail_uv_scale_mult;

    vec3 weights = triplanar_weights(wn);

    // Distance fade for the detail layer.
    float view_dist = length(VIEW);  // VIEW points camera->fragment in view space
    float fade = 1.0 - smoothstep(detail_fade_start_m, detail_fade_end_m, view_dist);

    // ---- Macro samples (each through hex-tile) ----
    vec3 a_x = maybe_hex_albedo(albedo_tex, uv_x);
    vec3 a_y = maybe_hex_albedo(albedo_tex, uv_y);
    vec3 a_z = maybe_hex_albedo(albedo_tex, uv_z);
    vec3 macro_albedo = a_x * weights.x + a_y * weights.y + a_z * weights.z;

    vec3 nx = hex_sample_normal(normal_tex, uv_x);
    vec3 ny = hex_sample_normal(normal_tex, uv_y);
    vec3 nz = hex_sample_normal(normal_tex, uv_z);
    nx.xy *= normal_strength; ny.xy *= normal_strength; nz.xy *= normal_strength;
    vec3 macro_normal = normalize(
        vec3(0.0, nx.y, nx.x) * weights.x +
        vec3(ny.x, 0.0, ny.y) * weights.y +
        vec3(nz.x, nz.y, 0.0) * weights.z +
        wn
    );

    float r_x = maybe_hex_r(rough_tex, uv_x);
    float r_y = maybe_hex_r(rough_tex, uv_y);
    float r_z = maybe_hex_r(rough_tex, uv_z);
    float macro_rough = r_x * weights.x + r_y * weights.y + r_z * weights.z;

    float ao_x = maybe_hex_r(ao_tex, uv_x);
    float ao_y = maybe_hex_r(ao_tex, uv_y);
    float ao_z = maybe_hex_r(ao_tex, uv_z);
    float ao = ao_x * weights.x + ao_y * weights.y + ao_z * weights.z;

    // ---- Macro variation (post-macro-sample, pre-detail) ----
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

    // ---- Detail samples (only if fade > 0; skip otherwise to save GPU) ----
    vec3 final_albedo = macro_albedo;
    vec3 final_normal = macro_normal;
    float final_rough = macro_rough;

    if (fade > 0.001) {
        // Detail albedo
        vec3 da_x = maybe_hex_albedo(detail_albedo_tex, duv_x);
        vec3 da_y = maybe_hex_albedo(detail_albedo_tex, duv_y);
        vec3 da_z = maybe_hex_albedo(detail_albedo_tex, duv_z);
        vec3 detail_albedo = da_x * weights.x + da_y * weights.y + da_z * weights.z;

        // Detail normal
        vec3 dnx = hex_sample_normal(detail_normal_tex, duv_x);
        vec3 dny = hex_sample_normal(detail_normal_tex, duv_y);
        vec3 dnz = hex_sample_normal(detail_normal_tex, duv_z);
        vec3 detail_normal = normalize(
            vec3(0.0, dnx.y, dnx.x) * weights.x +
            vec3(dny.x, 0.0, dny.y) * weights.y +
            vec3(dnz.x, dnz.y, 0.0) * weights.z +
            wn
        );

        // Detail roughness
        float dr_x = maybe_hex_r(detail_rough_tex, duv_x);
        float dr_y = maybe_hex_r(detail_rough_tex, duv_y);
        float dr_z = maybe_hex_r(detail_rough_tex, duv_z);
        float detail_rough = dr_x * weights.x + dr_y * weights.y + dr_z * weights.z;

        // Blend, scaled by both the per-channel strength and the distance fade.
        final_albedo = soft_light(macro_albedo, detail_albedo,
                                   detail_albedo_strength * fade);
        // Tangent-frame RNM blend (see blend_normal_world docstring).
        final_normal = blend_normal_world(wp, wn, macro_normal, detail_normal,
                                           detail_normal_strength * fade);
        final_rough = mix(macro_rough,
                          mix(macro_rough, detail_rough, 0.5),
                          detail_rough_strength * fade);
    }

    final_rough = mix(0.5, final_rough, roughness_strength);

    ALBEDO = final_albedo;
    NORMAL = normalize((VIEW_MATRIX * vec4(final_normal, 0.0)).xyz);
    ROUGHNESS = clamp(final_rough, 0.04, 1.0);
    METALLIC = 0.0;
    AO = ao;
}
