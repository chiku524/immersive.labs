import { useDesktopUpdate } from "./DesktopUpdateContext";
import { isTauriRuntime } from "../tauriRuntime";
import "./desktop-update-overlay.css";

const BRAND_MARK = "/brand-mark.png";

export function DesktopUpdateOverlay() {
  const ctx = useDesktopUpdate();

  if (!ctx || !isTauriRuntime()) return null;
  const { phase, errorMessage, pendingUpdateVersion, setPhase, retryUpdate } = ctx;
  if (phase === "idle") return null;

  if (phase === "error") {
    return (
      <div className="desktop-update-overlay" role="alert" aria-live="assertive">
        <div className="desktop-update-overlay__card desktop-update-overlay__card--error">
          <div className="desktop-update-overlay__error-icon" aria-hidden>
            <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <p className="desktop-update-overlay__error-title">Update failed</p>
          <p className="desktop-update-overlay__error-detail">{errorMessage ?? "Something went wrong."}</p>
          <div className="desktop-update-overlay__actions">
            <button
              type="button"
              className="desktop-update-overlay__btn desktop-update-overlay__btn--secondary"
              onClick={() => setPhase("idle")}
            >
              Continue
            </button>
            <button
              type="button"
              className="desktop-update-overlay__btn desktop-update-overlay__btn--primary"
              onClick={() => retryUpdate()}
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  const label =
    phase === "checking"
      ? "Checking for updates…"
      : phase === "downloading"
        ? pendingUpdateVersion
          ? `Downloading v${pendingUpdateVersion}…`
          : "Downloading update…"
        : "Installing… The app will restart in a moment.";

  return (
    <div className="desktop-update-overlay" aria-live="polite" aria-busy="true">
      <div className="desktop-update-overlay__card">
        <div className="desktop-update-overlay__symbol" aria-hidden>
          <img src={BRAND_MARK} alt="" width={56} height={56} />
        </div>
        <p className="desktop-update-overlay__name">Immersive Studio</p>
        <div className="desktop-update-overlay__spinner" aria-hidden />
        <p className="desktop-update-overlay__message">{label}</p>
      </div>
    </div>
  );
}
