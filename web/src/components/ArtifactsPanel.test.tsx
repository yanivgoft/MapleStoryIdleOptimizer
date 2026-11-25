import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import { initialState, switchContentType } from "../lib/schemaForm";
import { blankLine, emptyArtifacts, normalizeSlots, setLine, setStar } from "../lib/artifacts";
import { STATIC_POTENTIAL_TABLES, potentialsRequest, type PotentialsResult } from "../lib/artifactPotentials";
import { ALL, fixtureFor } from "../test/fixtures";
import type { ArtifactSchema, ArtifactsState, ComputeResult, FormState } from "../types";
import { ArtifactsPanel } from "./ArtifactsPanel";
import { ArtifactTableView } from "./ArtifactTable";

const strip = (h: string) => h.replace(/<!-- -->/g, "");
const MODELLED = ALL.filter((c) => c.schema.artifacts_modelled);
const UNMODELLED = ALL.filter((c) => !c.schema.artifacts_modelled);

/** the fixture case (real engine output): Alliance Badge 4, Arwen's Glass Shoes 2, Book of Ancient 5, Pig's Ribbon Not Unlocked equipped */
const CASE_KEYS = ["alliance_badge", "arwens_glass_shoes", "book_of_ancient", "pigs_ribbon"];
function caseTable(art: ArtifactSchema): ArtifactsState {
  let t = emptyArtifacts(art);
  for (const [k, star] of [["alliance_badge", 4], ["arwens_glass_shoes", 2], ["book_of_ancient", 5], ["pigs_ribbon", "Not Unlocked"]] as const) t = setStar(art, t, k, star);
  return t;
}

/** ``equipped`` = the artifact ids in the slots of the content type the panel shows (World Boss); ``others`` = slots of other content types */
async function render(id: string, artifacts: (art: ArtifactSchema) => ArtifactsState, withResult = true, equipped: string[] = [], others: Record<string, string[]> = {}) {
  const c = fixtureFor(id);
  const art = c.schema.artifacts as ArtifactSchema | undefined;
  const state: FormState = {
    ...initialState(c.schema, c.defaults["World Boss"], "World Boss"),
    artifacts: art ? artifacts(art) : {},
    equippedArtifacts: art ? { ...Object.fromEntries(Object.entries(others).map(([ct, k]) => [ct, normalizeSlots(k, art)])), "World Boss": normalizeSlots(equipped, art) } : {},
  };
  const kase = art ? ((await import(`../fixtures/${id}.artifacts_case.json`)).default as { result: ComputeResult }) : null;
  return strip(
    renderToString(
      <ArtifactsPanel schema={c.schema} classInfo={c.info} state={state} onState={() => undefined} result={withResult && kase ? kase.result : null} busy={false} stale={false} onOpenCompanion={() => undefined} />,
    ),
  );
}

const rowHtml = (html: string, key: string) => html.match(new RegExp(`<tr data-artifact="${key}"[\\s\\S]*?</tr>`))?.[0] ?? "";

