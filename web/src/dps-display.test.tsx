// GUARD (user rule): the ONLY absolute DPS figure in the whole app is the Total DPS of the Calculator's results summary, shown exactly once.  Everywhere else a
// DPS amount is a % (of the current Total DPS).  Every tab / section is rendered with the fixtures; the visible text AND every attribute (title, aria-label, data-*)
// must contain no absolute DPS: neither the formatted form (12.3Qa, 12,300,000,000,000,000) of any DPS-like number of that tab's fixtures, nor "<number> DPS".
import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import { ALL, WITH_STAT_VALUES, fixtureFor } from "./test/fixtures";
import { sensFixture } from "./test/sensFixture";
import { cubesFixture } from "./test/cubesFixture";
import { initialState } from "./lib/schemaForm";
import { IDLE } from "./lib/sensitivityLoader";
import { IDLE_STATUS } from "./lib/liveRequest";
import { blankEquip } from "./lib/equipment";
import { IDLE_RUN, type RunState } from "./lib/cubesRunner";
import { blankRow, cubesCsv, gearKey, type CubesState } from "./lib/cubes";
import { emptyArtifacts, normalizeSlots, setLine, setStar } from "./lib/artifacts";
import { formatFull, formatNumber } from "./lib/format";
import type { ArtifactSchema, ArtifactsState, ComputeResult, FormState } from "./types";
import { Results } from "./components/Results";
import { ArtifactsPanel } from "./components/ArtifactsPanel";
import { ArtifactTableView } from "./components/ArtifactTable";
import { CompanionsView } from "./components/CompanionsPanel";
import { EquipmentView } from "./components/EquipmentPanel";
import { StatValuesView } from "./components/StatValues";
import { CubesView } from "./components/CubesPanel";
import { STATIC_POTENTIAL_TABLES, type PotentialsResult } from "./lib/artifactPotentials";

const noop = () => undefined;
const strip = (h: string) => h.replace(/<!-- -->/g, "");
const none = { loading: false, unsupported: false, error: null, fieldErrors: [] };

/** Numeric leaves of a fixture that are DPS amounts (keys like dps / gain / total / baseline / uplift / current_value / milestone_ev; never a % or a ratio). */
const DPS_KEY = /(dps|gain|total|baseline|uplift|current_value|milestone_ev)/i;
const NOT_DPS_KEY = /(pct|ratio|share|weight|rank|level|star|pity|_n$|smallest|^n_for)/i;
export function dpsNumbers(node: unknown, key = "", under = false, out = new Set<number>()): Set<number> {
  if (typeof node === "number") {
    if (under && Number.isFinite(node) && Math.abs(node) >= 1e6) out.add(Math.abs(node));
  } else if (Array.isArray(node)) {
    node.forEach((x) => dpsNumbers(x, key, under, out));
  } else if (node && typeof node === "object") {
    for (const [k, v] of Object.entries(node)) {
      if (NOT_DPS_KEY.test(k)) continue;
      dpsNumbers(v, k, under || DPS_KEY.test(k), out);
    }
  }
  return out;
}

/** The ways an absolute number can appear on screen. */
function renderings(v: number): string[] {
  return [formatNumber(v, 3), formatNumber(v, 4), formatFull(v), String(Math.round(v))];
}
const tokenRe = (s: string) => new RegExp(`(?<![\\d.,])${s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![\\d]|[.,]\\d)`, "g");
const count = (html: string, s: string) => (html.match(tokenRe(s)) ?? []).length;

/** "12 DPS", "3.4Qa DPS", "1,000 DPS" (a number directly followed by the word DPS; "+1% DPS" is a percentage and fine). */
const NUMBER_DPS = /\d\s*(?:K|M|B|T|Qa|Qi|Sx|Sp)?\s+DPS\b/;

