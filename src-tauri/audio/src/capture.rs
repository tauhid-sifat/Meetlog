//! Shared capture-stream construction for cpal devices.
//!
//! Both the microphone and the system-audio loopback are cpal *input* streams;
//! they differ only in which device they open (a capture device vs. a render
//! device opened as loopback). This module holds the common plumbing.

use anyhow::{anyhow, Result};
use cpal::traits::{DeviceTrait, StreamTrait};
use cpal::{Device, SampleFormat, Stream, StreamConfig};
use tokio::sync::mpsc::UnboundedSender;

use super::resampler::{f32_to_i16_le, StreamResampler, TARGET_SAMPLE_RATE};
use super::AudioChunk;

/// Build an error callback that logs and forwards a human-readable message.
///
/// Stream errors (device unplugged, format change, profile switch) otherwise
/// die silently inside cpal while the meeting keeps running.
fn make_err_fn(
    source: &'static str,
    device_label: String,
    err_tx: UnboundedSender<String>,
) -> impl FnMut(cpal::StreamError) + Send + 'static {
    move |error: cpal::StreamError| {
        log::error!("audio stream error on '{source}' ({device_label}): {error}");
        let _ = err_tx.send(format!(
            "{source} capture interrupted on '{device_label}': {error}. The audio device may have changed."
        ));
    }
}

/// Which device config to base the stream on. Loopback capture opens an input
/// stream but must use the render device's *output* config.
#[derive(Clone, Copy)]
pub enum ConfigSource {
    Input,
    Output,
}

/// Build and start an input stream that forwards 16 kHz mono i16 PCM tagged
/// with `source`.
pub fn build_capture_stream(
    device: &Device,
    source: &'static str,
    sender: UnboundedSender<AudioChunk>,
    err_tx: UnboundedSender<String>,
    config_source: ConfigSource,
) -> Result<Stream> {
    let device_label = device.name().unwrap_or_default();
    let supported = match config_source {
        ConfigSource::Input => device.default_input_config().map_err(|e| {
            anyhow!(
                "capture '{source}': default input config for device '{device_label}': {e}"
            )
        })?,
        ConfigSource::Output => device.default_output_config().map_err(|e| {
            anyhow!(
                "capture '{source}': default output config for device '{device_label}': {e}"
            )
        })?,
    };
    let sample_format = supported.sample_format();
    let config: StreamConfig = supported.into();
    let channels = config.channels;
    let sample_rate = config.sample_rate.0;

    log::info!(
        "capture '{source}' on '{}': {} Hz, {} ch, {:?}",
        device.name().unwrap_or_default(),
        sample_rate,
        channels,
        sample_format
    );

    let mut resampler = StreamResampler::new(sample_rate, TARGET_SAMPLE_RATE, channels);

    let emit = move |samples: Vec<f32>| {
        if !samples.is_empty() {
            let _ = sender.send(AudioChunk {
                source,
                pcm: f32_to_i16_le(&samples),
            });
        }
    };

    let stream = match sample_format {
        SampleFormat::F32 => device
            .build_input_stream(
                &config,
                move |data: &[f32], _| {
                    let out = resampler.process(data);
                    emit(out);
                },
                make_err_fn(source, device_label.clone(), err_tx.clone()),
                None,
            )
            .map_err(|e| {
                anyhow!("capture '{source}': build input stream (F32) on '{device_label}': {e}")
            })?,
        SampleFormat::I16 => device
            .build_input_stream(
                &config,
                move |data: &[i16], _| {
                    let floats: Vec<f32> = data.iter().map(|&s| s as f32 / 32768.0).collect();
                    let out = resampler.process(&floats);
                    emit(out);
                },
                make_err_fn(source, device_label.clone(), err_tx.clone()),
                None,
            )
            .map_err(|e| {
                anyhow!("capture '{source}': build input stream (I16) on '{device_label}': {e}")
            })?,
        SampleFormat::U16 => device
            .build_input_stream(
                &config,
                move |data: &[u16], _| {
                    let floats: Vec<f32> = data
                        .iter()
                        .map(|&s| (s as f32 - 32768.0) / 32768.0)
                        .collect();
                    let out = resampler.process(&floats);
                    emit(out);
                },
                make_err_fn(source, device_label.clone(), err_tx.clone()),
                None,
            )
            .map_err(|e| {
                anyhow!("capture '{source}': build input stream (U16) on '{device_label}': {e}")
            })?,
        other => {
            return Err(anyhow!(
                "capture '{source}': unsupported sample format on '{device_label}': {other:?}"
            ))
        }
    };

    stream.play().map_err(|e| {
        anyhow!("capture '{source}': start stream on '{device_label}': {e}")
    })?;
    Ok(stream)
}

