#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use std::collections::{HashMap, VecDeque};
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::{mpsc, Mutex};
use tokio::sync::Mutex as AsyncMutex;
use std::time::Duration;
use notify::{Watcher, RecursiveMode, Config};
use tauri::{Manager, Window, State};
use tokio::io::{AsyncReadExt, AsyncSeekExt, SeekFrom};
use tokio::fs::File;

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

#[derive(serde::Serialize, Clone)]
struct LogLine {
    file: String,
    content: String,
}

struct LogBuffer {
    lines: VecDeque<String>,
    max_size: usize,
}

impl LogBuffer {
    fn new(max_size: usize) -> Self {
        Self {
            lines: VecDeque::with_capacity(max_size),
            max_size,
        }
    }

    fn push(&mut self, line: String) {
        if self.lines.len() >= self.max_size {
            self.lines.pop_front();
        }
        self.lines.push_back(line);
    }
}

#[derive(serde::Serialize, Clone, Debug)]
struct AppLog {
    timestamp: String,
    level: String,
    source: String,
    message: String,
    data: Option<serde_json::Value>,
}

struct AppState {
    #[allow(dead_code)]
    workspace_root: PathBuf,
    terminal_buffers: Mutex<HashMap<String, LogBuffer>>,
    active_process_child: AsyncMutex<Option<tauri::api::process::Child>>,
    app_logs: Mutex<VecDeque<AppLog>>,
}

fn log_to_app(state: &AppState, window: &Window, level: &str, source: &str, message: &str, data: Option<serde_json::Value>) {
    let log = AppLog {
        timestamp: chrono::Local::now().format("%H:%M:%S%.3f").to_string(),
        level: level.to_string(),
        source: source.to_string(),
        message: message.to_string(),
        data,
    };

    {
        let mut logs = state.app_logs.lock().unwrap();
        if logs.len() >= 1000 {
            logs.pop_front();
        }
        logs.push_back(log.clone());
    }

    let _ = window.emit("app-log", log);
}

fn log_vibe_command_call(state: &AppState, window: &Window, command: &str, args: &[String], level: &str, is_server: bool) {
    let mut full_command = format!("vibe {}", command);
    if is_server {
        full_command = format!("vibe --server {}", command);
    }
    if !args.is_empty() {
        full_command = format!("{} {}", full_command, args.join(" "));
    }
    
    let command_data = serde_json::json!({
        "command_line": full_command,
        "stdio": if is_server {
            serde_json::to_string(&serde_json::json!({
                "command": command,
                "args": args
            })).unwrap_or_default()
        } else {
            "".to_string()
        },
        "stdout": "",
        "stderr": "",
    });

    log_to_app(state, window, level, "Command", &format!("Executing: {}", full_command), Some(command_data));
    
    // Persistent file logging
    let log_path = PathBuf::from("implementation/logs/tauri_vibe_commands.log");
    if let Some(parent) = log_path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    
    if let Ok(mut file) = std::fs::OpenOptions::new().create(true).append(true).open(log_path) {
        let timestamp = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
        let _ = writeln!(file, "[{}] [{}] {}", timestamp, level, full_command);
    }
}

async fn spawn_vibe_process(command: String, args: Vec<String>) -> Result<(tauri::async_runtime::Receiver<tauri::api::process::CommandEvent>, tauri::api::process::Child), String> {
    use tauri::api::process::Command;

    let cmd = Command::new_sidecar("vibe")
        .or_else(|_| Ok(Command::new("vibe"))).map_err(|e: tauri::Error| e.to_string())?;

    let vibe_args = vec!["--server".to_string()];
    
    let (rx, mut child) = cmd
        .args(vibe_args)
        .spawn()
        .map_err(|e| format!("Failed to spawn vibe: {}", e))?;
    
    let payload = serde_json::json!({
        "command": command,
        "args": args
    });
    
    child.write(payload.to_string().as_bytes()).map_err(|e| e.to_string())?;
    child.write(b"\n").map_err(|e| e.to_string())?;
    
    Ok((rx, child))
}