function expectNoAbsolute(label: string, html: string, fixtures: unknown[], allowed: Map<string, number> = new Map()) {
  const numbers = new Set<number>();
  for (const f of fixtures) dpsNumbers(f, "", false, numbers);
  const seen = new Set<string>();
  for (const v of numbers) {
    for (const s of renderings(v)) {
      if (seen.has(s) || s.length < 4) continue;
      seen.add(s);
      expect(count(html, s), `${label}: absolute DPS "${s}" (from ${v}) is shown`).toBe(allowed.get(s) ?? 0);
    }
  }
  expect(html.match(NUMBER_DPS)?.[0], `${label}: a number followed by DPS`).toBeUndefined();
  expect(html.match(/\d{1,3}(?:,\d{3}){2,}/)?.[0], `${label}: a full number with thousands separators`).toBeUndefined();
}

describe("the guard itself", () => {
  const c = ALL[0];
  it("finds the DPS numbers of the fixtures and flags every way of printing one", () => {
    const nums = dpsNumbers(c.result);
    expect(nums.size).toBeGreaterThan(3);
    const v = c.result.skills.find((x) => x.dps > 1e6)!.dps;
    for (const html of [`<td>${formatNumber(v)}</td>`, `<td title="${formatFull(v)}">x</td>`, "<td>12.5Qa DPS</td>", "<td>1,234,567,890</td>"])
      expect(() => expectNoAbsolute("probe", html, [c.result]), html).toThrow();
    expect(() => expectNoAbsolute("probe", "<td>+12.5% DPS</td>", [c.result])).not.toThrow();
  });
});

describe("Calculator results: Total DPS is the only absolute DPS and appears exactly once", () => {
  it.each(ALL.map((c) => [c.info.id, c] as const))("%s", (id, c) => {
    const html = strip(renderToString(<Results result={c.result} busy={false} stale={false} />));
    const total = formatNumber(c.result.total_dps);
    expect(count(html, total), `${id}: the Total DPS figure`).toBe(1);
    expect(html).toContain("Total DPS updated"); // the live region carries no number
    expectNoAbsolute(id, html, [c.result], new Map([[total, 1]]));
    // the Advanced block holds no DPS entry either (an Attack stat is not DPS)
    const adv = html.split("Advanced: calculation details")[1] ?? "";
    expect(adv).not.toMatch(/(dps|damage uplift)/i);
  });
  it("busy / stale render still shows no second figure", () => {
    const c = ALL[0];
    const html = strip(renderToString(<Results result={c.result} busy stale />));
    expect(count(html, formatNumber(c.result.total_dps))).toBe(1);
  });
});

