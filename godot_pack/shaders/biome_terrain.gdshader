// Biome terrain shader (Godot 4.5 Forward+).
//
// 4-layer biome blender driven by an RGBA splat. Vertex stage displaces a
// PlaneMesh by a heightmap. Fragment stage blends 4 PBR sets by splat weights.
//
// Projection mode controlled by `triplanar_strength`:
//   0.0 = pure top-down UV (recommended for ARPG iso/topdown camera).
//         Clean tessellation. Tradeoff: textures stretch along near-vertical
//         cliff faces (visible only at iso angle on heightmaps with sharp
//         peaks like mana_crystal).
//   1.0 = slope-aware projection (top-down on flats; smoothly blends to
//         side-projected sample on cliffs). Removes cliff stretch BUT
//         introduces visible swirl artifacts on peaks where horizontal
//         normal flips axis. Useful for first-person scenes; not recommended
//         for top-down.
//
// Future quality knob: Mikkelsen 2022 hex-tiling — replaces all of the above
// with stochastic per-hex offset+rotation sampling, breaking visible texture
// repeats AND eliminating cliff stretch. ~30% perf cost vs. vanilla top-down.
// See WORLDGEN_QUALITY.md "Knob E" for status.
//
// Reads:
//   heightmap                   - heightmap.png (R channel = elevation 0..1)
//   splat                       - biome_splat_rgba.png (R G B A = biome 0..3)
//   albedo_R/G/B/A              - 4 biome albedo PBR maps
//   normal_R/G/B/A              - 4 biome normal maps (DirectX; flipped to GL in unpack)
//   rough_R/G/B/A               - 4 biome roughness maps (R channel)

shader_type spatial;
render_mode cull_back, depth_draw_opaque;

uniform sampler2D heightmap : hint_default_white;
uniform sampler2D splat     : hint_default_black;

uniform sampler2D albedo_R : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D albedo_G : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D albedo_B : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D albedo_A : source_color, filter_linear_mipmap, repeat_enable;

uniform sampler2D normal_R : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D normal_G : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D normal_B : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D normal_A : hint_normal, filter_linear_mipmap, repeat_enable;

uniform sampler2D rough_R : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D rough_G : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D rough_B : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D rough_A : hint_default_white, filter_linear_mipmap, repeat_enable;

uniform float terrain_size_m  : hint_range(16.0, 4096.0) = 512.0;
uniform float terrain_height_m: hint_range(1.0, 512.0) = 64.0;

// per-biome tiling (meters). R G B A in splat order.
uniform vec4  tile_meters = vec4(4.0, 4.0, 4.0, 3.0);

// 0 = pure top-down UV (cheap, stretches on cliffs)
// 1 = pure triplanar (cliffs read correctly, slightly more expensive)
uniform float triplanar_strength : hint_range(0.0, 1.0) = 1.0;
// blend exponent — higher = sharper transition between projections
uniform float triplanar_sharpness : hint_range(1.0, 16.0) = 4.0;

uniform float metallic_const : hint_range(0.0, 1.0) = 0.0;

// Fallback color for "no biome assigned" pixels (e.g. ocean / sea level cutoff
// where the splat is zero). Without this, valleys read as pitch black.
uniform vec3  ocean_color : source_color = vec3(0.05, 0.10, 0.16);
uniform float ocean_roughness : hint_range(0.0, 1.0) = 0.4;

varying vec3 v_world;
varying vec3 v_world_normal;
varying vec2 v_uv;

void vertex() {
    v_uv = UV;
    float h = texture(heightmap, UV).r;
    VERTEX.y += h * terrain_height_m;

    // Approximate the displaced normal by sampling 4 neighbours of the heightmap
    // (cheap analytic gradient — good enough for triplanar weight selection).
    float texel = 1.0 / float(textureSize(heightmap, 0).x);
    float hL = texture(heightmap, UV + vec2(-texel, 0.0)).r;
    float hR = texture(heightmap, UV + vec2( texel, 0.0)).r;
    float hD = texture(heightmap, UV + vec2(0.0, -texel)).r;
    float hU = texture(heightmap, UV + vec2(0.0,  texel)).r;
    // per-texel world step in X/Z
    float step_m = terrain_size_m * texel;
    vec3 nrm = normalize(vec3(
        (hL - hR) * terrain_height_m,
        2.0 * step_m,
        (hD - hU) * terrain_height_m));
    NORMAL = nrm;

    v_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    v_world_normal = normalize((MODEL_MATRIX * vec4(nrm, 0.0)).xyz);
}

