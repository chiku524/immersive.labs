import { Route, Routes } from "react-router-dom";
import { DesktopLaunch } from "./desktop/DesktopLaunch";
import { DesktopSplashGate } from "./desktop/DesktopSplashGate";
import { DesktopUpdateOverlay } from "./desktop/DesktopUpdateOverlay";
import { DesktopUpdateProvider } from "./desktop/DesktopUpdateContext";
import { StudioDesktopShell } from "./desktop/StudioDesktopShell";
import { DocsPage } from "./pages/DocsPage";
import { MarketingHome } from "./pages/MarketingHome";
import { PrivatePluginDetailPage } from "./pages/PrivatePluginDownloadPage";
import { StudioPage } from "./pages/StudioPage";

export default function App() {
  return (
    <DesktopUpdateProvider>
      <StudioDesktopShell />
      <DesktopUpdateOverlay />
      <Routes>
        <Route path="/desktop/splash" element={<DesktopSplashGate />} />
        <Route path="/desktop/launch" element={<DesktopLaunch />} />
        <Route path="/docs" element={<DocsPage />} />
        <Route path="/p/plugins/:slug" element={<PrivatePluginDetailPage />} />
        <Route path="/studio" element={<StudioPage />} />
        <Route path="/" element={<MarketingHome />} />
      </Routes>
    </DesktopUpdateProvider>
  );
}
