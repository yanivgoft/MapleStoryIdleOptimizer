import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ALL, fixtureFor, withoutArtifactSupport } from "../test/fixtures";
import type { ArtifactSchema, ArtifactSlot, ArtifactsState, ComputeResult, FormState, Profile } from "../types";
import { buildInputs, initialState, normalizeState } from "./schemaForm";
import { listProfiles, parseImport, saveProfile, exportJson, withArtifacts } from "./profiles";
import {
  artifactStarsExtra, artifactsAvailable, artifactsInUse, badgesFor, BAKED_DETAIL, BAKED_LABEL, blankLine, breakdown, bucketTotals, canEquip, defaultEntry, defaultStarFor, defaultTableStar,
  dpsDelta, EFFECTS, effectText, emptyArtifacts, equippedKeys, fillTemplate, lineCount, normalizeArtifacts, parseStar, placeholders, requestSlots, setEquipped, setLine, setStar, starIndex,
  starOptions, STAR_TOOLTIP, STAR_VALUES, visibleArtifacts, withoutArtifacts, equipCapTitle,
} from "./artifacts";

const fp = fixtureFor("fp_mage");
const art = fp.schema.artifacts as ArtifactSchema;
const MODELLED = ALL.filter((c) => c.schema.artifacts_modelled);
// every real class models artifacts now: the not-modelled path is exercised on synthetic variants (schema without `artifacts`, `artifacts_modelled: false`)
const UNMODELLED = [...ALL.filter((c) => !c.schema.artifacts_modelled), ...ALL.slice(0, 2).map(withoutArtifactSupport)];
const slot = (key: string, star: number | string = 5): ArtifactSlot => ({ key, star });
/** a table with exactly these artifacts equipped (default stars, no lines) */
const eq = (...keys: string[]): ArtifactsState => keys.reduce((st, k) => setEquipped(art, st, k, true), emptyArtifacts(art));
const info = (key: string) => art.artifacts.find((a) => a.key === key)!;

describe("artifact data coverage (engine schema vs web wording)", () => {
  it("fixtures: the classes.json flag matches each schema; the synthetic variants are not modelled", () => {
    for (const c of ALL) expect(!!c.info.artifacts_modelled, c.info.id).toBe(!!c.schema.artifacts_modelled);
    expect(MODELLED.map((c) => c.info.id)).toEqual(ALL.filter((c) => c.info.status?.artifacts).map((c) => c.info.id));
    expect(UNMODELLED.length).toBeGreaterThan(0);
    for (const c of UNMODELLED) {
      expect(c.schema.artifacts_modelled).toBe(false);
      expect(c.schema.artifacts).toBeUndefined();
    }
  });
  it.each(MODELLED.map((c) => [c.info.id, c.schema.artifacts as ArtifactSchema] as const))("%s: 36 artifacts, each with wording and values", (_id, a) => {
    expect(a.artifacts).toHaveLength(36);
    expect(a.slot_options).toHaveLength(37);
    expect(a.max_slots).toBe(5);
    for (const x of a.artifacts) {
      expect(EFFECTS[x.key], x.key).toBeDefined();
      for (const k of placeholders(x.key)) expect(STAR_VALUES[k], `${x.key}: ${k}`).toHaveLength(6);
      expect(a.slot_options).toContain(x.name);
    }
    expect(Object.keys(EFFECTS).sort()).toEqual(a.artifacts.map((x) => x.key).sort());
  });
  it("every engine star-value table is used by some artifact's wording", () => {
    const used = new Set(Object.keys(EFFECTS).flatMap(placeholders));
    expect(Object.keys(STAR_VALUES).filter((k) => !used.has(k))).toEqual([]);
  });
  it("artifacts with no live wording are exactly the ones flagged no-DPS or reference-only by the engine", () => {
    for (const x of art.artifacts) {
      if (EFFECTS[x.key].live.length === 0) expect(x.no_dps_effect || x.effect === "reference_only", x.key).toBe(true);
      if (x.no_dps_effect) expect(EFFECTS[x.key].baked ?? []).toHaveLength(0);
    }
  });
});

