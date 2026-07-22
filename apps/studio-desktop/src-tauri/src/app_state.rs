use serde::{Deserialize, Serialize};
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::{AppHandle, Manager, State};

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;
#[cfg(windows)]
const DETACHED_PROCESS: u32 = 0x00000008;

fn hide_console(cmd: &mut Command) {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(CREATE_NO_WINDOW | DETACHED_PROCESS);
    }
}

fn comfy_silent_launcher_path() -> PathBuf {
    desktop_data_dir().join("comfy_silent_launcher.py")
}

/// Copy bundled launcher into AppData so Comfy's venv pythonw can run it by path.
pub fn ensure_comfy_silent_launcher(app: &AppHandle) -> Result<PathBuf, String> {
    let dest = comfy_silent_launcher_path();
    if dest.is_file() {
        return Ok(dest);
    }
    let bundled = app
        .path()
        .resolve(
            "resources/comfy_silent_launcher.py",
            tauri::path::BaseDirectory::Resource,
        )
        .map_err(|err| err.to_string())?;
    if !bundled.is_file() {
        #[cfg(debug_assertions)]
        {
            let dev = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("resources/comfy_silent_launcher.py");
            if dev.is_file() {
                if let Some(parent) = dest.parent() {
                    std::fs::create_dir_all(parent).map_err(|err| err.to_string())?;
                }
                std::fs::copy(&dev, &dest).map_err(|err| err.to_string())?;
                return Ok(dest);
            }
        }
        return Err("Comfy silent launcher missing from app bundle.".into());
    }
    if let Some(parent) = dest.parent() {
        std::fs::create_dir_all(parent).map_err(|err| err.to_string())?;
    }
    std::fs::copy(&bundled, &dest).map_err(|err| err.to_string())?;
    Ok(dest)
}

/// Prefer pythonw.exe on Windows so background worker/ComfyUI never attach a console.
fn python_launcher(py: &Path) -> PathBuf {
    #[cfg(windows)]
    {
        let pyw = py.with_file_name("pythonw.exe");
        if pyw.is_file() {
            return pyw;
        }
    }
    py.to_path_buf()
}

fn worker_log_path() -> PathBuf {
    desktop_data_dir().join("worker-serve.log")
}

fn worker_setup_log_path() -> PathBuf {
    desktop_data_dir().join("worker-setup.log")
}

fn desktop_worker_python() -> PathBuf {
    #[cfg(windows)]
    {
        return desktop_data_dir().join("worker-venv/Scripts/python.exe");
    }
    #[cfg(not(windows))]
    {
        return desktop_data_dir().join("worker-venv/bin/python");
    }
}

fn worker_installed_version_path() -> PathBuf {
    desktop_data_dir().join("worker-installed-version.txt")
}

fn write_worker_installed_version(version: &str) {
    let path = worker_installed_version_path();
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let _ = std::fs::write(path, format!("{}\n", version.trim()));
}

fn read_cached_worker_installed_version() -> Option<String> {
    let raw = std::fs::read_to_string(worker_installed_version_path()).ok()?;
    let trimmed = raw.trim().to_string();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed)
    }
}

fn probe_worker_package_version() -> Option<String> {
    let py = desktop_worker_python();
    if !py.exists() {
        return None;
    }
    // Must use python.exe (not pythonw) so stdout is captured, but always hide the
    // console — this used to flash a terminal on Windows when polled from the UI.
    let mut cmd = Command::new(&py);
    cmd.args([
        "-c",
        "import importlib.metadata as m; print(m.version('immersive-studio'))",
    ]);
    hide_console(&mut cmd);
    let output = cmd.output().ok()?;
    if !output.status.success() {
        return None;
    }
    let version = String::from_utf8(output.stdout).ok()?;
    let trimmed = version.trim().to_string();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed)
    }
}

fn desktop_worker_package_version() -> Option<String> {
    if let Some(cached) = read_cached_worker_installed_version() {
        return Some(cached);
    }
    let probed = probe_worker_package_version()?;
    write_worker_installed_version(&probed);
    Some(probed)
}

fn refresh_worker_installed_version_cache() -> Option<String> {
    let probed = probe_worker_package_version()?;
    write_worker_installed_version(&probed);
    Some(probed)
}

fn embedded_queue_worker_enabled() -> bool {
    match read_env_value("STUDIO_EMBEDDED_QUEUE_WORKER") {
        Some(v) => {
            let t = v.trim().to_lowercase();
            !matches!(t.as_str(), "0" | "false" | "no" | "off")
        }
        // Match worker scale_config: unset defaults to embedded for sqlite.
        None => true,
    }
}

const WORKER_PYPI_SPEC: &str = "immersive-studio[dev]";

fn fetch_running_worker_version() -> Option<String> {
    let client = reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(3))
        .build()
        .ok()?;
    let response = client
        .get("http://127.0.0.1:8787/api/studio/health")
        .send()
        .ok()?;
    if !response.status().is_success() {
        return None;
    }
    let text = response.text().ok()?;
    let body: serde_json::Value = serde_json::from_str(&text).ok()?;
    body.get("worker_version")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
}

