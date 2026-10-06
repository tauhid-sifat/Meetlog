import { useCallback, useEffect, useRef, useState } from "react";
import { api, onSidecarMessage } from "../lib/api";
import type {
  CaptureSpec,
  MeetingStatus,
  TranscriptSegment,
} from "../types";

export interface MeetingResult {
  folder: string | null;
  markdownPath: string | null;
}

export function useMeeting() {
  const [status, setStatus] = useState<MeetingStatus>("idle");
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [speakers, setSpeakers] = useState<string[]>([]);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [result, setResult] = useState<MeetingResult | null>(null);
  const startedAt = useRef<number | null>(null);

  useEffect(() => {
    const pending = onSidecarMessage((event) => {
      switch (event.type) {
        case "interim":
          setInterim(event.text);
          break;
        case "segment":
          setSegments((prev) => [...prev, event.segment]);
          setSpeakers((prev) =>
            prev.includes(event.segment.speaker)
              ? prev
              : [...prev, event.segment.speaker],
          );
          setInterim("");
          break;
        case "speakers":
          setSpeakers(event.speakers);
          break;
        case "error":
          setError(event.message);
          break;
        case "stopped":
          setStatus("idle");
          setResult({ folder: event.folder, markdownPath: event.markdown_path });
          break;
        default:
          break;
      }
    });
    return () => {
      pending.then((unlisten) => unlisten());
    };
  }, []);

  useEffect(() => {
    if (status !== "live") return;
    const id = window.setInterval(() => {
      if (startedAt.current !== null) {
        setElapsed((Date.now() - startedAt.current) / 1000);
      }
    }, 500);
    return () => window.clearInterval(id);
  }, [status]);

  const start = useCallback(async (spec: CaptureSpec, title: string) => {
    setError(null);
    setSegments([]);
    setSpeakers([]);
    setInterim("");
    setResult(null);
    setElapsed(0);
    setStatus("starting");
    try {
      await api.startMeeting(spec, title);
      startedAt.current = Date.now();
      setStatus("live");
    } catch (e) {
      setError(String(e));
      setStatus("idle");
    }
  }, []);

  const stop = useCallback(async () => {
    setStatus("stopping");
    try {
      await api.stopMeeting();
    } catch (e) {
      setError(String(e));
      setStatus("idle");
    }
  }, []);

  const pause = useCallback(async () => {
    try {
      await api.sidecarSend({ type: "pause" });
      setStatus("paused");
    } catch (e) {
      setError(String(e));
    }
  }, []);

  const resume = useCallback(async () => {
    try {
      await api.sidecarSend({ type: "resume" });
      if (startedAt.current !== null) {
        startedAt.current = Date.now() - elapsed * 1000;
      }
      setStatus("live");
    } catch (e) {
      setError(String(e));
    }
  }, [elapsed]);

  const renameSpeaker = useCallback(async (from: string, to: string) => {
    const display = to.trim();
    if (!display) {
      setError("Speaker name must not be empty.");
      return;
    }
    try {
      await api.sidecarSend({ type: "rename_speaker", from, to: display });
      setSegments((prev) =>
        prev.map((segment) =>
          segment.speaker === from ? { ...segment, speaker: display } : segment,
        ),
      );
      setSpeakers((prev) => {
        if (!prev.includes(from)) return prev;
        const next = prev.map((name) => (name === from ? display : name));
        return [...new Set(next)];
      });
    } catch (e) {
      setError(String(e));
    }
  }, []);

  return {
    status,
    segments,
    speakers,
    interim,
    error,
    elapsed,
    result,
    start,
    stop,
    pause,
    resume,
    renameSpeaker,
    clearError: () => setError(null),
    clearResult: () => setResult(null),
  };
}

export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`;
}
