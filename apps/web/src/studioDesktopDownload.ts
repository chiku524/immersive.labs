/** GitHub Release tag for Immersive Studio desktop installers. */
export const STUDIO_DESKTOP_RELEASE_TAG = "studio-desktop-v0.1.0";

export const STUDIO_DESKTOP_VERSION = "0.1.0";

const GITHUB_REPO = "chiku524/immersive.labs";

function releaseBase(): string {
  const fromEnv = import.meta.env.VITE_STUDIO_DESKTOP_RELEASE_BASE?.trim();
  if (fromEnv) {
    return fromEnv.replace(/\/$/, "");
  }
  return `https://github.com/${GITHUB_REPO}/releases/download/${STUDIO_DESKTOP_RELEASE_TAG}`;
}

/** Link to the release page (all platform assets + notes). */
export function studioDesktopReleasePageUrl(): string {
  return `https://github.com/${GITHUB_REPO}/releases/tag/${STUDIO_DESKTOP_RELEASE_TAG}`;
}

/** Direct NSIS installer URL (Windows x64). */
export function studioDesktopWindowsInstallerUrl(): string {
  return `${releaseBase()}/Immersive%20Studio_${STUDIO_DESKTOP_VERSION}_x64-setup.exe`;
}

/** Direct MSI URL (Windows x64, alternative). */
export function studioDesktopWindowsMsiUrl(): string {
  return `${releaseBase()}/Immersive%20Studio_${STUDIO_DESKTOP_VERSION}_x64_en-US.msi`;
}
