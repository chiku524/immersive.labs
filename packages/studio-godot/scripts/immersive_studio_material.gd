class_name ImmersiveStudioMaterial
extends RefCounted

## Applies Immersive Labs sidecar PBR textures and tracks pack asset registry entries.

const ORM_SHADER := preload("res://shaders/immersive_studio_orm.gdshader")

static var ASSET_REGISTRY: Dictionary = {}


static func register_asset(
	asset_id: String,
	model: String,
	target_height: float = -1.0,
	target_width: float = -1.0,
	texture_root: String = "",
	variant: String = "default",
	slot: String = "main"
) -> void:
	var entry := {"model": model}
	if target_height > 0.0:
		entry["target_height"] = target_height
	if target_width > 0.0:
		entry["target_width"] = target_width
	if not texture_root.is_empty():
		var base := "%s/%s_%s" % [texture_root.rstrip("/"), variant, slot]
		entry["textures"] = {
			variant: {
				"albedo": base + "_albedo.png",
				"normal": base + "_normal.png",
				"orm": base + "_orm.png",
			},
		}
	ASSET_REGISTRY[asset_id] = entry


static func get_asset_entry(asset_id: String) -> Dictionary:
	return ASSET_REGISTRY.get(asset_id, {})


static func get_model_path(asset_id: String) -> String:
	return str(get_asset_entry(asset_id).get("model", ""))


static func get_default_scale(
	asset_id: String,
	aabb: AABB,
	target_height: float = -1.0,
	target_width: float = -1.0
) -> float:
	var entry := get_asset_entry(asset_id)
	if target_width > 0.0:
		return target_width / maxf(maxf(aabb.size.x, aabb.size.z), 0.001)
	if target_height > 0.0:
		return target_height / maxf(aabb.size.y, 0.001)
	if entry.has("target_width"):
		var width := float(entry["target_width"])
		return width / maxf(maxf(aabb.size.x, aabb.size.z), 0.001)
	return float(entry.get("target_height", 1.0)) / maxf(aabb.size.y, 0.001)


static func apply_to_node(
	root: Node,
	asset_id: String,
	texture_variant: String = "default",
	overrides: Dictionary = {},
	preserve_embedded: bool = true
) -> void:
	if preserve_embedded:
		return

	var entry: Dictionary = get_asset_entry(asset_id)
	var textures: Dictionary = entry.get("textures", {})
	var paths: Dictionary = textures.get(texture_variant, textures.get("default", {}))
	if paths.is_empty():
		return

	var albedo_path: String = str(overrides.get("albedo", paths.get("albedo", "")))
	if albedo_path.is_empty():
		return

	var material := _build_material(paths, overrides)
	for mesh_inst in root.find_children("*", "MeshInstance3D", true, false):
		var mi := mesh_inst as MeshInstance3D
		if mi.mesh == null:
			continue
		for surface_idx in mi.mesh.get_surface_count():
			mi.set_surface_override_material(surface_idx, material)


static func _build_material(paths: Dictionary, overrides: Dictionary) -> ShaderMaterial:
	var mat := ShaderMaterial.new()
	mat.shader = ORM_SHADER

	var albedo_tex: Texture2D = load(str(overrides.get("albedo", paths.get("albedo", ""))))
	if albedo_tex:
		mat.set_shader_parameter("albedo_tex", albedo_tex)

	var orm_path := str(overrides.get("orm", paths.get("orm", "")))
	if not orm_path.is_empty() and ResourceLoader.exists(orm_path):
		mat.set_shader_parameter("orm_tex", load(orm_path))

	mat.set_shader_parameter(
		"metallic_scale",
		float(overrides.get("metallic_scale", paths.get("metallic_scale", 0.22)))
	)
	mat.set_shader_parameter(
		"roughness_scale",
		float(overrides.get("roughness_scale", paths.get("roughness_scale", 0.88)))
	)
	mat.set_shader_parameter(
		"emission_energy",
		float(overrides.get("emission_energy", paths.get("emission_energy", 0.0)))
	)
	var emission_tint: Color = overrides.get("emission_tint", paths.get("emission_tint", Color.WHITE))
	mat.set_shader_parameter("emission_tint", Vector3(emission_tint.r, emission_tint.g, emission_tint.b))
	return mat
