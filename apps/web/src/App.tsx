import { Route, Routes } from "react-router-dom";
import { DocsPage } from "./pages/DocsPage";
import { MarketingHome } from "./pages/MarketingHome";
import { StudioPage } from "./pages/StudioPage";

export default function App() {
  return (
    <Routes>
      <Route path="/docs" element={<DocsPage />} />
      <Route path="/studio" element={<StudioPage />} />
      <Route path="/" element={<MarketingHome />} />
    </Routes>
  );
}
