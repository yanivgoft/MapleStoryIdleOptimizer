#!/usr/bin/env python3
"""Run the ORIGINAL ``src/verify_ice_lightning_mage_workbook.py`` against the workbook-free stand-in of ``reference_fake.py`` and print its numbers as JSON.

The script's only ``import formulas`` sits inside the live-workbook cross-check at the very end, so the run simply stops at the "Cross-check
against the actual live workbook" banner (nothing to replace).

The reference file is never modified.  Usage::

    run_reference_ice_lightning_mage.py CASES.json OUT.json        # CASES.json = [[case_id, inputs], ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reference_fake import Reference  # noqa: E402

REF = Reference("verify_ice_lightning_mage_workbook.py", "build_ice_lightning_mage_workbook", import_formulas_mid_script=False)

SCALARS = ("attack", "stat_damage", "actions_per_second", "cast_rate", "chain_lightning_per_second", "avg_buff_mult", "as_bonus",
           "monster_defense", "fight_duration", "monster_type", "normal_weight", "status_on", "skill_coefficient_base",
           "buff_cast_startup_time", "fixed_duration_active", "hasstun", "stf_b", "stf_n", "attack_bucket_sum", "PHI_UNIF",
           "companion_dps", "total_dps", "chain_dps", "monster_dmg_bonus", "damage_bonus", "chain_lightning_hits")


def run_case(inputs):
    return REF.run_case(inputs, SCALARS, basic=("CHAIN_LIGHTNING", "chain_dps"))


def main():
    REF.main(run_case)


if __name__ == "__main__":
    main()