vec3 unpack_normal(vec4 n_sample) {
    vec3 n = n_sample.xyz * 2.0 - 1.0;
    n.y = -n.y;
    return normalize(n);
}

// ---- Slope-aware projection (top-down + cliff-axis blend) ----------------
// For top-down terrains where world Y is always "up", a true triplanar/biplanar
// is overkill (and produces visible artifacts: stripes from full triplanar,
// or swirly axis-flips from biplanar's max-of-XZ tiebreaker).
//
// What we do instead:
//   - Always sample with top-down UV (XZ world position).
//   - On near-vertical surfaces (slope > slope_blend_lo), additionally sample
//     a side-projected UV using whichever of X or Z dominates the horizontal
//     normal component, and blend in via smoothstep(slope_blend_lo, hi, slope).
//   - This is what Far Cry 5 / Unity-cliff-shader / Unreal Landscape do for
//     ARPG/iso top-down terrain.
//
// The function names are kept (triplanar_color etc.) so the rest of the
// shader doesn't change. triplanar_strength still controls the global mix
// (0 = pure top-down, 1 = full slope-aware).

// Cliff blend factor: 0 on flat, 1 on near-vertical. Smoothstep gates so
// 90%+ of "ground" pixels get pure top-down (no swirl artifacts).
float cliff_blend(vec3 wnrm) {
    float slope = 1.0 - clamp(wnrm.y, 0.0, 1.0);
    return smoothstep(0.55, 0.85, slope);
}

// Two side-axis blend factor (0..1, sums with cliff_w_z to 1). Computed once
// from horizontal normal so X/Z projections blend smoothly instead of
// discrete-picking → no swirly axis-flip.
vec2 cliff_axis_weights(vec3 wnrm) {
    vec2 ax = vec2(abs(wnrm.x), abs(wnrm.z));
    float s = max(ax.x + ax.y, 1e-4);
    return ax / s;
}

vec3 triplanar_color(sampler2D tex, vec3 wpos, vec3 wnrm, float tile_m, vec3 unused) {
    float scale = 1.0 / max(tile_m, 0.01);
    vec2 cw = cliff_axis_weights(wnrm);
    vec3 top   = texture(tex, wpos.xz * scale).rgb;
    vec3 cx    = texture(tex, wpos.zy * scale).rgb;  // X-projected
    vec3 cz    = texture(tex, wpos.xy * scale).rgb;  // Z-projected
    vec3 cliff = cx * cw.x + cz * cw.y;
    return mix(top, cliff, cliff_blend(wnrm));
}

vec3 triplanar_normal(sampler2D tex, vec3 wpos, vec3 wnrm, float tile_m, vec3 unused) {
    float scale = 1.0 / max(tile_m, 0.01);
    vec2 cw = cliff_axis_weights(wnrm);
    vec3 top   = unpack_normal(texture(tex, wpos.xz * scale));
    vec3 cx    = unpack_normal(texture(tex, wpos.zy * scale));
    vec3 cz    = unpack_normal(texture(tex, wpos.xy * scale));
    vec3 cliff = normalize(cx * cw.x + cz * cw.y);
    return normalize(mix(top, cliff, cliff_blend(wnrm)));
}

float triplanar_scalar(sampler2D tex, vec3 wpos, float tile_m, vec3 wnrm) {
    float scale = 1.0 / max(tile_m, 0.01);
    vec2 cw = cliff_axis_weights(wnrm);
    float top   = texture(tex, wpos.xz * scale).r;
    float cx    = texture(tex, wpos.zy * scale).r;
    float cz    = texture(tex, wpos.xy * scale).r;
    float cliff = cx * cw.x + cz * cw.y;
    return mix(top, cliff, cliff_blend(wnrm));
}

