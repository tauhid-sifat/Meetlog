# Meetlog MVP Plan

## Summary

Build a Windows desktop app that captures meeting audio (microphone + system audio), transcribes it in real time via the Gemini Live API, and generates a structured Markdown meeting document. Supports English, Bangla, and mixed-language meetings. Local-first storage, provider-agnostic AI layer, raw transcript preserved. MVP is cloud-only (Gemini); local STT (Whisper) is deferred to post-MVP but the provider interface is designed for it.

## Context & Findings

**Stack:** Tauri v2 + Rust (audio/shell) + Python sidecar (AI) + React/TS (UI)
- Tauri v2 bundles Python as a single executable (PyInstaller) via `externalBin`; Rust spawns it and connects over a local TCP socket (sidecar prints its port to stdout).
- Rust WASAPI loopback via `cpal` v0.16+ (opens an input stream on the default render device) or the `wasapi` v0.25 crate. Mic + system audio captured separately, resampled to 16kHz mono PCM.
- Gemini Live API (`gemini-3.5-transcribe-live`): real-time STT, Bangla (`bn-BD`/`bn-IN`), automatic language detection + code-switching, `custom_vocabulary` up to 1,000 terms, VERBATIM or SMART mode. WebSocket, raw 16-bit PCM @16kHz. **Session limit: 10 minutes** (rotation required).
- Gemini LLM (`gemini-flash-latest`) handles meeting intelligence.
- Reference only: Stitch project `MeetMD Desktop UI System` (Precision Engineering design system). Not a build target; the spec's minimal UI (section 28) wins.

**Key deviation from spec:** MVP is cloud-only. No offline/no-internet mode. Both online and in-person meetings use Gemini. Provider abstraction retained so Whisper can be added later.

## Current status

| Phase | Status |
|-------|--------|
| 0 — STT validation | **Provisionally passed** on TTS-synthesized speech; real-recording benchmark + script-normalization issue open |
| 1 — Microphone → live transcript | Code complete and live-validated; real human microphone pending |
| 2 — Mic + Windows system audio | Not started (blocked: Rust toolchain not installed) |
| 3 — Transcript → Intelligence → Markdown | Code complete and live-validated |
| 4 — Desktop UI | Not started |
| 5 — Speaker intelligence | Not started |
| 6 — Advanced meeting intelligence | Not started |

## Constraints, Assumptions, Risks, Unknowns

| Type | Item | Mitigation |
|------|------|------------|
| Constraint | CPU-only dev machine | Cloud STT offloads compute; no local training. |
| Constraint | Gemini Live 10-min session limit | Session rotation with audio buffering across the reconnect window. |
| Constraint | Gemini free-tier quotas (TTS 10/day/model, per-model per-minute caps) | Use multiple TTS models or a paid tier for bulk benchmark synthesis. |
| Constraint | Solo developer, no deadline | Phased; each phase is a working increment. |
| Assumption | Gemini API key with sufficient quota | Verify before bulk runs; monitor cost. |
| Assumption | User records real meetings for the benchmark | User responsibility; critical path. |
| Risk | Bangla/mixed accuracy below bar on real speech | Benchmark on real recordings before any model change. |
| Risk | Script normalization (English/Banglish rendered in Bengali script) | Investigate as a normalization issue, not an STT failure (see open issue). |
| Risk | Echo when mixing mic + system audio | Recommend headphones; AEC in audio engine. |
| Risk | Rust/WASAPI audio capture reliability | Moved earlier (Phase 2); it is a top technical risk. |

## Workspace Setup

1. `git init` in `E:\My Code\Meetlog` (done)
2. Initial commit on `main` (`spec.md`, `.gitignore`) (done)
3. `develop` branch (done)
4. `feature/meetlog-mvp` off `develop` (done)
5. All work on `feature/meetlog-mvp`. No commits directly on `develop` or `main`.

## Roadmap (reordered — audio capture moved earlier)

Audio capture is a top technical risk, so mic and system-audio capture are proven before building the polished UI.

```
Phase 0  STT validation                         [provisionally passed]
Phase 1  Real microphone -> live transcript      [code done, real mic pending]
Phase 2  Mic + Windows system audio (loopback)   [blocked on Rust]
Phase 3  Transcript -> Intelligence -> Markdown  [code done, live validated]
Phase 4  Desktop UI
Phase 5  Speaker intelligence
Phase 6  Advanced meeting intelligence
Cross-Validation
```

---

## Phase 0: STT Validation

**Goal:** prove Gemini Live is good enough for real English/Bangla meetings before committing to it.

**Complete when:**
1. Gemini Live successfully transcribes English meeting speech.
2. Gemini Live successfully transcribes Bangla meeting speech.
3. Mixed English/Bangla speech is usable for meeting notes.
4. Transcript latency is acceptable for live use.
5. Technical terms and proper names are benchmarked.
6. Final transcript segments are not lost when stopping.
7. Sessions longer than 10 minutes can be rotated without losing transcript continuity.
8. Gemini does not introduce unacceptable script/language normalization.
9. API cost is measured for a realistic meeting.
10. The transcript can reliably feed the meeting intelligence pipeline.

**Status against criteria (TTS-synthesized speech, not real meetings):**