fn stop_listeners_on_port_8787() {
    #[cfg(windows)]
    {
        let mut cmd = Command::new("powershell");
        cmd.args([
            "-NoProfile",
            "-Command",
            "Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }",
        ]);
        hide_console(&mut cmd);
        let _ = cmd.status();
    }
}

fn pip_upgrade_package(py: &Path, args: &[&str]) -> Result<(), String> {
    let mut cmd = Command::new(py);
    cmd.args(args);
    hide_console(&mut cmd);
    let output = cmd
        .output()
        .map_err(|err| format!("Failed to run {}: {err}", py.display()))?;
    if output.status.success() {
        return Ok(());
    }
    let stderr = String::from_utf8_lossy(&output.stderr);
    let stdout = String::from_utf8_lossy(&output.stdout);
    Err(format!(
        "pip {} failed (exit {}).\n{}\n{}",
        args.join(" "),
        output.status,
        stdout.trim(),
        stderr.trim()
    ))
}

#[derive(Serialize)]
pub struct WorkerVersionInfo {
    pub installed_version: Option<String>,
    pub running_version: Option<String>,
}

#[tauri::command]
pub fn get_worker_versions() -> WorkerVersionInfo {
    WorkerVersionInfo {
        installed_version: desktop_worker_package_version(),
        running_version: fetch_running_worker_version(),
    }
}

fn upgrade_worker_sync(state: &AppState) -> Result<String, String> {
    let py = desktop_worker_python();
    if !py.is_file() {
        return Err("Desktop worker venv missing. Click Run setup first.".into());
    }

    let before = desktop_worker_package_version();
    stop_worker_internal(state)?;
    stop_listeners_on_port_8787();
    std::thread::sleep(std::time::Duration::from_secs(2));

    append_worker_log("--- worker upgrade started (PyPI) ---");
    pip_upgrade_package(&py, &["-m", "pip", "install", "-q", "-U", "pip"])?;
    pip_upgrade_package(
        &py,
        &["-m", "pip", "install", "-q", "-U", WORKER_PYPI_SPEC],
    )?;

    let installed = refresh_worker_installed_version_cache().unwrap_or_else(|| "unknown".into());
    append_worker_log(&format!("--- worker upgrade finished ({installed}) ---"));

    start_worker_internal(state)?;

    let mut running: Option<String> = None;
    for _ in 0..30 {
        std::thread::sleep(std::time::Duration::from_secs(1));
        if let Some(version) = fetch_running_worker_version() {
            running = Some(version);
            break;
        }
    }

    let before_label = before.unwrap_or_else(|| "none".into());
    let running_label = running.unwrap_or_else(|| "starting…".into());
    Ok(format!(
        "Worker upgraded: {before_label} → immersive-studio {installed} (API reports {running_label}). \
         worker.env was preserved — click Refresh if the API pill is still gray."
    ))
}

#[tauri::command]
pub fn upgrade_worker(state: State<AppState>) -> Result<String, String> {
    upgrade_worker_sync(&state)
}

fn tail_log_lines(path: &Path, max_lines: usize) -> String {
    let Ok(raw) = std::fs::read_to_string(path) else {
        return String::new();
    };
    let lines: Vec<&str> = raw.lines().collect();
    if lines.len() <= max_lines {
        return raw.trim().to_string();
    }
    lines[lines.len() - max_lines..].join("\n")
}

fn append_worker_log(line: &str) {
    if let Ok(mut file) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(worker_log_path())
    {
        let _ = writeln!(file, "{line}");
    }
}

#[derive(Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DesktopSettings {
    pub auto_start_api: bool,
    pub auto_start_comfy: bool,
    pub close_to_tray: bool,
    pub open_studio_when_ready: bool,
}

impl Default for DesktopSettings {
    fn default() -> Self {
        Self {
            auto_start_api: true,
            auto_start_comfy: false,
            close_to_tray: true,
            open_studio_when_ready: true,
        }
    }
}

pub struct AppState {
    pub worker: Mutex<Option<Child>>,
    /// Separate `immersive-studio queue-worker` when `STUDIO_EMBEDDED_QUEUE_WORKER=0`.
    pub queue_worker: Mutex<Option<Child>>,
    pub comfy: Mutex<Option<Child>>,
    pub settings: Mutex<DesktopSettings>,
}

#[derive(Serialize)]
pub struct ServiceCheck {
    pub ok: bool,
    pub detail: String,
}

#[derive(Serialize)]
pub struct BlenderCheck {
    pub ok: bool,
    pub detail: String,
    pub path: Option<String>,
}

#[derive(Serialize)]
pub struct PrereqStatus {
    pub ollama: ServiceCheck,
    pub comfy: ServiceCheck,
    pub api: ServiceCheck,
    pub blender: BlenderCheck,
    pub docker: ServiceCheck,
    pub repo_root: String,
    pub comfy_root: Option<String>,
}

pub fn settings_path(app: &AppHandle) -> Result<PathBuf, String> {
    app.path()
        .app_config_dir()
        .map_err(|err| err.to_string())
        .map(|dir| dir.join("settings.json"))
}

