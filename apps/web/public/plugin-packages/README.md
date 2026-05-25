# Plugin packages (static hosting)

- **Path:** `UE5.7-Win64/*.zip` — RunUAT marketplace drops (Win64, UE 5.7), same filenames as `fab-products/fab-marketplace-drops/UE5.7-Win64/`.
- **Populate:** from repo root of `fab-products`, run `scripts/build-fab-marketplace-drops-ue57.ps1`, then from `immersive.labs` run `scripts/sync-fab-plugin-zips-to-web.ps1`.
- **Site:** downloads are only on unlisted **`/p/plugins/<slug>`** pages (e.g. `/p/plugins/level-selection-sets`). There is no public index or `/fab-products` page.
- **Production (recommended):** zips are large and **gitignored**. In Cloudflare Pages / CI, set build env **`VITE_FAB_MARKETPLACE_ZIP_BASE`** to the HTTPS **folder** where all five `*-UE5.7-Win64.zip` files live. **Current release:** `https://github.com/chiku524/fab-products/releases/download/ue5.7-Win64-2026-05-23` (see [fab-products release](https://github.com/chiku524/fab-products/releases/tag/ue5.7-Win64-2026-05-23)). Redeploy after updating the var.
- **Alternative:** no env var—copy/sync zips into `public/plugin-packages/UE5.7-Win64/` before `npm run build` so Vite places them in `dist/`. Same-origin links are `/plugin-packages/UE5.7-Win64/<FileName>.zip` (see `src/data/fabPluginPackages.ts`).
- **Vercel routing:** The root `vercel.json` does **not** use a catch-all to `index.html` for all paths, so a **missing** zip returns **404** (not a fake `index.html` download). Do not reintroduce `"/(.*)" → /index.html` for the whole site.

Optional **source sample projects** (not the main Fab plugin files) are produced by `scripts/package-fab-product-zips.ps1` into `public/fab-samples/`.
