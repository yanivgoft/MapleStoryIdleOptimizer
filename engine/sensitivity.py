"""Sensitivity / stat values (class-agnostic core; FP-Mage and Dark Knight have specs): everything the workbook's ``Sensitivity`` sheet top section and
the Summary 'Marginal DPS & Stat Value' block provide, in plain Python and with the SAME numerics.

    from engine import sensitivity
    from engine.classes import fp_mage
    out = sensitivity.run(fp_mage, inputs)                               # everything
    out = sensitivity.run(fp_mage, inputs, which=["stats", "cdr"])       # a selection

``which`` (default all): ``"stats"`` (the continuous stats of the class's sweep, one +1 step each), ``"artifacts"`` (the 36 equip-toggle rows + ranking),
``"companions"`` (Companion Comparison table), ``"summon_time"`` (Summoning-Time potential-lines table), ``"cdr"`` (CDR milestone sweep).
The result is JSON-serialisable.  ``STAT_SWEEP`` / ``STAT_LIST`` / ``ARTIFACT_TOGGLES`` expose the (FP-Mage) sweep metadata for a UI; ``meta(class_module)`` /
``stat_sweep(class_module)`` the class's own.

Class-agnostic design: everything that differs between classes lives in a SPEC (``engine/sens_specs/<class>.py``, data: stat list, rebuild / search keys,
main-stat conversion, passive-level deltas, ...) and in the class module's ``model(inputs)``, which honours the ``inputs["_sens"]`` hooks of
``engine/common/sens.py``.  This module only builds the block inputs / hook values from a spec and combines the results; see engine/README.md
"How to add a class to the sensitivity engine".

How a "block" is evaluated
--------------------------
The workbook builds, per swept stat, a full private copy of the Calc + Summary pipeline with ONE Inputs value replaced by its New Value
(``build_stat_block``) and compares that block's Total DPS with the main sheet's.  Here a block is one more ``fp_mage.model()`` run on the
same inputs with that value replaced - plus the block-only terms the workbook adds (they are NOT part of a plain re-run; passed to the model
through ``inputs["_sens"]``, see ``fp_mage._build``):

* **flat_int / int_pct** - the main stat's FLAT-ATTACK channel (CLAUDE.md bug 7: 1 INT = 1 Attack, 1 LUK = 0.25 Attack, added before ATTACK%) next to the
  STAT_DAMAGE channel; ``compute()`` never applies it (the typed Flat ATTACK is assumed to include it).  ``mainstat_attack_delta``.
* **skill_lvl_2nd / 3rd / all** - Spell Mastery (Min Damage) and Magic Critical (Crit Rate / Crit Damage): their contribution is baked into the Inputs, only the
  DELTA of their level-dependent value is added in a block (the main sheet applies none of them).
* **crit_rate** with Book of Ancient equipped - its dependent Crit Damage (pct of the crit-rate change); **attack_speed** with Athena's Gloves / Bottle of Emotion
  equipped - their dependent Max Damage / Final Damage (all "baked into Inputs" artifacts keep their typed value, only the delta is modelled).
* **Equip toggles of the baked-in artifacts** (Book of Ancient, Athena's Gloves, Clear Spring Water, Soul Pouch, Lit Lamp, Star Rock, Cursed Doll, Shamaness
  Marble, Bottle of Emotion's Final Damage, Reindeer's base Def Pen) - equipping changes nothing in ``compute()`` (the user types the stat in), but the Equip row
  computes the what-if gain exactly as the blocks do (signed: adding when unequipped, removing when equipped).
* **Timeline strip**: every stat whose swept value changes something the Status/KO strip CONSUMES (``STATUS_REBUILD_KEYS``: cooldowns / buff durations / buff values -
  Skill Level Bonus, the per-cast weights' RELATIVE sizes - Skill / Basic Attack / Boss Damage, Crit Rate through Ring of Cycles, the artifacts that feed those) re-solves
  the strip; the others scale every damage row alike (or only the normal branch) and REUSE the main strip's timing factors and cast counts, which is exact
  (``tests/golden`` + /tmp checks: reuse == re-solve to ~1e-12 for every stat outside the set).
* **Baked-in Final Damage artifacts** (Cursed Doll, Lit Lamp, Clear Spring Water, Soul Pouch, Bottle of Emotion's Attack-Speed-dependent FD): their value is typed
  into Inputs!final_damage, so the what-if is a FACTOR on the whole product - 1 + x/100 when adding, 1/(1 + x/100) when removing (exact inverses), (1 + new)/(1 + old)
  for the Bottle's value when Attack Speed is swept (``sens["final_damage_factor"]``, applied to the live artifact bucket in ``fp_mage``).
* **Companion summon time**: blocks pin candidate 0 to the summon time the main sheet chose, except ``COMPANION_FULL_SEARCH_KEYS`` (they search the three
  candidates again).

Consequences of those semantics (reproduced on purpose, golden-checked; flagged per stat row as ``strip_reused`` / ``summon_time_pinned``):
(1) in Breakthrough / Hero Dungeon the blended RELATIVE gain is not the dollar delta of the two real states (bug 9, by design); (2) the workbook's companion chain
computes a permanent effect's uptime at a FRACTIONAL window (summoning time not a whole number of seconds) with a ~1.6e-9 relative precision loss ((a+b-|a-b|)/2 with
the 1e9 NEVER sentinel) - the engine is exact there.  (Until 2026-11-19 two more were listed here, both fixed: the level stats reused the main strip in KO contents,
and removing a baked-in Final Damage artifact was additive in the artifact bucket.)

The reported gain blends the two branches' RELATIVE growth by the time weight (CLAUDE.md bug 9): ``ratio = (1-w) boss_new/boss_base + w normal_new/normal_base``,
``DPS gain = Total x (ratio - 1)``, ``% gain = ratio x 100``, ``units per +1% = 1 / (% gain - 100)``.  Equip toggles use the direction-invariant convention of
CLAUDE.md item 15 (in blended content the equipped row inverts the per-branch removal ratios before blending: ``artifact_row``).
``inputs['typed_includes_artifacts']`` (the API default): the typed stats already contain the equipped artifacts, ``_Base`` evaluates every block on the character WITHOUT them
(``engine/typed_artifacts.py``), so the equip toggles are what-ifs on that base and Current / New of the stat table still show the typed numbers.  ``naive=True`` evaluates every block as a plain re-run instead (for documenting the differences; ``semantic_differences``).
"""
import math

