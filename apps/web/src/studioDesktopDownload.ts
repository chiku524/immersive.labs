/** GitHub Release tag for Immersive Studio desktop installers. */
export const STUDIO_DESKTOP_RELEASE_TAG = "studio-desktop-v0.1.1";

export const STUDIO_DESKTOP_VERSION = "0.1.1";

/** Tauri bundle base name on GitHub (spaces become dots in release asset names). */
export const STUDIO_DESKTOP_PRODUCT_FILE = "Immersive.Studio";

const GITHUB_REPO = "chiku524/immersive.labs";

const SITE_ORIGIN =
  typeof window !== "undefined" && window.location?.origin
    ? window.location.origin
    : "https://immersivelabs.space";

export type DesktopOs = "windows" | "macos" | "linux" | "other";

export type DesktopDownloadOffer = {
  os: DesktopOs;
  href: string;
  label: string;
  filename: string | null;
  /** macOS only — best-effort from client hints */
  macArch?: "aarch64" | "x64";
};

function releaseBase(): string {
  const fromEnv = import.meta.env.VITE_STUDIO_DESKTOP_RELEASE_BASE?.trim();
  if (fromEnv) {
    return fromEnv.replace(/\/$/, "");
  }
  return `https://github.com/${GITHUB_REPO}/releases/download/${STUDIO_DESKTOP_RELEASE_TAG}`;
}

export function studioDesktopAssetUrl(filename: string): string {
  return `${releaseBase()}/${encodeURIComponent(filename)}`;
}

/** Link to the release page (all platform assets + notes). */
export function studioDesktopReleasePageUrl(): string {
  return `https://github.com/${GITHUB_REPO}/releases/tag/${STUDIO_DESKTOP_RELEASE_TAG}`;
}

function assetFilename(os: DesktopOs, macArch: "aarch64" | "x64" = "aarch64"): string {
  const v = STUDIO_DESKTOP_VERSION;
  const p = STUDIO_DESKTOP_PRODUCT_FILE;
  switch (os) {
    case "windows":
      return `${p}_${v}_x64-setup.exe`;
    case "macos":
      return macArch === "x64" ? `${p}_${v}_x64.dmg` : `${p}_${v}_aarch64.dmg`;
    case "linux":
      return `${p}_${v}_amd64.AppImage`;
    default:
      return `${p}_${v}_x64-setup.exe`;
  }
}

export function detectDesktopOs(): DesktopOs {
  if (typeof navigator === "undefined") {
    return "other";
  }
  const ua = navigator.userAgent || "";
  const platform = navigator.platform || "";
  if (/Win/i.test(platform) || /Windows/i.test(ua)) {
    return "windows";
  }
  if (/Mac/i.test(platform) || /Macintosh/i.test(ua)) {
    return "macos";
  }
  if (/Linux/i.test(platform) || /Linux/i.test(ua)) {
    return "linux";
  }
  return "other";
}

/** Best-effort sync mac arch (refined async via `resolveMacArch`). */
export function guessMacArch(): "aarch64" | "x64" {
  if (typeof navigator === "undefined") {
    return "aarch64";
  }
  const ua = navigator.userAgent || "";
  if (/Intel Mac OS X/i.test(ua)) {
    return "x64";
  }
  return "aarch64";
}

export async function resolveMacArch(): Promise<"aarch64" | "x64"> {
  const nav = navigator as Navigator & {
    userAgentData?: {
      getHighEntropyValues?: (hints: string[]) => Promise<{ architecture?: string }>;
    };
  };
  try {
    const values = await nav.userAgentData?.getHighEntropyValues?.(["architecture"]);
    const arch = values?.architecture?.toLowerCase();
    if (arch === "x86" || arch === "x64") {
      return "x64";
    }
    if (arch === "arm" || arch === "aarch64") {
      return "aarch64";
    }
  } catch {
    /* ignore */
  }
  return guessMacArch();
}

export function studioDesktopDownloadOffer(
  os: DesktopOs = detectDesktopOs(),
  macArch: "aarch64" | "x64" = guessMacArch(),
): DesktopDownloadOffer {
  if (os === "other") {
    return {
      os,
      href: studioDesktopReleasePageUrl(),
      label: "Download desktop app",
      filename: null,
    };
  }

  const filename = assetFilename(os, macArch);
  const labels: Record<DesktopOs, string> = {
    windows: "Download for Windows",
    macos:
      macArch === "x64" ? "Download for macOS (Intel)" : "Download for macOS (Apple Silicon)",
    linux: "Download for Linux (AppImage)",
    other: "Download desktop app",
  };

  return {
    os,
    href: studioDesktopAssetUrl(filename),
    label: labels[os],
    filename,
    macArch: os === "macos" ? macArch : undefined,
  };
}

export async function studioDesktopDownloadOfferAsync(): Promise<DesktopDownloadOffer> {
  const os = detectDesktopOs();
  if (os === "macos") {
    const macArch = await resolveMacArch();
    return studioDesktopDownloadOffer(os, macArch);
  }
  return studioDesktopDownloadOffer(os);
}

/** Direct NSIS installer URL (Windows x64). */
export function studioDesktopWindowsInstallerUrl(): string {
  return studioDesktopAssetUrl(assetFilename("windows"));
}

/** Direct MSI URL (Windows x64, alternative). */
export function studioDesktopWindowsMsiUrl(): string {
  return studioDesktopAssetUrl(`${STUDIO_DESKTOP_PRODUCT_FILE}_${STUDIO_DESKTOP_VERSION}_x64_en-US.msi`);
}

/** Hosted one-time worker setup script (PyPI venv + worker.env). */
export function studioDesktopSetupScriptUrl(): string {
  return `${SITE_ORIGIN}/downloads/setup-desktop-studio.ps1`;
}

/** PowerShell one-liner to download and run setup (Windows). */
export function studioDesktopSetupOneLiner(): string {
  return `irm ${studioDesktopSetupScriptUrl()} | iex`;
}
