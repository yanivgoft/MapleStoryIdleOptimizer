#!/usr/bin/env python3
"""Run the ORIGINAL ``src/verify_night_lord_workbook.py`` against the workbook-free stand-in of ``reference_fake.py`` and print its numbers as JSON.

Night Lord's ``import formulas`` sits in the MIDDLE of the script (the live-workbook helpers are defined before the timeline-engine block): that single
line is replaced by ``formulas = None`` and the run stops at the "Cross-check against the actual live workbook" banner.

The reference file is never modified.  Usage::

    run_reference_night_lord.py CASES.json OUT.json        # CASES.json = [[case_id, inputs], ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reference_fake import Reference  # noqa: E402

REF = Reference("verify_night_lord_workbook.py", "build_night_lord_workbook")

SCALARS = ("attack", "stat_damage", "actions_per_second", "cast_rate", "showdown_per_second", "avg_buff_mult", "as_bonus",
           "monster_defense", "fight_duration", "monster_type", "normal_weight", "status_on", "skill_coefficient_base",
           "buff_cast_startup_time", "fixed_duration_active", "hasstun", "stf_b", "stf_n", "PHI_UNIF",
           "companion_dps", "total_dps", "showdown_dps", "crit_damage_bonus", "crit_rate_bonus", "monster_dmg_bonus",
           "shadow_partner_mult", "dark_sight_atk_avg", "dark_sight_crit_avg", "frailty_self_avg", "frailty_debuff_avg",
           "dark_sight_crit_uptime", "adrenalin_uptime", "adrenalin_fd_avg", "adrenalin_as_avg", "nimble_feet_avg",
           "aps_pre_adrenalin", "total_hit_rate", "night_lords_mark_pct", "engine_bbuff_mean", "_pl_on")


def run_case(inputs):
    return REF.run_case(inputs, SCALARS, hit_rate="after")


def main():
    REF.main(run_case)


if __name__ == "__main__":
    main()
