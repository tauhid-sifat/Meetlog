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

**Mixed-language finding (refined):** script behavior depends on the
surrounding script.

- English words inside a Bengali-script sentence may be transliterated. For
  `আমাদের Thursday-এর মধ্যে এটা finalize করতে হবে।` the model returned
  `আমাদের থার্সডে-র মধ্যে এটা ফাইনালইজ করতে হবে।` (Thursday → থার্সডে,
  finalize → ফাইনালইজ).
- English words inside Latin/Banglish text are preserved: `Thursday te client
  review ache.` came back verbatim.
- Romanized Bangla (Banglish) spoken as Bengali is rendered in Bengali script:
  `Eta basically existing workflow-er sathei integrate hobe.` became
  `এটা বেসিক্যালি এক্সিস্টিং ওয়ার্কফ্লোর সাথে ইন্টিগ্রেট হবে।`

This is a **normalization** issue, not a recognition failure: the model
understands the words and chooses script. WER/CER penalise the script change.
The spec (section 10) expects Latin script for code-switched English. Possible
mitigations: `custom_vocabulary` / `language_hints` per term, or a
post-processing transliteration pass. Tracked as an open issue.

### Real-meeting finding: wrong-language hallucination

A real Bangla+English meeting produced segments in scripts the user never
spoke: Hindi (Devanagari, e.g. `कैसे हो, ठीक हो?`, `वाओ।`) and Japanese
(hiragana, e.g. `おまけ、おまけ。`). This is distinct from the TTS script
normalization above — the model picked the wrong language, not just the wrong
script for the right language.

What we know:
- `language_codes=["bn-BD", "en-US"]` is sent on every session (provider
  default), but the Live API treats it as a recognition hint, not a hard
  output filter. The TTS ablation confirms it does not change script choice
  on clear audio.
- Short, low-confidence fragments (interjections like "wow") are the most
  likely to be misidentified.

What this fix does:
- `detect_language` now truthfully identifies Devanagari → `hindi`,
  hiragana/katakana → `japanese`, CJK → `chinese`, instead of mislabeling
  them `unknown`. The raw transcript is preserved untouched; only the label
  is corrected, so suspect segments are visible in the UI and `transcript.json`.
- No silent filtering or auto-correction: mapping Hindi back to Bangla would
  be wrong (`कैसे हो` is Hindi, not a transliteration of `কেমন আছো`).

Still open: preventing the hallucination itself. Options if it persists on
real speech are a stronger provider-level constraint (if the API gains one),
a short-audio confidence gate, or revisiting the STT provider choice. That
decision needs a real-recording benchmark first.

### Terminology / script preservation

Run with `scripts/validate_terminology.py` (TTS via `gemini-3.8-flash-tts`).
Free-tier TTS quota (10/day for `gemini-2.5-flash-tts`, 3/min for
`gemini-3.8-flash-tts`) stopped the run after 4 of 8 cases.

| Case | Spoken | Transcript | WER | Latin tokens kept |
|------|--------|------------|-----|-------------------|
| English in Bangla | `Thursday te client review ache.` | `Thursday te client review ache.` | 0.00 | 3/3 |
| Bangla in English | `We should finalize it, kintu deadline ta tight.` | verbatim | 0.00 | 2/2 |
| Banglish | `Eta basically existing workflow-er sathei integrate hobe.` | `এটা বেসিক্যালি এক্সিস্টিং ওয়ার্কফ্লোর সাথে ইন্টিগ্রেট হবে।` | 1.00 | 0/4 |
| Names / products | `Constance will update the Figma file and open a Jira ticket.` | verbatim | 0.00 | 3/3 |
| Dates / numbers | `The deadline is October 8, 2026 at 3 PM.` | — | — | pending quota |
| Technical in Bangla | `আমাদের RBAC আর IAM নিয়ে কাজ করতে হবে।` | — | — | pending quota |
| Internal terms | `Please check the FortiMapp endpoint and the Caboodle integration.` | — | — | pending quota |
| Count in Bangla | `Meeting e 25 jon attend korbe.` | — | — | pending quota |

Preliminary read: proper nouns and product names in Latin sentences are
preserved reliably; the problem is concentrated in Banglish and English words
embedded in Bengali script.

