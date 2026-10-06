import { useState } from "react";
import type { Settings } from "../types";

interface Props {
  settings: Settings;
  devices: string[];
  outputDir: string;
  hasApiKey: boolean;
  onSave: (settings: Settings, apiKey: string | null) => Promise<void>;
  onClearApiKey: () => Promise<void>;
}

export function SettingsView({
  settings,
  devices,
  outputDir,
  hasApiKey,
  onSave,
  onClearApiKey,
}: Props) {
  const [draft, setDraft] = useState<Settings>(settings);
  const [apiKey, setApiKey] = useState("");
  const [vocabInput, setVocabInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ kind: "ok" | "error"; text: string } | null>(
    null,
  );

  const save = async () => {
    setSaving(true);
    setStatus(null);
    try {
      await onSave(draft, apiKey.trim() || null);
      setApiKey("");
      setStatus({ kind: "ok", text: "Settings saved." });
    } catch (e) {
      setStatus({ kind: "error", text: `Save failed: ${String(e)}` });
    } finally {
      setSaving(false);
    }
  };

  const removeKey = async () => {
    setStatus(null);
    try {
      await onClearApiKey();
      setApiKey("");
      setStatus({ kind: "ok", text: "API key removed." });
    } catch (e) {
      setStatus({ kind: "error", text: `Remove failed: ${String(e)}` });
    }
  };

  const addTerm = () => {
    const term = vocabInput.trim();
    if (!term) return;
    if (!draft.custom_vocabulary.includes(term)) {
      setDraft({ ...draft, custom_vocabulary: [...draft.custom_vocabulary, term] });
    }
    setVocabInput("");
  };

  const removeTerm = (term: string) => {
    setDraft({
      ...draft,
      custom_vocabulary: draft.custom_vocabulary.filter((t) => t !== term),
    });
  };

  return (
    <div className="settings">
      <header className="view-head">
        <h1>Settings</h1>
        <p className="muted">Defaults for capture and accuracy. Changes apply to the next meeting — the current transcript is never touched.</p>
      </header>

      <section className="panel">
        <h2>Gemini API key</h2>
        <p className="hint">
          Stored in the Windows Credential Manager, never in plaintext.
          {hasApiKey ? " A key is currently set." : " No key set yet."}
        </p>
        <div className="field row-inline">
          <input
            type="password"
            value={apiKey}
            placeholder={hasApiKey ? "Replace key (leave blank to keep)" : "Paste API key"}
            onChange={(e) => setApiKey(e.currentTarget.value)}
          />
          {hasApiKey && (
            <button className="secondary" onClick={removeKey}>
              Remove stored key
            </button>
          )}
        </div>
      </section>

      <section className="panel">
        <h2>Audio</h2>
        <div className="field">
          <label>Default microphone</label>
          <select
            value={draft.microphone ?? ""}
            onChange={(e) => setDraft({ ...draft, microphone: e.currentTarget.value || null })}
          >
            <option value="">System default</option>
            {devices.map((device) => (
              <option key={device} value={device}>
                {device}
              </option>
            ))}
          </select>
        </div>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={draft.system_audio}
            onChange={(e) => setDraft({ ...draft, system_audio: e.currentTarget.checked })}
          />
          Enable system audio by default (online meetings)
        </label>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={draft.diarization}
            onChange={(e) => setDraft({ ...draft, diarization: e.currentTarget.checked })}
          />
          Enable speaker diarization
        </label>
        <div className="field">
          <label>Transcription mode</label>
          <select
            value={draft.transcription_mode}
            onChange={(e) => setDraft({ ...draft, transcription_mode: e.currentTarget.value })}
          >
            <option value="VERBATIM">Verbatim</option>
            <option value="SMART">Smart (clean filler and format)</option>
          </select>
        </div>
      </section>

      <section className="panel">
        <h2>Custom vocabulary</h2>
        <p className="hint">
          Product names, people, and technical terms. Improves accuracy and helps
          keep English terms in Latin script.
        </p>
        <div className="chips">
          {draft.custom_vocabulary.map((term) => (
            <span className="chip" key={term}>
              {term}
              <button className="chip-x" onClick={() => removeTerm(term)}>
                ×
              </button>
            </span>
          ))}
        </div>
        <div className="field row-inline">
          <input
            value={vocabInput}
            placeholder="Add term"
            onChange={(e) => setVocabInput(e.currentTarget.value)}
            onKeyDown={(e) => e.key === "Enter" && addTerm()}
          />
          <button className="secondary" onClick={addTerm}>
            Add
          </button>
        </div>
      </section>

      <section className="panel">
        <h2>Output</h2>
        <div className="field">
          <label>Meetings folder</label>
          <input
            value={draft.output_dir ?? ""}
            placeholder={outputDir}
            onChange={(e) => setDraft({ ...draft, output_dir: e.currentTarget.value || null })}
          />
        </div>
      </section>

      {status && (
        <div className={`banner ${status.kind === "ok" ? "success" : "error"}`}>
          {status.text}
        </div>
      )}

      <div className="actions">
        <button className="primary" onClick={save} disabled={saving}>
          {saving ? "Saving..." : "Save Settings"}
        </button>
      </div>
    </div>
  );
}
