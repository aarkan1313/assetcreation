// Minimal diagnostic shader — Option F from the audit doc.
//
// Strips out everything except: sample one texture by world-XZ UV.
// No blending. No normal maps. No AO. No slope math. No NaN guards.
// No luma floor. No PBR. Just: ALBEDO = texture(albedo, world_xz * scale).
//
// Purpose: if the black-pixel artifact persists with THIS shader, the
// bug is not in the v2 shader's math — it's in the mesh, the texture
// sampling, or the renderer config. If the artifact vanishes, the bug
// is somewhere in the v2 shader's blending/normal/AO path and we can
// bisect there.

shader_type spatial;
// Back to lit minimal shader to retest the black-patch bug after
// disabling SurfaceTool.generate_tangents(). Theory: degenerate tangents
// were corrupting Godot's view-space normal transform on some fragments.
render_mode cull_back, depth_draw_opaque, specular_schlick_ggx;

uniform sampler2D ground_albedo : source_color;
uniform float world_uv_scale = 0.04;

varying vec3 v_world_pos;

void vertex() {
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 uv = v_world_pos.xz * world_uv_scale;
	ALBEDO = texture(ground_albedo, uv).rgb;
}
