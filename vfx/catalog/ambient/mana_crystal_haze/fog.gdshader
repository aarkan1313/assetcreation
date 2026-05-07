// Volumetric fog material - reads sliced 3D density from a 2D atlas.
// `density_atlas` layout: D slices, each WxH, concatenated horizontally
// -> total atlas size (W*D, H). The shader reconstructs 3D by interpolating
// between two adjacent z-slices at the voxel's UVW.z.
shader_type fog;

uniform sampler2D density_atlas : filter_linear, repeat_disable;
uniform vec3 atlas_meta = vec3(64.0, 64.0, 32.0);  // W, H, D
uniform float density_scale = 1.0;
uniform vec3 color_top : source_color = vec3(1.0);
uniform vec3 color_bottom : source_color = vec3(0.4);
uniform float emission_strength = 0.0;
uniform float anim_speed = 0.05;
uniform float anim_amp = 0.05;

float sample_density(vec3 uvw) {
    float W = atlas_meta.x;
    float H = atlas_meta.y;
    float D = atlas_meta.z;
    float zf = clamp(uvw.z, 0.0, 1.0) * (D - 1.0);
    float z0 = floor(zf);
    float z1 = min(z0 + 1.0, D - 1.0);
    float zt = zf - z0;
    vec2 cell = vec2(W / (W * D), 1.0);  // = vec2(1/D, 1)
    float u_in = clamp(uvw.x, 0.0, 1.0) * cell.x;
    float v_in = clamp(uvw.y, 0.0, 1.0);
    vec2 uv0 = vec2(z0 / D + u_in, v_in);
    vec2 uv1 = vec2(z1 / D + u_in, v_in);
    float d0 = texture(density_atlas, uv0).r;
    float d1 = texture(density_atlas, uv1).r;
    return mix(d0, d1, zt);
}

void fog() {
    // OBJECT_POSITION -> UVW [0,1] within the FogVolume.
    // The fog renderer feeds us UVW directly; just read.
    vec3 uvw = UVW;
    // Cheap time warp on UV so density slowly evolves.
    uvw.xz += vec2(sin(TIME * anim_speed), cos(TIME * anim_speed * 1.3)) * anim_amp;

    float d = sample_density(uvw);
    DENSITY = d * density_scale;
    vec3 col = mix(color_bottom, color_top, clamp(uvw.y, 0.0, 1.0));
    ALBEDO = col;
    EMISSION = col * emission_strength;
}
