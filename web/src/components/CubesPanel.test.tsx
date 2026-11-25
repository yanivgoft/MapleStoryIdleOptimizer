import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import { cubesFixture } from "../test/cubesFixture";
import { IDLE_STATUS } from "../lib/liveRequest";
import { IDLE_RUN, type RunState } from "../lib/cubesRunner";
import { blankRow, evPctAt, gearKey, statOptions, type CubeRow, type CubesState } from "../lib/cubes";
import { CubeCountInput, CubeResults, CubesPanel, CubesView, CUBES_UNSUPPORTED_TEXT, GearEditor } from "./CubesPanel";

const strip = (h: string) => h.replace(/<!-- -->/g, "");
const fx = cubesFixture();
const meta = fx.meta;
const noop = () => undefined;
const state: CubesState = { [gearKey("head", "Potential")]: { ...blankRow(), rarity: "epic" } };
const rows = fx.cubes.result.rows;
const baseline = fx.cubes.result.baseline_total;
const doneRun: RunState = { ...IDLE_RUN, phase: "done", done: rows.length, total: rows.length, rows, baseline, notes: [], key: "k" };

const view = (over: Partial<Parameters<typeof CubesView>[0]> = {}) =>
  strip(
    renderToString(
      <CubesView meta={meta} metaStatus={IDLE_STATUS} state={state} onState={noop} run={IDLE_RUN} countText="100" onCountText={noop} cubes={100} sort="ev" onSort={noop}
        includeBlank={false} onIncludeBlank={noop} outdated={false} onCalculate={noop} onCancel={noop} {...over} />,
    ),
  );

/** the order of the data-row keys inside one roll track's tbody */
const order = (html: string, type: string) => {
  const block = html.split("<tbody ").find((b) => b.includes(`data-potential-type="${type}"`)) ?? "";
  return [...block.matchAll(/data-row="([^"]+)"/g)].map((m) => m[1]);
};

