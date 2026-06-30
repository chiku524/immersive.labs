import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { isTauriRuntime } from "../tauriRuntime";
import "./desktop-launch.css";

const BRAND_MARK = "/brand-mark.png";

/** Main window first paint after splash closes — brief "Opening…" then /studio. */
export function DesktopLaunch() {
  const navigate = useNavigate();
  const doneRef = useRef(false);

  useEffect(() => {
    if (!isTauriRuntime()) {
      navigate("/studio", { replace: true });
      return;
    }
    if (doneRef.current) return;
    doneRef.current = true;
    navigate("/studio", { replace: true });
  }, [navigate]);

  if (!isTauriRuntime()) return null;

  return (
    <div className="desktop-launch-screen">
      <div className="desktop-launch-screen__bg" aria-hidden />
      <div className="desktop-launch-screen__content">
        <div className="desktop-launch-screen__logo-wrap">
          <img
            src={BRAND_MARK}
            alt=""
            className="desktop-launch-screen__logo"
            width={72}
            height={72}
          />
        </div>
        <h1 className="desktop-launch-screen__title">Immersive Studio</h1>
        <p className="desktop-launch-screen__step">Opening…</p>
      </div>
    </div>
  );
}
