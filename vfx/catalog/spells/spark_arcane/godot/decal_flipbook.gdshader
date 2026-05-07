// Decal flipbook shader. UV-animates a sprite atlas into the decal's
// projected albedo via a same-size MeshInstance3D quad child.
shader_type spatial;
render_mode unshaded;

uniform sampler2D atlas : source_color, filter_linear;
uniform int h_frames = 1;
uniform int v_frames = 1;
uniform int n_frames = 1;
uniform float fps = 24.0;
uniform bool loop = true;
uniform float fade_in_s = 0.0;
uniform float fade_out_s = 0.0;
uniform float duration_s = 1.0;
uniform vec4 modulate : source_color = vec4(1.0);

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
    vec4 c = texture(atlas, uv) * modulate;

    float life = TIME;
    float fade_in = fade_in_s > 0.0 ? smoothstep(0.0, fade_in_s, life) : 1.0;
    float fade_out = fade_out_s > 0.0 ? 1.0 - smoothstep(duration_s - fade_out_s, duration_s, life) : 1.0;
    if (!loop) {
        c.a *= fade_in * fade_out;
    }

    ALBEDO = c.rgb;
    ALPHA = c.a;
}
