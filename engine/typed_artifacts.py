"""The typed stats INCLUDE the equipped artifacts (user decision 2026-11-25): "when an artifact is equipped it means it is already in your stats - the 40% came
from the glass shoes".  The values on the in-game preset page already contain every equipped artifact's bonus; the model, built when the workbooks assumed the
opposite, adds each live artifact's effect ON TOP of the typed value.  Entering the preset page numbers therefore counted every equipped artifact twice.

``strip(model_class, inputs)`` derives, from the typed values, the character WITHOUT the equipped artifacts' effects (the "base" B): the exact inverse of how each
effect composes into the typed stat.  The unchanged pipeline then adds the effects back live, so

* Total DPS of an equipped artifact is the DPS implied by the typed stats (the effect is counted once);
* an equip toggle (Sensitivity) is a what-if on that stripped base: removing = the model without the artifact, adding = with it.

The step is opt-in: ``inputs["typed_includes_artifacts"]`` (engine default False = exactly the workbooks' convention, so every workbook-pinned golden stays
bit-exact; the API fills it True when a request omits it).  ``ModelBase.__init__`` runs it, so ``compute`` / ``model`` and everything built on them (Sensitivity, cubes,
equipment, potentials) share one code path; ``sensitivity._Base`` strips ONCE and clears the flag so its blocks never strip again.

Which effects are in the typed stats (the effect's own composition into the typed stat is inverted):

=================================  ======================================================  =====================================================================
typed stat                         composition in every class model                        inverse (B from the typed T, effect a)
=================================  ======================================================  =====================================================================
companion_summon_time_increase_%   Arwen's Glass Shoes: ``typed + a`` (Companion host)       ``B = max(0, T - a)``
crit_rate                          ``typed + rainbow + ring of cycles (crit-rate mode)``     ``B = T - rainbow - roc`` (Ring of Cycles' mode follows B, see below)
crit_damage                        ``typed + rainbow + icy soul rock``                       ``B = T - sum``
boss_damage / normal_damage        ``typed + candle boss + sayram``                          ``B = T - sum``
skill_damage / basic_attack_damage ``typed + ring of cycles (crit rate >= 100 mode)``        ``B = T - a``
attack_pct                         NOT stripped (user, 2026-11-26): artifact and buff Attack% stack together in their own bucket, unrelated to the ATTACK % of the preset page
final_damage                       ``(1 + typed/100)(1 + art/100)``, art = candle x lava x horn x sealed bottle  ``B = (1 + T/100) / (1 + art/100) - 1``
damage                             Hexagon Necklace: ``(1 + typed/100)(1 + art/100)`` (Bishop: additive in ONE bucket)  ``B = (1 + T/100) / (1 + a/100) - 1`` (Bishop ``T - a``)
=================================  ======================================================  =====================================================================

No typed counterpart (nothing to strip, unchanged by the flag): Sealed Bottle's kill-stack Normal / Boss Monster Damage (during the fight), Shiny Watch and Mummydog's Bandages (Attack% only, never stripped; the watch's companion ramp is a during-the-fight effect), Chalice, Fire Flower, Secret Map's normal-monster Final Damage and Contract of Darkness (boss /
normal-branch-only terms), Peach Tree and Silver Pendant (enemy damage taken), Soul Contract (a % cooldown decrease; the typed field is in seconds), Reindeer's Spear's
boss / PvP extra Defense Penetration (its base Def Pen is already "baked into Inputs"), the reference-only artifacts (Book of Ancient, Athena's Gloves, Clear Spring
Water, Soul Pouch, Lit Lamp, Star Rock, Cursed Doll, Shamaness Marble, Bottle of Emotion's Final Damage: the user already types their stat by hand) and the seven
no-DPS-effect artifacts.

Effect VALUES come from a probe run of the class model on the summon-time-stripped inputs (``art_effects`` / ``art_ctx`` / ``art_pre`` of that model): time-averaged
effects (Hexagon stacks, Charm's duty cycle, Candle's window, Horn Flute's companion uptime, Old Music Box's content-type uptime, Rainbow's first 15 s, Ring of Cycles'
start-up) are stripped at the value the model adds, so ``strip`` followed by the live addition reproduces the typed value exactly.  None of those values depends on a
stripped stat except Ring of Cycles' crit-rate / excess-crit-rate mode (the threshold is the typed crit rate): it is resolved first, see ``_crit_rate``.

A typed value below the effect cannot be inverted: the base clamps at 0 and the note ``typed_below_artifact:<id>`` is reported (``info["notes"]``).
Ring of Cycles has a window of typed crit rates [100, 100 + its crit-rate bonus) that two different characters produce (crit-rate mode with a base below 100, or the
skill-damage mode with a base at or above 100): the crit-rate reading is taken (the conservative one: no skill / basic damage bonus) and ``typed_ambiguous:ring_of_cycles``
is reported.
"""
from . import artifacts as art_mod

