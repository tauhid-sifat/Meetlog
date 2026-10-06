//! Audio capture: microphone and Windows system-audio loopback.
//!
//! Both sources are captured as cpal input streams and converted to 16 kHz
//! mono i16 PCM. Each chunk is tagged with its source so the pipeline can keep
//! the microphone and system audio distinct (useful for later speaker
//! attribution) while still mixing them for transcription.

pub mod capture;
pub mod microphone;
pub mod resampler;
pub mod system_audio;

use anyhow::Result;
use cpal::Stream;
use serde::Serialize;
use tokio::sync::mpsc::UnboundedSender;

/// A tagged block of 16 kHz mono i16 PCM.
#[derive(Clone, Debug)]
pub struct AudioChunk {
    pub source: &'static str,
    pub pcm: Vec<u8>,
}

/// Live capture streams. Dropping this stops the streams.
pub struct CaptureHandles {
    streams: Vec<Stream>,
}

impl CaptureHandles {
    pub fn empty() -> Self {
        Self {
            streams: Vec::new(),
        }
    }

    fn push(&mut self, stream: Stream) {
        self.streams.push(stream);
    }

    pub fn len(&self) -> usize {
        self.streams.len()
    }
}

/// Which sources to capture for a meeting.
#[derive(Clone, Debug, Serialize, serde::Deserialize)]
pub struct CaptureSpec {
    /// "online" captures microphone + system audio; "offline" microphone only.
    pub mode: String,
    pub microphone: Option<String>,
    pub system_audio: bool,
}

impl Default for CaptureSpec {
    fn default() -> Self {
        Self {
            mode: "offline".to_string(),
            microphone: None,
            system_audio: false,
        }
    }
}

/// Start capture streams described by `spec`, forwarding tagged chunks.
///
/// Stream errors (device unplugged, format change, profile switch) are
/// forwarded as human-readable messages on `err_tx` so the UI can surface
/// them instead of silently capturing nothing.
pub fn start(
    spec: &CaptureSpec,
    sender: UnboundedSender<AudioChunk>,
    err_tx: UnboundedSender<String>,
) -> Result<CaptureHandles> {
    let mut handles = CaptureHandles::empty();

    let mic = microphone::build_stream(spec.microphone.as_deref(), sender.clone(), err_tx.clone())?;
    handles.push(mic);

    let want_system = spec.system_audio || spec.mode == "online";
    if want_system {
        let loopback = system_audio::build_stream(sender.clone(), err_tx.clone())?;
        handles.push(loopback);
    }

    log::info!("capture started with {} stream(s)", handles.len());
    Ok(handles)
}
