import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/** Keep in sync with `STUDIO_DESKTOP_RELEASE_TAG` in studioDesktopDownload.ts */
const DESKTOP_RELEASE_TAG = "studio-desktop-v0.1.1";

export default defineConfig({
  plugins: [react()],
  server: {
    // When VITE_STUDIO_API_PROXY=1, the browser calls same-origin /api/studio/* and Vite forwards
    // to immersive-studio serve (see apps/web/src/studioApiConfig.ts).
    proxy: {
      "/api/studio": {
        target: "http://127.0.0.1:8787",
        changeOrigin: false,
      },
      "/downloads/desktop": {
        target: "https://github.com",
        changeOrigin: true,
        rewrite: (path) => {
          const file = decodeURIComponent(path.replace(/^\/downloads\/desktop\//, ""));
          return `/chiku524/immersive.labs/releases/download/${DESKTOP_RELEASE_TAG}/${file}`;
        },
      },
    },
  },
});
