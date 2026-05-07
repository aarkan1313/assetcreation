shader_type spatial;
render_mode unshaded, depth_draw_opaque, cull_disabled, blend_add;

uniform sampler2D albedo_tex : source_color, filter_linear, repeat_disable;
uniform int h_frames = 1;
uniform int v_frames = 1;
uniform int n_frames = 1;
uniform float fps = 24.0;
uniform bool loop = true;
uniform vec4 modulate : source_color = vec4(1.0);
uniform float emission_strength = 0.0;

void vertex() {
    // Y-axis billboard: keep upright, rotate around world Y.
    vec3 obj_pos = MODEL_MATRIX[3].xyz;
    vec3 cam_pos = INV_VIEW_MATRIX[3].xyz;
    vec3 to_cam = cam_pos - obj_pos;
    to_cam.y = 0.0;
    if (length(to_cam) > 0.0001) {
        vec3 fwd = normalize(to_cam);
        vec3 up = vec3(0.0, 1.0, 0.0);
        vec3 right = normalize(cross(up, fwd));
        mat4 b = mat4(
            vec4(right, 0.0),
            vec4(up,    0.0),
            vec4(fwd,   0.0),
            vec4(obj_pos, 1.0));
        MODELVIEW_MATRIX = VIEW_MATRIX * b;
        MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
    }

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
