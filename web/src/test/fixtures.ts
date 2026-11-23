// Test-only: every class's fixture set (schema / defaults / sample inputs / result), loaded eagerly from src/fixtures/.
import type { ClassInfo, ClassSchema, ComputeResult, Values } from "../types";

const files = import.meta.glob("../fixtures/*.json", { eager: true, import: "default" }) as Record<string, unknown>;

function get<T>(name: string): T {
  const v = files[`../fixtures/${name}.json`];
  if (v === undefined) throw new Error(`missing fixture ${name}`);
  return v as T;
}

export const classList = get<{ classes: ClassInfo[] }>("classes").classes;
export const CLASS_IDS = classList.map((c) => c.id);

export interface ClassFixture {
  info: ClassInfo;
  schema: ClassSchema;
  defaults: Record<string, Values>;
  sampleInputs: Values;
  result: ComputeResult;
}

export function fixtureFor(id: string): ClassFixture {
  return {
    info: classList.find((c) => c.id === id)!,
    schema: get<ClassSchema>(`${id}.schema`),
    defaults: get<Record<string, Values>>(`${id}.defaults`),
    sampleInputs: get<Values>(`${id}.sample_inputs`),
    result: get<ComputeResult>(`${id}.result`),
  };
}

/** Id of the synthetic class below; no fixture file carries it, so the mock API answers 501 for it exactly like for a real class without stat values. */
export const NO_STAT_VALUES_ID = "no_stat_values_class";

export const ALL = CLASS_IDS.map(fixtureFor);

/** Classes whose stat values / cube tabs the API does not model (they answer 501): the fixture classes that say so in classes.json (derived, never listed by hand)
 *  plus one synthetic class (`withoutStatValues()`), so the list is never empty whichever real classes have fixtures. */
export const NO_STAT_VALUES = [...ALL.filter((c) => !c.info.status?.stat_values), withoutStatValues()];
/** Fixture classes that have stat values (and the sensitivity / cubes fixtures that go with them). */
export const WITH_STAT_VALUES = ALL.filter((c) => c.info.status?.stat_values);

/** Synthetic variant of a class that does not model artifacts: the schema says `artifacts_modelled: false` and has no `artifacts` section. */
export function withoutArtifactSupport(c: ClassFixture): ClassFixture {
  const { artifacts: _artifacts, ...schema } = c.schema as ClassSchema & { artifacts?: unknown };
  return {
    ...c,
    info: { ...c.info, artifacts_modelled: false, status: { ...c.info.status, artifacts: false } as ClassInfo["status"] },
    schema: { ...schema, artifacts_modelled: false } as ClassSchema,
  };
}

/** Synthetic class whose status says it has no stat values / cube tabs (a clone of `base` with an unknown id, so it has no sensitivity / cubes fixtures
 *  either).  Tests of the "not available for this class yet" paths use it, so they do not depend on which real classes happen to have fixtures. */
export function withoutStatValues(base: ClassFixture = fixtureFor("fp_mage")): ClassFixture {
  return {
    ...base,
    info: { ...base.info, id: NO_STAT_VALUES_ID, name: "No Stat Values Class", status: { ...base.info.status, stat_values: false } as ClassInfo["status"] },
    schema: { ...base.schema, class_id: NO_STAT_VALUES_ID, name: "No Stat Values Class" } as ClassSchema,
  };
}
