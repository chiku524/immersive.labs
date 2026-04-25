# Plugin packages (static hosting)

- **Path:** `UE5.7-Win64/*.zip` — RunUAT marketplace drops (Win64, UE 5.7), same filenames as `fab-products/fab-marketplace-drops/UE5.7-Win64/`.
- **Populate:** from repo root of `fab-products`, run `scripts/build-fab-marketplace-drops-ue57.ps1`, then from `immersive.labs` run `scripts/sync-fab-plugin-zips-to-web.ps1`.
- **Production (recommended):** zips are large and **gitignored**. In Vercel / CI, set build env **`VITE_FAB_MARKETPLACE_ZIP_BASE`** to the HTTPS **folder** where all five `*-UE5.7-Win64.zip` files live, e.g. `https://github.com/ORG/REPO/releases/download/ue5.7-2024/` (upload those files to that GitHub Release, then set the var and redeploy). The app inlines the URL at build time; the browser loads zips from that host (no same-origin 404).
- **Alternative:** no env var—copy/sync zips into `public/plugin-packages/UE5.7-Win64/` before `npm run build` so Vite places them in `dist/`. Same-origin links are `/plugin-packages/UE5.7-Win64/<FileName>.zip` (see `src/data/fabPluginPackages.ts`).
- **Vercel routing:** The root `vercel.json` does **not** use a catch-all to `index.html` for all paths, so a **missing** zip returns **404** (not a fake `index.html` download). Do not reintroduce `"/(.*)" → /index.html` for the whole site.

Optional **source sample projects** (not the main Fab plugin files) are produced by `scripts/package-fab-product-zips.ps1` into `public/fab-samples/`.
