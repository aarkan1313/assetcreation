// Clipmap geometry debug shader.
//
// Vertex shader displaces by sin(world_xz) so we can confirm
// the clipmap geometry + camera-relative translation work before
// wiring the kernel composer.
//
// Fragment shader colors by ring index (set per-instance) so we can
// see ring boundaries during debugging.

shader_type spatial;
render_mode unshaded, cull_back, depth_draw_opaque;

uniform int ring_index = 0;
// Color per ring: 0=red, 1=green, 2=blue, 3=yellow.
const vec3 RING_COLORS[4] = vec3[4](
	vec3(0.9, 0.4, 0.3),
	vec3(0.4, 0.9, 0.3),
	vec3(0.3, 0.5, 0.9),
	vec3(0.9, 0.8, 0.3)
);

varying vec3 v_world_pos;

void vertex() {
	// Skirt verts arrive with VERTEX.y = -skirt_depth_m (set by
	// ClipmapRing._build_donut_mesh). Surface verts arrive with
	// VERTEX.y = 0. We ADD displacement so skirts stay below the
	// surface and hide the heightmap-discontinuity crack between
	// adjacent rings.
	vec3 model_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float amplitude = 50.0;
	float frequency = 0.01;
	float h = sin(model_world.x * frequency) * sin(model_world.z * frequency) * amplitude;
	VERTEX.y += h;
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	int safe_ring = clamp(ring_index, 0, 3);
	ALBEDO = RING_COLORS[safe_ring];
}
