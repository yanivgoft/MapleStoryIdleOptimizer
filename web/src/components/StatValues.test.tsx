import { describe, expect, it, vi, afterEach } from "vitest";
import { renderToString } from "react-dom/server";
import { sensFixture } from "../test/sensFixture";
import { NO_STAT_VALUES, WITH_STAT_VALUES } from "../test/fixtures";
import { formatNumber } from "../lib/format";
import { IDLE } from "../lib/sensitivityLoader";
import { EquipRanking } from "./EquipRanking";
import { StatTable } from "./StatTable";
import { CdrTable, CompanionTable, SummonTable } from "./SensitivitySections";
import { StatValuesView, UNSUPPORTED_TEXT } from "./StatValues";

const strip = (h: string) => h.replace(/<!-- -->/g, "");
const fx = sensFixture();

describe("stat table", () => {
  const html = strip(renderToString(<StatTable rows={fx.result.stats!.rows} meta={fx.meta} />));
  it("renders all 27 stats with the columns, best value first", () => {
    expect((html.match(/data-stat=/g) ?? []).length).toBe(27);
    for (const h of ["Units per +1% DPS", "DPS gained per step", "% gained per step", "Relative value", "After one step", "Current"]) expect(html).toContain(h);
    expect((html.match(/<th scope="col"/g) ?? []).length).toBe(9);
    expect(html).not.toContain(">Notes<");
    const keys = [...html.matchAll(/data-stat="([a-z_0-9]+)"/g)].map((m) => m[1]);
    const rows = fx.result.stats!.rows;
    const units = keys.map((k) => rows.find((r) => r.key === k)!.units_per_1pct);
    const real = units.filter((u): u is number => u !== null && u > 0);
    expect([...real].sort((a, b) => a - b)).toEqual(real); // ascending
    expect(units.slice(real.length).every((u) => u === null || u <= 0)).toBe(true); // n/a rows last
    expect(html).toContain("n/a");
  });
  it("shows a compact step per row and NO prose notes (no semantics, no timing chips, no tooltips with sentences)", () => {
    expect(html).toContain('class="step">+1%<');
    expect(html).toContain('class="step">+1<');
    expect(html).toContain("sens-bar");
    for (const bad of ["diminishing", "factor 150", "factor 100", "combined by", "percentage point", "DR 150", "flat-Attack channel", "timing re-run", "summon time re-searched", "re-runs the timeline", "Notes"]) expect(html, bad).not.toContain(bad);
    expect(html).not.toMatch(/<tr[^>]* title=/);
    expect(html).not.toMatch(/<th[^>]* title=/);
    expect(html).not.toContain("class=\"info\"");
  });
});

describe("equip ranking", () => {
  const rows = fx.result.artifacts!.rows;
  const html = strip(renderToString(<EquipRanking rows={rows} />));
  it("ranked rows first, no-effect ones greyed with a bare tag (no reason text), locked ones marked", () => {
    expect((html.match(/data-group="ranked"/g) ?? []).length).toBe(rows.filter((r) => r.unlocked && !r.no_dps_effect).length);
    expect(html).toContain('data-group="no_effect"');
    expect(html).toContain('<span class="sub">no DPS effect</span>');
    expect(html).not.toMatch(/no DPS effect:|not modelled|not used by the DPS model/);
    expect(html).not.toMatch(/<tr[^>]* title=/);
    expect(html).toContain('data-group="locked"');
    expect(html.indexOf('data-group="ranked"')).toBeLessThan(html.indexOf('data-group="no_effect"'));
    expect(html.indexOf('data-group="no_effect"')).toBeLessThan(html.indexOf('data-group="locked"'));
    const best = rows.find((r) => r.rank_position === 1)!;
    expect(html).toContain(best.label);
  });
  it("marks equipped artifacts, honours limit / showLocked", () => {
    const eq = rows.map((r, i) => (i === 0 ? { ...r, equipped: true } : r));
    expect(strip(renderToString(<EquipRanking rows={eq} />))).toContain("equipped");
    expect((strip(renderToString(<EquipRanking rows={rows} limit={3} />)).match(/<tr /g) ?? []).length).toBe(3);
    expect(strip(renderToString(<EquipRanking rows={rows} showLocked={false} />))).not.toContain('data-group="locked"');
  });
});

describe("sections", () => {
  it("companion comparison: 16 rows, chosen one marked, best first", () => {
    const html = strip(renderToString(<CompanionTable part={fx.result.companions!} />));
    expect((html.match(/data-companion=/g) ?? []).length).toBe(16);
    expect(html).toContain("chosen");
    const first = fx.result.companions!.rows.find((r) => r.rank_position === 1)!;
    expect(html.indexOf("data-companion=")).toBe(html.indexOf(`data-companion="${first.name}"`));
  });
  it("summoning time and CDR tables", () => {
    const st = strip(renderToString(<SummonTable part={fx.result.summon_time!} />));
    expect((st.match(/<tr/g) ?? []).length).toBe(fx.result.summon_time!.rows.length + 1);
    expect(st).toContain(formatNumber(fx.result.summon_time!.rows[1].companion_dps));
    const cdr = strip(renderToString(<CdrTable part={fx.result.cdr!} />));
    expect((cdr.match(/<tr/g) ?? []).length).toBe(11);
    expect(cdr).toContain("5");
  });
});

