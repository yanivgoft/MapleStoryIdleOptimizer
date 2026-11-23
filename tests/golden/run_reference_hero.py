#!/usr/bin/env python3
"""Run the ORIGINAL ``src/verify_hero_workbook.py`` against the workbook-free stand-in of ``reference_fake.py`` and print its numbers as JSON.

Hero's ``import formulas`` sits in the MIDDLE of the script (the live-workbook helpers are defined before the timeline-engine block): that single
line is replaced by ``formulas = None`` and the run stops at the "Cross-check against the actual live workbook" banner.

The reference file is never modified.  Usage::

    run_reference_hero.py CASES.json OUT.json        # CASES.json = [[case_id, inputs], ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reference_fake import Reference  # noqa: E402

REF = Reference("verify_hero_workbook.py", "build_hero_workbook")

SCALARS = ("attack", "stat_damage", "actions_per_second", "cast_rate", "raging_blow_per_second", "attack_bucket_mult", "as_bonus",
           "monster_defense", "fight_duration", "monster_type", "normal_weight", "status_on", "skill_coefficient_base",
           "buff_cast_startup_time", "fixed_duration_active", "hasstun", "stf_b", "stf_n", "attack_bucket_sum", "PHI_UNIF",
           "companion_dps", "total_dps", "raging_blow_dps", "crit_damage_bonus", "final_damage_extra", "monster_dmg_bonus", "def_pen_eff",
           "combo_stacks", "maple_hero_pct")


def run_case(inputs):
    return REF.run_case(inputs, SCALARS)


def main():
    REF.main(run_case)


if __name__ == "__main__":
    main()