from .classes import fp_mage as _fp
from .common import companion as comp_mod
from .common import factors
from .data import artifacts as AD
from . import artifacts as art_mod
from . import potentials
from . import typed_artifacts
from . import sens_specs

# ----------------------------------------------------------------------------------------------------------------------------------------------
# sweep metadata (key, label, type) - the builder's STAT_SWEEP, in the same order.  The module-level names are FP-Mage's (public API); every class has its own in its spec
# ----------------------------------------------------------------------------------------------------------------------------------------------
_FP_SPEC = sens_specs.get("fp_mage")
STAT_LIST = [tuple(e) for e in _FP_SPEC.stat_list]
STEP_TEXT = {"flat": "+1", "pct": "+1 percentage point", "level": "+1 skill level", "mult": "x1.01 (multiplicative source)",
             "dr150": "+1 combined by diminishing returns (factor 150)", "dr100": "+1 combined by diminishing returns (factor 100)"}
# what differs between a block and a plain re-run of compute() with the value changed (documentation, exposed to the UI)
SEMANTIC_NOTES = dict(_FP_SPEC.semantics)


def _spec_of(class_module_or_spec):
    """The SensSpec of a class module (by ``CLASS_ID``) or a spec itself; NotImplementedError when the class has none."""
    if hasattr(class_module_or_spec, "stat_list"):
        return class_module_or_spec
    cid = getattr(class_module_or_spec, "CLASS_ID", None)
    spec = sens_specs.get(cid)
    if spec is None:
        raise NotImplementedError(f"engine.sensitivity is not implemented for {cid!r} (no spec in engine/sens_specs)")
    return spec


def stat_sweep(class_module_or_spec):
    """The class's sweep metadata [{key, label, type, step, semantics}] (what the UI renders; the order of the builder's STAT_SWEEP stat entries)."""
    spec = _spec_of(class_module_or_spec)
    return [dict(key=k, label=lab, type=t, step=STEP_TEXT[t], semantics=spec.semantics.get(k)) for k, lab, t in spec.stat_list]


STAT_SWEEP = stat_sweep(_FP_SPEC)
ARTIFACT_TOGGLES = [dict(key=k, label=lab, rank=AD.ARTIFACT_RANK[k], effect=art_mod.effect_kind(k),
                         no_dps_effect=k in AD.ARTIFACT_NO_DPS_EFFECT, reason=AD.ARTIFACT_NO_DPS_EFFECT.get(k))
                    for k, lab in AD.ARTIFACT_LABELS.items()]

CDR_SWEEP_VALUES = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
# stat sweeps whose block re-solves the Status/KO strip / blocks that search the summon-time candidates again: FP-Mage's lists (public names; every class has its own in its spec)
STATUS_REBUILD_KEYS = list(_FP_SPEC.status_rebuild_keys)
COMPANION_FULL_SEARCH_KEYS = tuple(_FP_SPEC.companion_full_search_keys)
# "Companion Summoning Time Increase %" potential lines (boots), value per rarity tier (companion_model.POTENTIAL_LINE_TIERS: a copy, checked by the tests)
POTENTIAL_LINE_TIERS = [("Epic", 5), ("Unique", 8), ("Legendary", 12), ("Mystic", 20)]
POTENTIAL_MAX_LINES = 3