describe("star options and effect text", () => {
  it("star options come from the schema; the tooltip says Not unlocked acts as star 0", () => {
    const o = starOptions(art);
    expect(o.map((x) => x.value)).toEqual(art.star_options);
    expect(o[0].label).toBe("Not unlocked");
    expect(STAR_TOOLTIP).toContain("acts as star 0");
    expect(o[6].label).toBe("Star 5 (max)");
    expect(starIndex("Not Unlocked")).toBe(0);
    expect(starIndex(null)).toBe(0);
    expect(starIndex(3)).toBe(3);
    expect(starIndex(9)).toBe(5);
  });
  it("default star follows the rank (Epic 5, Unique 3, Legendary Not Unlocked)", () => {
    expect(defaultStarFor(art, "charm_of_the_undead")).toBe(5);
    expect(defaultStarFor(art, "hexagon_necklace")).toBe(3);
    expect(defaultStarFor(art, "alliance_badge")).toBe("Not Unlocked");
  });
  it("effect text uses the engine's star values", () => {
    expect(effectText("alliance_badge", 4).summary).toBe("+18% Attack");
    expect(effectText("alliance_badge", "Not Unlocked").summary).toBe("+10% Attack");
    expect(effectText("arwens_glass_shoes", 5).summary).toBe("+40% Companion Summoning Time Increase");
    expect(effectText("arwens_glass_shoes", 0).summary).toContain("+20%");
    expect(effectText("candle", 1).live[0]).toBe("+9.6% Final Damage");
    expect(effectText("book_of_ancient", 5).baked).toEqual(["+20% Critical Rate", "Critical Damage +60% of your Critical Rate"]);
    expect(effectText("bottle_of_emotion", 3).baked[0]).toBe("+0.8% Final Damage per 3% Attack Speed above 60% (cap 16%)");
    expect(fillTemplate("{nope}", 0)).toBe("{nope}");
    expect(effectText("pigs_ribbon", 5).summary).toBe("");
  });
});

