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

export const ALL = CLASS_IDS.map(fixtureFor);

/** Fixture classes whose stat values / cube tabs the API does not model (they answer 501) - derived from classes.json, never listed by hand. */
export const NO_STAT_VALUES = ALL.filter((c) => !c.info.status?.stat_values);
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
