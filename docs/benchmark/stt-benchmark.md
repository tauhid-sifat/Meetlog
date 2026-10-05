# STT Benchmark Report

Status: **scaffold** — no recordings have been benchmarked yet.

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

| Provider | Model | Language | WER | CER | Latency p50 (s) | Latency p95 (s) | Cost/hour | Notes |
|----------|-------|----------|-----|-----|-----------------|-----------------|-----------|-------|
| Gemini Live | _(unset)_ | English | — | — | — | — | — | not yet run |
| Gemini Live | _(unset)_ | Bangla | — | — | — | — | — | not yet run |
| Gemini Live | _(unset)_ | Mixed / Banglish | — | — | — | — | — | not yet run |

## Custom vocabulary

| Terms | WER (baseline) | WER (with vocabulary) | Delta |
|-------|----------------|-----------------------|-------|
| 10 section-24 terms | — | — | — |

## Session rotation

| Audio length | Gap at 10-min boundary | Dropped audio |
|--------------|------------------------|---------------|
| — | — | — |

## Decision

Selected MVP provider(s): _(to be filled in after benchmarking)_

Pass targets: English WER ≤ 15%, Bangla WER ≤ 20%. If Bangla exceeds target,
flag "fine-tune required" and evaluate fine-tuned Bangla models (deferred from
the MVP scope).