def potential_line_totals():
    """{total %: sorted descriptions} over every combination of 1-3 summoning-time lines that can share one potential (copy of companion_model's)."""
    out = {}
    for i, (tier, v) in enumerate(POTENTIAL_LINE_TIERS):
        vals = sorted({v} | ({POTENTIAL_LINE_TIERS[i - 1][1]} if i > 0 else set()), reverse=True)

        def rec(prefix, start, remaining):
            if prefix:
                out.setdefault(sum(prefix), set()).add(f"{tier}: " + "+".join(str(x) for x in prefix))
            if remaining:
                for j in range(start, len(vals)):
                    rec(prefix + [vals[j]], j, remaining - 1)
        rec([], 0, POTENTIAL_MAX_LINES)
    return {k: sorted(v) for k, v in sorted(out.items())}


COMPANION_POT_TOTALS = [0] + list(potential_line_totals().keys())

LEVEL_KEYS = ("skill_lvl_1st", "skill_lvl_2nd", "skill_lvl_3rd", "skill_lvl_4th", "skill_lvl_all")


# ----------------------------------------------------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------------------------------------------------
def _num(v):
    return 0 if v is None else v


def supports(class_module):
    """Does this class have a Sensitivity spec AND a ``model`` entry (what ``api.registry`` asks)?"""
    return sens_specs.get(getattr(class_module, "CLASS_ID", None)) is not None and callable(getattr(class_module, "model", None))


def meta(class_module):
    """Static metadata of a class's tables (what a UI needs without computing)."""
    spec = _spec_of(class_module)
    return dict(class_id=spec.class_id, parts=list(PARTS), stats=stat_sweep(spec), artifacts=list(ARTIFACT_TOGGLES), cdr_values=list(CDR_SWEEP_VALUES))


def _add(sens, key, value):
    """sens[key] += value (hooks of several passives / artifacts may share a key)."""
    sens[key] = sens.get(key, 0.0) + value


def _new_value(kind, cur, extra=0.0):
    """Override expression of the stat sweeps (override_expr_for).  ``extra``: the live additive source sharing a "mult" stat's bucket (``SensSpec.mult_extra``)."""
    if kind == "dr150":
        return (1 - (1 - cur / 150) * (1 - 1 / 150)) * 150
    if kind == "dr100":
        return (1 - (1 - cur / 100) * (1 - 1 / 100)) * 100
    if kind == "mult":
        return (((1 + (cur + extra) / 100) * 1.01) - 1) * 100 - extra
    return cur + 1


def _ratio_div(new, base):
    """IFERROR(new / base, 1)."""
    return new / base if base != 0 else 1.0


def resolve_stars(inputs):
    """``({artifact id: resolved star 0..5}, {artifact id: unlocked?})`` for ALL artifacts: the equipped slots' stars, else ``inputs['artifact_stars']``
    ({id: 0..5 | None | 'Not Unlocked'}), else the workbook's default by rank (Epic 5, Unique 3, Legendary Not Unlocked)."""
    raw_slots = {}
    for a in inputs.get("artifacts") or []:
        if a is None:
            continue
        key = a.get("key") if isinstance(a, dict) else a
        key = art_mod.LABEL_TO_KEY.get(key, key)
        if key in AD.ARTIFACT_LABELS and key not in raw_slots:
            raw_slots[key] = a.get("star") if isinstance(a, dict) else None
    given = inputs.get("artifact_stars") or {}
    stars, unlocked = {}, {}
    for key in AD.ARTIFACT_LABELS:
        if key in raw_slots:
            s = raw_slots[key]
        elif key in given:
            s = given[key]
        else:
            s = art_mod.default_star(key)
        nu = s is None or s == "Not Unlocked"
        stars[key] = 0 if nu else int(s)
        unlocked[key] = not nu
    return stars, unlocked