- [x] 1. English — WER 0.00
- [x] 2. Bangla — WER 0.00
- [~] 3. Mixed — WER 0.29; usable content but script issue (see 8)
- [ ] 4. Latency — not yet measured on real-time speech
- [~] 5. Terms/names — 4/8 cases run (names/products 3/3 preserved); rest pending quota
- [x] 6. Finals not lost on stop — bug fixed, `audio_stream_end` flush validated
- [x] 7. Rotation continuity — validated (4 connects, 4 segments, 0 errors)
- [ ] 8. Script normalization — **OPEN ISSUE**
- [ ] 9. API cost — not yet measured
- [x] 10. Feeds intelligence — validated end-to-end

**Open issue — script normalization:** see `docs/benchmark/stt-benchmark.md`. Banglish spoken as Bengali is rendered in Bengali script; some English words inside Bengali sentences are transliterated. Treated as normalization, not recognition failure. Mitigations to evaluate: `custom_vocabulary` / `language_hints`, or a post-processing transliteration pass.

**Deliverable:** `docs/benchmark/stt-benchmark.md` (preliminary) + selected providers. Real-recording benchmark outstanding.

---

## Phase 1: Microphone → Live Transcript

**Goal:** speak into the real microphone and see words appear live.

**Status:** code complete (`ai/stt/`, `ai/main.py`, `ai/cli_test.py`); device path smoke-tested; needs a human speaker to validate content.

**Steps:**
1. `STTProvider` interface (`ai/stt/base.py`). ✅
2. `GeminiLiveProvider` with rotation + buffering (`ai/stt/gemini.py`). ✅
3. TCP sidecar, port on stdout (`ai/main.py`). ✅
4. Mic harness (`ai/cli_test.py`), `--device`, `--list-devices`. ✅
5. Persist `transcript.json`. ✅
6. Run a real spoken test and record quality.

**Acceptance criteria:**
- [x] `ai/stt/base.py` defines abstract `STTProvider` with `connect/start/send_audio/receive_transcript/pause/resume/stop/disconnect`.
- [x] `ai/stt/gemini.py` implements `GeminiLiveProvider(STTProvider)`; `connect()` waits for the session and opens a WebSocket.
- [x] `ai/main.py` prints its listening port as a single parseable integer line on startup.
- [x] `ai/cli_test.py` opens the default microphone and streams 16kHz mono PCM without crashing.
- [ ] Speaking "We should finalize this before Thursday." yields a final segment containing "Thursday" within 5s of utterance end (real mic).
- [ ] Speaking a Bangla sentence yields a Bangla final segment (not transliterated).
- [ ] After stop, `transcript.json` is an array of segments with `id, speaker, start, end, text, language`.
- [x] Pause stops segment growth; resume restarts it (code path).
- [x] A >10 min session continues past 10 min with no lost transcript (rotation validated at a lowered threshold).

---

## Phase 2: Mic + Windows System Audio

**Goal:** capture both sides of an online meeting (microphone + WASAPI loopback).

**Steps:**
1. Install Rust toolchain (`rustup`).
2. Scaffold Tauri v2 + React/TS project.
3. `microphone.rs` via `cpal`; enumerate + select input device.
4. `system_audio.rs` via `cpal` WASAPI loopback.
5. Resample both to 16kHz mono f32; chunk (~100ms) to the sidecar over TCP.
6. Handle device-disconnect errors cleanly.

**Acceptance criteria:**
- [ ] `cargo build` in `src-tauri/` and `npm run build` in `src/` complete with no errors.
- [ ] `list_input_devices()` returns ≥1 device on a machine with a mic.
- [ ] Starting loopback opens a stream on the default render device (logged).
- [ ] Both streams report 16kHz mono f32 at stream start (logged).
- [ ] Playing a known clip through speakers yields non-silent loopback buffers (RMS > 0).
- [ ] The sidecar logs receipt of audio chunks over TCP.
- [ ] Unplugging the default audio device does not crash the app; capture stops with a surfaced error.

---

## Phase 3: Transcript → Meeting Intelligence → Markdown

**Goal:** turn a transcript into a structured `meeting.md`.

**Status:** code complete and live-validated (correct decision, action item with owner, open question; no invented items).

**Steps:**
1. `MeetingIntelligenceProvider` interface. ✅
2. `StructuredMeetingData` model. ✅
3. Gemini LLM provider with transient-error retry. ✅
4. Deterministic Markdown renderer. ✅
5. Meeting folder storage (`meeting.md`, `transcript.json`, `metadata.json`). ✅
6. `pipeline.generate_meeting`. ✅

**Acceptance criteria:**
- [x] `ai/intelligence/base.py` defines `process_transcript(transcript) -> StructuredMeetingData`.
- [x] `StructuredMeetingData` has `title, summary, decisions[], action_items[], open_questions[], important_dates[], discussion_topics[]`.
- [x] A sample transcript returns valid structured data.
- [x] A transcript with a decision yields it; one with no decisions yields empty (no invented items).
- [x] Renderer produces H1 title, Date/Duration/Mode/Participants block, and section-18 sections.
- [x] Empty sections are omitted.
- [x] Rendering the same fixture twice is byte-identical.
- [x] Meeting folder contains `meeting.md`, `transcript.json`, `metadata.json`.
- [x] `transcript.json` is unchanged by the intelligence step.

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
2. Post-meeting diarization (pyannote.audio or Gemini diarization).
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
- [ ] Decision extraction precision/recall improves over Phase 3 on the benchmark transcripts (numbers recorded).
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
