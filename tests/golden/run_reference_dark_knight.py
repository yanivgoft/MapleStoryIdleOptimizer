#!/usr/bin/env python3
"""Run the ORIGINAL ``src/verify_dark_knight_workbook.py`` against the workbook-free stand-in of ``reference_fake.py`` and print its numbers as JSON.

Dark Knight's ``import formulas`` sits in the MIDDLE of the script (the live-workbook helpers are defined before the timeline-engine block): that single
line is replaced by ``formulas = None`` and the run stops at the "Cross-check against the actual live workbook" banner.

The reference file is never modified.  Usage::

    run_reference_dark_knight.py CASES.json OUT.json        # CASES.json = [[case_id, inputs], ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reference_fake import Reference  # noqa: E402

REF = Reference("verify_dark_knight_workbook.py", "build_dark_knight_workbook")

SCALARS = ("attack", "stat_damage", "actions_per_second", "cast_rate", "dark_impale_per_second", "attack_bucket_mult", "as_bonus", "monster_defense",
           "fight_duration", "monster_type", "normal_weight", "status_on", "skill_coefficient_base", "buff_cast_startup_time",
           "fixed_duration_active", "hasstun", "stf_b", "stf_n", "attack_bucket_sum", "PHI_UNIF", "companion_dps", "total_dps", "dark_impale_dps",
           "crit_rate_bonus", "crit_damage_bonus", "final_damage_extra", "monster_dmg_bonus", "maple_hero_pct", "total_defense",
           "iron_wall_str_bonus", "final_attack_pct", "advanced_final_attack_pct", "evil_eye_shock_enh_pct", "hex_avg", "hex_boss_avg",
           "dark_resonance_avg", "dark_resonance_boss_avg", "cross_over_chains_avg", "hyper_body_avg", "evil_eye_avg", "magic_crash_weaken_avg",
           "lord_critrate_avg", "lord_critdmg_avg")


def run_case(inputs):
    return REF.run_case(inputs, SCALARS)


def main():
    REF.main(run_case)


if __name__ == "__main__":
    main()