describe("the per-artifact table state", () => {
  it("emptyArtifacts: all 36 artifacts, default star by rank, nothing equipped, 3 blank lines", () => {
    const t = emptyArtifacts(art);
    expect(Object.keys(t)).toEqual(art.artifacts.map((a) => a.key));
    expect(t.charm_of_the_undead).toEqual({ star: 5, equipped: false, lines: [blankLine(), blankLine(), blankLine()] });
    expect(t.hexagon_necklace.star).toBe(3);
    expect(t.alliance_badge.star).toBeNull();                       // Legendary: Not Unlocked
    expect(Object.values(t).every((e) => !e.equipped && e.lines.length === 3)).toBe(true);
    expect(defaultTableStar(art, "alliance_badge")).toBeNull();
    expect(defaultEntry(art, "candle").star).toBeNull();
  });
  it("parseStar: Not Unlocked / null / 0-5 (also as text) are valid, anything else is junk", () => {
    expect(parseStar(null)).toEqual({ ok: true, value: null });
    expect(parseStar("Not Unlocked")).toEqual({ ok: true, value: null });
    expect(parseStar(" not unlocked ")).toEqual({ ok: true, value: null });
    expect(parseStar(0)).toEqual({ ok: true, value: 0 });
    expect(parseStar("3")).toEqual({ ok: true, value: 3 });
    for (const bad of [6, -1, 2.5, "x", {}, undefined, true]) expect(parseStar(bad), String(bad)).toEqual({ ok: false });
  });
  it("lineCount: 3 lines for Legendary artifacts, 2 for Epic / Unique (the engine's rule)", () => {
    for (const a of art.artifacts) expect(lineCount(a), a.key).toBe(a.rank === "Legendary" ? 3 : 2);
  });
  it("normalizeArtifacts repairs junk: unknown artifacts dropped, missing ones defaulted, bad stars -> default, lines padded / blanked", () => {
    const n = normalizeArtifacts(
      { candle: { star: 99, equipped: true, lines: [{ rarity: "Epic", stat: "Damage %" }, null, 5, { rarity: 3 }] }, no_such: { star: 1, equipped: true }, chalice: "x",
        pigs_ribbon: { star: "Not Unlocked", equipped: "yes", lines: [{ rarity: "Unique", stat: "Damage %" }, { rarity: "Epic", stat: "Accuracy" }, { rarity: "Epic", stat: "Accuracy" }] } },
      art,
    );
    expect(Object.keys(n)).toHaveLength(36);
    expect("no_such" in n).toBe(false);
    expect(n.candle.star).toBeNull();                                // 99 is not an option -> the default (Legendary: Not Unlocked)
    expect(n.candle.equipped).toBe(true);
    expect(n.candle.lines).toEqual([{ rarity: "Epic", stat: "Damage %" }, blankLine(), blankLine()]);
    expect(n.chalice).toEqual(defaultEntry(art, "chalice"));
    expect(n.pigs_ribbon.star).toBeNull();
    expect(n.pigs_ribbon.equipped).toBe(false);                      // only `true` equips
    expect(n.pigs_ribbon.lines[2]).toEqual(blankLine());             // an Epic artifact has no 3rd line
    expect(normalizeArtifacts("junk", art)).toEqual(emptyArtifacts(art));
    expect(normalizeArtifacts(undefined, art)).toEqual(emptyArtifacts(art));
    expect(normalizeArtifacts(null, art)).toEqual(emptyArtifacts(art));
  });
  it("at most max_slots (5) artifacts stay equipped: extras are un-equipped in schema order", () => {
    const raw = Object.fromEntries(art.artifacts.slice(0, 8).map((a) => [a.key, { star: 1, equipped: true, lines: [] }]));
    const n = normalizeArtifacts(raw, art);
    expect(equippedKeys(art, n)).toEqual(art.artifacts.slice(0, 5).map((a) => a.key));
  });
  it("setEquipped: caps at 5 with a clear reason, always allows unequipping, unknown keys are no-ops", () => {
    expect(art.max_slots).toBe(5);
    let t = eq(...art.artifacts.slice(0, 5).map((a) => a.key));
    expect(equippedKeys(art, t)).toHaveLength(5);
    const sixth = art.artifacts[5].key;
    expect(canEquip(art, t, sixth)).toBe(false);
    expect(equippedKeys(art, setEquipped(art, t, sixth, true))).toHaveLength(5);
    expect(setEquipped(art, t, sixth, true)[sixth].equipped).toBe(false);
    expect(canEquip(art, t, art.artifacts[0].key)).toBe(true);        // an equipped one can always be toggled off
    t = setEquipped(art, t, art.artifacts[0].key, false);
    expect(canEquip(art, t, sixth)).toBe(true);
    t = setEquipped(art, t, sixth, true);
    expect(equippedKeys(art, t)).toEqual(art.artifacts.slice(1, 6).map((a) => a.key));
    expect(setEquipped(art, t, "no_such", true)).toEqual(t);
    expect(equipCapTitle(art)).toContain("5");
  });
  it("setStar keeps equip state and lines; invalid stars are no-ops; Not Unlocked is null", () => {
    let t = setEquipped(art, emptyArtifacts(art), "candle", true);
    t = setLine(art, t, "candle", 0, { stat: "Damage %" });
    t = setStar(art, t, "candle", 2);
    expect(t.candle).toMatchObject({ star: 2, equipped: true });
    expect(t.candle.lines[0].stat).toBe("Damage %");
    expect(setStar(art, t, "candle", "Not Unlocked").candle.star).toBeNull();
    expect(setStar(art, t, "candle", 17).candle.star).toBe(2);
    expect(setStar(art, t, "no_such", 1)).toEqual(t);
  });
  it("setLine: rarity and stat of one line; Epic / Unique artifacts have no 3rd line; other artifacts untouched", () => {
    let t = emptyArtifacts(art);
    t = setLine(art, t, "alliance_badge", 2, { rarity: "Mystic", stat: "Boss Monster Damage %" });
    expect(t.alliance_badge.lines[2]).toEqual({ rarity: "Mystic", stat: "Boss Monster Damage %" });
    expect(t.alliance_badge.lines[0]).toEqual(blankLine());
    const epic = setLine(art, t, "pigs_ribbon", 2, { stat: "Damage %" });
    expect(epic.pigs_ribbon.lines[2]).toEqual(blankLine());
    expect(setLine(art, t, "pigs_ribbon", 5, { stat: "Damage %" })).toEqual(t);
    expect(t.candle).toEqual(defaultEntry(art, "candle"));
  });
  it("visibleArtifacts: filter by name (case-insensitive substring) and 'only unlocked / equipped'", () => {
    const t = setEquipped(art, setStar(art, emptyArtifacts(art), "alliance_badge", 1), "candle", true);
    expect(visibleArtifacts(art, t, { text: "", onlyActive: false })).toHaveLength(36);
    expect(visibleArtifacts(art, t, { text: " BADGE ", onlyActive: false }).map((a) => a.key)).toEqual(["alliance_badge"]);
    const active = visibleArtifacts(art, t, { text: "", onlyActive: true }).map((a) => a.key);
    // default-unlocked Epic (4) + Unique (9) artifacts, plus the two touched Legendary ones
    expect(active).toHaveLength(4 + 9 + 2);
    expect(active).toContain("candle");
    expect(active).toContain("alliance_badge");
    expect(active).not.toContain("chalice");
    expect(visibleArtifacts(art, t, { text: "zzz", onlyActive: false })).toEqual([]);
  });
});

