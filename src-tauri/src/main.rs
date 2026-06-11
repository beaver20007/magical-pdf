#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    fs,
    path::PathBuf,
    process::{Child, Command},
    sync::Mutex,
};
use tauri::Manager;

/// Holds the extract server process so we can kill it on app exit.
struct ExtractServer(Mutex<Option<Child>>);

#[tauri::command]
fn pick_save_path(filename: String) -> Result<String, String> {
    let path = rfd::FileDialog::new()
        .set_file_name(&filename)
        .save_file()
        .ok_or_else(|| "Сохранение отменено.".to_string())?;

    Ok(path.to_string_lossy().to_string())
}

#[tauri::command]
fn write_file(path: String, data: Vec<u8>) -> Result<String, String> {
    let path = PathBuf::from(path);
    fs::write(&path, data).map_err(|error| format!("Не удалось сохранить файл: {error}"))?;
    reveal_in_file_manager(&path);

    Ok(path.to_string_lossy().to_string())
}

/// Start the Python extract API server (uvicorn on :8765) if not already running.
/// Called from JS when the user opens the Extract tab.
#[tauri::command]
fn ensure_extract_server(app: tauri::AppHandle) -> Result<(), String> {
    let state = app.state::<ExtractServer>();
    let mut guard = state.0.lock().unwrap();

    // If a child process exists and is still running, do nothing.
    if let Some(child) = guard.as_mut() {
        if child.try_wait().map(|s| s.is_none()).unwrap_or(false) {
            return Ok(());
        }
    }

    // Locate extract/ directory relative to the app bundle / repo root.
    let extract_dir = resolve_extract_dir(&app)?;

    // Find Python interpreter: prefer venv inside extract/, then system python3/python.
    let python = find_python(&extract_dir)?;

    let mut cmd = Command::new(&python);
    cmd.current_dir(&extract_dir)
        .args([
            "-m", "uvicorn",
            "src.api.main:app",
            "--host", "127.0.0.1",
            "--port", "8765",
            "--log-level", "warning",
        ]);

    // Suppress console window on Windows release builds.
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
    }

    let child = cmd.spawn()
        .map_err(|e| format!("Не удалось запустить extract-сервер: {e}"))?;

    *guard = Some(child);
    Ok(())
}

fn resolve_extract_dir(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    // In dev: executable is inside src-tauri/target/debug — walk up to repo root.
    // In production bundle: resource_dir() points to bundled resources.
    let candidates: Vec<PathBuf> = vec![
        // bundled resource (set via tauri.conf.json resources if needed)
        app.path().resource_dir()
            .ok()
            .map(|d| d.join("extract"))
            .unwrap_or_default(),
        // dev: repo root (5 levels up from target/debug/magical-pdf.exe)
        std::env::current_exe()
            .unwrap_or_default()
            .ancestors()
            .nth(5)
            .unwrap_or(std::path::Path::new("."))
            .join("extract"),
        // fallback: cwd/extract
        std::env::current_dir()
            .unwrap_or_default()
            .join("extract"),
    ];

    candidates
        .into_iter()
        .find(|p| p.join("src").join("api").join("main.py").exists())
        .ok_or_else(|| "Директория extract/ не найдена рядом с приложением".to_string())
}

fn find_python(extract_dir: &PathBuf) -> Result<PathBuf, String> {
    // 1. venv inside extract/
    let venv_candidates = if cfg!(target_os = "windows") {
        vec![
            extract_dir.join(".venv").join("Scripts").join("python.exe"),
            extract_dir.join("venv").join("Scripts").join("python.exe"),
        ]
    } else {
        vec![
            extract_dir.join(".venv").join("bin").join("python"),
            extract_dir.join("venv").join("bin").join("python"),
        ]
    };

    for p in &venv_candidates {
        if p.exists() {
            return Ok(p.clone());
        }
    }

    // 2. System python3 / python
    let system = if cfg!(target_os = "windows") {
        vec!["python", "python3"]
    } else {
        vec!["python3", "python"]
    };

    for name in system {
        if Command::new(name).arg("--version").output().is_ok() {
            return Ok(PathBuf::from(name));
        }
    }

    Err("Python не найден. Установите Python 3.10+ или создайте venv в extract/.venv".to_string())
}

fn reveal_in_file_manager(path: &PathBuf) {
    #[cfg(target_os = "macos")]
    {
        let _ = Command::new("open").arg("-R").arg(path).spawn();
    }

    #[cfg(target_os = "windows")]
    {
        let _ = Command::new("explorer").arg("/select,").arg(path).spawn();
    }

    #[cfg(target_os = "linux")]
    {
        if let Some(parent) = path.parent() {
            let _ = Command::new("xdg-open").arg(parent).spawn();
        }
    }
}

fn main() {
    tauri::Builder::default()
        .manage(ExtractServer(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![
            pick_save_path,
            write_file,
            ensure_extract_server,
        ])
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                // Kill extract server when the last window closes.
                let state = window.app_handle().state::<ExtractServer>();
                if let Ok(mut guard) = state.0.lock() {
                    if let Some(mut child) = guard.take() {
                        let _ = child.kill();
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("не удалось запустить Magical PDF");
}
