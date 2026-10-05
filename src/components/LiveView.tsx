import { useEffect, useRef } from "react";
import { formatDuration } from "../hooks/useMeeting";
import type { MeetingResult } from "../hooks/useMeeting";
import type { MeetingStatus, TranscriptSegment } from "../types";

interface Props {
  status: MeetingStatus;
  segments: TranscriptSegment[];
  interim: string;
  elapsed: number;
  error: string | null;
  result: MeetingResult | null;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
  onOpenMarkdown: (path: string) => void;
  onOpenFolder: (path: string) => void;
}

export function LiveView({
  status,
  segments,
  interim,
  elapsed,
  error,
  result,
  onPause,
  onResume,
  onStop,
  onOpenMarkdown,
  onOpenFolder,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [segments, interim]);

  const live = status === "live" || status === "paused";

  return (
    <div className="live">
      <header className="live-head">
        <div className="rec">
          <span className={`dot ${status === "live" ? "on" : ""}`} />
          {status === "paused" ? "Paused" : live ? "Recording" : "Idle"}
        </div>
        <div className="timer mono">{formatDuration(elapsed)}</div>
      </header>

      {error && <div className="banner error">{error}</div>}

      {result && (
        <div className="banner success">
          Meeting saved.
          {result.markdownPath && (
            <>
              {" "}
              <button className="link" onClick={() => onOpenMarkdown(result.markdownPath!)}>
                Open meeting.md
              </button>
            </>
          )}
          {result.folder && (
            <>
              {" "}
              <button className="link" onClick={() => onOpenFolder(result.folder!)}>
                Open folder
              </button>
            </>
          )}
        </div>
      )}

      <div className="transcript" ref={scrollRef}>
        {segments.length === 0 && !interim && (
          <p className="muted empty">
            {live ? "Listening..." : "Start a meeting to see the live transcript."}
          </p>
        )}
        {segments.map((segment) => (
          <div className="row" key={segment.id}>
            <div className="gutter mono">{formatDuration(segment.start)}</div>
            <div className="content">
              <div className="speaker">
                {segment.speaker}
                <span className="lang mono">{segment.language}</span>
              </div>
              <div className="text">{segment.text}</div>
            </div>
          </div>
        ))}
        {interim && (
          <div className="row interim">
            <div className="gutter mono" />
            <div className="content">
              <div className="text">{interim}</div>
            </div>
          </div>
        )}
      </div>

      <footer className="controls">
        {status === "live" && (
          <button className="secondary" onClick={onPause}>
            Pause
          </button>
        )}
        {status === "paused" && (
          <button className="secondary" onClick={onResume}>
            Resume
          </button>
        )}
        <button className="danger" onClick={onStop} disabled={!live}>
          Stop Meeting
        </button>
      </footer>
    </div>
  );
}