describe("badges come from the engine's flags", () => {
  it("no-DPS-effect artifacts (the 7 flagged) get the badge with the engine's reason", () => {
    const flagged = art.artifacts.filter((a) => a.no_dps_effect);
    expect(flagged).toHaveLength(7);
    for (const a of flagged) {
      const b = badgesFor(a);
      expect(b).toHaveLength(1);
      expect(b[0].kind).toBe("no_dps");
      expect(b[0].detail).toBe(a.reason);
    }
  });
  it("baked-into-Inputs: every reference_only artifact plus Reindeer's base Defense Penetration", () => {
    const baked = art.artifacts.filter((a) => badgesFor(a).some((b) => b.kind === "baked")).map((a) => a.key).sort();
    const ref = art.artifacts.filter((a) => a.effect === "reference_only").map((a) => a.key);
    expect(baked).toEqual([...ref, "reindeer_spear"].sort());
    expect(ref.sort()).toEqual(["athena_gloves", "book_of_ancient", "bottle_of_emotion", "clear_spring_water", "cursed_doll", "lit_lamp", "shamaness_marble", "soul_pouch", "star_rock"]);
    const book = badgesFor(info("book_of_ancient"))[0];
    expect(book.label).toBe(BAKED_LABEL);
    expect(book.detail).toBe(BAKED_DETAIL);
    expect(book.partial).toBe(false);
    expect(badgesFor(info("bottle_of_emotion"))[0].partial).toBe(true);        // Attack% is live, Final Damage is baked
    expect(badgesFor(info("reindeer_spear"))[0].partial).toBe(true);
    expect(badgesFor(info("alliance_badge"))).toEqual([]);
  });
  it("companion effect: Arwen's Glass Shoes, Hexagon, Charm, Horn Flute", () => {
    const comp = art.artifacts.filter((a) => badgesFor(a).some((b) => b.kind === "companion" || b.kind === "status")).map((a) => a.key).sort();
    expect(comp).toEqual(["arwens_glass_shoes", "charm_of_the_undead", "hexagon_necklace", "horn_flute"]);
  });
});

