import type { ClassInfo, ClassSchema, ComputeResult, FieldError, Values } from "./types";
import type { SensPart, SensitivityMeta, SensitivityResult } from "./lib/sensitivity";
import type { CubeRow, CubesMeta, CubesResult, GearPayloadRow, RowRef } from "./lib/cubes";
import { compareEquip, type EquipResult, type equipPayload } from "./lib/equipment";
import { relevel } from "./lib/companions";
import { computePotentials, type PotentialsResult, type PotentialsState } from "./lib/artifactPotentials";

// Fixtures (one set per class, dumped from the real API by scripts/gen_fixtures.py) are loaded lazily so a normal build does not ship them in
// the main bundle: Vite turns each glob entry into its own chunk.
const fixtureLoaders = import.meta.glob("./fixtures/*.json", { import: "default" }) as Record<string, () => Promise<unknown>>;

async function fixture<T>(name: string): Promise<T> {
  const load = fixtureLoaders[`./fixtures/${name}.json`];
  if (!load) throw new ApiError(404, `mock mode: no fixture "${name}" (run web/scripts/gen_fixtures.py)`);
  return (await load()) as T;
}

export const API_URL: string = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");
export const MOCK: boolean = import.meta.env.VITE_MOCK === "1";

/** Text of a request that never got an answer (status 0). */
export const UNREACHABLE_MESSAGE = "Can't reach the calculator server.";

export class ApiError extends Error {
  status: number;
  fieldErrors: FieldError[];
  constructor(status: number, message: string, fieldErrors: FieldError[] = []) {
    super(message);
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

async function request<T>(path: string, init?: RequestInit, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, signal, headers: { "Content-Type": "application/json" } });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, UNREACHABLE_MESSAGE); // no URL in the text: players cannot act on it (the console / dev server shows it)
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON error body */
  }
  if (!res.ok) {
    const b = (body ?? {}) as { detail?: string; errors?: FieldError[] };
    throw new ApiError(res.status, b.detail ?? `HTTP ${res.status}`, b.errors ?? []);
  }
  return body as T;
}

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Mock base result: the plain fixture; with `inputs.artifacts` the artifacts fixture (`<id>.artifacts_case.json`, real engine output for 4 slots) when
 *  the very same slots are requested, else the plain fixture plus an artifacts block that only lists the equipped artifacts (numbers are not computed in mock mode). */
async function mockBase(id: string, inputs: Record<string, unknown>): Promise<ComputeResult> {
  const plain = await fixture<ComputeResult>(`${id}.result`);
  const slots = Array.isArray(inputs.artifacts) ? (inputs.artifacts as { key: string; star: number | string | null }[]) : [];
  if (!slots.length) return plain;
  const star = (s: number | string | null) => (typeof s === "number" ? s : 0);
  const sig = (l: { key: string; star: number | string | null }[]) => JSON.stringify(l.map((s) => [s.key, star(s.star)]).sort());
  if (fixtureLoaders[`./fixtures/${id}.artifacts_case.json`]) {
    const c = await fixture<{ artifacts: { key: string; star: number | string | null }[]; result: ComputeResult }>(`${id}.artifacts_case`);
    if (sig(c.artifacts) === sig(slots)) return c.result;
  }
  const schema = await fixture<ClassSchema>(`${id}.schema`);
  const equipped = slots.map((s) => {
    const a = schema.artifacts?.artifacts.find((x) => x.key === s.key);
    return { key: s.key, name: a?.name ?? s.key, star: star(s.star), rank: a?.rank ?? "", effect: a?.effect ?? "live", no_dps_effect: !!a?.no_dps_effect, reason: a?.reason ?? null };
  });
  return { ...plain, artifacts: { equipped, buckets: {}, rows: {}, reference_only: {}, notes: ["mock mode: artifact effects are not computed (only the fixture's own 4 artifacts have real numbers)"] } };
}

/** Mock compute: the class's fixture result scaled by Flat ATTACK relative to the fixture's inputs, so edits visibly move the numbers.  The
 *  fixture was computed with a Blaze Wizard companion; choosing "None" drops that companion's share (stun-only blocks are left as they are). */
