"""Artifacts added by the game AFTER the frozen workbooks (patch 2026-11-26), merged into ``engine.data.artifacts`` by the footer that
``tests/golden/gen_artifact_data.py`` writes at its end.  The generated tables stay exactly the workbook's (``--check``); ``WORKBOOK_ARTIFACT_LABELS`` /
``WORKBOOK_ARTIFACT_RANK`` keep the workbook subset for the checks that compare with the frozen builders.

Star values: the patch table gives the star-0 value; "every star adds 20 % of the base value" (user, 2026-11-26), the same rule as every other artifact table
(``v0 x (1 + 0.2 x star)``; stars 6 and 7 come from ``engine.artifacts.sv``).  Stack counts and durations do not scale with the star.

Equip effects (inventory effects - Normal Monster Damage 15 %, Final Damage 2 %, Defense 10 % - are part of the preset page, never modelled):

* Sealed Bottle: +6 % Final Damage; each time the player or the companion defeats an enemy +1 % Normal and +2 % Boss Monster Damage, up to 10 stacks (30 in Chapter Breakthrough).
* Shiny Watch: +10 % Attack; after a companion is summoned its Final Damage grows by 4 % every 3 s, up to 10 stacks, per companion.
* Mummydog's Bandages: +12 % Attack; below 50 % HP the Attack bonus is replaced by a heal and -40 % damage taken for 15 s (no DPS counterpart: HP is assumed to stay above 50 %).
"""

SEALED_BOTTLE_STACKS = 10                   # kill stacks (Normal +1 % / Boss +2 % Monster Damage each)
SEALED_BOTTLE_STACKS_BREAKTHROUGH = 30      # ... in Chapter Breakthrough
SHINY_WATCH_INTERVAL = 3.0                  # s between the companion's Final Damage stacks
SHINY_WATCH_MAX_STACKS = 10


def _steps(base):
    return [round(base * (1 + 0.2 * star), 10) for star in range(6)]


EXTRA_LABELS = {"sealed_bottle": "Sealed Bottle", "shiny_watch": "Shiny Watch", "mummydogs_bandages": "Mummydog's Bandages"}
EXTRA_RANK = {key: "Legendary" for key in EXTRA_LABELS}
EXTRA_STAR_VALUES = {
    "sealed_bottle_final_damage": _steps(6),
    "sealed_bottle_normal_damage_per_kill": _steps(1),
    "sealed_bottle_boss_damage_per_kill": _steps(2),
    "shiny_watch_attack_pct": _steps(10),
    "shiny_watch_companion_final_damage_per_stack": _steps(4),
    "mummydogs_bandages_attack_pct": _steps(12),
}


def extend(ns):
    """Merge the extra artifacts into the namespace of ``engine.data.artifacts`` (called once, at the end of that module)."""
    ns["WORKBOOK_ARTIFACT_LABELS"] = dict(ns["ARTIFACT_LABELS"])
    ns["WORKBOOK_ARTIFACT_RANK"] = dict(ns["ARTIFACT_RANK"])
    ns["WORKBOOK_ARTIFACT_STAR_VALUES"] = {k: list(v) for k, v in ns["ARTIFACT_STAR_VALUES"].items()}
    ns["ARTIFACT_LABELS"].update(EXTRA_LABELS)
    ns["ARTIFACT_RANK"].update(EXTRA_RANK)
    ns["ARTIFACT_STAR_VALUES"].update(EXTRA_STAR_VALUES)