describe("request building and capability", () => {
  const state = (a: ArtifactsState): FormState => ({ ...initialState(fp.schema, fp.defaults["World Boss"], "World Boss"), artifacts: a });
  it("sends the equipped artifacts only, once each, in the schema's order (not click order), at most 5, Not Unlocked as the engine's 'Not Unlocked'", () => {
    let t = setEquipped(art, emptyArtifacts(art), "candle", true);
    t = setStar(art, t, "candle", 2);
    t = setEquipped(art, t, "chalice", true);                          // Legendary: default Not Unlocked
    t = setEquipped(art, t, "pigs_ribbon", true);
    t = setStar(art, t, "pigs_ribbon", 0);
    const req = buildInputs(fp.schema, state(t)).artifacts as unknown[];
    expect(req).toEqual([{ key: "pigs_ribbon", star: 0 }, { key: "chalice", star: "Not Unlocked" }, { key: "candle", star: 2 }]);
    expect(requestSlots(art, undefined)).toEqual([]);
    expect(buildInputs(fp.schema, state(emptyArtifacts(art))).artifacts).toEqual([]);
    // five equipped is the cap: a hand-edited state with eight equipped still sends five
    const eight = Object.fromEntries(art.artifacts.slice(0, 8).map((a) => [a.key, { star: 3, equipped: true, lines: [] }]));
    expect(requestSlots(art, eight as unknown as ArtifactsState)).toHaveLength(5);
  });
  it("artifact_stars (equip ranking / stat values): the star of EVERY artifact, 'Not Unlocked' for the locked ones", () => {
    const t = setStar(art, emptyArtifacts(art), "alliance_badge", 4);
    const x = artifactStarsExtra(art, t) as { artifact_stars: Record<string, number | string> };
    expect(Object.keys(x.artifact_stars)).toHaveLength(36);
    expect(x.artifact_stars.alliance_badge).toBe(4);
    expect(x.artifact_stars.candle).toBe("Not Unlocked");
    expect(x.artifact_stars.charm_of_the_undead).toBe(5);
    expect(artifactStarsExtra(undefined, t)).toEqual({});
  });
  it.each(UNMODELLED.map((c) => [c.info.id, c] as const))("%s: artifacts are not sent when the schema says not modelled", (_id, c) => {
    const s: FormState = { ...initialState(c.schema, c.defaults["World Boss"], "World Boss"), artifacts: { candle: { star: 1, equipped: true, lines: [] } } as unknown as ArtifactsState };
    expect("artifacts" in buildInputs(c.schema, s)).toBe(false);
    expect(artifactsAvailable(c.schema, c.info)).toBe(false);
  });
  it("capability reads the schema first, class status only as a fallback; never a class list", () => {
    expect(artifactsAvailable(fp.schema, fp.info)).toBe(true);
    expect(artifactsAvailable({ ...fp.schema, artifacts_modelled: false }, fp.info)).toBe(false);
    expect(artifactsAvailable({ ...fp.schema, artifacts: undefined }, fp.info)).toBe(false);
    expect(artifactsAvailable(null, { id: "x", name: "X", status: { artifacts: true } })).toBe(true);
    expect(artifactsAvailable(null, { id: "x", name: "X", artifacts_modelled: false })).toBe(false);
    expect(artifactsAvailable(null, null)).toBe(false);
  });
  it("comparison request = the same inputs without artifacts", () => {
    const inputs = buildInputs(fp.schema, state(eq("candle")));
    const w = withoutArtifacts(inputs);
    expect("artifacts" in w).toBe(false);
    expect(w.level).toBe(inputs.level);
    expect("artifacts" in inputs).toBe(true);        // original untouched
  });
});

