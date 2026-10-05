//! Meetlog Tauri backend: audio capture and the Python AI sidecar.

mod sidecar;

use std::collections::HashMap;
use std::sync::Mutex;

use meetlog_audio::resampler::rms_i16_le;
use meetlog_audio::{AudioChunk, CaptureHandles, CaptureSpec};
use serde::Serialize;
use sidecar::Sidecar;
use tauri::{AppHandle, Emitter, Manager, State};
use tokio::sync::mpsc::UnboundedSender;

#[derive(Default)]
struct AppState {
    capture: Mutex<Option<CaptureHandles>>,
    sidecar: Mutex<Option<Sidecar>>,
    devices: Mutex<Vec<String>>,
}

#[derive(Serialize)]
struct ProbeResult {
    chunks: usize,
    rms: f32,
    seconds: f32,
}

#[tauri::command]
fn list_input_devices(state: State<'_, AppState>) -> Vec<String> {
    let devices = meetlog_audio::microphone::list_input_devices().unwrap_or_default();
    *state.devices.lock().unwrap() = devices.clone();
    devices
}

#[tauri::command]
fn sidecar_running(state: State<'_, AppState>) -> bool {
    state.sidecar.lock().unwrap().is_some()
}

#[tauri::command]
async fn start_sidecar(app: AppHandle, state: State<'_, AppState>) -> Result<(), String> {
    if state.sidecar.lock().unwrap().is_some() {
        return Ok(());
    }
    let sidecar = sidecar::start(app.clone())
        .await
        .map_err(|e| e.to_string())?;
    *state.sidecar.lock().unwrap() = Some(sidecar);
    Ok(())
}

#[tauri::command]
async fn sidecar_send(state: State<'_, AppState>, message: serde_json::Value) -> Result<(), String> {
    let guard = state.sidecar.lock().unwrap();
    match guard.as_ref() {
        Some(s) => s.send_json(message).map_err(|e| e.to_string()),
        None => Err("sidecar not running".to_string()),
    }
}

#[tauri::command]
async fn start_capture(state: State<'_, AppState>, spec: CaptureSpec) -> Result<(), String> {
    let sender: Option<UnboundedSender<String>> = {
        let guard = state.sidecar.lock().unwrap();
        guard.as_ref().map(|s| s.sender())
    };
    let sender = sender.ok_or_else(|| "sidecar not running".to_string())?;

    let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel::<AudioChunk>();
    let handles = meetlog_audio::start(&spec, tx).map_err(|e| e.to_string())?;

    // Forward captured audio to the sidecar.
    tauri::async_runtime::spawn(async move {
        while let Some(chunk) = rx.recv().await {
            let line = sidecar::audio_message(chunk.source, &chunk.pcm);
            if sender.send(line).is_err() {
                break;
            }
        }
    });

    *state.capture.lock().unwrap() = Some(handles);
    Ok(())
}

#[tauri::command]
fn stop_capture(state: State<'_, AppState>) {
    // Dropping the handles stops the streams.
    *state.capture.lock().unwrap() = None;
}

/// Capture for `seconds` and report per-source level, without the sidecar.
/// Used to verify microphone and system-audio capture work.
#[tauri::command]
async fn probe_capture(spec: CaptureSpec, seconds: f32) -> Result<HashMap<String, ProbeResult>, String> {
    let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel::<AudioChunk>();
    let handles = meetlog_audio::start(&spec, tx).map_err(|e| e.to_string())?;

    let mut stats: HashMap<String, (usize, f64)> = HashMap::new();
    let deadline = tokio::time::Instant::now() + std::time::Duration::from_secs_f32(seconds);
    loop {
        match tokio::time::timeout_at(deadline, rx.recv()).await {
            Ok(Some(chunk)) => {
                let entry = stats.entry(chunk.source.to_string()).or_insert((0, 0.0));
                entry.0 += 1;
                entry.1 += rms_i16_le(&chunk.pcm) as f64;
            }
            Ok(None) => break,
            Err(_) => break,
        }
    }
    drop(handles);

    let result = stats
        .into_iter()
        .map(|(source, (chunks, sum))| {
            let avg = if chunks > 0 { (sum / chunks as f64) as f32 } else { 0.0 };
            (
                source,
                ProbeResult {
                    chunks,
                    rms: avg,
                    seconds,
                },
            )
        })
        .collect();
    Ok(result)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(AppState::default())
        .setup(|app| {
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                match sidecar::start(handle.clone()).await {
                    Ok(sidecar) => {
                        let state = handle.state::<AppState>();
                        *state.sidecar.lock().unwrap() = Some(sidecar);
                        let _ = handle.emit("sidecar://ready", ());
                        log::info!("sidecar ready");
                    }
                    Err(e) => {
                        log::error!("sidecar failed to start: {e}");
                        let _ = handle.emit("sidecar://error", e.to_string());
                    }
                }
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            list_input_devices,
            sidecar_running,
            start_sidecar,
            sidecar_send,
            start_capture,
            stop_capture,
            probe_capture,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