pub fn load_settings(app: &AppHandle) -> DesktopSettings {
    let path = match settings_path(app) {
        Ok(path) => path,
        Err(_) => return DesktopSettings::default(),
    };
    let Ok(raw) = std::fs::read_to_string(path) else {
        return DesktopSettings::default();
    };
    serde_json::from_str(&raw).unwrap_or_default()
}

pub fn save_settings_file(app: &AppHandle, settings: &DesktopSettings) -> Result<(), String> {
    let path = settings_path(app)?;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|err| err.to_string())?;
    }
    let raw = serde_json::to_string_pretty(settings).map_err(|err| err.to_string())?;
    std::fs::write(path, raw).map_err(|err| err.to_string())
}

pub fn dev_repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../..")
        .canonicalize()
        .unwrap_or_else(|_| PathBuf::from(env!("CARGO_MANIFEST_DIR")))
}

pub fn desktop_data_dir() -> PathBuf {
    #[cfg(windows)]
    {
        let base = std::env::var("LOCALAPPDATA").unwrap_or_else(|_| ".".into());
        return PathBuf::from(base).join("Immersive Studio");
    }
    #[cfg(not(windows))]
    {
        let base = std::env::var("HOME").unwrap_or_else(|_| ".".into());
        return PathBuf::from(base).join(".immersive-studio");
    }
}

pub fn worker_env_path() -> PathBuf {
    #[cfg(debug_assertions)]
    {
        dev_repo_root().join("apps/studio-worker/.env.local")
    }
    #[cfg(not(debug_assertions))]
    {
        desktop_data_dir().join("worker.env")
    }
}

pub fn repo_root() -> PathBuf {
    if let Ok(path) = std::env::var("STUDIO_REPO_ROOT") {
        let candidate = PathBuf::from(path.trim());
        if candidate.exists() {
            return candidate.canonicalize().unwrap_or(candidate);
        }
    }

    let dev = dev_repo_root();
    if let Some(from_env) = read_env_value("STUDIO_REPO_ROOT") {
        let candidate = PathBuf::from(from_env);
        if candidate.exists() {
            return candidate.canonicalize().unwrap_or(candidate);
        }
    }

    #[cfg(not(debug_assertions))]
    {
        return desktop_data_dir();
    }

    #[cfg(debug_assertions)]
    {
        dev
    }
}

fn env_key_name(raw: &str) -> &str {
    // PowerShell Set-Content -Encoding utf8 writes a UTF-8 BOM; strip so the first key matches.
    raw.trim().trim_start_matches('\u{feff}')
}

pub fn read_env_value(key: &str) -> Option<String> {
    let path = worker_env_path();
    let file = std::fs::File::open(path).ok()?;
    for line in BufReader::new(file).lines().flatten() {
        let trimmed = line.trim().trim_start_matches('\u{feff}');
        if trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }
        let Some((k, v)) = trimmed.split_once('=') else {
            continue;
        };
        if env_key_name(k) == key {
            return Some(unquote_env_value(v.trim()));
        }
    }
    None
}

pub fn read_env_local_value(_root: &Path, key: &str) -> Option<String> {
    read_env_value(key)
}

fn unquote_env_value(raw: &str) -> String {
    if (raw.starts_with('"') && raw.ends_with('"')) || (raw.starts_with('\'') && raw.ends_with('\'')) {
        raw[1..raw.len() - 1].to_string()
    } else {
        raw.to_string()
    }
}

/// Upsert `KEY=value` in worker.env (or `.env.local` in dev) without clobbering other keys.
pub fn upsert_env_value(key: &str, value: &str) -> Result<(), String> {
    let path = worker_env_path();
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|err| err.to_string())?;
    }
    let existing_raw = std::fs::read_to_string(&path).unwrap_or_default();
    let existing = existing_raw.strip_prefix('\u{feff}').unwrap_or(&existing_raw);
    let mut found = false;
    let mut out: Vec<String> = Vec::new();
    for line in existing.lines() {
        let trimmed = line.trim().trim_start_matches('\u{feff}');
        if trimmed.is_empty() || trimmed.starts_with('#') {
            out.push(line.to_string());
            continue;
        }
        if let Some((k, _)) = trimmed.split_once('=') {
            if env_key_name(k) == key {
                out.push(format!("{key}={value}"));
                found = true;
                continue;
            }
        }
        out.push(line.to_string());
    }
    if !found {
        if !out.is_empty() && !out.last().map(|l| l.is_empty()).unwrap_or(true) {
            // keep a blank line only if file already had content
        }
        out.push(format!("{key}={value}"));
    }
    let mut body = out.join("\n");
    if !body.ends_with('\n') {
        body.push('\n');
    }
    std::fs::write(&path, body).map_err(|err| err.to_string())
}

fn mask_secret(value: &str) -> String {
    let chars: Vec<char> = value.chars().collect();
    if chars.len() <= 8 {
        return "••••".into();
    }
    let head: String = chars.iter().take(4).collect();
    let tail: String = chars.iter().rev().take(4).rev().collect();
    format!("{head}…{tail}")
}

