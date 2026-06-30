# Immersive Studio (desktop)

Tauri v2 shell for local-first Studio on Windows, macOS, and Linux.

## What it does

- **Splash intro** — frameless splash with staggered logo animation, then optional auto-update check before opening Studio.
- **Auto-updater** — checks on launch and every 30 minutes; tray menu **Check for Updates**; quiet Windows installs when signed bundles are published.
- **Opens to Game Studio** (`/studio` Pipeline UI) — same React app as `apps/web`.
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

3. Optional: Ollama, **Tripo API key** (`STUDIO_TRIPO_API_KEY` in worker env), Blender (`STUDIO_BLENDER_BIN` for fallback meshes), ComfyUI sibling folder (`../ComfyUI`) or `COMFYUI_ROOT`.

## Development

From the repo root:

```bash
npm install
npm run dev:studio-desktop
```

**Stop other Vite servers on port 5173** before starting (the desktop app pins that port).

### Expected flow

1. Tauri shows the **splash** window (`/desktop/splash`), then the main window at `/studio`.
2. Studio API auto-starts on `:8787` (watch the **Desktop** strip — API should turn OK within a few seconds).
3. Enter a prompt and run a job (**Generate 3D mesh** is on by default — Tripo primary, Blender fallback).
4. Close the window — app stays in the tray; API keeps running.

If API stays red, click **Start API** in the Desktop strip or tray menu.

## Production build

```bash
npm run build:studio-desktop
```

**Windows installer:** `apps/studio-desktop/src-tauri/target/release/bundle/nsis/Immersive.Studio_0.1.2_x64-setup.exe`

GitHub Release assets use `Immersive.Studio_*` (dots, not spaces). The Game Studio site links match those filenames.

Other platforms: `.dmg` (macOS), `.deb` / `.AppImage` (Linux) under the same `bundle/` folder.

The web bundle uses `apps/web/.env.desktop` (`VITE_STUDIO_API_URL=http://127.0.0.1:8787`).

### GitHub Release (CI)

1. Add GitHub repo secrets **`TAURI_PRIVATE_KEY`** (contents of `apps/studio-desktop/immersive-studio-updater.key`, generated locally — never commit) and optional **`TAURI_KEY_PASSWORD`**.
2. Push tag `studio-desktop-v0.1.2` (or run **Actions → Release Immersive Studio (desktop)**).
3. CI builds installers, signed `.nsis.zip` / `.app.tar.gz` updater bundles, and uploads **`latest.json`** for auto-update.

The updater endpoint is `https://github.com/chiku524/immersive.labs/releases/latest/download/latest.json` — publish each desktop release as the newest GitHub release so `latest` resolves correctly.

Code signing for the installer itself is not configured — Windows SmartScreen and macOS Gatekeeper may warn on first install.

## Settings file

Desktop preferences are stored in the OS app config directory as `settings.json` (`autoStartApi`, `autoStartComfy`, `closeToTray`, `openStudioWhenReady`).

## Notes

- Worker spawn loads `apps/studio-worker/.env.local` (same as `start-studio-api.ps1`).
- ComfyUI spawn uses `../ComfyUI/.venv` by default; set `COMFYUI_USE_GPU=1` in the environment for GPU mode.
- Prefer the **native venv worker** on Windows over Docker for Blender/Ollama paths.
- Regenerate app icons: `npm run tauri icon path/to/1024.png` inside this package.