void fragment() {
    vec4 w_raw = texture(splat, v_uv);
    float wsum_raw = w_raw.r + w_raw.g + w_raw.b + w_raw.a;
    // ocean_blend: 1.0 where no biome is painted, 0.0 where some biome dominates.
    // narrow band so the transition reads as shoreline rather than a wide blur.
    float ocean_blend = 1.0 - clamp(wsum_raw * 8.0, 0.0, 1.0);
    vec4 w = w_raw / max(wsum_raw, 1e-4);

    // Triplanar projection weights (world-normal-aligned).
    vec3 wnrm_abs = abs(v_world_normal);
    vec3 tw = pow(wnrm_abs, vec3(triplanar_sharpness));
    tw /= max(tw.x + tw.y + tw.z, 1e-4);

    // Top-down UV path (used when triplanar_strength < 1)
    vec2 uv_top_R = v_uv * (terrain_size_m / tile_meters.r);
    vec2 uv_top_G = v_uv * (terrain_size_m / tile_meters.g);
    vec2 uv_top_B = v_uv * (terrain_size_m / tile_meters.b);
    vec2 uv_top_A = v_uv * (terrain_size_m / tile_meters.a);

    vec3 alb_top = texture(albedo_R, uv_top_R).rgb * w.r
                 + texture(albedo_G, uv_top_G).rgb * w.g
                 + texture(albedo_B, uv_top_B).rgb * w.b
                 + texture(albedo_A, uv_top_A).rgb * w.a;
    vec3 nrm_top = unpack_normal(texture(normal_R, uv_top_R)) * w.r
                 + unpack_normal(texture(normal_G, uv_top_G)) * w.g
                 + unpack_normal(texture(normal_B, uv_top_B)) * w.b
                 + unpack_normal(texture(normal_A, uv_top_A)) * w.a;
    float rgh_top = texture(rough_R, uv_top_R).r * w.r
                  + texture(rough_G, uv_top_G).r * w.g
                  + texture(rough_B, uv_top_B).r * w.b
                  + texture(rough_A, uv_top_A).r * w.a;

    // Triplanar path
    vec3 alb_tri = triplanar_color(albedo_R, v_world, v_world_normal, tile_meters.r, tw) * w.r
                 + triplanar_color(albedo_G, v_world, v_world_normal, tile_meters.g, tw) * w.g
                 + triplanar_color(albedo_B, v_world, v_world_normal, tile_meters.b, tw) * w.b
                 + triplanar_color(albedo_A, v_world, v_world_normal, tile_meters.a, tw) * w.a;
    vec3 nrm_tri = triplanar_normal(normal_R, v_world, v_world_normal, tile_meters.r, tw) * w.r
                 + triplanar_normal(normal_G, v_world, v_world_normal, tile_meters.g, tw) * w.g
                 + triplanar_normal(normal_B, v_world, v_world_normal, tile_meters.b, tw) * w.b
                 + triplanar_normal(normal_A, v_world, v_world_normal, tile_meters.a, tw) * w.a;
    float rgh_tri = triplanar_scalar(rough_R, v_world, tile_meters.r, v_world_normal) * w.r
                  + triplanar_scalar(rough_G, v_world, tile_meters.g, v_world_normal) * w.g
                  + triplanar_scalar(rough_B, v_world, tile_meters.b, v_world_normal) * w.b
                  + triplanar_scalar(rough_A, v_world, tile_meters.a, v_world_normal) * w.a;

    vec3  alb_biome = mix(alb_top, alb_tri, triplanar_strength);
    vec3  nrm_biome = normalize(mix(nrm_top, nrm_tri, triplanar_strength));
    float rgh_biome = mix(rgh_top, rgh_tri, triplanar_strength);

    // Blend with ocean fallback where no biome is painted.
    vec3  alb = mix(alb_biome, ocean_color, ocean_blend);
    vec3  nrm = normalize(mix(nrm_biome, vec3(0.0, 0.0, 1.0), ocean_blend));
    float rgh = mix(rgh_biome, ocean_roughness, ocean_blend);

    ALBEDO     = alb;
    NORMAL_MAP = nrm * 0.5 + 0.5;
    ROUGHNESS  = clamp(rgh, 0.04, 1.0);
    METALLIC   = metallic_const;
}
