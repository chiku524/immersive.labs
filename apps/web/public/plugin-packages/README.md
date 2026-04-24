# Plugin packages (static hosting)

- **Path:** `UE5.7-Win64/*.zip` — RunUAT marketplace drops (Win64, UE 5.7), same filenames as `fab-products/fab-marketplace-drops/UE5.7-Win64/`.
- **Populate:** from repo root of `fab-products`, run `scripts/build-fab-marketplace-drops-ue57.ps1`, then from `immersive.labs` run `scripts/sync-fab-plugin-zips-to-web.ps1`.
- **Web routes:** `apps/web` links use `/plugin-packages/UE5.7-Win64/<FileName>.zip` (see `src/data/fabPluginPackages.ts`). Zips are gitignored; CI/deploy must include copied artifacts.

Optional **source sample projects** (not the main Fab plugin files) are produced by `scripts/package-fab-product-zips.ps1` into `public/fab-samples/`.
