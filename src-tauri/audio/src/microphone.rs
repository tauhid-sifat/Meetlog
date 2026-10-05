//! Microphone capture: device enumeration and stream construction.

use anyhow::{anyhow, Result};
use cpal::traits::{DeviceTrait, HostTrait};
use cpal::Stream;
use tokio::sync::mpsc::UnboundedSender;

use super::capture::{build_capture_stream, ConfigSource};
use super::AudioChunk;

pub fn list_input_devices() -> Result<Vec<String>> {
    let host = cpal::default_host();
    let mut names = Vec::new();
    for device in host.input_devices()? {
        if let Ok(name) = device.name() {
            names.push(name);
        }
    }
    Ok(names)
}

/// Build and start a microphone stream forwarding 16 kHz mono i16 PCM.
pub fn build_stream(
    device_name: Option<&str>,
    sender: UnboundedSender<AudioChunk>,
) -> Result<Stream> {
    let host = cpal::default_host();
    let device = match device_name {
        Some(name) => host
            .input_devices()?
            .find(|d| d.name().map(|n| n == name).unwrap_or(false))
            .ok_or_else(|| anyhow!("input device not found: {name}"))?,
        None => host
            .default_input_device()
            .ok_or_else(|| anyhow!("no default input device"))?,
    };
    build_capture_stream(&device, "mic", sender, ConfigSource::Input)
}
