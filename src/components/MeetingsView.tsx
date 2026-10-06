import type { MeetingInfo } from "../types";

interface Props {
  meetings: MeetingInfo[];
  outputDir: string;
  onRefresh: () => void;
  onOpenMarkdown: (path: string) => void;
  onOpenFolder: (path: string) => void;
}

export function MeetingsView({
  meetings,
  outputDir,
  onRefresh,
  onOpenMarkdown,
  onOpenFolder,
}: Props) {
  return (
    <div className="meetings">
      <header className="view-head row-between">
        <div>
          <h1>Meeting memory</h1>
          <p className="muted">Every saved meeting lives as portable Markdown. Raw transcript is always preserved.</p>
          <p className="muted mono">{outputDir}</p>
        </div>
        <button className="secondary" onClick={onRefresh}>
          Refresh list
        </button>
      </header>

      {meetings.length === 0 ? (
        <div className="panel">
          <h2>No meetings yet</h2>
          <p className="hint">Start your first meeting and Meetlog will file meeting.md, transcript.json, and metadata here automatically.</p>
        </div>
      ) : (
        <ul className="meeting-list">
          {meetings.map((meeting) => (
            <li key={meeting.folder} className="meeting-item">
              <div>
                <div className="meeting-title">{meeting.title || meeting.name}</div>
                <div className="muted mono">{meeting.date}</div>
              </div>
              <div className="meeting-actions">
                {meeting.markdown_path ? (
                  <button
                    className="secondary"
                    onClick={() => onOpenMarkdown(meeting.markdown_path!)}
                  >
                    Open meeting.md
                  </button>
                ) : (
                  <span className="muted">no markdown</span>
                )}
                <button className="ghost" onClick={() => onOpenFolder(meeting.folder)}>
                  Show folder
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
