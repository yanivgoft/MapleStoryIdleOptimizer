// "Import from Excel (.xlsx)" in the Profiles tab: pick or drop a <Class>-DPS-Calculator.xlsx, preview what will be imported, save it as a NEW profile.
// The file is read ENTIRELY IN THE BROWSER (File.arrayBuffer -> fflate -> DOMParser); it is never uploaded.  The only network call is the class SCHEMA
// (static class definition, no user data), exactly as when you switch class.  The heavy parts (unzip + the workbook map) are loaded on first use.
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import "./importxlsx.css";
import { api } from "../api";
import type { ClassInfo, ClassSchema, Profile } from "../types";
import { listProfiles, saveProfile } from "../lib/profiles";
import type { ImportResult, Loaded, NoteGroup } from "../lib/importXlsx";

type Lib = typeof import("../lib/importXlsx");
let libPromise: Promise<Lib> | null = null;
const loadLib = () => (libPromise ??= import("../lib/importXlsx"));

/** What the user sees when a file cannot be used (friendly wording; XlsxError messages are already written for people). */
export function describeLoadError(e: unknown): string {
  const err = e as { name?: string; code?: string; message?: string; status?: number };
  if (err?.name === "XlsxError") {
    return err.code === "not_zip" ? `${err.message} (Saved profiles in .json files are loaded with "Import file" instead.)` : (err.message ?? "This file cannot be read.");
  }
  if (err?.name === "ApiError" || typeof err?.status === "number") return `Could not load the class definition from the server (${err.message ?? "error"}). Your file was not uploaded anywhere; try again in a moment.`;
  return `This file could not be read: ${err?.message ?? "unknown error"}`;
}

const CUBES_SHEET = "PotentialCubes";

export const filesOfDrop = (dt: { files?: ArrayLike<File> } | null | undefined): File[] => Array.from(dt?.files ?? []);

interface Props {
  classes: ClassInfo[];
  /** The new profile was saved (the Profiles list should refresh); `load` asks the app to open it right away. */
  onSaved: (p: Profile, load: boolean) => void;
  /** Test seam: schema loader (default: the app's API client, which serves fixtures in mock mode). */
  loadSchema?: (classId: string) => Promise<ClassSchema>;
}

interface Opened {
  loaded: Loaded;
  classId: string | null; // detected or chosen
  chosen: boolean;
  schema: ClassSchema | null;
  schemaError: string | null;
}

