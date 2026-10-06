export interface TranscriptSegment {
  id: string;
  speaker: string;
  start: number;
  end: number;
  text: string;
  language: string;
}

export type SidecarEvent =
  | { type: "ready" }
  | { type: "interim"; text: string; language: string; speaker: string }
  | { type: "segment"; segment: TranscriptSegment }
  | { type: "speakers"; speakers: string[] }
  | { type: "error"; message: string }
  | { type: "system"; message: string }
  | {
      type: "stopped";
      folder: string | null;
      markdown_path: string | null;
      transcript: unknown;
    };

export interface Settings {
  microphone: string | null;
  output_dir: string | null;
  custom_vocabulary: string[];
  system_audio: boolean;
  transcription_mode: string;
  diarization: boolean;
  model: string | null;
}

export interface CaptureSpec {
  mode: "online" | "offline";
  microphone: string | null;
  system_audio: boolean;
}

export interface MeetingInfo {
  folder: string;
  name: string;
  date: string;
  title: string;
  has_markdown: boolean;
  markdown_path: string | null;
  modified: number;
}

export type MeetingStatus = "idle" | "starting" | "live" | "paused" | "stopping";

export const defaultSettings: Settings = {
  microphone: null,
  output_dir: null,
  custom_vocabulary: [],
  system_audio: true,
  transcription_mode: "VERBATIM",
  diarization: true,
  model: null,
};