describe("result breakdown (real engine output with 4 artifacts)", () => {
  it.each(MODELLED.map((c) => [c.info.id] as const))("%s", async (id) => {
    const c = (await import(`../fixtures/${id}.artifacts_case.json`)).default as { artifacts: ArtifactSlot[]; result: ComputeResult };
    const rows = breakdown(c.result);
    expect(rows.map((r) => r.key)).toEqual(["alliance_badge", "arwens_glass_shoes", "book_of_ancient", "pigs_ribbon"]);
    const by = Object.fromEntries(rows.map((r) => [r.key, r]));
    expect(by.alliance_badge.values[0]).toMatchObject({ value: 18, unit: "%", applied: true });
    expect(by.alliance_badge.bucket).toBe("Attack %");
    expect(by.arwens_glass_shoes.values[0].value).toBe(28);
    expect(by.arwens_glass_shoes.badges.map((b) => b.kind)).toEqual(["companion"]);
    expect(by.book_of_ancient.values.every((v) => !v.applied)).toBe(true);
    expect(by.book_of_ancient.values.find((v) => v.label === "Critical Rate")?.value).toBe(20);
    expect(by.pigs_ribbon.bucket).toBe("none");
    expect(by.pigs_ribbon.note).toContain("not used");
    expect(by.pigs_ribbon.star).toBe(0);
    const totals = Object.fromEntries(bucketTotals(c.result).map((t) => [t.key, t.value]));
    expect(totals.attack_pct).toBe(18);
    expect(totals.companion_summon_time_increase_pct).toBe(28);
    expect(totals.crit_rate).toBeUndefined();
    const plain = ALL.find((x) => x.info.id === id)!.result;
    expect(c.result.total_dps).toBeGreaterThan(plain.total_dps);
  });
  it("no artifacts block -> nothing; delta maths", () => {
    expect(breakdown(fp.result)).toEqual([]);
    expect(breakdown(null)).toEqual([]);
    expect(bucketTotals(undefined)).toEqual([]);
    expect(dpsDelta(110, 100)?.abs).toBe(10);
    expect(dpsDelta(110, 100)?.pct).toBeCloseTo(10, 9);
    expect(dpsDelta(110, null)).toBeNull();
    expect(dpsDelta(5, 0)).toEqual({ abs: 5, pct: null });
  });
});

describe("profile round-trip", () => {
  const store = new Map<string, string>();
  beforeEach(() => {
    store.clear();
    (globalThis as { localStorage?: unknown }).localStorage = {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
      removeItem: (k: string) => void store.delete(k),
    };
  });
  afterEach(() => delete (globalThis as { localStorage?: unknown }).localStorage);
  const base = (): FormState => initialState(fp.schema, fp.defaults["Chapter Boss"], "Chapter Boss");

  it("the table (stars, equipped, lines) is saved, listed, exported, imported and restored", () => {
    let t = emptyArtifacts(art);
    t = setEquipped(art, setStar(art, t, "candle", 2), "candle", true);
    t = setEquipped(art, setStar(art, t, "pigs_ribbon", "Not Unlocked"), "pigs_ribbon", true);
    t = setLine(art, t, "candle", 2, { rarity: "Legendary", stat: "Damage %" });
    t = setLine(art, t, "horn_flute", 0, { rarity: "Epic", stat: "Critical Rate %" });
    saveProfile("art", { ...base(), artifacts: t });
    const [p] = listProfiles();
    expect(p.state.artifacts).toEqual(t);
    expect(normalizeState(fp.schema, p.state).artifacts).toEqual(t);
    const back = parseImport(exportJson([p]));
    expect(back[0].state.artifacts).toEqual(t);
    expect(normalizeState(fp.schema, back[0].state).artifacts).toEqual(t);
  });
  it("profiles saved before the Artifacts tab (no artifacts key) still load, with the default table", () => {
    const legacy = { id: "old", name: "old", savedAt: "2026-01-01T00:00:00Z", state: { classId: "fp_mage", contentType: "Chapter Boss", shared: base().shared, perContent: base().perContent } };
    store.set("msi.profiles.v1", JSON.stringify([legacy]));
    const [p] = listProfiles();
    expect(p.state.artifacts).toEqual({});
    const s = normalizeState(fp.schema, p.state);
    expect(s.artifacts).toEqual(emptyArtifacts(art));
    expect(equippedKeys(art, s.artifacts)).toEqual([]);
    expect(parseImport(JSON.stringify(legacy))[0].state.artifacts).toEqual({});
  });
  it("junk in a stored / imported profile is repaired, not crashing", () => {
    const p = withArtifacts({ id: "j", name: "j", savedAt: "", state: { ...base(), artifacts: { candle: { star: { x: 1 }, equipped: true, lines: "x" }, "BAD KEY": { star: 1 }, chalice: 7, horn_flute: [1] } as unknown as ArtifactsState } });
    expect(Object.keys(p.state.artifacts)).toEqual(["candle"]);         // junk keys / non-object entries dropped at load
    const n = normalizeState(fp.schema, p.state);
    expect(n.artifacts.candle).toEqual({ star: null, equipped: true, lines: [blankLine(), blankLine(), blankLine()] });
    expect(n.artifacts.chalice).toEqual(defaultEntry(art, "chalice"));
    expect(withArtifacts({ ...p, state: { ...p.state, artifacts: "x" as unknown as ArtifactsState } }).state.artifacts).toEqual({});
    expect(normalizeState(fp.schema, withArtifacts({ ...p, state: { ...p.state, artifacts: 5 as unknown as ArtifactsState } }).state).artifacts).toEqual(emptyArtifacts(art));
  });
  it("an artifact set from a profile of a not-modelled class is kept but never sent", () => {
    const c = UNMODELLED[0];
    const raw = { candle: { star: 1, equipped: true, lines: [] } } as unknown as ArtifactsState;
    const st = normalizeState(c.schema, { ...initialState(c.schema, c.defaults["World Boss"], "World Boss"), artifacts: raw });
    expect(st.artifacts).toEqual(raw);
    expect("artifacts" in buildInputs(c.schema, st)).toBe(false);
  });
});

