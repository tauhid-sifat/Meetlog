import { useState } from "react";
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

  const start = () => {
    onStart(
      { mode, microphone, system_audio: mode === "online" },
      title.trim() || "Meeting",
    );
  };

  return (
    <div className="setup">
      <header className="view-head">
        <h1>New Meeting</h1>
        <p className="muted">Choose how to capture audio and configure the session.</p>
      </header>

      <div className="mode-cards">
        <button
          className={`mode-card ${mode === "online" ? "selected" : ""}`}
          onClick={() => setMode("online")}
        >
          <span className="mode-title">Online Meeting</span>
          <span className="muted">Microphone + system audio (Meet, Teams, Zoom).</span>
        </button>
        <button
          className={`mode-card ${mode === "offline" ? "selected" : ""}`}
          onClick={() => setMode("offline")}
        >
          <span className="mode-title">In-Person Meeting</span>
          <span className="muted">Microphone only.</span>
        </button>
      </div>

      <section className="panel">
        <div className="field">
          <label>Meeting title</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.currentTarget.value)}
            placeholder="Meeting"
          />
        </div>
        <div className="field">
          <label>Microphone</label>
          <select
            value={microphone ?? ""}
            onChange={(e) => setMicrophone(e.currentTarget.value || null)}
          >
            {devices.length === 0 && <option value="">No input devices found</option>}
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
      </section>

      {error && <div className="banner error">{error}</div>}

      <div className="actions">
        <button className="primary" onClick={start}>
          Start Meeting
        </button>
      </div>
    </div>
  );
}
