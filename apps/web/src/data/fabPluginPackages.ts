/**
 * Full Fab marketplace drops: RunUAT BuildPlugin output, zipped (Win64) per
 * fab-products/scripts/build-fab-marketplace-drops-ue57.ps1.
 *
 * Filenames here must match the zips in fab-products/fab-marketplace-drops/UE5.7-Win64/
 * after sync: scripts/sync-fab-plugin-zips-to-web.ps1 → public/plugin-packages/UE5.7-Win64/
 */
export const PLUGIN_ZIP_DIR = "plugin-packages/UE5.7-Win64";

/** Matches the zip suffix in build-fab-marketplace-drops-ue57.ps1 ($Ue = "5.7"). */
export const MARKETPLACE_ZIP_PREFIX = "UE5.7-Win64";

export type FabPluginPackage = {
  slug: string;
  /** Product name for page titles and cards */
  name: string;
  shortName: string;
  /**
   * Exact zip filename (must match RunUAT output, e.g. HarborSuite-UE5.7-Win64.zip).
   * Used for `href` and the browser download attribute.
   */
  zipFile: string;
  description: string;
  installNote: string;
  /** Category line on /fab-products cards */
  tag: string;
  /** One-line blurb on /fab-products */
  cardBlurb: string;
  /**
   * Top-level folder name inside the .zip (matches fab-products build: `{ProductId}-UE5.7-Win64`).
   */
  packagedRootFolder: string;
};

export const fabPluginPackages: readonly FabPluginPackage[] = [
  {
    slug: "harbor-suite",
    name: "Harbor Suite (Fab plugin)",
    shortName: "Harbor Suite",
    zipFile: "HarborSuite-UE5.7-Win64.zip",
    description:
      "Pre-production and shipping gates for Unreal. Editor plugin + small runtime. Full marketplace drop (Win64, UE 5.7).",
    installNote:
      "Unzip; copy the folder below into your project’s Plugins (or engine plugins), enable, rebuild. You may rename the plugin subfolder to match your pipeline.",
    tag: "Unreal · Editor workflow",
    cardBlurb:
      "RunUAT-packaged editor + runtime: charts, stowage, shakedown, clearance gates—drop into a project or engine plugins.",
    packagedRootFolder: "HarborSuite-UE5.7-Win64",
  },
  {
    slug: "level-selection-sets",
    name: "Level Selection Sets (Fab plugin)",
    shortName: "Level Selection Sets",
    zipFile: "LevelSelectionSets-UE5.7-Win64.zip",
    description:
      "Data-only editor workflow for per-level and cross-level actor sets. Full marketplace drop (Win64, UE 5.7).",
    installNote:
      "Unzip; copy the folder below into your project’s Plugins, enable, rebuild. You may rename the plugin subfolder to match your pipeline.",
    tag: "Unreal · Editor",
    cardBlurb:
      "RunUAT-packaged editor plugin: save and recall named actor selection sets per level and across levels.",
    packagedRootFolder: "LevelSelectionSets-UE5.7-Win64",
  },
  {
    slug: "worldbuilder-templates",
    name: "World Builder Templates (Fab plugin)",
    shortName: "World Builder Templates",
    zipFile: "WorldBuilderTemplates-UE5.7-Win64.zip",
    description:
      "Procedural and template-driven world blockout. Full marketplace drop (Win64, UE 5.7).",
    installNote:
      "Unzip; copy the folder below into your project’s Plugins, enable, rebuild. You may rename the plugin subfolder to match your pipeline.",
    tag: "Unreal · World templates",
    cardBlurb:
      "RunUAT-packaged editor plugin: ready-made world maps and template-driven blockout from the content browser.",
    packagedRootFolder: "WorldBuilderTemplates-UE5.7-Win64",
  },
  {
    slug: "workflow-toolkit",
    name: "Workflow Toolkit (Fab plugin)",
    shortName: "Workflow Toolkit",
    zipFile: "WorkflowToolkit-UE5.7-Win64.zip",
    description: "Editor workflow helpers. Full marketplace drop (Win64, UE 5.7).",
    installNote:
      "Unzip; copy the folder below into your project’s Plugins, enable, rebuild. You may rename the plugin subfolder to match your pipeline.",
    tag: "Unreal · Editor + runtime",
    cardBlurb:
      "RunUAT-packaged editor + runtime: shortcut panel and game-instance utilities for PIE and dev iteration.",
    packagedRootFolder: "WorkflowToolkit-UE5.7-Win64",
  },
  {
    slug: "worldbuilder-audit-convert",
    name: "World Builder Audit/Convert (Fab plugin)",
    shortName: "World Builder Audit/Convert",
    zipFile: "WorldBuilderAuditConvert-UE5.7-Win64.zip",
    description:
      "Editor utilities for audit and batch conversion toward instancing. Full marketplace drop (Win64, UE 5.7).",
    installNote:
      "Unzip; copy the folder below into your project’s Plugins, enable, rebuild. You may rename the plugin subfolder to match your pipeline.",
    tag: "Unreal · Editor",
    cardBlurb:
      "RunUAT-packaged editor plugin: audit levels and batch toward ISM/HISM with presets, preview, and reports.",
    packagedRootFolder: "WorldBuilderAuditConvert-UE5.7-Win64",
  },
];

export const fabPluginPackageBySlug: ReadonlyMap<string, FabPluginPackage> = new Map(
  fabPluginPackages.map((p) => [p.slug, p] as const),
);

export const fabPluginUrlPath = (pkg: Pick<FabPluginPackage, "zipFile">) =>
  `/${PLUGIN_ZIP_DIR.replace(/\/$/, "")}/${pkg.zipFile}`;
