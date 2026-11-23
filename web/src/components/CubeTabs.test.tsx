import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import { cubesFixture } from "../test/cubesFixture";
import { fixtureFor, NO_STAT_VALUES, WITH_STAT_VALUES } from "../test/fixtures";
import { initialState } from "../lib/schemaForm";
import { IDLE_STATUS } from "../lib/liveRequest";
import { IDLE_RUN, type RunState } from "../lib/cubesRunner";
import { blankEquip, compareEquip } from "../lib/equipment";
import { gearKey, blankRow, type CubesState } from "../lib/cubes";
import { emptyArtifacts, setLine, setStar } from "../lib/artifacts";
import { STATIC_POTENTIAL_TABLES } from "../lib/artifactPotentials";
import type { ArtifactSchema } from "../types";
import type { FormState } from "../types";
import { ArtifactsPanel } from "./ArtifactsPanel";
import { ArtifactTable, ArtifactTableView, POTENTIALS_UNSUPPORTED_TEXT } from "./ArtifactTable";
import { CubesPanel, CubesView, CUBES_UNSUPPORTED_TEXT, GearEditor, noteText } from "./CubesPanel";
import { EquipmentPanel, EquipmentView, EQUIP_UNSUPPORTED_TEXT } from "./EquipmentPanel";

const strip = (h: string) => h.replace(/<!-- -->/g, "");
const fx = cubesFixture();
const meta = fx.meta;
const noop = () => undefined;

const state: CubesState = {
  [gearKey("head", "Potential")]: { rarity: "epic", pity: 12, lines: [{ stat: "Damage %", value: 12 }, { stat: "(none)", value: null }, { stat: "(none)", value: null }] },
  [gearKey("boots", "Bonus Potential")]: { ...blankRow(), rarity: "unique" },
};
const doneRun: RunState = { ...IDLE_RUN, phase: "done", done: 30, total: 30, rows: fx.cubes.result.rows, baseline: fx.cubes.result.baseline_total, notes: ["above"], key: "k" };

function cubesView(over: Partial<Parameters<typeof CubesView>[0]> = {}) {
  return strip(
    renderToString(
      <CubesView meta={meta} metaStatus={IDLE_STATUS} state={state} onState={noop} run={IDLE_RUN} milestone={100} onMilestone={noop} sort="ev" onSort={noop} includeBlank={false}
        onIncludeBlank={noop} outdated={false} onCalculate={noop} onCancel={noop} {...over} />,
    ),
  );
}

