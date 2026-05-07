shader_type spatial;
render_mode unshaded, depth_draw_opaque, cull_disabled, blend_mix;

uniform sampler2D albedo_tex : source_color, filter_linear, repeat_disable;
uniform int h_frames = 1;
uniform int v_frames = 1;
uniform int n_frames = 1;
uniform float fps = 24.0;
uniform bool loop = true;
uniform vec4 modulate : source_color = vec4(1.0);
uniform float emission_strength = 0.0;

void vertex() {
    // Full-billboard: cancel rotation, apply view-space translate.
    MODELVIEW_MATRIX = VIEW_MATRIX * mat4(
        INV_VIEW_MATRIX[0],
        INV_VIEW_MATRIX[1],
        INV_VIEW_MATRIX[2],
        MODEL_MATRIX[3]);
    MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);

}

void fragment() {
    float t = TIME * fps;
    int idx = int(t);
    if (loop) {
        idx = idx % n_frames;
    } else if (idx >= n_frames) {
        idx = n_frames - 1;
    }
    int col = idx % h_frames;
    int row = idx / h_frames;
    vec2 cell = vec2(1.0 / float(h_frames), 1.0 / float(v_frames));
    vec2 uv = vec2(float(col), float(row)) * cell + UV * cell;
    vec4 c = texture(albedo_tex, uv) * modulate;
    ALBEDO = c.rgb;
    ALPHA = c.a;
    EMISSION = c.rgb * emission_strength;
}
