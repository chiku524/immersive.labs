/**
 * Shared TypeScript shapes for the Video Game Generation Studio pipeline.
 * Keep in sync with docs/studio/json-schema-spec.md.
 */

export type StudioStylePreset =
  | "realistic_hd_pbr"
  | "anime_stylized"
  | "toon_bold";

export type StudioAssetCategory =
  | "prop"
  | "environment_piece"
  | "character_base"
  | "material_library";

export interface StudioMaterialSlot {
  id: string;
  role: "albedo" | "normal" | "orm" | "emissive" | "mask";
  resolution_hint: 512 | 1024 | 2048 | 4096;
  notes?: string;
}

export interface StudioAssetVariant {
  variant_id: string;
  label: string;
  seed?: number;
}

export interface StudioAssetSpec {
  spec_version: "0.1";
  asset_id: string;
  display_name: string;
  category: StudioAssetCategory;
  style_preset: StudioStylePreset;
  poly_budget_tris: number;
  /** World units: 1 unit = 1 meter in Unity convention. */
  target_height_m?: number;
  palette?: string[];
  tags: string[];
  material_slots: StudioMaterialSlot[];
  variants: StudioAssetVariant[];
  generation: {
    source_prompt: string;
    negative_prompt?: string;
    /** References to locked style assets (paths or hashes). */
    reference_assets?: string[];
  };
  unity: {
    import_subfolder: string;
    collider: "box" | "capsule" | "mesh_convex" | "none";
  };
}

export interface StudioJobManifest {
  manifest_version: "0.1";
  job_id: string;
  created_at: string;
  engine_target: "unity";
  assets: StudioAssetSpec[];
  toolchain: {
    llm_model?: string;
    image_pipeline?: string;
    mesh_pipeline?: string;
  };
}
