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
        <div className="brand">Meetlog</div>
        <nav>
          <button
            className={`nav ${view === "new" ? "active" : ""}`}
            onClick={() => setView("new")}
          >
            New Meeting
          </button>
          <button
            className={`nav ${view === "live" ? "active" : ""}`}
            onClick={() => setView("live")}
          >
            Live
          </button>
          <button
            className={`nav ${view === "meetings" ? "active" : ""}`}
            onClick={() => {
              refreshMeetings();
              setView("meetings");
            }}
          >
            Meetings
          </button>
          <button
            className={`nav ${view === "settings" ? "active" : ""}`}
            onClick={() => setView("settings")}
          >
            Settings
          </button>
        </nav>
        <div className="status mono">
          <span className={`dot ${sidecarReady ? "on" : ""}`} />
          {sidecarReady ? "AI engine ready" : "AI engine starting"}
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
            interim={meeting.interim}
            elapsed={meeting.elapsed}
            error={meeting.error}
            result={meeting.result}
            onPause={meeting.pause}
            onResume={meeting.resume}
            onStop={meeting.stop}
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
