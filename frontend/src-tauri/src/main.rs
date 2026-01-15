#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use std::collections::{HashMap, VecDeque};
use std::fs;
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

struct AppState {
    #[allow(dead_code)]
    workspace_root: PathBuf,
    terminal_buffers: Mutex<HashMap<String, LogBuffer>>,
    active_process_stdin: AsyncMutex<Option<tokio::process::ChildStdin>>,
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
fn read_file_content(path: String) -> Result<String, String> {
    fs::read_to_string(path).map_err(|e| e.to_string())
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
async fn send_vibe_input(state: State<'_, AppState>, input: String) -> Result<(), String> {
    let mut stdin_lock = state.active_process_stdin.lock().await;
    if let Some(stdin) = stdin_lock.as_mut() {
        use tokio::io::AsyncWriteExt;
        stdin.write_all(input.as_bytes()).await.map_err(|e| e.to_string())?;
        stdin.write_all(b"\n").await.map_err(|e| e.to_string())?;
        stdin.flush().await.map_err(|e| e.to_string())?;
        Ok(())
    } else {
        Err("No active process".to_string())
    }
}

#[tauri::command]
async fn run_vibe_command(window: Window, state: State<'_, AppState>, command: String, args: Vec<String>) -> Result<(), String> {
    use std::process::Stdio;
    use tokio::io::{AsyncBufReadExt, BufReader};
    use tokio::process::Command;

    let mut cmd = Command::new("vibe");
    cmd.arg("--server");
    
    let mut child = cmd
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .stdin(Stdio::piped())
        .spawn()
        .map_err(|e| e.to_string())?;

    let stdout = child.stdout.take().unwrap();
    let stderr = child.stderr.take().unwrap();
    let mut stdin = child.stdin.take().unwrap();

    // Send initial payload as per protocol spec
    let payload = serde_json::json!({
        "command": command,
        "args": args
    });
    use tokio::io::AsyncWriteExt;
    stdin.write_all(payload.to_string().as_bytes()).await.unwrap();
    stdin.write_all(b"\n").await.unwrap();
    stdin.flush().await.unwrap();

    {
        let mut stdin_lock = state.active_process_stdin.lock().await;
        *stdin_lock = Some(stdin);
    }

    let window_stdout = window.clone();
    let handle_stdout = window.app_handle();
    tokio::spawn(async move {
        let mut reader = BufReader::new(stdout).lines();
        while let Ok(Some(line)) = reader.next_line().await {
            // Try to parse as JSON for server mode events
            if let Ok(json) = serde_json::from_str::<serde_json::Value>(&line) {
                window_stdout.emit("vibe-server-event", json).unwrap();
            }

            {
                let state = handle_stdout.state::<AppState>();
                let mut buffers = state.terminal_buffers.lock().unwrap();
                let buffer = buffers.entry("main".to_string()).or_insert_with(|| LogBuffer::new(5000));
                buffer.push(line.clone());
            }
            window_stdout.emit("log-line", line).unwrap();
        }
    });

    let window_stderr = window.clone();
    let handle_stderr = window.app_handle();
    tokio::spawn(async move {
        let mut reader = BufReader::new(stderr).lines();
        while let Ok(Some(line)) = reader.next_line().await {
            let formatted_line = format!("ERR: {}", line);
            {
                let state = handle_stderr.state::<AppState>();
                let mut buffers = state.terminal_buffers.lock().unwrap();
                let buffer = buffers.entry("main".to_string()).or_insert_with(|| LogBuffer::new(5000));
                buffer.push(formatted_line.clone());
            }
            window_stderr.emit("log-line", formatted_line).unwrap();
        }
    });

    let handle_finished = window.app_handle();
    tokio::spawn(async move {
        let status = child.wait().await;
        {
            let state = handle_finished.state::<AppState>();
            let mut stdin_lock = state.active_process_stdin.lock().await;
            *stdin_lock = None;
        }
        window.emit("command-finished", status.map(|s| s.to_string()).ok()).unwrap();
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
fn set_workspace_root(_state: State<'_, AppState>, path: String) -> Result<(), String> {
    let path_buf = PathBuf::from(&path);
    if !path_buf.exists() {
        return Err("Path does not exist".to_string());
    }
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
    description: String,
    github_url: String,
    secrets: serde_json::Value
) -> Result<(), String> {
    let home = std::env::var("HOME").map_err(|e| e.to_string())?;
    let path = Path::new(&home).join(".vibe-tools").join("projects.json");
    if !path.exists() {
        return Err("Registry file not found".to_string());
    }
    
    let content = fs::read_to_string(&path).map_err(|e| e.to_string())?;
    let mut registry: serde_json::Value = serde_json::from_str(&content).map_err(|e| e.to_string())?;
    
    if let Some(projects) = registry["projects"].as_array_mut() {
        if let Some(project) = projects.iter_mut().find(|p| p["id"] == id) {
            project["name"] = serde_json::Value::String(name);
            project["description"] = serde_json::Value::String(description);
            project["metadata"]["github_url"] = serde_json::Value::String(github_url);
            project["secrets"] = secrets;
        } else {
            return Err("Project not found in registry".to_string());
        }
    }
    
    fs::write(path, serde_json::to_string_pretty(&registry).map_err(|e| e.to_string())?)
        .map_err(|e| e.to_string())?;
    
    Ok(())
}

#[tauri::command]
fn main() {
    let workspace_root = get_workspace_root().unwrap_or_else(|_| ".".into());
    let workspace_root_path = PathBuf::from(&workspace_root);

    tauri::Builder::default()
        .manage(AppState {
            workspace_root: workspace_root_path.clone(),
            terminal_buffers: Mutex::new(HashMap::new()),
            active_process_stdin: AsyncMutex::new(None),
        })
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
            read_file_content,
            get_workspace_root,
            run_vibe_command,
            send_vibe_input,
            get_active_agents,
            get_total_cost,
            open_in_cursor,
            update_artifact_meta,
            move_file,
            list_logs,
            tail_log_file,
            get_terminal_buffer,
            get_projects,
            set_workspace_root,
            update_project_registry
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
