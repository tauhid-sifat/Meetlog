# Meeting Transcription & Meeting Memory

## 1. Product Overview

A Windows desktop application that listens to meetings through the user's microphone and/or system audio, produces a live English/Bangla transcript, understands the meeting, and generates a structured Markdown meeting document.

The application is designed for both:

* **Online meetings**: microphone + system audio
* **Offline/in-person meetings**: microphone only

The primary user-facing artifact is a Markdown file.

```text
Meeting Audio
     ↓
Speech-to-Text
     ↓
Live Transcript
     ↓
Meeting Intelligence
     ↓
Structured Markdown
     ↓
meeting.md
```

The application should support multiple AI providers rather than being tightly coupled to a single model.

---

# 2. Product Goal

The goal is to make meeting documentation nearly automatic.

The user should be able to start a meeting and focus on the conversation while the application:

1. Captures the conversation.
2. Transcribes it in real time.
3. Handles English, Bangla, and mixed English/Bangla speech.
4. Preserves the original conversation.
5. Identifies useful meeting information.
6. Produces a clean Markdown meeting document.

The core principle is:

> **Capture everything. Preserve what was said. Structure what matters.**

---

# 3. Meeting Modes

The application supports two primary meeting modes.

## 3.1 Online Meeting

For meetings conducted through:

* Google Meet
* Microsoft Teams
* Zoom
* Discord
* Browser-based meetings
* Other desktop applications

Audio sources:

```text
Microphone
    +
Windows System Audio
    ↓
Audio Pipeline
    ↓
Speech-to-Text
```

The application should not require individual integrations with Google Meet, Teams, or Zoom for basic transcription.

If the user can hear the meeting through the computer, the application should be able to capture that system audio.

---

## 3.2 Offline Meeting

For physical/in-person meetings.

Audio source:

```text
Laptop / External Microphone
            ↓
       Audio Pipeline
            ↓
       Local STT
            ↓
     Live Transcript
```

Offline mode must work without an internet connection.

The user should be able to:

1. Select a microphone.
2. Start an offline meeting.
3. Record/transcribe the conversation.
4. See the live transcript.
5. Stop the meeting.
6. Generate `meeting.md`.

No cloud service should be required for the core offline workflow.

---

# 4. Audio Capture

## 4.1 Microphone Capture

The application must support:

* Built-in laptop microphone
* USB microphone
* Wired headset
* Bluetooth headset
* External conference microphone
* Other Windows recording devices

The user must be able to select the microphone.

---

## 4.2 System Audio Capture

For online meetings, the application must capture Windows system audio.

Potential sources include:

* Google Meet
* Microsoft Teams
* Zoom
* Chrome
* Edge
* Discord
* Other applications

Initial technical direction:

**Windows WASAPI loopback capture**

The implementation should preserve the distinction between:

```text
Microphone Audio
System Audio
```

where possible.

This can improve future speaker attribution and audio processing.

---

# 5. Audio Pipeline

The audio architecture should support multiple input sources.

```text
                   ┌──────────────┐
                   │ Microphone   │
                   └──────┬───────┘
                          │
                          │
                   ┌──────▼───────┐
                   │              │
System Audio ─────►│ Audio Engine │
                   │              │
                   └──────┬───────┘
                          ↓
                   Audio Chunks
                          ↓
                    STT Provider
```

The audio engine is responsible for:

* Capturing audio
* Buffering
* Resampling when necessary
* Noise handling where appropriate
* Splitting audio into transcription chunks
* Managing microphone and system audio streams
* Feeding audio to the selected STT provider

The audio engine should not contain provider-specific logic.

---

# 6. Speech-to-Text

Speech-to-text is the most important AI component of the product.

The architecture must support interchangeable STT providers.

Potential providers include:

* Gemini Live
* Whisper-based models
* Faster-Whisper
* Other multilingual speech models
* Future local or cloud STT providers

The application should not hard-code a single STT provider.

---

# 7. STT Provider Architecture

Define a common provider interface.

Conceptually:

```text
STTProvider
│
├── GeminiLiveProvider
│
├── WhisperProvider
│
├── LocalMultilingualProvider
│
└── FutureProvider
```

The provider should expose capabilities similar to:

