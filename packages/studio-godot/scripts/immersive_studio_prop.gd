extends Node3D

## Attach to interactable scenes to replace procedural meshes with Immersive Labs models.

@export var asset_id: String = ""
@export var texture_variant: String = "default"
@export var target_height: float = -1.0
@export var target_width: float = -1.0
@export var rotation_y: float = 0.0
@export var hide_procedural: bool = true


func _ready() -> void:
	if asset_id.is_empty():
		return
	if hide_procedural:
		ImmersiveStudioModel.hide_procedural_visuals(get_parent())
	ImmersiveStudioModel.spawn_child(
		self,
		asset_id,
		texture_variant,
		target_height,
		target_width,
		true,
		rotation_y,
		false
	)
