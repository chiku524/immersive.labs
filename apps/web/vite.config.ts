import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

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
    },
  },
});
