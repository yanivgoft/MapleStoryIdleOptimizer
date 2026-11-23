import type { ReactElement, ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import { buildInputs, initialState, switchContentType } from "../lib/schemaForm";
import { normalizeSlots, setSlot, setStar, slotsFor } from "../lib/artifacts";
import { ALL, fixtureFor, withoutArtifactSupport } from "../test/fixtures";
import type { ArtifactSchema, FormState } from "../types";
import { EquippedArtifacts } from "./EquippedArtifacts";
import { InputsForm } from "./InputsForm";

const strip = (h: string) => h.replace(/<!-- -->/g, "");
const MODELLED = ALL.filter((c) => c.schema.artifacts_modelled);

/** every element of a React element tree (the component is hook-free, so calling it gives the tree without a DOM) */
function walk(node: ReactNode, out: ReactElement[] = []): ReactElement[] {
  if (Array.isArray(node)) node.forEach((n) => walk(n, out));
  else if (node && typeof node === "object" && "props" in node) {
    out.push(node as ReactElement);
    walk((node as ReactElement<{ children?: ReactNode }>).props.children, out);
  }
  return out;
}

const selectsOf = (tree: ReactElement) => walk(tree).filter((e) => e.type === "select") as ReactElement<{ id: string; value: string; onChange: (e: { target: { value: string } }) => void; children: ReactNode }>[];

const form = (c: (typeof ALL)[number], st: FormState) =>
  strip(renderToString(<InputsForm schema={c.schema} classInfo={c.info} state={st} onState={() => undefined} errors={{}} loadDefaults={() => undefined} />));
/** the artifact id shown in each slot select of the rendered form (the `selected` option) */
const shown = (html: string, art: ArtifactSchema): string[] =>
  Array.from({ length: art.max_slots }, (_v, i) => {
    const sel = html.match(new RegExp(`<select id="f-artifact-slot-${i + 1}"[\\s\\S]*?</select>`))![0];
    return sel.match(/<option value="([^"]*)" selected="">/)?.[1] ?? "";
  });

