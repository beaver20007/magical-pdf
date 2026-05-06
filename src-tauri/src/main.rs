#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{fs, path::PathBuf, process::Command};

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
        .invoke_handler(tauri::generate_handler![pick_save_path, write_file])
        .run(tauri::generate_context!())
        .expect("не удалось запустить Magical PDF");
}
