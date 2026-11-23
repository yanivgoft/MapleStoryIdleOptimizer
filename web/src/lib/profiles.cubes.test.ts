import { describe, expect, it } from "vitest";
import { exportJson, parseImport, withArtifacts } from "./profiles";
import { initialState, normalizeState } from "./schemaForm";
import { fixtureFor } from "../test/fixtures";
import type { ArtifactSchema, FormState, Profile } from "../types";
import { emptyArtifacts, setLine, setStar } from "./artifacts";

const c = fixtureFor("fp_mage");
const art = c.schema.artifacts as ArtifactSchema;
const base = (): FormState => initialState(c.schema, c.defaults["World Boss"], "World Boss");
const profile = (state: FormState): Profile => ({ id: "p1", name: "mine", savedAt: "2026-11-20T00:00:00Z", state });

describe("cube tabs data travels with the profile", () => {
  const state: FormState = {
    ...base(),
    cubes: { "head|Potential": { rarity: "epic", pity: 12, lines: [{ stat: "Damage %", value: 12 }, { stat: "(none)", value: null }, { stat: "(none)", value: null }] } },
    equipment: { current: { attack: 1500, lines: [{ stat: "Damage %", value: 14 }, ...Array.from({ length: 4 }, () => ({ stat: "(none)", value: null }))] }, new: { attack: null, lines: Array.from({ length: 5 }, () => ({ stat: "(none)", value: null })) } },
    artifacts: setLine(art, setStar(art, emptyArtifacts(art), "book_of_ancient", 5), "book_of_ancient", 0, { rarity: "Legendary", stat: "Damage %" }),   // potential lines live in the artifacts table now
  };
  it("export -> import round-trips cubes, equipment and the artifacts table (with its potential lines)", () => {
    const back = parseImport(exportJson([profile(state)]))[0].state;
    expect(back.cubes).toEqual(state.cubes);
    expect(back.equipment).toEqual(state.equipment);
    expect(back.artifacts).toEqual(state.artifacts);
    expect(back.potentials).toBeUndefined();
  });
  it("profiles saved before the tabs existed simply have none (and stay valid)", () => {
    const old = withArtifacts(profile(base())).state;
    expect(old.cubes).toBeUndefined();
    expect(old.equipment).toBeUndefined();
    expect(old.potentials).toBeUndefined();
    expect(parseImport(exportJson([profile(base())]))).toHaveLength(1);
  });
  it("junk in an imported file is repaired, not trusted", () => {
    const junk = { ...profile(base()), state: { ...base(), cubes: [1, 2], equipment: "x", potentials: { Bad: 1 }, artifacts: { Bad: 1, candle: 4 } } } as unknown as Profile;
    const s = withArtifacts(junk).state;
    expect(s.cubes).toEqual({});
    expect(s.equipment?.current.lines).toHaveLength(5);
    expect(s.potentials).toBeUndefined();               // the old potentials state only matters next to an old slots list (it is migrated, then dropped)
    expect(s.artifacts).toEqual({});
  });
  it("normalizeState (loading a profile into the form) keeps them", () => {
    const n = normalizeState(c.schema, state);
    expect(n.cubes).toEqual(state.cubes);
    expect(n.equipment).toEqual(state.equipment);
    expect(n.artifacts).toEqual(state.artifacts);
  });
});