describe("Artifacts tab render (server-side): one table", () => {
  it.each(MODELLED.map((c) => [c.info.id] as const))("%s: 36 rows by rank, badges only (no effect text), equip count, breakdown, ranking section", async (id) => {
    const html = await render(id, caseTable, true, CASE_KEYS);
    expect(html).toContain('aria-label="Artifacts table"');
    expect(html.match(/<tr data-artifact="/g)).toHaveLength(36);
    for (const rank of ["Epic", "Unique", "Legendary"]) expect(html).toContain(`<th scope="rowgroup" colSpan="7">${rank}</th>`.replace("colSpan", "colSpan"));
    expect(html).toContain("4 / 5 equipped in World Boss");
    // no per-artifact effect description, no reason text, no caption above the table
    for (const bad of ["+18% Attack", "+28% Companion Summoning Time Increase", "stat not used for damage", "No DPS effect:", "Equip effect not applied", "Set each artifact", "Equipped artifacts</strong>", "acts as star 0", "Not unlocked acts as star 0 when"]) expect(html, bad).not.toContain(bad);
    expect(html).not.toMatch(/class="note art-fx"/);
    expect(html).not.toContain("reference only: already in your stats");     // the breakdown carries no per-row prose either
    expect(html).toContain("Baked into your stats");
    expect(html).toContain("Companion effect");
    expect(html).toContain("go to Companion");
    expect(html).toContain("No DPS effect");
    expect(html).toContain("What the equipped artifacts do in this calculation");
    expect(html).toContain("Total DPS with these artifacts vs. none");
    expect(html).toContain("calculating...");                                // baseline compute has not run (server render)
    expect(html).toContain('aria-label="Artifact ranking (DPS gain if equipped)"');
    // the old slots design is gone
    expect(html).not.toContain("art-slot-");
    expect(html).not.toContain("Add an artifact");
    expect(html).not.toContain("pot-card");
  });
  it("columns: Artifact, Star level, Equipped, Line 1-3, Potential total; sticky-header table in its own scroll box", async () => {
    const html = await render("fp_mage", caseTable, false, CASE_KEYS);
    for (const h of ["Artifact", "Star level", "Equipped", "Line 1", "Line 2", "Line 3 (Legendary)", "Potential total"]) expect(html).toContain(h);
    expect(html).not.toMatch(/<(th|select)[^>]* title=/);                    // no explanatory tooltips on the headers / star selects
    expect(html).toContain('class="art-table-wrap"');
    expect(html).toContain('type="search"');
    expect(html).toContain('placeholder="filter by name"');
    expect(html).toContain("Show only unlocked / equipped");
  });
  it("star select shows 'Not unlocked' + Star 0-5 and the engine default by rank; equipped rows (of the current content type) are marked", async () => {
    const html = await render("fp_mage", caseTable, false, CASE_KEYS);
    const pig = rowHtml(html, "pigs_ribbon");
    expect(pig).toContain('<option value="Not Unlocked" selected="">Not unlocked</option>');
    expect(pig).not.toContain("acts as star 0");
    expect(pig).toContain('class="equipped');
    expect(rowHtml(html, "charm_of_the_undead")).toContain('<option value="5" selected="">Star 5 (max)</option>');         // Epic default
    expect(rowHtml(html, "hexagon_necklace")).toContain('<option value="3" selected="">Star 3</option>');                 // Unique default
    expect(rowHtml(html, "candle")).toContain('<option value="Not Unlocked" selected="">Not unlocked</option>');          // Legendary default
  });
  it("Line 3 exists for Legendary artifacts only; Epic / Unique rows show a dash", async () => {
    const html = await render("fp_mage", () => emptyArtifacts(fixtureFor("fp_mage").schema.artifacts!), false);
    expect(rowHtml(html, "charm_of_the_undead")).toContain('class="line-na"');
    expect(rowHtml(html, "charm_of_the_undead")).not.toContain("line 3 rarity");
    expect(rowHtml(html, "hexagon_necklace")).toContain('class="line-na"');
    expect(rowHtml(html, "candle")).toContain("Candle line 3 rarity");
    expect(rowHtml(html, "candle")).not.toContain('class="line-na"');
    expect(html.match(/line 3 stat/g)).toHaveLength(art36Legendary(fixtureFor("fp_mage").schema.artifacts!));
  });
  it("the Equipped column is read-only: a marker for the current content type's artifacts, no checkbox, no hint text", async () => {
    const keys = ["alliance_badge", "candle", "horn_flute", "secret_map", "flaming_lava"];
    const html = await render("hero", emptyArtifacts, false, keys);
    expect(html).toContain("5 / 5 equipped in World Boss");
    expect(html).not.toContain('aria-label="Equip ');
    expect(html).not.toMatch(/<td class="equip-cell"><input/);
    expect(html.match(/<span class="chip ok">equipped<\/span>/g)).toHaveLength(5);
    expect(rowHtml(html, "candle")).toContain(">equipped</span>");
    expect(rowHtml(html, "chalice")).not.toContain(">equipped</span>");
    // other content types' slots do not show here; only the current one counts
    const other = await render("hero", emptyArtifacts, false, ["candle"], { "Chapter Boss": ["chalice", "horn_flute"] });
    expect(other).toContain("1 / 5 equipped in World Boss");
    expect(rowHtml(other, "chalice")).not.toContain(">equipped</span>");
  });
  it("switching the content type changes which rows are marked and the count", async () => {
    const c = fixtureFor("fp_mage");
    const art = c.schema.artifacts as ArtifactSchema;
    const base: FormState = { ...initialState(c.schema, c.defaults["World Boss"], "World Boss"), equippedArtifacts: { "World Boss": normalizeSlots(["candle"], art), "Chapter Boss": normalizeSlots(["chalice", "horn_flute"], art) } };
    const html = (st: FormState) => strip(renderToString(<ArtifactsPanel schema={c.schema} classInfo={c.info} state={st} onState={() => undefined} result={null} busy={false} stale={false} onOpenCompanion={() => undefined} />));
    const wb = html(base);
    expect(wb).toContain("1 / 5 equipped in World Boss");
    expect(rowHtml(wb, "candle")).toContain(">equipped</span>");
    const cb = html(switchContentType(base, c.schema, "Chapter Boss", c.defaults["Chapter Boss"]));
    expect(cb).toContain("2 / 5 equipped in Chapter Boss");
    expect(rowHtml(cb, "candle")).not.toContain(">equipped</span>");
    expect(rowHtml(cb, "chalice")).toContain(">equipped</span>");
  });
  it("equipped but no result yet: no breakdown, a waiting note; nothing equipped: no breakdown at all", async () => {
    const html = await render("fp_mage", caseTable, false, CASE_KEYS);
    expect(html).not.toContain("What the equipped artifacts do");
    expect(html).toContain("appears after the next calculation");
    const none = await render("fp_mage", emptyArtifacts, false);
    expect(none).toContain("0 / 5 equipped");
    expect(none).not.toContain("What the equipped artifacts do");
    expect(none).not.toContain("appears after the next calculation");
  });
  it.each(UNMODELLED.map((c) => [c.info.id] as const))("%s: friendly 'not available' panel instead of the table", async (id) => {
    const html = await render(id, () => ({}), false);
    expect(html).toContain(`Artifacts are not available for ${fixtureFor(id).schema.name} yet`);
    expect(html).not.toContain("art-table");
    expect(html).not.toContain("Artifact ranking");
  });
});

const art36Legendary = (art: ArtifactSchema) => art.artifacts.filter((a) => a.rank === "Legendary").length;

describe("the table view: filter, potential lines, gains", () => {
  const fp = fixtureFor("fp_mage");
  const art = fp.schema.artifacts as ArtifactSchema;
  const none = { loading: false, unsupported: false, error: null, fieldErrors: [] };
  const view = (state: ArtifactsState, extra: Partial<Parameters<typeof ArtifactTableView>[0]> = {}) =>
    strip(renderToString(<ArtifactTableView art={art} state={state} onState={() => undefined} tables={STATIC_POTENTIAL_TABLES} result={null} status={none} onOpenCompanion={() => undefined} equipped={[]} {...extra} />));

  it("filter by name: only matching rows, a note when nothing matches", () => {
    const html = view(emptyArtifacts(art), { initialText: "badge" });
    expect(html.match(/<tr data-artifact="/g)).toHaveLength(1);
    expect(html).toContain('data-artifact="alliance_badge"');
    expect(html).toContain('value="badge"');
    expect(html).not.toContain('<th scope="rowgroup" colSpan="7">Epic</th>');
    expect(view(emptyArtifacts(art), { initialText: "zzz" })).toContain("No artifact matches &quot;zzz&quot;");
  });
  it("show only unlocked / equipped: Epic + Unique defaults are unlocked, locked Legendary ones are hidden unless equipped", () => {
    const html = view(emptyArtifacts(art), { initialOnlyActive: true, equipped: ["candle"] });
    expect(html.match(/<tr data-artifact="/g)).toHaveLength(4 + 9 + 1);
    expect(html).toContain('data-artifact="candle"');
    expect(html).not.toContain('data-artifact="chalice"');
    expect(html).toContain('id="art-only-active" type="checkbox" checked=""');
  });
  it("lines: rarity + stat dropdowns with the artifact stats only; locked lines are greyed with their unlock star", () => {
    let t = setStar(art, emptyArtifacts(art), "alliance_badge", 1);
    t = setLine(art, t, "alliance_badge", 0, { rarity: "Legendary", stat: "Damage %" });
    t = setLine(art, t, "alliance_badge", 1, { rarity: "Epic", stat: "Critical Rate %" });
    const html = view(t);
    const row = rowHtml(html, "alliance_badge");
    expect(row).toContain("Alliance Badge line 1 rarity");
    for (const r of STATIC_POTENTIAL_TABLES.rarities) expect(row).toContain(`>${r}</option>`);
    const statSelect = row.match(/<select aria-label="Alliance Badge line 1 stat"[\s\S]*?<\/select>/)![0];
    expect(statSelect.match(/<option/g)).toHaveLength(1 + STATIC_POTENTIAL_TABLES.stats.length);        // (none) + the 12 artifact stats, no "other stats" group
    expect(statSelect).not.toContain('optgroup label="Other"');                                         // grouped by kind of stat (lib/statGroups.ts), nothing left over
    expect(statSelect.match(/<optgroup label="([^"]+)"/g)!.map((g) => g.slice(17, -1))).toEqual(["Main stat %", "Critical", "Damage", "Attack and accuracy", "Defense and health"]);
    expect(row).toContain("+14");                                               // Damage % at Legendary (the engine's value table)
    expect(row).toContain("(locked: star 2)");                                  // line 2 needs star 2, the artifact is at star 1
    expect(row).not.toContain("(locked: star 1)");
  });
  it("a stored stat the artifacts cannot roll stays selectable as ONE flagged option and is marked as not valued", () => {
    const t = setLine(art, emptyArtifacts(art), "charm_of_the_undead", 0, { rarity: "Epic", stat: "Final Damage %" });
    const html = view(t);
    const sel = rowHtml(html, "charm_of_the_undead").match(/<select aria-label="Charm of the Undead line 1 stat"[\s\S]*?<\/select>/)![0];
    expect(sel).toContain("not rollable on artifacts");
    expect(sel.match(/<option/g)).toHaveLength(1 + 1 + STATIC_POTENTIAL_TABLES.stats.length);      // (none) + the flagged stored stat + the 12 artifact stats
    expect(sel.match(/>⚠ Final Damage % \(not rollable on artifacts\)</g)).toHaveLength(1);
    expect(sel).toContain('class="warn"');
    expect(rowHtml(html, "charm_of_the_undead")).toContain("not valued");
    // another artifact's select does not offer it
    expect(rowHtml(html, "pigs_ribbon")).not.toContain("Final Damage %");
  });
  it("gains: per-line DPS and the artifact's total from the API answer; a class without stat values shows no gains and says so", () => {
    let t = setStar(art, emptyArtifacts(art), "alliance_badge", 5);
    t = setLine(art, t, "alliance_badge", 0, { rarity: "Legendary", stat: "Damage %" });
    const result: PotentialsResult = {
      class_id: "fp_mage", baseline_total: 1000,
      rows: [{ key: "alliance_badge", label: "Alliance Badge", rank: "Legendary", equipped: false, star: 5, total: 123, lines: [{ rarity: "Legendary", stat: "Damage %", active: true, gain: 123 }, { rarity: "Rare", stat: "(none)", active: true, gain: 0 }, { rarity: "Rare", stat: "(none)", active: true, gain: 0 }] }],
    };
    const html = view(t, { result });
    const row = rowHtml(html, "alliance_badge");
    expect(row).toContain("= 123 DPS");
    expect(row).toContain("+12.30%");
    expect(rowHtml(html, "candle")).not.toContain("DPS)");
    const off = view(t, { result: null, gainsUnsupported: true });
    expect(off).toContain('data-testid="gains-unsupported"');
    expect(off).toContain("Artifact potentials are not available for this class yet.");
    expect(rowHtml(off, "alliance_badge")).not.toContain("DPS");
    expect(rowHtml(off, "alliance_badge")).toContain("line 1 stat");          // the lines can still be edited
    const err = view(t, { status: { ...none, error: "boom" } });
    expect(err).toContain("boom");
  });
  it("request: only artifacts with a line, 'Not Unlocked' for a null star, unknown stats / rarities sent as (none), only the artifact's own line count", () => {
    let t = setLine(art, emptyArtifacts(art), "alliance_badge", 0, { rarity: "Legendary", stat: "Damage %" });
    t = setLine(art, t, "alliance_badge", 2, { rarity: "Epic", stat: "Critical Rate %" });
    t = setLine(art, t, "pigs_ribbon", 0, { rarity: "Epic", stat: "Final Damage %" });         // not rollable on artifacts
    t = setLine(art, t, "hexagon_necklace", 1, { rarity: "Mystic", stat: "Accuracy" });
    t = setStar(art, t, "hexagon_necklace", 2);
    const req = potentialsRequest(art, t, STATIC_POTENTIAL_TABLES);
    expect(Object.keys(req).sort()).toEqual(["alliance_badge", "hexagon_necklace"]);
    expect(req.alliance_badge).toEqual({ star: "Not Unlocked", lines: [{ rarity: "Legendary", stat: "Damage %" }, blankLine(), { rarity: "Epic", stat: "Critical Rate %" }] });
    expect(req.hexagon_necklace).toEqual({ star: 2, lines: [blankLine(), { rarity: "Mystic", stat: "Accuracy" }] });
    expect(potentialsRequest(art, emptyArtifacts(art), STATIC_POTENTIAL_TABLES)).toEqual({});          // nothing rolled: nothing requested
  });
});
