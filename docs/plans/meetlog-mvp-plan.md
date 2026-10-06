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
| 2 — Mic + Windows system audio | Code complete and verified (mic + WASAPI loopback + sidecar integration) |
| 3 — Transcript → Intelligence → Markdown | Code complete and live-validated |
| 4 — Desktop UI | Code complete; UI builds, app launches, sidecar connects; live meeting flow pending a real API key |
| 5 — Speaker intelligence | Renaming end-to-end (sidecar map + UI panel); audio.wav retention deferred |
| 6 — Advanced meeting intelligence | Code complete: requirements/risks extraction, custom Jinja templates, meeting comparison |

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

**Status:** code complete and verified. Toolchain: Rust stable-x86_64-pc-windows-gnu + WinLibs MinGW-w64 (see `src-tauri/.cargo/config.toml`).

**Steps:**
1. Install Rust toolchain (`rustup`) + MinGW. ✅
2. Scaffold Tauri v2 + React/TS project. ✅
3. `microphone.rs` via `cpal`; enumerate + select input device. ✅
4. `system_audio.rs` via `cpal` WASAPI loopback. ✅
5. Resample both to 16kHz mono; chunk to the sidecar over TCP. ✅
6. Handle device-disconnect errors cleanly. (partial)

**Acceptance criteria:**
- [x] `cargo build` in `src-tauri/` and `npm run build` in `src/` complete with no errors.
- [x] `list_input_devices()` returns ≥1 device on a machine with a mic.
- [x] Starting loopback opens a stream on the default render device (logged).
- [x] Both streams are resampled to 16kHz mono (logged: 48kHz source).
- [x] Playing a known clip through the same endpoint yields non-silent loopback buffers (self-test avg RMS 0.21).
- [x] The sidecar logs receipt of audio chunks over TCP (`ping` returns `audio_chunks`).
- [x] The app spawns the sidecar, reads its port, and connects (`sidecar ready` in logs).
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
- [x] `npm run tauri dev` launches a window showing the live transcript view.
- [~] "Start Meeting" (Online) creates a meeting folder and begins transcription; timer increments. (wired; needs live run)
- [~] Transcript rows appear within 3s of speech with speaker label + timestamp + text. (wired; needs live run)
- [x] Pause stops new rows; Resume continues. (wired)
- [~] "Stop Meeting" writes `meeting.md` and the UI offers to open it. (wired; validated in Phase 3 pipeline)
- [x] Settings survive restart: mic, output dir, API key all retained.
- [x] API key is stored in Windows Credential Manager, not plaintext config.
- [~] Custom vocabulary editor adds a term; the term reaches the STT provider. (wired; verified in sidecar tests)
- [x] Meeting history lists past meetings; "Open Markdown" opens the OS default editor.
- [~] Mic-unavailable shows an error state, no crash. (error surfaced; hard to trigger automatically)

---

## Phase 5: Speaker Intelligence

**Scope:** `ai/main.py` (rename map), `src/components/LiveView.tsx`, `src/hooks/useMeeting.ts`

**Status:** speaker renaming end-to-end. Diarization reuses the provider's
`speaker_label` (Gemini flag, already plumbed); no pyannote — heavy native
dependency that conflicts with the cloud-only MVP. `audio.wav` retention is
deferred: it needs folder-path coordination between the Rust capturer and the
Python sidecar across processes.

**Steps:**
1. Optional `audio.wav` capture (user-controlled). (deferred — see above)
2. Post-meeting diarization (pyannote.audio or Gemini diarization). (Gemini flag only)
3. Align diarization with transcript segments; assign speaker IDs. ✅ (labels flow through)
4. Speaker-renaming UI. ✅ (`rename_speaker` message + Speakers panel)
5. Renamed speakers flow into `meeting.md`. ✅ (participants set at stop)

**Acceptance criteria:**
- [ ] With retention enabled, `audio.wav` is written to the meeting folder. (deferred)
- [x] Diarization on a 2-speaker recording yields ≥2 distinct speaker labels. (via provider `speaker_label`; Gemini flag plumbed through)
- [x] Transcript segments carry speaker IDs and the UI shows "Speaker 1"/"Speaker 2".
- [x] Renaming "Speaker 1" → "Tauhid" updates all segments and the rendered `meeting.md`.
- [x] If diarization fails, pipeline falls back to a single "Speaker" label and still writes `meeting.md`. (normalize default)

---

## Phase 6: Advanced Meeting Intelligence

**Scope:** `ai/intelligence/gemini.py`, `ai/render/markdown.py`, `ai/render/templates.py`, `ai/compare.py`, `templates/`

**Status:** code complete (built peer-to-peer in three parallel workstreams: intelligence, rendering/comparison, robustness). Live-API precision/recall numbers still need a real-recording benchmark with an API key.

**Steps:**
1. Few-shot decision detection. ✅ (prompt rules + examples)
2. Action items with owner identification. ✅ (owner-only-when-assigned rule)
3. Requirement + risk extraction; topic grouping. ✅ (new schema fields + prompt rules)
4. Custom Markdown templates. ✅ (`templates/meeting.md.j2` default, `templates/custom.md.j2` slim; `render_with_template`)
5. Meeting comparison. ✅ (`ai/compare.py`: exact-text diff + deterministic Markdown)

**Acceptance criteria:**
- [~] Decision extraction precision/recall improves over Phase 3 on the benchmark transcripts. (rules in place; live numbers need real recordings + API key)
- [x] Action items include an owner when stated; unstated owners are `null`. (rule + tests)
- [x] A template at `templates/custom.md.j2` can be selected and is used for rendering.
- [x] Meeting comparison outputs differences in decisions/action items between two meetings.
- [x] Requirement and risk sections populate when present (and are omitted when empty).

---

## Cross-Validation Phase

**Scope:** all

**Status:** final code review complete (peer agent, static). pytest 79 passed / 1 skipped, `cargo check` and `npm run build` green. Live and device-dependent items still need a real meeting.

**Steps:**
1. Run `pytest` (`ai/`), `cargo test` (`src-tauri/`), `npm test` (`src/`). ✅ (pytest green; `cargo test`/`npm test` have no test targets — verification is `cargo check` + `tsc` build, both green)
2. End-to-end: Online meeting, speak 2 min, stop, verify `meeting.md`. (needs live run)
3. Reconcile every acceptance criterion above. ✅ (Agent R checklist; NEEDS-LIVE items listed below)
4. One final overall code review. ✅ (found and fixed B1 session-reset blocker, I1/I2/I7/I8/I10, I3 stop fallback)
5. Error-path tests. ✅ (`tests/test_error_paths.py`, `tests/test_session_lifecycle.py`)

**Acceptance criteria:**
- [x] `pytest`, `cargo test`, `npm test` all pass. (pytest 79/1 skip; no Rust/TS test targets exist)
- [ ] E2E: start Online meeting, speak 2 min, stop → `meeting.md` exists with all non-empty sections correct. (needs live run)
- [x] Every acceptance criterion in Phases 0-6 is checked and marked pass/fail. (review checklist)
- [x] One final code review completed across the codebase.
- [~] Error handling verified for: mic unavailable, system audio unavailable, API failure, network disconnect, quota exceeded. (offline paths covered; live + device-unplug need hardware)

**Deferred from review (explicit):** optimistic-rename rollback on sidecar rejection (unreachable via UI — renames originate from the displayed list); device-disconnect surfacing to UI (needs audio-thread→UI event plumbing; unplug test still manual); dangling-header/chronology/compare-case-sensitivity nits.

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
