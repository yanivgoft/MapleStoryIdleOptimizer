import { useEffect, useRef, useState } from "react";
import type { ClassInfo, FormState, Profile } from "../types";
import { ImportXlsx } from "./ImportXlsx";
import { deleteProfile, exportJson, importProfiles, listProfiles, parseImport, saveProfile, subscribeProfiles } from "../lib/profiles";
import { useCloudBridge } from "../lib/cloud/bridge";
import { CloudStatusIcon } from "./CloudStatusIcon";

interface Props {
  state: FormState;
  classes: ClassInfo[];
  onLoad: (p: Profile) => void;
}

export function ProfilesPanel({ state, classes, onLoad }: Props) {
  const [profiles, setProfiles] = useState<Profile[]>(listProfiles);
  const [name, setName] = useState("");
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const refresh = () => setProfiles(listProfiles());
  // optional accounts feature (null = off): the list also changes when the account merges / downloads profiles
  const cloud = useCloudBridge();
  useEffect(() => subscribeProfiles(() => setProfiles(listProfiles())), []);
  const className = (id: string) => classes.find((c) => c.id === id)?.name ?? id;

  const download = (list: Profile[], file: string) => {
    const url = URL.createObjectURL(new Blob([exportJson(list)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = file;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="card profiles" aria-label="Saved profiles">
      <h2>Saved profiles</h2>
      {cloud ? (
        <p className="note">
          Profiles live in this browser (localStorage); {cloud.signedIn ? "press Save to account to copy the changed ones to your account" : "sign in (header) to keep them in your account"}. You can also export a file to back them up.
        </p>
      ) : (
        <p className="note">Profiles live only in this browser (localStorage). Export a file to back them up or move them to another device.</p>
      )}
      {cloud?.signedIn && (
        <div className="cloud-bar">
          <button type="button" disabled={cloud.busy || cloud.dirtyCount === 0} onClick={cloud.save}>
            Save to account{cloud.dirtyCount > 0 ? ` (${cloud.dirtyCount} unsaved)` : ""}
          </button>
          <button type="button" disabled={cloud.busy} onClick={cloud.refresh}>
            Refresh from account
          </button>
        </div>
      )}
      <form
        className="row"
        onSubmit={(e) => {
          e.preventDefault();
          saveProfile(name, state);
          setMsg({ kind: "ok", text: `Saved "${name.trim() || "Unnamed"}"` });
          setName("");
          refresh();
        }}
      >
        <label htmlFor="profile-name">Profile name</label>
        <input id="profile-name" value={name} maxLength={60} onChange={(e) => setName(e.target.value)} placeholder="e.g. Main, 140 Breakthrough" />
        <button type="submit">Save current inputs</button>
      </form>

      {profiles.length === 0 ? (
        <p className="empty">No saved profiles yet.</p>
      ) : (
        <ul className="plist">
          {profiles.map((p) => (
            <li key={p.id}>
              <div>
                {cloud && cloud.statuses[p.id] && <CloudStatusIcon status={cloud.statuses[p.id]} />}
                <strong>{p.name}</strong>
                <span className="meta">
                  {className(p.state.classId)} · {p.state.contentType} · {new Date(p.savedAt).toLocaleString()}
                </span>
                {cloud?.errors[p.id] && <span className="cloud-msg">{cloud.errors[p.id]}</span>}
              </div>
              <div className="actions">
                <button onClick={() => onLoad(p)}>Load</button>
                <button onClick={() => download([p], `${p.name.replace(/[^\w-]+/g, "_")}.json`)}>Export</button>
                <button
                  className="danger"
                  onClick={() => {
                    if (window.confirm(`Delete profile "${p.name}"?`)) {
                      deleteProfile(p.id);
                      refresh();
                    }
                  }}
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <div className="row">
        <button disabled={profiles.length === 0} onClick={() => download(profiles, "msi-profiles.json")}>
          Export all
        </button>
        <label className="filebtn" htmlFor="import-file">
          Import file
        </label>
        <input
          ref={fileRef}
          id="import-file"
          type="file"
          accept="application/json,.json"
          className="sr-only"
          onChange={async (e) => {
            const f = e.target.files?.[0];
            if (!f) return;
            try {
              const n = importProfiles(parseImport(await f.text()));
              setMsg({ kind: "ok", text: `Imported ${n} profile${n === 1 ? "" : "s"}` });
              refresh();
            } catch (err) {
              setMsg({ kind: "err", text: (err as Error).message });
            }
            if (fileRef.current) fileRef.current.value = "";
          }}
        />
      </div>
      <ImportXlsx
        classes={classes}
        onSaved={(p, load) => {
          setMsg({ kind: "ok", text: `Imported "${p.name}" from Excel as a new profile (${className(p.state.classId)}).` });
          refresh();
          if (load) onLoad(p);
        }}
      />
      {msg && (
        <p className={msg.kind === "ok" ? "note" : "error"} role="status">
          {msg.text}
        </p>
      )}
    </section>
  );
}
