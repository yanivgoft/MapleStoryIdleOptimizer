"""Deliberate differences between the engine and the FROZEN workbooks introduced by the 2026-11-26 patch (the workbooks are not edited).

``to_workbook(class_id, passives)`` maps an engine spec's ``(hook, base, fidx, step, unlock)`` passive tuples back to what the frozen builder's
``PASSIVE_DELTA_SLOT`` rows say, so ``sens_extras/<id>.py::test_static`` keeps comparing every OTHER passive with the builder and each patched one is listed here.
Tuples may be 4 long (``(hook, base, fidx, step)``, classes without unlock levels); the unlock level is then not part of the key.
"""

# (class id, hook, patched engine base, workbook base) ; workbook base None = a row the engine added and the builder does not have
PASSIVE_BASE_PATCHES = [
    ("hero", "max_damage_delta", 300, 200),             # Combat Mastery: Max Damage Multiplier 20% -> 30%
    ("hero", "final_damage_delta", 180, 150),           # Power Stance 15% -> 18%
    ("dark_knight", "max_damage_delta", 300, 200),      # Barricade Mastery
    ("dark_knight", "final_damage_delta", 180, 150),    # Power Stance
    ("paladin", "max_damage_delta", 300, 200),          # Paladin Expert (Mighty Paladin)
    ("bowmaster", "max_damage_delta", 300, 200),        # Bow Expert
    ("marksman", "max_damage_delta", 300, 200),         # Crossbow Expert
    ("shadower", "max_damage_delta", 300, 200),         # Dagger Expert
    ("night_lord", "max_damage_delta", 300, None),      # Claw Expert: the builder has no Max Damage row at all
]

# engine rows whose HOOK changed too: (class id, engine hook, engine base) -> (workbook hook, workbook base)
PASSIVE_REPLACE = {
    ("dark_knight", "final_pact_stack_delta", 10): ("final_damage_delta", 100),     # Final Pact: a live ramp of +1% per second x 12 now, was a flat +10 in the typed Final Damage
}


# engine rows the builder does not have (a second copy of a curve for a Lv118 boost): (class id, hook, base, unlock)
PASSIVE_DROP = {("dark_knight", "final_pact_stack_delta", 10, 118), ("bishop", "defense_pct_delta", 250, 3)}      # (bishop: 4-tuples, the last element is the job step)


def to_workbook(class_id, passives):
    """``passives``: iterable of tuples starting ``(hook, base, ...)``; returns them as the frozen builder has them (sorted)."""
    out = []
    for t in passives:
        hook, base, rest = t[0], t[1], tuple(t[2:])
        if (class_id, hook, base, t[-1]) in PASSIVE_DROP:
            continue
        hook, base = PASSIVE_REPLACE.get((class_id, hook, base), (hook, base))
        patch = [p for p in PASSIVE_BASE_PATCHES if p[0] == class_id and p[1] == hook and p[2] == base]
        if patch:
            if patch[0][3] is None:
                continue
            base = patch[0][3]
        out.append((hook, base) + rest)
    return sorted(out)


# Passives whose base the patch changed in the engine data, for the native classes' displayed-value tests (the user's in-game readings predate the patch and the site snapshot
# data/ref_maplestoryidle_info/site_job_skill_impact_all.json too): (class id, hook) -> (pre-patch base, engine base)
PATCHED_NATIVE_PASSIVES = {
    ("night_walker", "max_damage_delta"): (200, 300),     # Throwing Expert
    ("dawn_warrior", "max_damage_delta"): (200, 300),     # Student of the Blade
    ("blaze_wizard", "max_damage_delta"): (200, 300),     # Pure Magic
}


def pre_patch_base(class_id, hook, base):
    """Engine base -> the base the pre-patch site snapshot / in-game readings had."""
    old, new = PATCHED_NATIVE_PASSIVES.get((class_id, hook), (None, None))
    return old if (new is not None and base == new) else base


# the engine's spec carries these toggle keys on top of the frozen builders' lists (engine/sens_specs/__init__.py): the workbook checks compare without them
EXTRA_STATUS_KEYS = frozenset({"shiny_watch_equipped", "mummydogs_bandages_equipped"})
EXTRA_SEARCH_KEYS = frozenset({"shiny_watch_equipped", "athena_gloves_equipped"})


def workbook_keys(keys, search=False):
    """A spec's ``status_rebuild_keys`` (default) / ``companion_full_search_keys`` (``search=True``) as the frozen builder lists them."""
    drop = EXTRA_SEARCH_KEYS if search else EXTRA_STATUS_KEYS
    return type(keys)(k for k in keys if k not in drop)
