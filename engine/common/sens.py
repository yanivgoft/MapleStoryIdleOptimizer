"""Shared plumbing of the Sensitivity engine (``engine/sensitivity.py``): the per-class SPEC type and the small helpers every class module uses to honour
the ``inputs["_sens"]`` block-only hooks.

A class that supports Sensitivity has

* a **spec** (``engine/sens_specs/<class>.py``: ``SPEC = SensSpec(...)``) - pure DATA: its stat sweep, the strip-rebuild / companion-search key lists, the main-stat
  flat-Attack conversion, the passive-skill level deltas, ...;
* a **model entry** ``engine/classes/<class>.py::model(inputs)`` that honours the ``_sens`` hooks below (every hook is a no-op without ``_sens``).

The hook vocabulary (keys of ``inputs["_sens"]``, all optional):

====================================  =====================================================================================================================
``eq``                                the equipped-artifact dict {id: star} to use instead of the Inputs slots (an equip toggle may exceed 4 slots)
``want_comp_host``                    build ``model.comp_host`` even when no companion / player stun is active (comparison tables)
``strip``                             ``(e1, e_engine)`` of the main model: re-use the Status/KO timeline strip instead of re-solving it
``comp_pin``                          ``(summon time s, boss-phase extension E)`` of the main sheet's chosen companion candidate: a block does not search again
``monster_defense``                   PvP opponent Defense fixed to the main sheet's value (the block's ``ib("monster_defense")`` is the baseline Inputs cell)
``mainstat_attack_delta``             flat-Attack channel of the main / sub stat (CLAUDE.md bug 7): ADDED to ATTACK as ``delta x (1 + ATTACK%/100)``
``min_damage_delta`` / ``max_damage_delta`` / ``skill_damage_delta`` / ``basic_attack_damage_delta`` / ``boss_damage_delta`` / ``final_damage_delta`` /
``crit_rate_delta`` / ``crit_damage_delta`` /
``attack_speed_extra``                additive deltas baked into the Inputs of passive skills / artifacts (level deltas, Athena's direct Attack Speed ...)
``as_bonus_extra``                    (Ice/Lightning Mage) a passive's level delta added to the BONUS side of the Attack Speed diminishing returns (MP Eater's flat Attack Speed), not the typed side
``attack_mult_delta``                 (Buccaneer) an Attack% passive's level delta (Dark Clarity: baked into Inputs!attack_pct): ADDED to the additive Attack% bucket next to the class's own live Attack% terms
``def_pen_delta``                     (Bowmaster) a Def Pen passive's level delta (Armor Break: baked into Inputs!def_pen): ADDED to the typed Def Pen, BEFORE Reindeer's dose (the block's ``def_pen_total_block``)
``passive_ref``                       (Paladin, ``SensSpec.passive_deltas_in_model``) the MAIN model's ``passive_values``: the class module adds ``own passive value - ref`` through its passive hooks
``def_pen_dose``                      ``(+1 | -1, magnitude %)``: Reindeer's Spear base Def Pen folded into / out of ``Inputs!def_pen`` (diminishing returns)
``def_pen_dose_rows``                 False: the dose reaches only the Reindeer boss-branch correction and the companion, not the rows' defense reduction (a workbook gap)
``bdi_extra``                         Shamaness Marble's Buff Duration Increase what-if (only for classes whose workbook block wires it)
``boss_damage_extra``                 Star Rock's baked-in Boss Damage what-if
``crit_rate_threshold_extra``         Book of Ancient's direct Crit Rate what-if (feeds Ring of Cycles' threshold AND the live crit rate)
``boa_crit_damage``                   ``(signed pct/100, reference crit rate | None)``: Book of Ancient's dependent Crit Damage what-if
``final_damage_factor``               multiplicative factor on the whole Final Damage product (baked-in Final Damage artifacts, both directions)
====================================  =====================================================================================================================
"""
from dataclasses import dataclass, field
from typing import Callable, Optional, Tuple


@dataclass(frozen=True)
class MainStat:
    """The main stat's flat-Attack channel (CLAUDE.md bug 7): 1 main = 1 Attack, each sub stat ``ratio`` Attack, added BEFORE ATTACK%.
    ``flat`` / ``pct``: the Inputs keys of the main stat's flat value and %; ``subs``: ((Inputs key, ratio), ...) - only sub stats that are sweep stats."""
    flat: str
    pct: str
    subs: Tuple[Tuple[str, float], ...] = ()


