import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ALL, fixtureFor, withoutArtifactSupport } from "../test/fixtures";
import type { ArtifactSchema, ArtifactSlot, ArtifactsState, ComputeResult, FormState, Profile } from "../types";
import { buildInputs, copyContentValues, initialState, normalizeState, switchContentType } from "./schemaForm";
import { listProfiles, parseImport, saveProfile, exportJson, withArtifacts } from "./profiles";
import {
  artifactStarsExtra, artifactsAvailable, artifactsInUse, badgesFor, BAKED_DETAIL, BAKED_LABEL, blankLine, breakdown, bucketTotals, currentSlots, defaultEntry, defaultStarFor, defaultTableStar,
  dpsDelta, EFFECTS, effectText, EMPTY_SLOT, emptyArtifacts, equippedCount, equippedKeys, fillTemplate, legacyEquippedKeys, lineCount, normalizeArtifacts, normalizeEquipped, normalizeSlots,
  parseStar, placeholders, requestSlots, setLine, setSlot, setStar, slotsFor, starIndex, starOptions, STAR_TOOLTIP, STAR_VALUES, visibleArtifacts, withoutArtifacts,
} from "./artifacts";

const fp = fixtureFor("fp_mage");
const art = fp.schema.artifacts as ArtifactSchema;
const MODELLED = ALL.filter((c) => c.schema.artifacts_modelled);
// every real class models artifacts now: the not-modelled path is exercised on synthetic variants (schema without `artifacts`, `artifacts_modelled: false`)
const UNMODELLED = [...ALL.filter((c) => !c.schema.artifacts_modelled), ...ALL.slice(0, 2).map(withoutArtifactSupport)];
const slot = (key: string, star: number | string = 5): ArtifactSlot => ({ key, star });
/** the slots of a content type holding exactly these artifacts */
const slotsOf = (...keys: string[]): string[] => normalizeSlots(keys, art);
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
  it("emptyArtifacts: all 36 artifacts, default star by rank, 3 blank lines (no equipped flag any more)", () => {
    const t = emptyArtifacts(art);
    expect(Object.keys(t)).toEqual(art.artifacts.map((a) => a.key));
    expect(t.charm_of_the_undead).toEqual({ star: 5, lines: [blankLine(), blankLine(), blankLine()] });
    expect(t.hexagon_necklace.star).toBe(3);
    expect(t.alliance_badge.star).toBeNull();                       // Legendary: Not Unlocked
    expect(Object.values(t).every((e) => !("equipped" in e) && e.lines.length === 3)).toBe(true);
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
    expect("equipped" in n.candle).toBe(false);                      // the old per-artifact flag is dropped (normalizeEquipped reads it first)
    expect(n.candle.lines).toEqual([{ rarity: "Epic", stat: "Damage %" }, blankLine(), blankLine()]);
    expect(n.chalice).toEqual(defaultEntry(art, "chalice"));
    expect(n.pigs_ribbon.star).toBeNull();
    expect(n.pigs_ribbon.lines[2]).toEqual(blankLine());             // an Epic artifact has no 3rd line
    expect(normalizeArtifacts("junk", art)).toEqual(emptyArtifacts(art));
    expect(normalizeArtifacts(undefined, art)).toEqual(emptyArtifacts(art));
    expect(normalizeArtifacts(null, art)).toEqual(emptyArtifacts(art));
  });
  it("normalizeSlots: max_slots entries, unknown ids and repeats become empty, extras are cut, junk is empty", () => {
    expect(art.max_slots).toBe(5);
    expect(normalizeSlots(undefined, art)).toEqual(Array(5).fill(EMPTY_SLOT));
    expect(normalizeSlots("x", art)).toEqual(Array(5).fill(EMPTY_SLOT));
    expect(normalizeSlots(["candle", "no_such", "candle", 7, null, "chalice", "horn_flute"], art)).toEqual(["candle", "", "", "", ""]);
    expect(normalizeSlots(["candle", "chalice", "horn_flute", "secret_map", "flaming_lava", "lunar_dew"], art)).toEqual(["candle", "chalice", "horn_flute", "secret_map", "flaming_lava"]);
    expect(normalizeSlots(["", "candle", "", "chalice"], art)).toEqual(["", "candle", "", "chalice", ""]);        // positions are kept
  });
  it("equippedKeys / equippedCount: once each, schema order (not slot order), at most max_slots", () => {
    const keys = ["horn_flute", "candle", "alliance_badge"];
    expect(equippedKeys(art, keys)).toEqual(art.artifacts.map((a) => a.key).filter((k) => keys.includes(k)));
    expect(equippedKeys(art, ["candle", "candle", ""])).toEqual(["candle"]);
    expect(equippedKeys(art, art.artifacts.slice(0, 8).map((a) => a.key))).toEqual(art.artifacts.slice(0, 5).map((a) => a.key));
    expect(equippedCount(art, undefined)).toBe(0);
    expect(equippedCount(art, keys)).toBe(3);
  });
  it("setSlot: an artifact can sit in one slot only (a duplicate is a no-op), clearing and moving work, unknown keys / slots are no-ops", () => {
    let eqd = setSlot(art, undefined, "World Boss", 0, "candle");
    expect(eqd["World Boss"]).toEqual(["candle", "", "", "", ""]);
    eqd = setSlot(art, eqd, "World Boss", 2, "chalice");
    expect(slotsFor(art, eqd, "World Boss")).toEqual(["candle", "", "chalice", "", ""]);
    expect(setSlot(art, eqd, "World Boss", 1, "candle")).toEqual(eqd);                       // already in slot 1
    expect(setSlot(art, eqd, "World Boss", 4, "chalice")).toEqual(eqd);
    expect(setSlot(art, eqd, "World Boss", 0, "candle")["World Boss"]).toEqual(["candle", "", "chalice", "", ""]);   // re-choosing the same slot's own artifact is fine
    expect(setSlot(art, eqd, "World Boss", 0, "no_such")).toEqual(eqd);
    expect(setSlot(art, eqd, "World Boss", 5, "horn_flute")).toEqual(eqd);                   // there are max_slots slots (0..4)
    expect(setSlot(art, eqd, "World Boss", -1, "horn_flute")).toEqual(eqd);
    const cleared = setSlot(art, eqd, "World Boss", 0, EMPTY_SLOT);
    expect(slotsFor(art, cleared, "World Boss")).toEqual(["", "", "chalice", "", ""]);
    expect(slotsFor(art, setSlot(art, cleared, "World Boss", 1, "candle"), "World Boss")).toEqual(["", "candle", "chalice", "", ""]);   // move candle to slot 2
    // a different content type is independent, and an artifact may be equipped in both
    const both = setSlot(art, eqd, "Chapter Boss", 0, "candle");
    expect(slotsFor(art, both, "Chapter Boss")).toEqual(["candle", "", "", "", ""]);
    expect(slotsFor(art, both, "World Boss")).toEqual(["candle", "", "chalice", "", ""]);
    expect(slotsFor(art, eqd, "Hero Dungeon")).toEqual(Array(5).fill(EMPTY_SLOT));            // never set: empty
    expect(eqd["World Boss"]).toEqual(["candle", "", "chalice", "", ""]);                    // input not mutated
  });
  it("setStar keeps the lines; invalid stars are no-ops; Not Unlocked is null", () => {
    let t = setLine(art, emptyArtifacts(art), "candle", 0, { stat: "Damage %" });
    t = setStar(art, t, "candle", 2);
    expect(t.candle.star).toBe(2);
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
    const t = setStar(art, emptyArtifacts(art), "alliance_badge", 1);
    expect(visibleArtifacts(art, t, { text: "", onlyActive: false })).toHaveLength(36);
    expect(visibleArtifacts(art, t, { text: " BADGE ", onlyActive: false }).map((a) => a.key)).toEqual(["alliance_badge"]);
    const active = visibleArtifacts(art, t, { text: "", onlyActive: true }, ["candle"]).map((a) => a.key);
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
  const state = (a: ArtifactsState, slots: string[] = [], ct = "World Boss"): FormState => ({ ...initialState(fp.schema, fp.defaults["World Boss"], "World Boss"), artifacts: a, contentType: ct, equippedArtifacts: { [ct]: normalizeSlots(slots, art) } });
  it("sends the current content type's slots only, once each, in the schema's order (not slot order), at most 5, Not Unlocked as the engine's 'Not Unlocked'", () => {
    let t = setStar(art, emptyArtifacts(art), "candle", 2);                     // Legendary: default Not Unlocked
    t = setStar(art, t, "pigs_ribbon", 0);
    const req = buildInputs(fp.schema, state(t, ["candle", "chalice", "pigs_ribbon"])).artifacts as unknown[];
    expect(req).toEqual([{ key: "pigs_ribbon", star: 0 }, { key: "chalice", star: "Not Unlocked" }, { key: "candle", star: 2 }]);
    expect(requestSlots(art, undefined, undefined)).toEqual([]);
    expect(buildInputs(fp.schema, state(emptyArtifacts(art))).artifacts).toEqual([]);
    // five is the cap: a hand-edited list of eight still sends five, and a repeat once
    expect(requestSlots(art, t, art.artifacts.slice(0, 8).map((a) => a.key))).toHaveLength(5);
    expect(requestSlots(art, t, ["candle", "candle"])).toEqual([{ key: "candle", star: 2 }]);
  });
  it("a state with no slots for the content type (or none at all) sends an empty list", () => {
    const s = state(emptyArtifacts(art), ["candle"]);
    expect(buildInputs(fp.schema, { ...s, contentType: "Chapter Boss" }).artifacts).toEqual([]);
    expect(buildInputs(fp.schema, { ...s, equippedArtifacts: undefined }).artifacts).toEqual([]);
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
    const s: FormState = { ...initialState(c.schema, c.defaults["World Boss"], "World Boss"), artifacts: { candle: { star: 1, lines: [] } } as unknown as ArtifactsState, equippedArtifacts: { "World Boss": ["candle"] } };
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
    const inputs = buildInputs(fp.schema, state(emptyArtifacts(art), ["candle"]));
    const w = withoutArtifacts(inputs);
    expect("artifacts" in w).toBe(false);
    expect(w.level).toBe(inputs.level);
    expect((inputs.artifacts as unknown[]).length).toBe(1);        // original untouched
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

  it("the table (stars, lines) and the equipped slots per content type are saved, listed, exported, imported and restored", () => {
    let t = emptyArtifacts(art);
    t = setStar(art, t, "candle", 2);
    t = setStar(art, t, "pigs_ribbon", "Not Unlocked");
    t = setLine(art, t, "candle", 2, { rarity: "Legendary", stat: "Damage %" });
    t = setLine(art, t, "horn_flute", 0, { rarity: "Epic", stat: "Critical Rate %" });
    const equippedArtifacts = { "Chapter Boss": slotsOf("candle", "pigs_ribbon"), "World Boss": slotsOf("horn_flute") };
    saveProfile("art", { ...base(), artifacts: t, equippedArtifacts });
    const [p] = listProfiles();
    expect(p.state.artifacts).toEqual(t);
    expect(p.state.equippedArtifacts).toEqual(equippedArtifacts);
    expect(normalizeState(fp.schema, p.state).artifacts).toEqual(t);
    expect(normalizeState(fp.schema, p.state).equippedArtifacts).toEqual(equippedArtifacts);
    const back = parseImport(exportJson([p]));
    expect(JSON.parse(exportJson([p])).version).toBe(2);
    expect(back[0].state.artifacts).toEqual(t);
    expect(back[0].state.equippedArtifacts).toEqual(equippedArtifacts);
    expect(normalizeState(fp.schema, back[0].state).artifacts).toEqual(t);
    expect(normalizeState(fp.schema, back[0].state).equippedArtifacts).toEqual(equippedArtifacts);
  });
  it("profiles saved before the Artifacts tab (no artifacts key) still load, with the default table", () => {
    const legacy = { id: "old", name: "old", savedAt: "2026-01-01T00:00:00Z", state: { classId: "fp_mage", contentType: "Chapter Boss", shared: base().shared, perContent: base().perContent } };
    store.set("msi.profiles.v1", JSON.stringify([legacy]));
    const [p] = listProfiles();
    expect(p.state.artifacts).toEqual({});
    const s = normalizeState(fp.schema, p.state);
    expect(s.artifacts).toEqual(emptyArtifacts(art));
    expect(Object.values(s.equippedArtifacts!).every((l) => l.every((k) => k === EMPTY_SLOT))).toBe(true);
    expect(parseImport(JSON.stringify(legacy))[0].state.artifacts).toEqual({});
  });
  it("junk in a stored / imported profile is repaired, not crashing", () => {
    const p = withArtifacts({ id: "j", name: "j", savedAt: "", state: { ...base(), artifacts: { candle: { star: { x: 1 }, lines: "x" }, "BAD KEY": { star: 1 }, chalice: 7, horn_flute: [1] } as unknown as ArtifactsState } });
    expect(Object.keys(p.state.artifacts)).toEqual(["candle"]);         // junk keys / non-object entries dropped at load
    const n = normalizeState(fp.schema, p.state);
    expect(n.artifacts.candle).toEqual({ star: null, lines: [blankLine(), blankLine(), blankLine()] });
    expect(n.artifacts.chalice).toEqual(defaultEntry(art, "chalice"));
    expect(withArtifacts({ ...p, state: { ...p.state, artifacts: "x" as unknown as ArtifactsState } }).state.artifacts).toEqual({});
    expect(normalizeState(fp.schema, withArtifacts({ ...p, state: { ...p.state, artifacts: 5 as unknown as ArtifactsState } }).state).artifacts).toEqual(emptyArtifacts(art));
  });
  it("an artifact set from a profile of a not-modelled class is kept but never sent", () => {
    const c = UNMODELLED[0];
    const raw = { candle: { star: 1, equipped: true, lines: [] } } as unknown as ArtifactsState;   // (kept as stored, never sent)
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
  const old = (): Profile => ({ id: "old", name: "old", savedAt: "2026-01-01T00:00:00Z", state: { ...base(), equippedArtifacts: undefined, artifacts: OLD_SLOTS, potentials: OLD_POTENTIALS } as unknown as FormState });

  it("equipped = the slots, their star; own stars and lines of the potentials entries; everything else the default", () => {
    store.set("msi.profiles.v1", JSON.stringify([old()]));
    const [p] = listProfiles();
    expect(Array.isArray(p.state.artifacts)).toBe(true);                 // the stored shape is kept until the schema is known
    const n = normalizeState(fp.schema, p.state);
    expect("potentials" in n).toBe(false);
    expect(Object.keys(n.artifacts)).toHaveLength(36);
    for (const ct of fp.schema.content_types) expect(equippedKeys(art, n.equippedArtifacts![ct]), ct).toEqual(["pigs_ribbon", "candle", "horn_flute"]);   // every content type starts from the old set
    expect(n.artifacts.candle.star).toBe(2);
    expect(n.artifacts.candle.lines).toEqual([{ rarity: "Legendary", stat: "Damage %" }, { rarity: "Epic", stat: "Critical Rate %" }, blankLine()]);
    expect(n.artifacts.pigs_ribbon.star).toBeNull();
    expect(n.artifacts.horn_flute.star).toBe(0);
    expect(n.artifacts.chalice).toEqual({ star: 4, lines: [{ rarity: "Unique", stat: "Defense Penetration %" }, blankLine(), blankLine()] });
    expect(n.artifacts.secret_map.star).toBeNull();
    expect(n.artifacts.lunar_dew.star).toBeNull();                       // Legendary default
    expect(n.artifacts.lunar_dew.lines[0]).toEqual({ rarity: "Mystic", stat: "Boss Monster Damage %" });
    expect(n.artifacts.hexagon_necklace).toEqual(defaultEntry(art, "hexagon_necklace"));
    // the request the engine gets is the old equipped set
    expect(requestSlots(art, n.artifacts, currentSlots(art, n))).toEqual([{ key: "pigs_ribbon", star: "Not Unlocked" }, { key: "candle", star: 2 }, { key: "horn_flute", star: 0 }]);
    expect(buildInputs(fp.schema, n).artifacts).toEqual(requestSlots(art, n.artifacts, currentSlots(art, n)));
    expect(artifactsInUse(art, n.artifacts, currentSlots(art, n)).map((x) => `${x.name} ${x.star}`)).toEqual(["Pig's Ribbon not unlocked", "Candle \u26052", "Horn Flute \u26050"]);
  });
  it("round trip: migrate, save, load, normalise again gives the same table (and the old fields are gone)", () => {
    store.set("msi.profiles.v1", JSON.stringify([old()]));
    const migrated = normalizeState(fp.schema, listProfiles()[0].state);
    saveProfile("new", migrated);
    const saved = listProfiles().find((x) => x.name === "new")!;
    expect(saved.state.artifacts).toEqual(migrated.artifacts);
    expect(saved.state.equippedArtifacts).toEqual(migrated.equippedArtifacts);
    expect("potentials" in saved.state).toBe(false);
    expect(normalizeState(fp.schema, saved.state).artifacts).toEqual(migrated.artifacts);
    expect(normalizeState(fp.schema, saved.state).equippedArtifacts).toEqual(migrated.equippedArtifacts);
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
        equippedArtifacts: undefined,
        artifacts: [slot("candle", 3), slot("candle", 1), { key: "Alliance Badge", star: 9 }, slot("horn_flute"), slot("chalice"), slot("secret_map"), slot("lunar_dew"), null, 4],
        potentials: { candle: { lines: [{ rarity: "Rare" }, null, { rarity: "Epic", stat: "Damage %" }] }, chalice: 5, secret_map: { lines: "x", star: "zz" } },
      },
    };
    const n = normalizeState(fp.schema, withArtifacts(junk as unknown as Profile).state);
    expect(equippedKeys(art, n.equippedArtifacts![n.contentType])).toEqual(["candle", "chalice", "alliance_badge", "horn_flute", "secret_map"].sort((a, b) => art.artifacts.findIndex((x) => x.key === a) - art.artifacts.findIndex((x) => x.key === b)));
    expect(n.artifacts.candle.star).toBe(3);                              // the first slot wins
    expect(equippedKeys(art, n.equippedArtifacts![n.contentType])).not.toContain("lunar_dew");   // the 6th slot is cut: at most 5 stay equipped
    expect(n.artifacts.alliance_badge.star).toBeNull();                   // star 9 -> the default (Legendary: Not Unlocked)
    expect(n.artifacts.candle.lines).toEqual([blankLine(), blankLine(), { rarity: "Epic", stat: "Damage %" }]);   // positions are kept: a malformed line 1 does not shift line 3 up
    expect(n.artifacts.secret_map.lines).toEqual([blankLine(), blankLine(), blankLine()]);
  });
});

describe("equipped artifacts per content type (the Inputs page's Equipped artifacts section)", () => {
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
  const cts = fp.schema.content_types;
  const [A, B] = [cts[0], cts[1]];
  const fresh = (ct = A): FormState => initialState(fp.schema, fp.defaults[ct], ct);
  /** a profile as the app stored it BEFORE this change: one global `equipped` flag per artifact */
  const oldGlobal = (flagged: string[], extra: Record<string, unknown> = {}): Profile => {
    const st = fresh();
    const artifacts = Object.fromEntries(Object.entries(emptyArtifacts(art)).map(([k, e]) => [k, { ...e, equipped: flagged.includes(k) }]));
    return { id: "old", name: "old", savedAt: "2026-01-01T00:00:00Z", state: { ...st, artifacts, equippedArtifacts: undefined, ...extra } as unknown as FormState };
  };
  const allHave = (n: FormState, keys: string[]) => {
    for (const ct of cts) expect(equippedKeys(art, n.equippedArtifacts![ct]), ct).toEqual(keys);
  };

  it("a fresh state has no equipped artifacts anywhere", () => {
    const s = fresh();
    expect(s.equippedArtifacts).toEqual({});
    for (const ct of cts) expect(slotsFor(art, s.equippedArtifacts, ct)).toEqual(Array(art.max_slots).fill(EMPTY_SLOT));
    expect(buildInputs(fp.schema, s).artifacts).toEqual([]);
  });
  it("migration: an old profile with global equipped flags seeds EVERY content type with that set (schema order), once; the flags are gone", () => {
    const flagged = ["pigs_ribbon", "candle", "horn_flute"];
    store.set("msi.profiles.v1", JSON.stringify([oldGlobal(flagged)]));
    const [p] = listProfiles();
    expect(p.state.equippedArtifacts).toBeUndefined();                       // stored shape is kept until the schema is known
    const n = normalizeState(fp.schema, p.state);
    allHave(n, art.artifacts.map((a) => a.key).filter((k) => flagged.includes(k)));
    expect(Object.keys(n.equippedArtifacts!).sort()).toEqual([...cts].sort());
    expect(Object.values(n.artifacts).some((e) => "equipped" in e)).toBe(false);
    expect(n.equippedArtifacts![A]).toEqual(normalizeSlots(art.artifacts.map((a) => a.key).filter((k) => flagged.includes(k)), art));   // placed from slot 1 on
    // the request of the profile's content type is the old equipped set with the old stars
    expect(buildInputs(fp.schema, n).artifacts).toEqual(requestSlots(art, n.artifacts, flagged));
    // idempotent: a second normalise (and a save + reload) does not re-seed from anything
    const again = normalizeState(fp.schema, n);
    expect(again.equippedArtifacts).toEqual(n.equippedArtifacts);
    // a later change of one content type survives the next normalise (the migration is one-time)
    const edited: FormState = { ...n, equippedArtifacts: setSlot(art, n.equippedArtifacts, B, 0, "chalice") };
    expect(normalizeState(fp.schema, edited).equippedArtifacts![B][0]).toBe("chalice");
    expect(normalizeState(fp.schema, edited).equippedArtifacts![A]).toEqual(n.equippedArtifacts![A]);
  });
  it("migration caps at max_slots (schema order) and drops unknown artifacts; an old profile with nothing equipped gets empty slots", () => {
    const eight = art.artifacts.slice(0, 8).map((a) => a.key);
    const n = normalizeState(fp.schema, withArtifacts(oldGlobal(eight)).state);
    allHave(n, eight.slice(0, art.max_slots));
    const withJunk = oldGlobal([]);
    (withJunk.state.artifacts as unknown as Record<string, unknown>).no_such = { star: 1, equipped: true, lines: [] };
    allHave(normalizeState(fp.schema, withArtifacts(withJunk).state), []);
    allHave(normalizeState(fp.schema, withArtifacts(oldGlobal([])).state), []);
  });
  it("the oldest shape (a slots list [{key, star}]) still migrates: those artifacts, with their stars, in every content type", () => {
    const list = [slot("candle", 2), { key: "(none)", star: "Not Unlocked" }, slot("pigs_ribbon", "Not Unlocked")];
    const st = { ...fresh(), artifacts: list, equippedArtifacts: undefined } as unknown as FormState;
    const n = normalizeState(fp.schema, withArtifacts({ id: "x", name: "x", savedAt: "", state: st }).state);
    allHave(n, ["pigs_ribbon", "candle"]);
    expect(buildInputs(fp.schema, n).artifacts).toEqual([{ key: "pigs_ribbon", star: "Not Unlocked" }, { key: "candle", star: 2 }]);
    expect(legacyEquippedKeys(list, art)).toEqual(["pigs_ribbon", "candle"]);
    expect(legacyEquippedKeys(undefined, art)).toEqual([]);
  });
  it("an old export file (version 1) imports and migrates; the new export is version 2 with the slots", () => {
    const text = JSON.stringify({ app: "msi-dps", version: 1, profiles: [oldGlobal(["candle", "chalice"])] });
    const [p] = parseImport(text);
    const n = normalizeState(fp.schema, p.state);
    allHave(n, ["chalice", "candle"].sort((a, b) => art.artifacts.findIndex((x) => x.key === a) - art.artifacts.findIndex((x) => x.key === b)));
    const out = JSON.parse(exportJson([{ ...p, state: n }]));
    expect(out.version).toBe(2);
    expect(out.profiles[0].state.equippedArtifacts[B]).toEqual(n.equippedArtifacts![B]);
  });
  it("per-content independence: World Boss with 5 artifacts, Chapter Boss with 2, a third content type with none; the request follows the content type", () => {
    const wb = "World Boss", cb = "Chapter Boss";
    expect(cts).toContain(wb);
    expect(cts).toContain(cb);
    let s = fresh(wb);
    const five = ["candle", "chalice", "horn_flute", "secret_map", "flaming_lava"];
    five.forEach((k, i) => (s = { ...s, equippedArtifacts: setSlot(art, s.equippedArtifacts, wb, i, k) }));
    s = switchContentType(s, fp.schema, cb, fp.defaults[cb]);
    expect(buildInputs(fp.schema, s).artifacts).toEqual([]);                           // a content type visited the first time starts empty (not copied)
    s = { ...s, equippedArtifacts: setSlot(art, setSlot(art, s.equippedArtifacts, cb, 0, "pigs_ribbon"), cb, 1, "candle") };
    const reqCb = (buildInputs(fp.schema, s).artifacts as { key: string }[]).map((x) => x.key);
    expect(reqCb).toEqual(["pigs_ribbon", "candle"]);
    s = switchContentType(s, fp.schema, wb);
    const reqWb = (buildInputs(fp.schema, s).artifacts as { key: string }[]).map((x) => x.key);
    expect(reqWb).toEqual(art.artifacts.map((a) => a.key).filter((k) => five.includes(k)));
    expect(reqWb).toHaveLength(5);
    // back to Chapter Boss: its own 2 again; the stars are shared
    s = { ...s, artifacts: setStar(art, s.artifacts, "candle", 3) };
    const both = (ct: string) => buildInputs(fp.schema, switchContentType(s, fp.schema, ct)).artifacts as { key: string; star: unknown }[];
    expect(both(cb).map((x) => x.key)).toEqual(["pigs_ribbon", "candle"]);
    expect(both(cb).find((x) => x.key === "candle")!.star).toBe(3);
    expect(both(wb).find((x) => x.key === "candle")!.star).toBe(3);
  });
  it("stored slots with a duplicate or an unknown artifact are repaired at load; a request never holds a duplicate", () => {
    const st = { ...fresh(), equippedArtifacts: { [A]: ["candle", "candle", "no_such", "chalice", "chalice", "horn_flute", "x"], "Not A Content Type": ["candle"] } } as unknown as FormState;
    const n = normalizeState(fp.schema, st);
    expect(n.equippedArtifacts![A]).toEqual(["candle", "", "", "chalice", ""]);        // the repeats / unknown ones are emptied, slots stay where they were, extras are cut
    expect("Not A Content Type" in n.equippedArtifacts!).toBe(false);
    const keys = (buildInputs(fp.schema, n).artifacts as { key: string }[]).map((x) => x.key);
    expect(new Set(keys).size).toBe(keys.length);
    expect(keys.length).toBeLessThanOrEqual(art.max_slots);
  });
  it("withArtifacts repairs a malformed equippedArtifacts (non-array values dropped, non-strings emptied); a non-object one triggers the old-flag migration", () => {
    const bad = withArtifacts({ id: "b", name: "b", savedAt: "", state: { ...fresh(), equippedArtifacts: { [A]: ["candle", 5, null], [B]: "x" } as unknown as FormState["equippedArtifacts"] } });
    expect(bad.state.equippedArtifacts).toEqual({ [A]: ["candle", "", ""] });
    const n = normalizeState(fp.schema, bad.state);
    expect(n.equippedArtifacts![A]).toEqual(normalizeSlots(["candle"], art));
    const junk = withArtifacts({ id: "b", name: "b", savedAt: "", state: { ...fresh(), equippedArtifacts: "x" as unknown as FormState["equippedArtifacts"] } });
    expect("equippedArtifacts" in junk.state).toBe(false);
    expect(normalizeEquipped(undefined, art, cts, undefined)[A]).toEqual(Array(art.max_slots).fill(EMPTY_SLOT));
  });
  it("copy from another content type copies its equipped slots too (and not by reference)", () => {
    let s = fresh(A);
    s = { ...s, equippedArtifacts: setSlot(art, s.equippedArtifacts, A, 1, "candle") };
    s = switchContentType(s, fp.schema, B, fp.defaults[B]);
    const copied = copyContentValues(s, fp.schema, A, B);
    expect(slotsFor(art, copied.equippedArtifacts, B)).toEqual(slotsFor(art, copied.equippedArtifacts, A));
    expect(slotsFor(art, copied.equippedArtifacts, B)[1]).toBe("candle");
    expect(copied.equippedArtifacts![B]).not.toBe(copied.equippedArtifacts![A]);
  });
  it("a class without artifact support keeps whatever was stored and never sends anything", () => {
    const c = UNMODELLED[0];
    const st = normalizeState(c.schema, { ...initialState(c.schema, c.defaults["World Boss"], "World Boss"), equippedArtifacts: { "World Boss": ["candle"] } });
    expect(st.equippedArtifacts).toEqual({ "World Boss": ["candle"] });
    expect("artifacts" in buildInputs(c.schema, st)).toBe(false);
  });
  it.each(MODELLED.map((c) => [c.info.id, c] as const))("%s: slots round-trip through the profile store and the request follows the slots (data-driven over every content type)", (_id, c) => {
    const a = c.schema.artifacts as ArtifactSchema;
    let s = initialState(c.schema, c.defaults[c.schema.content_types[0]], c.schema.content_types[0]);
    c.schema.content_types.forEach((ct, i) => {
      s = switchContentType(s, c.schema, ct, c.defaults[ct]);
      for (let k = 0; k <= i % (a.max_slots + 1) && k < a.max_slots; k++) s = { ...s, equippedArtifacts: setSlot(a, s.equippedArtifacts, ct, k, a.artifacts[(i * 3 + k) % a.artifacts.length].key) };
    });
    saveProfile("rt", s);
    const back = normalizeState(c.schema, listProfiles()[0].state);
    expect(back.equippedArtifacts).toEqual(s.equippedArtifacts);
    c.schema.content_types.forEach((ct, i) => {
      const req = buildInputs(c.schema, switchContentType(back, c.schema, ct)).artifacts as unknown[];
      expect(req, ct).toHaveLength(Math.min(i % (a.max_slots + 1), a.max_slots - 1) + 1);
    });
  });
});
