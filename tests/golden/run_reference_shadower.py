#!/usr/bin/env python3
"""Run the ORIGINAL ``src/verify_shadower_workbook.py`` against the workbook-free stand-in of ``reference_fake.py`` and print its numbers as JSON.

Shadower's ``import formulas`` sits in the MIDDLE of the script (the live-workbook helpers are defined before the timeline-engine block): that single
line is replaced by ``formulas = None`` and the run stops at the "Cross-check against the actual live workbook" banner.

The reference file is never modified.  Usage::

    run_reference_shadower.py CASES.json OUT.json        # CASES.json = [[case_id, inputs], ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reference_fake import Reference  # noqa: E402

REF = Reference("verify_shadower_workbook.py", "build_shadower_workbook")

SCALARS = ("attack", "stat_damage", "actions_per_second", "cast_rate", "cruel_stab_per_second", "avg_buff_mult", "as_bonus",
           "monster_defense", "fight_duration", "monster_type", "normal_weight", "status_on", "skill_coefficient_base",
           "buff_cast_startup_time", "fixed_duration_active", "hasstun", "stf_b", "stf_n", "PHI_UNIF", "companion_dps", "total_dps",
           "cruel_stab_dps", "cruel_stab_hit", "crit_damage_bonus", "crit_rate_bonus", "monster_dmg_bonus", "maple_hero_pct",
           "shadow_partner_mult", "meso_stack_avg", "bm_stack_avg", "murderous_intent_mult", "steal_avg", "meso_mastery_avg",
           "nimble_feet_avg", "dark_sight_crit_avg", "dark_sight_atk_avg", "into_darkness_avg", "smokescreen_avg", "dsa_pct", "dsc_pct",
           "id_pct", "ss_pct", "total_hit_rate", "asn_pct", "_pl_on", "engine_bbuff_mean")


def run_case(inputs):
    return REF.run_case(inputs, SCALARS, hit_rate="before")


def main():
    REF.main(run_case)


if __name__ == "__main__":
    main()