describe("every other tab shows no absolute DPS", () => {
  it.each(WITH_STAT_VALUES.map((c) => [c.info.id] as const))("%s: Stat values, Companions, Equipment compare, Cubes, Artifacts", async (id) => {
    const c = fixtureFor(id);
    const sens = sensFixture(id);
    const cubes = cubesFixture(id);
    const state = initialState(c.schema, c.defaults["World Boss"], "World Boss");

    const stat = strip(
      renderToString(<StatValuesView result={sens.result} status={IDLE} meta={sens.meta} open={["companions", "summon_time", "cdr"]} onOpenHelp={noop} />),
    );
    expectNoAbsolute(`${id}/stat values`, stat, [sens.result]);
    expect(stat).not.toContain("Total DPS now");

    const comp = strip(
      renderToString(
        <CompanionsView schema={c.schema} state={state} onState={noop} onOpenCalculator={noop} onOpenHelp={noop} supported status={IDLE} result={sens.result} />,
      ),
    );
    expectNoAbsolute(`${id}/companions`, comp, [sens.result]);

    const eq = { current: { attack: 1500, lines: [{ stat: "Damage %", value: 14 }, ...blankEquip().current.lines.slice(1)] }, new: blankEquip().new };
    const equip = strip(
      renderToString(<EquipmentView meta={cubes.meta} metaStatus={IDLE_STATUS} state={eq} onState={noop} status={IDLE_STATUS} onOpenHelp={noop} result={cubes.equipment.result} />),
    );
    expectNoAbsolute(`${id}/equipment`, equip, [cubes.equipment.result]);

    const baseline = cubes.cubes.result.baseline_total;
    const rows = cubes.cubes.result.rows;
    const run: RunState = { ...IDLE_RUN, phase: "done", done: rows.length, total: rows.length, rows, baseline, notes: [], key: "k" };
    const cubeState: CubesState = { [gearKey("head", "Potential")]: { ...blankRow(), rarity: "epic" } };
    const cubesHtml = strip(
      renderToString(
        <CubesView meta={cubes.meta} metaStatus={IDLE_STATUS} state={cubeState} onState={noop} run={run} countText="100" onCountText={noop} cubes={100} sort="ev" onSort={noop} includeBlank={false}
          onIncludeBlank={noop} outdated={false} onCalculate={noop} onCancel={noop} onCsv={noop} />,
      ),
    );
    expectNoAbsolute(`${id}/cubes`, cubesHtml, [cubes.cubes.result]);
    expect(cubesHtml).not.toContain("Total DPS now");

    if (c.schema.artifacts_modelled) {
      const art = c.schema.artifacts as ArtifactSchema;
      const kase = (await import(`./fixtures/${id}.artifacts_case.json`)).default as { result: ComputeResult };
      let t: ArtifactsState = emptyArtifacts(art);
      t = setStar(art, t, "book_of_ancient", 5);
      const panelState: FormState = { ...state, artifacts: t, equippedArtifacts: { "World Boss": normalizeSlots(["alliance_badge", "arwens_glass_shoes", "book_of_ancient", "pigs_ribbon"], art) } };
      const panel = strip(
        renderToString(
          <ArtifactsPanel schema={c.schema} classInfo={c.info} state={panelState} onState={noop} result={kase.result} busy={false} stale={false} onOpenCompanion={noop} onOpenInputs={noop} onOpenHelp={noop} />,
        ),
      );
      expectNoAbsolute(`${id}/artifacts`, panel, [kase.result, sens.result.artifacts]);

      // the potential lines table with the gains of every line and the artifact total
      const pot = cubes.potentials;
      let pt = emptyArtifacts(art);
      for (const [key, p] of Object.entries(pot.request.potentials)) {
        pt = setStar(art, pt, key, p.star ?? 0);
        p.lines.forEach((l, i) => (pt = setLine(art, pt, key, i, { rarity: l.rarity, stat: l.stat })));
      }
      const table = strip(
        renderToString(
          <ArtifactTableView art={art} state={pt} onState={noop} tables={STATIC_POTENTIAL_TABLES} result={pot.result as PotentialsResult} status={none} onOpenCompanion={noop} equipped={[]} />,
        ),
      );
      expectNoAbsolute(`${id}/artifact potentials`, table, [pot.result]);
      expect(table).toMatch(/\+\d+\.\d\d%/); // the artifact's potential total is a %
    }
  });

  it("the cubes CSV exports percentages only (no CurrentValue / EV@n columns)", () => {
    const { meta, cubes } = cubesFixture();
    const lines = cubesCsv(cubes.result.rows, meta.milestones, meta.csv_columns).trim().split("\n");
    const header = lines[0].split(",");
    expect(header).not.toContain("CurrentValue");
    expect(header.filter((h) => /^EV@/.test(h))).toEqual([]);
    expect(header).toContain("CurrentValue%");
    expect(header.filter((h) => /^EV%@/.test(h)).length).toBe(meta.milestones.length);
    for (const l of lines.slice(1)) expect(l.split(",").length, l).toBe(header.length);
    const nums = new Set<number>();
    dpsNumbers(cubes.result, "", false, nums);
    for (const v of nums) expect(lines.join("\n")).not.toContain(String(v));
  });

});
