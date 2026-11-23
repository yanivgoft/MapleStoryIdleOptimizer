// Test-only: the FP-Mage sensitivity fixture (result + meta), loaded eagerly from src/fixtures/.
import type { SensitivityMeta, SensitivityResult } from "../lib/sensitivity";

const files = import.meta.glob("../fixtures/*.sensitivity*.json", { eager: true, import: "default" }) as Record<string, unknown>;

export function sensFixture(id = "fp_mage"): { result: SensitivityResult; meta: SensitivityMeta } {
  const result = files[`../fixtures/${id}.sensitivity.json`] as SensitivityResult | undefined;
  const meta = files[`../fixtures/${id}.sensitivity_meta.json`] as SensitivityMeta | undefined;
  if (!result || !meta) throw new Error(`missing sensitivity fixture for ${id} (run web/scripts/gen_fixtures.py --sensitivity-only)`);
  return { result, meta };
}
