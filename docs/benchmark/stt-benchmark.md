# STT Benchmark Report

Status: **preliminary** — validated on TTS-synthesized speech, not yet on real
meeting recordings.

This report records the Phase 0 evaluation of speech-to-text providers for
English, Bangla, and mixed English/Bangla meetings. It is filled in by running
the harness against real meeting recordings.

## How to run

1. Put recordings in `tests/data/` (16-bit PCM WAV). Audio files are gitignored.
2. Put a ground-truth transcript next to each recording as `<name>.txt`.
3. Run the harness:

   ```powershell
   $env:GEMINI_API_KEY = "..."
   .\.venv\Scripts\python.exe -m ai.benchmark.run_benchmark `
       --audio tests/data/meeting1.wav `
       --reference tests/data/meeting1.txt `
       --language en-US --language bn-BD `
       --json tests/data/meeting1.result.json
   ```

   Add `--vocab "Caboodle,FortiMapp,Constance,Efti"` to measure the effect of
   custom vocabulary. Add `--fast` to skip real-time pacing.

## Results

### Preliminary: TTS-synthesized validation

Generated with `gemini-2.5-flash-preview-tts`, transcribed with
`gemini-3.5-transcribe-live` via `scripts/validate_live_stt.py`. Short
single-utterance clips, so these are a smoke test of the live path, not a
substitute for real meeting audio.

| Provider | Model | Language | WER | CER | Notes |
|----------|-------|----------|-----|-----|-------|
| Gemini Live | gemini-3.5-transcribe-live | English | 0.00 | 0.00 | exact |
| Gemini Live | gemini-3.5-transcribe-live | Bangla | 0.00 | 0.00 | exact |
| Gemini Live | gemini-3.5-transcribe-live | Mixed | 0.29 | 0.36 | see below |

**Mixed-language finding:** the model wrote the English words inside a mixed
utterance using Bengali script rather than Latin script. For
`আমাদের Thursday-এর মধ্যে এটা finalize করতে হবে।` the model returned
`আমাদের থার্সডে-র মধ্যে এটা ফাইনালইজ করতে হবে।` (Thursday → থার্সডে,
finalize → ফাইনালইজ). WER/CER penalise this even though it is phonetically
correct. The spec (section 10) expects Latin script for code-switched English.
Possible mitigations to evaluate: a `language_hints`/`custom_vocabulary` entry
per English term, or a post-processing transliteration pass. Tracked as an
open issue.

### Real meeting recordings

| Provider | Model | Language | WER | CER | Latency p50 (s) | Latency p95 (s) | Cost/hour | Notes |
|----------|-------|----------|-----|-----|-----------------|-----------------|-----------|-------|
| Gemini Live | gemini-3.5-transcribe-live | English | — | — | — | — | — | pending recordings |
| Gemini Live | gemini-3.5-transcribe-live | Bangla | — | — | — | — | — | pending recordings |
| Gemini Live | gemini-3.5-transcribe-live | Mixed / Banglish | — | — | — | — | — | pending recordings |

## Custom vocabulary

| Terms | WER (baseline) | WER (with vocabulary) | Delta |
|-------|----------------|-----------------------|-------|
| 10 section-24 terms | — | — | — |

## Session rotation

| Audio length | Gap at 10-min boundary | Dropped audio |
|--------------|------------------------|---------------|
| — | — | — |

## Decision

Selected MVP provider(s): **Gemini Live `gemini-3.5-transcribe-live`** for
speech-to-text and **`gemini-flash-latest`** for meeting intelligence. The live
path is confirmed working end-to-end on synthetic speech (English and Bangla
exact). The real-recording benchmark and the mixed-script mitigation remain
open before this decision is final.

Pass targets: English WER ≤ 15%, Bangla WER ≤ 20%. If Bangla exceeds target,
flag "fine-tune required" and evaluate fine-tuned Bangla models (deferred from
the MVP scope).