async function mockCompute(id: string, inputs: Record<string, unknown>): Promise<ComputeResult> {
  const base = await mockBase(id, inputs);
  const sampleInputs = await fixture<Record<string, unknown>>(`${id}.sample_inputs`);
  const k = (Number(inputs.flat_attack) || 1) / (Number(sampleInputs.flat_attack) || 1);
  const sc = <T extends object>(o: T, keys: (keyof T)[]): T => {
    const c = { ...o };
    for (const key of keys) (c[key] as number) = (c[key] as number) * k;
    return c;
  };
  const scaled: ComputeResult = {
    ...base,
    ...sc(base, ["total_dps", "player_dps", "boss_dps", "normal_dps", "player_boss_dps", "player_normal_dps"]),
    skills: base.skills.map((s) => sc(s, ["dps", "boss_dps", "normal_dps"])),
    companion: base.companion ? sc(base.companion, ["dps", "boss_dps", "normal_dps"]) : null,
  };
  const comp = scaled.companion;
  if (comp && comp.choice !== "None" && inputs.companion_choice === "None") {
    scaled.total_dps -= comp.dps;
    scaled.boss_dps -= comp.boss_dps;
    scaled.normal_dps -= comp.normal_dps;
    scaled.companion = null;
  } else if (comp && typeof inputs.companion_choice === "string" && inputs.companion_choice !== "None") {
    scaled.companion = { ...comp, choice: inputs.companion_choice, level: Number(inputs.companion_level) || 0 };
  }
  return scaled;
}

/** Mock stat values: the class's sensitivity fixture restricted to the requested parts (classes without one answer 501 like the API). */
async function mockSensitivity(id: string, which?: SensPart[], inputs?: Record<string, unknown>): Promise<SensitivityResult> {
  if (!fixtureLoaders[`./fixtures/${id}.sensitivity.json`]) throw new ApiError(501, "stat values are not modelled for this class yet");
  const full = await fixture<SensitivityResult>(`${id}.sensitivity`);
  if (!which) return full;
  const parts = ["stats", "artifacts", "companions", "summon_time", "cdr"] as const;
  const out: Record<string, unknown> = { ...full };
  // the Companions tab sends every companion's level: re-label the fixture's comparison with them (the numbers stay the fixture's)
  const levels = inputs?.companion_levels as Record<string, number> | undefined;
  if (levels && full.companions) {
    out.companions = relevel(full.companions, levels, String(inputs?.companion_choice ?? "None"), Number(inputs?.companion_level) || 0);
  }
  for (const p of parts) if (!which.includes(p)) delete out[p];
  return out as unknown as SensitivityResult;
}

// ---- cube tabs, mock mode: the real engine's answers for a sample case (src/fixtures/<id>.cubes_*.json); edits re-use them as far as they can ---------------------------
const noFeature = () => new ApiError(501, "this feature is not modelled for this class yet");

async function mockCubesMeta(id: string): Promise<CubesMeta> {
  if (!fixtureLoaders[`./fixtures/${id}.cubes_meta.json`]) throw noFeature();
  return fixture<CubesMeta>(`${id}.cubes_meta`);
}

/** Mock cubes: the fixture's rows (real engine numbers for the fixture's own gear) for the requested slots, labelled with the requested rarity / pity / lines
 *  (the numbers do not follow your edits). */
async function mockCubes(id: string, gear: GearPayloadRow[], only: RowRef[]): Promise<CubesResult> {
  if (!fixtureLoaders[`./fixtures/${id}.cubes_case.json`]) throw noFeature();
  const c = await fixture<{ gear: unknown; result: CubesResult }>(`${id}.cubes_case`);
  const want = new Set(only.map((r) => `${r.slot}|${r.potential_type}`));
  const asked = new Map(gear.map((g) => [`${g.slot}|${g.potential_type}`, g]));
  const rows: CubeRow[] = c.result.rows
    .filter((r) => want.has(`${r.slot}|${r.potential_type}`))
    .map((r) => {
      const g = asked.get(`${r.slot}|${r.potential_type}`);
      if (!g) return r;
      const lines: [string, number][] = [0, 1, 2].map((i) => [g.lines[i]?.stat ?? "(none)", g.lines[i]?.value ?? 0]);
      return { ...r, rarity: g.rarity, pity: g.pity, lines };
    });
  return { ...c.result, rows, notes: ["mock mode: the numbers are the fixture's, not computed from your gear"] };
}

async function mockEquipment(id: string, body: ReturnType<typeof equipPayload>): Promise<EquipResult> {
  if (!fixtureLoaders[`./fixtures/${id}.equipment_case.json`]) throw noFeature();
  const c = await fixture<{ result: EquipResult }>(`${id}.equipment_case`);
  const { rate_by_stat: rate, baseline_total: total } = c.result;
  return { ...c.result, ...compareEquip(body, rate, total) };
}

async function mockPotentials(id: string, inputs: Record<string, unknown>, state: PotentialsState): Promise<PotentialsResult> {
  if (!fixtureLoaders[`./fixtures/${id}.potentials_case.json`]) throw noFeature();
  const c = await fixture<{ result: PotentialsResult; rate_by_stat: Record<string, number> }>(`${id}.potentials_case`);
  const meta = await mockCubesMeta(id);
  const slots = Array.isArray(inputs.artifacts) ? (inputs.artifacts as { key: string; star: number | string | null }[]) : [];
  return { ...c.result, rows: computePotentials(meta.artifact_potentials, state, c.rate_by_stat, c.result.baseline_total, slots) };
}