@dataclass(frozen=True)
class PassiveLevel:
    """A passive skill whose contribution is baked into the typed Inputs: a skill-level block only adds the DELTA of its level-dependent value.
    ``hook``: the ``_sens`` key receiving the delta; ``base`` (tenths of %), ``fidx`` (FactorTable index), ``step`` (job step 1..4) = the Skills-sheet row;
    ``unlock``: the character level the row unlocks at (None = always on)."""
    hook: str
    base: float
    fidx: int
    step: int
    unlock: Optional[int] = None


@dataclass(frozen=True)
class SensSpec:
    class_id: str
    stat_list: Tuple[Tuple[str, str, str], ...]                 # (key, label, type) in the builder's STAT_SWEEP order (stat entries only)
    mainstat: MainStat
    status_rebuild_keys: Tuple[str, ...]                         # the builder's STATUS_REBUILD_KEYS (stats AND "<artifact>_equipped" toggles)
    companion_full_search_keys: Tuple[str, ...]                  # the builder's COMPANION_FULL_SEARCH_KEYS
    summon_time_keys: Tuple[str, ...] = ()                       # the builder's SUMMON_TIME_KEYS (documentation / consistency check)
    passive_levels: Tuple[PassiveLevel, ...] = ()                # passives whose level deltas the skill_lvl_* blocks add
    semantics: dict = field(default_factory=dict)                # per-stat notes shown next to the table (what differs from a plain re-run)
    # the workbook block wires Shamaness Marble's equip what-if into the Buff Duration Increase (False: the block's helper cell is defined but unused,
    # the toggle is inert - DK / Paladin / Bowmaster builders)
    bdi_toggle_wired: bool = True
    # keep the PvP opponent's Defense at the main sheet's value in every block (the block's ``ib("monster_defense")`` reads the baseline Inputs cell, so a
    # swept Defense / Defense % never moves the opponent)
    pin_monster_defense: bool = False
    # how a baked-in Final Damage what-if enters the class's Final Damage: "factor" = a factor on the live artifact Final Damage bucket (the workbook's
    # ``fd_baked_factor``); "typed" = a factor on the TYPED Inputs Final Damage inside the class's additive Final Damage bucket (Hero / Marksman / Buccaneer: the block
    # retypes ``Inputs!final_damage`` via helper cells); documentation for the class module that implements ``final_damage_factor``
    baked_fd_form: str = "factor"
    # the workbook block applies the Reindeer's Spear Def Pen dose (equip what-if) to the rows' own defense reduction (FP-Mage, Hero, Bishop: True); False = only to
    # the boss-branch Reindeer correction and the companion (Dark Knight / Paladin builders: the block's K formula reads Inputs!def_pen, a workbook gap)
    reindeer_dose_in_rows: bool = True
    # the workbook block's Actions Per Second includes Athena's Gloves' direct Attack Speed (FP-Mage: ``attack_speed_total_block``; Dark Knight: False - its ``s_aps`` reads
    # ``attack_speed_with_delta``, which has no Athena term, so only the dependent Max Damage follows the toggle)
    athena_as_in_aps: bool = True
    # the class's potential-line / equipment-dropdown / artifact-potential stat -> sweep key maps (the builder's POTENTIAL_STAT_TO_SWEEP_KEY,
    # EQUIP_COMPARE_STAT_TO_SWEEP_KEY, ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY, POTENTIAL_SUB_STAT_PCT_LINES): {"cubes": {...}, "equipment": {...}, "potentials": {...},
    # "cubes_sub_stat_pct": {stat: (sweep key, Inputs key)}}; empty = the engine's FP-Mage / INT defaults.  Read by api/features.py (STAT_TO_KEY_BY_CLASS)
    stat_to_key: dict = field(default_factory=dict)
    # escape hatches for class-specific block-only terms: (base, key, cur, new) -> dict of extra ``_sens`` keys (stats) / (base, art, equipped, star) -> dict (toggles)
    extra_stat_sens: Optional[Callable] = None
    extra_toggle_sens: Optional[Callable] = None
    # "mult"-kind sweeps whose +1% must bump the FULL effective bucket (the builder's MULT_KIND_EXTRA_REF: a live additive source that shares the typed Final Damage's bucket,
    # e.g. Hero's Enrage / Combo Synergy): ((stat key, model attribute holding the extra %), ...).  Row ``current`` / ``new`` then include the extra, like the workbook's table
    mult_extra: Tuple[Tuple[str, str], ...] = ()
    # the CLASS MODULE computes the passive-level deltas itself (Paladin: the passives' F is time-averaged with Combat Orders' skill-level bonus, so the block's delta
    # also moves with its own Combat Orders uptime, not only with the swept skill level): the engine then skips the ``passive_levels`` loop of ``_stat_sens`` and hands the
    # main model's ``passive_values`` to every block as ``_sens["passive_ref"]`` (the model adds ``own value - ref`` through its passive hooks)
    passive_deltas_in_model: bool = False


