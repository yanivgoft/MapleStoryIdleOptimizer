#!/usr/bin/env python3
"""Run the ORIGINAL ``src/verify_buccaneer_workbook.py`` against the workbook-free stand-in of ``reference_fake.py`` and print its numbers as JSON.

Buccaneer's ``import formulas`` sits in the MIDDLE of the script (the live-workbook helpers are defined before the timeline-engine block): that single
line is replaced by ``formulas = None`` and the run stops at the "Cross-check against the actual live workbook" banner.

The reference file is never modified.  Usage::

    run_reference_buccaneer.py CASES.json OUT.json        # CASES.json = [[case_id, inputs], ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reference_fake import Reference  # noqa: E402

REF = Reference("verify_buccaneer_workbook.py", "build_buccaneer_workbook")

SCALARS = ("attack", "stat_damage", "actions_per_second", "cast_rate", "cast_rate_avg", "hook_bomber_per_second", "hook_bomber_per_second_avg",
           "attack_bucket_mult", "monster_defense", "fight_duration", "monster_type", "normal_weight", "status_on",
           "skill_coefficient_base", "buff_cast_startup_time", "fixed_duration_active", "hasstun", "stf_b", "stf_n",
           "PHI_UNIF", "companion_dps", "total_dps", "hook_bomber_dps", "sea_serpent_burst_dps", "serpent_assault_dps",
           "crit_damage_bonus", "crit_rate_bonus", "final_damage_extra", "final_damage_rest", "monster_dmg_bonus",
           "maple_hero_pct", "uptime", "serpent_T", "serpent_scale_avg", "crossbones_full", "time_leap_full", "speed_infusion_full",
           "roll_of_dice_pct", "OCTOPUNCH_COOLDOWN", "_x_boss", "_x_norm")


def _post_scalars(ns, out):
    out["as_bonus"] = ns["_nimble_feet_as_avg"]() + ns["_speed_infusion_as_avg"]()


def run_case(inputs):
    return REF.run_case(inputs, SCALARS, post_scalars=_post_scalars)


def main():
    REF.main(run_case)


if __name__ == "__main__":
    main()
