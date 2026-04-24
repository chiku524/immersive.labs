/**
 * Full Fab marketplace drop zips (RunUAT packaged plugins), not demo sample zips.
 * Zips are synced from fab-products/fab-marketplace-drops/UE5.7-Win64/ via
 * scripts/sync-fab-plugin-zips-to-web.ps1 into public/plugin-packages/UE5.7-Win64/
 */
export const PLUGIN_ZIP_DIR = "plugin-packages/UE5.7-Win64";

export type FabPluginPackage = {
  slug: string;
  name: string;
  shortName: string;
  /** Filename under PLUGIN_ZIP_DIR (must match build-fab-marketplace-drops-ue57.ps1 output) */
  zipFile: string;
  description: string;
  /** Optional: short install note (paths are plugin-relative) */
  installNote: string;
};

export const fabPluginPackages: readonly FabPluginPackage[] = [
  {
    slug: "harbor-suite",
    name: "Harbor Suite (Fab plugin)",
    shortName: "Harbor Suite",
    zipFile: "HarborSuite-UE5.7-Win64.zip",
    description:
      "Pre-production and shipping gates for Unreal. Editor plugin + small runtime. Full marketplace drop (Win64, UE 5.7).",
    installNote: "Unzip, copy Plugins/HarborSuite into your project (or engine plugins), enable, rebuild.",
  },
  {
    slug: "level-selection-sets",
    name: "Level Selection Sets (Fab plugin)",
    shortName: "Level Selection Sets",
    zipFile: "LevelSelectionSets-UE5.7-Win64.zip",
    description:
      "Data-only editor workflow for per-level and cross-level actor sets. Full marketplace drop (Win64, UE 5.7).",
    installNote: "Unzip, copy Plugins/LevelSelectionSets into your project, enable, rebuild.",
  },
  {
    slug: "worldbuilder-templates",
    name: "World Builder Templates (Fab plugin)",
    shortName: "World Builder Templates",
    zipFile: "WorldBuilderTemplates-UE5.7-Win64.zip",
    description:
      "Procedural and template-driven world blockout. Full marketplace drop (Win64, UE 5.7).",
    installNote: "Unzip, copy Plugins/WorldBuilderTemplates into your project, enable, rebuild.",
  },
  {
    slug: "workflow-toolkit",
    name: "Workflow Toolkit (Fab plugin)",
    shortName: "Workflow Toolkit",
    zipFile: "WorkflowToolkit-UE5.7-Win64.zip",
    description:
      "Editor workflow helpers. Full marketplace drop (Win64, UE 5.7).",
    installNote: "Unzip, copy Plugins/WorkflowToolkit into your project, enable, rebuild.",
  },
  {
    slug: "worldbuilder-audit-convert",
    name: "World Builder Audit/Convert (Fab plugin)",
    shortName: "World Builder Audit/Convert",
    zipFile: "WorldBuilderAuditConvert-UE5.7-Win64.zip",
    description:
      "Editor utilities for audit and conversion. Full marketplace drop (Win64, UE 5.7).",
    installNote: "Unzip, copy Plugins/WorldBuilderAuditConvert into your project, enable, rebuild.",
  },
];

export const fabPluginPackageBySlug: ReadonlyMap<string, FabPluginPackage> = new Map(
  fabPluginPackages.map((p) => [p.slug, p] as const),
);

export const fabPluginUrlPath = (pkg: Pick<FabPluginPackage, "zipFile">) =>
  `/${PLUGIN_ZIP_DIR.replace(/\/$/, "")}/${pkg.zipFile}`;
