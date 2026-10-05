//! Python AI sidecar lifecycle and TCP client.
//!
//! The sidecar (`ai/main.py`) is spawned as a child process and prints its
//! listening port to stdout as a single integer line. We connect over
//! loopback TCP and exchange newline-delimited JSON.
//!
//! In development the sidecar runs from the repo's virtualenv. A packaged build
//! would use the PyInstaller binary registered as a Tauri `externalBin`.

use std::path::PathBuf;
use std::process::Stdio;

use anyhow::{anyhow, Result};
use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine;
use serde_json::json;
use tauri::{AppHandle, Emitter};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::TcpStream;
use tokio::process::{Child, Command};
use tokio::sync::mpsc::UnboundedSender;

/// Event name the frontend listens on for sidecar messages.
pub const EVENT_NAME: &str = "sidecar://message";

pub struct Sidecar {
    child: Child,
    tx: UnboundedSender<String>,
}

impl Sidecar {
    /// Send a raw JSON message (one line) to the sidecar.
    pub fn send(&self, message: String) -> Result<()> {
        self.tx
            .send(message)
            .map_err(|_| anyhow!("sidecar writer closed"))
    }

    pub fn send_json(&self, value: serde_json::Value) -> Result<()> {
        self.send(value.to_string())
    }

    /// A cloneable sender for callers that push many messages (e.g. audio).
    pub fn sender(&self) -> UnboundedSender<String> {
        self.tx.clone()
    }
}

impl Drop for Sidecar {
    fn drop(&mut self) {
        let _ = self.child.start_kill();
    }
}

/// Build the JSON line for an audio chunk, tagged with its source.
pub fn audio_message(source: &str, pcm: &[u8]) -> String {
    json!({
        "type": "audio",
        "source": source,
        "data": BASE64.encode(pcm),
    })
    .to_string()
}

/// Resolve the repo root from the crate manifest dir (dev layout).
fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}

fn python_command() -> (String, Vec<String>) {
    let root = repo_root();
    let venv_python = root.join(".venv").join("Scripts").join("python.exe");
    if venv_python.exists() {
        (
            venv_python.to_string_lossy().to_string(),
            vec!["-m".to_string(), "ai.main".to_string()],
        )
    } else {
        (
            "python".to_string(),
            vec!["-m".to_string(), "ai.main".to_string()],
        )
    }
}

/// Spawn the sidecar, read its port, connect, and start reader/writer tasks.
pub async fn start(app: AppHandle) -> Result<Sidecar> {
    let (program, args) = python_command();
    let root = repo_root();

    log::info!("spawning sidecar: {program} {args:?} (cwd {root:?})");
    let mut child = Command::new(&program)
        .args(&args)
        .current_dir(&root)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| anyhow!("failed to spawn sidecar: {e}"))?;

    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| anyhow!("sidecar stdout unavailable"))?;
    let stderr = child.stderr.take();

    // Forward sidecar stderr to our log for diagnostics.
    if let Some(stderr) = stderr {
        tokio::spawn(async move {
            let mut lines = BufReader::new(stderr).lines();
            while let Ok(Some(line)) = lines.next_line().await {
                log::info!("[sidecar] {line}");
            }
        });
    }

    // The first parseable integer line on stdout is the port.
    let port = {
        let mut lines = BufReader::new(stdout).lines();
        let mut found = None;
        for _ in 0..20 {
            match lines.next_line().await {
                Ok(Some(line)) => {
                    let trimmed = line.trim();
                    if let Ok(p) = trimmed.parse::<u16>() {
                        found = Some(p);
                        break;
                    }
                    log::info!("[sidecar stdout] {trimmed}");
                }
                _ => break,
            }
        }
        found.ok_or_else(|| anyhow!("sidecar did not report a port"))?
    };

    let stream = TcpStream::connect(("127.0.0.1", port)).await?;
    let (read_half, write_half) = stream.into_split();

    // Writer task: drains the outgoing channel onto the socket.
    let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel::<String>();
    tokio::spawn(async move {
        let mut write_half = write_half;
        while let Some(mut line) = rx.recv().await {
            line.push('\n');
            if write_half.write_all(line.as_bytes()).await.is_err() {
                break;
            }
        }
    });

    // Reader task: forwards every line to the frontend as an event.
    tokio::spawn(async move {
        let mut lines = BufReader::new(read_half).lines();
        while let Ok(Some(line)) = lines.next_line().await {
            let _ = app.emit(EVENT_NAME, line);
        }
    });

    Ok(Sidecar { child, tx })
}
