//! Windows system-audio capture via WASAPI loopback.
//!
//! cpal 0.16 supports loopback on Windows by opening an *input* stream on a
//! render (output) device. We open the default output device, so whatever the
//! user can hear (Google Meet, Teams, Zoom, a browser, ...) is captured without
//! any per-application integration.

use anyhow::{anyhow, Result};
use cpal::traits::{DeviceTrait, HostTrait};
use cpal::Stream;
use tokio::sync::mpsc::UnboundedSender;

use super::capture::{build_capture_stream, ConfigSource};
use super::AudioChunk;

/// Build and start a loopback stream on the default output device.
pub fn build_stream(sender: UnboundedSender<AudioChunk>) -> Result<Stream> {
    let host = cpal::default_host();
    let device = host
        .default_output_device()
        .ok_or_else(|| anyhow!("no default output device for WASAPI loopback"))?;
    log::info!(
        "system audio loopback on '{}'",
        device.name().unwrap_or_default()
    );
    build_capture_stream(&device, "system", sender, ConfigSource::Output)
}
