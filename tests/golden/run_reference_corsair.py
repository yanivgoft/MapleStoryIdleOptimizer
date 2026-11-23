#!/usr/bin/env python3
"""Run the ORIGINAL ``src/verify_corsair_workbook.py`` against the workbook-free stand-in of ``reference_fake.py`` and print its numbers as JSON.

Corsair's ``import formulas`` sits in the MIDDLE of the script (the live-workbook helpers are defined before the timeline-engine block): that single
line is replaced by ``formulas = None`` and the run stops at the "Cross-check against the actual live workbook" banner.

The reference file is never modified.  Usage::

    run_reference_corsair.py CASES.json OUT.json        # CASES.json = [[case_id, inputs], ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reference_fake import Reference  # noqa: E402

REF = Reference("verify_corsair_workbook.py", "build_corsair_workbook")

SCALARS = ("attack", "stat_damage", "actions_per_second", "cast_rate", "cast_rate_avg", "eight_legs_easton_per_second", "attack_bucket_mult",
           "monster_defense", "fight_duration", "monster_type", "normal_weight", "status_on", "skill_coefficient_base",
           "buff_cast_startup_time", "fixed_duration_active", "hasstun", "stf_b", "stf_n", "PHI_UNIF",
           "companion_dps", "total_dps", "eight_legs_easton_dps", "crit_damage_bonus", "crit_rate_bonus", "final_damage_extra", "final_damage_rest",
           "monster_dmg_bonus", "maple_hero_pct", "ahoy_mateys_pct", "ahoy_mateys_proc_fd", "jolly_roger_full", "jolly_roger_pct",
           "roll_of_dice_pct", "qd_factor", "qd_damage_mult", "crew_window", "_nimble_feet_as_bonus")


def run_case(inputs):
    return REF.run_case(inputs, SCALARS)


def main():
    REF.main(run_case)


if __name__ == "__main__":
    main()
