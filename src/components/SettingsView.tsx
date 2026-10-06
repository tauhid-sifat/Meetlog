import { useEffect, useState } from "react";
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

  // Parent loads settings async; keep draft in sync until user edits are saved.
  useEffect(() => {
    setDraft(settings);
  }, [settings]);

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
        <h2 id="api-key-heading">Gemini API key</h2>
        <p className="hint" id="api-key-hint">
          Stored in the Windows Credential Manager, never in plaintext.
          {hasApiKey ? " A key is currently set." : " No key set yet."}
        </p>
        <div className="field row-inline">
          <input
            id="api-key-input"
            type="password"
            autoComplete="off"
            value={apiKey}
            aria-labelledby="api-key-heading"
            aria-describedby="api-key-hint"
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
          <label htmlFor="settings-mic">Default microphone</label>
          <select
            id="settings-mic"
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
          <label htmlFor="settings-mode">Transcription mode</label>
          <select
            id="settings-mode"
            value={draft.transcription_mode}
            onChange={(e) => setDraft({ ...draft, transcription_mode: e.currentTarget.value })}
          >
            <option value="VERBATIM">Verbatim</option>
            <option value="SMART">Smart (clean filler and format)</option>
          </select>
        </div>
      </section>

      <section className="panel">
        <h2 id="vocab-heading">Custom vocabulary</h2>
        <p className="hint" id="vocab-hint">
          Product names, people, and technical terms. Improves accuracy and helps
          keep English terms in Latin script.
        </p>
        {draft.custom_vocabulary.length > 0 ? (
          <div className="chips" aria-labelledby="vocab-heading">
            {draft.custom_vocabulary.map((term) => (
              <span className="chip" key={term} title={term}>
                {term}
                <button
                  className="chip-x"
                  onClick={() => removeTerm(term)}
                  aria-label={`Remove ${term}`}
                  title={`Remove ${term}`}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        ) : (
          <p className="hint">No terms yet — add names and product terms below.</p>
        )}
        <div className="field row-inline">
          <input
            id="vocab-input"
            value={vocabInput}
            aria-label="Add vocabulary term"
            aria-describedby="vocab-hint"
            placeholder="Add term"
            maxLength={60}
            onChange={(e) => setVocabInput(e.currentTarget.value)}
            onKeyDown={(e) => e.key === "Enter" && addTerm()}
          />
          <button className="secondary" onClick={addTerm} disabled={!vocabInput.trim()}>
            Add
          </button>
        </div>
      </section>

      <section className="panel">
        <h2>Output</h2>
        <div className="field">
          <label htmlFor="settings-output">Meetings folder</label>
          <input
            id="settings-output"
            value={draft.output_dir ?? ""}
            placeholder={outputDir || "Default location"}
            onChange={(e) => setDraft({ ...draft, output_dir: e.currentTarget.value || null })}
          />
        </div>
      </section>

      {status && (
        <div
          className={`banner ${status.kind === "ok" ? "success" : "error"}`}
          role={status.kind === "ok" ? "status" : "alert"}
        >
          {status.text}
        </div>
      )}

      <div className="actions">
        <button className="primary" onClick={save} disabled={saving} aria-busy={saving}>
          {saving ? "Saving…" : "Save Settings"}
        </button>
      </div>
    </div>
  );
}
