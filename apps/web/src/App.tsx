import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { DesktopLaunch } from "./desktop/DesktopLaunch";
import { DesktopSplashGate } from "./desktop/DesktopSplashGate";
import { DesktopUpdateOverlay } from "./desktop/DesktopUpdateOverlay";
import { DesktopUpdateProvider } from "./desktop/DesktopUpdateContext";
import { StudioDesktopShell } from "./desktop/StudioDesktopShell";
import { StudioPage } from "./pages/StudioPage";

const isDesktopBuild = import.meta.env.MODE === "desktop";

const DocsPage = lazy(() => import("./pages/DocsPage").then((m) => ({ default: m.DocsPage })));
const MarketingHome = lazy(() =>
  import("./pages/MarketingHome").then((m) => ({ default: m.MarketingHome })),
);
const PrivatePluginDetailPage = lazy(() =>
  import("./pages/PrivatePluginDownloadPage").then((m) => ({ default: m.PrivatePluginDetailPage })),
);

function LazyFallback() {
  return <div className="app-route-loading" aria-busy="true" />;
}

export default function App() {
  return (
    <DesktopUpdateProvider>
      <StudioDesktopShell />
      <DesktopUpdateOverlay />
      {isDesktopBuild ? (
        <Routes>
          <Route path="/desktop/splash" element={<DesktopSplashGate />} />
          <Route path="/desktop/launch" element={<DesktopLaunch />} />
          <Route path="/studio" element={<StudioPage />} />
          <Route path="*" element={<Navigate to="/studio" replace />} />
        </Routes>
      ) : (
        <Suspense fallback={<LazyFallback />}>
          <Routes>
            <Route path="/desktop/splash" element={<DesktopSplashGate />} />
            <Route path="/desktop/launch" element={<DesktopLaunch />} />
            <Route path="/docs" element={<DocsPage />} />
            <Route path="/p/plugins/:slug" element={<PrivatePluginDetailPage />} />
            <Route path="/studio" element={<StudioPage />} />
            <Route path="/" element={<MarketingHome />} />
          </Routes>
        </Suspense>
      )}
    </DesktopUpdateProvider>
  );
}
