// Generated 2026-05-06T04:18:34.864472+00:00 from template ring_field_2d
// Ring field — magic circles, runes, portal rings. canvas_item.
// Designed to be parameterized by JSON (LLM-friendly).
shader_type canvas_item;

uniform vec3 color_inner : source_color = vec3(0.33, 0.84, 1.0);
uniform vec3 color_outer : source_color = vec3(0.65, 0.42, 1.0);
uniform vec3 color_glow  : source_color = vec3(1.0, 1.0, 1.0);
uniform float radius : hint_range(0.05, 0.5) = 0.42;
uniform float edge_width : hint_range(0.001, 0.1) = 0.04;
uniform float noise_scale : hint_range(1.0, 64.0) = 11.0;
uniform float pulse_speed : hint_range(0.0, 8.0) = 1.8;
uniform float distortion : hint_range(0.0, 0.5) = 0.12;
uniform float rune_count : hint_range(0.0, 24.0) = 12.0;
uniform float rune_strength : hint_range(0.0, 2.0) = 0.7;
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

float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 4; i++) {
        v += a * vnoise(p);
        p *= 2.0;
        a *= 0.5;
    }
    return v;
}

void fragment() {
    vec2 uv = UV - 0.5;
    float t = TIME;

    // domain warp for organic edge
    vec2 warp = vec2(
        fbm(uv * noise_scale + vec2(t * 0.3, 0.0)),
        fbm(uv * noise_scale + vec2(0.0, t * 0.3))
    ) - 0.5;
    uv += warp * distortion;

    float r = length(uv);
    float ang = atan(uv.y, uv.x);

    // ring band
    float ring = 1.0 - smoothstep(0.0, edge_width, abs(r - radius));
    float pulse = 0.5 + 0.5 * sin(t * pulse_speed);
    ring *= 0.6 + 0.4 * pulse;

    // runes evenly spaced
    if (rune_count > 0.0) {
        float a = ang * rune_count / 6.2831853;
        float runeMask = step(0.55, abs(fract(a) - 0.5) * 2.0);
        float runeBand = smoothstep(radius - edge_width * 1.5, radius + edge_width * 1.5, r);
        runeBand *= 1.0 - smoothstep(radius + edge_width * 1.5, radius + edge_width * 5.0, r);
        ring += runeMask * runeBand * rune_strength;
    }

    // outer glow
    float glow = exp(-pow((r - radius) / (edge_width * 4.0), 2.0)) * 0.5;

    vec3 col = mix(color_outer, color_inner, ring);
    col += color_glow * glow * pulse;

    float alpha = clamp(ring + glow, 0.0, 1.0) * opacity;
    COLOR = vec4(col, alpha);
}
