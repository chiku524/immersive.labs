import { Route, Routes } from "react-router-dom";
import { DocsPage } from "./pages/DocsPage";
import { FabProductsPage } from "./pages/FabProductsPage";
import { MarketingHome } from "./pages/MarketingHome";
import {
  PrivatePluginDetailPage,
  PrivatePluginListPage,
} from "./pages/PrivatePluginDownloadPage";
import { StudioPage } from "./pages/StudioPage";

export default function App() {
  return (
    <Routes>
      <Route path="/docs" element={<DocsPage />} />
      <Route path="/fab-products" element={<FabProductsPage />} />
      <Route path="/p/plugins" element={<PrivatePluginListPage />} />
      <Route path="/p/plugins/:slug" element={<PrivatePluginDetailPage />} />
      <Route path="/studio" element={<StudioPage />} />
      <Route path="/" element={<MarketingHome />} />
    </Routes>
  );
}
