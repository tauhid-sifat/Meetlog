//! Application settings persistence and API-key storage.
//!
//! Non-secret settings live in a JSON file under the app config directory. The
//! Gemini API key is stored in the Windows Credential Manager via the OS
//! keychain, never in plaintext on disk.

use std::path::PathBuf;

use anyhow::{anyhow, Result};
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};

const KEYRING_SERVICE: &str = "meetlog";
const KEYRING_USER: &str = "gemini_api_key";

#[derive(Serialize, Deserialize, Clone, Debug)]
#[serde(default)]
pub struct Settings {
    pub microphone: Option<String>,
    pub output_dir: Option<String>,
    pub custom_vocabulary: Vec<String>,
    pub system_audio: bool,
    pub transcription_mode: String,
    pub diarization: bool,
    pub model: Option<String>,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            microphone: None,
            output_dir: None,
            custom_vocabulary: Vec::new(),
            system_audio: true,
            transcription_mode: "VERBATIM".to_string(),
            diarization: false,
            model: None,
        }
    }
}

fn settings_path(app: &AppHandle) -> Result<PathBuf> {
    let dir = app
        .path()
        .app_config_dir()
        .map_err(|e| anyhow!("app config dir: {e}"))?;
    Ok(dir.join("settings.json"))
}

pub fn load(app: &AppHandle) -> Settings {
    settings_path(app)
        .ok()
        .and_then(|path| std::fs::read_to_string(path).ok())
        .and_then(|text| serde_json::from_str(&text).ok())
        .unwrap_or_default()
}

pub fn save(app: &AppHandle, settings: &Settings) -> Result<()> {
    let path = settings_path(app)?;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&path, serde_json::to_string_pretty(settings)?)?;
    Ok(())
}

pub fn set_api_key(key: &str) -> Result<()> {
    let key = key.trim();
    let entry = keyring::Entry::new(KEYRING_SERVICE, KEYRING_USER)?;
    if key.is_empty() {
        let _ = entry.delete_credential();
    } else {
        entry.set_password(key)?;
    }
    Ok(())
}

pub fn get_api_key() -> Option<String> {
    keyring::Entry::new(KEYRING_SERVICE, KEYRING_USER)
        .ok()
        .and_then(|entry| entry.get_password().ok())
}