#[tauri::command]
fn emit_log(state: State<'_, AppState>, window: Window, level: String, source: String, message: String, data: Option<serde_json::Value>) {
    log_to_app(&state, &window, &level, &source, &message, data);
}

#[tauri::command]
fn get_all_logs(state: State<'_, AppState>) -> Result<Vec<AppLog>, String> {
    let logs = state.app_logs.lock().unwrap();
    Ok(logs.iter().cloned().collect())
}

#[tauri::command]
fn clear_logs(state: State<'_, AppState>, window: Window) {
    let mut logs = state.app_logs.lock().unwrap();
    logs.clear();
    let _ = window.emit("logs-cleared", ());
}

#[tauri::command]
fn list_directory(_state: State<'_, AppState>, _window: Window, path: String) -> Result<Vec<FileEntry>, String> {
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
fn list_directory_recursive(path: String) -> Result<Vec<FileEntry>, String> {
    let mut all_files = Vec::new();
    let root_path = PathBuf::from(&path);
    
    fn scan(dir: &Path, all: &mut Vec<FileEntry>) -> std::io::Result<()> {
        if dir.is_dir() {
            for entry in fs::read_dir(dir)? {
                let entry = entry?;
                let path = entry.path();
                let metadata = entry.metadata()?;
                
                all.push(FileEntry {
                    name: entry.file_name().to_string_lossy().into_owned(),
                    path: path.to_string_lossy().into_owned(),
                    is_dir: metadata.is_dir(),
                });
                
                if metadata.is_dir() {
                    // Skip node_modules and hidden folders
                    let os_name = entry.file_name();
                    let name = os_name.to_string_lossy();
                    if name != "node_modules" && !name.starts_with('.') {
                        scan(&path, all)?;
                    }
                }
            }
        }
        Ok(())
    }
    
    scan(&root_path, &mut all_files).map_err(|e| e.to_string())?;
    Ok(all_files)
}

#[tauri::command]
fn read_file_content(path: String) -> Result<String, String> {
    fs::read_to_string(path).map_err(|e| e.to_string())
}

#[tauri::command]
fn write_file_content(state: State<'_, AppState>, window: Window, path: String, content: String) -> Result<(), String> {
    log_to_app(&state, &window, "INFO", "FS", &format!("Writing file: {}", path), None);
    fs::write(path, content).map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_workspace_root() -> Result<String, String> {
    let mut curr = std::env::current_dir().map_err(|e| e.to_string())?;
    let mut depth = 0;
    while depth < 20 {
        if curr.join(".git").exists() || curr.join("pyproject.toml").exists() {
            return Ok(curr.to_string_lossy().into_owned());
        }
        if let Some(parent) = curr.parent() {
            curr = parent.to_path_buf();
            depth += 1;
        } else {
            break;
        }
    }
    Ok(std::env::current_dir().map(|p| p.to_string_lossy().into_owned()).unwrap_or_else(|_| ".".into()))
}

#[tauri::command]
async fn send_vibe_input(state: State<'_, AppState>, input: String) -> Result<(), String> {
    let mut child_lock = state.active_process_child.lock().await;
    if let Some(child) = child_lock.as_mut() {
        child.write(input.as_bytes()).map_err(|e| e.to_string())?;
        child.write(b"\n").map_err(|e| e.to_string())?;
        Ok(())
    } else {
        Err("No active process".to_string())
    }
}

#[tauri::command]
async fn run_vibe_command(window: Window, state: State<'_, AppState>, command: String, args: Vec<String>) -> Result<(), String> {
    use tauri::api::process::CommandEvent;

    log_vibe_command_call(&state, &window, &command, &args, "INFO", true);

    let (mut rx, child) = spawn_vibe_process(command.clone(), args).await?;

    {
        let mut child_lock = state.active_process_child.lock().await;
        *child_lock = Some(child);
    }

    let window_clone = window.clone();
    let handle = window.app_handle();
    let command_name = command.clone();

    tokio::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    if let Ok(json) = serde_json::from_str::<serde_json::Value>(&line) {
                        let _ = window_clone.emit("vibe-server-event", json);
                    }

                    {
                        let state = handle.state::<AppState>();
                        let mut buffers = state.terminal_buffers.lock().unwrap();
                        let buffer = buffers.entry("main".to_string()).or_insert_with(|| LogBuffer::new(5000));
                        buffer.push(line.clone());
                    }
                    let _ = window_clone.emit("log-line", line);
                }
                CommandEvent::Stderr(line) => {
                    let formatted_line = format!("ERR: {}", line);
                    {
                        let state = handle.state::<AppState>();
                        let mut logs = state.app_logs.lock().unwrap();
                        if logs.len() >= 1000 {
                            logs.pop_front();
                        }
                        logs.push_back(AppLog {
                            timestamp: chrono::Local::now().format("%H:%M:%S%.3f").to_string(),
                            level: "ERROR".to_string(),
                            source: "Command".to_string(),
                            message: line.clone(),
                            data: None,
                        });
                        
                        let mut buffers = state.terminal_buffers.lock().unwrap();
                        let buffer = buffers.entry("main".to_string()).or_insert_with(|| LogBuffer::new(5000));
                        buffer.push(formatted_line.clone());
                    }
                    let _ = window_clone.emit("log-line", formatted_line);
                    let _ = window_clone.emit("app-log", AppLog {
                        timestamp: chrono::Local::now().format("%H:%M:%S%.3f").to_string(),
                        level: "ERROR".to_string(),
                        source: "Command".to_string(),
                        message: line,
                        data: None,
                    });
                }
                CommandEvent::Terminated(payload) => {
                    {
                        let state = handle.state::<AppState>();
                        let mut child_lock = state.active_process_child.lock().await;
                        *child_lock = None;
                    }

                    let status = payload.code;
                    {
                        let state = handle.state::<AppState>();
                        log_to_app(&state, &window_clone, "INFO", "Command", &format!("Command {} finished with status {:?}", command_name, status), None);
                    }

                    let _ = window_clone.emit("command-finished", serde_json::json!({
                        "command": command_name,
                        "status": status.map(|s| s.to_string())
                    }));
                    break;
                }
                _ => {}
            }
        }
    });

    Ok(())
}