class _Base:
    """The evaluated main model + everything the blocks read from it (``class_module`` defaults to FP-Mage)."""

    def __init__(self, inputs, naive=False, class_module=None):
        self.module = class_module if class_module is not None else _fp
        self.spec = _spec_of(self.module)
        self.inputs = dict(inputs)
        self.inputs.pop("_sens", None)
        # typed stats that already include the equipped artifacts (inputs["typed_includes_artifacts"]): the blocks are what-ifs on the character WITHOUT them, derived
        # ONCE here (the flag is cleared in ``self.inputs`` so no block strips again); ``typed_inputs`` keeps what the user typed (the tables' Current / New columns)
        self.typed_inputs = self.inputs
        self.inputs, self.typed_info = typed_artifacts.strip_if_flagged(self.module, self.inputs)
        self.naive = naive
        self.model = self.module.model(dict(self.inputs, _sens={"want_comp_host": True}))
        m = self.model
        self.total = m.total_dps
        res = m.result()
        self.boss_only, self.normal_only = res["boss_dps"], res["normal_dps"]
        self.w = m.normal_weight
        self.eq = dict(m.eq)
        self.strip = (m.e1, m.e_engine) if (m.status_on and m.e1 is not None) else None
        cr = m.companion_result
        self.pin = (cr["s"], cr["E"]) if cr is not None else None
        self.stars, self.unlocked = self._resolve_stars()

    # ---- artifact stars (ArtifactsInput) ----
    def _resolve_stars(self):
        return resolve_stars(self.inputs)

    # ---- block evaluation ----
    def block(self, overrides=None, sens=None, rebuild=False, full_search=False):
        """Total / boss-only / normal-only DPS of one block: the main inputs with ``overrides`` and the block-only terms ``sens``."""
        d = dict(self.inputs)
        if overrides:
            d.update(overrides)
        if self.naive:
            d["_sens"] = {k: v for k, v in (sens or {}).items() if k == "eq"}
        else:
            s = dict(sens or {})
            if self.strip is not None and not rebuild:
                s["strip"] = self.strip
            if self.pin is not None and not full_search:
                s["comp_pin"] = self.pin
            if self.spec.pin_monster_defense:
                s["monster_defense"] = self.model.monster_defense
            if not self.spec.reindeer_dose_in_rows:
                s["def_pen_dose_rows"] = False
            if self.spec.passive_deltas_in_model:      # the class module adds ``own passive value - the main model's`` itself (Paladin, see SensSpec)
                s["passive_ref"] = self.model.passive_values
            d["_sens"] = s
        m = self.module.model(d)
        res = m.result()
        return res["total_dps"], res["boss_dps"], res["normal_dps"]

    def weighted_ratio(self, new_boss, new_normal):
        w = self.w
        return ((1 - w) * _ratio_div(new_boss, self.boss_only) + w * _ratio_div(new_normal, self.normal_only))

    def inverse_weighted_ratio(self, new_boss, new_normal):
        """The time-weighted blend of the INVERSE per-branch ratios (base / new): for an equip toggle measured as a REMOVAL (``new`` = the model without the artifact)
        this is the growth blend of the matching ADDING view, ``(1-w) boss_with / boss_without + w normal_with / normal_without``."""
        w = self.w

        def inv(new, base):
            return base / new if (base != 0 and new != 0) else 1.0
        return (1 - w) * inv(new_boss, self.boss_only) + w * inv(new_normal, self.normal_only)


# ----------------------------------------------------------------------------------------------------------------------------------------------
# stat table
# ----------------------------------------------------------------------------------------------------------------------------------------------
def _stat_sens(base, key, cur, new):
    """Block-only terms of a stat sweep (see the module docstring)."""
    inp, spec = base.inputs, base.spec
    sens = {}
    eq, stars = base.eq, base.stars
    ms = spec.mainstat
    sub_ratio = dict(ms.subs)
    if key in (ms.flat, ms.pct) or key in sub_ratio:
        flat, pct = _num(inp.get(ms.flat)), _num(inp.get(ms.pct))
        nf, np_ = (new, pct) if key == ms.flat else ((flat, new) if key == ms.pct else (flat, pct))
        delta = (nf * (1 + np_ / 100)) - (flat * (1 + pct / 100))
        if key in sub_ratio:                        # a sub stat: ratio x its own change (the main part of the delta is 0)
            delta = delta + sub_ratio[key] * (new - cur)
        sens["mainstat_attack_delta"] = delta
    if key in LEVEL_KEYS and not spec.passive_deltas_in_model:
        level = inp["level"]
        sl_old = factors.SkillLevels(level, *(_num(inp.get(k)) for k in LEVEL_KEYS))
        sl_new = factors.SkillLevels(level, *(new if k == key else _num(inp.get(k)) for k in LEVEL_KEYS))
        for p in spec.passive_levels:
            if p.unlock is not None and level < p.unlock:
                continue
            delta = sl_new.coeff_pct(p.base, p.fidx, True, p.step) - sl_old.coeff_pct(p.base, p.fidx, True, p.step)
            if delta:
                _add(sens, p.hook, delta)
    if key == "crit_rate" and "book_of_ancient" in eq:
        sens["crit_damage_delta"] = (sens.get("crit_damage_delta", 0.0)
                                     + art_mod.sv("book_of_ancient_crit_damage_pct_of_crit_rate", stars["book_of_ancient"]) / 100 * (new - cur))
    if key == "attack_speed":
        if "athena_gloves" in eq:
            sens["max_damage_delta"] = art_mod.sv("athena_gloves_max_damage_pct_of_attack_speed", stars["athena_gloves"]) / 100 * (new - cur)
        if "bottle_of_emotion" in eq:
            star = stars["bottle_of_emotion"]
            sens["final_damage_factor"] = (1 + _bottle_fd(star, new) / 100) / (1 + _bottle_fd(star, cur) / 100)
    if spec.extra_stat_sens is not None:
        sens.update(spec.extra_stat_sens(base, key, cur, new))
    return sens


_BAKED_FD = ("clear_spring_water", "soul_pouch", "cursed_doll", "lit_lamp", "bottle_of_emotion")


def _baked_fd_value(art, star, ct, mt, as_cur):
    """Final Damage % a baked-in Final Damage artifact grants in this content (the value typed into Inputs when equipped)."""
    sv = art_mod.sv
    if art == "clear_spring_water":
        return sv("clear_spring_water_final_damage", star) if ct in AD.GROWTH_DUNGEON_CONTENT_TYPES else 0
    if art == "soul_pouch":
        return sv("soul_pouch_final_damage", star) if mt == "pvp" else 0
    if art == "cursed_doll":
        return sv("cursed_doll_final_damage", star)
    if art == "lit_lamp":
        return sv("lit_lamp_final_damage", star) if ct == "World Boss" else 0
    return _bottle_fd(star, as_cur)


