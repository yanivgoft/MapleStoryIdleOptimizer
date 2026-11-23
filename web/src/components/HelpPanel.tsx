import { useMemo } from "react";
import type { ClassInfo, ClassSchema, Field } from "../types";
import { groupClasses, optionLabel } from "../lib/classes";
import { ACCOUNTS, CAPABILITY_COLUMNS, PRIVACY, CONVENTIONS, HOW_TO_USE, INTRO, KNOWN_GAPS_URL, LIMITATIONS, NO_SCHEMA_HINTS, WHICH_STATS_INTRO, classCapabilities } from "../content/help";

import { CLOUD_ENABLED } from "../lib/cloud/config";

export const HELP_SECTIONS = [
  { id: HOW_TO_USE.id, title: HOW_TO_USE.title },
  { id: "help-which-stats", title: "Which stats to type" },
  { id: CONVENTIONS.id, title: CONVENTIONS.title },
  { id: "help-modelled", title: "What is modelled per class" },
  { id: "help-limitations", title: "Known limitations" },
  { id: PRIVACY.id, title: PRIVACY.title },
] as const;

/** Fields worth explaining: the typed stats, grouped like the form (computed rows, the content-type picker and the read-only companion level are left out). */
export function hintGroups(schema: ClassSchema): { group: string; fields: Field[] }[] {
  const groups: { group: string; fields: Field[] }[] = [];
  for (const f of schema.fields) {
    if (f.computed || f.key === "content_type" || f.key === "companion_level" || !f.help) continue;
    let g = groups.find((x) => x.group === f.group);
    if (!g) groups.push((g = { group: f.group, fields: [] }));
    g.fields.push(f);
  }
  return groups;
}

function FieldHints({ schema }: { schema: ClassSchema | null }) {
  const groups = useMemo(() => (schema ? hintGroups(schema) : []), [schema]);
  if (!schema) return NO_SCHEMA_HINTS;
  return (
    <>
      <h4>Field hints for {schema.name}</h4>
      {groups.map((g) => (
        <section key={g.group} aria-label={g.group}>
          <h5>{g.group}</h5>
          <dl className="help-fields">
            {g.fields.map((f) => (
              <div key={f.key}>
                <dt>
                  {f.label}
                  {f.unit && f.unit !== "flat" && !f.label.includes(f.unit) ? <span className="unit"> ({f.unit})</span> : null}
                </dt>
                <dd>{f.help}</dd>
              </div>
            ))}
          </dl>
        </section>
      ))}
    </>
  );
}

function ClassTable({ classes }: { classes: ClassInfo[] }) {
  const groups = useMemo(() => groupClasses(classes), [classes]);
  return (
    <div className="table-wrap">
      <table className="help-table">
        <caption className="sr-only">What the app models for each class</caption>
        <thead>
          <tr>
            <th scope="col">Class</th>
            {CAPABILITY_COLUMNS.map((c) => (
              <th scope="col" key={c}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {groups.flatMap((g) =>
            g.classes.map((c) => {
              const cap = classCapabilities(c);
              return (
                <tr key={c.id} data-class={c.id}>
                  <th scope="row">{optionLabel(c)}</th>
                  {CAPABILITY_COLUMNS.map((col) => (
                    <td key={col} className={cap[col] ? "yes" : "no"}>
                      {cap[col] ? "yes" : "coming soon"}
                    </td>
                  ))}
                </tr>
              );
            }),
          )}
        </tbody>
      </table>
    </div>
  );
}

/** The "Help" tab: how to use the app, which stats to type, the modelling conventions, what each class supports and the known limitations.  Copy lives in content/help.tsx. */
export function HelpPanel({ classes, schema }: { classes: ClassInfo[]; schema: ClassSchema | null }) {
  return (
    <article className="help" aria-labelledby="help-title">
      <h2 id="help-title">Help</h2>
      {INTRO}
      <nav aria-label="On this page" className="help-toc">
        <ul>
          {[...HELP_SECTIONS, ...(CLOUD_ENABLED ? [{ id: ACCOUNTS.id, title: ACCOUNTS.title }] : [])].map((s) => (
            <li key={s.id}>
              <a href={`#${s.id}`}>{s.title}</a>
            </li>
          ))}
        </ul>
      </nav>

      <section id={HOW_TO_USE.id} aria-labelledby={`${HOW_TO_USE.id}-h`} className="card">
        <h3 id={`${HOW_TO_USE.id}-h`}>{HOW_TO_USE.title}</h3>
        {HOW_TO_USE.body}
      </section>

      <section id="help-which-stats" aria-labelledby="help-which-stats-h" className="card">
        <h3 id="help-which-stats-h">Which stats to type</h3>
        {WHICH_STATS_INTRO}
        <FieldHints schema={schema} />
      </section>

      <section id={CONVENTIONS.id} aria-labelledby={`${CONVENTIONS.id}-h`} className="card">
        <h3 id={`${CONVENTIONS.id}-h`}>{CONVENTIONS.title}</h3>
        {CONVENTIONS.body}
      </section>

      <section id="help-modelled" aria-labelledby="help-modelled-h" className="card">
        <h3 id="help-modelled-h">What is modelled per class</h3>
        <p>
          The calculator works for every class.  The other features depend on how much of the class's data the engine has; "coming soon" means the tab shows a "not available for this class yet" message.
          Stat values, Cubes and Equipment compare share one switch because the cube tabs price lines with the stat-values engine.
        </p>
        <ClassTable classes={classes} />
      </section>

      <section id="help-limitations" aria-labelledby="help-limitations-h" className="card">
        <h3 id="help-limitations-h">Known limitations</h3>
        <ul>
          {LIMITATIONS.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
        <p>
          The full list, class by class, is in{" "}
          <a href={KNOWN_GAPS_URL} target="_blank" rel="noreferrer noopener">
            KNOWN_GAPS.md on GitHub
          </a>
          .
        </p>
      </section>

      <section id={PRIVACY.id} aria-labelledby={`${PRIVACY.id}-h`} className="card">
        <h3 id={`${PRIVACY.id}-h`}>{PRIVACY.title}</h3>
        {PRIVACY.body}
      </section>

      {CLOUD_ENABLED && (
        <section id={ACCOUNTS.id} aria-labelledby={`${ACCOUNTS.id}-h`} className="card">
          <h3 id={`${ACCOUNTS.id}-h`}>{ACCOUNTS.title}</h3>
          {ACCOUNTS.body}
        </section>
      )}
    </article>
  );
}
