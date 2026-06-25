#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    fs,
    net::TcpStream,
    path::PathBuf,
    process::{Child, Command},
    sync::Mutex,
    thread,
    time::Duration,
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

/// Called from JS (Extract tab) to ensure the server is running and ready.
/// Returns Ok(()) as soon as /health responds — or after 30 s timeout.
#[tauri::command]
fn ensure_extract_server(app: tauri::AppHandle) -> Result<(), String> {
    spawn_extract_server(&app)?;
    wait_for_extract_ready(30)
}

// ── internal helpers ──────────────────────────────────────────────────────────

/// Spawn uvicorn if not already running.  Safe to call multiple times.
fn spawn_extract_server(app: &tauri::AppHandle) -> Result<(), String> {
    let state = app.state::<ExtractServer>();
    let mut guard = state.0.lock().unwrap();

    // Already running — nothing to do.
    if let Some(child) = guard.as_mut() {
        if child.try_wait().map(|s| s.is_none()).unwrap_or(false) {
            return Ok(());
        }
    }

    let extract_dir = resolve_extract_dir(app)?;
    let python = find_python(&extract_dir)?;

    let mut cmd = Command::new(&python);
    cmd.current_dir(&extract_dir).args([
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

    let child = cmd
        .spawn()
        .map_err(|e| format!("Не удалось запустить extract-сервер: {e}"))?;

    *guard = Some(child);
    Ok(())
}

/// Poll TCP port 8765 until accepting connections (server ready) or timeout.
fn wait_for_extract_ready(timeout_secs: u64) -> Result<(), String> {
    let deadline = std::time::Instant::now() + Duration::from_secs(timeout_secs);
    while std::time::Instant::now() < deadline {
        if TcpStream::connect("127.0.0.1:8765").is_ok() {
            return Ok(());
        }
        thread::sleep(Duration::from_millis(300));
    }
    Err(format!(
        "Extract-сервер не ответил за {timeout_secs} секунд. \
         Проверьте Python и зависимости в extract/.venv"
    ))
}

fn resolve_extract_dir(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let candidates: Vec<PathBuf> = vec![
        // Bundled resource (production).
        app.path()
            .resource_dir()
            .ok()
            .map(|d| d.join("extract"))
            .unwrap_or_default(),
        // Dev: repo root is 5 levels above target/debug/<exe>.
        std::env::current_exe()
            .unwrap_or_default()
            .ancestors()
            .nth(5)
            .unwrap_or(std::path::Path::new("."))
            .join("extract"),
        // Fallback: cwd/extract.
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
        .setup(|app| {
            // Auto-spawn extract server in background at startup.
            // UI stays responsive; Extract tab polls /health before enabling.
            let handle = app.handle().clone();
            thread::spawn(move || {
                if let Err(e) = spawn_extract_server(&handle) {
                    eprintln!("[extract] auto-start failed: {e}");
                }
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            pick_save_path,
            write_file,
            ensure_extract_server,
        ])
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
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
