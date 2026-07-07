class_name ImmersiveStudioModel
extends RefCounted

## Spawns Immersive Labs GLB props with uniform scale and optional sidecar PBR materials.


static func spawn_child(
	parent: Node3D,
	asset_id: String,
	texture_variant: String = "default",
	target_height: float = -1.0,
	target_width: float = -1.0,
	snap_bottom: bool = true,
	rotation_y: float = 0.0,
	apply_textures: bool = false,
	material_overrides: Dictionary = {}
) -> Node3D:
	var entry: Dictionary = ImmersiveStudioMaterial.get_asset_entry(asset_id)
	if entry.is_empty():
		push_warning("ImmersiveStudioModel: unknown asset '%s'" % asset_id)
		return null

	var model_path: String = str(entry.get("model", ""))
	if model_path.is_empty() or not ResourceLoader.exists(model_path):
		push_warning("ImmersiveStudioModel: missing model for '%s'" % asset_id)
		return null

	var scene := load(model_path) as PackedScene
	if scene == null:
		return null

	var inst := scene.instantiate() as Node3D
	parent.add_child(inst)
	inst.name = "StudioModel"
	inst.rotation.y = rotation_y

	var aabb := _local_mesh_aabb(inst)
	if aabb.size.length_squared() > 0.0001:
		var uniform_scale := ImmersiveStudioMaterial.get_default_scale(
			asset_id,
			aabb,
			target_height,
			target_width
		)
		inst.scale = Vector3.ONE * uniform_scale

		var scaled_pos := aabb.position * inst.scale
		var scaled_size := aabb.size * inst.scale
		var anchor := Vector3(
			scaled_pos.x + scaled_size.x * 0.5,
			scaled_pos.y if snap_bottom else scaled_pos.y + scaled_size.y * 0.5,
			scaled_pos.z + scaled_size.z * 0.5
		)
		inst.position = -anchor

	if apply_textures:
		ImmersiveStudioMaterial.apply_to_node(
			inst,
			asset_id,
			texture_variant,
			material_overrides,
			false
		)
	return inst


static func spawn_at(
	parent: Node3D,
	asset_id: String,
	pos: Vector3,
	rotation_y: float = 0.0,
	target_height: float = -1.0,
	target_width: float = -1.0,
	snap_bottom: bool = true,
	apply_textures: bool = false,
	material_overrides: Dictionary = {}
) -> Node3D:
	var inst := spawn_child(
		parent,
		asset_id,
		"default",
		target_height,
		target_width,
		snap_bottom,
		rotation_y,
		apply_textures,
		material_overrides
	)
	if inst:
		inst.position += pos
	return inst


static func hide_procedural_visuals(root: Node) -> void:
	for child in root.get_children():
		if child is MeshInstance3D:
			child.visible = false
		elif child.name == "Visuals":
			child.visible = false


static func _local_mesh_aabb(node: Node) -> AABB:
	var result := AABB()
	var first := true
	for child in node.find_children("*", "MeshInstance3D", true, false):
		var mesh_inst := child as MeshInstance3D
		if mesh_inst.mesh == null:
			continue
		var mesh_aabb := mesh_inst.mesh.get_aabb()
		var corners: Array[Vector3] = [
			mesh_aabb.position,
			mesh_aabb.position + Vector3(mesh_aabb.size.x, 0.0, 0.0),
			mesh_aabb.position + Vector3(0.0, mesh_aabb.size.y, 0.0),
			mesh_aabb.position + Vector3(0.0, 0.0, mesh_aabb.size.z),
			mesh_aabb.position + Vector3(mesh_aabb.size.x, mesh_aabb.size.y, 0.0),
			mesh_aabb.position + Vector3(mesh_aabb.size.x, 0.0, mesh_aabb.size.z),
			mesh_aabb.position + Vector3(0.0, mesh_aabb.size.y, mesh_aabb.size.z),
			mesh_aabb.position + mesh_aabb.size,
		]
		for corner in corners:
			var local_corner := mesh_inst.transform * corner
			if first:
				result = AABB(local_corner, Vector3.ZERO)
				first = false
			else:
				result = result.expand(local_corner)
	return result