### Ablation: script-normalization mitigations

Run with `scripts/experiment_script.py` on the cached `mixed` and `banglish`
clips (no TTS quota used). Variants: baseline, `system_instruction`,
`custom_vocabulary`, both, `language_hints`.

| Clip | Variant | WER | Latin chars | Transcript |
|------|---------|-----|-------------|------------|
| mixed | baseline | 0.29 | 0 | `আমাদের থার্সডে-র মধ্যে এটা ফাইনালইজ করতে হবে।` |
| mixed | system_instruction | 0.29 | 0 | (unchanged) |
| mixed | custom_vocabulary | 0.29 | 0 | (unchanged) |
| mixed | language_hints `en-US` | 1.00 | 42 | `Amader Thursday er modhye eta finalize korte hobe.` |
| banglish | baseline | 1.00 | 0 | `এটা বেসিক্যালি এক্সিস্টিং ওয়ার্কফ্লোর সাথে ইন্টিগ্রেট হবে।` |
| banglish | system_instruction | 1.00 | 0 | (unchanged) |
| banglish | **custom_vocabulary** | **0.71** | **34** | `এটা basically existing workflow এর সাথে integrate হবে।` |
| banglish | language_hints `en-US` | 0.29 | 46 | `Eta basically existing workflow sathe integrate hobe.` |

**Conclusions:**
- `system_instruction` has **no effect** on the transcribe-live model.
- `custom_vocabulary` is a **partial mitigation**: listed English terms are
  kept in Latin script when the model would otherwise use Bengali script
  (banglish WER 1.00 → 0.71) **without** breaking Bengali script.
- `language_hints` (a `LanguageHints(language_codes=[...])` object, not a plain
  list) forces the output script: `en-US` romanizes the Bengali
  (`আমাদের` → `Amader`), which is wrong for Bengali meetings. Not suitable as a
  global setting.

**Recommended direction:** populate `custom_vocabulary` with the meeting's
English product names and technical terms (already planned, spec section 24) as
a first-line mitigation. General English words embedded in Bengali script may
still be transliterated; evaluate a post-processing transliteration pass for
those, but do not switch models.

### Real meeting recordings

| Provider | Model | Language | WER | CER | Latency p50 (s) | Latency p95 (s) | Cost/hour | Notes |
|----------|-------|----------|-----|-----|-----------------|-----------------|-----------|-------|
| Gemini Live | gemini-3.5-transcribe-live | English | — | — | — | — | — | pending recordings |
| Gemini Live | gemini-3.5-transcribe-live | Bangla | — | — | — | — | — | pending recordings |
| Gemini Live | gemini-3.5-transcribe-live | Mixed / Banglish | — | — | — | — | — | pending recordings |

## Custom vocabulary

Not yet measured (pending TTS/API quota). Run
`scripts/validate_terminology.py --vocab "Thursday,FortiMapp,Caboodle,RBAC,IAM,Jira,Figma"`
and compare against the baseline above.

| Terms | WER (baseline) | WER (with vocabulary) | Delta |
|-------|----------------|-----------------------|-------|
| section-24 terms | — | — | pending |

## Session rotation

Validated with `scripts/validate_rotation.py` at a lowered rotation interval
(45s of audio, rotate every 12s) to exercise the >10-minute path quickly. The
provider flushes finals before rotating and buffers audio across the reconnect
window.

| Audio length | Rotation interval | Session connects | Segments | Errors | Result |
|--------------|-------------------|------------------|----------|--------|--------|
| 45s (looped) | 12s | 4 | 4 | 0 | PASS |

Real 10-minute sessions still to be run end-to-end.

## Decision

Selected MVP provider(s): **Gemini Live `gemini-3.5-transcribe-live`** for
speech-to-text and **`gemini-flash-latest`** for meeting intelligence. The live
path is confirmed working end-to-end on synthetic speech (English and Bangla
exact). The real-recording benchmark and the mixed-script mitigation remain
open before this decision is final.

Pass targets: English WER ≤ 15%, Bangla WER ≤ 20%. If Bangla exceeds target,
flag "fine-tune required" and evaluate fine-tuned Bangla models (deferred from
the MVP scope).
