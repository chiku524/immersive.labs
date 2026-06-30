import { useEffect, useRef } from "react";
import { isTauriRuntime } from "../tauriRuntime";
import type { DesktopUpdatePhase } from "./DesktopUpdateContext";

const CHECK_INTERVAL_MS = 30 * 60 * 1000;

type UpdaterContext = {
  setPhase: (p: DesktopUpdatePhase, errorMessage?: string | null) => void;
  setPendingUpdateVersion: (v: string | null) => void;
  registerRetry: (fn: () => void) => void;
} | null;

export function useDesktopUpdater(updateContext: UpdaterContext) {
  const isRunningRef = useRef(false);
  const setPhase = updateContext?.setPhase;
  const setPendingUpdateVersion = updateContext?.setPendingUpdateVersion;
  const registerRetry = updateContext?.registerRetry;

  useEffect(() => {
    if (!isTauriRuntime() || !setPhase || !setPendingUpdateVersion || !registerRetry) return;

    const setPhaseFn = setPhase;
    const setPendingFn = setPendingUpdateVersion;
    const registerRetryFn = registerRetry;

    async function checkAndInstall() {
      if (isRunningRef.current) return;
      isRunningRef.current = true;
      try {
        const { check } = await import("@tauri-apps/plugin-updater");
        const { relaunch } = await import("@tauri-apps/plugin-process");
        const update = await check();
        if (!update) {
          setPhaseFn("idle");
          return;
        }

        setPendingFn(update.version);
        setPhaseFn("downloading");
        await update.downloadAndInstall((ev) => {
          if (ev.event === "Finished") setPhaseFn("installing");
        });
        setPhaseFn("restarting");
        await relaunch();
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        const isReleaseJsonError = /release\s*json|valid\s*release|could\s*not\s*fetch/i.test(message);
        const isAclDenied = /not allowed by ACL|plugin:updater\|check/i.test(message);
        if (isReleaseJsonError || isAclDenied) {
          if (import.meta.env.DEV) {
            console.debug("[Immersive Studio updater] Skipping update UI:", message);
          }
          setPhaseFn("idle");
          return;
        }
        setPhaseFn("error", message);
        console.warn("[Immersive Studio updater]", message);
      } finally {
        isRunningRef.current = false;
      }
    }

    registerRetryFn(checkAndInstall);
    void checkAndInstall();
    const interval = setInterval(checkAndInstall, CHECK_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [setPhase, setPendingUpdateVersion, registerRetry]);
}
