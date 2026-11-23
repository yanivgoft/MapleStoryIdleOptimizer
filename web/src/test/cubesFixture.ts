// Test-only: the FP-Mage cube-tab fixtures (real engine output through the API, see scripts/gen_fixtures.py), loaded eagerly.
import type { CubesMeta, CubesResult } from "../lib/cubes";
import type { EquipResult } from "../lib/equipment";
import type { PotentialsResult } from "../lib/artifactPotentials";

const files = import.meta.glob("../fixtures/*.{cubes_meta,cubes_case,equipment_case,potentials_case}.json", { eager: true, import: "default" }) as Record<string, unknown>;

function get<T>(id: string, name: string): T {
  const v = files[`../fixtures/${id}.${name}.json`];
  if (v === undefined) throw new Error(`missing fixture ${id}.${name} (run web/scripts/gen_fixtures.py --cubes-only)`);
  return v as T;
}

export function cubesFixture(id = "fp_mage") {
  return {
    meta: get<CubesMeta>(id, "cubes_meta"),
    cubes: get<{ gear: { slot: string; potential_type: string; rarity: string; pity: number; lines: { stat: string; value: number }[] }[]; result: CubesResult }>(id, "cubes_case"),
    equipment: get<{ request: { current: { attack: number; lines: { stat: string; value: number }[] }; new: { attack: number; lines: { stat: string; value: number }[] } }; result: EquipResult }>(id, "equipment_case"),
    potentials: get<{ request: { potentials: Record<string, { star?: number | string | null; lines: { rarity: string; stat: string }[] }> }; result: PotentialsResult; rate_by_stat: Record<string, number> }>(id, "potentials_case"),
  };
}
