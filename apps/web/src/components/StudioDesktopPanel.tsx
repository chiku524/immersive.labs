import { invoke } from "@tauri-apps/api/core";
import { useCallback, useEffect, useRef, useState } from "react";
import { fetchDesktopServiceStatus } from "../desktop/desktopServiceChecks";
import { isTauriRuntime } from "../tauriRuntime";
import "./StudioDesktopPanel.css";

type ServiceCheck = { ok: boolean; detail: string };
type BlenderCheck = ServiceCheck & { path?: string | null };
type PrereqStatus = {
  ollama: ServiceCheck;
  comfy: ServiceCheck;
  api: ServiceCheck;
  blender: BlenderCheck;
  docker: ServiceCheck;
  repo_root: string;
  comfy_root?: string | null;
};

type DesktopSettings = {
  autoStartApi: boolean;
  autoStartComfy: boolean;
  closeToTray: boolean;
  openStudioWhenReady: boolean;
};

export { isTauriRuntime };

const HEALTH_POLL_MS = 60_000;

export function StudioDesktopPanel() {
  const [status, setStatus] = useState<PrereqStatus | null>(null);
  const [settings, setSettings] = useState<DesktopSettings | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const staticInfoRef = useRef<Pick<PrereqStatus, "blender" | "docker" | "repo_root" | "comfy_root"> | null>(
    null,
  );

  const loadStaticInfo = useCallback(async () => {
    if (!isTauriRuntime()) {
      return;
    }
    try {
      const next = await invoke<PrereqStatus>("check_prerequisites");
      staticInfoRef.current = {
        blender: next.blender,
        docker: next.docker,
        repo_root: next.repo_root,
        comfy_root: next.comfy_root,
      };
      setStatus((prev) => ({
        ...next,
        ollama: prev?.ollama ?? next.ollama,
        comfy: prev?.comfy ?? next.comfy,
        api: prev?.api ?? next.api,
      }));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    }
  }, []);

  const refreshHealth = useCallback(async (showBusy = false) => {
    if (!isTauriRuntime()) {
      return;
    }
    if (showBusy) {
      setBusy(true);
    }
    try {
      const live = await fetchDesktopServiceStatus();
      const base = staticInfoRef.current;
      setStatus((prev) => ({
        ollama: live.ollama,
        comfy: live.comfy,
        api: live.api,
        blender: base?.blender ?? prev?.blender ?? { ok: false, detail: "…" },
        docker: base?.docker ?? prev?.docker ?? { ok: false, detail: "…" },
        repo_root: base?.repo_root ?? prev?.repo_root ?? "",
        comfy_root: base?.comfy_root ?? prev?.comfy_root,
      }));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      if (showBusy) {
        setBusy(false);
      }
    }
  }, []);

  const refresh = useCallback(async () => {
    await loadStaticInfo();
    await refreshHealth(true);
  }, [loadStaticInfo, refreshHealth]);

  const loadSettings = useCallback(async () => {
    if (!isTauriRuntime()) {
      return;
    }
    try {
      const next = await invoke<DesktopSettings>("get_settings");
      setSettings(next);
    } catch {
      setSettings(null);
    }
  }, []);

  useEffect(() => {
    void loadStaticInfo();
    void loadSettings();
    void refreshHealth(false);

    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        void refreshHealth(false);
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        void refreshHealth(false);
      }
    }, HEALTH_POLL_MS);

    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.clearInterval(timer);
    };
  }, [loadStaticInfo, loadSettings, refreshHealth]);

  if (!isTauriRuntime()) {
    return null;
  }

  const apiReady = status?.api.ok ?? false;
  const comfyReady = status?.comfy.ok ?? false;
  const comfyInstalled = Boolean(status?.comfy_root);

  async function saveSettings(patch: Partial<DesktopSettings>) {
    if (!settings) {
      return;
    }
    const next = { ...settings, ...patch };
    setSettings(next);
    try {
      await invoke("save_settings", { settings: next });
      setMessage("Settings saved.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <section className="studio-desktop-panel" aria-label="Desktop controls">
      <div className="studio-desktop-panel-head">
        <strong>Desktop</strong>
        <span className="studio-desktop-panel-sub">Local worker controls</span>
        <button
          type="button"
          className="studio-desktop-settings-toggle"
          onClick={() => setShowSettings((v) => !v)}
          aria-expanded={showSettings}
        >
          {showSettings ? "Hide" : "Settings"}
        </button>
      </div>
      <div className="studio-desktop-panel-grid">
        <StatusPill label="API" ok={status?.api.ok} detail={status?.api.detail} />
        <StatusPill label="Ollama" ok={status?.ollama.ok} detail={status?.ollama.detail} />
        <StatusPill label="Blender" ok={status?.blender.ok} detail={status?.blender.detail} />
        <StatusPill label="Comfy" ok={status?.comfy.ok} detail={status?.comfy.detail} />
      </div>
      {showSettings && settings ? (
        <div className="studio-desktop-settings">
          <label className="studio-desktop-setting">
            <input
              type="checkbox"
              checked={settings.autoStartApi}
              onChange={(e) => void saveSettings({ autoStartApi: e.target.checked })}
            />
            <span>Auto-start API on launch</span>
          </label>
          <label className="studio-desktop-setting">
            <input
              type="checkbox"
              checked={settings.autoStartComfy}
              onChange={(e) => void saveSettings({ autoStartComfy: e.target.checked })}
            />
            <span>Auto-start ComfyUI on launch</span>
          </label>
          <label className="studio-desktop-setting">
            <input
              type="checkbox"
              checked={settings.closeToTray}
              onChange={(e) => void saveSettings({ closeToTray: e.target.checked })}
            />
            <span>Close to system tray</span>
          </label>
        </div>
      ) : null}
      <div className="studio-desktop-panel-actions">
        <button type="button" className="studio-retry" disabled={busy} onClick={() => void refresh()}>
          Refresh
        </button>
        <button
          type="button"
          className="studio-retry"
          disabled={busy}
          onClick={() => {
            void invoke<string>("run_worker_setup")
              .then((text) => setMessage(text))
              .catch((err) => {
                setMessage(err instanceof Error ? err.message : String(err));
              });
          }}
        >
          Run setup
        </button>
        <button
          type="button"
          className="studio-retry"
          disabled={busy || apiReady}
          onClick={() => {
            void (async () => {
              setBusy(true);
              setMessage(null);
              try {
                const text = await invoke<string>("start_worker");
                setMessage(text);
                await refreshHealth(true);
              } catch (err) {
                setMessage(err instanceof Error ? err.message : String(err));
              } finally {
                setBusy(false);
              }
            })();
          }}
        >
          Start API
        </button>
        <button
          type="button"
          className="studio-retry"
          disabled={busy || comfyReady || !comfyInstalled}
          title={
            comfyInstalled
              ? undefined
              : "ComfyUI not installed (optional). Install ComfyUI or set COMFYUI_ROOT in worker.env."
          }
          onClick={() => {
            void (async () => {
              setBusy(true);
              setMessage(null);
              try {
                const text = await invoke<string>("start_comfy");
                setMessage(text);
                await refreshHealth(true);
              } catch (err) {
                setMessage(err instanceof Error ? err.message : String(err));
              } finally {
                setBusy(false);
              }
            })();
          }}
        >
          Start Comfy
        </button>
        <button
          type="button"
          className="studio-retry"
          onClick={() => {
            void invoke("open_jobs_folder").catch((err) => {
              setMessage(err instanceof Error ? err.message : String(err));
            });
          }}
        >
          Jobs folder
        </button>
      </div>
      {message ? (
        <p className="studio-desktop-panel-message" role="status">
          {message}
        </p>
      ) : null}
    </section>
  );
}

function StatusPill({
  label,
  ok,
  detail,
}: {
  label: string;
  ok?: boolean;
  detail?: string;
}) {
  const klass = ok === undefined ? "unknown" : ok ? "ok" : "bad";
  return (
    <div className={`studio-desktop-pill studio-desktop-pill--${klass}`} title={detail}>
      <span>{label}</span>
      <span className="studio-desktop-pill-state">{ok === undefined ? "…" : ok ? "OK" : "—"}</span>
    </div>
  );
}
