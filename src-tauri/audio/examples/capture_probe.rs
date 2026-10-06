//! Headless capture probe.
//!
//! Captures microphone and/or system audio for a few seconds and prints, per
//! source, the number of chunks and the average RMS level. Use it to verify
//! that capture works without launching the GUI.
//!
//!     cargo run -p meetlog-audio --example capture_probe -- online 6
//!     cargo run -p meetlog-audio --example capture_probe -- offline 6
//!     cargo run -p meetlog-audio --example capture_probe -- online 6 "Microphone (USB Audio Device)"

use std::collections::HashMap;
use std::time::Duration;

use meetlog_audio::resampler::rms_i16_le;
use meetlog_audio::{start, AudioChunk, CaptureSpec};

#[tokio::main(flavor = "current_thread")]
async fn main() {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    let args: Vec<String> = std::env::args().collect();
    let mode = args.get(1).cloned().unwrap_or_else(|| "online".to_string());
    let seconds: f32 = args
        .get(2)
        .and_then(|s| s.parse().ok())
        .unwrap_or(6.0);
    let mic = args.get(3).cloned();

    let spec = CaptureSpec {
        system_audio: mode == "online",
        microphone: mic,
        mode,
    };
    println!("capture spec: {spec:?} for {seconds}s");

    let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel::<AudioChunk>();
    let (err_tx, mut err_rx) = tokio::sync::mpsc::unbounded_channel::<String>();
    let handles = match start(&spec, tx, err_tx) {
        Ok(h) => h,
        Err(e) => {
            eprintln!("failed to start capture: {e}");
            std::process::exit(1);
        }
    };
    tokio::spawn(async move {
        while let Some(message) = err_rx.recv().await {
            eprintln!("stream error: {message}");
        }
    });

    let mut stats: HashMap<String, (usize, f64, f32)> = HashMap::new();
    let deadline = tokio::time::Instant::now() + Duration::from_secs_f32(seconds);
    loop {
        match tokio::time::timeout_at(deadline, rx.recv()).await {
            Ok(Some(chunk)) => {
                let rms = rms_i16_le(&chunk.pcm);
                let entry = stats
                    .entry(chunk.source.to_string())
                    .or_insert((0, 0.0, 0.0));
                entry.0 += 1;
                entry.1 += rms as f64;
                entry.2 = entry.2.max(rms);
            }
            Ok(None) => break,
            Err(_) => break,
        }
    }
    drop(handles);

    println!("\n--- capture summary ---");
    for (source, (chunks, sum, peak)) in &stats {
        let avg = if *chunks > 0 { sum / *chunks as f64 } else { 0.0 };
        println!(
            "{source:>7}: chunks={chunks:<5} avg_rms={avg:.4} peak_rms={peak:.4}"
        );
    }
    if stats.is_empty() {
        println!("no audio captured");
    }
}
