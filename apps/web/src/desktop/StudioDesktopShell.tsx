import { useEffect, useCallback, useRef } from "react";
import { useLocation } from "react-router-dom";
import { isTauriRuntime } from "../tauriRuntime";
import { useDesktopUpdate } from "./DesktopUpdateContext";
import { useDesktopUpdater } from "./useDesktopUpdater";

/** Wires tray "Check for Updates" and periodic updater checks on the main window only. */
export function StudioDesktopShell() {
  const location = useLocation();
  const desktopUpdate = useDesktopUpdate();
  const skipUpdaterOnSplash = isTauriRuntime() && location.pathname === "/desktop/splash";

  useDesktopUpdater(
    desktopUpdate && !skipUpdaterOnSplash
      ? {
          setPhase: desktopUpdate.setPhase,
          setPendingUpdateVersion: desktopUpdate.setPendingUpdateVersion,
          registerRetry: desktopUpdate.registerRetry,
        }
      : null,
  );

  useDesktopMenuEvents(desktopUpdate);

  return null;
}

function useDesktopMenuEvents(
  updateContext: ReturnType<typeof useDesktopUpdate>,
) {
  const unlistensRef = useRef<Array<() => void>>([]);

  const handleCheckUpdates = useCallback(() => {
    if (updateContext?.registerRetry) {
      updateContext.setPhase("checking");
      updateContext.retryUpdate();
    }
  }, [updateContext]);

  useEffect(() => {
    if (!isTauriRuntime()) return;
    unlistensRef.current = [];
    import("@tauri-apps/api/event")
      .then((event) =>
        event
          .listen("menu-check-updates", () => handleCheckUpdates())
          .then((u) => unlistensRef.current.push(u)),
      )
      .catch((e) => import.meta.env.DEV && console.debug("[useDesktopMenuEvents]", e));

    return () => unlistensRef.current.forEach((fn) => fn());
  }, [handleCheckUpdates]);
}
