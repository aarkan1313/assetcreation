// Generated 2026-05-06T10:44:54.019676+00:00 from template portal_swirl_2d
// Portal swirl — spiraling polar coordinates with depth illusion. canvas_item.
shader_type canvas_item;

uniform vec3 color_outer : source_color = vec3(0.30, 0.10, 0.50);
uniform vec3 color_mid   : source_color = vec3(0.70, 0.45, 0.95);
uniform vec3 color_inner : source_color = vec3(1.0, 1.0, 1.0);
uniform vec3 color_void  : source_color = vec3(0.05, 0.0, 0.10);
uniform float radius : hint_range(0.05, 0.5) = 0.42;
uniform float swirl : hint_range(0.0, 16.0) = 6.0;
uniform float spin_speed : hint_range(-8.0, 8.0) = 1.4;
uniform float depth_pulse : hint_range(0.0, 1.0) = 0.35;
uniform float arms : hint_range(1.0, 12.0) = 5.0;
uniform float arm_strength : hint_range(0.0, 1.5) = 0.6;
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
    vec2 uv = UV - 0.5;
    float t = TIME;
    float r = length(uv) * 2.0;
    float ang = atan(uv.y, uv.x);

    // swirl angle: tighter near center, looser at edge
    float swirl_amount = swirl / max(r, 0.01);
    float a = ang + swirl_amount + t * spin_speed;

    // arms: angular ribbing (galaxy-like)
    float armPattern = 0.5 + 0.5 * sin(a * arms);
    armPattern = pow(armPattern, 2.5) * arm_strength;

    // soft swirl noise for variation
    vec2 spiral_uv = vec2(cos(a) * r, sin(a) * r) * 4.0;
    float n = vnoise(spiral_uv + vec2(t * 0.4, 0.0));

    // depth — center pulses inward
    float pulse = 0.5 + 0.5 * sin(t * 1.7);
    float depth = smoothstep(0.0, radius, r) * (1.0 - depth_pulse * pulse);

    // colour ramp from void → outer → mid → inner
    vec3 col = color_void;
    col = mix(col, color_outer, smoothstep(0.0, radius * 0.4, r));
    col = mix(col, color_mid, smoothstep(radius * 0.4, radius * 0.85, r) * (0.6 + armPattern));
    col = mix(col, color_inner, armPattern * (1.0 - smoothstep(radius * 0.6, radius, r)));

    // edge falloff
    float edge = 1.0 - smoothstep(radius, radius + 0.05, r);

    float alpha = edge * opacity;
    COLOR = vec4(col, alpha);
}