describe("Equipped artifacts section of the Inputs form", () => {
  it.each(MODELLED.map((c) => [c.info.id] as const))("%s: max_slots dropdowns with every artifact, between 'Additional bonuses' and the Companion section", (id) => {
    const c = fixtureFor(id);
    const art = c.schema.artifacts as ArtifactSchema;
    const html = form(c, initialState(c.schema, c.defaults["World Boss"], "World Boss"));
    expect(html).toContain("<legend>Equipped artifacts</legend>");
    expect(html).toContain('id="equipped-artifacts-section"');
    expect(html.match(/<select id="f-artifact-slot-\d+"/g)).toHaveLength(art.max_slots);
    const first = html.match(/<select id="f-artifact-slot-1"[\s\S]*?<\/select>/)![0];
    expect(first.match(/<option/g)).toHaveLength(1 + art.artifacts.length);
    expect(first).toContain(`>${art.none_label}</option>`);
    for (const a of art.artifacts) expect(first).toContain(`>${a.name.replace(/'/g, "&#x27;")}</option>`);
    const at = (t: string) => html.indexOf(`<legend>${t}</legend>`);
    expect(at("Additional bonuses")).toBeGreaterThan(-1);
    expect(at("Equipped artifacts")).toBeGreaterThan(at("Additional bonuses"));
    expect(at("Equipped artifacts")).toBeLessThan(at("Companion"));
    expect(at("Equipped artifacts")).toBeLessThan(at("Computed (read-only)"));
    expect(html).not.toContain("Artifacts in use:");                          // the old summary above the form is replaced by this section
  });
  it("a class without artifact support has no section", () => {
    const c = withoutArtifactSupport(ALL[0]);
    const html = form(c, initialState(c.schema, c.defaults["World Boss"], "World Boss"));
    expect(html).not.toContain("Equipped artifacts");
  });
  it("shows the chosen artifacts of the CURRENT content type with their stars; options chosen in another slot are disabled", () => {
    const c = fixtureFor("fp_mage");
    const art = c.schema.artifacts as ArtifactSchema;
    let st = initialState(c.schema, c.defaults["World Boss"], "World Boss");
    st = { ...st, artifacts: setStar(art, st.artifacts, "candle", 3), equippedArtifacts: { "World Boss": normalizeSlots(["candle", "", "pigs_ribbon"], art) } };
    const html = form(c, st);
    expect(shown(html, art)).toEqual(["candle", "", "pigs_ribbon", "", ""]);
    expect(html).toContain("★3");
    // candle is taken by slot 1: disabled in the others, not in slot 1 itself
    const slot2 = html.match(/<select id="f-artifact-slot-2"[\s\S]*?<\/select>/)![0];
    const slot1 = html.match(/<select id="f-artifact-slot-1"[\s\S]*?<\/select>/)![0];
    expect(slot2).toMatch(/<option value="candle" disabled="">Candle<\/option>/);
    expect(slot2).toMatch(/<option value="pigs_ribbon" disabled="">/);
    expect(slot1).not.toMatch(/<option value="candle" disabled/);
    expect(slot1).toMatch(/<option value="pigs_ribbon" disabled="">/);
    expect(slot1).not.toMatch(/<option value="chalice" disabled/);
    // an artifact that is not unlocked says so
    const locked = form(c, { ...st, artifacts: setStar(art, st.artifacts, "pigs_ribbon", "Not Unlocked") });
    expect(locked).toContain("not unlocked (acts as star 0)");
  });
  it("switching the content type changes the slots shown in the form AND the `artifacts` of the next compute request", () => {
    const c = fixtureFor("fp_mage");
    const art = c.schema.artifacts as ArtifactSchema;
    const wb = "World Boss";
    const cb = "Chapter Boss";
    let st = initialState(c.schema, c.defaults[wb], wb);
    st = { ...st, equippedArtifacts: { [wb]: normalizeSlots(["candle", "chalice", "horn_flute", "secret_map", "flaming_lava"], art), [cb]: normalizeSlots(["", "pigs_ribbon", "candle"], art) } };
    const keys = (s: FormState) => (buildInputs(c.schema, s).artifacts as { key: string }[]).map((x) => x.key);
    // World Boss: 5 artifacts, in the form and in the request (schema order)
    expect(shown(form(c, st), art)).toEqual(["candle", "chalice", "horn_flute", "secret_map", "flaming_lava"]);
    expect(keys(st)).toHaveLength(5);
    // switch (what the content-type dropdown does): Chapter Boss has its own 2
    const toCb = switchContentType({ ...st, perContent: { ...st.perContent, [cb]: st.perContent[wb] } }, c.schema, cb);
    expect(shown(form(c, toCb), art)).toEqual(["", "pigs_ribbon", "candle", "", ""]);
    expect(keys(toCb)).toEqual(art.artifacts.map((a) => a.key).filter((k) => ["pigs_ribbon", "candle"].includes(k)));
    // and back: nothing was lost
    const back = switchContentType(toCb, c.schema, wb);
    expect(shown(form(c, back), art)).toEqual(shown(form(c, st), art));
    expect(keys(back)).toEqual(keys(st));
    // a content type without stored slots shows empty slots and sends none
    const third = c.schema.content_types.find((ct) => ct !== wb && ct !== cb)!;
    const toThird = switchContentType(st, c.schema, third, c.defaults[third]);
    expect(shown(form(c, toThird), art)).toEqual(["", "", "", "", ""]);
    expect(keys(toThird)).toEqual([]);
  });
  it("choosing in a slot stores it for the current content type only; a duplicate never gets through; clearing works", () => {
    const c = fixtureFor("fp_mage");
    const art = c.schema.artifacts as ArtifactSchema;
    let st: FormState = initialState(c.schema, c.defaults["World Boss"], "World Boss");
    const apply = (next: FormState) => (st = next);
    const choose = (slot: number, value: string) => {
      const tree = EquippedArtifacts({ schema: c.schema, classInfo: c.info, state: st, onState: apply }) as ReactElement;
      selectsOf(tree)[slot - 1].props.onChange({ target: { value } });
    };
    choose(1, "candle");
    choose(2, "candle");                                                       // the same artifact in a second slot: refused
    choose(3, "chalice");
    expect(slotsFor(art, st.equippedArtifacts, "World Boss")).toEqual(["candle", "", "chalice", "", ""]);
    choose(1, "");
    expect(slotsFor(art, st.equippedArtifacts, "World Boss")).toEqual(["", "", "chalice", "", ""]);
    choose(2, "candle");                                                       // free again after clearing slot 1
    expect(slotsFor(art, st.equippedArtifacts, "World Boss")).toEqual(["", "candle", "chalice", "", ""]);
    expect(st.equippedArtifacts!["Chapter Boss"]).toBeUndefined();            // other content types untouched
    const keys = (buildInputs(c.schema, st).artifacts as { key: string }[]).map((x) => x.key);
    expect(new Set(keys).size).toBe(keys.length);
    // the section's selects are the only ones carrying the slot ids
    expect(selectsOf(EquippedArtifacts({ schema: c.schema, classInfo: c.info, state: st, onState: apply }) as ReactElement).map((s) => s.props.id)).toEqual(
      Array.from({ length: art.max_slots }, (_v, i) => `f-artifact-slot-${i + 1}`),
    );
    // setSlot through the form equals the pure helper
    expect(st.equippedArtifacts).toEqual(setSlot(art, setSlot(art, { "World Boss": normalizeSlots(["", "", "chalice"], art) }, "World Boss", 1, "candle"), "World Boss", 0, ""));
  });
});