def _bottle_fd(star, attack_speed):
    """Bottle of Emotion's Attack-Speed-dependent Final Damage (artifact_bottle_of_emotion_final_damage_value_expr, equipped)."""
    per_point = art_mod.sv("bottle_of_emotion_final_damage_per_3pct_as", star) / 3
    cap = art_mod.sv("bottle_of_emotion_final_damage_cap", star)
    return min(cap, max(0, per_point * (attack_speed - 60)))


def _gain_fields(base, new_total, new_boss, new_normal):
    ratio = base.weighted_ratio(new_boss, new_normal)
    return ratio, base.total * (ratio - 1), ratio * 100


def stat_table(base):
    rows = []
    spec = base.spec
    for key, label, kind in spec.stat_list:
        cur = _num(base.inputs.get(key))
        extra = _num(getattr(base.model, dict(spec.mult_extra)[key])) if (kind == "mult" and key in dict(spec.mult_extra)) else 0.0
        new = _new_value(kind, cur, extra)
        sens = _stat_sens(base, key, cur, new)
        total, boss, normal = base.block({key: new}, sens, rebuild=key in spec.status_rebuild_keys, full_search=key in spec.companion_full_search_keys)
        ratio, gain, pct = _gain_fields(base, total, boss, normal)
        d = pct - 100
        # Current / New show what the user TYPED and would type (the model steps the stripped base; with the flag off the two are the same number)
        typed_cur = _num(base.typed_inputs.get(key))
        typed_new = new if typed_cur == cur else _new_value(kind, typed_cur, extra)
        rows.append(dict(key=key, label=label, type=kind, current=typed_cur + extra, new=typed_new + extra, baseline_total=base.total, new_total=total, dps_gain=gain,
                         pct_gain=pct, dps_per_1=gain, units_per_1pct=(1 / d if d != 0 else None), new_boss_total=boss, new_normal_total=normal,
                         boss_ratio=_ratio_div(boss, base.boss_only), normal_ratio=_ratio_div(normal, base.normal_only),
                         semantics=spec.semantics.get(key),
                         # the workbook's block reuses the main sheet's Status/KO strip unless the stat moves timing (so e.g. a buff's level bonus does not
                         # change the strip's buff values in KO / stun contents) and pins the main sheet's summon-time choice unless it searches again
                         strip_reused=(base.strip is not None and key not in spec.status_rebuild_keys and not base.naive),
                         summon_time_pinned=(base.pin is not None and key not in spec.companion_full_search_keys and not base.naive)))
    return dict(baseline_total=base.total, baseline_boss_total=base.boss_only, baseline_normal_total=base.normal_only, normal_weight=base.w, rows=rows)


# ----------------------------------------------------------------------------------------------------------------------------------------------
# artifact equip toggles
# ----------------------------------------------------------------------------------------------------------------------------------------------
def _toggle_sens(base, art, equipped, star):
    """(eq after the toggle, block-only terms) of one artifact's equip toggle: ``T`` = +1 adding / -1 removing."""
    inp = base.inputs
    t = -1 if equipped else 1
    eq = dict(base.eq)
    if equipped:
        eq.pop(art)
    else:
        eq[art] = star
    sens = {"eq": eq}
    spec = base.spec
    ct, mt = base.model.content_type, base.model.monster_type
    sv = art_mod.sv
    as_cur, cr_cur = _num(inp.get("attack_speed")), _num(inp.get("crit_rate"))
    if art == "book_of_ancient":
        direct = t * sv("book_of_ancient_crit_rate", star)
        sens["crit_rate_threshold_extra"] = direct
        pct = sv("book_of_ancient_crit_damage_pct_of_crit_rate", star) / 100
        if equipped:   # removing: strip the Crit Damage the REAL crit rate produced (Inputs value + the real Ring of Cycles / Rainbow contributions)
            rows = base.model.art_effects.rows
            # (a class with a live crit-rate source, e.g. Dark Knight's Lord of Darkness, exposes it as ``model.crit_rate_bonus``)
            sens["boa_crit_damage"] = (-pct, cr_cur + rows["roc_crit_rate"] + rows["rainbow_crit_rate"] + getattr(base.model, "crit_rate_bonus", 0.0))
        else:          # adding: the full dependent value from the resulting total crit rate
            sens["boa_crit_damage"] = (pct, None)
    elif art == "athena_gloves":
        direct = t * sv("athena_gloves_attack_speed", star)
        if spec.athena_as_in_aps:
            sens["attack_speed_extra"] = direct
        pct = sv("athena_gloves_max_damage_pct_of_attack_speed", star) / 100
        sens["max_damage_delta"] = t * pct * ((as_cur + direct) if not equipped else as_cur)
    elif art in _BAKED_FD:
        # baked-in Final Damage artifacts: the value typed into Inputs!final_damage multiplies the whole product, so the what-if is a factor on it:
        # (1 + x/100) when adding, its inverse when removing (see fp_mage ``final_damage_factor``)
        x = _baked_fd_value(art, star, ct, mt, as_cur)
        sens["final_damage_factor"] = 1 / (1 + x / 100) if equipped else 1 + x / 100
    elif art == "star_rock":
        sens["boss_damage_extra"] = t * sv("star_rock_boss_damage", star)
    elif art == "shamaness_marble":
        if spec.bdi_toggle_wired:
            sens["bdi_extra"] = t * sv("shamaness_marble_buff_duration_increase_pct", star)
    elif art == "reindeer_spear":
        sens["def_pen_dose"] = (t, sv("reindeer_spear_def_pen", star))
    if spec.extra_toggle_sens is not None:
        sens.update(spec.extra_toggle_sens(base, art, equipped, star))
    return eq, sens


