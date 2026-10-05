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
          <h1>Meetings</h1>
          <p className="muted mono">{outputDir}</p>
        </div>
        <button className="secondary" onClick={onRefresh}>
          Refresh
        </button>
      </header>

      {meetings.length === 0 ? (
        <p className="muted empty">No meetings yet.</p>
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
                    Open Markdown
                  </button>
                ) : (
                  <span className="muted">no markdown</span>
                )}
                <button className="ghost" onClick={() => onOpenFolder(meeting.folder)}>
                  Folder
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
