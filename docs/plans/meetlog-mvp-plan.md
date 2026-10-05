# Meetlog MVP Plan

## Summary

Build a Windows desktop app that captures meeting audio (microphone + system audio), transcribes it in real time via the Gemini Live API, and generates a structured Markdown meeting document. Supports English, Bangla, and mixed-language meetings. Local-first storage, provider-agnostic AI layer, raw transcript preserved. MVP is cloud-only (Gemini); local STT (Whisper) is deferred to post-MVP but the provider interface is designed for it.

## Context & Findings

**Stack:** Tauri v2 + Rust (audio/shell) + Python sidecar (AI) + React/TS (UI)
- Tauri v2 bundles Python as a single executable (PyInstaller) via `externalBin`; Rust spawns it and connects over a local TCP socket (sidecar prints its port to stdout).
- Rust WASAPI loopback via `cpal` v0.16+ (opens an input stream on the default render device) or the `wasapi` v0.25 crate. Mic + system audio captured separately, resampled to 16kHz mono PCM.
- Gemini Live API (`gemini-3.5-transcribe-live`): real-time STT, Bangla (`bn-BD`/`bn-IN`), automatic language detection + code-switching, `custom_vocabulary` up to 1,000 terms, VERBATIM or SMART mode. WebSocket, raw 16-bit PCM @16kHz. **Session limit: 10 minutes** (rotation required).
- Gemini LLM handles meeting intelligence.
- Reference only: Stitch project `MeetMD Desktop UI System` (Precision Engineering design system). Not a build target; the spec's minimal UI (section 28) wins.

**Key deviation from spec:** MVP is cloud-only. No offline/no-internet mode. Both online and in-person meetings use Gemini. Provider abstraction retained so Whisper can be added later.

## Constraints, Assumptions, Risks, Unknowns

| Type | Item | Mitigation |
|------|------|------------|
| Constraint | CPU-only dev machine | Cloud STT offloads compute; no local training. |
| Constraint | Gemini Live 10-min session limit | Session rotation; no gap >2s at boundary. |
| Constraint | Solo developer, no deadline | Phased; each phase is a working increment. |
| Assumption | Gemini API key with sufficient quota | Verify in Phase 0; monitor cost. |
| Assumption | User records 2-3 real meetings for the benchmark | User responsibility; critical path for Phase 0. |
| Risk | Gemini Bangla accuracy below bar | Phase 0 benchmark; fallback is fine-tuned Whisper (deferred). |
| Risk | Echo when mixing mic + system audio | Recommend headphones; AEC in audio engine. |
| Risk | Gemini API cost on long meetings | Usage monitoring; quota alerts. |
| Unknown | Gemini speaker identification in-stream | Test in Phase 0; else post-meeting diarization (Phase 5). |
| Unknown | Optimal audio chunk size for Gemini Live | Test in Phase 0; start at 100ms. |

## Workspace Setup

1. `git init` in `E:\My Code\Meetlog`
2. Initial commit on `main` (`spec.md`, `.gitignore`)
3. Create `develop` branch
4. Create `feature/meetlog-mvp` off `develop`
5. All work on `feature/meetlog-mvp`. No commits directly on `develop` or `main`.

## Proposed File Structure

```
Meetlog/
├── src-tauri/                  # Rust backend (Tauri)
│   ├── src/
│   │   ├── main.rs
│   │   ├── audio/{mod,microphone,system_audio}.rs
│   │   └── sidecar/mod.rs
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   └── capabilities/default.json
├── src/                        # React/TS frontend
│   ├── App.tsx
│   ├── components/{TranscriptView,MeetingControls,Settings,MarkdownView}.tsx
│   ├── hooks/useTranscript.ts
│   └── types/index.ts
├── ai/                         # Python sidecar
│   ├── main.py                 # TCP server entry
│   ├── stt/{base,gemini}.py
│   ├── intelligence/{base,gemini}.py
│   ├── models/transcript.py
│   ├── render/markdown.py
│   ├── storage/transcript.py
│   └── requirements.txt
├── tests/{data,integration}/
├── docs/{benchmark/stt-benchmark.md,plans/meetlog-mvp-plan.md}
├── package.json
├── tsconfig.json
├── vite.config.ts
└── README.md
```

---

## Phase 0: STT Benchmark

**Scope:** `tests/data/`, `ai/benchmark/`, `docs/benchmark/`

**Steps:**
1. Record 2-3 real meetings (30+ min each) covering English, Bangla, mixed. Save to `tests/data/`.
2. Create ground-truth transcripts (`.txt`) alongside each recording.
3. Add `google-genai` to `ai/requirements.txt`; store API key in env var.
4. Write `ai/benchmark/run_benchmark.py`: streams an audio file to Gemini Live, computes WER/CER per language segment.
5. Test English, Bangla, mixed, Banglish separately; measure latency and cost.
6. Test `custom_vocabulary` with the section 24 terms; compare WER on those terms.
7. Test session rotation on a >10 min file.
8. Write `docs/benchmark/stt-benchmark.md`.