def lines_potential_gains(base, lines, stats=None):
    """``{artifact id: Total Potential DPS Gain}`` of the potential lines in ``lines`` (``inputs["artifact_lines"]``: ``{artifact id: {"star"?, "lines": [(rarity, stat) |
    {rarity, stat}, ...]}}``): each line is priced at the character's own stat rates (this class's stats part at the current inputs, ``stats`` = that part when the caller
    has it already), the artifact's lines unlock with its RESOLVED star (equip slot, else ``artifact_stars``, else the default by rank; an entry's own ``star`` wins), the
    class's own ``potentials`` stat map applies.  This is the value ``artifact_table`` adds to the artifact's equip row (``artifact_potential_gain``): for an UNEQUIPPED
    artifact what equipping it brings besides its effect, for an EQUIPPED one what removing it loses besides its effect (its lines are real stats of the preset)."""
    stats = stats if stats is not None else stat_table(base)
    rates = {r["key"]: r["dps_gain"] for r in stats["rows"]}
    s2k = (base.spec.stat_to_key or {}).get("potentials")
    state = {}
    for art, entry in (lines or {}).items():
        if art not in AD.ARTIFACT_LABELS or not isinstance(entry, dict):
            continue
        norm = []
        for ln in entry.get("lines") or []:
            if isinstance(ln, dict):
                norm.append((ln.get("rarity") or potentials.DEFAULT_RARITY, ln.get("stat") or potentials.NONE_STAT))
            else:
                norm.append(tuple(ln))
        state[art] = {"star": entry["star"] if "star" in entry else base.stars[art], "lines": norm}
    if not state or not base.total > 0:
        return {}
    return {art: g for art, g in potentials.potential_gains(state, rates, base.total, s2k).items() if art in state}


def artifact_row(base, art, pot=0.0):
    """One row of the artifact table: the equip toggle of ``art`` (adding when unequipped, removing when equipped) with ``pot`` = the DPS of its potential lines."""
    label = AD.ARTIFACT_LABELS[art]
    equipped = art in base.eq
    star = base.stars[art]
    no_effect = art in AD.ARTIFACT_NO_DPS_EFFECT
    row = dict(key=art, label=label, rank=AD.ARTIFACT_RANK[art], effect=art_mod.effect_kind(art), no_dps_effect=no_effect,
               reason=AD.ARTIFACT_NO_DPS_EFFECT.get(art), equipped=equipped, star=star, unlocked=base.unlocked[art], potential_gain=pot,
               baked_into_inputs=art in art_mod.REFERENCE_ONLY or art == "reindeer_spear")
    hyp = None
    if no_effect:
        # the stat is not used by the model: the block is bit-for-bit the baseline; skip the evaluation
        ratio, new_total, dollar = 1.0, base.total, 0.0 + pot
        row.update(new_total=base.total, ratio=1.0)
    else:
        _eq, sens = _toggle_sens(base, art, equipped, star)
        key = f"{art}_equipped"
        total, boss, normal = base.block(None, sens, rebuild=key in base.spec.status_rebuild_keys, full_search=key in base.spec.companion_full_search_keys)
        ratio = base.weighted_ratio(boss, normal)
        if equipped and 0.0 < base.w < 1.0:
            # Blended content (Breakthrough / Hero Dungeon): the row measures REMOVAL, whose per-branch ratios r' = without / with are not invertible by the
            # time-weighted blend (bug 9: (1-w) r'_boss + w r'_normal is not 1 / the adding blend).  Invert each branch first, then blend: exactly the adding view
            # of the same real pair, so both directions report the SAME gain and % gain (2026-11-25).  Pure boss / pure normal content (w = 0 / 1) is unchanged
            # bit for bit (the two forms are algebraically equal there).
            ratio_add = base.inverse_weighted_ratio(boss, normal)
            hyp = total                                  # the hypothetical-UNEQUIPPED blended total (the block without the artifact)
            dollar = hyp * (ratio_add - 1) + pot
            row.update(new_total=total, ratio=ratio, ratio_adding=ratio_add)
        else:
            dollar = (-1 if equipped else 1) * base.total * (ratio - 1) + pot
            row.update(new_total=total, ratio=ratio)
    # direction-invariant % (CLAUDE.md item 15): divide by the HYPOTHETICAL-UNEQUIPPED total in both directions
    if equipped and hyp is not None:
        h = hyp - pot                                    # without the artifact its potential lines are gone too (pot = 0 when none are entered)
        pct = (h + dollar) / h * 100
    else:
        pct = base.total / (base.total - dollar) * 100 if equipped else (base.total + dollar) / base.total * 100
    row.update(dps_gain=dollar, pct_gain=pct)
    return row


