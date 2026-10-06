import { useCallback, useEffect, useState } from "react";
import { MeetingsView } from "./components/MeetingsView";
import { LiveView } from "./components/LiveView";
import { SettingsView } from "./components/SettingsView";
import { SetupView } from "./components/SetupView";
import { useMeeting } from "./hooks/useMeeting";
import { api, onSidecarError, onSidecarReady } from "./lib/api";
import { defaultSettings, type CaptureSpec, type MeetingInfo, type Settings } from "./types";

type View = "new" | "live" | "meetings" | "settings";

function App() {
  const [view, setView] = useState<View>("new");
  const [settings, setSettings] = useState<Settings>(defaultSettings);
  const [devices, setDevices] = useState<string[]>([]);
  const [meetings, setMeetings] = useState<MeetingInfo[]>([]);
  const [outputDir, setOutputDir] = useState("");
  const [hasApiKey, setHasApiKey] = useState(false);
  const [sidecarReady, setSidecarReady] = useState(false);

  const meeting = useMeeting();

  const refreshMeetings = useCallback(async () => {
    setMeetings(await api.listMeetings());
  }, []);

  useEffect(() => {
    (async () => {
      const [loaded, inputs, out, key] = await Promise.all([
        api.loadSettings(),
        api.listInputDevices(),
        api.getOutputDir(),
        api.hasApiKey(),
      ]);
      setSettings(loaded);
      setDevices(inputs);
      setOutputDir(out);
      setHasApiKey(key);
      await refreshMeetings();
    })();

    const ready = onSidecarReady(() => setSidecarReady(true));
    const errored = onSidecarError(() => setSidecarReady(false));
    return () => {
      ready.then((unlisten) => unlisten());
      errored.then((unlisten) => unlisten());
    };
  }, [refreshMeetings]);

  useEffect(() => {
    if (meeting.status === "starting" || meeting.status === "live") {
      setView("live");
    }
  }, [meeting.status]);

  const handleStart = (spec: CaptureSpec, title: string) => {
    meeting.start(spec, title);
  };

  const handleSaveSettings = async (next: Settings, apiKey: string | null) => {
    if (apiKey) {
      await api.setApiKey(apiKey);
    }
    await api.saveSettings(next);
    setSettings(next);
    setHasApiKey(await api.hasApiKey());
    setOutputDir(await api.getOutputDir());
    await refreshMeetings();
  };

  const handleClearApiKey = async () => {
    await api.setApiKey("");
    setHasApiKey(false);
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
            <i />
          </span>
          <span>
            Meetlog
            <small>Meeting memory</small>
          </span>
        </div>
        <nav aria-label="Primary">
          <button
            className={`nav ${view === "new" ? "active" : ""}`}
            aria-current={view === "new" ? "page" : undefined}
            onClick={() => setView("new")}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M8 2v8" />
              <path d="M4.5 4.5a3.5 3.5 0 0 0 7 0" />
              <rect x="3" y="9.5" width="10" height="4.5" rx="1.5" />
            </svg>
            New Meeting
          </button>
          <button
            className={`nav ${view === "live" ? "active" : ""}`}
            aria-current={view === "live" ? "page" : undefined}
            onClick={() => setView("live")}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
              <path d="M3 8h2l1.5-3.5L9 10l1.2-2H13" />
            </svg>
            Live
          </button>
          <button
            className={`nav ${view === "meetings" ? "active" : ""}`}
            aria-current={view === "meetings" ? "page" : undefined}
            onClick={() => {
              refreshMeetings();
              setView("meetings");
            }}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect x="2.5" y="3" width="11" height="10" rx="1.5" />
              <path d="M2.5 6.5h11" />
            </svg>
            Meetings
          </button>
          <button
            className={`nav ${view === "settings" ? "active" : ""}`}
            aria-current={view === "settings" ? "page" : undefined}
            onClick={() => setView("settings")}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="8" cy="8" r="2.2" />
              <path d="M8 1.8v1.7M8 12.5v1.7M1.8 8h1.7M12.5 8h1.7M3.6 3.6l1.2 1.2M11.2 11.2l1.2 1.2M12.4 3.6l-1.2 1.2M4.8 11.2l-1.2 1.2" />
            </svg>
            Settings
          </button>
        </nav>
        <div className="status mono">
          <span className={`dot ${sidecarReady ? "on" : ""}`} />
          {sidecarReady ? "AI engine ready" : "AI engine starting — transcription waits"}
        </div>
      </aside>

      <main className="main">
        {view === "new" && (
          <SetupView
            settings={settings}
            devices={devices}
            error={meeting.error}
            onStart={handleStart}
          />
        )}
        {view === "live" && (
          <LiveView
            status={meeting.status}
            segments={meeting.segments}
            speakers={meeting.speakers}
            interim={meeting.interim}
            elapsed={meeting.elapsed}
            error={meeting.error}
            result={meeting.result}
            onPause={meeting.pause}
            onResume={meeting.resume}
            onStop={meeting.stop}
            onRenameSpeaker={meeting.renameSpeaker}
            onOpenMarkdown={(path) => api.openPath(path)}
            onOpenFolder={(path) => api.openPath(path)}
          />
        )}
        {view === "meetings" && (
          <MeetingsView
            meetings={meetings}
            outputDir={outputDir}
            onRefresh={refreshMeetings}
            onOpenMarkdown={(path) => api.openPath(path)}
            onOpenFolder={(path) => api.openPath(path)}
          />
        )}
        {view === "settings" && (
          <SettingsView
            settings={settings}
            devices={devices}
            outputDir={outputDir}
            hasApiKey={hasApiKey}
            onSave={handleSaveSettings}
            onClearApiKey={handleClearApiKey}
          />
        )}
      </main>
    </div>
  );
}

export default App;