fn tripo_key_format_valid(key: &str) -> bool {
    !key.is_empty() && key.starts_with("tsk_")
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TripoKeyStatus {
    pub configured: bool,
    pub format_valid: bool,
    pub masked: Option<String>,
    pub env_path: String,
}

#[tauri::command]
pub fn get_tripo_key_status() -> TripoKeyStatus {
    let env_path = worker_env_path().display().to_string();
    let key = read_env_value("STUDIO_TRIPO_API_KEY").unwrap_or_default();
    let configured = !key.is_empty();
    TripoKeyStatus {
        configured,
        format_valid: tripo_key_format_valid(&key),
        masked: if configured {
            Some(mask_secret(&key))
        } else {
            None
        },
        env_path,
    }
}

#[tauri::command]
pub fn set_tripo_api_key(state: State<AppState>, key: String) -> Result<String, String> {
    let trimmed = key.trim().to_string();
    if trimmed.contains('\n') || trimmed.contains('\r') || trimmed.contains('=') {
        return Err("Tripo API key contains invalid characters.".into());
    }
    upsert_env_value("STUDIO_TRIPO_API_KEY", &trimmed)?;
    if !trimmed.is_empty() {
        // Ensure the Tripo mesh/texture path is active when a key is saved.
        upsert_env_value("STUDIO_MESH_PROVIDER", "tripo")?;
        let tex_src = read_env_value("STUDIO_TEXTURE_SOURCE").unwrap_or_default();
        if tex_src.is_empty() || tex_src == "none" {
            upsert_env_value("STUDIO_TEXTURE_SOURCE", "tripo")?;
        }
        upsert_env_value("STUDIO_TRIPO_TEXTURE", "1")?;
        upsert_env_value("STUDIO_EXPORT_MESH_DEFAULT", "1")?;
    }

    // Reload env into API + queue-worker processes.
    let _ = stop_worker_internal(&state);
    std::thread::sleep(std::time::Duration::from_millis(800));
    start_worker_internal(&state)?;

    if trimmed.is_empty() {
        return Ok(format!(
            "Cleared STUDIO_TRIPO_API_KEY in {}. API restarted — Tripo meshes will fall back to Blender until a tsk_… key is set.",
            worker_env_path().display()
        ));
    }
    if !tripo_key_format_valid(&trimmed) {
        return Ok(format!(
            "Saved key to {} (masked {}), but it does not look like a Tripo OpenAPI key (must start with tsk_…, not tcli_…). API restarted.",
            worker_env_path().display(),
            mask_secret(&trimmed)
        ));
    }
    Ok(format!(
        "Tripo API key saved to {} ({}). Mesh provider=tripo. API restarted so the key is in effect.",
        worker_env_path().display(),
        mask_secret(&trimmed)
    ))
}

#[tauri::command]
pub fn open_worker_env() -> Result<(), String> {
    let path = worker_env_path();
    if !path.is_file() {
        return Err(format!(
            "Config file not found at {}. Click Run setup first.",
            path.display()
        ));
    }
    tauri_plugin_opener::open_path(&path, None::<&str>).map_err(|err| err.to_string())
}

pub fn apply_env_local(cmd: &mut Command, root: &Path) {
    let path = worker_env_path();
    let Ok(file) = std::fs::File::open(&path) else {
        #[cfg(debug_assertions)]
        cmd.env("STUDIO_REPO_ROOT", root);
        return;
    };

    for line in BufReader::new(file).lines().flatten() {
        let trimmed = line.trim().trim_start_matches('\u{feff}');
        if trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }
        let Some((k, v)) = trimmed.split_once('=') else {
            continue;
        };
        cmd.env(env_key_name(k), unquote_env_value(v.trim()));
    }
    if read_env_value("STUDIO_WORKER_DATA_DIR").is_some() {
        cmd.env_remove("STUDIO_REPO_ROOT");
    } else {
        #[cfg(debug_assertions)]
        cmd.env("STUDIO_REPO_ROOT", root);
    }
}

pub fn http_check(url: &str) -> ServiceCheck {
    let client = match reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(4))
        .build()
    {
        Ok(client) => client,
        Err(err) => {
            return ServiceCheck {
                ok: false,
                detail: err.to_string(),
            };
        }
    };

    match client.get(url).send() {
        Ok(response) if response.status().is_success() => ServiceCheck {
            ok: true,
            detail: format!("HTTP {}", response.status()),
        },
        Ok(response) => ServiceCheck {
            ok: false,
            detail: format!("HTTP {}", response.status()),
        },
        Err(err) => ServiceCheck {
            ok: false,
            detail: err.to_string(),
        },
    }
}

