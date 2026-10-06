import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import type {
  CaptureSpec,
  MeetingInfo,
  Settings,
  SidecarEvent,
} from "../types";

export const api = {
  listInputDevices: () => invoke<string[]>("list_input_devices"),
  probeCapture: (spec: CaptureSpec, seconds: number) =>
    invoke<Record<string, { chunks: number; rms: number }>>("probe_capture", {
      spec,
      seconds,
    }),

  loadSettings: () => invoke<Settings>("load_settings"),
  saveSettings: (settings: Settings) => invoke<void>("save_settings", { settings }),
  setApiKey: (key: string) => invoke<void>("set_api_key", { key }),
  frontendLog: (message: string) => invoke<void>("frontend_log", { message }),
  hasApiKey: () => invoke<boolean>("has_api_key"),
  getOutputDir: () => invoke<string>("get_output_dir"),

  listMeetings: () => invoke<MeetingInfo[]>("list_meetings"),
  readTextFile: (path: string) => invoke<string>("read_text_file", { path }),
  openPath: (path: string) => invoke<void>("open_path", { path }),

  startMeeting: (spec: CaptureSpec, title: string) =>
    invoke<void>("start_meeting", { spec, title }),
  stopMeeting: () => invoke<void>("stop_meeting"),
  sidecarSend: (message: unknown) => invoke<void>("sidecar_send", { message }),
  sidecarRunning: () => invoke<boolean>("sidecar_running"),
};

export function onSidecarMessage(
  cb: (event: SidecarEvent) => void,
): Promise<UnlistenFn> {
  return listen<string>("sidecar://message", (event) => {
    try {
      cb(JSON.parse(event.payload) as SidecarEvent);
    } catch {
      // ignore non-JSON lines
    }
  });
}

export function onSidecarReady(cb: () => void): Promise<UnlistenFn> {
  return listen("sidecar://ready", () => cb());
}

export function onSidecarError(cb: (message: string) => void): Promise<UnlistenFn> {
  return listen<string>("sidecar://error", (event) => cb(event.payload));
}

export function onAudioError(cb: (message: string) => void): Promise<UnlistenFn> {
  return listen<string>("audio://error", (event) => cb(event.payload));
}