describe("tab view states", () => {
  const view = (over: Partial<Parameters<typeof StatValuesView>[0]> = {}) =>
    strip(renderToString(<StatValuesView result={fx.result} status={IDLE} meta={fx.meta} open={[]} {...over} />));
  it("full result: header total, stat table, artifact ranking, three collapsed sections", () => {
    const html = view();
    expect(html).toContain(formatNumber(fx.result.baseline_total));
    expect(html).toContain("Units per +1% DPS");
    expect(html).toContain("Artifact ranking (DPS gain if equipped)");
    expect(html).toContain("About this tab");
    expect(html).toContain("Sort by");
    for (const t of ["Companion comparison", "Companion summoning time potential", "Cooldown decrease milestones"]) expect(html).toContain(t);
    expect(html).not.toMatch(/<details[^>]* open/);
    expect(html).not.toContain('class="hint"');                               // no per-section prose in the working area
    const working = html.split('class="about-tab"')[0];
    expect(working).not.toMatch(/diminishing|factor 1[05]0|combined by|Every companion at your companion level|step function/);
    expect(view({ open: ["cdr"] })).toMatch(/<details[^>]* open/);
  });
  it("loading shows a spinner and a skeleton when nothing is loaded yet", () => {
    const html = view({ result: null, status: { ...IDLE, loading: true } });
    expect(html).toContain("spinner");
    expect(html).toContain("skeleton");
    expect(html).toContain('aria-busy="true"');
  });
  it("stale result is dimmed while recomputing", () => {
    expect(view({ stale: true, status: { ...IDLE, loading: true } })).toContain("sens-stale");
    expect(view({ pending: true })).toContain("Waiting for the inputs to settle");
  });
  it("501 -> friendly message; 422 -> field list; generic error with retry", () => {
    expect(view({ result: null, status: { ...IDLE, unsupported: true } })).toContain(UNSUPPORTED_TEXT);
    const e422 = view({ result: null, status: { ...IDLE, error: "Some inputs are invalid", fieldErrors: ["level: must be between 1 and 300"] } });
    expect(e422).toContain("level: must be between 1 and 300");
    expect(e422).toContain('role="alert"');
    expect(view({ result: null, status: { ...IDLE, error: "boom" }, onRetry: () => undefined })).toContain("Try again");
  });
  it("a partial result (stats only) shows the placeholders of the rest", () => {
    const html = view({ result: { ...fx.result, artifacts: undefined, companions: undefined, summon_time: undefined, cdr: undefined } });
    expect(html).toContain("Loading the artifact ranking");
    expect(html).toContain("Not loaded yet");
  });
});

describe("mock mode serves the fixture", () => {
  afterEach(() => vi.unstubAllEnvs());
  async function mockApi() {
    vi.stubEnv("VITE_MOCK", "1");
    vi.resetModules();
    return await import("../api");
  }
  it("fp_mage: parts filter, meta; every stat-values class has its fixture, the others answer 501", async () => {
    const { api, ApiError } = await mockApi();
    const all = await api.sensitivity("fp_mage", {});
    expect(all.stats!.rows).toHaveLength(27);
    const some = await api.sensitivity("fp_mage", {}, ["cdr"]);
    expect(some.cdr).toBeDefined();
    expect(some.stats).toBeUndefined();
    expect((await api.sensitivityMeta("fp_mage")).stats).toHaveLength(27);
    expect(WITH_STAT_VALUES.length).toBeGreaterThan(0);
    expect(NO_STAT_VALUES.length).toBeGreaterThan(0);
    for (const c of WITH_STAT_VALUES) {       // classes.json says stat values are modelled -> the generator dumped both sensitivity fixtures
      const r = await api.sensitivity(c.info.id, {}, ["stats"]);
      expect(r.stats!.rows.length, c.info.id).toBeGreaterThan(0);
      expect((await api.sensitivityMeta(c.info.id)).stats.length, c.info.id).toBe(r.stats!.rows.length);
    }
    for (const c of NO_STAT_VALUES) {
      await expect(api.sensitivity(c.info.id, {}, ["stats"])).rejects.toBeInstanceOf(ApiError);
      await expect(api.sensitivity(c.info.id, {}, ["stats"])).rejects.toMatchObject({ status: 501 });
      await expect(api.sensitivityMeta(c.info.id)).rejects.toMatchObject({ status: 501 });
    }
  });
});
