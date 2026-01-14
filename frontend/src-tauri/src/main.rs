#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use std::fs;
use std::path::PathBuf;
use std::sync::mpsc;
use std::time::Duration;
use notify::{Watcher, RecursiveMode, Config};
use tauri::{Manager, Window};

// Prevents additional console window on Windows in release, DO NOT REMOVE!!

#[derive(serde::Serialize, Clone)]
struct FileEntry {
    name: String,
    path: String,
    is_dir: bool,
}

#[derive(serde::Serialize, Clone)]
struct FileChangeEvent {
    path: String,
    kind: String,
}

#[tauri::command]
fn list_directory(path: String) -> Result<Vec<FileEntry>, String> {
    let entries = fs::read_dir(&path).map_err(|e| e.to_string())?;
    let mut files = Vec::new();
    
    for entry in entries {
        let entry = entry.map_err(|e| e.to_string())?;
        let metadata = entry.metadata().map_err(|e| e.to_string())?;
        files.push(FileEntry {
            name: entry.file_name().to_string_lossy().into_owned(),
            path: entry.path().to_string_lossy().into_owned(),
            is_dir: metadata.is_dir(),
        });
    }
    
    // Sort: directories first, then alphabetically
    files.sort_by(|a, b| {
        if a.is_dir != b.is_dir {
            b.is_dir.cmp(&a.is_dir)
        } else {
            a.name.cmp(&b.name)
        }
    });
    
    Ok(files)
}

#[tauri::command]
fn get_workspace_root() -> Result<String, String> {
    let mut curr = std::env::current_dir().map_err(|e| e.to_string())?;
    loop {
        if curr.join(".git").exists() || curr.join("pyproject.toml").exists() {
            return Ok(curr.to_string_lossy().into_owned());
        }
        if let Some(parent) = curr.parent() {
            curr = parent.to_path_buf();
        } else {
            return Ok(std::env::current_dir().map(|p| p.to_string_lossy().into_owned()).unwrap_or_else(|_| ".".into()));
        }
    }
}

#[tauri::command]
async fn run_vibe_command(window: Window, command: String, args: Vec<String>) -> Result<(), String> {
    use std::process::Stdio;
    use tokio::io::{AsyncBufReadExt, BufReader};
    use tokio::process::Command;

    let mut child = Command::new("vibe")
        .arg(&command)
        .args(args)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| e.to_string())?;

    let stdout = child.stdout.take().unwrap();
    let stderr = child.stderr.take().unwrap();

    let window_clone = window.clone();
    tokio::spawn(async move {
        let mut reader = BufReader::new(stdout).lines();
        while let Ok(Some(line)) = reader.next_line().await {
            window_clone.emit("log-line", line).unwrap();
        }
    });

    let window_clone = window.clone();
    tokio::spawn(async move {
        let mut reader = BufReader::new(stderr).lines();
        while let Ok(Some(line)) = reader.next_line().await {
            window_clone.emit("log-line", format!("ERR: {}", line)).unwrap();
        }
    });

    tokio::spawn(async move {
        let status = child.wait().await;
        window.emit("command-finished", status.map(|s| s.to_string()).ok()).unwrap();
    });

    Ok(())
}

#[derive(serde::Serialize, serde::Deserialize, Clone)]
struct AgentProcess {
    pid: i32,
    command: String,
    chat_id: Option<String>,
    tracked: bool,
}

#[tauri::command]
async fn get_active_agents() -> Result<Vec<AgentProcess>, String> {
    use std::process::Command;
    let output = Command::new("vibe")
        .args(["ps", "--json"])
        .output()
        .map_err(|e| e.to_string())?;
    
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    
    let agents: Vec<AgentProcess> = serde_json::from_slice(&output.stdout).map_err(|e| e.to_string())?;
    Ok(agents)
}

#[tauri::command]
async fn get_total_cost() -> Result<f64, String> {
    use std::process::Command;
    let output = Command::new("vibe")
        .args(["cost", "--json"])
        .output()
        .map_err(|e| e.to_string())?;
    
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    
    let data: serde_json::Value = serde_json::from_slice(&output.stdout).map_err(|e| e.to_string())?;
    let cost = data["total_cost"].as_f64().ok_or("Invalid cost format")?;
    Ok(cost)
}

fn main() {
    let workspace_root = get_workspace_root().unwrap_or_else(|_| ".".into());
    let workspace_root_path = PathBuf::from(&workspace_root);

    tauri::Builder::default()
        .setup(move |app| {
            let handle = app.handle();
            let (tx, rx) = mpsc::channel();

            let mut watcher = notify::RecommendedWatcher::new(tx, Config::default().with_poll_interval(Duration::from_millis(500)))
                .expect("Failed to create watcher");

            watcher.watch(&workspace_root_path, RecursiveMode::Recursive).expect("Failed to watch workspace");

            std::thread::spawn(move || {
                for res in rx {
                    match res {
                        Ok(event) => {
                            if let Some(path) = event.paths.first() {
                                handle.emit_all("file-changed", FileChangeEvent {
                                    path: path.to_string_lossy().into_owned(),
                                    kind: format!("{:?}", event.kind),
                                }).unwrap();
                            }
                        }
                        Err(e) => println!("watch error: {:?}", e),
                    }
                }
            });

            // Prevent watcher from being dropped
            Box::leak(Box::new(watcher));

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            list_directory, 
            get_workspace_root,
            run_vibe_command,
            get_active_agents,
            get_total_cost
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
