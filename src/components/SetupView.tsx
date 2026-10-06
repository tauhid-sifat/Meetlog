import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { CaptureSpec, Settings } from "../types";

interface ProbeLevels {
  chunks: number;
  rms: number;
}

function verdict(source: string, rms: number): string {
  const what = source === "system" ? "System audio" : "Microphone";
  if (rms > 0.02) return `${what} OK — picking up sound.`;
  return source === "system"
    ? "System audio silent — play something on this computer and check the output device."
    : "Microphone silent — speak and check the selected device.";
}

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
  const modeTouched = useRef(false);

  // Settings load async; sync mode once until the user picks explicitly.
  useEffect(() => {
    if (!modeTouched.current) {
      setMode(settings.system_audio ? "online" : "offline");
    }
  }, [settings.system_audio]);

  useEffect(() => {
    if ((microphone === null || microphone === "") && devices.length > 0) {
      const preferred = settings.microphone && devices.includes(settings.microphone)
        ? settings.microphone
        : devices[0];
      setMicrophone(preferred ?? null);
    }
  }, [devices, settings.microphone, microphone]);

  const noDevices = devices.length === 0;
  const [testing, setTesting] = useState(false);
  const [levels, setLevels] = useState<Record<string, ProbeLevels> | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  const testAudio = async () => {
    if (noDevices || testing) return;
    setTesting(true);
    setTestError(null);
    setLevels(null);
    try {
      const result = await api.probeCapture(
        { mode, microphone, system_audio: mode === "online" },
        4,
      );
      setLevels(result);
    } catch (e) {
      setTestError(String(e));
    } finally {
      setTesting(false);
    }
  };

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
          onClick={() => {
            modeTouched.current = true;
            setMode("online");
          }}
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
          onClick={() => {
            modeTouched.current = true;
            setMode("offline");
          }}
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
            disabled={noDevices}
            aria-describedby={noDevices ? "mic-empty-hint" : undefined}
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
          <p className="hint" id="mic-empty-hint">
            No microphone detected. Plug in a device, then reopen this view. Starting is paused until input is available so you never record silence.
          </p>
        )}
      </section>

      {error && <div className="banner error" role="alert">Capture failed: {error} Check the microphone and try again.</div>}

      <section className="panel">
        <h2>Check levels before you start</h2>
        <p className="hint">
          Records 4 seconds from the selected sources. If system audio reads
          silent while sound is playing, the meeting app is on a different
          output device than the loopback target.
        </p>
        <div className="actions">
          <button
            className="secondary"
            onClick={testAudio}
            disabled={noDevices || testing}
            aria-busy={testing}
          >
            {testing ? "Listening…" : "Test audio"}
          </button>
        </div>
        {testError && <div className="banner error" role="alert">Audio test failed: {testError}</div>}
        {levels && (
          <ul className="levels">
            {Object.entries(levels).map(([source, stats]) => (
              <li key={source}>
                <span className="mono">{source}</span>
                <span className="meter" aria-hidden="true">
                  <i style={{ width: `${Math.min(100, stats.rms * 500)}%` }} />
                </span>
                <span className="muted">{verdict(source, stats.rms)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="actions">
        <button
          className="primary"
          onClick={start}
          disabled={noDevices}
          aria-disabled={noDevices}
        >
          {noDevices ? "No microphone — Start unavailable" : "Start Meeting"}
        </button>
        <span className="muted">{mode === "online" ? "Mic + system audio" : "Mic only"} · Transcript auto-saves</span>
      </div>
    </div>
  );
}
