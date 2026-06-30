import { useEffect, useState } from "react";
import { isTauriRuntime } from "../tauriRuntime";
import {
  STUDIO_DESKTOP_PRODUCT_FILE,
  STUDIO_DESKTOP_VERSION,
  studioDesktopDownloadOffer,
  studioDesktopDownloadOfferAsync,
  studioDesktopReleasePageUrl,
  studioDesktopSetupOneLiner,
  studioDesktopSetupScriptUrl,
  studioDesktopWindowsMsiUrl,
  type DesktopDownloadOffer,
} from "../studioDesktopDownload";
import "./StudioDesktopDownloadCTA.css";

function openInstallerDownload(href: string, filename: string) {
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

function InstallerDownloadButton({
  className,
  offer,
}: {
  className: string;
  offer: DesktopDownloadOffer;
}) {
  if (!offer.filename) {
    return (
      <a
        className={className}
        href={offer.href}
        target="_blank"
        rel="noopener noreferrer"
      >
        {offer.label}
      </a>
    );
  }

  return (
    <a
      className={className}
      href={offer.href}
      download={offer.filename}
      onClick={(event) => {
        event.preventDefault();
        openInstallerDownload(offer.href, offer.filename!);
      }}
    >
      {offer.label}
    </a>
  );
}

export function StudioDesktopDownloadCTA({ compact = false }: { compact?: boolean }) {
  const [offer, setOffer] = useState<DesktopDownloadOffer>(() => studioDesktopDownloadOffer());

  useEffect(() => {
    void studioDesktopDownloadOfferAsync().then(setOffer);
  }, []);

  if (isTauriRuntime()) {
    return null;
  }

  const os = offer.os;
  const isWindows = os === "windows";

  if (compact) {
    return <InstallerDownloadButton className="btn btn-primary studio-desktop-download-compact" offer={offer} />;
  }

  return (
    <div className="studio-desktop-download-cta" id="desktop-setup">
      <p className="studio-desktop-download-steps">
        <strong>Immersive Studio desktop app</strong> — local-first Game Studio (Tripo 3D, Ollama specs,
        optional ComfyUI). Two steps on Windows:
      </p>
      <ol className="studio-desktop-download-step-list">
        <li>Install the desktop app for your OS.</li>
        <li>
          {isWindows ? (
            <>
              Run one-time worker setup (Python + PyPI <code>immersive-studio</code>, Tripo/Blender config) — use the
              button below or <strong>Run setup</strong> inside the app.
            </>
          ) : (
            <>
              Install Python 3.11+, <code>pip install immersive-studio</code>, and configure{" "}
              <code>STUDIO_TRIPO_API_KEY</code> — see{" "}
              <a href={studioDesktopReleasePageUrl()} target="_blank" rel="noopener noreferrer">
                release notes
              </a>
              .
            </>
          )}
        </li>
      </ol>
      <div className="studio-desktop-download-actions">
        <InstallerDownloadButton className="btn btn-primary studio-desktop-download-btn" offer={offer} />
        {isWindows ? (
          <a
            className="btn btn-secondary studio-desktop-download-btn"
            href={studioDesktopSetupScriptUrl()}
            download="setup-desktop-studio.ps1"
          >
            Download setup script
          </a>
        ) : null}
        {isWindows ? (
          <InstallerDownloadButton
            className="btn btn-ghost studio-desktop-download-btn"
            offer={{
              os: "windows",
              href: studioDesktopWindowsMsiUrl(),
              label: "Windows MSI",
              filename: `${STUDIO_DESKTOP_PRODUCT_FILE}_${STUDIO_DESKTOP_VERSION}_x64_en-US.msi`,
            }}
          />
        ) : null}
        <a
          className="btn btn-ghost studio-desktop-download-btn"
          href={studioDesktopReleasePageUrl()}
          target="_blank"
          rel="noopener noreferrer"
        >
          All platforms
        </a>
      </div>
      {isWindows ? (
        <p className="studio-desktop-download-note">
          Or paste in PowerShell: <code className="studio-desktop-oneliner">{studioDesktopSetupOneLiner()}</code>
        </p>
      ) : null}
      <p className="studio-desktop-download-note">
        Requires Python 3.11+ for the worker, <code>STUDIO_TRIPO_API_KEY</code> for prompt-faithful meshes (Blender
        fallback included), plus Ollama for real specs. Optional ComfyUI on :8188 for extra textures. Windows SmartScreen
        may warn until the app is code-signed.
      </p>
      {os === "macos" && offer.macArch ? (
        <p className="studio-desktop-download-note">
          Detected {offer.macArch === "aarch64" ? "Apple Silicon" : "Intel"} Mac — wrong build? Pick the other{" "}
          <code>.dmg</code> on{" "}
          <a href={studioDesktopReleasePageUrl()} target="_blank" rel="noopener noreferrer">
            GitHub Releases
          </a>
          .
        </p>
      ) : null}
    </div>
  );
}

/** Nav/header chip — direct installer download when OS is known. */
export function StudioDesktopDownloadNavLink() {
  if (isTauriRuntime()) {
    return null;
  }
  const offer = studioDesktopDownloadOffer();
  if (offer.filename) {
    return <InstallerDownloadButton className="nav-download" offer={{ ...offer, label: "Download app" }} />;
  }
  const onStudio = typeof window !== "undefined" && window.location.pathname.startsWith("/studio");
  return (
    <a className="nav-download" href={onStudio ? "#desktop-setup" : "/studio#desktop-setup"}>
      Download app
    </a>
  );
}
