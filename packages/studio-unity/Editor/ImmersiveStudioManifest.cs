using System;

namespace ImmersiveLabs.Studio.Editor
{
    [Serializable]
    public sealed class JobManifestDto
    {
        public string manifest_version;
        public string job_id;
        public string created_at;
        public string engine_target;
        public AssetSpecDto[] assets;
        public ToolchainDto toolchain;
    }

    [Serializable]
    public sealed class ToolchainDto
    {
        public string llm_model;
        public string image_pipeline;
        public string mesh_pipeline;
        public string unity_urp_version;
    }

    [Serializable]
    public sealed class AssetSpecDto
    {
        public string spec_version;
        public string asset_id;
        public string display_name;
        public string category;
        public string style_preset;
        public int poly_budget_tris;
        public float target_height_m;
        public string[] tags;
        public MaterialSlotDto[] material_slots;
        public VariantDto[] variants;
        public GenerationDto generation;
        public UnityHintsDto unity;
    }

    [Serializable]
    public sealed class MaterialSlotDto
    {
        public string id;
        public string role;
        public int resolution_hint;
        public string notes;
    }

    [Serializable]
    public sealed class VariantDto
    {
        public string variant_id;
        public string label;
        public int seed;
    }

    [Serializable]
    public sealed class GenerationDto
    {
        public string source_prompt;
        public string negative_prompt;
        public string[] reference_assets;
    }

    [Serializable]
    public sealed class UnityHintsDto
    {
        public string import_subfolder;
        public string collider;
    }
}
