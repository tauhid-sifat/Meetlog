# Meetlog

Local-first AI meeting memory for Windows. Meetlog listens to meetings through
the microphone and/or system audio, produces a live English/Bangla transcript,
and generates a structured Markdown meeting document.

```text
Meeting Audio → Speech-to-Text → Live Transcript → Meeting Intelligence → meeting.md
```

## Features

- **Online meetings** — microphone + Windows system audio (WASAPI loopback), no per-app integrations needed
- **In-person meetings** — microphone only
- **English, Bangla, and mixed speech** — code-switching and Banglish preserved as spoken, never auto-translated
- **Live transcript** — streaming segments with timestamps, speaker labels, and language tags
- **Speaker intelligence** — provider diarization plus manual renaming (`Speaker 1` → name)
- **Meeting intelligence** — summary, decisions, action items (with owners when stated), requirements, risks, open questions, important dates
- **Markdown-first output** — every meeting saves `meeting.md`, `transcript.json`, and `metadata.json` locally
- **Provider-agnostic AI layer** — STT and intelligence behind interfaces; MVP runs on Gemini, local providers can plug in later

## Architecture

```text
Tauri v2 desktop shell (React + TypeScript UI)
 ├── Rust audio engine (src-tauri/audio) — mic + loopback capture, 16 kHz mono PCM
 ├── Python AI sidecar (ai/) — Gemini Live STT, meeting intelligence, storage
 │    └── talks to Tauri over loopback TCP (newline-delimited JSON)
 └── Local meeting folders (~/Meetlog/Meetings)
```

## Prerequisites

- **Node.js** (npm) — frontend and Tauri CLI
- **Rust** (stable `x86_64-pc-windows-gnu` toolchain) + **WinLibs MinGW-w64** on `PATH`
  (see `src-tauri/.cargo/config.toml` — the target dir must live on a
  space-free path because MinGW `windres` does not quote paths)
- **Python 3.14** with a virtualenv at `.venv` (`pip install -r ai/requirements.txt`)
- **Gemini API key** — paste it in Settings; it is stored in Windows Credential Manager, never in plaintext

## Run

```powershell
npm install
npm run tauri dev
```

Then: Settings → save the Gemini API key → New Meeting → Start → speak → Stop.
Use **headphones** for online meetings to avoid echo. The **Test audio** button
on the setup screen verifies mic and system levels before you start.

Production build:

```powershell
npm run tauri build
```

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest        # Python sidecar + AI (89 passed, 1 skipped)
cargo test -p meetlog-audio                  # Rust audio unit tests
cargo check --manifest-path src-tauri/Cargo.toml
npm run build                                # tsc + vite
```

The skipped Python test and the live end-to-end run need a real Gemini API key;
see [issues #9 and #10](https://github.com/tauhid-sifat/Meetlog/issues).

## Project layout

| Path | What lives there |
|------|------------------|
| `src/` | React/TS UI (setup, live transcript, history, settings) |
| `src-tauri/` | Tauri shell, settings/keychain, meeting lifecycle commands |
| `src-tauri/audio/` | `meetlog-audio` crate: capture, resampling, examples |
| `ai/` | Python sidecar: STT providers, intelligence, rendering, storage |
| `ai/compare.py` | Meeting-to-meeting diff |
| `templates/` | Default + slim Markdown templates (Jinja2) |
| `scripts/` | Validation and benchmark harnesses (need `GEMINI_API_KEY`) |
| `tests/` | Python test suite |
| `docs/` | MVP plan, STT benchmark report |
| `spec.md` | Product specification |

## Status and roadmap

MVP phases 0–6 are code-complete on `main`; see
[docs/plans/meetlog-mvp-plan.md](docs/plans/meetlog-mvp-plan.md) for per-phase
acceptance status. Open work is tracked in
[GitHub issues](https://github.com/tauhid-sifat/Meetlog/issues): real-recording
benchmark, live end-to-end validation, optional `audio.wav` retention, and a
manual device-unplug test.

## License

MIT — see [LICENSE](LICENSE).
