import { useEffect, useRef, useState } from "react";
import { formatDuration } from "../hooks/useMeeting";
import type { MeetingResult } from "../hooks/useMeeting";
import type { MeetingStatus, TranscriptSegment } from "../types";

interface Props {
  status: MeetingStatus;
  segments: TranscriptSegment[];
  speakers: string[];
  interim: string;
  elapsed: number;
  error: string | null;
  result: MeetingResult | null;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
  onRenameSpeaker: (from: string, to: string) => void;
  onOpenMarkdown: (path: string) => void;
  onOpenFolder: (path: string) => void;
}

function SpeakerRow({
  name,
  onRename,
}: {
  name: string;
  onRename: (from: string, to: string) => void;
}) {
  const [draft, setDraft] = useState(name);
  useEffect(() => {
    setDraft(name);
  }, [name]);
  const changed = draft.trim() !== "" && draft.trim() !== name;
  return (
    <div className="speaker-row">
      <span className="speaker-id mono">{name}</span>
      <input
        value={draft}
        aria-label={`Rename ${name}`}
        onChange={(e) => setDraft(e.currentTarget.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && changed) onRename(name, draft.trim());
        }}
      />
      <button
        className="secondary"
        disabled={!changed}
        onClick={() => onRename(name, draft.trim())}
      >
        Rename
      </button>
    </div>
  );
}

export function LiveView({
  status,
  segments,
  speakers,
  interim,
  elapsed,
  error,
  result,
  onPause,
  onResume,
  onStop,
  onRenameSpeaker,
  onOpenMarkdown,
  onOpenFolder,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [confirmStop, setConfirmStop] = useState(false);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [segments, interim]);

  useEffect(() => {
    if (status !== "live" && status !== "paused") setConfirmStop(false);
  }, [status]);

  const live = status === "live" || status === "paused";
  const starting = status === "starting";
  const stopping = status === "stopping";

  const statusLabel =
    status === "live" ? "Recording" : status === "paused" ? "Paused" : starting ? "Connecting capture" : stopping ? "Saving meeting" : "Idle";

  const handleStop = () => {
    if (!live) return;
    if (!confirmStop) {
      setConfirmStop(true);
      return;
    }
    setConfirmStop(false);
    onStop();
  };

  return (
    <div className="live">
      <header className="live-head">
        <div>
          <div className="rec">
            <span className={`level ${status === "live" ? "live" : "paused"}`} aria-hidden="true">
              <i /><i /><i /><i /><i />
            </span>
            <span className={`dot ${status === "live" ? "on" : ""}`} aria-hidden="true" />
            {statusLabel}
          </div>
          <div className="live-sub">
            <span>{segments.length} {segments.length === 1 ? "segment" : "segments"} captured</span>
            <span aria-hidden="true">·</span>
            <span>{interim ? "Hearing speech…" : live ? "Listening for speech" : "Transcript auto-saves locally"}</span>
          </div>
        </div>
        <div className="timer mono" aria-label={`Elapsed ${formatDuration(elapsed)}`}>{formatDuration(elapsed)}</div>
      </header>

      {error && <div className="banner error" role="alert">Transcription interrupted: {error} Your captured segments above are safe. Resume or stop to save.</div>}

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

      {speakers.length > 0 && (
        <section className="panel speakers-panel">
          <h2>Speakers</h2>
          {speakers.map((speaker) => (
            <SpeakerRow
              key={speaker}
              name={speaker}
              onRename={onRenameSpeaker}
            />
          ))}
        </section>
      )}

      <div className="transcript" ref={scrollRef} aria-live="polite">
        {segments.length === 0 && !interim && (
          <div className="empty">
            <strong>{live ? "Listening — speak to test capture" : starting ? "Connecting audio capture…" : "No transcript yet"}</strong>
            <span className="muted">
              {live
                ? "If nothing appears within a few seconds, check the microphone in New Meeting. Interim speech appears below while the engine confirms words."
                : starting
                  ? "Opening microphone and system audio. This takes a moment."
                  : "Start a meeting to see the live transcript. Everything is preserved as raw transcript even if summary fails."}
            </span>
          </div>
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
              <div className="interim-tag">Hearing</div>
              <div className="text">{interim}</div>
            </div>
          </div>
        )}
      </div>

      {confirmStop && live && (
        <div className="banner confirm" role="alert">
          Stop and save this meeting? Transcript ({segments.length} segments) is preserved and meeting.md will be built. Press Stop again to confirm.
        </div>
      )}

      <footer className="controls">
        <span className="stop-hint">{live ? "Pause keeps capture open. Stop saves and builds Markdown." : "Idle — nothing to stop."}</span>
        <span className="spacer" />
        {status === "live" && (
          <button className="secondary" onClick={onPause}>
            Pause capture
          </button>
        )}
        {status === "paused" && (
          <button className="secondary" onClick={onResume}>
            Resume capture
          </button>
        )}
        <button className={`danger ${confirmStop ? "armed" : ""}`} onClick={handleStop} disabled={!live || stopping}>
          {stopping ? "Saving…" : confirmStop ? "Confirm Stop" : "Stop Meeting"}
        </button>
        {confirmStop && (
          <button className="ghost" onClick={() => setConfirmStop(false)}>
            Keep recording
          </button>
        )}
      </footer>
    </div>
  );
}