**Acceptance criteria:**
- [ ] `tests/data/` contains ≥2 recordings, each ≥30 min, each with a sibling `.txt` ground-truth transcript.
- [ ] `ai/benchmark/run_benchmark.py` runs on a given audio+transcript pair and prints WER, CER, and latency (p50/p95).
- [ ] English segment of recording 1 reports WER; value recorded in the report (pass target ≤15%).
- [ ] Bangla segment reports WER (pass target ≤20%); if above, the report flags "fine-tune required".
- [ ] Mixed/Banglish segment produces a transcript without auto-translating Bangla to English.
- [ ] Custom-vocabulary test shows improved WER on the 10 section-24 terms vs baseline; result recorded.
- [ ] A >10 min file transcribes with no gap >2s at the 10-minute boundary (rotation verified).
- [ ] `docs/benchmark/stt-benchmark.md` contains a table: Provider, Language, WER, CER, Latency p50/p95, Cost/hour.
- [ ] Selected MVP provider(s) are explicitly recorded in the report.

---

## Phase 1: Microphone Transcription Prototype

**Scope:** `ai/stt/`, `ai/main.py`, `ai/cli_test.py`

**Steps:**
1. Define `STTProvider` in `ai/stt/base.py`.
2. Implement `GeminiLiveProvider` in `ai/stt/gemini.py` with session rotation.
3. Write `ai/main.py` as a TCP server receiving audio chunks, emitting transcript segments.
4. Write `ai/cli_test.py`: captures mic via `sounddevice`, streams to sidecar, prints live transcript.
5. Persist raw transcript to `transcript.json`.

**Acceptance criteria:**
- [ ] `ai/stt/base.py` defines abstract `STTProvider` with `connect/start/send_audio/receive_transcript/pause/resume/stop/disconnect`; importing it raises no errors.
- [ ] `ai/stt/gemini.py` implements `GeminiLiveProvider(STTProvider)`; `connect()` with a valid key opens a WebSocket session.
- [ ] `ai/main.py` prints its listening port as a single parseable integer line on startup.
- [ ] `ai/cli_test.py` captures 30s of mic audio and prints interim + final transcript lines.
- [ ] Saying "We should finalize this before Thursday." yields a final segment containing "Thursday" within 5s of utterance end.
- [ ] Saying "আমাদের এটা বৃহস্পতিবারের মধ্যে ফাইনাল করতে হবে।" yields a Bangla final segment (not transliterated).
- [ ] A mixed sentence yields one segment labeled `language: "mixed"`.
- [ ] After stop, `transcript.json` is an array of segments each with `id, speaker, start, end, text, language`.
- [ ] Pause stops segment growth; resume restarts it.
- [ ] A >10 min session continues past 10 min with no dropped audio.

---

## Phase 2: Markdown Pipeline

**Scope:** `ai/intelligence/`, `ai/models/`, `ai/render/`, `ai/storage/`

**Steps:**
1. Define `MeetingIntelligenceProvider` in `ai/intelligence/base.py`.
2. Define `StructuredMeetingData` in `ai/models/transcript.py`.
3. Implement Gemini LLM provider in `ai/intelligence/gemini.py`.
4. Write deterministic renderer `ai/render/markdown.py`.
5. Omit empty sections.
6. Write `meeting.md`, `transcript.json`, `metadata.json` to `Meetings/<date> - <title>/`.

**Acceptance criteria:**
- [ ] `ai/intelligence/base.py` defines `process_transcript(transcript) -> StructuredMeetingData`.
- [ ] `StructuredMeetingData` has `title, summary, decisions[], action_items[], open_questions[], important_dates[], discussion_topics[]`.
- [ ] A sample transcript returns a `StructuredMeetingData` that validates against the schema.
- [ ] A transcript containing a decision yields it in `decisions`; a transcript with no decisions yields an empty `decisions` (no invented items).
- [ ] Renderer produces Markdown with H1 title, Date/Duration/Mode/Participants block, and the spec section-18 sections.
- [ ] If `open_questions` is empty, the output contains no `## Open Questions` heading.
- [ ] Rendering the same fixture twice is byte-identical (deterministic).
- [ ] Meeting folder `Meetings/<YYYY-MM-DD> - <Title>/` contains `meeting.md`, `transcript.json`, `metadata.json`.
- [ ] `transcript.json` is unchanged by the intelligence step.

---

## Phase 3: Online Audio Engine

**Scope:** `src-tauri/src/audio/`, `src-tauri/tauri.conf.json`, sidecar wiring

**Steps:**
1. Scaffold Tauri v2 + React/TS project.
2. `microphone.rs` via `cpal`; enumerate + select input device.
3. `system_audio.rs` via `cpal` WASAPI loopback.
4. Resample both to 16kHz mono f32; chunk (~100ms) to the sidecar over TCP.
5. Handle device-disconnect errors cleanly.

