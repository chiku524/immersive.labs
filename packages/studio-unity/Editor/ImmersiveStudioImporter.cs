using System;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;
using ImmersiveLabs.Studio.Editor;
using UnityEditor;
using UnityEngine;

namespace ImmersiveLabs.Studio.EditorTools
{
    public static class ImmersiveStudioImporter
    {
        private static readonly Regex s_pbrName = new Regex(
            @"^(?<base>.+)_(?<role>albedo|normal|orm)$",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        private const string MenuPath = "Immersive Labs/Import Studio Pack...";

        [MenuItem(MenuPath)]
        public static void ImportPackMenu()
        {
            var packRoot = EditorUtility.OpenFolderPanel("Select studio pack folder (contains manifest.json)", "", "");
            if (string.IsNullOrEmpty(packRoot))
            {
                return;
            }

            var manifestPath = Path.Combine(packRoot, "manifest.json");
            if (!File.Exists(manifestPath))
            {
                EditorUtility.DisplayDialog(
                    "Immersive Studio",
                    "Could not find manifest.json in the selected folder.",
                    "OK");
                return;
            }

            var json = File.ReadAllText(manifestPath);
            if (json.Length > 0 && json[0] == '\uFEFF')
            {
                json = json.Substring(1);
            }

            var manifest = JsonUtility.FromJson<JobManifestDto>(json);
            if (manifest == null || manifest.assets == null || manifest.assets.Length == 0)
            {
                EditorUtility.DisplayDialog("Immersive Studio", "manifest.json could not be parsed.", "OK");
                return;
            }

            var jobId = string.IsNullOrEmpty(manifest.job_id) ? "unknown_job" : SanitizeFileName(manifest.job_id);
            var destRoot = Path.Combine(Application.dataPath, "ImmersiveStudioImports", jobId);
            Directory.CreateDirectory(destRoot);

            foreach (var asset in manifest.assets)
            {
                if (asset == null || string.IsNullOrEmpty(asset.asset_id))
                {
                    continue;
                }

                var destAssetDir = Path.Combine(destRoot, asset.asset_id);
                Directory.CreateDirectory(destAssetDir);

                var srcTex = Path.Combine(packRoot, "Textures", asset.asset_id);
                if (Directory.Exists(srcTex))
                {
                    foreach (var file in Directory.GetFiles(srcTex, "*.png", SearchOption.TopDirectoryOnly))
                    {
                        var name = Path.GetFileName(file);
                        if (name.StartsWith("README", System.StringComparison.OrdinalIgnoreCase))
                        {
                            continue;
                        }

                        File.Copy(file, Path.Combine(destAssetDir, name), true);
                    }
                }
                else
                {
                    Debug.LogWarning($"[Immersive Studio] No Textures folder for asset '{asset.asset_id}'.");
                }

                var srcModels = Path.Combine(packRoot, "Models", asset.asset_id);
                if (Directory.Exists(srcModels))
                {
                    foreach (var file in Directory.GetFiles(srcModels, "*.glb", SearchOption.TopDirectoryOnly))
                    {
                        var name = Path.GetFileName(file);
                        if (name.StartsWith("README", System.StringComparison.OrdinalIgnoreCase))
                        {
                            continue;
                        }

                        File.Copy(file, Path.Combine(destAssetDir, name), true);
                    }
                }
            }

            AssetDatabase.Refresh();

            var urpLit = Shader.Find("Universal Render Pipeline/Lit");
            var packedOrmLit = Shader.Find("ImmersiveStudio/Packed ORM Lit");
            if (urpLit == null)
            {
                urpLit = Shader.Find("Standard");
            }

            if (urpLit == null)
            {
                EditorUtility.DisplayDialog(
                    "Immersive Studio",
                    "Could not find URP Lit or Standard shader. Textures were copied; create materials manually.",
                    "OK");
                return;
            }

            foreach (var asset in manifest.assets)
            {
                if (asset == null || string.IsNullOrEmpty(asset.asset_id))
                {
                    continue;
                }

                var relFolder = $"Assets/ImmersiveStudioImports/{jobId}/{asset.asset_id}";
                var fullMaterials = Path.Combine(Application.dataPath, "ImmersiveStudioImports", jobId, asset.asset_id, "Materials");
                Directory.CreateDirectory(fullMaterials);
                AssetDatabase.Refresh();

                var groups = BuildPbrGroups(relFolder);
                var litByPbrBase = new Dictionary<string, Material>(StringComparer.OrdinalIgnoreCase);
                foreach (var kv in groups)
                {
                    var baseName = kv.Key;
                    var set = kv.Value;
                    if (set.AlbedoPath == null)
                    {
                        continue;
                    }

                    ConfigureTextureImporter(set.AlbedoPath, TextureImporterType.Default, sRgb: true);
                    if (set.NormalPath != null)
                    {
                        ConfigureTextureImporter(set.NormalPath, TextureImporterType.NormalMap, sRgb: false);
                    }

                    if (set.OrmPath != null)
                    {
                        ConfigureTextureImporter(set.OrmPath, TextureImporterType.Default, sRgb: false);
                    }

                    AssetDatabase.Refresh();

                    var albedo = AssetDatabase.LoadAssetAtPath<Texture2D>(set.AlbedoPath);
                    if (albedo == null)
                    {
                        continue;
                    }

                    var normal = set.NormalPath != null ? AssetDatabase.LoadAssetAtPath<Texture2D>(set.NormalPath) : null;
                    var orm = set.OrmPath != null ? AssetDatabase.LoadAssetAtPath<Texture2D>(set.OrmPath) : null;

                    var matPath = $"{relFolder}/Materials/{baseName}_Lit.mat";
                    Shader shaderForMat = orm != null && packedOrmLit != null ? packedOrmLit : urpLit;
                    if (orm != null && packedOrmLit == null)
                    {
                        Debug.LogWarning(
                            "[Immersive Studio] ORM texture present but shader 'ImmersiveStudio/Packed ORM Lit' " +
                            "was not found — using URP Lit (ORM channels will not map correctly). " +
                            "Ensure package Shaders/ImmersiveStudioPackedORMLit.shader is imported.");
                    }

                    var mat = new Material(shaderForMat);
                    if (mat.HasProperty("_BaseMap"))
                    {
                        mat.SetTexture("_BaseMap", albedo);
                    }
                    else if (mat.HasProperty("_MainTex"))
                    {
                        mat.SetTexture("_MainTex", albedo);
                    }

                    if (normal != null && mat.HasProperty("_BumpMap"))
                    {
                        mat.SetTexture("_BumpMap", normal);
                        mat.EnableKeyword("_NORMALMAP");
                    }

                    if (orm != null)
                    {
                        if (mat.HasProperty("_PackedORMMap"))
                        {
                            mat.SetTexture("_PackedORMMap", orm);
                        }
                        else if (mat.HasProperty("_OcclusionMap"))
                        {
                            mat.SetTexture("_OcclusionMap", orm);
                        }
                    }

                    AssetDatabase.CreateAsset(mat, matPath);
                    litByPbrBase[baseName] = mat;
                }

                var preferredBase = GetPreferredPbrMaterialBase(asset);
                Material meshMat = null;
                if (!string.IsNullOrEmpty(preferredBase))
                {
                    litByPbrBase.TryGetValue(preferredBase, out meshMat);
                    if (meshMat == null)
                    {
                        meshMat = AssetDatabase.LoadAssetAtPath<Material>($"{relFolder}/Materials/{preferredBase}_Lit.mat");
                    }
                }

                if (meshMat == null)
                {
                    meshMat = FindFirstMaterialInFolder($"{relFolder}/Materials");
                }

                var orderedBases = GetOrderedPbrMaterialBases(asset);
                ApplyMaterialToImportedGlbMeshes(relFolder, meshMat, litByPbrBase, orderedBases);
                ApplyBoxCollidersToImportedGlbsIfNeeded(relFolder, asset);
            }

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            EditorUtility.DisplayDialog(
                "Immersive Studio",
                $"Import finished for job `{jobId}`. Assets live under Assets/ImmersiveStudioImports/{jobId}/.",
                "OK");
        }

        /// <summary>
        /// Match texture naming {variant}_{slot}_{role}.png — use first variant and first generated PBR slot.
        /// </summary>
        private static string GetPreferredPbrMaterialBase(AssetSpecDto asset)
        {
            if (asset == null || asset.variants == null || asset.variants.Length == 0)
            {
                return null;
            }

            if (asset.material_slots == null || asset.material_slots.Length == 0)
            {
                return null;
            }

            var vid = asset.variants[0].variant_id;
            foreach (var slot in asset.material_slots)
            {
                if (slot == null || string.IsNullOrEmpty(slot.id))
                {
                    continue;
                }

                var role = (slot.role ?? string.Empty).ToLowerInvariant();
                if (role == "albedo" || role == "normal" || role == "orm")
                {
                    return $"{vid}_{slot.id}";
                }
            }

            return $"{vid}_{asset.material_slots[0].id}";
        }

        /// <summary>
        /// Unique {variant}_{slot} keys in the same order as the worker texture loop (variant order, then PBR slots).
        /// </summary>
        private static List<string> GetOrderedPbrMaterialBases(AssetSpecDto asset)
        {
            var list = new List<string>();
            if (asset == null || asset.variants == null || asset.material_slots == null)
            {
                return list;
            }

            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var texSlots = new List<MaterialSlotDto>();
            foreach (var slot in asset.material_slots)
            {
                if (slot == null || string.IsNullOrEmpty(slot.id))
                {
                    continue;
                }

                var role = (slot.role ?? string.Empty).ToLowerInvariant();
                if (role == "albedo" || role == "normal" || role == "orm")
                {
                    texSlots.Add(slot);
                }
            }

            foreach (var v in asset.variants)
            {
                if (v == null || string.IsNullOrEmpty(v.variant_id))
                {
                    continue;
                }

                var vid = v.variant_id;
                foreach (var slot in texSlots)
                {
                    var key = $"{vid}_{slot.id}";
                    if (seen.Add(key))
                    {
                        list.Add(key);
                    }
                }
            }

            return list;
        }

        private static string StripImportedMaterialInstanceName(string rawName)
        {
            if (string.IsNullOrEmpty(rawName))
            {
                return string.Empty;
            }

            var idx = rawName.IndexOf(" (Instance)", StringComparison.Ordinal);
            if (idx > 0)
            {
                return rawName.Substring(0, idx);
            }

            return rawName;
        }

        private static bool ImportedMaterialMatchesPbrBase(string importedName, string pbrBase)
        {
            if (string.IsNullOrEmpty(importedName) || string.IsNullOrEmpty(pbrBase))
            {
                return false;
            }

            var a = StripImportedMaterialInstanceName(importedName).Trim();
            if (string.Equals(a, pbrBase, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            if (a.StartsWith(pbrBase + ".", StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            return false;
        }

        private static Material FindFirstMaterialInFolder(string materialsRelFolder)
        {
            if (string.IsNullOrEmpty(materialsRelFolder))
            {
                return null;
            }

            if (!AssetDatabase.IsValidFolder(materialsRelFolder))
            {
                return null;
            }

            var guids = AssetDatabase.FindAssets("t:Material", new[] { materialsRelFolder });
            if (guids == null || guids.Length == 0)
            {
                return null;
            }

            return AssetDatabase.LoadAssetAtPath<Material>(AssetDatabase.GUIDToAssetPath(guids[0]));
        }

        private static void ApplyMaterialToImportedGlbMeshes(
            string relFolder,
            Material fallbackMat,
            Dictionary<string, Material> litByPbrBase,
            List<string> orderedPbrBases)
        {
            var guids = AssetDatabase.FindAssets(string.Empty, new[] { relFolder });
            var hasMeshAsset = false;
            foreach (var g in guids)
            {
                var p = AssetDatabase.GUIDToAssetPath(g);
                if (p.IndexOf("/Materials/", System.StringComparison.Ordinal) >= 0)
                {
                    continue;
                }

                var e = Path.GetExtension(p);
                if (e.Equals(".glb", System.StringComparison.OrdinalIgnoreCase)
                    || e.Equals(".gltf", System.StringComparison.OrdinalIgnoreCase))
                {
                    hasMeshAsset = true;
                    break;
                }
            }

            var orderedMats = new List<Material>();
            if (orderedPbrBases != null)
            {
                foreach (var b in orderedPbrBases)
                {
                    if (string.IsNullOrEmpty(b))
                    {
                        continue;
                    }

                    if (litByPbrBase != null && litByPbrBase.TryGetValue(b, out var m) && m != null)
                    {
                        orderedMats.Add(m);
                    }
                }
            }

            if (fallbackMat == null && (litByPbrBase == null || litByPbrBase.Count == 0))
            {
                if (hasMeshAsset)
                {
                    Debug.LogWarning(
                        "[Immersive Studio] Found .glb but no generated Lit material — add textures or assign materials manually.");
                }

                return;
            }

            var assigned = 0;
            foreach (var guid in guids)
            {
                var path = AssetDatabase.GUIDToAssetPath(guid);
                if (path.IndexOf("/Materials/", System.StringComparison.Ordinal) >= 0)
                {
                    continue;
                }

                var ext = Path.GetExtension(path);
                if (!ext.Equals(".glb", System.StringComparison.OrdinalIgnoreCase)
                    && !ext.Equals(".gltf", System.StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                var root = AssetDatabase.LoadMainAssetAtPath(path) as GameObject;
                if (root == null)
                {
                    foreach (var sub in AssetDatabase.LoadAllAssetsAtPath(path))
                    {
                        if (sub is GameObject go && go.transform.parent == null)
                        {
                            root = go;
                            break;
                        }
                    }
                }

                if (root == null)
                {
                    continue;
                }

                foreach (var mr in root.GetComponentsInChildren<MeshRenderer>(true))
                {
                    AssignMaterialsToRenderer(
                        mr.sharedMaterials,
                        out var next,
                        fallbackMat,
                        litByPbrBase,
                        orderedMats);
                    mr.sharedMaterials = next;
                    EditorUtility.SetDirty(mr);
                    assigned++;
                }

                foreach (var smr in root.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                {
                    AssignMaterialsToRenderer(
                        smr.sharedMaterials,
                        out var next,
                        fallbackMat,
                        litByPbrBase,
                        orderedMats);
                    smr.sharedMaterials = next;
                    EditorUtility.SetDirty(smr);
                    assigned++;
                }

                EditorUtility.SetDirty(root);
            }

            if (assigned > 0)
            {
                Debug.Log($"[Immersive Studio] Updated materials on {assigned} renderer(s) under `{relFolder}`.");
            }
        }

        private static void AssignMaterialsToRenderer(
            Material[] current,
            out Material[] next,
            Material fallbackMat,
            Dictionary<string, Material> litByPbrBase,
            List<Material> orderedMats)
        {
            var n = current != null ? current.Length : 0;
            if (n == 0)
            {
                var single = PickSlotMaterial(0, null, fallbackMat, litByPbrBase, orderedMats);
                next = single != null ? new[] { single } : Array.Empty<Material>();
                return;
            }

            next = new Material[n];
            for (var i = 0; i < n; i++)
            {
                var cur = current[i];
                var nm = cur != null ? cur.name : string.Empty;
                next[i] = PickSlotMaterial(i, nm, fallbackMat, litByPbrBase, orderedMats);
            }
        }

        private static void ApplyBoxCollidersToImportedGlbsIfNeeded(string relFolder, AssetSpecDto asset)
        {
            if (asset?.unity == null || !string.Equals(asset.unity.collider, "box", StringComparison.OrdinalIgnoreCase))
            {
                return;
            }

            var guids = AssetDatabase.FindAssets(string.Empty, new[] { relFolder });
            foreach (var guid in guids)
            {
                var path = AssetDatabase.GUIDToAssetPath(guid);
                if (path.IndexOf("/Materials/", System.StringComparison.Ordinal) >= 0)
                {
                    continue;
                }

                var ext = Path.GetExtension(path);
                if (!ext.Equals(".glb", System.StringComparison.OrdinalIgnoreCase)
                    && !ext.Equals(".gltf", System.StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                var root = AssetDatabase.LoadMainAssetAtPath(path) as GameObject;
                if (root == null)
                {
                    foreach (var sub in AssetDatabase.LoadAllAssetsAtPath(path))
                    {
                        if (sub is GameObject go && go.transform.parent == null)
                        {
                            root = go;
                            break;
                        }
                    }
                }

                if (root == null)
                {
                    continue;
                }

                if (ImmersiveStudioColliderUtility.TryApplyBoxColliderIfConfigured(root, asset))
                {
                    EditorUtility.SetDirty(root);
                }
            }
        }

        private static Material PickSlotMaterial(
            int slotIndex,
            string importedMaterialName,
            Material fallbackMat,
            Dictionary<string, Material> litByPbrBase,
            List<Material> orderedMats)
        {
            if (litByPbrBase != null && litByPbrBase.Count > 0 && !string.IsNullOrEmpty(importedMaterialName))
            {
                foreach (var kv in litByPbrBase)
                {
                    if (ImportedMaterialMatchesPbrBase(importedMaterialName, kv.Key))
                    {
                        return kv.Value;
                    }
                }
            }

            if (orderedMats != null && orderedMats.Count > 0)
            {
                return orderedMats[slotIndex % orderedMats.Count];
            }

            return fallbackMat;
        }

        private sealed class PbrTextureSet
        {
            public string AlbedoPath;
            public string NormalPath;
            public string OrmPath;
        }

        private static Dictionary<string, PbrTextureSet> BuildPbrGroups(string relFolder)
        {
            var map = new Dictionary<string, PbrTextureSet>();
            var guids = AssetDatabase.FindAssets("t:Texture2D", new[] { relFolder });
            foreach (var guid in guids)
            {
                var texPath = AssetDatabase.GUIDToAssetPath(guid);
                if (!texPath.EndsWith(".png", System.StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                if (texPath.Contains("/Materials/", System.StringComparison.Ordinal))
                {
                    continue;
                }

                var fileName = Path.GetFileNameWithoutExtension(texPath);
                var m = s_pbrName.Match(fileName);
                if (!m.Success)
                {
                    continue;
                }

                var baseKey = m.Groups["base"].Value;
                var role = m.Groups["role"].Value.ToLowerInvariant();
                if (!map.TryGetValue(baseKey, out var set))
                {
                    set = new PbrTextureSet();
                    map[baseKey] = set;
                }

                switch (role)
                {
                    case "albedo":
                        set.AlbedoPath = texPath;
                        break;
                    case "normal":
                        set.NormalPath = texPath;
                        break;
                    case "orm":
                        set.OrmPath = texPath;
                        break;
                }
            }

            return map;
        }

        private static void ConfigureTextureImporter(string assetPath, TextureImporterType type, bool sRgb)
        {
            var importer = AssetImporter.GetAtPath(assetPath) as TextureImporter;
            if (importer == null)
            {
                return;
            }

            importer.textureType = type;
            importer.sRGBTexture = sRgb;
            importer.SaveAndReimport();
        }

        private static string SanitizeFileName(string value)
        {
            foreach (var c in Path.GetInvalidFileNameChars())
            {
                value = value.Replace(c, '_');
            }

            return string.IsNullOrEmpty(value) ? "job" : value;
        }
    }
}