export const api = {
  async classes(): Promise<ClassInfo[]> {
    if (MOCK) return (await fixture<{ classes: ClassInfo[] }>("classes")).classes;
    return (await request<{ classes: ClassInfo[] }>("/api/classes")).classes;
  },
  async schema(id: string): Promise<ClassSchema> {
    if (MOCK) return fixture<ClassSchema>(`${id}.schema`);
    return request<ClassSchema>(`/api/classes/${encodeURIComponent(id)}/schema`);
  },
  async defaults(id: string, contentType: string): Promise<Values> {
    if (MOCK) return (await fixture<Record<string, Values>>(`${id}.defaults`))[contentType];
    return request<Values>(`/api/classes/${encodeURIComponent(id)}/defaults?content_type=${encodeURIComponent(contentType)}`);
  },
  async compute(id: string, inputs: Record<string, unknown>, signal?: AbortSignal): Promise<ComputeResult> {
    if (MOCK) {
      await wait(150);
      return await mockCompute(id, inputs);
    }
    return request<ComputeResult>(`/api/classes/${encodeURIComponent(id)}/compute`, { method: "POST", body: JSON.stringify(inputs) }, signal);
  },
  /** Stat values (POST .../sensitivity); `which` limits the parts (default all).  501 = not modelled for this class.  Mock mode serves the class's
   *  fixture as it is (numbers do not follow the inputs). */
  async sensitivity(id: string, inputs: Record<string, unknown>, which?: SensPart[], signal?: AbortSignal): Promise<SensitivityResult> {
    if (MOCK) {
      await wait(200);
      if (signal?.aborted) throw new DOMException("aborted", "AbortError");
      return mockSensitivity(id, which, inputs);
    }
    const body = which ? { ...inputs, which } : inputs;
    return request<SensitivityResult>(`/api/classes/${encodeURIComponent(id)}/sensitivity`, { method: "POST", body: JSON.stringify(body) }, signal);
  },
  /** Static tables of the cube tabs (GET .../cubes/meta): slots, rarities, stat options, pity caps, equipment stats, artifact-potential values.  501 = not modelled. */
  async cubesMeta(id: string, signal?: AbortSignal): Promise<CubesMeta> {
    if (MOCK) return mockCubesMeta(id);
    return request<CubesMeta>(`/api/classes/${encodeURIComponent(id)}/cubes/meta`, undefined, signal);
  },
  /** Cube optimizer rows (POST .../cubes) for the `only` rows of `gear`; the caller sends a few rows per request (see lib/cubesRunner). */
  async cubes(id: string, inputs: Record<string, unknown>, gear: GearPayloadRow[], only: RowRef[], signal?: AbortSignal): Promise<CubesResult> {
    if (MOCK) {
      await wait(250);
      if (signal?.aborted) throw new DOMException("aborted", "AbortError");
      return mockCubes(id, gear, only);
    }
    return request<CubesResult>(`/api/classes/${encodeURIComponent(id)}/cubes`, { method: "POST", body: JSON.stringify({ ...inputs, gear, only }) }, signal);
  },
  async equipmentCompare(id: string, inputs: Record<string, unknown>, body: ReturnType<typeof equipPayload>, signal?: AbortSignal): Promise<EquipResult> {
    if (MOCK) {
      await wait(120);
      if (signal?.aborted) throw new DOMException("aborted", "AbortError");
      return mockEquipment(id, body);
    }
    return request<EquipResult>(`/api/classes/${encodeURIComponent(id)}/equipment-compare`, { method: "POST", body: JSON.stringify({ ...inputs, ...body }) }, signal);
  },
  async artifactPotentials(id: string, inputs: Record<string, unknown>, potentials: Record<string, unknown>, signal?: AbortSignal): Promise<PotentialsResult> {
    if (MOCK) {
      await wait(120);
      if (signal?.aborted) throw new DOMException("aborted", "AbortError");
      return mockPotentials(id, inputs, potentials as unknown as PotentialsState);
    }
    return request<PotentialsResult>(`/api/classes/${encodeURIComponent(id)}/artifact-potentials`, { method: "POST", body: JSON.stringify({ ...inputs, potentials }) }, signal);
  },
  async sensitivityMeta(id: string, signal?: AbortSignal): Promise<SensitivityMeta> {
    if (MOCK) {
      await mockSensitivity(id, ["cdr"]); // same 501 as the API for classes without a fixture
      return fixture<SensitivityMeta>(`${id}.sensitivity_meta`);
    }
    return request<SensitivityMeta>(`/api/classes/${encodeURIComponent(id)}/sensitivity/meta`, undefined, signal);
  },
};
