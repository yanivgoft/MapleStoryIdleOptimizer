const SUFFIXES: [number, string][] = [
  [1e24, "Sp"],
  [1e21, "Sx"],
  [1e18, "Qi"],
  [1e15, "Qa"],
  [1e12, "T"],
  [1e9, "B"],
  [1e6, "M"],
  [1e3, "K"],
];

/**
 * Compact number: 1.23e12 -> "1.23T", 45678 -> "45.7K", 999 -> "999".  Three significant digits for abbreviated values;
 * values below 1000 keep up to 2 decimals.  Non-finite or missing values render as an en dash.
 */
export function formatNumber(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "–";
  const abs = Math.abs(value);
  if (abs < 1000) {
    if (abs === 0) return "0";
    return String(Number(value.toFixed(abs < 10 ? 2 : 1)));
  }
  for (const [limit, suffix] of SUFFIXES) {
    if (abs >= limit) {
      let scaled = value / limit;
      // rounding can carry into the next unit (999.9K -> 1000K): bump it
      if (Math.abs(Number(scaled.toPrecision(digits))) >= 1000) {
        const idx = SUFFIXES.findIndex(([l]) => l === limit);
        if (idx > 0) {
          const [nl, ns] = SUFFIXES[idx - 1];
          scaled = value / nl;
          return `${Number(scaled.toPrecision(digits))}${ns}`;
        }
      }
      return `${Number(scaled.toPrecision(digits))}${suffix}`;
    }
  }
  return String(value);
}

/** Full number with thousands separators (tooltips). */
export function formatFull(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "–";
  return Math.round(value).toLocaleString("en-US");
}

export function formatPercent(fraction: number | null | undefined, digits = 1): string {
  if (fraction === null || fraction === undefined || !Number.isFinite(fraction)) return "–";
  return `${(fraction * 100).toFixed(digits)}%`;
}
