import { useState, useEffect, useRef } from "react";
import { useDesktopUpdate } from "./DesktopUpdateContext";
import { isTauriRuntime } from "../tauriRuntime";
import "./desktop-splash.css";

const INTRO_DURATION_MS = 1800;
const BRAND_MARK = "/brand-mark.png";

/**
 * Frameless splash: staggered logo / title / tagline → quiet update check → main window.
 */
export function DesktopSplashGate() {
  const desktopUpdate = useDesktopUpdate();
  const [introDone, setIntroDone] = useState(false);
  const [postUpdate, setPostUpdate] = useState(false);
  const updateCancelledRef = useRef(false);

  useEffect(() => {
    if (!isTauriRuntime()) {
      setIntroDone(true);
      return;
    }
    const t = setTimeout(() => setIntroDone(true), INTRO_DURATION_MS);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (!introDone || !isTauriRuntime()) return;
    updateCancelledRef.current = false;

    const setPhase = desktopUpdate?.setPhase;
    const setPendingUpdateVersion = desktopUpdate?.setPendingUpdateVersion;

    const run = async () => {
      try {
        const { check } = await import("@tauri-apps/plugin-updater");
        const { relaunch } = await import("@tauri-apps/plugin-process");

        const update = await check();
        if (updateCancelledRef.current) return;

        if (update) {
          setPendingUpdateVersion?.(update.version);
          setPhase?.("downloading");
          await update.downloadAndInstall((ev) => {
            if (ev.event === "Finished") setPhase?.("installing");
          });
          setPhase?.("restarting");
          await relaunch();
          return;
        }
      } catch {
        /* missing updater / network errors do not block launch */
      }

      if (updateCancelledRef.current) return;
      setPostUpdate(true);
    };

    void run();
    return () => {
      updateCancelledRef.current = true;
    };
  }, [introDone, desktopUpdate?.setPhase, desktopUpdate?.setPendingUpdateVersion]);

  useEffect(() => {
    if (!postUpdate || !isTauriRuntime()) return;

    void (async () => {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        await invoke("close_splash_and_show_main");
      } catch {
        /* ignore */
      }
    })();
  }, [postUpdate]);

  if (!isTauriRuntime()) return null;

  return (
    <main className="desktop-splash" aria-busy={!postUpdate}>
      <div className="desktop-splash__content">
        <div className="desktop-splash__symbol" aria-hidden>
          <img src={BRAND_MARK} alt="" width={72} height={72} />
        </div>
        <h1 className="desktop-splash__name">Immersive Studio</h1>
        <p className="desktop-splash__tagline">Local-first 3D from prompts</p>
      </div>
    </main>
  );
}
