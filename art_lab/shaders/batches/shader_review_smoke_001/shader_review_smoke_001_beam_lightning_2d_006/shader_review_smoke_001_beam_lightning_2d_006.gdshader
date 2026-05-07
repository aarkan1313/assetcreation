// Generated 2026-05-06T10:12:00.767812+00:00 from template beam_lightning_2d
// Lightning beam — straight or arc, jagged segments with hot core. canvas_item.
shader_type canvas_item;

uniform vec3 color_core : source_color = vec3(1.0, 1.0, 1.0);
uniform vec3 color_edge : source_color = vec3(0.55, 0.78, 1.0);
uniform vec3 color_glow : source_color = vec3(0.30, 0.55, 1.0);
uniform float thickness : hint_range(0.001, 0.2) = 0.05;
uniform float core_thickness : hint_range(0.0, 1.0) = 0.35; // fraction of thickness
uniform float jaggedness : hint_range(0.0, 1.0) = 0.55;
uniform float frequency : hint_range(1.0, 64.0) = 14.0;
uniform float speed : hint_range(0.0, 8.0) = 4.0;
uniform float arc : hint_range(-0.5, 0.5) = 0.0; // bow up/down
uniform float fork_strength : hint_range(0.0, 1.0) = 0.4;
uniform float opacity : hint_range(0.0, 1.0) = 1.0;

float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float vnoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float a = hash21(i);
    float b = hash21(i + vec2(1, 0));
    float c = hash21(i + vec2(0, 1));
    float d = hash21(i + vec2(1, 1));
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

void fragment() {
    vec2 uv = UV;
    float t = TIME;

    // Parabolic arc centerline along x; arc bows the line up/down.
    float midY = 0.5 + arc * sin(uv.x * 3.14159);

    // Jagged offset using noise advected along x
    float n1 = vnoise(vec2(uv.x * frequency, t * speed));
    float n2 = vnoise(vec2(uv.x * frequency * 2.3, t * speed * 1.7));
    float jaggle = (n1 - 0.5) * jaggedness + (n2 - 0.5) * jaggedness * 0.5;
    float lineY = midY + jaggle * 0.25;

    float dist = abs(uv.y - lineY);

    // Edge falloff: hot core, cool wash, glow halo
    float core = 1.0 - smoothstep(0.0, thickness * core_thickness, dist);
    float band = 1.0 - smoothstep(0.0, thickness, dist);
    float glow = 1.0 - smoothstep(0.0, thickness * 4.0, dist);

    // Forks: secondary bolts off the main line
    float fork = 0.0;
    if (fork_strength > 0.0) {
        for (int i = 0; i < 3; i++) {
            float fi = float(i);
            float fx = fract(uv.x * 1.7 + fi * 0.31 + t * 0.6 * speed * 0.1);
            float forkLineY = midY + (vnoise(vec2(uv.x * frequency * 0.7 + fi * 11.0, t * speed * 0.6)) - 0.5) * 0.4;
            float fdist = abs(uv.y - forkLineY) + abs(uv.x - (0.4 + 0.2 * fi)) * 0.5;
            fork += (1.0 - smoothstep(0.0, thickness * 0.7, fdist)) * fork_strength;
        }
    }
    band += fork;

    vec3 col = mix(color_glow, color_edge, band);
    col = mix(col, color_core, core);

    float alpha = clamp(band + glow * 0.5 + core, 0.0, 1.0) * opacity;
    COLOR = vec4(col, alpha);
}