```text
connect()
start()
sendAudio()
receiveTranscript()
pause()
resume()
stop()
disconnect()
```

The exact implementation can vary by provider.

The rest of the application should not need to know which STT model is being used.

---

# 8. Gemini Live

Gemini Live should be evaluated as a primary cloud-based live transcription option.

Potential advantages:

* Real-time processing
* Strong multilingual capabilities
* Streaming interaction
* Potentially useful contextual understanding

However, the application must not assume Gemini Live is always available.

Internet availability, API limits, latency, pricing, and model capabilities must be considered.

Gemini should therefore be implemented as one provider within the STT abstraction.

---

# 9. Local STT

A local STT provider is required for true offline meetings.

Candidate approaches include:

* Whisper-based models
* Faster-Whisper
* Other multilingual speech models
* Future lightweight local speech models

The final model must be selected through an actual benchmark.

The benchmark must specifically test:

* English
* Bangla
* Bangla-English code switching
* Banglish
* Technical terminology
* Names
* Fast speech
* Multiple speakers
* Long meetings
* Latency
* CPU usage
* GPU usage
* RAM usage

Generic English benchmark performance is not sufficient.

---

# 10. Language Support

Primary languages:

* English
* Bangla

The application must support natural code-switching.

### English

```text
We should finalize this before Thursday.
```

### Bangla

```text
আমাদের এটা বৃহস্পতিবারের মধ্যে ফাইনাল করতে হবে।
```

### Mixed

```text
আমাদের Thursday-এর মধ্যে এটা finalize করতে হবে।
```

### Banglish

```text
Eta basically existing workflow-er sathei integrate hobe.
```

The default behavior is to preserve the language actually spoken.

The application should not automatically translate Bangla into English.

Translation may be introduced as a future feature.

---

# 11. Live Transcript

The application must display a live transcript during the meeting.

Example:

```text
10:32

Speaker 1
Should we move this to the next sprint?

10:32

Speaker 2
হ্যাঁ, I think that's better.

10:33

Speaker 1
ঠিক আছে, তাহলে let's keep it in the next sprint.
```

Requirements:

* Streaming transcript
* Timestamps
* English support
* Bangla support
* Mixed-language support
* Automatic updates
* Automatic saving
* Low latency

Target latency:

**Approximately 1-3 seconds where practical.**

Accuracy should take priority over achieving an artificial latency target.

---

# 12. Raw Transcript

The application must preserve the original/raw transcript.

A transcript segment should contain information similar to:

```json
{
  "id": "segment_001",
  "speaker": "speaker_1",
  "start": 12.41,
  "end": 18.22,
  "text": "yeah basically amra eta next sprint e nibo",
  "language": "mixed"
}
```

The exact schema can evolve.

The raw transcript must not be destroyed when AI cleanup or summarization occurs.

This allows:

* Recovery
* Reprocessing
* Model comparison
* Improved future AI processing
* Debugging transcription errors

---

# 13. Speaker Diarization

The application should support speaker diarization.

Initial output may be:

```text
Speaker 1
Speaker 2
Speaker 3
```

The user should eventually be able to rename speakers:

```text
Speaker 1 → Tauhid
Speaker 2 → Constance
Speaker 3 → Efti
```

Future versions may support speaker recognition through voice profiles.

Speaker diarization must not block the initial MVP.

---

# 14. Meeting Intelligence

The transcript should be processed into structured meeting information.

The AI layer should identify:

* Summary
* Discussion topics
* Decisions
* Action items
* Open questions
* Important dates
* Deadlines
* Requirements
* Blockers
* Risks
* Mentioned people
* Mentioned projects

The system must distinguish between:

**Confirmed information**

and

**Possible/uncertain information.**

The AI must not invent decisions, action items, deadlines, or requirements that were not discussed.

---

# 15. Meeting Intelligence Provider

Meeting intelligence should be independent from STT.

```text
STT
 ↓
Transcript
 ↓
Meeting Intelligence Provider
 ↓
Structured Meeting Data
 ↓
Markdown Renderer
```

Potential providers:

* Gemini
* Local LLM
* Other compatible LLM providers

The provider should return structured data rather than directly controlling the final Markdown file.

---

