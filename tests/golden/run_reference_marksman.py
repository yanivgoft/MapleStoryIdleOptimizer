#!/usr/bin/env python3
"""Run the ORIGINAL ``src/verify_marksman_workbook.py`` against the workbook-free stand-in of ``reference_fake.py`` and print its numbers as JSON.

Marksman's ``import formulas`` sits in the MIDDLE of the script (the live-workbook helpers are defined before the timeline-engine block): that single
line is replaced by ``formulas = None`` and the run stops at the "Cross-check against the actual live workbook" banner.

The reference file is never modified.  Usage::

    run_reference_marksman.py CASES.json OUT.json        # CASES.json = [[case_id, inputs], ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reference_fake import Reference  # noqa: E402

REF = Reference("verify_marksman_workbook.py", "build_marksman_workbook")

SCALARS = ("attack", "stat_damage", "actions_per_second", "cast_rate", "epa_per_second", "attack_bucket_mult", "as_bonus",
           "monster_defense", "fight_duration", "monster_type", "normal_weight", "status_on", "skill_coefficient_base",
           "buff_cast_startup_time", "fixed_duration_active", "hasstun", "stf_b", "stf_n", "attack_bucket_sum", "PHI_UNIF",
           "companion_dps", "total_dps", "epa_dps", "crit_damage_bonus", "crit_rate_bonus", "mortal_blow_bonus", "monster_dmg_bonus",
           "maple_hero_pct", "blink_bolt_pct", "epa_hit_rate", "snipe_hit_rate", "bolt_surplus_trigger_rate", "sharp_eyes_uptime",
           "illusion_step_avg", "marksmanship_base_pct", "marksmanship_cond_avg", "illusion_step_pct", "last_man_standing_cond_avg",
           "epa_final_attack_addition", "_pl_on")


def run_case(inputs):
    return REF.run_case(inputs, SCALARS)


def main():
    REF.main(run_case)


if __name__ == "__main__":
    main()