describe("profiles saved with the OLD slots UI (a slots list + the separate Artifact potentials state) migrate to the table", () => {
  const store = new Map<string, string>();
  beforeEach(() => {
    store.clear();
    (globalThis as { localStorage?: unknown }).localStorage = {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
      removeItem: (k: string) => void store.delete(k),
    };
  });
  afterEach(() => delete (globalThis as { localStorage?: unknown }).localStorage);
  const base = (): FormState => initialState(fp.schema, fp.defaults["Chapter Boss"], "Chapter Boss");
  const OLD_SLOTS = [slot("candle", 2), { key: "(none)", star: "Not Unlocked" }, slot("pigs_ribbon", "Not Unlocked"), slot("horn_flute", 0)];
  const OLD_POTENTIALS = {
    candle: { lines: [{ rarity: "Legendary", stat: "Damage %" }, { rarity: "Epic", stat: "Critical Rate %" }, { rarity: "Rare", stat: "(none)" }] },    // equipped: the slot's star counts
    chalice: { star: 4, lines: [{ rarity: "Unique", stat: "Defense Penetration %" }] },                       // listed with its own star
    secret_map: { star: null, lines: [] },                                                                    // own star: Not Unlocked
    lunar_dew: { lines: [{ rarity: "Mystic", stat: "Boss Monster Damage %" }] },                              // no star: the default by rank
    no_such: { star: 1, lines: [] },
  };
  const old = (): Profile => ({ id: "old", name: "old", savedAt: "2026-01-01T00:00:00Z", state: { ...base(), artifacts: OLD_SLOTS, potentials: OLD_POTENTIALS } as unknown as FormState });

  it("equipped = the slots, their star; own stars and lines of the potentials entries; everything else the default", () => {
    store.set("msi.profiles.v1", JSON.stringify([old()]));
    const [p] = listProfiles();
    expect(Array.isArray(p.state.artifacts)).toBe(true);                 // the stored shape is kept until the schema is known
    const n = normalizeState(fp.schema, p.state);
    expect("potentials" in n).toBe(false);
    expect(Object.keys(n.artifacts)).toHaveLength(36);
    expect(equippedKeys(art, n.artifacts)).toEqual(["pigs_ribbon", "candle", "horn_flute"]);
    expect(n.artifacts.candle).toMatchObject({ star: 2, equipped: true });
    expect(n.artifacts.candle.lines).toEqual([{ rarity: "Legendary", stat: "Damage %" }, { rarity: "Epic", stat: "Critical Rate %" }, blankLine()]);
    expect(n.artifacts.pigs_ribbon.star).toBeNull();
    expect(n.artifacts.horn_flute.star).toBe(0);
    expect(n.artifacts.chalice).toEqual({ star: 4, equipped: false, lines: [{ rarity: "Unique", stat: "Defense Penetration %" }, blankLine(), blankLine()] });
    expect(n.artifacts.secret_map.star).toBeNull();
    expect(n.artifacts.lunar_dew.star).toBeNull();                       // Legendary default
    expect(n.artifacts.lunar_dew.lines[0]).toEqual({ rarity: "Mystic", stat: "Boss Monster Damage %" });
    expect(n.artifacts.hexagon_necklace).toEqual(defaultEntry(art, "hexagon_necklace"));
    // the request the engine gets is the old equipped set
    expect(requestSlots(art, n.artifacts)).toEqual([{ key: "pigs_ribbon", star: "Not Unlocked" }, { key: "candle", star: 2 }, { key: "horn_flute", star: 0 }]);
    expect(artifactsInUse(art, n.artifacts).map((x) => `${x.name} ${x.star}`)).toEqual(["Pig's Ribbon not unlocked", "Candle \u26052", "Horn Flute \u26050"]);
  });
  it("round trip: migrate, save, load, normalise again gives the same table (and the old fields are gone)", () => {
    store.set("msi.profiles.v1", JSON.stringify([old()]));
    const migrated = normalizeState(fp.schema, listProfiles()[0].state);
    saveProfile("new", migrated);
    const saved = listProfiles().find((x) => x.name === "new")!;
    expect(saved.state.artifacts).toEqual(migrated.artifacts);
    expect("potentials" in saved.state).toBe(false);
    expect(normalizeState(fp.schema, saved.state).artifacts).toEqual(migrated.artifacts);
    const exported = parseImport(exportJson([saved]));
    expect(normalizeState(fp.schema, exported[0].state).artifacts).toEqual(migrated.artifacts);
    // the old profile exported as a file and imported again migrates the same way
    expect(normalizeState(fp.schema, parseImport(exportJson([old()]))[0].state).artifacts).toEqual(migrated.artifacts);
  });
  it("junk in the old shape is repaired: repeats, unknown names, too many slots, bad stars, potentials without lines", () => {
    const junk = {
      ...old(),
      state: {
        ...base(),
        artifacts: [slot("candle", 3), slot("candle", 1), { key: "Alliance Badge", star: 9 }, slot("horn_flute"), slot("chalice"), slot("secret_map"), slot("lunar_dew"), null, 4],
        potentials: { candle: { lines: [{ rarity: "Rare" }, null, { rarity: "Epic", stat: "Damage %" }] }, chalice: 5, secret_map: { lines: "x", star: "zz" } },
      },
    };
    const n = normalizeState(fp.schema, withArtifacts(junk as unknown as Profile).state);
    expect(equippedKeys(art, n.artifacts)).toEqual(["candle", "chalice", "alliance_badge", "horn_flute", "secret_map"].sort((a, b) => art.artifacts.findIndex((x) => x.key === a) - art.artifacts.findIndex((x) => x.key === b)));
    expect(n.artifacts.candle.star).toBe(3);                              // the first slot wins
    expect(n.artifacts.lunar_dew.equipped).toBe(false);                   // the 6th slot is cut: at most 5 stay equipped
    expect(n.artifacts.alliance_badge.star).toBeNull();                   // star 9 -> the default (Legendary: Not Unlocked)
    expect(n.artifacts.candle.lines).toEqual([blankLine(), blankLine(), { rarity: "Epic", stat: "Damage %" }]);   // positions are kept: a malformed line 1 does not shift line 3 up
    expect(n.artifacts.secret_map.lines).toEqual([blankLine(), blankLine(), blankLine()]);
  });
});