# 16. Structured Meeting Data

The AI layer should conceptually produce something similar to:

```json
{
  "title": "Feature Discussion",
  "summary": "...",
  "decisions": [
    {
      "text": "Move the feature to the next sprint."
    }
  ],
  "action_items": [
    {
      "owner": "Efti",
      "text": "Confirm backend scope"
    }
  ],
  "open_questions": [
    {
      "text": "Should the UI work be included in the following sprint?"
    }
  ],
  "important_dates": [],
  "discussion_topics": []
}
```

The exact schema should be defined during implementation.

---

# 17. Markdown Generation

Markdown is the primary output format.

The application should generate:

```text
meeting.md
```

The Markdown renderer should be deterministic.

The LLM should provide structured meeting data.

The application should convert that structured data into Markdown.

This prevents the model from having complete control over document formatting.

---

# 18. Default Markdown Structure

```markdown
# Meeting: Feature Discussion

**Date:** October 5, 2026
**Duration:** 42 minutes
**Mode:** Online
**Participants:** Tauhid, Constance, Efti

## Summary

...

## Discussion

### Feature Scope

...

### UI

...

## Decisions

- ...

## Action Items

- [ ] Efti: Confirm backend scope.
- [ ] Tauhid: Update documentation.

## Open Questions

- ...

## Important Dates

- ...

## Full Transcript

### Speaker 1

...

### Speaker 2

...
```

Sections that contain no meaningful information should normally be omitted.

---

# 19. Markdown as the Source of Meeting Memory

The Markdown document is not merely an export format.

It is the primary durable meeting artifact.

The application should make it easy to use the resulting Markdown files with:

* Markdown editors
* Git repositories
* Knowledge bases
* AI tools
* Documentation systems
* Local search
* Other developer/BA workflows

The generated files should remain readable without the application.

---

# 20. TTS / Voice Output

Voice generation is **not part of the core transcription pipeline**.

However, the architecture should allow a TTS provider to be added.

Potential providers include:

* Fish Audio
* Gemini TTS
* Other voice models

Fish Audio models such as `s2.1-pro-free` should be treated as a **TTS/voice-generation component**, not as the primary STT engine.

Potential future features:

* Read meeting summary aloud
* Read action items aloud
* Voice-based meeting navigation
* Ask questions about the meeting and hear the response
* Voice-controlled meeting search

TTS should remain optional.

---

# 21. Local vs Cloud Processing

The application supports two processing strategies.

## Local

```text
Audio
 ↓
Local STT
 ↓
Local LLM
 ↓
Markdown
```

Advantages:

* Offline operation
* Privacy
* No API cost
* No network dependency

## Cloud

```text
Audio
 ↓
Cloud STT
 ↓
Cloud LLM
 ↓
Markdown
```

Advantages:

* Potentially stronger models
* Lower local hardware requirements
* Easier access to advanced capabilities

The user should eventually be able to choose the preferred processing mode.

---

# 22. Processing Profiles

The application should eventually expose profiles such as:

### Offline

```text
STT: Local
Meeting AI: Local
TTS: Local/Disabled
Internet: Not required
```

### Balanced

```text
STT: Local
Meeting AI: Cloud
TTS: Optional
```

### Best Quality

```text
STT: Gemini Live / Best available provider
Meeting AI: Best available LLM
TTS: Optional
```

The exact profiles should be finalized after benchmarking.

---

# 23. Privacy

Meeting content can contain sensitive information.

Default principles:

* Local processing should be preferred where possible.
* Cloud processing must be explicit.
* The application should clearly show when cloud processing is active.
* Audio should not be uploaded without user configuration.
* Meeting files should be stored locally by default.
* Temporary audio should be automatically cleaned according to user settings.
* API keys must never be stored in plain text.
* The user must be able to disable cloud providers.

---

# 24. Custom Vocabulary

The application should support a custom vocabulary/context dictionary.

Example:

```text
Caboodle
FortiMapp
Ask Caboodle
Constance
Efti
RBAC
IAM
PRD
Jira
Figma
```

Custom vocabulary can improve:

* Product names
* Company names
* People's names
* Technical terminology
* Internal terminology
* Project terminology

The vocabulary should be usable by whichever STT/AI provider supports contextual vocabulary.

