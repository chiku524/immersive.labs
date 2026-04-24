import { useState, useEffect, type FormEvent, type ReactNode } from "react";
import "../pages/PrivatePluginDownloadPage.css";

const STORAGE_KEY = "il_private_plugin_dl_ok";

function getRequiredPassword(): string {
  return (import.meta.env.VITE_PRIVATE_PLUGIN_DL_PASSWORD as string | undefined) ?? "";
}

function isUnlocked(): boolean {
  if (typeof sessionStorage === "undefined") {
    return false;
  }
  return sessionStorage.getItem(STORAGE_KEY) === "1";
}

/**
 * If VITE_PRIVATE_PLUGIN_DL_PASSWORD is set, requires passphrase before showing children.
 * If unset, shows children with a small note (unlisted URL only; not a secret).
 */
export function PrivatePluginDownloadGate({ children }: { children: ReactNode }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [unlocked, setUnlocked] = useState(false);
  const [required, setRequired] = useState<string | null>(null);

  useEffect(() => {
    const p = getRequiredPassword();
    setRequired(p);
    if (p && isUnlocked()) {
      setUnlocked(true);
    }
  }, []);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const p = getRequiredPassword();
    if (password === p) {
      sessionStorage.setItem(STORAGE_KEY, "1");
      setError(null);
      setUnlocked(true);
    } else {
      setError("That passphrase is not correct.");
    }
  };

  if (required && !unlocked) {
    return (
      <div className="pp-gate">
        <p className="pp-gate-eyebrow">Private download</p>
        <p className="pp-muted" style={{ margin: "0 0 1rem" }}>
          Enter the share passphrase to view plugin zips. This is not a substitute for real access
          control; keep links off public indexes.
        </p>
        <form onSubmit={onSubmit} style={{ display: "grid", gap: 12 }}>
          <label>
            <span className="pp-gate-hint">Passphrase</span>
            <input
              type="password"
              name="il-plugin-dl"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="off"
            />
          </label>
          {error ? <p className="pp-error">{error}</p> : null}
          <button type="submit" className="btn btn-primary" style={{ justifySelf: "start" }}>
            Continue
          </button>
        </form>
      </div>
    );
  }

  return (
    <>
      {!required ? (
        <p className="pp-banner">
          Unlisted link only. Set <code className="pp-code">VITE_PRIVATE_PLUGIN_DL_PASSWORD</code> at
          build time to require a passphrase on these pages.
        </p>
      ) : null}
      {children}
    </>
  );
}
