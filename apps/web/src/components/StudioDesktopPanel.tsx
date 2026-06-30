import { invoke } from "@tauri-apps/api/core";
import { useCallback, useEffect, useState } from "react";
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

export function StudioDesktopPanel() {
  const [status, setStatus] = useState<PrereqStatus | null>(null);
  const [settings, setSettings] = useState<DesktopSettings | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  const refresh = useCallback(async () => {
    if (!isTauriRuntime()) {
      return;
    }
    setBusy(true);
    try {
      const next = await invoke<PrereqStatus>("check_prerequisites");
      setStatus(next);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, []);

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
    void refresh();
    void loadSettings();
    const timer = window.setInterval(() => void refresh(), 15_000);
    return () => window.clearInterval(timer);
  }, [refresh, loadSettings]);

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
                await refresh();
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
                await refresh();
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