FLAG = "typed_includes_artifacts"

# artifacts that are NOT stripped even though their effect has a typed counterpart: their bonus applies only DURING the fight (a stack, a duty cycle, a window, a start-up),
# so the preset page does not show it and it stays added on top of the typed value (user, 2026-11-26).  Rainbow Snail Shell and Ring of Cycles share the crit-rate inverse,
# so they must be exempt together.
STRIP_EXEMPT = frozenset({"hexagon_necklace", "charm_of_the_undead", "candle", "horn_flute", "old_music_box", "rainbow_snail_shell", "ring_of_cycles"})
assert ("rainbow_snail_shell" in STRIP_EXEMPT) == ("ring_of_cycles" in STRIP_EXEMPT), "the crit-rate pair is inverted jointly (Ring of Cycles' mode follows the base crit rate)"

# typed stat -> [(artifact id, name of the Effects row holding its value)]
ADD_ROWS = {
    "crit_damage": [("rainbow_snail_shell", "rainbow_crit_damage"), ("icy_soul_rock", "icy_soul_rock")],
    "boss_damage": [("candle", "candle_boss_damage"), ("sayrams_necklace", "sayrams_necklace_boss")],
    "normal_damage": [("sayrams_necklace", "sayrams_necklace_normal")],
    "skill_damage": [("ring_of_cycles", "roc_skill_damage")],
    "basic_attack_damage": [("ring_of_cycles", "roc_basic_attack_damage")],
}
FACTOR_ROWS = {
    "final_damage": [("candle", "candle_final_damage"), ("flaming_lava", "flaming_lava"), ("horn_flute", "horn_flute"), ("sealed_bottle", "sealed_bottle_final_damage")],
    "damage": [("hexagon_necklace", "hexagon_damage")],
}
SUMMON_KEY = "companion_summon_time_increase_pct"
CRIT_KEY = "crit_rate"
CRIT_ROWS = [("rainbow_snail_shell", "rainbow_crit_rate"), ("ring_of_cycles", "roc_crit_rate")]
# every artifact with at least one typed stat (the others never trigger the probe run)
STRIPPED_ARTIFACTS = frozenset({a for rows in list(ADD_ROWS.values()) + list(FACTOR_ROWS.values()) + [CRIT_ROWS] for a, _r in rows} | {"arwens_glass_shoes"}) - STRIP_EXEMPT


def damage_is_additive(model_class):
    """Does the class add the artifact Damage% (Hexagon) into the typed Damage bucket (Bishop) instead of multiplying it?"""
    return getattr(model_class, "TYPED_DAMAGE_COMPOSITION", "factor") == "additive"


def _num(v):
    return 0.0 if v is None else float(v)


def _copy_ctx(c, crit_rate):
    return art_mod.Ctx(c.content_type, c.monster_type, c.fight_duration, c.pvp_len, c.fixed_duration_active, aps=c.aps, startup=c.startup, crit_rate=crit_rate,
                       attack_speed=c.attack_speed, horn_uptime=c.horn_uptime)


def _crit_offset(probe, typed):
    """The class's live crit-rate source in Ring of Cycles' threshold (Night Lord / Shadower Dark Sight, Dark Knight Lord of Darkness: ``Ctx.crit_rate`` = typed + bonus; 0
    for every other class)."""
    return probe.art_ctx.crit_rate - typed


def _crit_rate(probe, eq, typed):
    """(base crit rate B, notes): the exact inverse of ``typed = B + rainbow + roc_crit_rate(B)`` where Ring of Cycles' crit-rate mode only exists while the threshold
    ``B + live bonus + rainbow`` is below 100 (otherwise it grants Skill / Basic Attack Damage instead)."""
    ctx, pre = probe.art_ctx, probe.art_pre
    off = _crit_offset(probe, typed)
    at0 = art_mod.Effects(eq, _copy_ctx(ctx, off), pre)          # base crit rate 0
    rainbow = at0.rows["rainbow_crit_rate"]
    notes = []
    if "ring_of_cycles" not in eq:
        base = typed - rainbow
        if base < 0:
            notes.append("typed_below_artifact:rainbow_snail_shell")
        return max(0.0, base), notes
    roc_cr = at0.rows["roc_crit_rate"]                      # the crit-rate mode value (0 when the threshold is already at 100 without B)
    b1 = typed - rainbow - roc_cr                            # crit-rate mode: B + off + rainbow < 100
    ok1 = roc_cr > 0 and b1 >= 0 and b1 + off + rainbow < 100
    b2 = typed - rainbow                                     # skill-damage mode: B + off + rainbow >= 100
    ok2 = b2 >= 0 and b2 + off + rainbow >= 100
    if ok1:
        if ok2:
            notes.append("typed_ambiguous:ring_of_cycles")
        return b1, notes
    if ok2:
        return b2, notes
    # typed is below rainbow + roc (a typed value too small for the equipped set): base 0 (the ring then sits in its crit-rate mode)
    notes += [f"typed_below_artifact:{a}" for a in ("rainbow_snail_shell", "ring_of_cycles") if a in eq]
    return 0.0, notes


