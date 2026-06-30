use serde::{Deserialize, Serialize};
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::{AppHandle, Manager, State};

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

fn hide_console(cmd: &mut Command) {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
}

fn worker_log_path() -> PathBuf {
    desktop_data_dir().join("worker-serve.log")
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

pub fn read_env_value(key: &str) -> Option<String> {
    let path = worker_env_path();
    let file = std::fs::File::open(path).ok()?;
    for line in BufReader::new(file).lines().flatten() {
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }
        let Some((k, v)) = trimmed.split_once('=') else {
            continue;
        };
        if k.trim() == key {
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

pub fn apply_env_local(cmd: &mut Command, root: &Path) {
    let path = worker_env_path();
    let Ok(file) = std::fs::File::open(&path) else {
        #[cfg(debug_assertions)]
        cmd.env("STUDIO_REPO_ROOT", root);
        return;
    };

    for line in BufReader::new(file).lines().flatten() {
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }
        let Some((k, v)) = trimmed.split_once('=') else {
            continue;
        };
        cmd.env(k.trim(), unquote_env_value(v.trim()));
    }
    #[cfg(debug_assertions)]
    cmd.env("STUDIO_REPO_ROOT", root);
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
    match Command::new("docker").args(["info"]).output() {
        Ok(output) if output.status.success() => ServiceCheck {
            ok: true,
            detail: "docker info OK".into(),
        },
        Ok(output) => ServiceCheck {
            ok: false,
            detail: String::from_utf8_lossy(&output.stderr).trim().to_string(),
        },
        Err(err) => ServiceCheck {
            ok: false,
            detail: format!("Not available ({err})"),
        },
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
        return Ok("Studio API already running at http://127.0.0.1:8787".into());
    }

    let mut guard = state.worker.lock().map_err(|err| err.to_string())?;
    if let Some(mut child) = guard.take() {
        let _ = child.kill();
    }

    let root = repo_root();
    let python = python_exe(&root);
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
    Ok("Starting Studio API on http://127.0.0.1:8787 (wait a few seconds, then refresh).".into())
}

pub fn stop_worker_internal(state: &AppState) -> Result<(), String> {
    let mut guard = state.worker.lock().map_err(|err| err.to_string())?;
    if let Some(mut child) = guard.take() {
        child.kill().map_err(|err| err.to_string())?;
    }
    Ok(())
}

pub fn start_comfy_internal(state: &AppState) -> Result<String, String> {
    if http_check("http://127.0.0.1:8188/system_stats").ok {
        return Ok("ComfyUI already running at http://127.0.0.1:8188".into());
    }

    let mut guard = state.comfy.lock().map_err(|err| err.to_string())?;
    if let Some(mut child) = guard.take() {
        let _ = child.kill();
    }

    let repo = repo_root();
    let comfy = comfy_root(&repo)?;
    let python = comfy_python(&comfy)?;

    let use_gpu = std::env::var("COMFYUI_USE_GPU")
        .ok()
        .or_else(|| read_env_local_value(&repo, "COMFYUI_USE_GPU"))
        .is_some_and(|v| v == "1");

    let mut cmd = Command::new(&python);
    cmd.args(["main.py", "--listen", "127.0.0.1", "--port", "8188"])
        .current_dir(&comfy)
        .env("TQDM_DISABLE", "1")
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    hide_console(&mut cmd);

    if !use_gpu {
        cmd.arg("--cpu");
    }

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

pub fn wait_for_health(url: &str, attempts: u32) -> bool {
    for _ in 0..attempts {
        if http_check(url).ok {
            return true;
        }
        std::thread::sleep(std::time::Duration::from_millis(750));
    }
    false
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
        let _ = start_comfy_internal(&app.state::<AppState>());
    }

    if settings.open_studio_when_ready {
        let handle = app.clone();
        std::thread::spawn(move || {
            let ready = wait_for_health("http://127.0.0.1:8787/api/studio/health", 40);
            if ready {
                let _ = open_studio_window(&handle);
            }
        });
    }
}

#[tauri::command]
pub fn check_prerequisites() -> PrereqStatus {
    check_prerequisites_snapshot()
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
pub fn start_comfy(state: State<AppState>) -> Result<String, String> {
    start_comfy_internal(&state)
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
pub fn run_worker_setup(app: AppHandle) -> Result<String, String> {
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

        let mut cmd = Command::new("powershell");
        cmd.args([
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
            &script.to_string_lossy(),
        ]);
        hide_console(&mut cmd);
        cmd.spawn()
            .map_err(|err| format!("Failed to launch setup: {err}"))?;

        Ok("Setup running in the background — wait for it to finish, then click Start API.".into())
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
