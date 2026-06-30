mod app_state;

use app_state::{
    check_prerequisites, get_settings, open_jobs_folder, open_studio, run_autostart, run_worker_setup,
    save_job_pack_zip, save_settings,
    show_window, start_comfy, start_worker, stop_comfy, stop_worker, AppState, DesktopSettings,
    stop_all_internal,
};
use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Emitter, Manager, WindowEvent,
};

const WINDOW_LABEL_MAIN: &str = "main";
const WINDOW_LABEL_SPLASH: &str = "splashscreen";

#[tauri::command]
fn close_splash_and_show_main(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(splash) = app.get_webview_window(WINDOW_LABEL_SPLASH) {
        splash.close().map_err(|e| e.to_string())?;
    }
    if let Some(main_win) = app.get_webview_window(WINDOW_LABEL_MAIN) {
        main_win.show().map_err(|e| e.to_string())?;
        main_win.set_focus().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
fn get_app_version(app: tauri::AppHandle) -> String {
    app.package_info().version.to_string()
}

fn focus_studio_windows(app: &tauri::AppHandle) {
    if let Some(w) = app.get_webview_window(WINDOW_LABEL_SPLASH) {
        let _ = w.show();
        let _ = w.set_focus();
        return;
    }
    if let Some(w) = app.get_webview_window(WINDOW_LABEL_MAIN) {
        let _ = w.unminimize();
        let _ = w.show();
        let _ = w.set_focus();
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .manage(AppState {
            worker: std::sync::Mutex::new(None),
            comfy: std::sync::Mutex::new(None),
            settings: std::sync::Mutex::new(DesktopSettings::default()),
        })
        .invoke_handler(tauri::generate_handler![
            check_prerequisites,
            get_settings,
            save_settings,
            start_worker,
            stop_worker,
            start_comfy,
            stop_comfy,
            open_jobs_folder,
    open_studio,
    show_window,
    run_worker_setup,
    save_job_pack_zip,
    close_splash_and_show_main,
            get_app_version,
        ])
        .setup(|app| {
            let show_i = MenuItem::with_id(app, "tray_show", "Show Immersive Studio", true, None::<&str>)?;
            let start_api_i =
                MenuItem::with_id(app, "tray_start_api", "Start Studio API", true, None::<&str>)?;
            let start_comfy_i =
                MenuItem::with_id(app, "tray_start_comfy", "Start ComfyUI", true, None::<&str>)?;
            let jobs_i = MenuItem::with_id(app, "tray_jobs", "Open jobs folder", true, None::<&str>)?;
            let updates_i =
                MenuItem::with_id(app, "tray_check_updates", "Check for Updates", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "tray_quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(
                app,
                &[&show_i, &start_api_i, &start_comfy_i, &jobs_i, &updates_i, &quit_i],
            )?;

            let icon = app
                .default_window_icon()
                .ok_or_else(|| tauri::Error::from(std::io::Error::other("missing app icon")))?
                .clone();

            let _tray = TrayIconBuilder::new()
                .icon(icon)
                .menu(&menu)
                .tooltip("Immersive Studio")
                .on_menu_event(move |app, event| match event.id.as_ref() {
                    "tray_show" => {
                        let _ = show_window(app.clone());
                    }
                    "tray_start_api" => {
                        let state = app.state::<AppState>();
                        let _ = app_state::start_worker_internal(&state);
                    }
                    "tray_start_comfy" => {
                        let state = app.state::<AppState>();
                        let _ = app_state::start_comfy_internal(&state);
                    }
                    "tray_jobs" => {
                        let _ = open_jobs_folder();
                    }
                    "tray_check_updates" => {
                        let _ = app.emit("menu-check-updates", ());
                    }
                    "tray_quit" => {
                        let state = app.state::<AppState>();
                        stop_all_internal(&state);
                        app.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        focus_studio_windows(tray.app_handle());
                    }
                })
                .build(app)?;

            if let Some(main_win) = app.get_webview_window(WINDOW_LABEL_MAIN) {
                let _ = main_win.center();
            }

            let autostart_handle = app.handle().clone();
            std::thread::spawn(move || {
                std::thread::sleep(std::time::Duration::from_millis(400));
                run_autostart(&autostart_handle);
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                if window.label() != WINDOW_LABEL_MAIN {
                    return;
                }
                let app = window.app_handle();
                let close_to_tray = app
                    .state::<AppState>()
                    .settings
                    .lock()
                    .map(|s| s.close_to_tray)
                    .unwrap_or(true);
                if close_to_tray {
                    let _ = window.hide();
                    api.prevent_close();
                } else {
                    let state = app.state::<AppState>();
                    stop_all_internal(&state);
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Immersive Studio");
}