#[tauri::command]
fn get_terminal_buffer(state: State<'_, AppState>, session: String) -> Result<Vec<String>, String> {
    let buffers = state.terminal_buffers.lock().unwrap();
    if let Some(buffer) = buffers.get(&session) {
        Ok(buffer.lines.iter().cloned().collect())
    } else {
        Ok(Vec::new())
    }
}

#[tauri::command]
fn open_in_cursor(path: String) -> Result<(), String> {
    use std::process::Command;
    #[cfg(target_os = "windows")]
    let cmd = "cursor.cmd";
    #[cfg(not(target_os = "windows"))]
    let cmd = "cursor";

    Command::new(cmd)
        .arg(path)
        .spawn()
        .map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
fn update_artifact_meta(path: String, status: Option<String>, owner: Option<String>) -> Result<(), String> {
    let content = fs::read_to_string(&path).map_err(|e| e.to_string())?;
    let match_fm = content.match_indices("---\n").collect::<Vec<_>>();
    if match_fm.len() >= 2 {
        let start = match_fm[0].0 + 4;
        let end = match_fm[1].0;
        let fm_str = &content[start..end];
        let mut data: serde_yaml::Value = serde_yaml::from_str(fm_str).map_err(|e| e.to_string())?;
        
        if let Some(s) = status {
            data["status"] = serde_yaml::Value::String(s);
        }
        if let Some(o) = owner {
            if data.as_mapping().unwrap().contains_key("agent") {
                data["agent"] = serde_yaml::Value::String(o);
            } else {
                data["owner"] = serde_yaml::Value::String(o);
            }
        }
        
        let new_fm = serde_yaml::to_string(&data).map_err(|e| e.to_string())?;
        let new_content = format!("---\n{}---\n{}", new_fm.trim_start_matches("---\n"), &content[end+4..]);
        fs::write(path, new_content).map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
fn move_file(from: String, to: String) -> Result<(), String> {
    let to_path = PathBuf::from(&to);
    if let Some(parent) = to_path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    fs::rename(from, to).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
async fn tail_log_file(window: Window, path: String) -> Result<(), String> {
    let path_buf = PathBuf::from(&path);
    if !path_buf.exists() {
        return Err("File does not exist".to_string());
    }

    let file_name = path_buf.file_name().unwrap_or_default().to_string_lossy().into_owned();

    tokio::spawn(async move {
        let mut file = match File::open(&path_buf).await {
            Ok(f) => f,
            Err(_) => return,
        };

        // Seek to end of file first
        let _ = file.seek(SeekFrom::End(0)).await;
        let mut buffer = [0u8; 8192];

        loop {
            match file.read(&mut buffer).await {
                Ok(0) => {
                    // Wait for more content
                    tokio::time::sleep(Duration::from_millis(100)).await;
                }
                Ok(n) => {
                    let content = String::from_utf8_lossy(&buffer[..n]).to_string();
                    window.emit("new-log-line", LogLine {
                        file: file_name.clone(),
                        content,
                    }).unwrap();
                }
                Err(_) => break,
            }
        }
    });

    Ok(())
}

#[tauri::command]
fn list_logs(root: String) -> Result<Vec<FileEntry>, String> {
    let logs_dir = Path::new(&root).join("implementation").join("logs");
    if !logs_dir.exists() {
        return Ok(Vec::new());
    }

    let entries = fs::read_dir(logs_dir).map_err(|e| e.to_string())?;
    let mut files = Vec::new();

    for entry in entries {
        let entry = entry.map_err(|e| e.to_string())?;
        let metadata = entry.metadata().map_err(|e| e.to_string())?;
        if metadata.is_file() {
            files.push(FileEntry {
                name: entry.file_name().to_string_lossy().into_owned(),
                path: entry.path().to_string_lossy().into_owned(),
                is_dir: false,
            });
        }
    }

    // Sort by name descending (most recent first if timestamped)
    files.sort_by(|a, b| b.name.cmp(&a.name));

    Ok(files)
}

#[tauri::command]
fn get_projects() -> Result<serde_json::Value, String> {
    let home = std::env::var("HOME").map_err(|e| e.to_string())?;
    let path = Path::new(&home).join(".vibe-tools").join("projects.json");
    if !path.exists() {
        return Ok(serde_json::to_value(serde_json::json!({"projects": [], "last_active_project_id": null})).unwrap());
    }
    let content = fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&content).map_err(|e| e.to_string())
}

#[tauri::command]
fn set_workspace_root(state: State<'_, AppState>, window: Window, path: String) -> Result<(), String> {
    let path_buf = PathBuf::from(&path);
    if !path_buf.exists() {
        return Err("Path does not exist".to_string());
    }
    log_to_app(&state, &window, "INFO", "System", &format!("Switching workspace to {}", path), None);
    std::env::set_current_dir(&path_buf).map_err(|e| e.to_string())?;
    // We don't update state.workspace_root because it's not Mutex protected, 
    // but subsequent commands use current_dir or root passed from frontend.
    // Actually, we should probably update the frontend's workspaceRoot state.
    Ok(())
}

#[tauri::command]
fn update_project_registry(
    id: String,
    name: String,
    path: String,
    description: String,
    metadata: serde_json::Value,
    secrets: serde_json::Value
) -> Result<(), String> {
    let home = std::env::var("HOME").map_err(|e| e.to_string())?;
    let registry_path = Path::new(&home).join(".vibe-tools").join("projects.json");
    if !registry_path.exists() {
        return Err("Registry file not found".to_string());
    }
    
    let content = fs::read_to_string(&registry_path).map_err(|e| e.to_string())?;
    let mut registry: serde_json::Value = serde_json::from_str(&content).map_err(|e| e.to_string())?;
    
    if let Some(projects) = registry["projects"].as_array_mut() {
        if let Some(project) = projects.iter_mut().find(|p| p["id"] == id) {
            project["name"] = serde_json::Value::String(name);
            project["path"] = serde_json::Value::String(path);
            project["description"] = serde_json::Value::String(description);
            project["metadata"] = metadata;
            project["secrets"] = secrets;
        } else {
            return Err("Project not found in registry".to_string());
        }
    }
    
    fs::write(registry_path, serde_json::to_string_pretty(&registry).map_err(|e| e.to_string())?)
        .map_err(|e| e.to_string())?;
    
    Ok(())
}

#[tauri::command]
async fn run_vibe_command_json(state: State<'_, AppState>, window: Window, command: String, args: Vec<String>) -> Result<serde_json::Value, String> {
    use tauri::api::process::CommandEvent;

    log_vibe_command_call(&state, &window, &command, &args, "INFO", true);

    let (mut rx, _child) = spawn_vibe_process(command.clone(), args.clone()).await?;
    
    let mut result_json: Option<serde_json::Value> = None;
    let mut error_msg = String::new();
    let mut success = false;

    while let Some(event) = rx.recv().await {
        match event {
            CommandEvent::Stdout(line) => {
                if let Ok(json) = serde_json::from_str::<serde_json::Value>(&line) {
                    if json["type"] == "result" {
                        result_json = Some(json["data"].clone());
                    }
                    let _ = window.emit("vibe-server-event", json);
                }
            }
            CommandEvent::Stderr(line) => {
                if !error_msg.is_empty() { error_msg.push('\n'); }
                error_msg.push_str(&line);
            }
            CommandEvent::Terminated(payload) => {
                success = payload.code == Some(0);
                break;
            }
            _ => {}
        }
    }

    if let Some(res) = result_json {
        log_to_app(&state, &window, "INFO", "Command", &format!("Command {} finished with result", command), Some(serde_json::json!({
            "command_line": format!("vibe --server {} {}", command, args.join(" ")),
            "stdio": serde_json::json!({ "command": command, "args": args }),
            "stdout": res,
            "stderr": error_msg,
        })));
        return Ok(res);
    }

    if !success {
        log_to_app(&state, &window, "ERROR", "Command", &format!("Command {} failed: {}", command, error_msg), Some(serde_json::json!({
            "command_line": format!("vibe --server {} {}", command, args.join(" ")),
            "stdio": serde_json::json!({ "command": command, "args": args }),
            "stdout": "",
            "stderr": error_msg,
        })));
        return Err(error_msg);
    }
    
    Err("Command finished without returning a result".to_string())
}

fn main() {
    let workspace_root = ".".to_string();
    let workspace_root_path = PathBuf::from(&workspace_root);

    tauri::Builder::default()
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .manage(AppState {
            workspace_root: workspace_root_path.clone(),
            terminal_buffers: Mutex::new(HashMap::new()),
            active_process_child: AsyncMutex::new(None),
            app_logs: Mutex::new(VecDeque::with_capacity(1000)),
        })
        .setup(move |app| {
            let handle = app.handle();
            let (tx, rx) = mpsc::channel();

            let mut watcher = notify::RecommendedWatcher::new(tx, Config::default())
                .expect("Failed to create watcher");

            // Only watch relevant directories to avoid hanging on node_modules
            for dir in ["product", "implementation", "issues"] {
                let path = workspace_root_path.join(dir);
                if path.exists() {
                    let _ = watcher.watch(&path, RecursiveMode::Recursive);
                }
            }

            std::thread::spawn(move || {
                for res in rx {
                    match res {
                        Ok(event) => {
                            if let Some(path) = event.paths.first() {
                                let path_str = path.to_string_lossy().into_owned();
                                
                                // Specific handling for logs
                                if path_str.contains("implementation/logs") {
                                    handle.emit_all("log-file-changed", FileChangeEvent {
                                        path: path_str.clone(),
                                        kind: format!("{:?}", event.kind),
                                    }).unwrap();
                                }

                                handle.emit_all("file-changed", FileChangeEvent {
                                    path: path_str,
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
            list_directory_recursive,
            read_file_content,
            write_file_content,
            get_workspace_root,
            run_vibe_command,
            send_vibe_input,
            open_in_cursor,
            update_artifact_meta,
            move_file,
            list_logs,
            tail_log_file,
            get_terminal_buffer,
            get_projects,
            set_workspace_root,
            update_project_registry,
            run_vibe_command_json,
            emit_log,
            get_all_logs,
            clear_logs
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
