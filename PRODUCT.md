# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

People who hold meetings in English, Bangla, or mixed English/Bangla and need reliable meeting documentation without taking notes during the conversation.

The user starts a meeting and focuses on the conversation while the application captures, transcribes, and structures it. Downstream, the resulting files are used with Markdown editors, Git repositories, knowledge bases, AI tools, documentation systems, and local search.

That the primary buyer or team role is a developer, business analyst, or small mixed-language team operating in a bilingual meeting culture is (inferred). No specific persona, team size, or industry is confirmed.

## Product Purpose

Meetlog listens to meetings through microphone and/or Windows system audio, produces a live English/Bangla transcript, and generates a structured Markdown meeting document (`meeting.md`).

The goal is to make meeting documentation nearly automatic: capture the conversation, transcribe it in real time, handle English/Bangla code-switching, preserve the original conversation, identify useful meeting information, and produce a clean Markdown document.

The core principle is: Capture everything. Preserve what was said. Structure what matters.

Success means a user can open the Windows application, choose Online or Offline mode, capture microphone audio (plus system audio in Online mode), transcribe English and Bangla speech in real time including code-switching, see the live transcript, stop the meeting, generate a structured `meeting.md`, review decisions and action items, access the full transcript, and recover the raw transcript if AI processing makes a mistake.

## Positioning

A meeting listener that works regardless of where the meeting happens, built first for real English/Bangla mixed speech, and committed to an open portable record rather than a closed dashboard.

Neighboring transcription tools could not truthfully copy this combination: audio-source agnosticism with no per-platform meeting integrations required; English plus Bangla as a core case including code-switching and Banglish preserved as spoken rather than auto-translated; provider-agnostic STT and meeting-intelligence layers; raw transcript preservation alongside structured output; and AI structures while the application deterministically renders the final Markdown.

## Operating Context

Windows desktop application (Tauri v2 shell). Online meetings happen in Google Meet, Microsoft Teams, Zoom, Discord, browser-based meetings, or other desktop applications; the application captures microphone plus Windows system audio (initial direction: WASAPI loopback) and preserves the mic/system distinction where possible. In-person meetings use laptop or external microphone only.

Supported microphone classes include built-in laptop microphone, USB microphone, wired headset, Bluetooth headset, external conference microphone, and other Windows recording devices; the user selects the microphone.

The durable artifact is a local meeting folder, for example `Meetings/2026-10-05 - Feature Discussion/` containing `meeting.md`, `transcript.json`, and `metadata.json`, with optional `audio.wav` only when the user enables audio retention.

Downstream contexts are Markdown editors, Git repositories, knowledge bases, AI tools, documentation systems, local search, and developer/BA workflows; generated files must remain readable without the application.

Echo is a known risk when mixing microphone and system audio; current guidance is to use headphones.

## Capabilities and Constraints

Confirmed functionality and constraints:

- Two meeting modes: Online (microphone plus system audio) and Offline/In-Person (microphone only).
- Microphone capture with user-selectable device; system-audio capture via Windows loopback for Online mode; both streams resampled (current implementation: 16 kHz mono PCM) and fed to the selected STT provider through an audio engine without provider-specific logic.
- Interchangeable STT providers behind a common interface (`connect/start/sendAudio/receiveTranscript/pause/resume/stop/disconnect`); the application must not hard-code a single provider.
- MVP processing is cloud-only via Gemini Live transcription plus a Gemini LLM for meeting intelligence (inferred) as the configured cloud providers; local STT, local LLM, and no-internet operation are deferred post-MVP while the provider abstraction is retained.
- Language support: English, Bangla, mixed English/Bangla, and Banglish; default behavior preserves the language actually spoken with no automatic Bangla-to-English translation.
- Live transcript with streaming updates, timestamps, automatic saving, and approximately 1-3 seconds latency where practical; accuracy takes priority over the latency target.
- Raw transcript preserved with per-segment identity, speaker, start/end, text, and language; the intelligence step must not destroy it, enabling recovery, reprocessing, comparison, and debugging.
- Speaker diarization starting at `Speaker 1/2/3` labels with user renaming (for example `Speaker 1` to Tauhid); diarization must not block the MVP.
- Meeting intelligence identifies summary, discussion topics, decisions, action items, open questions, important dates, deadlines, requirements, blockers, risks, mentioned people, and mentioned projects; it must distinguish confirmed from possible/uncertain information and must not invent decisions, action items, deadlines, or requirements.
- Intelligence is independent from STT and returns structured data; a deterministic Markdown renderer converts that data into `meeting.md` following the default structure (title, date/duration/mode/participants, summary, discussion, decisions, action items, open questions, important dates, full transcript), omitting empty sections.
- Custom vocabulary/context dictionary usable by whichever provider supports it.
- MVP controls: start meeting, pause, resume, stop meeting, select microphone, enable/disable system audio, select AI provider, view live transcript, edit meeting title, open generated Markdown, select output directory.
- Privacy: local processing preferred where possible; cloud processing explicit and clearly indicated; no audio upload without user configuration; meeting files stored locally by default; temporary audio cleaned per user settings; API keys never in plain text (current implementation uses Windows Credential Manager); user can disable cloud providers.
- Graceful handling of microphone unavailable, system audio unavailable, STT provider unavailable, internet disconnect (Offline mode must not depend on internet once local STT lands), API quota exceeded, local model unavailable, AI processing failure, insufficient resources, audio device changes, and provider interruptions, preserving captured state and allowing recovery where possible.
- Non-goals for the MVP: calendar integration; Meet/Teams/Zoom API integrations; team collaboration; cloud storage; enterprise administration; CRM and project-management features; advanced TTS and voice assistant; complex dashboards; automatic email follow-ups.

Open decisions:

- Final local STT model choice, pending a real-recording benchmark covering English, Bangla, code-switching, Banglish, terminology, names, speed, multi-speaker, long sessions, latency, and CPU/GPU/RAM behavior.
- Script-normalization handling where Banglish or English words are rendered in Bengali script; whether mitigations are `custom_vocabulary`/`language_hints`, a post-processing pass, or accepted behavior.
- MVP meaning of Offline/In-Person mode: the spec requires a no-internet workflow with local STT, the implementation plan defers that post-MVP, and current start-screen copy describes in-person capture as working fully offline; which claim governs the MVP.
- Final processing profiles (Offline/Balanced/Best Quality) and when the user can choose a preferred mode.
- Whether MVP diarization promises anything beyond provider speaker labels plus rename with single-speaker fallback.
- Audio-retention default and cross-process coordination for `audio.wav`.
- Translation as a future feature; scope and default behavior undecided.
- TTS provider and any voice-output features; optional and undecided.

## Brand Commitments

Name: meetlog (application identifier `com.meetlog.app`).

Committed posture: minimal UX that stays out of the way of the meeting rather than becoming a meeting-management dashboard; accuracy of real English/Bangla transcription over feature breadth. No confirmed voice, logo, palette, typography, or messaging beyond the product name and this restraint.

## Evidence on Hand

- `spec.md`: authoritative product spec (meeting modes, audio, STT, language, transcript, intelligence, Markdown, privacy, scope, principles, vision).
- `docs/plans/meetlog-mvp-plan.md`: MVP implementation plan including the cloud-only deviation, phase status, constraints, risks, and out-of-scope list.
- `docs/benchmark/stt-benchmark.md` (referenced by the plan): preliminary TTS-synthesized STT evidence only; real-recording benchmark, latency measurement, API-cost measurement, and script-normalization resolution are outstanding.
- `package.json` and `src-tauri/tauri.conf.json`: app identity (`meetlog`, `0.1.0`, `com.meetlog.app`) and Tauri v2 desktop bounds.
- `src/components/*.tsx`: confirms start/setup, live transcript, meeting history, and settings areas exist as implementation; not product claims.

No testimonials, customers, case studies, press, benchmarks for marketing, pricing, licensing, or deployment claims exist. Future work must not fabricate them.

## Product Principles

- Audio-source agnostic: if the user can hear the meeting, the app should be able to capture it, without per-platform integrations.
- English plus Bangla first: mixed speech is the core case; preserve what was said and never auto-translate by default.
- Preserve the source: raw transcript survives cleanup and summarization; accuracy outranks added features.
- Provider-agnostic structure: STT, intelligence, and any future voice layers are replaceable; AI determines meeting information while the application controls document structure.
- Portable memory with minimal intrusion: local-first Markdown as the durable record, readable without the app, produced by an interface that stays out of the meeting.
