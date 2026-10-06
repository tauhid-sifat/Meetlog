//! Meeting history: list saved meeting folders and read their files.

use std::path::Path;

use serde::Serialize;

#[derive(Serialize)]
pub struct MeetingInfo {
    pub folder: String,
    pub name: String,
    pub date: String,
    pub title: String,
    pub has_markdown: bool,
    pub markdown_path: Option<String>,
    pub modified: u64,
}

/// List meeting folders under `output_dir`, newest first.
pub fn list_meetings(output_dir: &Path) -> Vec<MeetingInfo> {
    let mut out = Vec::new();
    let Ok(entries) = std::fs::read_dir(output_dir) else {
        return out;
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }
        let name = path
            .file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_default();
        let (date, title) = match name.split_once(" - ") {
            Some((d, t)) => (d.to_string(), t.to_string()),
            None => (String::new(), name.clone()),
        };
        let markdown = path.join("meeting.md");
        let has_markdown = markdown.exists();
        let modified = entry
            .metadata()
            .ok()
            .and_then(|m| m.modified().ok())
            .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
            .map(|d| d.as_secs())
            .unwrap_or(0);

        out.push(MeetingInfo {
            folder: path.to_string_lossy().to_string(),
            name,
            date,
            title,
            has_markdown,
            markdown_path: has_markdown.then(|| markdown.to_string_lossy().to_string()),
            modified,
        });
    }

    out.sort_by(|a, b| b.name.cmp(&a.name));
    out
}
