// Fire/dissolve mask — burn-edge effect for sprites or panels. canvas_item.
// Drives an ALBEDO-textured sprite via TEXTURE input; if no texture, uses pure ramp.
shader_type canvas_item;

uniform vec3 color_burn : source_color = vec3(1.0, 0.55, 0.10);
uniform vec3 color_ash  : source_color = vec3(0.18, 0.10, 0.07);
uniform vec3 color_ember : source_color = vec3(1.0, 0.85, 0.30);
uniform float threshold : hint_range(0.0, 1.0) = 0.45;
uniform float edge_width : hint_range(0.001, 0.5) = 0.10;
uniform float noise_scale : hint_range(1.0, 64.0) = 8.0;
uniform float scroll_speed : hint_range(0.0, 4.0) = 0.7;
uniform float warp_strength : hint_range(0.0, 1.0) = 0.3;
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
    for (int i = 0; i < 5; i++) {
        v += a * vnoise(p);
        p *= 2.0;
        a *= 0.5;
    }
    return v;
}

void fragment() {
    vec2 uv = UV;
    float t = TIME * scroll_speed;

    // domain warp
    vec2 warp = vec2(
        fbm(uv * noise_scale + vec2(t, 0.0)),
        fbm(uv * noise_scale + vec2(0.0, t * 0.7))
    ) - 0.5;
    vec2 sample_uv = uv + warp * warp_strength;

    float n = fbm(sample_uv * noise_scale + vec2(0.0, t));
    // bottom-to-top burn bias
    float bias = 1.0 - uv.y;
    n = mix(n, bias, 0.4);

    // burn edge bands
    float burnt   = smoothstep(threshold - edge_width, threshold, n);
    float edge    = smoothstep(threshold, threshold + edge_width, n) - burnt;
    float visible = 1.0 - smoothstep(threshold + edge_width, threshold + edge_width * 1.5, n);

    // sample base sprite if any (transparent if no texture bound)
    vec4 base = texture(TEXTURE, UV);

    // edge ember pulse
    float pulse = 0.7 + 0.3 * sin(TIME * 6.0 + n * 8.0);
    vec3 col = base.rgb;
    col = mix(col, color_burn, edge * 0.95);
    col += color_ember * edge * pulse;
    col = mix(col, color_ash, burnt);

    float alpha = base.a * visible + edge * 0.85;
    COLOR = vec4(col, alpha * opacity);
}
