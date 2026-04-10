using System.IO;
using UnityEditor;
using UnityEngine;

namespace ImmersiveLabs.Studio.Editor
{
    /// <summary>
    /// Applies <c>unity.collider</c> hints from a worker <c>spec.json</c> to the current selection.
    /// </summary>
    public static class ImmersiveStudioColliderUtility
    {
        private const string MenuPath = "Immersive Labs/Apply Box Collider From spec.json";

        [MenuItem(MenuPath, true)]
        private static bool ValidateApplyCollider()
        {
            return Selection.gameObjects != null && Selection.gameObjects.Length > 0;
        }

        /// <summary>
        /// When <c>unity.collider</c> is <c>box</c>, adds or updates a <see cref="BoxCollider"/>
        /// from renderer bounds (or <see cref="AssetSpecDto.target_height_m"/> fallback).
        /// </summary>
        /// <returns>True if a box collider was applied.</returns>
        public static bool TryApplyBoxColliderIfConfigured(GameObject go, AssetSpecDto spec)
        {
            if (spec?.unity == null || spec.unity.collider != "box")
            {
                return false;
            }

            ApplyBoxCollider(go, spec);
            return true;
        }

        [MenuItem(MenuPath)]
        public static void ApplyBoxColliderFromSpec()
        {
            var path = EditorUtility.OpenFilePanel("Select spec.json", Application.dataPath, "json");
            if (string.IsNullOrEmpty(path))
            {
                return;
            }

            var json = File.ReadAllText(path);
            if (json.Length > 0 && json[0] == '\uFEFF')
            {
                json = json.Substring(1);
            }

            var spec = JsonUtility.FromJson<AssetSpecDto>(json);
            if (spec == null || spec.unity == null)
            {
                EditorUtility.DisplayDialog("Immersive Studio", "spec.json could not be parsed.", "OK");
                return;
            }

            if (spec.unity.collider != "box")
            {
                EditorUtility.DisplayDialog(
                    "Immersive Studio",
                    $"Collider type `{spec.unity.collider}` is not automated yet. Only `box` is supported.",
                    "OK");
                return;
            }

            foreach (var go in Selection.gameObjects)
            {
                ApplyBoxCollider(go, spec);
            }

            EditorUtility.DisplayDialog(
                "Immersive Studio",
                "Applied BoxCollider to selection using spec bounds / target height fallback.",
                "OK");
        }

        private static void ApplyBoxCollider(GameObject go, AssetSpecDto spec)
        {
            var box = go.GetComponent<BoxCollider>();
            if (box == null)
            {
                box = go.AddComponent<BoxCollider>();
            }

            var rend = go.GetComponentInChildren<Renderer>();
            if (rend != null)
            {
                var b = rend.bounds;
                var t = go.transform;
                var inv = Quaternion.Inverse(t.rotation);
                box.center = inv * (b.center - t.position);
                var lossy = t.lossyScale;
                var sx = Mathf.Abs(lossy.x) < 1e-5f ? 1e-5f : lossy.x;
                var sy = Mathf.Abs(lossy.y) < 1e-5f ? 1e-5f : lossy.y;
                var sz = Mathf.Abs(lossy.z) < 1e-5f ? 1e-5f : lossy.z;
                box.size = new Vector3(b.size.x / sx, b.size.y / sy, b.size.z / sz);
                return;
            }

            var h = spec.target_height_m > 0.001f ? spec.target_height_m : 1f;
            box.center = new Vector3(0f, h * 0.5f, 0f);
            box.size = new Vector3(h * 0.6f, h, h * 0.6f);
        }
    }
}
