#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde_json::Value;
use std::{collections::HashMap, sync::{Arc, Mutex}, time::Duration};
use tauri::{Manager, State};
use tauri_plugin_shell::{process::{CommandChild, CommandEvent}, ShellExt};
use tokio::sync::oneshot;

type Pending = HashMap<String, oneshot::Sender<Result<Value, String>>>;

struct BackendInner {
    child: Mutex<Option<CommandChild>>,
    pending: Mutex<Pending>,
}

struct Backend(Arc<BackendInner>);

#[tauri::command]
fn frontend_ready(app: tauri::AppHandle, report: Value) -> Result<(), String> {
    let args: Vec<String> = std::env::args().collect();
    if args.iter().any(|arg| arg == "--smoke-test") {
        let report_index = args.iter().position(|arg| arg == "--report").ok_or("Missing smoke report path")?;
        let path = args.get(report_index + 1).ok_or("Missing smoke report path")?;
        if report.get("version").and_then(Value::as_str) != Some("0.2.0") {
            return Err("Unexpected backend version".into());
        }
        std::fs::write(path, serde_json::to_vec(&serde_json::json!({"ok":true,"frontend_ready":true,"workspace":report})).unwrap())
            .map_err(|_| "Cannot write smoke report")?;
        app.exit(0);
    }
    Ok(())
}

fn fail_pending(inner: &BackendInner) {
    if let Ok(mut pending) = inner.pending.lock() {
        for (_, sender) in pending.drain() {
            let _ = sender.send(Err("本地后端已停止，请重新启动应用。".into()));
        }
    }
}

#[tauri::command]
async fn backend_request(state: State<'_, Backend>, request: Value) -> Result<Value, String> {
    let id = request.get("id").and_then(Value::as_str)
        .filter(|id| !id.is_empty() && id.len() <= 80)
        .ok_or("请求标识无效。")?.to_string();
    let encoded = serde_json::to_vec(&request).map_err(|_| "请求无法编码。")?;
    if encoded.len() > 512 * 1024 {
        return Err("请求过大。".into());
    }
    let (sender, receiver) = oneshot::channel();
    {
        let mut pending = state.0.pending.lock().map_err(|_| "后端状态不可用。")?;
        if pending.contains_key(&id) { return Err("请求标识重复。".into()); }
        pending.insert(id.clone(), sender);
    }
    let write_result = {
        let mut child = state.0.child.lock().map_err(|_| "后端状态不可用。")?;
        let mut line = encoded;
        line.push(b'\n');
        match child.as_mut() {
            Some(child) => child.write(&line).map_err(|_| "无法连接本地后端。".to_string()),
            None => Err("本地后端未启动。".to_string()),
        }
    };
    if let Err(error) = write_result {
        state.0.pending.lock().map_err(|_| "后端状态不可用。")?.remove(&id);
        return Err(error);
    }
    let result = tokio::time::timeout(Duration::from_secs(180), receiver).await;
    state.0.pending.lock().map_err(|_| "后端状态不可用。")?.remove(&id);
    match result {
        Ok(Ok(response)) => response,
        _ => Err("本地后端响应超时，请检查任务状态后再试。".into()),
    }
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            if std::env::args().any(|arg| arg == "--smoke-test") {
                if let Some(window) = app.get_webview_window("main") { window.hide()?; }
            }
            let (mut events, child) = app.shell().sidecar("studynote-backend")?.spawn()?;
            let inner = Arc::new(BackendInner { child: Mutex::new(Some(child)), pending: Mutex::new(HashMap::new()) });
            app.manage(Backend(inner.clone()));
            tauri::async_runtime::spawn(async move {
                while let Some(event) = events.recv().await {
                    match event {
                        CommandEvent::Stdout(bytes) => {
                            // Shell events are line-delimited; protocol data never enters logs.
                            if let Ok(response) = serde_json::from_slice::<Value>(&bytes) {
                                if let Some(id) = response.get("id").and_then(Value::as_str) {
                                    if let Ok(mut pending) = inner.pending.lock() {
                                        if let Some(sender) = pending.remove(id) { let _ = sender.send(Ok(response)); }
                                    }
                                }
                            }
                        }
                        CommandEvent::Terminated(_) => { fail_pending(&inner); break; }
                        _ => {} // Do not echo stderr, request payloads, or provider credentials.
                    }
                }
                fail_pending(&inner);
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![backend_request, frontend_ready])
        .build(tauri::generate_context!())
        .expect("StudyNote desktop initialization failed");
    app.run(|handle, event| {
        if let tauri::RunEvent::Exit = event {
            let backend = handle.state::<Backend>();
            if let Ok(mut child) = backend.0.child.lock() {
                if let Some(child) = child.take() { let _ = child.kill(); }
            };
        }
    });
}