pub fn find_blender(root: &Path) -> BlenderCheck {
    if let Some(path) = read_env_local_value(root, "STUDIO_BLENDER_BIN") {
        if Path::new(&path).exists() {
            return BlenderCheck {
                ok: true,
                detail: "Configured in .env.local".into(),
                path: Some(path),
            };
        }
        return BlenderCheck {
            ok: false,
            detail: "STUDIO_BLENDER_BIN path not found".into(),
            path: Some(path),
        };
    }

    #[cfg(windows)]
    {
        let candidates = [
            r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",
        ];
        for candidate in candidates {
            if Path::new(candidate).exists() {
                return BlenderCheck {
                    ok: true,
                    detail: "Default install".into(),
                    path: Some(candidate.to_string()),
                };
            }
        }
    }

    #[cfg(not(windows))]
    {
        if let Ok(path) = Command::new("which").arg("blender").output() {
            if path.status.success() {
                let resolved = String::from_utf8_lossy(&path.stdout).trim().to_string();
                if !resolved.is_empty() {
                    return BlenderCheck {
                        ok: true,
                        detail: "On PATH".into(),
                        path: Some(resolved),
                    };
                }
            }
        }
    }

    BlenderCheck {
        ok: false,
        detail: "Not found — set STUDIO_BLENDER_BIN in apps/studio-worker/.env.local".into(),
        path: None,
    }
}

pub fn docker_check() -> ServiceCheck {
    // Never shell out from the desktop app — docker CLI flashes consoles on Windows.
    ServiceCheck {
        ok: false,
        detail: "Not used (desktop app)".into(),
    }
}

pub fn python_exe(root: &Path) -> PathBuf {
    #[cfg(not(debug_assertions))]
    {
        #[cfg(windows)]
        let desktop_py = desktop_data_dir().join("worker-venv/Scripts/python.exe");
        #[cfg(not(windows))]
        let desktop_py = desktop_data_dir().join("worker-venv/bin/python");
        if desktop_py.exists() {
            return desktop_py;
        }
    }

    #[cfg(windows)]
    {
        let venv_py = root.join("apps/studio-worker/.venv/Scripts/python.exe");
        if venv_py.exists() {
            return venv_py;
        }
    }

    #[cfg(not(windows))]
    {
        let venv_py = root.join("apps/studio-worker/.venv/bin/python");
        if venv_py.exists() {
            return venv_py;
        }
    }

    PathBuf::from("python")
}

fn jobs_folder() -> PathBuf {
    if let Some(data) = read_env_value("STUDIO_WORKER_DATA_DIR") {
        return PathBuf::from(data).join("jobs");
    }
    repo_root().join("jobs")
}

pub fn comfy_root(repo: &Path) -> Result<PathBuf, String> {
    if let Ok(custom) = std::env::var("COMFYUI_ROOT") {
        let path = PathBuf::from(custom.trim());
        if path.join("main.py").exists() {
            return Ok(path);
        }
    }

    if let Some(custom) = read_env_local_value(repo, "COMFYUI_ROOT") {
        let path = PathBuf::from(custom);
        if path.join("main.py").exists() {
            return Ok(path);
        }
    }

    let mut candidates: Vec<PathBuf> = Vec::new();
    #[cfg(windows)]
    {
        if let Ok(profile) = std::env::var("USERPROFILE") {
            candidates.push(PathBuf::from(profile).join("ComfyUI"));
        }
        candidates.push(PathBuf::from(r"C:\ComfyUI"));
    }
    #[cfg(not(windows))]
    {
        if let Ok(home) = std::env::var("HOME") {
            candidates.push(PathBuf::from(home).join("ComfyUI"));
        }
    }

    if let Some(parent) = repo.parent() {
        candidates.push(parent.join("ComfyUI"));
    }

    for path in candidates {
        if path.join("main.py").exists() {
            return Ok(path);
        }
    }

    Err(
        "ComfyUI not installed (optional for textures). Install from https://github.com/comfyanonymous/ComfyUI \
         or set COMFYUI_ROOT in worker.env."
            .into(),
    )
}

pub fn comfy_python(comfy: &Path) -> Result<PathBuf, String> {
    #[cfg(windows)]
    let venv_py = comfy.join(".venv/Scripts/python.exe");
    #[cfg(not(windows))]
    let venv_py = comfy.join(".venv/bin/python");

    if venv_py.exists() {
        Ok(venv_py)
    } else {
        Err(format!(
            "Missing ComfyUI venv at {}. Create it and pip install -r requirements.txt.",
            venv_py.display()
        ))
    }
}

pub fn check_prerequisites_snapshot() -> PrereqStatus {
    let root = repo_root();
    let comfy_path = comfy_root(&root).ok();
    PrereqStatus {
        ollama: http_check("http://127.0.0.1:11434/api/tags"),
        comfy: http_check("http://127.0.0.1:8188/system_stats"),
        api: http_check("http://127.0.0.1:8787/api/studio/health"),
        blender: find_blender(&root),
        docker: docker_check(),
        repo_root: root.to_string_lossy().to_string(),
        comfy_root: comfy_path.map(|p| p.to_string_lossy().to_string()),
    }
}

