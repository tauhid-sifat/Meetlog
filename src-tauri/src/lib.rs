//! Meetlog Tauri backend: audio capture, settings, meeting history, and the
//! Python AI sidecar.

mod meetings;
mod settings;
mod sidecar;

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Mutex;

use meetlog_audio::resampler::rms_i16_le;
use meetlog_audio::{AudioChunk, CaptureHandles, CaptureSpec};
use meetings::MeetingInfo;
use serde::Serialize;
use sidecar::Sidecar;
use tauri::{AppHandle, Emitter, Manager, State};
use tauri_plugin_opener::OpenerExt;
use tokio::sync::mpsc::UnboundedSender;

#[derive(Default)]
struct AppState {
    capture: Mutex<Option<CaptureHandles>>,
    sidecar: Mutex<Option<Sidecar>>,
    devices: Mutex<Vec<String>>,
}

impl AppState {
    fn sidecar_sender(&self) -> Option<UnboundedSender<String>> {
        self.sidecar.lock().unwrap().as_ref().map(|s| s.sender())
    }
}

#[derive(Serialize)]
struct ProbeResult {
    chunks: usize,
    rms: f32,
    seconds: f32,
}

fn default_output_dir() -> PathBuf {
    let home = std::env::var("USERPROFILE")
        .or_else(|_| std::env::var("HOME"))
        .unwrap_or_default();
    PathBuf::from(home).join("Meetlog").join("Meetings")
}

fn effective_output_dir(app: &AppHandle) -> PathBuf {
    settings::load(app)
        .output_dir
        .filter(|s| !s.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(default_output_dir)
}

fn begin_capture(
    state: &AppState,
    spec: &CaptureSpec,
    sender: UnboundedSender<String>,
) -> Result<(), String> {
    let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel::<AudioChunk>();
    let handles = meetlog_audio::start(spec, tx).map_err(|e| e.to_string())?;
    tauri::async_runtime::spawn(async move {
        while let Some(chunk) = rx.recv().await {
            if sender
                .send(sidecar::audio_message(chunk.source, &chunk.pcm))
                .is_err()
            {
                break;
            }
        }
    });
    *state.capture.lock().unwrap() = Some(handles);
    Ok(())
}

// --- audio ----------------------------------------------------------------- #

#[tauri::command]
fn list_input_devices(state: State<'_, AppState>) -> Vec<String> {
    let devices = meetlog_audio::microphone::list_input_devices().unwrap_or_default();
    *state.devices.lock().unwrap() = devices.clone();
    devices
}

#[tauri::command]
async fn probe_capture(
    spec: CaptureSpec,
    seconds: f32,
) -> Result<HashMap<String, ProbeResult>, String> {
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
            Ok(None) | Err(_) => break,
        }
    }
    drop(handles);

    Ok(stats
        .into_iter()
        .map(|(source, (chunks, sum))| {
            let avg = if chunks > 0 {
                (sum / chunks as f64) as f32
            } else {
                0.0
            };
            (
                source,
                ProbeResult {
                    chunks,
                    rms: avg,
                    seconds,
                },
            )
        })
        .collect())
}

// --- sidecar --------------------------------------------------------------- #

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
async fn sidecar_send(
    state: State<'_, AppState>,
    message: serde_json::Value,
) -> Result<(), String> {
    state
        .sidecar_sender()
        .ok_or_else(|| "sidecar not running".to_string())?
        .send(message.to_string())
        .map_err(|_| "sidecar writer closed".to_string())
}

// --- meeting lifecycle ----------------------------------------------------- #

#[tauri::command]
async fn start_meeting(
    app: AppHandle,
    state: State<'_, AppState>,
    spec: CaptureSpec,
    title: String,
) -> Result<(), String> {
    let settings = settings::load(&app);
    let api_key = settings::get_api_key().ok_or_else(|| {
        "No Gemini API key set. Add one in Settings before starting a meeting.".to_string()
    })?;
    let sender = state
        .sidecar_sender()
        .ok_or_else(|| "sidecar not running".to_string())?;

    let start = serde_json::json!({
        "type": "start",
        "config": {
            "api_key": api_key,
            "title": title,
            "mode": spec.mode,
            "custom_vocabulary": settings.custom_vocabulary,
            "transcription_mode": settings.transcription_mode,
            "diarization": settings.diarization,
            "model": settings.model,
        }
    });
    sender
        .send(start.to_string())
        .map_err(|_| "sidecar writer closed".to_string())?;

    begin_capture(&state, &spec, sender)
}

#[tauri::command]
async fn stop_meeting(_app: AppHandle, state: State<'_, AppState>) -> Result<(), String> {
    // Dropping the capture handles stops the streams.
    *state.capture.lock().unwrap() = None;
    let sender = state
        .sidecar_sender()
        .ok_or_else(|| "sidecar not running".to_string())?;
    let stop = serde_json::json!({
        "type": "stop",
        "config": {
            "api_key": settings::get_api_key(),
            "generate_markdown": true,
        }
    });
    sender
        .send(stop.to_string())
        .map_err(|_| "sidecar writer closed".to_string())
}

#[tauri::command]
fn stop_capture(state: State<'_, AppState>) {
    *state.capture.lock().unwrap() = None;
}

// --- settings & history ---------------------------------------------------- #

#[tauri::command]
fn load_settings(app: AppHandle) -> settings::Settings {
    settings::load(&app)
}

#[tauri::command]
fn save_settings(app: AppHandle, settings: settings::Settings) -> Result<(), String> {
    settings::save(&app, &settings).map_err(|e| e.to_string())
}

#[tauri::command]
fn set_api_key(key: String) -> Result<(), String> {
    settings::set_api_key(&key).map_err(|e| e.to_string())
}

#[tauri::command]
fn has_api_key() -> bool {
    settings::get_api_key().is_some()
}

#[tauri::command]
fn get_output_dir(app: AppHandle) -> String {
    effective_output_dir(&app).to_string_lossy().to_string()
}

#[tauri::command]
fn list_meetings(app: AppHandle) -> Vec<MeetingInfo> {
    meetings::list_meetings(&effective_output_dir(&app))
}

#[tauri::command]
fn read_text_file(path: String) -> Result<String, String> {
    std::fs::read_to_string(&path).map_err(|e| format!("read {path}: {e}"))
}

#[tauri::command]
fn open_path(app: AppHandle, path: String) -> Result<(), String> {
    app.opener()
        .open_path(path, None::<String>)
        .map_err(|e| e.to_string())
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
            probe_capture,
            sidecar_running,
            start_sidecar,
            sidecar_send,
            start_meeting,
            stop_meeting,
            stop_capture,
            load_settings,
            save_settings,
            set_api_key,
            has_api_key,
            get_output_dir,
            list_meetings,
            read_text_file,
            open_path,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