def artifact_table(base):
    potential = base.inputs.get("artifact_potential_gain") or {}
    rows = [artifact_row(base, art, potential.get(art, 0.0)) for art in AD.ARTIFACT_LABELS]
    # ranking: unlocked artifacts only, best % gain first, ties by table position (the sheet's SUMPRODUCT + COUNTIFS rank)
    order = sorted((i for i, r in enumerate(rows) if r["unlocked"]), key=lambda i: (-rows[i]["pct_gain"], i))
    for pos, i in enumerate(order, 1):
        rows[i]["rank_position"] = pos
    for r in rows:
        r.setdefault("rank_position", None)
    return dict(baseline_total=base.total, rows=rows, ranking=[rows[i]["key"] for i in order])


# ----------------------------------------------------------------------------------------------------------------------------------------------
# companion tables
# ----------------------------------------------------------------------------------------------------------------------------------------------
def _companion_levels(base, level=None):
    """Level of each companion for the comparison table (the CompanionsInput sheet): ``inputs['companion_levels']`` {name: level}, else ``level`` /
    ``inputs['companion_comparison_level']`` for all of them, else the chosen companion's level (10 when none)."""
    given = base.inputs.get("companion_levels") or {}
    default = level if level is not None else base.inputs.get("companion_comparison_level")
    if default is None:
        default = base.model.companion_level or 10
    out = {}
    for name in comp_mod.COMPANIONS_ORDER:
        out[name] = int(given.get(name, default) or 0)
    return out


def companion_table(base, level=None):
    m = base.model
    host = m.comp_host
    pb, pn, w = m.pb_total, m.pn_total, base.w
    cur = m.companion_dps
    levels = _companion_levels(base, level)
    rows = []
    for name in comp_mod.COMPANIONS_ORDER:
        lvl = levels[name]
        r = comp_mod.run(host, name, lvl, m.summon_time_inc) if lvl >= 1 else comp_mod.run(host, "None", 0, m.summon_time_inc)
        ratio = (1 - w) * _ratio_div(pb + r["comp_boss_dps"], pb) + w * _ratio_div(pn + r["comp_norm_dps"], pn)
        rows.append(dict(name=name, level=lvl, unlocked=lvl >= 1, dps_gain=(base.total - cur) * (ratio - 1), pct_gain=(ratio - 1) * 100 + 100,
                         companion_dps=r["comp_blend_dps"], companion_boss_dps=r["comp_boss_dps"], companion_normal_dps=r["comp_norm_dps"]))
    order = sorted((i for i, r in enumerate(rows) if r["unlocked"]), key=lambda i: (-rows[i]["dps_gain"], i))
    for pos, i in enumerate(order, 1):
        rows[i]["rank_position"] = pos
    for r in rows:
        r.setdefault("rank_position", None)
    return dict(baseline_total=base.total, chosen=m.companion_choice, chosen_level=m.companion_level, current_companion_dps=cur,
                rows=rows, ranking=[rows[i]["name"] for i in order])


def summon_time_table(base):
    """Value of every Summoning-Time total the boots potential lines can add up to (rows of the Sensitivity 'Companion Summoning Time Increase %' table).
    b0 = the Inputs value WITHOUT the boots lines listed on PotentialCubes (``inputs['companion_potential_lines_pct']``, default 0) + Arwen's Glass Shoes."""
    m = base.model
    host = m.comp_host
    own_lines = _num(base.inputs.get("companion_potential_lines_pct"))
    b0 = max(0, _num(base.inputs.get("companion_summon_time_increase_pct")) - own_lines) + art_mod.summon_time_inc_pct(base.eq)
    choice, lvl = m.companion_choice, m.companion_level
    pb, pn, w = m.pb_total, m.pn_total, base.w
    teff = m.pvp_len if m.monster_type == "pvp" else m.fight_duration
    tb0 = 20 if m.content_type == "Breakthrough" else (30 if m.content_type == "Hero Dungeon" else 0)
    tbp = max(0.000001, (teff - tb0) if tb0 > 0 else 1)
    results = {x: comp_mod.run(host, choice, lvl, b0 + x) for x in COMPANION_POT_TOTALS}

    def dm(r):
        return pb * tbp + r["dmg_b"] + r["upl_b"] + r["ext"]

    def tm(r):
        return tbp + r["E"]
    r0 = results[0]
    rows = []
    for x in COMPANION_POT_TOTALS:
        r = results[x]
        row = dict(total_pct=x, summon_time_increase_pct=b0 + x, companion_dps=r["comp_blend_dps"], best_candidate=r["best"], summon_time_s=r["s"], window_s=r["W"])
        if tb0 > 0:
            row["avg_boss_dps_change"] = (((dm(r) / tm(r)) / (dm(r0) / tm(r0)) - 1) if dm(r0) != 0 and tm(r0) != 0 else 0.0)
            row["boss_phase_time_factor"] = tm(r) / tm(r0)
            row["boss_damage_change"] = (dm(r) / dm(r0) - 1) if dm(r0) != 0 else 0.0
        else:
            row["avg_boss_dps_change"] = row["boss_phase_time_factor"] = row["boss_damage_change"] = None
        row["normal_dps_change"] = ((pn + r["comp_norm_dps"]) / (pn + r0["comp_norm_dps"]) - 1) if (pn + r0["comp_norm_dps"]) != 0 else 0.0
        row["weighted_dps_change"] = ((1 - w) * _ratio_div(pb + r["comp_boss_dps"], pb + r0["comp_boss_dps"])
                                      + w * _ratio_div(pn + r["comp_norm_dps"], pn + r0["comp_norm_dps"]) - 1)
        rows.append(row)
    return dict(b0=b0, companion=choice, companion_level=lvl, boss_phase_content=tb0 > 0, rows=rows)