def strip(model_class, inputs):
    """``model_class``: the class's ``_Model`` or its module (``model()``).  ``(stripped inputs, info)``.  ``stripped inputs`` = a copy of ``inputs`` with the flag cleared and the typed stats of the equipped artifacts' effects removed
    (the very ``inputs`` dict, flag cleared, when no equipped artifact has a typed stat); ``info`` = ``dict(notes=[...], typed={stat: typed}, base={stat: base},
    amounts={stat: {artifact id: value}})`` (empty dicts when nothing was stripped)."""
    out = dict(inputs)
    out[FLAG] = False
    info = dict(notes=[], typed={}, base={}, amounts={})
    eq = art_mod.resolve_slots(inputs.get("artifacts"))
    todo = [a for a in eq if a in STRIPPED_ARTIFACTS]
    if not todo:
        return out, info

    def record(key, typed, base, amounts):
        info["typed"][key], info["base"][key], info["amounts"][key] = typed, base, {a: v for a, v in amounts.items() if v}
        out[key] = base

    # (1) Arwen's Glass Shoes first: the companion's timing (so Horn Flute's uptime and every other effect value) depends on the EFFECTIVE summoning time
    # (typed + shoes), which stripping then re-adding leaves untouched
    shoes = art_mod.summon_time_inc_pct(eq) if "arwens_glass_shoes" not in STRIP_EXEMPT else 0
    if shoes:
        t = _num(inputs.get(SUMMON_KEY))
        if t < shoes:
            info["notes"].append("typed_below_artifact:arwens_glass_shoes")
        record(SUMMON_KEY, t, max(0.0, t - shoes), {"arwens_glass_shoes": shoes})
    # (2) one probe run of the model on those inputs: the effect values (aps / start-up / Horn Flute uptime ...) the final run will see
    build = model_class if isinstance(model_class, type) else model_class.model          # a model class (ModelBase) or a class module (Sensitivity / cubes)
    probe = build(dict(out))
    eff = probe.art_effects
    rows = eff.rows
    # (3) crit rate (Ring of Cycles' mode follows the base value), then the final Effects at the base crit rate
    if any(a in eq and a not in STRIP_EXEMPT for a, _r in CRIT_ROWS):
        typed = _num(inputs.get(CRIT_KEY))
        base, notes = _crit_rate(probe, eq, typed)
        info["notes"] += notes
        eff = art_mod.Effects(eq, _copy_ctx(probe.art_ctx, base + _crit_offset(probe, typed)), probe.art_pre)
        rows = eff.rows
        record(CRIT_KEY, typed, base, {a: rows[r] for a, r in CRIT_ROWS if a in eq})
    # (4) additive buckets
    for key, parts in ADD_ROWS.items():
        amounts = {a: rows[r] for a, r in parts if a in eq and a not in STRIP_EXEMPT}
        if not any(amounts.values()):
            continue
        record_add(info, out, key, _num(inputs.get(key)), amounts)
    # (5) multiplicative buckets (Damage: additive in Bishop's single bucket)
    for key, parts in FACTOR_ROWS.items():
        amounts = {a: rows[r] for a, r in parts if a in eq and a not in STRIP_EXEMPT}
        if not any(amounts.values()):
            continue
        t = _num(inputs.get(key))
        if key == "damage" and damage_is_additive(type(probe)):
            record_add(info, out, key, t, amounts)
            continue
        prod = 1.0
        for v in amounts.values():
            prod *= 1 + v / 100
        base = ((1 + t / 100) / prod - 1) * 100
        if base < 0:
            info["notes"] += [f"typed_below_artifact:{a}" for a, v in amounts.items() if v]
            base = 0.0
        info["typed"][key], info["base"][key], info["amounts"][key] = t, base, {a: v for a, v in amounts.items() if v}
        out[key] = base
    info["notes"] = sorted(set(info["notes"]))
    return out, info


def record_add(info, out, key, typed, amounts):
    base = typed - sum(amounts.values())
    if base < 0:
        info["notes"] += [f"typed_below_artifact:{a}" for a, v in amounts.items() if v]
        base = 0.0
    info["typed"][key], info["base"][key], info["amounts"][key] = typed, base, {a: v for a, v in amounts.items() if v}
    out[key] = base


def strip_if_flagged(model_class, inputs):
    """``(inputs to evaluate, info | None)``: the stripped inputs when ``inputs[FLAG]`` is set, else ``inputs`` unchanged and ``None``."""
    if not inputs.get(FLAG):
        return inputs, None
    return strip(model_class, inputs)
