# Immersive Studio (desktop)

Tauri v2 shell for local-first Studio on Windows, macOS, and Linux.

## What it does

- **Opens directly to Game Studio** (`/studio` Pipeline UI) — same React app as `apps/web`.
- **Desktop control strip** on `/studio`: API / Ollama / Blender / Comfy status, start API & Comfy, jobs folder, settings.
- **System tray**: left-click to show the window; menu for API, ComfyUI, jobs folder, quit.
- **Close to tray**: closing the window keeps API/Comfy running (default).
- **Auto-start**: Studio API starts on launch by default; optional ComfyUI auto-start.

Optional **launcher** (`npm run dev:launcher` in this package) is only for troubleshooting — normal dev does not use it.

## Prerequisites

1. Run the local Studio setup once:

   ```powershell
   .\scripts\local-pc-studio\setup-local-studio.ps1
   ```

2. Install [Rust](https://rustup.rs/) (for Tauri).

3. Optional: Ollama, Blender (`STUDIO_BLENDER_BIN` in `apps/studio-worker/.env.local`), ComfyUI sibling folder (`../ComfyUI`) or `COMFYUI_ROOT`.

## Development

From the repo root:

```bash
npm install
npm run dev:studio-desktop
```

**Stop other Vite servers on port 5173** before starting (the desktop app pins that port).

### Expected flow

1. Tauri waits for Vite, then opens **http://127.0.0.1:5173/studio** (Pipeline page).
2. Studio API auto-starts on `:8787` (watch the **Desktop** strip — API should turn OK within a few seconds).
3. Enter a prompt and run a job (enable mesh/textures as needed).
4. Close the window — app stays in the tray; API keeps running.

If API stays red, click **Start API** in the Desktop strip or tray menu.

## Production build

```bash
npm run build:studio-desktop
```

**Windows installer:** `apps/studio-desktop/src-tauri/target/release/bundle/nsis/Immersive Studio_0.1.0_x64-setup.exe`

Other platforms: `.dmg` (macOS), `.deb` / `.AppImage` (Linux) under the same `bundle/` folder.

The web bundle uses `apps/web/.env.desktop` (`VITE_STUDIO_API_URL=http://127.0.0.1:8787`).

### GitHub Release (CI)

1. Commit and push the desktop app to `main`.
2. Create a GitHub Release (tag e.g. `studio-desktop-v0.1.0`) or run **Actions → Release Immersive Studio (desktop) → Run workflow**.
3. CI builds Windows, macOS, and Linux installers and uploads them as draft release assets.

Code signing is not configured yet — Windows SmartScreen and macOS Gatekeeper may warn on first install.

## Settings file

Desktop preferences are stored in the OS app config directory as `settings.json` (`autoStartApi`, `autoStartComfy`, `closeToTray`, `openStudioWhenReady`).

## Notes

- Worker spawn loads `apps/studio-worker/.env.local` (same as `start-studio-api.ps1`).
- ComfyUI spawn uses `../ComfyUI/.venv` by default; set `COMFYUI_USE_GPU=1` in the environment for GPU mode.
- Prefer the **native venv worker** on Windows over Docker for Blender/Ollama paths.
- Regenerate app icons: `npm run tauri icon path/to/1024.png` inside this package.
