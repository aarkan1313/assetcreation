extends RefCounted
class_name RuntimeImageCache


static func load_image(cache_manifest_path: String, fallback_image_path: String = "") -> Image:
	if cache_manifest_path != "":
		var img: Image = _load_cached_image(cache_manifest_path)
		if img != null:
			return img
	if fallback_image_path != "":
		return load_png_image(fallback_image_path)
	return null


static func load_texture(cache_manifest_path: String, fallback_image_path: String = "") -> Texture2D:
	var img: Image = load_image(cache_manifest_path, fallback_image_path)
	if img == null:
		return null
	return ImageTexture.create_from_image(img)


static func load_png_image(path: String) -> Image:
	var f: FileAccess = FileAccess.open(path, FileAccess.READ)
	if f == null:
		var tex: Texture2D = load(path) as Texture2D
		return tex.get_image() if tex != null else null
	var bytes: PackedByteArray = f.get_buffer(f.get_length())
	f.close()
	var img: Image = Image.new()
	var rc: Error = img.load_png_from_buffer(bytes)
	return img if rc == OK else null


static func _load_cached_image(manifest_path: String) -> Image:
	var f: FileAccess = FileAccess.open(manifest_path, FileAccess.READ)
	if f == null:
		return null
	var txt: String = f.get_as_text()
	f.close()
	var parsed: Variant = JSON.parse_string(txt)
	if typeof(parsed) != TYPE_DICTIONARY:
		return null

	var data_path: String = String(parsed.get("data_path", ""))
	var data_file: FileAccess = FileAccess.open(data_path, FileAccess.READ)
	if data_file == null:
		return null
	var bytes: PackedByteArray = data_file.get_buffer(data_file.get_length())
	data_file.close()

	var width: int = int(parsed.get("width", 0))
	var height: int = int(parsed.get("height", 0))
	var format_name: String = String(parsed.get("format", ""))
	var image_format: Image.Format = _image_format(format_name)
	if width <= 0 or height <= 0 or image_format == Image.FORMAT_MAX:
		return null

	var expected_bytes: int = width * height * _bytes_per_pixel(format_name)
	if bytes.size() != expected_bytes:
		push_error("RuntimeImageCache: byte count mismatch for " + manifest_path)
		return null

	return Image.create_from_data(width, height, false, image_format, bytes)


static func _image_format(format_name: String) -> Image.Format:
	match format_name:
		"rf32":
			return Image.FORMAT_RF
		"rgba8":
			return Image.FORMAT_RGBA8
		"r8":
			return Image.FORMAT_R8
		_:
			return Image.FORMAT_MAX


static func _bytes_per_pixel(format_name: String) -> int:
	match format_name:
		"rf32":
			return 4
		"rgba8":
			return 4
		"r8":
			return 1
		_:
			return 0