pub fn start_worker_internal(state: &AppState) -> Result<String, String> {
    if http_check("http://127.0.0.1:8787/api/studio/health").ok {
        let mut msg = "Studio API already running at http://127.0.0.1:8787".to_string();
        if !embedded_queue_worker_enabled() {
            match start_queue_worker_internal(state) {
                Ok(qmsg) => msg = format!("{msg}. {qmsg}"),
                Err(err) => {
                    append_worker_log(&format!("queue-worker spawn failed: {err}"));
                    msg = format!("{msg}. Warning: queue-worker failed to start ({err}).");
                }
            }
        }
        return Ok(msg);
    }

    let mut guard = state.worker.lock().map_err(|err| err.to_string())?;
    if let Some(mut child) = guard.take() {
        let _ = child.kill();
    }

    let root = repo_root();
    let python = python_launcher(&python_exe(&root));
    let mut cmd = Command::new(&python);
    cmd.args([
        "-m",
        "studio_worker.cli",
        "serve",
        "--host",
        "127.0.0.1",
        "--port",
        "8787",
    ])
    .current_dir(&root);
    hide_console(&mut cmd);
    cmd.stdout(Stdio::null());
    if let Ok(log) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(worker_log_path())
    {
        cmd.stderr(Stdio::from(log));
    } else {
        cmd.stderr(Stdio::null());
    }
    apply_env_local(&mut cmd, &root);

    append_worker_log(&format!(
        "--- spawn worker via {} (cwd {}) ---",
        python.display(),
        root.display()
    ));

    let child = cmd.spawn().map_err(|err| {
        let msg = format!(
            "Failed to start worker with {}: {err}. Run setup from the Desktop panel or worker-serve.log.",
            python.display()
        );
        append_worker_log(&msg);
        msg
    })?;

    *guard = Some(child);
    drop(guard);

    let mut msg =
        "Starting Studio API on http://127.0.0.1:8787 (wait a few seconds, then refresh).".to_string();
    if !embedded_queue_worker_enabled() {
        match start_queue_worker_internal(state) {
            Ok(qmsg) => msg = format!("{msg} {qmsg}"),
            Err(err) => {
                append_worker_log(&format!("queue-worker spawn failed: {err}"));
                msg = format!(
                    "{msg} Warning: queue-worker failed to start ({err}). Jobs may stay pending until you fix worker.env / re-run setup."
                );
            }
        }
    } else {
        let _ = stop_queue_worker_internal(state);
    }
    Ok(msg)
}

fn queue_worker_log_path() -> PathBuf {
    desktop_data_dir().join("queue-worker.log")
}

fn start_queue_worker_internal(state: &AppState) -> Result<String, String> {
    let mut guard = state.queue_worker.lock().map_err(|err| err.to_string())?;
    if let Some(child) = guard.as_mut() {
        if child.try_wait().ok().flatten().is_none() {
            return Ok("Queue worker already running.".into());
        }
        *guard = None;
    }

    let root = repo_root();
    let python = python_launcher(&python_exe(&root));
    let mut cmd = Command::new(&python);
    cmd.args([
        "-m",
        "studio_worker.cli",
        "queue-worker",
        "--worker-id",
        "desktop-q",
    ])
    .current_dir(&root);
    hide_console(&mut cmd);
    cmd.stdout(Stdio::null());
    if let Ok(log) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(queue_worker_log_path())
    {
        cmd.stderr(Stdio::from(log));
    } else {
        cmd.stderr(Stdio::null());
    }
    apply_env_local(&mut cmd, &root);
    // Ensure the separate process does not also embed a consumer.
    cmd.env("STUDIO_EMBEDDED_QUEUE_WORKER", "0");

    append_worker_log(&format!(
        "--- spawn queue-worker via {} (cwd {}) ---",
        python.display(),
        root.display()
    ));

    let child = cmd.spawn().map_err(|err| {
        let msg = format!(
            "Failed to start queue-worker with {}: {err}. See {}.",
            python.display(),
            queue_worker_log_path().display()
        );
        append_worker_log(&msg);
        msg
    })?;

    *guard = Some(child);
    Ok("Queue worker started (STUDIO_EMBEDDED_QUEUE_WORKER=0).".into())
}

fn stop_queue_worker_internal(state: &AppState) -> Result<(), String> {
    let mut guard = state.queue_worker.lock().map_err(|err| err.to_string())?;
    if let Some(mut child) = guard.take() {
        let _ = child.kill();
    }
    Ok(())
}

pub fn stop_worker_internal(state: &AppState) -> Result<(), String> {
    let _ = stop_queue_worker_internal(state);
    let mut guard = state.worker.lock().map_err(|err| err.to_string())?;
    if let Some(mut child) = guard.take() {
        child.kill().map_err(|err| err.to_string())?;
    }
    Ok(())
}

