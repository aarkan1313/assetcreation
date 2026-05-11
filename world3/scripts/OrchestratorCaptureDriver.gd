extends Node

# Phase E.4 parameterized capture driver.
#
# Reads a JSON config from user://orchestrator_capture_request.json (the
# orchestrator writes this file before invoking Godot), instantiates a
# World3AutoReviewTour for the requested bundle, waits for warmup frames,
# saves a PNG, and quits.
#
# This indirection avoids Godot's CLI parser eating our custom flags or
# falling back to the project launcher on unrecognized args.
#
# Request schema:
# {
#   "bundle_dir":     "res://toporeview/<bundle>",
#   "material":       "res://textures/wgv3/terrain_blend_<kit>.tres",
#   "mode":           "close|medium|iso|topdown",
#   "output":         "res://docs/captures/review/<id>_<mode>.png",
#   "macro_albedo":   "res://...",          // optional
#   "macro_mask":     "res://...",          // optional
#   "tour_profile":   "standard",            // optional, default "standard"
#   "warmup_frames":  60,                    // optional, default 60
#   "viewport_size":  [1600, 1000],          // optional
#   "start_x_m":      64.0,                  // optional
#   "start_z_m":      128.0,                 // optional
#   "chunk_size_m":   256.0,                 // optional
#   "chunk_resolution_m": 8.0                // optional
# }

const TourScript = preload("res://scripts/World3AutoReviewTour.gd")
const REQUEST_PATH := "user://orchestrator_capture_request.json"

const MODE_TOUR_INDEX := {
	"close": 0,
	"medium": 1,
	"iso": 2,
	"topdown": 3,
}


func _ready() -> void:
	print("[OrchestratorCaptureDriver] _ready")
	var req: Dictionary = _load_request()
	if req.is_empty():
		get_tree().quit(2)
		return
	print("[OrchestratorCaptureDriver] request: ", req)

	var viewport_size: Vector2i = Vector2i(1600, 1000)
	if req.has("viewport_size"):
		var vs: Array = req["viewport_size"]
		if vs.size() == 2:
			viewport_size = Vector2i(int(vs[0]), int(vs[1]))
	get_window().size = viewport_size

	var tour: Node3D = _build_tour(req)
	add_child(tour)

	var warmup_frames: int = int(req.get("warmup_frames", 60))
	for i in range(warmup_frames):
		await get_tree().process_frame

	var img: Image = get_viewport().get_texture().get_image()
	if img == null:
		push_error("[OrchestratorCaptureDriver] viewport image is null (need a real rendering driver, not --headless)")
		get_tree().quit(3)
		return

	var output: String = req.get("output", "")
	var err: int = img.save_png(output)
	if err != OK:
		push_error("[OrchestratorCaptureDriver] save_png failed: %d path=%s" % [err, output])
		get_tree().quit(4)
		return

	print("[OrchestratorCaptureDriver] wrote " + output)
	get_tree().quit(0)


func _load_request() -> Dictionary:
	if not FileAccess.file_exists(REQUEST_PATH):
		push_error("[OrchestratorCaptureDriver] no request file at " + REQUEST_PATH)
		return {}
	var f: FileAccess = FileAccess.open(REQUEST_PATH, FileAccess.READ)
	if f == null:
		push_error("[OrchestratorCaptureDriver] cannot open " + REQUEST_PATH)
		return {}
	var text: String = f.get_as_text()
	f.close()
	var parsed: Variant = JSON.parse_string(text)
	if not (parsed is Dictionary):
		push_error("[OrchestratorCaptureDriver] request is not a JSON object")
		return {}
	var req: Dictionary = parsed
	for key in ["bundle_dir", "material", "mode", "output"]:
		if not req.has(key):
			push_error("[OrchestratorCaptureDriver] missing required field: " + key)
			return {}
	if not MODE_TOUR_INDEX.has(req["mode"]):
		push_error("[OrchestratorCaptureDriver] mode must be close|medium|iso|topdown, got " + str(req["mode"]))
		return {}
	return req


func _build_tour(req: Dictionary) -> Node3D:
	var tour: Node3D = Node3D.new()
	tour.set_script(TourScript)
	tour.name = "Tour"
	var bundle_dir: String = req["bundle_dir"]
	tour.material_path = req["material"]
	tour.heightmap_path = bundle_dir.path_join("heightmap.png")
	tour.meta_path = bundle_dir.path_join("meta.json")
	if req.has("macro_albedo") and req["macro_albedo"] != "":
		tour.source_macro_albedo_override_path = req["macro_albedo"]
	if req.has("macro_mask") and req["macro_mask"] != "":
		tour.source_macro_valid_mask_override_path = req["macro_mask"]
		tour.source_valid_mask_path = req["macro_mask"]
	tour.tour_profile = req.get("tour_profile", "standard")
	tour.initial_tour_index = MODE_TOUR_INDEX[req["mode"]]
	tour.initial_tour_progress = 0.5
	tour.auto_play = false
	tour.start_x_m = float(req.get("start_x_m", 64.0))
	tour.start_z_m = float(req.get("start_z_m", 128.0))
	tour.chunk_size_m = float(req.get("chunk_size_m", 256.0))
	tour.chunk_resolution_m = float(req.get("chunk_resolution_m", 8.0))
	tour.view_radius_chunks = 2

	# Phase E.5: apply style pack render-time overrides. Any field omitted
	# from the style block keeps the tour's hardcoded default.
	if req.has("style") and req["style"] is Dictionary:
		_apply_style(tour, req["style"])
	return tour


func _apply_style(tour: Node3D, style: Dictionary) -> void:
	if style.has("background_color"):
		var bc: Array = style["background_color"]
		if bc.size() >= 3:
			var a: float = float(bc[3]) if bc.size() >= 4 else 1.0
			tour.review_background_color = Color(float(bc[0]), float(bc[1]), float(bc[2]), a)
	if style.has("sun_energy"):
		tour.review_sun_energy = float(style["sun_energy"])
	if style.has("ambient_energy"):
		tour.review_ambient_energy = float(style["ambient_energy"])
	if style.has("tonemap_exposure"):
		tour.review_tonemap_exposure = float(style["tonemap_exposure"])
	if style.has("normal_strength"):
		tour.review_normal_strength = float(style["normal_strength"])
	if style.has("detail_normal_strength"):
		tour.review_detail_normal_strength = float(style["detail_normal_strength"])
	if style.has("detail_rough_strength"):
		tour.review_detail_rough_strength = float(style["detail_rough_strength"])
	if style.has("roughness_strength"):
		tour.review_roughness_strength = float(style["roughness_strength"])
	if style.has("roughness_floor"):
		tour.review_roughness_floor = float(style["roughness_floor"])
	if style.has("specular_strength"):
		tour.review_specular_strength = float(style["specular_strength"])
	if style.has("albedo_gain"):
		tour.review_albedo_gain = float(style["albedo_gain"])
	if style.has("source_macro_strength"):
		tour.review_source_macro_strength = float(style["source_macro_strength"])