describe("Cubes tab", () => {
  it("gear editor: 15 slots x 2 tracks, rarity / pity / 3 lines, pity caps per track, saved values shown", () => {
    const html = strip(renderToString(<GearEditor meta={meta} state={state} onState={noop} />));
    expect((html.match(/data-row="/g) ?? []).length).toBe(30);
    for (const s of meta.slots) expect(html).toContain(`>${s.label}</td>`);
    expect(html).toContain('aria-label="Head Potential rarity"');
    expect(html).toContain('aria-label="Head Potential pity count"');
    for (const i of [1, 2, 3]) expect(html).toContain(`aria-label="Boots Bonus Potential line ${i} stat"`);
    expect(html).toContain("cap 120"); // Epic on Potential
    expect(html).toContain("cap 417"); // Unique on Bonus Potential
    expect(html).toContain("cap 30"); // Normal on Potential
    expect(html).toContain("cap 42"); // Normal on Bonus Potential
    expect(html).toContain('value="12"'); // the line value
    expect(html).toMatch(/<option value="Damage %" selected="">Damage %<\/option>/);
    expect((html.match(/class="cfg"/g) ?? []).length).toBe(2); // the two configured rows are marked
    expect(html).toContain("Companion Summoning Time Increase %"); // offered (the boots roll it)
  });
  it("stat dropdowns list ONLY the stats the slot can roll: no 'Other stats' group; a stored non-rollable stat is ONE flagged option", () => {
    const html = strip(renderToString(<GearEditor meta={meta} state={state} onState={noop} />));
    expect(html).not.toContain("Other stats");
    expect(html).not.toContain("optgroup");
    const sel = (h: string, id: string) => h.match(new RegExp(`<select aria-label="${id}"[\\s\\S]*?</select>`))?.[0] ?? "";
    const head = sel(html, "Head Potential line 2 stat");
    expect((head.match(/<option/g) ?? []).length).toBe(1 + meta.stats_by_slot.head.length);        // (none) + the head's own stats
    expect(head).not.toContain("Companion Summoning Time Increase %");                              // only boots-like slots roll it
    expect(head).not.toContain("not rollable");
    expect(sel(html, "Boots Potential line 1 stat")).toContain("Companion Summoning Time Increase %");
    // an old profile / an import may hold a stat the slot cannot roll: kept as one clearly labelled, flagged option
    const odd: CubesState = { ...state, [gearKey("head", "Potential")]: { ...state[gearKey("head", "Potential")], lines: [{ stat: "Companion Summoning Time Increase %", value: 4 }, { stat: "(none)", value: null }, { stat: "(none)", value: null }] } };
    const h2 = strip(renderToString(<GearEditor meta={meta} state={odd} onState={noop} />));
    const flagged = sel(h2, "Head Potential line 1 stat");
    expect(flagged).toContain("\u26A0 Companion Summoning Time Increase % (not rollable on this slot)");
    expect(flagged).toContain('class="warn"');
    expect(flagged).toContain("kept so nothing is lost");
    expect((flagged.match(/Companion Summoning Time Increase %/g) ?? []).length).toBe(2 + 1);        // value attr + label + the title text
    expect((flagged.match(/<option/g) ?? []).length).toBe(1 + 1 + meta.stats_by_slot.head.length);
    expect(sel(h2, "Head Potential line 2 stat")).not.toContain("Companion Summoning");              // other lines do not offer it
    expect(sel(h2, "Cape Potential line 1 stat")).not.toContain("not rollable");
  });
  it("explains the two pity tracks and the crit-rate cap before any calculation, button counts the rows", () => {
    const html = cubesView();
    expect(html).toContain("Potential and Bonus Potential are separate roll tracks");
    expect(html).toContain("Normal 30 / 42");
    expect(html).toContain("Ring of Cycles");
    expect(html).toContain("Calculate (2 rows)");
    expect(html).not.toContain("Recommendations");
    expect(cubesView({ includeBlank: true })).toContain("Calculate (30 rows)");
    expect(cubesView({ state: {} })).toContain("Fill in at least one row");
    expect(cubesView({ state: {} })).toMatch(/<button[^>]*disabled[^>]*>Calculate \(0 rows\)/);
  });
  it("progress bar while running (with Cancel), done / cancelled / stopped wording", () => {
    const running = cubesView({ run: { ...doneRun, phase: "running", done: 12, total: 30, rows: fx.cubes.result.rows.slice(0, 12) } });
    expect(running).toContain(">Cancel<");
    expect(running).toContain('aria-valuenow="12"');
    expect(running).toContain('aria-valuemax="30"');
    expect(running).toContain("12 / 30 rows");
    expect(running).toContain("width:40%");
    expect(cubesView({ run: { ...doneRun, phase: "cancelled" } })).toContain("(cancelled)");
    expect(cubesView({ run: { ...doneRun, phase: "error", status: { ...IDLE_STATUS, error: "boom" } } })).toContain("(stopped)");
    expect(cubesView({ run: doneRun })).toContain("(done)");
  });
  it("ranked recommendations: every row, the columns, verdict chips with their reason, EV at the chosen milestone", () => {
    const html = cubesView({ run: doneRun, milestone: 200, onCsv: noop });
    expect((html.match(/data-verdict="/g) ?? []).length).toBe(30);
    for (const h of ["Cubes to positive EV", "N for 50%", "N for 75%", "EV @ 200 cubes", "Worth rolling?"]) expect(html).toContain(h);
    expect(html).toMatch(/data-verdict="(yes|maybe|marginal|no)"/);
    expect(html).toContain('class="verdict ');
    expect(html).toContain("Download CSV");
    expect(html).toContain("Total DPS now");
    expect(html).toContain("no cube count up to 1000 has a positive expected gain");
    expect(html).toContain("Some Skill Cooldown Decrease values are above the table");
    expect(html).not.toContain("changed since this was calculated");
    // split into the two roll tracks (Potential, then Bonus Potential), each ranked on its own: best expected gain first
    const blocks = html.split(/<tbody /).slice(1);
    expect(blocks.length).toBe(2);
    expect(blocks[0]).toContain('data-potential-type="Potential"');
    expect(blocks[1]).toContain('data-potential-type="Bonus Potential"');
    for (const [i, type] of ["Potential", "Bonus Potential"].entries()) {
      const first = blocks[i].match(/data-row="([^"]+)" data-verdict/)![1];
      const best = fx.cubes.result.rows.filter((r) => r.potential_type === type).sort((a, b) => (b.milestone_ev_pct["200"] ?? 0) - (a.milestone_ev_pct["200"] ?? 0))[0];
      expect(first).toBe(`${best.slot}|${type}`);
      expect((blocks[i].match(/data-verdict="/g) ?? []).length).toBe(15);
      expect(blocks[i]).not.toContain(type === "Potential" ? "|Bonus Potential" : "|Potential\"");
    }
  });
  it("marks an outdated result and shows API failures (429 / 504 / 422 / 501) without hiding the rows", () => {
    expect(cubesView({ run: doneRun, outdated: true })).toContain("changed since this was calculated");
    const err = cubesView({ run: { ...doneRun, phase: "error", status: { ...IDLE_STATUS, error: "Too many cube requests in a short time (rate limit exceeded, slow down). Wait a little and try again.", fieldErrors: ["gear[1].rarity: bad"] } } });
    expect(err).toContain("Too many cube requests");
    expect(err).toContain("gear[1].rarity: bad");
    expect(err).toContain("Try again");
    expect(err).toContain("Recommendations"); // the rows that arrived stay
    expect(cubesView({ run: { ...IDLE_RUN, phase: "error", status: { ...IDLE_STATUS, unsupported: true } } })).toContain(CUBES_UNSUPPORTED_TEXT);
  });
  it("meta loading / failing", () => {
    const loading = cubesView({ meta: null });
    expect(loading).toContain("Loading the cube tables");
    expect(loading).not.toContain("Current potential lines");
    expect(cubesView({ meta: null, metaStatus: { ...IDLE_STATUS, error: "Cannot reach the API" } })).toContain("Cannot reach the API");
  });
  it("note texts", () => {
    expect(noteText("below")).toContain("below the table");
    expect(noteText("cdr_lines_exceed_inputs:head/Potential")).toContain("head/Potential");
    expect(noteText("something else")).toBe("something else");
  });
  it("the panel says 'not available' for a class without stat values, without any request", () => {
    const html = strip(renderToString(<CubesPanel classId="hero" inputs={{}} supported={false} active meta={null} metaStatus={IDLE_STATUS} state={undefined} onState={noop} />));
    expect(html).toContain(CUBES_UNSUPPORTED_TEXT);
    expect(html).not.toContain("Calculate");
  });
});

describe("Equipment compare tab", () => {
  const eqState = { current: { attack: 1500, lines: [{ stat: "Damage %", value: 14 }, ...blankEquip().current.lines.slice(1)] }, new: blankEquip().new };
  const view = (over: Partial<Parameters<typeof EquipmentView>[0]> = {}) =>
    strip(renderToString(<EquipmentView meta={meta} metaStatus={IDLE_STATUS} state={eqState} onState={noop} result={fx.equipment.result} status={IDLE_STATUS} {...over} />));
  it("two editors with the 21-stat dropdown, the fixed Attack line and 5 lines each", () => {
    const html = view({ result: null });
    for (const side of ["Current equip", "New equip"]) {
      expect(html).toContain(`aria-label="${side} attack"`);
      for (let i = 1; i <= 5; i++) expect(html).toContain(`aria-label="${side} line ${i} stat"`);
    }
    const select = html.match(/<select aria-label="Current equip line 1 stat"[\s\S]*?<\/select>/)![0];
    expect((select.match(/<option /g) ?? []).length).toBe(22); // (none) + 21 stats
    expect(html).toContain("Waiting for the first comparison");
    expect(html).toContain('value="1500"');
  });
  it("the result: delta, verdict, both sides' gains per line", () => {
    const html = view();
    expect(html).toContain("New vs current");
    expect(html).toContain("The new equip is better");
    expect(html).toContain(`+${fx.equipment.result.delta_pct.toFixed(2)}% of Total DPS`);
    expect(html).toContain('aria-label="Current equip result"');
    expect(html).toContain('aria-label="New equip result"');
    const dup = compareEquip({ current: { attack: 0, lines: [{ stat: "Damage %", value: 5 }, { stat: "Damage %", value: 6 }] }, new: { attack: 0, lines: [] } }, fx.equipment.result.rate_by_stat, fx.equipment.result.baseline_total);
    expect(view({ result: { ...fx.equipment.result, ...dup } })).toContain("added to the first Damage % line"); // a second line of the same stat merges into the first
    expect(html).toContain("crit rate is at or above 100%"); // the fixture's sample character is over the cap (152.5%): its Critical Rate line is priced as Critical Damage
    expect(view({ result: { ...fx.equipment.result, crit_priced_as_crit_damage: false } })).not.toContain("crit rate is at or above 100%");
    expect(view({ result: { ...fx.equipment.result, better: "current", delta_pct: -2.5 } })).toContain("Your current equip is better");
  });
  it("states: loading, pending, error with retry, 501", () => {
    expect(view({ result: null, status: { ...IDLE_STATUS, loading: true } })).toContain("Comparing");
    expect(view({ pending: true })).toContain("sens-stale");
    const err = view({ result: null, status: { ...IDLE_STATUS, error: "equipment compare took longer than 30 s; try again." }, onRetry: noop });
    expect(err).toContain("took longer than 30 s");
    expect(err).toContain("Try again");
    expect(view({ status: { ...IDLE_STATUS, unsupported: true } })).toContain(EQUIP_UNSUPPORTED_TEXT);
    expect(view({ meta: null })).toContain("Loading the equipment tables");
  });
  it("the panel says 'not available' without a request for classes without stat values", () => {
    const html = strip(renderToString(<EquipmentPanel classId="hero" inputs={{}} supported={false} active meta={null} metaStatus={IDLE_STATUS} state={undefined} onState={noop} />));
    expect(html).toContain(EQUIP_UNSUPPORTED_TEXT);
  });
});

describe("Artifacts table: potential lines (the old 'Artifact potentials' section is part of the table now)", () => {
  const c = fixtureFor("fp_mage");
  const art = c.schema.artifacts as ArtifactSchema;
  const none = { loading: false, unsupported: false, error: null, fieldErrors: [] };
  const rowHtml = (html: string, key: string) => html.match(new RegExp(`<tr data-artifact="${key}"[\\s\\S]*?</tr>`))?.[0] ?? "";
  const view = (over: Partial<Parameters<typeof ArtifactTableView>[0]> = {}) =>
    strip(
      renderToString(
        <ArtifactTableView art={art} state={setLine(art, setStar(art, emptyArtifacts(art), "book_of_ancient", 5), "pigs_ribbon", 0, { rarity: "Unique", stat: "Defense Penetration %" })}
          onState={noop} tables={meta.artifact_potentials} result={fx.potentials.result} status={none} onOpenCompanion={noop} equipped={["book_of_ancient"]} {...over} />,
      ),
    );
  it("every artifact is a row; line counts follow the rank; gains and totals come from the API answer", () => {
    const html = view();
    for (const a of meta.artifact_potentials.artifacts) {
      const row = rowHtml(html, a.key);
      expect(row, a.key).toBeTruthy();
      expect((row.match(/line \d rarity/g) ?? []).length, a.key).toBe(a.lines);
    }
    expect(view()).not.toContain("Add an artifact");
    const book = rowHtml(html, "book_of_ancient");
    expect(book).toContain(">equipped</span>");           // read-only marker (the equipped set is chosen in the Inputs tab)
  });
  it("locked lines are marked with their unlock star", () => {
    const lockedRows = fx.potentials.result.rows.map((r) => (r.key === "pigs_ribbon" ? { ...r, star: 0, lines: r.lines.map((l) => ({ ...l, active: false })) } : r));
    const html = view({ result: { ...fx.potentials.result, rows: lockedRows } });
    expect(rowHtml(html, "pigs_ribbon")).toContain("locked: star 1");
    expect(rowHtml(html, "pigs_ribbon")).toContain("line-cell inactive");
  });
  it("states: loading, error, 501, no stat values", () => {
    expect(view({ status: { ...none, loading: true }, pending: true })).toContain("Calculating the potential gains...");
    expect(view({ status: { ...none, error: "boom" }, onRetry: noop })).toContain("boom");
    expect(view({ status: { ...none, unsupported: true } })).toContain(POTENTIALS_UNSUPPORTED_TEXT);
    expect(view({ gainsUnsupported: true })).toContain(POTENTIALS_UNSUPPORTED_TEXT);
  });
  it("the container: a class without stat values shows the table (lines editable, no gains) and the note; nothing is requested", () => {
    const x = NO_STAT_VALUES[0];
    const xart = x.schema.artifacts as ArtifactSchema;
    const html = strip(renderToString(<ArtifactTable classId={x.info.id} inputs={{}} supported={false} active meta={null} metaStatus={IDLE_STATUS} art={xart} state={undefined} onState={noop} onOpenCompanion={noop} equipped={[]} />));
    expect(html).toContain(POTENTIALS_UNSUPPORTED_TEXT);
    expect(html.match(/<tr data-artifact="/g)).toHaveLength(36);
    expect(html).toContain("line 1 stat");
  });
  it("without the cube meta the static tables fill the dropdowns (the same data)", () => {
    const html = strip(renderToString(<ArtifactTable classId="fp_mage" inputs={{}} supported active meta={null} metaStatus={IDLE_STATUS} art={art} state={undefined} onState={noop} onOpenCompanion={noop} equipped={[]} />));
    expect(rowHtml(html, "candle")).toContain(`>${STATIC_POTENTIAL_TABLES.stats[0]}</option>`);
  });
});

describe("Artifacts tab: the table needs no cube meta, the potentials are part of it", () => {
  const c = fixtureFor("fp_mage");
  const st: FormState = initialState(c.schema, c.defaults["World Boss"], "World Boss");
  const render = (extra: object) =>
    strip(renderToString(<ArtifactsPanel schema={c.schema} classInfo={c.info} state={st} onState={noop} result={null} busy={false} stale={false} onOpenCompanion={noop} {...extra} />));
  it("with or without the meta the table shows the same rows", () => {
    for (const extra of [{}, { cubesMeta: meta, cubesMetaStatus: IDLE_STATUS }, { cubesMeta: null }]) {
      const html = render(extra);
      expect(html.match(/<tr data-artifact="/g)).toHaveLength(36);
      expect(html).not.toContain("Artifact potentials");
    }
  });
  it("classes without stat values: the table is there, with the 'not available' note and no gains", () => {
    expect(NO_STAT_VALUES.length).toBeGreaterThan(0);
    for (const x of NO_STAT_VALUES) {
      const xs = initialState(x.schema, x.defaults["World Boss"], "World Boss");
      const html = strip(renderToString(<ArtifactsPanel schema={x.schema} classInfo={x.info} state={xs} onState={noop} result={null} busy={false} stale={false} onOpenCompanion={noop} cubesMeta={undefined} />));
      expect(html, x.info.id).toContain(POTENTIALS_UNSUPPORTED_TEXT);
      expect(html.match(/<tr data-artifact="/g), x.info.id).toHaveLength(36);
    }
    // the status flag in classes.json and the cube fixtures the generator dumps agree (a stat-values class has a cubes meta fixture, the others do not)
    const withMeta = Object.keys(import.meta.glob("../fixtures/*.cubes_meta.json")).map((f) => f.replace(/^.*\//, "").replace(".cubes_meta.json", "")).sort();
    expect(withMeta).toEqual(WITH_STAT_VALUES.map((x) => x.info.id).sort());
  });
});