pub fn start_comfy_internal(state: &AppState, app: &AppHandle) -> Result<String, String> {
    if http_check("http://127.0.0.1:8188/system_stats").ok {
        return Ok("ComfyUI already running at http://127.0.0.1:8188".into());
    }

    let mut guard = state.comfy.lock().map_err(|err| err.to_string())?;
    if let Some(mut child) = guard.take() {
        let _ = child.kill();
    }

    let repo = repo_root();
    let comfy = comfy_root(&repo)?;
    let python = python_launcher(&comfy_python(&comfy)?);
    let launcher = ensure_comfy_silent_launcher(app)?;

    let use_gpu = std::env::var("COMFYUI_USE_GPU")
        .ok()
        .or_else(|| read_env_local_value(&repo, "COMFYUI_USE_GPU"))
        .is_some_and(|v| v == "1");

    let mut args = vec![
        launcher.to_string_lossy().to_string(),
        comfy.to_string_lossy().to_string(),
        "--listen".into(),
        "127.0.0.1".into(),
        "--port".into(),
        "8188".into(),
    ];
    if !use_gpu {
        args.push("--cpu".into());
    }

    let mut cmd = Command::new(&python);
    cmd.args(&args)
        .current_dir(&comfy)
        .env("TQDM_DISABLE", "1")
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    hide_console(&mut cmd);

    let child = cmd.spawn().map_err(|err| {
        format!(
            "Failed to start ComfyUI with {}: {err}",
            python.display()
        )
    })?;

    *guard = Some(child);
    let mode = if use_gpu { "GPU" } else { "CPU" };
    Ok(format!(
        "Starting ComfyUI on http://127.0.0.1:8188 ({mode} mode — first load can take a minute)."
    ))
}

pub fn stop_comfy_internal(state: &AppState) -> Result<(), String> {
    let mut guard = state.comfy.lock().map_err(|err| err.to_string())?;
    if let Some(mut child) = guard.take() {
        child.kill().map_err(|err| err.to_string())?;
    }
    Ok(())
}

pub fn stop_all_internal(state: &AppState) {
    let _ = stop_worker_internal(state);
    let _ = stop_comfy_internal(state);
}

#[cfg(debug_assertions)]
pub fn studio_dev_url() -> String {
    std::env::var("STUDIO_WEB_DEV_URL")
        .ok()
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(resolve_studio_dev_url)
}

/// Find the Vite dev server port (5173 is pinned in dev:web but may differ if already taken).
#[cfg(debug_assertions)]
pub fn resolve_studio_dev_url() -> String {
    for port in 5173..=5180u16 {
        let base = format!("http://127.0.0.1:{port}");
        if http_check(&base).ok {
            return format!("{base}/studio");
        }
    }
    "http://127.0.0.1:5173/studio".to_string()
}

fn is_studio_location(url: &tauri::Url) -> bool {
    let path = url.path();
    if path == "/studio" || path.starts_with("/studio/") {
        return true;
    }
    false
}

pub fn open_studio_window(app: &AppHandle) -> Result<String, String> {
    let window = app
        .get_webview_window("main")
        .ok_or_else(|| "Main window not found".to_string())?;

    window.show().map_err(|err| err.to_string())?;
    window.set_focus().map_err(|err| err.to_string())?;

    let current = window.url().map_err(|err| err.to_string())?;

    #[cfg(debug_assertions)]
    {
        let target = studio_dev_url();
        if is_studio_location(&current) {
            return Ok(format!("Studio is open at {}", current.as_str()));
        }

        let url = tauri::Url::parse(&target).map_err(|err| err.to_string())?;
        window
            .navigate(url)
            .map_err(|err| format!("Navigate to {target} failed: {err}"))?;
        return Ok(format!("Opened {target}"));
    }

    #[cfg(not(debug_assertions))]
    {
        if is_studio_location(&current) {
            return Ok(format!("Studio is open at {}", current.as_str()));
        }
        let mut target = current.clone();
        target.set_path("/studio");
        target.set_query(None);
        target.set_fragment(None);
        window
            .navigate(target.clone())
            .map_err(|err| err.to_string())?;
        Ok(format!("Opened Studio at {}", target.as_str()))
    }
}

pub fn run_autostart(app: &AppHandle) {
    let settings = load_settings(app);

    let _ = app.state::<AppState>().settings.lock().map(|mut guard| {
        *guard = settings.clone();
    });

    if settings.auto_start_api {
        let _ = start_worker_internal(&app.state::<AppState>());
    }

    if settings.auto_start_comfy {
        let _ = start_comfy_internal(&app.state::<AppState>(), app);
    }
}

#[derive(Serialize)]
pub struct ServiceStatus {
    pub ollama: ServiceCheck,
    pub comfy: ServiceCheck,
    pub api: ServiceCheck,
}

#[tauri::command]
pub fn check_prerequisites() -> PrereqStatus {
    check_prerequisites_snapshot()
}

/// Lightweight probe for the desktop panel poll: HTTP checks only (no CORS, no console),
/// so Ollama/ComfyUI report correctly even though they don't send CORS headers to the WebView.
#[tauri::command]
pub fn check_services() -> ServiceStatus {
    ServiceStatus {
        ollama: http_check("http://127.0.0.1:11434/api/tags"),
        comfy: http_check("http://127.0.0.1:8188/system_stats"),
        api: http_check("http://127.0.0.1:8787/api/studio/health"),
    }
}

#[tauri::command]
pub fn get_settings(app: AppHandle) -> DesktopSettings {
    load_settings(&app)
}

#[tauri::command]
pub fn save_settings(app: AppHandle, state: State<AppState>, settings: DesktopSettings) -> Result<(), String> {
    save_settings_file(&app, &settings)?;
    let mut guard = state.settings.lock().map_err(|err| err.to_string())?;
    *guard = settings;
    Ok(())
}

#[tauri::command]
pub fn start_worker(state: State<AppState>) -> Result<String, String> {
    start_worker_internal(&state)
}

