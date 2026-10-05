//! Loopback self-test.
//!
//! Plays a 440 Hz tone through the default output device using cpal, and
//! captures the same device's loopback with our capture code. Both use the same
//! endpoint, so this isolates the loopback path from any question of where an
//! external player routed its audio.
//!
//!     cargo run -p meetlog-audio --example loopback_selftest -- 4

use std::f32::consts::TAU;
use std::time::Duration;

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{SampleFormat, StreamConfig};

use meetlog_audio::resampler::rms_i16_le;
use meetlog_audio::{system_audio, AudioChunk};

#[tokio::main(flavor = "current_thread")]
async fn main() {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    let seconds: f32 = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(4.0);

    let host = cpal::default_host();
    let device = host.default_output_device().expect("no default output device");
    println!("output device: {}", device.name().unwrap_or_default());

    let supported = device.default_output_config().expect("no output config");
    let sample_format = supported.sample_format();
    let config: StreamConfig = supported.into();
    let sample_rate = config.sample_rate.0 as f32;
    let channels = config.channels as usize;

    // --- play a tone -------------------------------------------------------
    let mut phase = 0.0f32;
    let out_stream = match sample_format {
        SampleFormat::F32 => device
            .build_output_stream(
                &config,
                move |data: &mut [f32], _| {
                    for frame in data.chunks_mut(channels) {
                        let s = 0.3 * (phase * TAU).sin();
                        for x in frame.iter_mut() {
                            *x = s;
                        }
                        phase = (phase + 440.0 / sample_rate).fract();
                    }
                },
                |e| eprintln!("output stream error: {e}"),
                None,
            )
            .expect("build output stream"),
        other => panic!("unsupported output sample format: {other:?}"),
    };
    out_stream.play().expect("play tone");
    println!("playing 440 Hz tone for {seconds}s...");

    // --- capture loopback --------------------------------------------------
    let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel::<AudioChunk>();
    let handles = system_audio::build_stream(tx).expect("start loopback");

    let mut chunks = 0usize;
    let mut sum = 0.0f64;
    let mut peak = 0.0f32;
    let deadline = tokio::time::Instant::now() + Duration::from_secs_f32(seconds);
    loop {
        match tokio::time::timeout_at(deadline, rx.recv()).await {
            Ok(Some(chunk)) => {
                let r = rms_i16_le(&chunk.pcm);
                chunks += 1;
                sum += r as f64;
                peak = peak.max(r);
            }
            Ok(None) => break,
            Err(_) => break,
        }
    }
    drop(handles);
    drop(out_stream);

    let avg = if chunks > 0 { sum / chunks as f64 } else { 0.0 };
    println!("\n--- loopback self-test ---");
    println!("chunks={chunks} avg_rms={avg:.4} peak_rms={peak:.4}");
    if peak > 0.01 {
        println!("RESULT: PASS (loopback captured the tone)");
    } else {
        println!("RESULT: FAIL (loopback captured silence)");
        std::process::exit(1);
    }
}
