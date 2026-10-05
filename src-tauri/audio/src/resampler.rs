//! Streaming linear resampler.
//!
//! cpal delivers audio at the device's native sample rate and channel count.
//! The rest of the pipeline (and Gemini Live) expects 16 kHz mono. This
//! resampler downmixes to mono and resamples with phase continuity across
//! callback boundaries, so chunked input does not introduce clicks.

pub const TARGET_SAMPLE_RATE: u32 = 16_000;

pub struct StreamResampler {
    ratio: f64,
    channels: usize,
    buffer: Vec<f32>,
    pos: f64,
}

impl StreamResampler {
    pub fn new(src_rate: u32, dst_rate: u32, channels: u16) -> Self {
        Self {
            ratio: src_rate as f64 / dst_rate as f64,
            channels: channels.max(1) as usize,
            buffer: Vec::new(),
            pos: 0.0,
        }
    }

    /// Process interleaved f32 input; returns mono f32 at the target rate.
    pub fn process(&mut self, input: &[f32]) -> Vec<f32> {
        if input.is_empty() {
            return Vec::new();
        }
        for frame in input.chunks(self.channels) {
            let sum: f32 = frame.iter().copied().sum();
            self.buffer.push(sum / self.channels as f32);
        }

        let mut out = Vec::new();
        while self.pos < self.buffer.len() as f64 {
            let i = self.pos.floor() as usize;
            let frac = (self.pos - i as f64) as f32;
            // Clamp the interpolation partner at the buffer end; the next
            // buffer's first sample is not available yet.
            let next = (i + 1).min(self.buffer.len() - 1);
            let sample = self.buffer[i] * (1.0 - frac) + self.buffer[next] * frac;
            out.push(sample);
            self.pos += self.ratio;
        }

        let consumed = (self.pos.floor() as usize).min(self.buffer.len());
        if consumed > 0 {
            self.buffer.drain(0..consumed);
            self.pos -= consumed as f64;
        }
        out
    }
}

/// Convert mono f32 samples in [-1, 1] to little-endian i16 PCM bytes.
pub fn f32_to_i16_le(samples: &[f32]) -> Vec<u8> {
    let mut bytes = Vec::with_capacity(samples.len() * 2);
    for &s in samples {
        let v = (s.clamp(-1.0, 1.0) * i16::MAX as f32) as i16;
        bytes.extend_from_slice(&v.to_le_bytes());
    }
    bytes
}

/// RMS level of little-endian i16 PCM bytes, normalised to [0, 1].
pub fn rms_i16_le(pcm: &[u8]) -> f32 {
    if pcm.len() < 2 {
        return 0.0;
    }
    let mut sum = 0.0f64;
    let mut count = 0u32;
    for pair in pcm.chunks_exact(2) {
        let s = i16::from_le_bytes([pair[0], pair[1]]) as f32 / 32768.0;
        sum += (s as f64) * (s as f64);
        count += 1;
    }
    if count == 0 {
        return 0.0;
    }
    (sum / count as f64).sqrt() as f32
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn downmixes_stereo_to_mono() {
        let mut r = StreamResampler::new(16_000, 16_000, 2);
        let out = r.process(&[1.0, 0.0, 0.0, 1.0]);
        assert_eq!(out.len(), 2);
        assert!((out[0] - 0.5).abs() < 1e-6);
        assert!((out[1] - 0.5).abs() < 1e-6);
    }

    #[test]
    fn downsamples_48k_to_16k() {
        let mut r = StreamResampler::new(48_000, 16_000, 1);
        let input: Vec<f32> = (0..4800).map(|i| (i as f32 * 0.01).sin()).collect();
        let out = r.process(&input);
        // 4800 input samples at 48k -> ~1600 output samples at 16k.
        assert!(out.len() > 1500 && out.len() < 1700, "got {}", out.len());
    }

    #[test]
    fn i16_conversion_clamps() {
        let bytes = f32_to_i16_le(&[2.0, -2.0, 0.0]);
        assert_eq!(bytes.len(), 6);
        assert_eq!(i16::from_le_bytes([bytes[0], bytes[1]]), i16::MAX);
        assert_eq!(i16::from_le_bytes([bytes[2], bytes[3]]), -i16::MAX);
    }

    #[test]
    fn rms_of_silence_is_zero() {
        assert_eq!(rms_i16_le(&[0u8; 128]), 0.0);
    }
}