# the stat sweep every class shares (the builders' STAT_SWEEP stat entries after the class's own main / sub stat rows, before its optional extra rows)
COMMON_STATS = (
    ('damage', 'DAMAGE %', 'pct'),
    ('damage_amp', 'DAMAGE_AMP %', 'pct'),
    ('boss_damage', 'BOSS_DAMAGE %', 'pct'),
    ('normal_damage', 'NORMAL_DAMAGE %', 'pct'),
    ('status_effect_damage', 'STATUS_EFFECT_DAMAGE %', 'pct'),
    ('final_damage', 'FINAL_DAMAGE % (multiplicative source)', 'mult'),
    ('min_damage', 'MIN_DAMAGE %', 'pct'),
    ('max_damage', 'MAX_DAMAGE %', 'pct'),
    ('crit_rate', 'CRIT_RATE %', 'pct'),
    ('crit_damage', 'CRIT_DAMAGE %', 'pct'),
    ('attack_speed', 'ATTACK_SPEED % (diminishing returns, factor 150)', 'dr150'),
    ('def_pen', 'DEF_PEN % (diminishing returns, factor 100)', 'dr100'),
    ('basic_attack_damage', 'BASIC_ATTACK_DAMAGE %', 'pct'),
    ('skill_damage', 'SKILL_DAMAGE %', 'pct'),
    ('skill_lvl_1st', 'Skill Level Bonus — 1st Job', 'level'),
    ('skill_lvl_2nd', 'Skill Level Bonus — 2nd Job', 'level'),
    ('skill_lvl_3rd', 'Skill Level Bonus — 3rd Job', 'level'),
    ('skill_lvl_4th', 'Skill Level Bonus — 4th Job', 'level'),
    ('skill_lvl_all', 'Skill Level Bonus — All Skills', 'level'),
    ('flat_attack', 'Flat ATTACK', 'flat'),
    ('attack_pct', 'ATTACK %', 'pct'),
    ('skill_cooldown_decrease', 'Skill Cooldown Decrease (seconds)', 'flat'),
    ('basic_attack_target_increase', 'Basic Attack Target Increase (flat)', 'flat'),
    ('buff_duration_increase_pct', 'Buff Duration Increase %', 'pct'),
    ('companion_summon_time_increase_pct', 'Companion Summoning Time Increase %', 'pct'),
)

def stat_list(head, tail=()):
    """A class's STAT_SWEEP stat entries: its main / sub stat (and Defense) rows, the common sweep, its optional extra rows."""
    return tuple(head) + COMMON_STATS + tuple(tail)