describe("Cubes tab: minimal working area, explanations at the bottom", () => {
  it("ONE short intro line; the how-to-read text and the verdict legend are in a collapsed 'About this tab' block AFTER the results", () => {
    const html = view({ run: doneRun });
    expect(html).toContain("Enter the potential lines you have now to see which slots are worth cubing.");
    expect(html).toContain('<details class="about-tab">');
    expect(html).not.toMatch(/<details[^>]*\bopen\b/); // collapsed
    const about = html.indexOf('class="about-tab"');
    expect(about).toBeGreaterThan(html.indexOf("Cube recommendations")); // below the table
    expect(about).toBeGreaterThan(html.indexOf("Calculate ("));
    const before = html.slice(0, about);
    for (const text of ["How to read the table", "Worth rolling?</strong> A plain rule", "separate roll tracks", "Marginal</strong> = positive"]) {
      expect(before).not.toContain(text);
      expect(html.slice(about)).toContain(text);
    }
    expect(html.slice(about)).toContain("About this tab");
    // no banner / legend paragraph above the controls or the table
    expect(html.slice(0, html.indexOf("Current potential lines"))).not.toContain("Nothing is calculated while you type");
  });
  it("no spreadsheet / internals words anywhere in the tab's text (loaded, with results, with notes and a 501)", () => {
    const words = /excel|workbook|spreadsheet|\bsheet\b|potentialcubes|\bengine\b|\bmodel(l?ed)?\b|\bscript\b|golden/i;
    const text = (h: string) => h.replace(/<[^>]+>/g, " ").replace(/&[a-z#0-9]+;/g, " ");
    const htmls = [
      view(),
      view({ run: { ...doneRun, notes: ["above", "below", "cdr_lines_exceed_inputs:head/Potential"] } }),
      view({ run: { ...IDLE_RUN, phase: "error", status: { ...IDLE_STATUS, unsupported: true } }, onOpenHelp: noop }),
      view({ meta: null }),
    ];
    for (const h of htmls) expect(text(h)).not.toMatch(words);
    for (const h of htmls) expect(h).not.toMatch(/(title|aria-label)="[^"]*(excel|workbook|spreadsheet|sheet|engine)/i);
  });
});

describe("Cubes tab: 'Cubes you have' (typed count)", () => {
  it("replaces the preset dropdown by a number input, default 100", () => {
    const html = view();
    expect(html).not.toContain("Cubes to compare");
    expect(html).not.toContain('id="cube-milestone"');
    expect(html).toContain('<label for="cube-count">Cubes you have</label>');
    expect(html).toMatch(/<input id="cube-count" type="text" inputMode="numeric"[^>]*value="100"/);
    expect(html).toContain('aria-invalid="false"');
    expect(html).not.toContain('role="alert"');
  });
  it("an invalid entry (empty, decimal, text, out of range) shows a message tied to the input", () => {
    for (const [text, msg] of [["", "Enter a whole number of cubes from 1 to 1000"], ["0", "from 1 to 1000"], ["1001", "from 1 to 1000"], ["12.5", "Whole cubes only"], ["abc", "from 1 to 1000"]] as const) {
      const html = strip(renderToString(<CubeCountInput text={text} onText={noop} max={1000} />));
      expect(html, text).toContain(msg);
      expect(html, text).toContain('aria-invalid="true"');
      expect(html, text).toContain('aria-describedby="cube-count-err"');
      expect(html, text).toContain('role="alert"');
    }
    const ok = strip(renderToString(<CubeCountInput text="86" onText={noop} max={1000} />));
    expect(ok).toContain('value="86"');
    expect(ok).not.toContain('role="alert"');
    expect(strip(renderToString(<CubeCountInput text="600" onText={noop} max={500} />))).toContain("from 1 to 500");
  });
  it("every count-dependent part of the table uses EXACTLY the typed count (86): header, average gain column, verdict, ranking", () => {
    const html = view({ run: doneRun, cubes: 86, countText: "86" });
    expect(html).toContain("Average gain after 86 cubes");
    expect(html).not.toContain("Average gain after 100 cubes");
    // the % shown for the first row of each track is the curve's value at 86 cubes
    const sample = rows.find((r) => r.potential_type === "Potential")!;
    expect(sample.ev_pct_by_cubes).toHaveLength(1001);
    expect(evPctAt(sample, 86)).toBe(sample.ev_pct_by_cubes![86]);
    const ranked86 = order(html, "Potential");
    const expected86 = rows.filter((r) => r.potential_type === "Potential").sort((a, b) => evPctAt(b, 86) - evPctAt(a, 86) || (a.smallest_n ?? 1e9) - (b.smallest_n ?? 1e9)).map((r) => `${r.slot}|${r.potential_type}`);
    expect(ranked86).toEqual(expected86);
    expect(ranked86).toHaveLength(15);
    // a changed count re-ranks instantly: the same rows, no new request, and 86 differs from 5 (the order of the two is not the same list of percentages)
    const ranked5 = order(view({ run: doneRun, cubes: 5, countText: "5" }), "Potential");
    expect([...ranked5].sort()).toEqual([...ranked86].sort());
    expect(evPctAt(sample, 86)).toBeGreaterThanOrEqual(evPctAt(sample, 5));
  });
  it("two rows whose order flips between 85 and 100 cubes: the table follows the typed count", () => {
    const curveRow = (slot: string, f: (n: number) => number): CubeRow => {
      const c = Array.from({ length: 1001 }, (_v, n) => f(n));
      const ms = meta.milestones;
      return { ...rows[0], slot, potential_type: "Potential", smallest_n: 1, ev_pct_by_cubes: c, milestone_ev_pct: Object.fromEntries(ms.map((n) => [String(n), c[n]])), milestone_ev: Object.fromEntries(ms.map((n) => [String(n), c[n] * 100])) };
    };
    const two = [curveRow("head", (n) => n * 0.01), curveRow("cape", (n) => Math.min(n, 85) * 0.0115)];
    const html = (n: number) => strip(renderToString(<CubeResults rows={two} meta={meta} cubes={n} sort="ev" />));
    expect(order(html(86), "Potential")).toEqual(["cape|Potential", "head|Potential"]);
    expect(order(html(100), "Potential")).toEqual(["head|Potential", "cape|Potential"]);
    expect(html(86)).toContain("+0.978%"); // cape at 86 cubes: 85 x 0.0115
    expect(html(86)).toContain("+0.860%"); // head at 86 cubes
    expect(html(100)).toContain("+1.00%");
    expect(html(86)).not.toContain("8.6K"); // no absolute DPS under the %
  });
  it("falls back to the preset milestones when a row has no per-count curve (old cached rows, mock fixtures)", () => {
    const plain = rows.map(({ ev_pct_by_cubes: _drop, ...r }) => r as CubeRow);
    const html = strip(renderToString(<CubeResults rows={plain} meta={meta} cubes={86} sort="ev" />));
    expect((html.match(/data-verdict="/g) ?? []).length).toBe(30);
    expect(html).toContain("Average gain after 86 cubes");
    const p = plain.find((r) => r.potential_type === "Potential")!;
    expect(evPctAt(p, 86)).toBe(p.milestone_ev_pct["80"]); // the largest preset count not above 86
  });
});

describe("Cubes tab: results table wording and the verdict reason", () => {
  it("'never (already near the best)' for a row whose gain never turns positive", () => {
    const never = rows.map((r, i) => (i === 0 ? { ...r, smallest_n: null } : r));
    const html = strip(renderToString(<CubeResults rows={never} meta={meta} cubes={100} sort="ev" />));
    expect(html).toContain("never (already near the best)");
    expect(html).not.toContain(">never<");
  });
  it("the verdict chip is a focusable button that keeps its short label; its reason is reachable without hovering", () => {
    const html = strip(renderToString(<CubeResults rows={rows} meta={meta} cubes={100} sort="ev" />));
    const chips = [...html.matchAll(/<button type="button" class="verdict (yes|maybe|marginal|no)"[^>]*aria-expanded="false"[^>]*>(Yes|Maybe|Marginal|No)<\/button>/g)];
    expect(chips).toHaveLength(30);
    for (const c of chips) expect(c[1].charAt(0).toUpperCase() + c[1].slice(1)).toBe(c[2]);
    expect(html).toContain("title=\"On average +"); // hover text stays too
    expect(html).not.toContain("verdict-why"); // collapsed until pressed
  });
});

describe("Cubes tab: not available for this class", () => {
  it("ONE line plus a See Help link button (onOpenHelp), also when the API says 501", () => {
    const panel = strip(renderToString(<CubesPanel classId="hero" inputs={{}} supported={false} active meta={null} metaStatus={IDLE_STATUS} state={undefined} onState={noop} onOpenHelp={noop} />));
    expect(panel).toBe(`<p class="empty unavailable" role="status">${CUBES_UNSUPPORTED_TEXT} <button type="button" class="link">See Help</button></p>`);
    expect(CUBES_UNSUPPORTED_TEXT).toBe("Not available for this class yet.");
    expect(panel).not.toContain("<p>"); // no second paragraph
    const noHelp = strip(renderToString(<CubesPanel classId="hero" inputs={{}} supported={false} active meta={null} metaStatus={IDLE_STATUS} state={undefined} onState={noop} />));
    expect(noHelp).toContain(CUBES_UNSUPPORTED_TEXT);
    expect(noHelp).not.toContain("See Help"); // the prop is optional
    const live = view({ run: { ...IDLE_RUN, phase: "error", status: { ...IDLE_STATUS, unsupported: true } }, onOpenHelp: noop });
    expect(live).toContain(CUBES_UNSUPPORTED_TEXT);
    expect(live).toContain("See Help");
  });
});

describe("Cubes tab: line values are a dropdown of the values the game rolls", () => {
  const line = (stat: string, value: number | null) => ({ stat, value });
  const gear = (slot: string, rarity: string, lines: { stat: string; value: number | null }[]): CubesState => ({
    [gearKey(slot, "Potential")]: { rarity, pity: null, lines: [...lines, line("(none)", null), line("(none)", null), line("(none)", null)].slice(0, 3) },
  });
  const editor = (st: CubesState) => strip(renderToString(<GearEditor meta={meta} state={st} onState={noop} />));
  const sel = (h: string, id: string) => h.match(new RegExp(`<select aria-label="${id}"[\\s\\S]*?</select>`))?.[0] ?? "";
  const labels = (h: string) => [...h.matchAll(/<option[^>]*>([^<]*)<\/option>/g)].map((m) => m[1]);
  const fixed = (h: string, id: string) => h.match(new RegExp(`<span class="valfix[^"]*" data-value-for="${id}">([^<]*)</span>`))?.[1];

  it("a blank option first, then the plain numbers prime first (no '(prime)' / '(normal)' text); the stored value is the selected one", () => {
    const h = editor(gear("head", "legendary", [line("Critical Rate %", 12), line("Critical Rate %", 9), line("Damage %", 25)]));
    const v2 = sel(h, "Head Potential line 2 value");
    expect(labels(v2)).toEqual(["", "12", "9"]);
    expect(v2).toMatch(/<option value="9" selected="">9<\/option>/);
    expect(labels(sel(h, "Head Potential line 3 value"))).toEqual(["", "25", "18"]);
    expect(h).not.toMatch(/\((prime|normal|custom)\)/);
  });
  it("a line with exactly ONE allowed value shows it as plain text: no dropdown, no input", () => {
    const h = editor(gear("head", "legendary", [line("Critical Rate %", 12), line("Critical Rate %", 9)]));
    expect(fixed(h, "Head Potential line 1 value")).toBe("12");
    expect(sel(h, "Head Potential line 1 value")).toBe("");
    expect(h).not.toMatch(/<input[^>]*aria-label="Head Potential line 1 value"/);
    // shown even when the stored value is still blank (the state gets it on load / on choosing the stat)
    expect(fixed(editor(gear("head", "legendary", [line("Critical Rate %", null)])), "Head Potential line 1 value")).toBe("12");
  });
  it("blank until chosen: no stat = disabled input; a stat with several values shows the empty option selected", () => {
    const h = editor(gear("head", "legendary", [line("Critical Rate %", 12), line("Critical Rate %", null)]));
    const v2 = sel(h, "Head Potential line 2 value");
    expect(v2).toContain('<option value="" selected=""></option>');
    expect(v2).not.toMatch(/<option value="12" selected/);
    expect(sel(h, "Head Potential line 3 value")).toBe("");                                          // (none): a disabled box, not a dropdown
    expect(h).toMatch(/<input[^>]*aria-label="Head Potential line 3 value"[^>]*disabled|<input[^>]*disabled[^>]*aria-label="Head Potential line 3 value"/);
  });
  it("NO custom option anywhere: a stored value that is not rollable is not offered or shown as a choice", () => {
    for (const rarity of meta.rarities.map((r) => r.key)) {
      for (const slot of meta.slots.map((s) => s.key)) {
        const h = editor(gear(slot, rarity, statOptions(meta, slot).slice(0, 3).map((s) => line(s, 12.5))));
        expect(h).not.toMatch(/custom/i);
        expect(h).not.toContain('<option value="12.5"');
      }
    }
    const h = editor(gear("head", "legendary", [line("Critical Rate %", 12), line("Critical Rate %", 12.5)]));
    expect(labels(sel(h, "Head Potential line 2 value"))).toEqual(["", "12", "9"]);                 // the stored 12.5 is not an option
    expect(sel(h, "Head Potential line 2 value")).not.toContain("selected");
  });
  it("the options follow the row's rarity, the slot and the line position", () => {
    const hat = editor(gear("head", "mystic", [line("Skill Cooldown Decrease (seconds)", 2), line("Skill Cooldown Decrease (seconds)", 1.5)]));
    expect(fixed(hat, "Head Potential line 1 value")).toBe("2");
    expect(labels(sel(hat, "Head Potential line 2 value"))).toEqual(["", "2", "1.5"]);
    const belt = editor(gear("belt", "unique", [line("Buff Duration Increase %", 8)]));
    expect(fixed(belt, "Belt Potential line 1 value")).toBe("8");
  });
  it("a stat that has no roll entry here (not rollable on the slot) stays flagged with NO value input: a stored value is only shown as text", () => {
    const h = editor(gear("boots", "epic", [line("Skill Cooldown Decrease (seconds)", 0.5)]));
    expect(sel(h, "Boots Potential line 1 stat")).toContain("not rollable on this slot");
    expect(h).not.toMatch(/<input[^>]*aria-label="Boots Potential line 1 value"/);
    expect(sel(h, "Boots Potential line 1 value")).toBe("");
    expect(fixed(h, "Boots Potential line 1 value")).toBe("0.5");
    expect(fixed(editor(gear("boots", "epic", [line("Skill Cooldown Decrease (seconds)", null)])), "Boots Potential line 1 value")).toBe("");
  });
});

/** the elements of a React element tree (host elements only, no component is rendered) matching a predicate */
function findAll(node: unknown, pred: (props: Record<string, unknown>, type: unknown) => boolean, out: { props: Record<string, any> }[] = []) {
  if (Array.isArray(node)) node.forEach((n) => findAll(n, pred, out));
  else if (node && typeof node === "object" && "props" in node) {
    const el = node as { type: unknown; props: Record<string, any> };
    if (pred(el.props, el.type)) out.push(el);
    findAll(el.props.children, pred, out);
  }
  return out;
}

describe("Cubes tab: changing a row's rarity deletes its three lines", () => {
  it("rarity select -> onState gets that row with rarity set and all three lines (none) / blank; the other rows and the pity stay", () => {
    const k = gearKey("head", "Potential");
    const other = gearKey("belt", "Potential");
    const full = (rarity: string): CubesState => ({
      [k]: { rarity, pity: 9, lines: [{ stat: "Critical Rate %", value: 12 }, { stat: "Damage %", value: 18 }, { stat: "Str %", value: 9 }] },
      [other]: { rarity: "epic", pity: null, lines: [{ stat: "Damage %", value: 6 }, emptyLineOf(), emptyLineOf()] },
    });
    const seen: CubesState[] = [];
    const tree = GearEditor({ meta, state: full("legendary"), onState: (s) => seen.push(s) });
    const [select] = findAll(tree, (p) => p["aria-label"] === "Head Potential rarity");
    select.props.onChange({ target: { value: "mystic" } });
    expect(seen).toHaveLength(1);
    expect(seen[0][k]).toEqual({ rarity: "mystic", pity: 9, lines: [emptyLineOf(), emptyLineOf(), emptyLineOf()] });
    expect(seen[0][other]).toEqual(full("legendary")[other]);
  });
});

function emptyLineOf() {
  return { stat: "(none)", value: null };
}

describe("Cubes tab: one block per equipment slot", () => {
  it("each slot is its own tbody (Potential row first, then Bonus Potential) and the slot name is on the block's first row", () => {
    const html = strip(renderToString(<GearEditor meta={meta} state={state} onState={noop} />));
    const blocks = html.split(/<tbody /).slice(1);
    expect(blocks).toHaveLength(meta.slots.length);
    meta.slots.forEach((s, i) => {
      expect(blocks[i]).toContain(`class="slot-block" data-slot="${s.key}"`);
      const rows = [...blocks[i].matchAll(/<tr data-row="([^"]+)"/g)].map((m) => m[1]);
      expect(rows).toEqual([`${s.key}|Potential`, `${s.key}|Bonus Potential`]);
      expect(blocks[i].indexOf(`>${s.label}</td>`)).toBeLessThan(blocks[i].indexOf(`data-row="${s.key}|Bonus Potential"`));
    });
  });
});
