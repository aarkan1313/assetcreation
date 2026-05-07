// Generated 2026-05-06T10:44:53.829629+00:00 from template shield_ripple_2d
// Shield ripple — hex-pattern shield with hit ripple expansion. canvas_item.
shader_type canvas_item;

uniform vec3 color_shield : source_color = vec3(0.40, 0.78, 1.0);
uniform vec3 color_hit    : source_color = vec3(1.0, 0.95, 0.55);
uniform float hex_scale : hint_range(2.0, 64.0) = 18.0;
uniform float hex_strength : hint_range(0.0, 1.0) = 0.45;
uniform float fresnel_power : hint_range(0.5, 8.0) = 2.5;
uniform float ripple_speed : hint_range(0.0, 8.0) = 3.0;
uniform float ripple_strength : hint_range(0.0, 1.0) = 0.7;
uniform float ripple_freq : hint_range(1.0, 64.0) = 18.0;
uniform vec2  hit_position = vec2(0.5, 0.5);
uniform float hit_age : hint_range(0.0, 4.0) = 0.0;
uniform float opacity : hint_range(0.0, 1.0) = 1.0;

// hex distance — return distance to nearest hex centre.
float hexDist(vec2 p) {
    p = abs(p);
    float c = dot(p, normalize(vec2(1.0, 1.732)));
    return max(c, p.x);
}

vec4 hexCoords(vec2 uv) {
    vec2 r = vec2(1.0, 1.732);
    vec2 h = r * 0.5;
    vec2 a = mod(uv, r) - h;
    vec2 b = mod(uv - h, r) - h;
    vec2 gv = (dot(a, a) < dot(b, b)) ? a : b;
    float x = atan(gv.x, gv.y);
    float y = 0.5 - hexDist(gv);
    vec2 id = uv - gv;
    return vec4(x, y, id.x, id.y);
}

void fragment() {
    vec2 uv = UV - 0.5;
    float t = TIME;

    // hex pattern
    vec4 hex = hexCoords(uv * hex_scale);
    float hex_edge = smoothstep(0.02, 0.04, hex.y) * (1.0 - smoothstep(0.46, 0.5, hex.y));
    hex_edge *= hex_strength;

    // fresnel-style edge brightness from radial
    float r = length(uv) * 2.0;
    float fres = pow(clamp(r, 0.0, 1.0), fresnel_power);

    // continuous slow ripple
    float ripple = sin(r * ripple_freq - t * ripple_speed) * 0.5 + 0.5;
    ripple = pow(ripple, 4.0) * ripple_strength;

    // hit ripple — expanding ring centered at hit_position
    float hit = 0.0;
    if (hit_age > 0.0 && hit_age < 4.0) {
        vec2 hp = hit_position - 0.5;
        float hd = length(uv - hp);
        float hit_radius = hit_age * 0.6;
        float ring = exp(-pow((hd - hit_radius) * 6.0, 2.0));
        float fade = 1.0 - smoothstep(0.0, 4.0, hit_age);
        hit = ring * fade;
    }

    vec3 col = color_shield * (0.4 + ripple + fres * 0.6 + hex_edge * 0.8);
    col = mix(col, color_hit, hit);

    float alpha = (fres * 0.7 + hex_edge + ripple * 0.3 + hit) * opacity;
    COLOR = vec4(col, clamp(alpha, 0.0, 1.0));
}
