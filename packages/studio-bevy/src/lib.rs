//! Immersive Labs studio pack helpers for **Bevy 0.19**.
//!
//! Packs ship engine-agnostic `.glb` meshes plus optional sidecar PBR PNGs
//! (`{variant}_{slot}_albedo|normal|orm.png`). Use [`AssetRegistry`] with the
//! auto-generated `Bevy/pack_registry.rs` from each pack, then [`spawn_prop`].

use std::collections::HashMap;

use bevy::gltf::GltfAssetLabel;
use bevy::image::ImageLoaderSettings;
use bevy::prelude::*;

/// One studio pack asset (path under the Bevy `assets/` folder).
#[derive(Clone, Debug)]
pub struct AssetEntry {
    /// Asset-relative glTF path, e.g. `models/prop_crate/prop_crate.glb`.
    pub model: String,
    /// Optional target height in meters (1 unit = 1 m).
    pub target_height_m: Option<f32>,
    /// Folder containing sidecar PNGs (same layout as the pack `Textures/` copy).
    pub texture_root: Option<String>,
}

/// In-memory registry populated from a pack's `Bevy/pack_registry.rs`.
#[derive(Resource, Default, Clone, Debug)]
pub struct AssetRegistry {
    entries: HashMap<String, AssetEntry>,
}

impl AssetRegistry {
    pub fn register(
        &mut self,
        asset_id: impl Into<String>,
        model: impl Into<String>,
        target_height_m: Option<f32>,
        texture_root: Option<&str>,
    ) {
        self.entries.insert(
            asset_id.into(),
            AssetEntry {
                model: model.into(),
                target_height_m,
                texture_root: texture_root.map(|s| s.to_string()),
            },
        );
    }

    pub fn get(&self, asset_id: &str) -> Option<&AssetEntry> {
        self.entries.get(asset_id)
    }

    pub fn contains(&self, asset_id: &str) -> bool {
        self.entries.contains_key(asset_id)
    }
}

/// Spawn a studio GLB as a Bevy 0.19 [`WorldAssetRoot`] (`#Scene0`).
///
/// Returns `None` when `asset_id` is missing from the registry.
pub fn spawn_prop(
    commands: &mut Commands,
    asset_server: &AssetServer,
    registry: &AssetRegistry,
    asset_id: &str,
) -> Option<Entity> {
    let entry = registry.get(asset_id)?;
    let model_path = entry.model.clone();
    let handle = asset_server.load(GltfAssetLabel::Scene(0).from_asset(model_path));
    let mut transform = Transform::default();
    if let Some(height) = entry.target_height_m.filter(|h| *h > 0.0) {
        // Uniform scale hint when the authored mesh is ~1 m tall; refine after load if needed.
        transform.scale = Vec3::splat(height);
    }
    Some(
        commands
            .spawn((
                Name::new(format!("StudioProp:{asset_id}")),
                WorldAssetRoot(handle),
                transform,
                Visibility::default(),
            ))
            .id(),
    )
}

/// Build a [`StandardMaterial`] from Immersive Labs sidecar PBR maps.
///
/// ORM packing: R = AO, G = roughness, B = metallic (glTF metallicRoughness G/B).
pub fn build_orm_standard_material(
    asset_server: &AssetServer,
    texture_root: &str,
    variant: &str,
    slot: &str,
) -> StandardMaterial {
    let base = format!("{}/{}_{}", texture_root.trim_end_matches('/'), variant, slot);
    let albedo = load_srgb(asset_server, &format!("{base}_albedo.png"));
    let normal = load_linear(asset_server, &format!("{base}_normal.png"));
    let orm = load_linear(asset_server, &format!("{base}_orm.png"));

    StandardMaterial {
        base_color_texture: Some(albedo),
        normal_map_texture: Some(normal),
        metallic_roughness_texture: Some(orm.clone()),
        occlusion_texture: Some(orm),
        metallic: 1.0,
        perceptual_roughness: 1.0,
        ..default()
    }
}

/// Collect descendant entities that have [`MeshMaterial3d<StandardMaterial>`].
///
/// Call after the glTF scene has finished spawning, then
/// [`set_orm_material_on_entities`] for sidecar-only packs.
pub fn collect_mesh_material_entities(
    root: Entity,
    children: &Query<&Children>,
    material_query: &Query<Entity, With<MeshMaterial3d<StandardMaterial>>>,
) -> Vec<Entity> {
    let mut out = Vec::new();
    let mut stack = vec![root];
    while let Some(entity) = stack.pop() {
        if material_query.get(entity).is_ok() {
            out.push(entity);
        }
        if let Ok(kids) = children.get(entity) {
            for child in kids.iter() {
                stack.push(child);
            }
        }
    }
    out
}

/// Insert a shared ORM material on the given mesh entities.
pub fn set_orm_material_on_entities(
    commands: &mut Commands,
    entities: &[Entity],
    material: Handle<StandardMaterial>,
) {
    for entity in entities {
        commands
            .entity(*entity)
            .insert(MeshMaterial3d(material.clone()));
    }
}

fn load_srgb(asset_server: &AssetServer, path: &str) -> Handle<Image> {
    asset_server
        .load_builder()
        .with_settings(|settings: &mut ImageLoaderSettings| {
            settings.is_srgb = true;
        })
        .load(path.to_string())
}

fn load_linear(asset_server: &AssetServer, path: &str) -> Handle<Image> {
    asset_server
        .load_builder()
        .with_settings(|settings: &mut ImageLoaderSettings| {
            settings.is_srgb = false;
        })
        .load(path.to_string())
}
