// Hex-tile sampled triplanar terrain material.
//
// Standard triplanar with one trick added: instead of sampling the
// texture once at world UV, sample it three times at hex-grid-jittered
// offsets and blend. The hex grid means any pixel falls inside a
// triangle of three hex centers; we sample at each center with a small
// random rotation and offset, then blend by barycentric weights.
//
// Net effect: the visible "tile period" of the source texture is broken.
// You can stand a meter away from a 0.5m-period rock texture and not
// see any periodicity, because no two adjacent samples have the same
// rotation+offset.
//
// Reference: Mikkelsen 2022, building on Heitz & Neyret 2018. Cost is
// 3x texture samples per channel — well within budget for terrain.
//
// Uniforms:
//   albedo_tex / normal_tex / rough_tex / ao_tex — the PBR set
//   world_uv_scale — world meters per texture period (smaller = bigger
//                    visible features); 0.1 means one tile per 10m
//   hex_strength   — 0..1; 0=plain triplanar, 1=full hex-tile blending

shader_type spatial;
render_mode cull_back, depth_draw_opaque, specular_schlick_ggx;

uniform sampler2D albedo_tex : source_color;
uniform sampler2D normal_tex : hint_normal;
uniform sampler2D rough_tex;
uniform sampler2D ao_tex : hint_default_white;

uniform float world_uv_scale = 0.1;            // 1 / meters per texture period
uniform float hex_strength : hint_range(0.0, 1.0) = 1.0;
uniform float blend_sharpness : hint_range(1.0, 32.0) = 8.0;  // triplanar blend exponent
uniform float roughness_strength : hint_range(0.0, 1.0) = 1.0;
uniform float normal_strength : hint_range(0.0, 2.0) = 1.0;

// Macro variation: low-frequency multiplicative tint over the entire
// surface. Breaks the "everything is one shade" look when viewed from
// far away. macro_scale is in world meters per noise period; bigger =
// gentler, slower variation.
uniform float macro_scale = 30.0;       // meters per noise period
uniform float macro_value_strength : hint_range(0.0, 1.0) = 0.35;  // brightness wobble
uniform float macro_hue_strength : hint_range(0.0, 0.3) = 0.05;    // hue wobble

// ---- helpers ----------------------------------------------------------

// 2D hash for jitter; deterministic per integer cell.
vec2 hash22(vec2 p) {
    p = vec2(dot(p, vec2(127.1, 311.7)),
             dot(p, vec2(269.5, 183.3)));
    return fract(sin(p) * 43758.5453) * 2.0 - 1.0;
}

