using System;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEngine;

namespace ImmersiveLabs.Studio.Editor
{
    internal enum StudioGlbRole
    {
        Main,
        Collider,
        Lod,
        Unknown,
    }

    internal sealed class StudioGlbEntry
    {
        public string AssetPath;
        public StudioGlbRole Role;
        public int LodIndex;
    }

    /// <summary>
    /// Classifies worker GLB filenames and applies collider / LOD assembly after import.
    /// </summary>
    internal static class ImmersiveStudioGlbUtility
    {
        private static readonly Regex s_lodName = new Regex(
            @"_LOD(?<n>\d+)$",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        internal static List<StudioGlbEntry> ClassifyGlbs(string relFolder, string assetId)
        {
            var list = new List<StudioGlbEntry>();
            if (string.IsNullOrEmpty(relFolder) || string.IsNullOrEmpty(assetId))
            {
                return list;
            }

            var guids = AssetDatabase.FindAssets(string.Empty, new[] { relFolder });
            foreach (var guid in guids)
            {
                var path = AssetDatabase.GUIDToAssetPath(guid);
                if (path.IndexOf("/Materials/", StringComparison.Ordinal) >= 0)
                {
                    continue;
                }

                var ext = Path.GetExtension(path);
                if (!ext.Equals(".glb", StringComparison.OrdinalIgnoreCase)
                    && !ext.Equals(".gltf", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                var fileStem = Path.GetFileNameWithoutExtension(path);
                var role = StudioGlbRole.Unknown;
                var lodIndex = 0;
                if (string.Equals(fileStem, assetId, StringComparison.OrdinalIgnoreCase))
                {
                    role = StudioGlbRole.Main;
                }
                else if (fileStem.EndsWith("_collider", StringComparison.OrdinalIgnoreCase)
                         && fileStem.StartsWith(assetId, StringComparison.OrdinalIgnoreCase))
                {
                    role = StudioGlbRole.Collider;
                }
                else
                {
                    var m = s_lodName.Match(fileStem);
                    if (m.Success
                        && fileStem.StartsWith(assetId, StringComparison.OrdinalIgnoreCase))
                    {
                        role = StudioGlbRole.Lod;
                        if (!int.TryParse(m.Groups["n"].Value, out lodIndex))
                        {
                            lodIndex = 1;
                        }
                    }
                }

                list.Add(new StudioGlbEntry
                {
                    AssetPath = path,
                    Role = role,
                    LodIndex = lodIndex,
                });
            }

            list.Sort((a, b) =>
            {
                var ra = RoleSortKey(a);
                var rb = RoleSortKey(b);
                var cmp = ra.CompareTo(rb);
                return cmp != 0 ? cmp : string.Compare(a.AssetPath, b.AssetPath, StringComparison.OrdinalIgnoreCase);
            });
            return list;
        }

        private static int RoleSortKey(StudioGlbEntry e)
        {
            switch (e.Role)
            {
                case StudioGlbRole.Main:
                    return 0;
                case StudioGlbRole.Lod:
                    return 10 + e.LodIndex;
                case StudioGlbRole.Collider:
                    return 100;
                default:
                    return 200;
            }
        }

        internal static bool IsRenderableGlb(StudioGlbEntry entry)
        {
            return entry != null
                   && (entry.Role == StudioGlbRole.Main || entry.Role == StudioGlbRole.Lod);
        }

        internal static GameObject LoadImportedRoot(string assetPath)
        {
            if (string.IsNullOrEmpty(assetPath))
            {
                return null;
            }

            var root = AssetDatabase.LoadMainAssetAtPath(assetPath) as GameObject;
            if (root != null)
            {
                return root;
            }

            foreach (var sub in AssetDatabase.LoadAllAssetsAtPath(assetPath))
            {
                if (sub is GameObject go && go.transform.parent == null)
                {
                    return go;
                }
            }

            return null;
        }

        internal static void HideRenderers(GameObject root)
        {
            if (root == null)
            {
                return;
            }

            foreach (var r in root.GetComponentsInChildren<Renderer>(true))
            {
                r.enabled = false;
            }
        }

        internal static Mesh ExtractFirstMesh(GameObject root)
        {
            if (root == null)
            {
                return null;
            }

            var mf = root.GetComponentInChildren<MeshFilter>(true);
            if (mf != null && mf.sharedMesh != null)
            {
                return mf.sharedMesh;
            }

            var smr = root.GetComponentInChildren<SkinnedMeshRenderer>(true);
            return smr != null ? smr.sharedMesh : null;
        }

        internal static bool TryApplyConvexMeshCollider(GameObject mainRoot, string colliderAssetPath)
        {
            if (mainRoot == null || string.IsNullOrEmpty(colliderAssetPath))
            {
                return false;
            }

            var colliderRoot = LoadImportedRoot(colliderAssetPath);
            if (colliderRoot == null)
            {
                return false;
            }

            var mesh = ExtractFirstMesh(colliderRoot);
            HideRenderers(colliderRoot);
            if (mesh == null)
            {
                return false;
            }

            var mc = mainRoot.GetComponent<MeshCollider>();
            if (mc == null)
            {
                mc = mainRoot.AddComponent<MeshCollider>();
            }

            mc.sharedMesh = mesh;
            mc.convex = true;
            EditorUtility.SetDirty(mainRoot);
            return true;
        }

        internal static bool TryBuildLodGroup(
            GameObject mainRoot,
            IReadOnlyList<StudioGlbEntry> entries)
        {
            if (mainRoot == null || entries == null || entries.Count == 0)
            {
                return false;
            }

            var lodEntries = new List<StudioGlbEntry>();
            foreach (var e in entries)
            {
                if (e.Role == StudioGlbRole.Lod)
                {
                    lodEntries.Add(e);
                }
            }

            if (lodEntries.Count == 0)
            {
                return false;
            }

            lodEntries.Sort((a, b) => a.LodIndex.CompareTo(b.LodIndex));
            var lods = new List<LOD>();
            var mainRenderers = mainRoot.GetComponentsInChildren<Renderer>(true);
            if (mainRenderers.Length > 0)
            {
                lods.Add(new LOD(0.6f, mainRenderers));
            }

            var step = 0.45f / Math.Max(lodEntries.Count, 1);
            var transition = 0.6f - step;
            foreach (var lod in lodEntries)
            {
                var lodRoot = LoadImportedRoot(lod.AssetPath);
                if (lodRoot == null)
                {
                    continue;
                }

                lodRoot.transform.SetParent(mainRoot.transform, false);
                var rend = lodRoot.GetComponentsInChildren<Renderer>(true);
                if (rend.Length == 0)
                {
                    continue;
                }

                transition = Math.Max(0.05f, transition - step);
                lods.Add(new LOD(transition, rend));
            }

            if (lods.Count <= 1)
            {
                return false;
            }

            var group = mainRoot.GetComponent<LODGroup>();
            if (group == null)
            {
                group = mainRoot.AddComponent<LODGroup>();
            }

            group.SetLODs(lods.ToArray());
            group.RecalculateBounds();
            EditorUtility.SetDirty(mainRoot);
            return true;
        }
    }
}