def standard_stat_to_key(main, main_flat, main_pct, sub=None, defense_pct=None):
    """The class's potential-line / equipment-dropdown / artifact-potential stat -> sweep key maps (``SensSpec.stat_to_key``): ``main`` = the main stat's
    potential-line name ("Str"), ``main_flat`` / ``main_pct`` its Inputs keys, ``sub`` = (name, Inputs key) of a sub stat that is a sweep stat, ``defense_pct`` =
    the sweep key of a "Defense %" potential line (classes that convert Defense into the main stat)."""
    cubes = {"Critical Rate %": "crit_rate", "Critical Damage %": "crit_damage", "Attack Speed %": "attack_speed", "Damage %": "damage",
             "Final Damage %": "final_damage", "Min Damage Multiplier %": "min_damage", "Max Damage Multiplier %": "max_damage", "Defense Penetration": "def_pen"}
    if defense_pct:
        cubes["Defense %"] = defense_pct
    cubes.update({"Basic Attack Damage %": "basic_attack_damage", "Skill Damage %": "skill_damage", "Skill Cooldown Decrease (seconds)": "skill_cooldown_decrease",
                  "Buff Duration Increase %": "buff_duration_increase_pct", "All Skill Level": "skill_lvl_all",
                  "Basic Attack Target Increase": "basic_attack_target_increase", f"{main} %": main_pct, main: main_flat})
    if sub:
        cubes[sub[0]] = sub[1]
    equipment = {"Main Stat (flat)": main_flat, "Main Stat %": main_pct}
    equipment.update(EQUIPMENT_STAT_TO_KEY)
    potentials = {"Main Stat %": main_pct}
    potentials.update(POTENTIAL_STAT_TO_KEY)
    return {"cubes": cubes, "cubes_sub_stat_pct": {f"{sub[0]} %": (sub[1], sub[1])} if sub else {}, "equipment": equipment, "potentials": potentials}


EQUIPMENT_STAT_TO_KEY = {
    'Attack (flat)': 'flat_attack',
    'Min Damage %': 'min_damage',
    'Max Damage %': 'max_damage',
    'Damage %': 'damage',
    'Critical Rate %': 'crit_rate',
    'Critical Damage %': 'crit_damage',
    'Boss Monster Damage %': 'boss_damage',
    'Normal Monster Damage %': 'normal_damage',
    'Defense Penetration %': 'def_pen',
    'Defense (flat)': 'defense',
    'Skill Level Bonus — 1st Job': 'skill_lvl_1st',
    'Skill Level Bonus — 2nd Job': 'skill_lvl_2nd',
    'Skill Level Bonus — 3rd Job': 'skill_lvl_3rd',
    'Skill Level Bonus — 4th Job': 'skill_lvl_4th',
    'Skill Level Bonus — All Skills': 'skill_lvl_all',
    'Final Damage %': 'final_damage',
    'Basic Attack Damage %': 'basic_attack_damage',
    'Skill Damage %': 'skill_damage',
    'Attack Speed %': 'attack_speed',
}
POTENTIAL_STAT_TO_KEY = {
    'Damage Taken Decrease %': None,
    'Defense %': None,
    'Accuracy': None,
    'Critical Rate %': 'crit_rate',
    'Min Damage Multiplier %': 'min_damage',
    'Max Damage Multiplier %': 'max_damage',
    'Boss Monster Damage %': 'boss_damage',
    'Normal Monster Damage %': 'normal_damage',
    'Status Effect Damage %': None,
    'Damage %': 'damage',
    'Defense Penetration %': 'def_pen',
}

# ----------------------------------------------------------------------------------------------------------------------------------------------
# hook helpers used by the class modules (identical expressions to the FP-Mage original: numerics unchanged)
# ----------------------------------------------------------------------------------------------------------------------------------------------
def def_pen_with_dose(def_pen, sens):
    """Reindeer's Spear equip toggle: one signed dose of its base Def Pen folded into the typed Inputs value (diminishing returns)."""
    if sens.get("def_pen_dose"):
        _dose, _mag = sens["def_pen_dose"]
        return 100 * (1 - (1 - def_pen / 100) * (1 - _mag / 100) ** _dose)
    return def_pen


def final_damage_bucket(agg_final_damage, sens):
    """Live artifact Final Damage bucket (in %) with a baked-in Final Damage what-if: a factor (1 + x/100) when adding the artifact, 1/(1 + x/100) when
    removing it, (1 + new)/(1 + old) for Bottle of Emotion's Attack-Speed-dependent value - on the whole product, so applied to ``1 + bucket/100``."""
    if sens.get("final_damage_factor") is not None:
        return ((1 + agg_final_damage / 100) * sens["final_damage_factor"] - 1) * 100
    return agg_final_damage


def boa_crit_damage_delta(sens, own_total_crit_rate):
    """Book of Ancient what-if: ``(sign x pct/100) x (reference crit rate | this setup's own total crit-rate sources)`` (0 without the hook)."""
    if sens.get("boa_crit_damage"):
        _k, _ref = sens["boa_crit_damage"]
        return _k * (_ref if _ref is not None else own_total_crit_rate)
    return 0.0