#[tauri::command]
pub fn stop_worker(state: State<AppState>) -> Result<(), String> {
    stop_worker_internal(&state)
}

#[tauri::command]
pub fn start_comfy(app: AppHandle, state: State<AppState>) -> Result<String, String> {
    start_comfy_internal(&state, &app)
}

#[tauri::command]
pub fn stop_comfy(state: State<AppState>) -> Result<(), String> {
    stop_comfy_internal(&state)
}

#[tauri::command]
pub fn open_jobs_folder() -> Result<(), String> {
    let jobs = jobs_folder();
    std::fs::create_dir_all(&jobs).map_err(|err| err.to_string())?;
    tauri_plugin_opener::open_path(&jobs, None::<&str>).map_err(|err| err.to_string())
}

#[tauri::command]
pub async fn run_worker_setup(app: AppHandle) -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(move || run_worker_setup_sync(&app))
        .await
        .map_err(|err| format!("Setup task failed: {err}"))?
}

fn run_worker_setup_sync(app: &AppHandle) -> Result<String, String> {
    #[cfg(not(windows))]
    {
        let _ = app;
        return Err("Worker setup script is Windows-only for now. Install immersive-studio from PyPI and configure ~/.immersive-studio/worker.".into());
    }

    #[cfg(windows)]
    {
        let script = app
            .path()
            .resolve(
                "resources/setup-desktop-studio.ps1",
                tauri::path::BaseDirectory::Resource,
            )
            .map_err(|err| err.to_string())?;

        if !script.exists() {
            return Err(
                "Bundled setup script missing. Download from https://immersivelabs.space/downloads/setup-desktop-studio.ps1 and run with PowerShell.".into(),
            );
        }

        std::fs::create_dir_all(desktop_data_dir()).map_err(|err| err.to_string())?;
        let log_path = worker_setup_log_path();
        let log_file = std::fs::File::create(&log_path).map_err(|err| err.to_string())?;
        let err_file = log_file.try_clone().map_err(|err| err.to_string())?;

        let mut cmd = Command::new("powershell");
        cmd.args([
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            &script.to_string_lossy(),
        ]);
        hide_console(&mut cmd);
        cmd.stdout(std::process::Stdio::from(log_file));
        cmd.stderr(std::process::Stdio::from(err_file));

        append_worker_log("--- worker setup started ---");
        let mut child = cmd
            .spawn()
            .map_err(|err| format!("Failed to launch setup: {err}"))?;
        let status = child
            .wait()
            .map_err(|err| format!("Setup process failed: {err}"))?;

        if !status.success() {
            let tail = tail_log_lines(&log_path, 12);
            append_worker_log(&format!("--- worker setup failed (exit {status}) ---"));
            let detail = if tail.is_empty() {
                format!("Setup failed (exit {status}). See {}", log_path.display())
            } else {
                format!(
                    "Setup failed (exit {status}). Last log lines:\n{tail}\n\nFull log: {}",
                    log_path.display()
                )
            };
            return Err(detail);
        }

        append_worker_log("--- worker setup finished ---");
        let version = refresh_worker_installed_version_cache().unwrap_or_else(|| "unknown".into());
        Ok(format!(
            "Setup complete — immersive-studio {version} installed in the desktop worker venv. \
             Config: {} — click Start API (add STUDIO_TRIPO_API_KEY to worker.env for Tripo meshes).",
            worker_env_path().display()
        ))
    }
}

#[tauri::command]
pub fn open_studio(app: AppHandle) -> Result<String, String> {
    open_studio_window(&app)
}

#[tauri::command]
pub fn show_window(app: AppHandle) -> Result<(), String> {
    let window = app
        .get_webview_window("main")
        .ok_or_else(|| "Main window not found".to_string())?;
    window.show().map_err(|err| err.to_string())?;
    window.set_focus().map_err(|err| err.to_string())?;
    Ok(())
}

#[tauri::command]
pub async fn save_job_pack_zip(job_id: String) -> Result<String, String> {
    let url = format!(
        "http://127.0.0.1:8787/api/studio/jobs/{}/download",
        job_id.trim()
    );
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(120))
        .build()
        .map_err(|err| err.to_string())?;
    let response = client
        .get(&url)
        .send()
        .await
        .map_err(|err| format!("Could not reach Studio API: {err}"))?;
    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        return Err(format!("Download failed (HTTP {status}): {body}"));
    }
    let bytes = response
        .bytes()
        .await
        .map_err(|err| format!("Reading pack.zip failed: {err}"))?;
    let default_name = format!("immersive-studio-{}.zip", job_id.trim());
    let path = tauri::async_runtime::spawn_blocking(move || {
        rfd::FileDialog::new()
            .set_file_name(&default_name)
            .add_filter("Zip archive", &["zip"])
            .save_file()
    })
    .await
    .map_err(|err| err.to_string())?;
    let Some(path) = path else {
        return Err("Save cancelled".into());
    };
    std::fs::write(&path, &bytes).map_err(|err| format!("Writing {} failed: {err}", path.display()))?;
    Ok(path.to_string_lossy().to_string())
}
