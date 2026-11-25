// Player-facing wording for the few server-side texts that still carry our own jargon (artifact "no DPS effect" reasons, the artifacts note, a stat-row note).
// The server keeps its technical phrasing (it is pinned by the generated data tables); everything the player reads goes through `plainText` first.
// Unknown texts pass through unchanged, and the guard test (ui-text.test.tsx) fails when a forbidden word still reaches the screen.

const RULES: [RegExp, string][] = [
  [/^reference_only artifacts:.*$/i, "Baked-in artifacts are already inside the stats you typed, so equipping them changes nothing here; their gain in the ranking is a what-if."],
  [/stat not used by the DPS model/gi, "stat not used for damage"],
  [/\(Accuracy vs Evasion not modelled\)/gi, "(accuracy and evasion do not change damage here)"],
  [/\(not modelled\)/gi, "(not covered)"],
  [/\s*\(block F minus the main sheet's F\)/gi, ""],
  [/\bin the DPS model\b/gi, "here"],
];

export function plainText(text: string | null | undefined): string {
  if (!text) return "";
  return RULES.reduce((t, [re, to]) => t.replace(re, to), text);
}