---

# 25. Meeting Storage

Each meeting should produce a local folder.

Example:

```text
Meetings/
└── 2026-10-05 - Feature Discussion/
    ├── meeting.md
    ├── transcript.json
    └── metadata.json
```

Audio storage should be optional.

If audio recording is enabled:

```text
Meetings/
└── 2026-10-05 - Feature Discussion/
    ├── meeting.md
    ├── transcript.json
    ├── metadata.json
    └── audio.wav
```

The user should control whether audio is retained.

---

# 26. Desktop Application

Initial platform:

**Windows**

Recommended initial direction:

**Tauri + React + TypeScript + Rust**

Conceptual architecture:

```text
Tauri Desktop Application
│
├── React / TypeScript
│   ├── Meeting View
│   ├── Transcript View
│   ├── Meeting History
│   └── Settings
│
├── Rust Native Layer
│   ├── Microphone Capture
│   ├── WASAPI System Audio
│   ├── Audio Processing
│   └── Application Controls
│
├── AI Layer
│   ├── STT Providers
│   ├── Meeting Intelligence Providers
│   └── TTS Providers
│
└── Storage
    ├── Markdown
    ├── JSON
    └── Optional Audio
```

This is a starting technical direction and should be validated during implementation.

---

# 27. Provider Abstraction

The application must avoid hard dependencies on a single AI vendor.

Conceptually:

```text
AI Providers
│
├── STT
│   ├── Gemini Live
│   ├── Whisper
│   └── Other STT
│
├── Meeting Intelligence
│   ├── Gemini
│   ├── Local LLM
│   └── Other LLM
│
└── TTS
    ├── Fish Audio
    ├── Gemini TTS
    └── Other TTS
```

Providers should be replaceable without changing the core meeting workflow.

---

# 28. User Interface

The UI should remain minimal.

The primary screen should focus on the live transcript.

```text
┌────────────────────────────────────────────┐
│ ● Recording                  00:32:41      │
│ Feature Discussion                         │
├────────────────────────────────────────────┤
│                                            │
│ Speaker 1                                  │
│ Should we move this to the next sprint?   │
│                                            │
│ Speaker 2                                  │
│ হ্যাঁ, I think that's better.              │
│                                            │
│ Speaker 1                                  │
│ ঠিক আছে, let's keep it in the sprint.      │
│                                            │
├────────────────────────────────────────────┤
│ [ Pause ]                 [ Stop Meeting ] │
└────────────────────────────────────────────┘
```

The application should avoid becoming a complex meeting-management dashboard.

---

# 29. Meeting Start

The user should have a simple choice:

```text
┌──────────────────────────────────┐
│          Start Meeting           │
│                                  │
│   ┌────────────┐ ┌────────────┐  │
│   │   Online   │ │  Offline   │  │
│   │            │ │            │  │
│   │ Mic +      │ │ Microphone │  │
│   │ System     │ │ only       │  │
│   │ Audio      │ │            │  │
│   └────────────┘ └────────────┘  │
└──────────────────────────────────┘
```

The mode determines which audio sources are enabled.

---

# 30. Controls

The MVP should support:

* Start meeting
* Pause
* Resume
* Stop meeting
* Select microphone
* Enable/disable system audio
* Select AI provider
* View live transcript
* Edit meeting title
* Open generated Markdown
* Select output directory

Future:

* Global hotkey
* System tray
* Automatic meeting detection
* Automatic meeting naming

---

# 31. Error Handling

The application must gracefully handle:

* Microphone unavailable
* System audio unavailable
* STT provider unavailable
* Internet disconnected
* API quota exceeded
* Local model unavailable
* AI processing failure
* Insufficient system resources
* Audio device changes
* Provider connection interruption

For cloud STT failures, the application should preserve captured audio/transcript state and allow recovery where possible.

For offline mode, loss of internet must not interrupt the transcription pipeline.

---

# 32. Development Phases

## Phase 0 — STT Benchmark

Create a real English/Bangla meeting test dataset.

Test:

* Gemini Live
* Whisper/Faster-Whisper
* Other promising multilingual models

Evaluate:

* English accuracy
* Bangla accuracy
* Mixed-language accuracy
* Banglish accuracy
* Technical terminology
* Proper names
* Latency
* CPU
* GPU
* RAM
* Long-session stability

**Deliverable:**

STT benchmark + selected initial providers.

---

## Phase 1 — Offline Microphone Prototype

Build:

```text
Microphone
    ↓
Local STT
    ↓
Live Transcript
```

Requirements:

* No internet
* English
* Bangla
* Mixed language
* Timestamps
* Local storage

**Deliverable:**

Working offline transcription.

---

## Phase 2 — Markdown Pipeline

Build:

```text
Transcript
    ↓
Meeting Intelligence
    ↓
Structured Data
    ↓
Markdown Renderer
    ↓
meeting.md
```

**Deliverable:**

Useful Markdown meeting documents.

---

## Phase 3 — Online Audio

Add:

```text
Microphone
     +
System Audio
     ↓
Audio Engine
     ↓
STT
```

Validate with:

* Google Meet
* Microsoft Teams
* Zoom

**Deliverable:**

Reliable online meeting transcription.

---

## Phase 4 — Desktop UI

Build the Windows application around the validated pipeline.

**Deliverable:**

Usable Windows MVP.

---

## Phase 5 — Speaker Intelligence

Add:

* Speaker diarization
* Speaker renaming
* Speaker profiles
* Better speaker attribution

---

## Phase 6 — Advanced Meeting Intelligence

Add:

* Better decision detection
* Better action-item extraction
* Requirement extraction
* Risk detection
* Topic grouping
* Meeting comparison
* Custom Markdown templates

---

# 33. MVP Scope

The MVP must support:

* Windows
* Online meetings
* Offline meetings
* Microphone capture
* System audio capture
* Live transcription
* English
* Bangla
* English/Bangla code switching
* Local STT
* At least one cloud STT provider
* Raw transcript preservation
* Basic speaker diarization
* Meeting summary
* Decisions
* Action items
* Open questions
* Markdown generation
* Local Markdown storage

---

# 34. MVP Non-Goals

Do not build initially:

* Calendar integration
* Google Meet API integration
* Microsoft Teams API integration
* Zoom API integration
* Team collaboration
* Cloud storage
* Enterprise administration
* CRM integration
* Project management features
* Advanced TTS
* Voice assistant
* Complex dashboards
* Automatic email follow-ups

The first version should solve one problem exceptionally well:

> **Turn an English/Bangla meeting into a reliable, structured Markdown document.**

---

# 35. Success Criteria

The MVP is successful when a user can:

1. Open the Windows application.
2. Choose Online or Offline mode.
3. Start a meeting.
4. Capture microphone audio.
5. Capture system audio when using Online mode.
6. Transcribe English and Bangla speech in real time.
7. Handle natural English/Bangla code switching.
8. Continue working without internet in Offline mode.
9. See the live transcript.
10. Stop the meeting.
11. Generate a structured `meeting.md`.
12. Review decisions and action items.
13. Access the full transcript.
14. Recover the raw transcript if AI processing makes a mistake.

---

# 36. Core Product Principles

### 1. Audio-source agnostic

The application should work regardless of whether the meeting happens in Meet, Teams, Zoom, or a physical room.

### 2. English + Bangla first

Mixed-language meetings are a core use case, not an edge case.

### 3. Local-first

Offline transcription must be possible.

### 4. Provider agnostic

Gemini, Whisper, local models, and future providers should be replaceable.

### 5. Preserve the source

Never destroy the raw transcript.

### 6. Markdown-first

The meeting should exist as an open, portable Markdown document.

### 7. AI structures; application renders

AI determines meeting information. The application controls the final document structure.

### 8. Minimal UX

The application should stay out of the way of the meeting.

### 9. Accuracy over gimmicks

Transcription quality for real English/Bangla meetings is more important than adding a large number of AI features.

---

# 37. Final Product Vision

The long-term vision is:

> **A local-first AI meeting memory for Windows that can listen to any meeting, understand English/Bangla conversations, and turn them into structured, portable Markdown knowledge.**

The user should not have to think about transcription, meeting notes, decisions, or action-item capture.

They simply start the meeting.

The application listens.

The Markdown becomes the memory.