float hash21(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

// 3D value noise. Returns 0..1.
float hash31(vec3 p) {
    p = fract(p * vec3(443.897, 441.423, 437.195));
    p += dot(p, p.yzx + 19.19);
    return fract((p.x + p.y) * p.z);
}

float value_noise_3d(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);  // smoothstep
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

// 2-octave noise — adds slight medium-frequency variation on top of
// the low-frequency macro envelope. Cheap (only 2 samples).
float macro_noise(vec3 p) {
    float n = value_noise_3d(p);
    n += value_noise_3d(p * 2.13 + vec3(13.7, 7.4, 21.9)) * 0.5;
    return n / 1.5;
}

// Hex-grid coordinate. For a UV, returns the three nearest hex-cell
// centers and barycentric weights. This is the standard "triangle grid
// across hex tiling" decomposition.
//
// Output is three (cell_id, weight) pairs packed as: cells[0..2] is the
// 2D integer cell coord, weights[0..2] sum to 1.
void hex_weights(vec2 uv, out vec2 c0, out vec2 c1, out vec2 c2,
                 out float w0, out float w1, out float w2) {
    // Skewed-grid lattice: maps hex centers onto integer points.
    // GRID_TO_SKEW = mat2((1, 0), (-0.5, 1)) * (2/sqrt(3))
    // = mat2((1.1547, 0), (-0.5774, 1.1547))
    const float K = 1.15470054;  // 2 / sqrt(3)
    mat2 GRID_TO_SKEW = mat2(vec2(K, 0.0), vec2(-K * 0.5, K));
    vec2 skewed = GRID_TO_SKEW * uv;
    vec2 ip = floor(skewed);
    vec2 fp = skewed - ip;

    // Inside a unit square split into two triangles by the diagonal.
    // The three vertices are the cell corners.
    if (fp.x + fp.y < 1.0) {
        c0 = ip + vec2(0.0, 0.0);
        c1 = ip + vec2(1.0, 0.0);
        c2 = ip + vec2(0.0, 1.0);
        w0 = 1.0 - fp.x - fp.y;
        w1 = fp.x;
        w2 = fp.y;
    } else {
        c0 = ip + vec2(1.0, 0.0);
        c1 = ip + vec2(0.0, 1.0);
        c2 = ip + vec2(1.0, 1.0);
        w0 = 1.0 - fp.y;
        w1 = 1.0 - fp.x;
        w2 = fp.x + fp.y - 1.0;
    }
}

// Sample a texture at a hex-cell offset: small UV translation + rotation
// based on the cell ID. Each cell gets its own random rotation/offset,
// so adjacent samples don't share the same "look."
vec4 sample_jittered(sampler2D tex, vec2 uv, vec2 cell) {
    vec2 jitter = hash22(cell) * 0.5;            // ±0.5 UV units
    float rot = hash21(cell + 17.31) * 6.2831853;  // 0..2π
    float c = cos(rot);
    float s = sin(rot);
    mat2 R = mat2(vec2(c, -s), vec2(s, c));
    vec2 sampled_uv = R * (uv) + jitter;
    return texture(tex, sampled_uv);
}

// Hex-tile sample: three rotated samples, blended by hex weights.
// Uses Heitz-Neyret variance-preservation for albedo.
vec3 hex_sample_albedo(sampler2D tex, vec2 uv) {
    vec2 c0, c1, c2;
    float w0, w1, w2;
    hex_weights(uv, c0, c1, c2, w0, w1, w2);

    vec3 s0 = sample_jittered(tex, uv, c0).rgb;
    vec3 s1 = sample_jittered(tex, uv, c1).rgb;
    vec3 s2 = sample_jittered(tex, uv, c2).rgb;

    // Variance-preserving blend: subtract the mean, scale weights to
    // preserve variance, then add the mean back. Standard practice
    // from Heitz-Neyret. For PBR albedo this matters less than for
    // contrast-heavy surfaces, but still cheap insurance.
    vec3 mean = (s0 + s1 + s2) / 3.0;
    vec3 d0 = s0 - mean;
    vec3 d1 = s1 - mean;
    vec3 d2 = s2 - mean;
    float ws = sqrt(w0 * w0 + w1 * w1 + w2 * w2);
    vec3 blended = mean + (w0 * d0 + w1 * d1 + w2 * d2) / max(ws, 1e-4);
    return blended;
}

// Single-channel and 3-channel hex samples (for normal/roughness/ao).
// Plain weighted blend, no variance preservation needed.
vec3 hex_sample_rgb(sampler2D tex, vec2 uv) {
    vec2 c0, c1, c2;
    float w0, w1, w2;
    hex_weights(uv, c0, c1, c2, w0, w1, w2);
    vec3 s0 = sample_jittered(tex, uv, c0).rgb;
    vec3 s1 = sample_jittered(tex, uv, c1).rgb;
    vec3 s2 = sample_jittered(tex, uv, c2).rgb;
    return s0 * w0 + s1 * w1 + s2 * w2;
}

float hex_sample_r(sampler2D tex, vec2 uv) {
    vec2 c0, c1, c2;
    float w0, w1, w2;
    hex_weights(uv, c0, c1, c2, w0, w1, w2);
    float s0 = sample_jittered(tex, uv, c0).r;
    float s1 = sample_jittered(tex, uv, c1).r;
    float s2 = sample_jittered(tex, uv, c2).r;
    return s0 * w0 + s1 * w1 + s2 * w2;
}

// Lerp between hex sample and plain sample by hex_strength.
vec3 maybe_hex_albedo(sampler2D tex, vec2 uv) {
    vec3 plain = texture(tex, uv).rgb;
    if (hex_strength <= 0.001) return plain;
    vec3 hex = hex_sample_albedo(tex, uv);
    return mix(plain, hex, hex_strength);
}
vec3 maybe_hex_rgb(sampler2D tex, vec2 uv) {
    vec3 plain = texture(tex, uv).rgb;
    if (hex_strength <= 0.001) return plain;
    return mix(plain, hex_sample_rgb(tex, uv), hex_strength);
}
float maybe_hex_r(sampler2D tex, vec2 uv) {
    float plain = texture(tex, uv).r;
    if (hex_strength <= 0.001) return plain;
    return mix(plain, hex_sample_r(tex, uv), hex_strength);
}

// Triplanar weights from world-space normal.
vec3 triplanar_weights(vec3 n) {
    vec3 w = pow(abs(n), vec3(blend_sharpness));
    return w / (w.x + w.y + w.z + 1e-5);
}

// ---- fragment ---------------------------------------------------------

void fragment() {
    vec3 wp = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
    vec3 wn = normalize((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz);

    vec2 uv_x = wp.zy * world_uv_scale;
    vec2 uv_y = wp.xz * world_uv_scale;
    vec2 uv_z = wp.xy * world_uv_scale;

    vec3 weights = triplanar_weights(wn);

    // Albedo
    vec3 a_x = maybe_hex_albedo(albedo_tex, uv_x);
    vec3 a_y = maybe_hex_albedo(albedo_tex, uv_y);
    vec3 a_z = maybe_hex_albedo(albedo_tex, uv_z);
    vec3 albedo = a_x * weights.x + a_y * weights.y + a_z * weights.z;

    // Macro variation: low-frequency noise modulates brightness + a
    // tiny hue shift. Sample at world position scaled by 1/macro_scale.
    if (macro_value_strength > 0.001 || macro_hue_strength > 0.001) {
        float scale = 1.0 / max(macro_scale, 0.01);
        float n = macro_noise(wp * scale);
        float n_signed = n * 2.0 - 1.0;  // -1..1
        // Brightness wobble: multiplicative
        float brightness = 1.0 + n_signed * macro_value_strength;
        albedo *= brightness;
        // Subtle channel-shift hue wobble: sample two more octaves at
        // different offsets for r/g/b channel-specific tint, then
        // re-mix.
        if (macro_hue_strength > 0.001) {
            float n_r = macro_noise(wp * scale + vec3(11.3, 0.0, 0.0));
            float n_b = macro_noise(wp * scale + vec3(0.0, 0.0, 17.7));
            albedo.r *= 1.0 + (n_r * 2.0 - 1.0) * macro_hue_strength;
            albedo.b *= 1.0 + (n_b * 2.0 - 1.0) * macro_hue_strength;
        }
        albedo = clamp(albedo, vec3(0.0), vec3(1.0));
    }

    // Normal (sampled as RGB, decoded after blend)
    vec3 n_x = maybe_hex_rgb(normal_tex, uv_x) * 2.0 - 1.0;
    vec3 n_y = maybe_hex_rgb(normal_tex, uv_y) * 2.0 - 1.0;
    vec3 n_z = maybe_hex_rgb(normal_tex, uv_z) * 2.0 - 1.0;
    n_x.xy *= normal_strength;
    n_y.xy *= normal_strength;
    n_z.xy *= normal_strength;
    // Whiteout-style triplanar normal blend: tangent-frame-agnostic.
    vec3 n_blend = normalize(
        vec3(0.0, n_x.y, n_x.x) * weights.x +
        vec3(n_y.x, 0.0, n_y.y) * weights.y +
        vec3(n_z.x, n_z.y, 0.0) * weights.z +
        wn
    );

    // Roughness
    float r_x = maybe_hex_r(rough_tex, uv_x);
    float r_y = maybe_hex_r(rough_tex, uv_y);
    float r_z = maybe_hex_r(rough_tex, uv_z);
    float roughness = r_x * weights.x + r_y * weights.y + r_z * weights.z;
    roughness = mix(0.5, roughness, roughness_strength);

    // AO
    float ao_x = maybe_hex_r(ao_tex, uv_x);
    float ao_y = maybe_hex_r(ao_tex, uv_y);
    float ao_z = maybe_hex_r(ao_tex, uv_z);
    float ao = ao_x * weights.x + ao_y * weights.y + ao_z * weights.z;

    ALBEDO = albedo;
    // Convert blended world-space normal back to view space for output.
    NORMAL = normalize((VIEW_MATRIX * vec4(n_blend, 0.0)).xyz);
    ROUGHNESS = clamp(roughness, 0.04, 1.0);
    METALLIC = 0.0;
    AO = ao;
}