export function ImportXlsx({ classes, onSaved, loadSchema = api.schema }: Props) {
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [opened, setOpened] = useState<Opened | null>(null);
  const [lib, setLib] = useState<Lib | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const hintId = useId();

  const pickSchema = useCallback(
    async (loaded: Loaded, classId: string | null, chosen: boolean) => {
      if (!classId) {
        setOpened({ loaded, classId: null, chosen, schema: null, schemaError: null });
        return;
      }
      try {
        const schema = await loadSchema(classId);
        setOpened({ loaded, classId, chosen, schema, schemaError: null });
      } catch (e) {
        setOpened({ loaded, classId, chosen, schema: null, schemaError: describeLoadError(e) });
      }
    },
    [loadSchema],
  );

  const handleFile = useCallback(
    async (file: File | undefined, extra = 0) => {
      if (!file) return;
      setError(null);
      setBusy(true);
      try {
        const l = await loadLib();
        setLib(l);
        const loaded = await l.loadWorkbookFile(file);
        if (!loaded.book.hasSheet("Inputs")) {
          throw Object.assign(new Error(`This workbook has no "Inputs" sheet, so it is not one of the MapleStory Idle DPS calculators (its sheets: ${loaded.book.sheetNames.slice(0, 6).join(", ")}).`), { name: "XlsxError", code: "not_xlsx" });
        }
        await pickSchema(loaded, loaded.classId, false);
        if (extra > 0) setError(`${extra} more file${extra === 1 ? " was" : "s were"} dropped; only "${file.name}" is imported (one workbook at a time).`);
      } catch (e) {
        setError(describeLoadError(e));
        setOpened(null);
      } finally {
        setBusy(false);
        if (inputRef.current) inputRef.current.value = "";
      }
    },
    [pickSchema],
  );

  return (
    <section className="xlsx-import" aria-labelledby={`${hintId}-h`}>
      <h3 id={`${hintId}-h`}>Import from your Excel calculator</h3>
      <p className="note" id={hintId}>
        Already filled in a <code>&lt;Class&gt;-DPS-Calculator.xlsx</code>? Load its typed-in values instead of retyping them. The file is read in your browser only and is never uploaded.
      </p>
      <div
        className={`xlsx-drop${over ? " over" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          const files = filesOfDrop(e.dataTransfer);
          void handleFile(files[0], files.length - 1);
        }}
      >
        <label className="filebtn" htmlFor="import-xlsx-file">
          Import from Excel (.xlsx)
        </label>
        <input
          ref={inputRef}
          id="import-xlsx-file"
          type="file"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          className="sr-only"
          aria-describedby={hintId}
          disabled={busy}
          onChange={(e) => void handleFile(e.target.files?.[0])}
        />
        <span className="hint">{busy ? "Reading the workbook..." : "or drop the .xlsx file here"}</span>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {opened && lib && (
        <ImportFlow
          lib={lib}
          opened={opened}
          classes={classes}
          loadSchema={pickSchema}
          onCancel={() => setOpened(null)}
          onApplied={(p, load) => {
            setOpened(null);
            onSaved(p, load);
          }}
        />
      )}
    </section>
  );
}

/** Class choice (when the title was not recognised or the user overrides it) -> schema -> import -> dialog. */
function ImportFlow({
  lib,
  opened,
  classes,
  loadSchema,
  onCancel,
  onApplied,
}: {
  lib: Lib;
  opened: Opened;
  classes: ClassInfo[];
  loadSchema: (l: Loaded, id: string | null, chosen: boolean) => Promise<void>;
  onCancel: () => void;
  onApplied: (p: Profile, load: boolean) => void;
}) {
  const result = useMemo<ImportResult | { error: string } | null>(() => {
    if (!opened.schema) return null;
    try {
      return lib.importWorkbook(opened.loaded.book, opened.schema, { classChosen: opened.chosen });
    } catch (e) {
      return { error: describeLoadError(e) };
    }
  }, [lib, opened]);
  const ok = result && !("error" in result) ? result : null;
  return (
    <ImportDialog
      lib={lib}
      fileName={opened.loaded.fileName}
      fileTitle={opened.loaded.title}
      classes={classes}
      classId={opened.classId}
      detected={!!opened.loaded.classId && !opened.chosen}
      result={ok}
      problem={opened.schemaError ?? (result && "error" in result ? result.error : null)}
      onClass={(id) => {
        void loadSchema(opened.loaded, id, true);
      }}
      onCancel={onCancel}
      onApply={(name, load) => {
        if (!ok) return;
        const final = lib.uniqueProfileName(name, listProfiles(), ok.state.classId);
        onApplied(saveProfile(final, ok.state), load);
      }}
    />
  );
}

export interface DialogProps {
  lib: Pick<Lib, "groupNotes" | "uniqueProfileName">;
  fileName: string;
  fileTitle: string | null;
  classes: ClassInfo[];
  classId: string | null;
  detected: boolean; // the class was recognised from the workbook title
  result: ImportResult | null;
  problem: string | null;
  onClass: (id: string) => void;
  onCancel: () => void;
  onApply: (profileName: string, loadNow: boolean) => void;
}

/** The preview dialog (pure presentation + modal behaviour; the import itself happened before). */
export function ImportDialog(p: DialogProps) {
  const id = useId();
  const ref = useRef<HTMLDivElement>(null);
  const className = p.classes.find((c) => c.id === p.classId)?.name ?? p.result?.summary.className ?? "";
  const [typed, setTyped] = useState<string | null>(null); // null = still the suggested name
  const name = typed ?? `${className || "Workbook"} (Excel import)`.slice(0, 60);
  const [loadNow, setLoadNow] = useState(true);
  const existing = useMemo(() => (typeof localStorage === "undefined" ? [] : listProfiles()), []);
  const finalName = p.result ? p.lib.uniqueProfileName(name, existing, p.result.state.classId) : name;

  // modal behaviour: focus moves in, Tab stays inside, Escape closes, focus returns to what opened it
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    return () => prev?.focus?.();
  }, []);
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.stopPropagation();
      p.onCancel();
      return;
    }
    if (e.key !== "Tab" || !ref.current) return;
    const items = Array.from(ref.current.querySelectorAll<HTMLElement>("button:not([disabled]), input:not([disabled]), select:not([disabled]), summary"));
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && (document.activeElement === first || document.activeElement === ref.current)) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  const r = p.result;
  const s = r?.summary;
  const warnGroups = r ? p.lib.groupNotes(r.warnings) : [];
  const ignoredGroups = r ? p.lib.groupNotes(r.ignored) : [];
  const loadoutCts = s ? Object.keys(s.loadouts) : [];
  const nContents = s ? Object.keys(s.valuesPerContent).length + s.skippedContentTypes.length : 0;
  const cubesTabMissing = p.classes.find((c) => c.id === p.classId)?.status?.stat_values === false;
  const nImported = s ? Object.keys(s.valuesPerContent).length : 0;

  return (
    <div className="xlsx-backdrop" onMouseDown={(e) => e.target === e.currentTarget && p.onCancel()}>
      <div ref={ref} className="xlsx-dialog" role="dialog" aria-modal="true" aria-labelledby={`${id}-t`} aria-describedby={`${id}-d`} tabIndex={-1} onKeyDown={onKeyDown}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (r) p.onApply(name, loadNow);
          }}
        >
          <h2 id={`${id}-t`}>Import from Excel</h2>
          <p className="note" id={`${id}-d`}>
            Preview of what will be imported from <strong>{p.fileName}</strong>. Nothing is saved until you press Import; the file stays on your device.
          </p>

          <div className="field-row">
            <label htmlFor={`${id}-class`}>Class</label>
            <select id={`${id}-class`} value={p.classId ?? ""} onChange={(e) => e.target.value && p.onClass(e.target.value)}>
              {!p.classId && <option value="">Choose the class...</option>}
              {p.classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <span className="note">
              {p.detected
                ? `Recognised from the workbook title "${p.fileTitle ?? ""}".`
                : p.classId
                  ? "Chosen by you."
                  : `The workbook title ${p.fileTitle ? `"${p.fileTitle}" ` : ""}is not one of the calculators' - pick the class it was made for.`}
            </span>
          </div>

          {p.problem && (
            <p className="error" role="alert">
              {p.problem}
            </p>
          )}

          {r && s && (
            <>
              <dl className="facts">
                <dt>Character level</dt>
                <dd>{s.level ?? "not set (default used)"}</dd>
                <dt>Opens on</dt>
                <dd>{s.contentType}</dd>
                <dt>Content types</dt>
                <dd>
                  {nImported} of {nImported + s.skippedContentTypes.length} with values
                  {s.skippedContentTypes.length > 0 && <span className="note"> (none for {s.skippedContentTypes.join(", ")}; they start from the defaults)</span>}
                </dd>
                <dt>Artifacts</dt>
                <dd>
                  {loadoutCts.length ? (
                    <>
                      equipped artifacts set for {loadoutCts.length} of {nContents} content types
                      <span className="note"> ({loadoutCts.map((ct) => `${ct}: ${s.loadouts[ct].join(", ")}`).join("; ")})</span>
                    </>
                  ) : (
                    "none equipped"
                  )}
                  <span className="note">
                    {" "}
                    - star levels of {s.starsRead} artifact{s.starsRead === 1 ? "" : "s"} and {s.linesRead} potential line{s.linesRead === 1 ? "" : "s"} read from ArtifactsInput
                  </span>
                </dd>
                <dt>Companions</dt>
                <dd>{s.companionLevels.length ? s.companionLevels.map((c) => `${c.name} Lv ${c.level}`).join(", ") : "none unlocked"}</dd>
                <dt>Cubes</dt>
                <dd>
                  {s.cubesRead ? (
                    <>
                      {s.cubePieces} piece{s.cubePieces === 1 ? "" : "s"} with lines
                      <span className="note">
                        {" "}
                        - {s.cubeLines} line{s.cubeLines === 1 ? "" : "s"}; {s.cubeRows} of 30 gear rows set (rarity, pity or lines), read from {CUBES_SHEET}
                        {cubesTabMissing && "; the Cubes tab is not available for this class yet, the gear is kept in the profile for when it is"}
                      </span>
                    </>
                  ) : (
                    <span className="note">no {CUBES_SHEET} sheet in the file</span>
                  )}
                </dd>
              </dl>

              <details>
                <summary>Values read per content type</summary>
                <table className="counts">
                  <thead>
                    <tr>
                      <th scope="col">Content type</th>
                      <th scope="col" className="num">
                        Values
                      </th>
                      <th scope="col">Companion</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(s.valuesPerContent).map(([ct, n]) => (
                      <tr key={ct}>
                        <th scope="row">{ct}</th>
                        <td className="num">{n}</td>
                        <td>{s.companionChoices[ct] ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>

              <details className={warnGroups.length ? "warn" : undefined} open={warnGroups.length > 0}>
                <summary>Warnings ({r.warnings.length})</summary>
                {warnGroups.length > 0 ? (
                  <>
                    <p className="note">These values were imported as typed (or replaced by a default where unreadable) - check them after importing.</p>
                    <NoteList groups={warnGroups} />
                  </>
                ) : (
                  <p className="note">No warnings.</p>
                )}
              </details>
              <details>
                <summary>Ignored ({r.ignored.length})</summary>
                {ignoredGroups.length > 0 ? <NoteList groups={ignoredGroups} /> : <p className="note">Nothing was ignored.</p>}
              </details>

              <div className="field-row">
                <label htmlFor={`${id}-name`}>New profile name</label>
                <input id={`${id}-name`} type="text" value={name} maxLength={60} onChange={(e) => setTyped(e.target.value)} />
              </div>
              {finalName !== (name.trim() || "Excel import") && (
                <p className="note" role="status">
                  A profile with this name already exists; it will be saved as &quot;{finalName}&quot; (nothing is overwritten).
                </p>
              )}
              <div className="field-row">
                <input id={`${id}-load`} type="checkbox" checked={loadNow} onChange={(e) => setLoadNow(e.target.checked)} />
                <label htmlFor={`${id}-load`}>Open it in the calculator after importing</label>
              </div>
            </>
          )}

          <div className="buttons">
            <button type="button" onClick={p.onCancel}>
              Cancel
            </button>
            <button type="submit" disabled={!r}>
              Import as new profile
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function NoteList({ groups }: { groups: NoteGroup[] }) {
  return (
    <ul className="notes">
      {groups.map((g) => (
        <li key={g.message}>
          {g.message}{" "}
          <span className="cells">
            ({g.wheres.slice(0, 12).join(", ")}
            {g.wheres.length > 12 ? `, +${g.wheres.length - 12} more` : ""})
          </span>
        </li>
      ))}
    </ul>
  );
}