# ----------------------------------------------------------------------------------------------------------------------------------------------
# CDR milestones
# ----------------------------------------------------------------------------------------------------------------------------------------------
def cdr_table(base):
    rows = []
    prev = None
    for cdr in CDR_SWEEP_VALUES:
        total, _b, _n = base.block({"skill_cooldown_decrease": cdr}, {}, rebuild=True, full_search=True)
        rows.append(dict(cdr=cdr, total_dps=total, step_gain=(total - prev) if prev is not None else 0.0,
                         pct_gain=(0 if base.total == 0 else (total - base.total) / base.total * 100)))
        prev = total
    return dict(baseline_total=base.total, current_cdr=_num(base.inputs.get("skill_cooldown_decrease")), rows=rows,
                note="step function in fixed-duration content (exact cast counts); fixed-duration content only")


# ----------------------------------------------------------------------------------------------------------------------------------------------
# API
# ----------------------------------------------------------------------------------------------------------------------------------------------
PARTS = ("stats", "artifacts", "companions", "summon_time", "cdr")


def run(class_module, inputs, which=None, naive=False, companion_level=None):
    """Sensitivity tables of ``inputs`` (the ``<class>.compute`` input dict; extra optional keys: ``artifact_stars`` {id: star}, ``artifact_potential_gain``
    {id: DPS}, ``artifact_lines`` {id: {star?, lines}} (the potential lines entered on the Artifacts tab: priced here and added to that artifact's equip / removal row, see
    ``lines_potential_gains``), ``companion_levels`` {name: level}, ``companion_potential_lines_pct``).  ``which``: iterable of PARTS (default all).  JSON-serialisable.
    NotImplementedError for a class without a spec (``engine/sens_specs``)."""
    _spec_of(class_module)
    which = list(PARTS) if which is None else ([which] if isinstance(which, str) else list(which))
    for p in which:
        if p not in PARTS:
            raise ValueError(f"unknown part {p!r} (choose from {PARTS})")
    base = _Base(inputs, naive=naive, class_module=class_module)
    out = dict(class_id=class_module.CLASS_ID, content_type=base.model.content_type, baseline_total=base.total, baseline_boss_total=base.boss_only,
               baseline_normal_total=base.normal_only, normal_weight=base.w, semantics="naive" if naive else "workbook")
    if base.typed_info is not None and base.typed_info["notes"]:
        out["typed_notes"] = list(base.typed_info["notes"])        # e.g. typed_below_artifact:<id>: the typed value is smaller than that equipped artifact's effect
    if "stats" in which:
        out["stats"] = stat_table(base)
    if "artifacts" in which:
        lines = base.inputs.get("artifact_lines")
        if lines:
            gains = lines_potential_gains(base, lines, out.get("stats"))
            base.inputs["artifact_potential_gain"] = dict(base.inputs.get("artifact_potential_gain") or {}, **gains)
        out["artifacts"] = artifact_table(base)
    if "companions" in which:
        out["companions"] = companion_table(base, companion_level)
    if "summon_time" in which:
        out["summon_time"] = summon_time_table(base)
    if "cdr" in which:
        out["cdr"] = cdr_table(base)
    return out


def semantic_differences(class_module, inputs):
    """{stat key: (workbook-semantics DPS gain, plain re-run DPS gain)} - where the two differ (documentation helper)."""
    a = stat_table(_Base(inputs, class_module=class_module))["rows"]
    b = stat_table(_Base(inputs, naive=True, class_module=class_module))["rows"]
    return {x["key"]: (x["dps_gain"], y["dps_gain"]) for x, y in zip(a, b) if x["dps_gain"] != y["dps_gain"]}
