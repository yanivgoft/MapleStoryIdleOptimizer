import { useMemo } from "react";
import type { ClassInfo } from "../types";
import { groupClasses, optionLabel, statusItems, statusLine } from "../lib/classes";

interface Props {
  classes: ClassInfo[];
  value: string | null;
  onChange: (id: string) => void;
}

/** Class dropdown grouped by job family ("Hero (STR / DEX)") plus a status line for the selected class: what the engine models. */
export function ClassPicker({ classes, value, onChange }: Props) {
  const groups = useMemo(() => groupClasses(classes), [classes]);
  const current = classes.find((c) => c.id === value);
  return (
    <div className="class-picker">
      <label htmlFor="class-picker" className="sr-only">
        Class
      </label>
      <select id="class-picker" value={value ?? ""} onChange={(e) => onChange(e.target.value)} disabled={!classes.length}>
        {groups.map((g) => (
          <optgroup key={g.family} label={g.family}>
            {g.classes.map((c) => (
              <option key={c.id} value={c.id}>
                {optionLabel(c)}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      {current && (
        <p className="class-status" title={statusLine(current)} aria-label={`Status: ${statusLine(current)}`}>
          <span className="status-title">Status</span>
          {statusItems(current).map((i) => (
            <span key={i.label} className={`status-item ${i.state}`}>
              {i.label}: {i.state === "ready" ? "yes" : "coming soon"}
            </span>
          ))}
        </p>
      )}
    </div>
  );
}