**Acceptance criteria:**
- [ ] `cargo build` in `src-tauri/` and `npm run build` in `src/` complete with no errors.
- [ ] `list_input_devices()` returns ≥1 device on a machine with a mic.
- [ ] Starting loopback opens a stream on the default render device (logged).
- [ ] Both streams report 16kHz mono f32 at stream start (logged).
- [ ] Playing a known clip through speakers yields non-silent loopback buffers (RMS > 0).
- [ ] The sidecar logs receipt of audio chunks over TCP.
- [ ] Unplugging the default audio device does not crash the app; capture stops with a surfaced error.

---

## Phase 4: Desktop UI

**Scope:** `src/` (React/TS), `src-tauri/src/main.rs`, `src-tauri/src/sidecar/mod.rs`

**Steps:**
1. Main view: live transcript, recording indicator, timer, editable title.
2. Controls: start, stop, pause, resume.
3. Settings: mic selection, output dir, API key, custom vocabulary editor.
4. Meeting history list + open folder/Markdown.
5. Markdown preview.
6. Sidecar lifecycle (spawn on start, kill on close).
7. Wire audio → sidecar → transcript state → UI.
8. Start/stop flow: create folder, capture, on stop run intelligence + write `meeting.md`.
9. Persist settings.

**Acceptance criteria:**
- [ ] `npm run tauri dev` launches a window showing the live transcript view.
- [ ] "Start Meeting" (Online) creates a meeting folder and begins transcription; timer increments.
- [ ] Transcript rows appear within 3s of speech with speaker label + timestamp + text.
- [ ] Pause stops new rows; Resume continues.
- [ ] "Stop Meeting" writes `meeting.md` and the UI offers to open it.
- [ ] Settings survive restart: mic, output dir, API key all retained.
- [ ] API key is stored in Windows Credential Manager / OS keychain, not plaintext config.
- [ ] Custom vocabulary editor adds a term; the term reaches the STT provider (verified in logs).
- [ ] Meeting history lists past meetings; "Open Markdown" opens the OS default editor.
- [ ] Mic-unavailable shows an error state, no crash.

---

## Phase 5: Speaker Intelligence

**Scope:** `ai/diarization/`, `src/components/TranscriptView.tsx`

**Steps:**
1. Optional `audio.wav` capture (user-controlled).
2. Post-meeting diarization (pyannote.audio or equivalent).
3. Align diarization with transcript segments; assign speaker IDs.
4. Speaker-renaming UI.
5. Renamed speakers flow into `meeting.md`.

**Acceptance criteria:**
- [ ] With retention enabled, `audio.wav` is written to the meeting folder.
- [ ] Diarization on a 2-speaker recording yields ≥2 distinct speaker labels.
- [ ] Transcript segments carry speaker IDs and the UI shows "Speaker 1"/"Speaker 2".
- [ ] Renaming "Speaker 1" → "Tauhid" updates all segments and the rendered `meeting.md`.
- [ ] If diarization fails, pipeline falls back to a single "Speaker" label and still writes `meeting.md`.

---

## Phase 6: Advanced Meeting Intelligence

**Scope:** `ai/intelligence/gemini.py`, `ai/render/markdown.py`

**Steps:**
1. Few-shot decision detection.
2. Action items with owner identification.
3. Requirement + risk extraction; topic grouping.
4. Custom Markdown templates.
5. Meeting comparison.

**Acceptance criteria:**
- [ ] Decision extraction precision/recall improves over Phase 2 on the benchmark transcripts (numbers recorded).
- [ ] Action items include an owner when stated; unstated owners are `null`.
- [ ] A template at `templates/custom.md.j2` can be selected and is used for rendering.
- [ ] Meeting comparison outputs differences in decisions/action items between two meetings.
- [ ] Requirement and risk sections populate when present.

---

## Cross-Validation Phase

**Scope:** all

**Steps:**
1. Run `pytest` (`ai/`), `cargo test` (`src-tauri/`), `npm test` (`src/`).
2. End-to-end: Online meeting, speak 2 min, stop, verify `meeting.md`.
3. Reconcile every acceptance criterion above.
4. One final overall code review.
5. Error-path tests.

**Acceptance criteria:**
- [ ] `pytest`, `cargo test`, `npm test` all pass.
- [ ] E2E: start Online meeting, speak 2 min, stop → `meeting.md` exists with all non-empty sections correct.
- [ ] Every acceptance criterion in Phases 0-6 is checked and marked pass/fail.
- [ ] One final code review completed across the codebase.
- [ ] Error handling verified for: mic unavailable, system audio unavailable, API failure, network disconnect, quota exceeded.

---

## Out of Scope

- Local STT (Whisper/faster-whisper) — post-MVP
- Offline/no-internet mode — post-MVP
- Local LLM — post-MVP
- TTS / voice output
- Calendar / Meet / Teams / Zoom API integrations
- Cloud storage, team collaboration, CRM, project management
- Global hotkey, system tray, automatic meeting detection
- Automatic email follow-ups
- The rich Stitch UI (telemetry panels, entity graph, command palette) — visual reference only

## Rollback Note

Plain branch in the current working directory. To abandon: delete `feature/meetlog-mvp` and reset `develop` to its prior state. No worktree to clean up.
