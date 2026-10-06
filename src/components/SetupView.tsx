import { useEffect, useState } from "react";
import type { CaptureSpec, Settings } from "../types";

interface Props {
  settings: Settings;
  devices: string[];
  error: string | null;
  onStart: (spec: CaptureSpec, title: string) => void;
}

export function SetupView({ settings, devices, error, onStart }: Props) {
  const [mode, setMode] = useState<"online" | "offline">(
    settings.system_audio ? "online" : "offline",
  );
  const [microphone, setMicrophone] = useState<string | null>(
    settings.microphone ?? (devices[0] ?? null),
  );
  const [title, setTitle] = useState("Meeting");

  useEffect(() => {
    if ((microphone === null || microphone === "") && devices.length > 0) {
      const preferred = settings.microphone && devices.includes(settings.microphone)
        ? settings.microphone
        : devices[0];
      setMicrophone(preferred ?? null);
    }
  }, [devices, settings.microphone, microphone]);

  const noDevices = devices.length === 0;

  const start = () => {
    if (noDevices) return;
    onStart(
      { mode, microphone, system_audio: mode === "online" },
      title.trim() || "Meeting",
    );
  };

  return (
    <div className="setup">
      <header className="view-head">
        <h1>Start a meeting</h1>
        <p className="muted">Pick capture mode, check the microphone, then stay in the conversation. Meetlog keeps the transcript and builds meeting.md.</p>
      </header>

      <div className="mode-cards" role="radiogroup" aria-label="Meeting capture mode">
        <button
          type="button"
          role="radio"
          aria-checked={mode === "online"}
          className={`mode-card ${mode === "online" ? "selected" : ""}`}
          onClick={() => setMode("online")}
        >
          <span className="pick" aria-hidden="true" />
          <span className="mode-title">Online Meeting</span>
          <span className="mode-desc">Microphone + system audio for Meet, Teams, Zoom. Use headphones to avoid echo.</span>
        </button>
        <button
          type="button"
          role="radio"
          aria-checked={mode === "offline"}
          className={`mode-card ${mode === "offline" ? "selected" : ""}`}
          onClick={() => setMode("offline")}
        >
          <span className="pick" aria-hidden="true" />
          <span className="mode-title">In-Person Meeting</span>
          <span className="mode-desc">Microphone only. Works fully offline with local transcription.</span>
        </button>
      </div>

      <section className="panel">
        <div className="field">
          <label htmlFor="meeting-title">Meeting title</label>
          <input
            id="meeting-title"
            value={title}
            onChange={(e) => setTitle(e.currentTarget.value)}
            placeholder="e.g. Feature Discussion"
            maxLength={120}
          />
        </div>
        <div className="field">
          <label htmlFor="meeting-mic">Microphone</label>
          <select
            id="meeting-mic"
            value={microphone ?? ""}
            onChange={(e) => setMicrophone(e.currentTarget.value || null)}
          >
            {noDevices && <option value="">No input devices found</option>}
            {devices.map((device) => (
              <option key={device} value={device}>
                {device}
              </option>
            ))}
          </select>
        </div>
        {mode === "online" && (
          <p className="hint">
            System audio is captured via WASAPI loopback from the default output
            device. Headphones are recommended to avoid echo.
          </p>
        )}
        {noDevices && (
          <p className="hint">
            No microphone detected. Plug in a device, then reopen this view. Starting is paused until input is available so you never record silence.
          </p>
        )}
      </section>

      {error && <div className="banner error" role="alert">Capture failed: {error} Check the microphone and try again.</div>}

      <div className="actions">
        <button className="primary" onClick={start} disabled={noDevices}>
          {noDevices ? "No microphone — Start unavailable" : "Start Meeting"}
        </button>
        <span className="muted">{mode === "online" ? "Mic + system audio" : "Mic only"} · Transcript auto-saves</span>
      </div>
    </div>
  );
}
