"""Shadower: the DPS model of ``src/verify_shadower_workbook.py`` as a function of a plain inputs dict.

    from engine.classes import shadower
    result = shadower.compute(shadower.defaults("World Boss"))

``compute(inputs)`` is bit-identical to the verify script (same operations in the same order); the verify script stays the independent
reference, ``tests/golden/test_shadower.py`` compares the two (with no artifact equipped).  Artifact equip effects (``inputs["artifacts"]``, up to 4
slots) are ported in ``engine/artifacts.py`` (shared with the other classes; the Artifacts sheet of the builders is identical) and wired the way
``src/build_shadower_workbook.py`` wires them; the verify script does not model artifacts, so ``tests/golden/test_shadower_artifacts.py`` checks them
against the workbook itself (``tests/golden/shadower_artifacts_golden.json``, evaluated with ``formulas``).  The artifacts' enemy-damage-taken term
(Peach Tree / Silver Pendant) is the workbook's ``AGG_ENEMY_DMG_TAKEN`` inside Summary's ``R_MONSTER_DMG_BONUS`` (next to Venom's Weaken): it adds to BOTH the
Boss and the Normal Monster Damage terms and to the companion's ``boss_pct`` / ``norm_pct``; the explicit input ``artifact_monster_dmg_bonus`` (default 0) is a
manual additive on top of it, reported with the total under ``derived.artifact_monster_dmg_bonus``.

Inputs dict: the workbook's Inputs keys already resolved for the chosen content type (see ``schema()``), plus ``companion_level`` (the
level of the chosen companion, 0 = not unlocked).  A missing / ``None`` value reads as 0, exactly like a blank workbook cell.

Shadower specifics (all in the verify script): LUK main / DEX sub; Cruel Stab is the basic attack (5 lines, 6 from Lv136; target count
``6 + increase``) and gets what is left of the action rate after every action-costing row.  Phase Dash (Lv63) is the player's own stun (2 s, cooldown
23 s, cast on cooldown from the start): it feeds the Status Effect Damage / KO timeline and, in Breakthrough / Hero Dungeon, lengthens the boss
phase, so from Lv63 a "companion" result exists even with no companion chosen (choice "None": only the stun uplift).  Timeline-engine buffs: Dark
Sight (Attack) is an Attack% buff in the additive bucket with Steal / Meso Mastery; Into Darkness and Smokescreen are two separate multiplicative
Final Damage buffs, Smokescreen's strip effect scaled by ``1 + Into Darkness's steady-state average`` (``fd_cross_scale``).  Dark Sight (Crit
Rate) and Smokescreen's Lv113 Crit Damage +30 are passengers of those casts.  Steal (3 stacks), Meso Mastery (25 x (1 - exp(-0.75 x APS x 5))),
Nimble Feet (Attack Speed), Shadow Partner (average multiplier), Venom's Weaken (+15% damage taken from Lv82) and Murderous Intent are averaged.
Meso Explosion + Blood Money share one group (Blood Money triggers on every Meso Explosion cast); Dark Flare and Sudden Raid's DoT are DoT rows (hits from
the engine's effective cast count); Cruel Stab / Venom / Toxic Venom (20% proc, one roll per attack per enemy hit via the target-count blend over the
8 triggering rows) / Shadow Shifter (``incoming_hit_rate`` x 20%) are uniformly spread rows.  The companion's ``unit`` is Cruel Stab's per-percent
hit divided by Shadow Partner's average multiplier (user-confirmed).  No Defense Penetration source; ``monster_dmg_bonus`` (Venom's Weaken) joins both
the boss and the normal branch term.

Artifacts: the Attack% artifacts (Old Music Box, Secret Map, Reindeer's Spear, Alliance Badge, Bottle of Emotion, Charm's average) join Dark Sight's additive Attack%
bucket next to Steal / Meso Mastery (also the strip's constant term ``A0``); the Final Damage artifacts (Candle, Flaming Lava, Horn Flute) multiply on top of the
Final Damage input (Into Darkness / Smokescreen stay their own factors), Hexagon's Damage% is the (1 + Damage%) factor next to Shadow Partner, Peach Tree / Silver
Pendant add to both branches' Monster Damage terms, Ring of Cycles' / Rainbow Snail Shell's Crit Rate (threshold: Inputs + Dark Sight's Crit Rate) and Crit Damage
add to the crit totals (next to Dark Sight's Crit Rate / Smokescreen's Crit Damage), Reindeer's Spear / Contract of Darkness / the boss-only and normal-only Final
Damage artifacts are the boss / normal branch extras, Soul Contract's cooldown decrease reaches every cooldown through ``Fight.cd_extra_pct`` (buffs, Phase Dash's
stun, every skill row), Horn Flute's uptime comes from the stub run's candidate-0 timing (which carries Phase Dash's stun), Arwen's Glass Shoes adds to the
Summoning Time Increase.  Shadow Partner's average multiplier is divided out of the companion's ``unit`` with or without artifacts.
"""
import math

from .. import _src  # noqa: F401
from ..common import blend as blend_mod
from ..common import classapi
from ..common import companion as comp_mod
from ..common import content as content_mod
from ..common import damage as dmg
from ..common import factors
from ..common import fight as fight_mod
from ..common import model as model_mod
from ..common import schema as schema_mod
from ..common import sens as sens_mod
from ..common import status as status_mod
from ..data import shadower as D
from .. import artifacts as art_mod
import status_timeline as stl  # noqa: E402  (src/status_timeline.py through the shim)

CLASS_ID = "shadower"
CLASS_NAME = "Shadower"
STAT_IDENTITY = {"main": "LUK", "sub": "DEX"}

_MAIN_STAT_FIELDS = [
    schema_mod.field("flat_luk", "Flat LUK", "Main stats", "float", "flat", 0),
    schema_mod.field("luk_pct", "LUK %", "Main stats", "float", "%", 0),
    schema_mod.field("dex", "DEX", "Main stats", "float", "flat", 0),
]


def _lv(spec, level):
    """``(base, level, value from that level)`` -> the value at ``level``; a plain number stays as it is."""
    if isinstance(spec, tuple):
        return spec[2] if level >= spec[1] else spec[0]
    return spec


class _Model(model_mod.ModelBase):
    DATA = D

    # ------------------------------------------------------------------------------------------------------------------
    def target_count_mult(self, targets):
        """Damage%-FREE target-count blend for hit-count / proc-trigger rates (Toxic Venom rolls once per target hit)."""
        if self.monster_type == "pvp":
            return 1
        return (1 - self.normal_weight) + self.normal_weight * min(targets, self.fight.max_enemies_hit)

    def buff_pct(self, key):
        b = self.buffs[key]
        return self.coeff_pct(b["base"], b["fidx"], b["scales"], b["job_step"]) if self.unlocked(key) else 0.0

    def buff_uptime(self, cooldown, duration, casts=None):
        """Uptime of a cast buff.  ``casts`` = the Status/KO engine's cast count of that buff (None = the averaged model's own count)."""
        return self.fight.buff_uptime(cooldown, duration, True, casts)

    # ---- per-hit pipeline ----
    def hit_damage(self, coeff_pct_val, is_basic, maple_ratio=0.0):
        """Expected damage of one hit at coefficient % ``coeff_pct_val`` (masteries are already multiplied into it).  Boss/Normal Monster Damage% is
        applied by the caller."""
        base_damage = self.attack * (coeff_pct_val / 100)
        dmg_reduction = dmg.defense_reduction(self.monster_defense, self.def_pen)
        maple_mult = (1 + maple_ratio * self.maple_hero_pct / 100) if maple_ratio else 1.0
        final_mult = (1 + self.final_damage / 100) * (1 + self.art_final_damage / 100) * maple_mult
        source_pct = (self.basic_attack_damage + self.art_basic_attack_damage) if is_basic else (self.skill_damage + self.art_skill_damage)
        extra_mult = self.avg_buff_mult * self.shadow_partner_mult * (1 + self.art_joint_damage / 100)
        base_hit = (
            base_damage * (1 + self.stat_damage / 100) * (1 + self.damage / 100)
            * (1 + self.damage_amp / 100) * dmg_reduction * final_mult * (1 + source_pct / 100) * extra_mult
        )
        return dmg.expected_hit(base_hit, self.min_damage, self.max_damage, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate,
                                self.crit_damage + self.crit_damage_bonus + self.art_crit_damage)

    def boss_mult(self, mastery_boss):
        """Boss branch multiplier of a row (1 in PvP) - the per-cast boss weight of the timeline strip; the boss-only artifact extras are part of it
        (the workbook's Calc column Y carries them)."""
        if self.monster_type == "pvp":
            return 1.0 * self.extra_boss
        return (1 + (self.boss_damage + mastery_boss + self.monster_dmg_bonus + self.art_boss_damage + self.art_enemy_taken) / 100) * self.extra_boss

    def branch_pair(self, key, rate_boss, rate_normal, hd_, mastery_boss, mastery_normal, targets):
        """Boss and normal DPS of one row (before weighting): rate x hit x its own branch multiplier x the row's timing factor."""
        fb, fn = self.timing_factors(key)
        # outside the Boss/Normal Damage% buckets the artifacts add boss-only / normal-only multipliers (Reindeer's Spear, Contract of Darkness, branch Final
        # Damage), applied even in PvP (extra_boss / extra_norm are exactly 1.0 with no such artifact equipped)
        if self.monster_type == "pvp":
            b, n = 1.0 * self.extra_boss, 1.0 * self.extra_norm
        else:
            b = (1 + (self.boss_damage + mastery_boss + self.monster_dmg_bonus + self.art_boss_damage + self.art_enemy_taken) / 100) * self.extra_boss
            n = ((1 + (self.normal_damage + mastery_normal + self.monster_dmg_bonus + self.art_normal_damage + self.art_enemy_taken) / 100)
                 * min(targets, self.fight.max_enemies_hit) * self.extra_norm)
        return self.ledger.put(key, rate_boss, rate_normal, hd_, b, n, fb, fn)

    def blended(self, pair):
        return (1 - self.normal_weight) * pair[0] + self.normal_weight * pair[1]

    # ------------------------------------------------------------------------------------------------------------------
    def _build(self, inp):
        ct = self.read_content(inp)
        sens = self.sens
        level = self.level
        content_type = self.content_type
        monster_type = self.monster_type
        normal_weight = self.normal_weight
        fight_duration = self.fight_duration
        fixed_duration_active = self.fixed_duration_active
        coeff_pct = self.coeff_pct
        gated = self.gated
        unlocked = self.unlocked
        flat_attack, attack_pct = inp("flat_attack"), inp("attack_pct")
        self.attack = dmg.attack_value(flat_attack, attack_pct)
        if sens.get("mainstat_attack_delta"):      # Sensitivity: the main/sub stat's flat-Attack channel (bug 7), applied before ATTACK%
            self.attack += sens["mainstat_attack_delta"] * (1 + attack_pct / 100)
        flat_luk, luk_pct, dex = inp("flat_luk"), inp("luk_pct"), inp("dex")
        self.stat_damage = (flat_luk * (1 + luk_pct / 100)) * 0.01 + dex * 0.0025
        self.damage = inp("damage")
        self.damage_amp = inp("damage_amp")
        self.boss_damage = boss_damage = inp("boss_damage")
        self.normal_damage = normal_damage = inp("normal_damage")
        self.status_effect_damage = status_effect_damage = inp("status_effect_damage")
        self.final_damage = inp("final_damage") + sens.get("final_damage_delta", 0.0)      # (+ Shadower Instinct's / Shadow Shifter's level deltas, Sensitivity only)
        self.min_damage = inp("min_damage") + sens.get("min_damage_delta", 0.0)      # (+ Dagger Mastery's level delta, Sensitivity only)
        self.max_damage = inp("max_damage") + sens.get("max_damage_delta", 0.0)      # (+ Dagger Expert's level delta / Athena's Gloves' dependent Max Damage, Sensitivity only)
        self.crit_rate = crit_rate = inp("crit_rate") + sens.get("crit_rate_threshold_extra", 0.0) + sens.get("crit_rate_delta", 0.0)   # (+ Book of Ancient what-if / Critical Edge's level delta)
        self.crit_damage = crit_damage = inp("crit_damage") + sens.get("crit_damage_delta", 0.0)      # (+ Critical Edge's level delta / Book of Ancient's dependent Crit Damage, Sensitivity only)
        attack_speed_base = inp("attack_speed")
        self.def_pen = def_pen = sens_mod.def_pen_with_dose(inp("def_pen"), sens)      # (Reindeer's Spear equip what-if, Sensitivity only)
        self.basic_attack_damage = inp("basic_attack_damage") + sens.get("basic_attack_damage_delta", 0.0)   # (+ Physical Training's level delta, Sensitivity only)
        self.skill_damage = inp("skill_damage") + sens.get("skill_damage_delta", 0.0)      # (+ Dagger Expert's level delta, Sensitivity only)
        basic_attack_target_increase = inp("basic_attack_target_increase")
        buff_duration_increase_pct = inp("buff_duration_increase_pct") + sens.get("bdi_extra", 0.0)     # (+ Shamaness Marble what-if, Sensitivity only)
        summon_time_inc = inp("companion_summon_time_increase_pct")
        incoming_hit_rate = inp("incoming_hit_rate")
        self.pvp_len = pvp_len = inp("pvp_fight_length") or content_mod.DEFAULT_PVP_FIGHT_LENGTH
        fight = self.fight = fight_mod.Fight(ct, pvp_len, inp("skill_cooldown_decrease"), buff_duration_increase_pct,
                                             inp("max_enemies_hit"))
        max_enemies_hit = fight.max_enemies_hit

        # ---- artifacts (equip effects): slots, the early quantities (Attack% bucket / Hexagon / Charm) and Soul Contract's cooldown decrease ----
        self.eq = eq = sens["eq"] if "eq" in sens else art_mod.resolve_slots(inp.raw("artifacts"))   # (Sensitivity: an equip-toggle what-if may exceed 4 slots)
        actx = self.art_ctx = art_mod.Ctx(content_type, monster_type, fight_duration, pvp_len, fixed_duration_active,
                                          crit_rate=crit_rate, attack_speed=attack_speed_base)
        pre = self.art_pre = art_mod.Pre(eq, actx)
        # Arwen's Glass Shoes: the companion's effective Summoning Time Increase % = the Inputs value + the artifact (every use below)
        summon_time_inc += art_mod.summon_time_inc_pct(eq)
        fight.cd_extra_pct = art_mod.soul_contract_pct(eq, content_type)
        # Attack% the artifacts add to Dark Sight's additive bucket (AGG_ATTACK_PCT incl. Charm's average); ``art_a0`` = the same without Charm (the strip's A0
        # next to Steal / Meso Mastery, and the companion's k1)
        # (+ Channel Karma's / Shadow Shifter's Attack% level delta: Sensitivity only, it joins the same additive bucket, the strip's A0 and the companion's k1)
        attack_mult_delta = sens.get("attack_mult_delta", 0.0)
        self.art_attack_pct = art_attack_pct = pre.agg_attack_pct + attack_mult_delta
        art_a0 = pre.a0 + attack_mult_delta
        # live artifact terms of the damage pipeline; zero / neutral until the full effects are known (after the buff-casting startup delay)
        self.art_final_damage = self.art_joint_damage = self.art_skill_damage = self.art_basic_attack_damage = 0.0
        self.art_boss_damage = self.art_normal_damage = self.art_crit_rate = self.art_crit_damage = self.art_enemy_taken = 0.0
        self.extra_boss = self.extra_norm = 1.0
        self.ph_b = self.ph_n = 1.0
        self.ledger = blend_mod.BranchLedger(normal_weight)
        eff_cooldown = fight.eff_cooldown
        eff_duration = fight.eff_duration
        capped_window = fight.capped_window
        buff_uptime = self.buff_uptime
        target_count_mult = self.target_count_mult
        # the artifacts' enemy-damage-taken term (Peach Tree / Silver Pendant, the workbook's AGG_ENEMY_DMG_TAKEN inside R_MONSTER_DMG_BONUS) plus the explicit
        # manual hook ``artifact_monster_dmg_bonus`` (default 0): set once the effects are known (below); it is part of ``art_enemy_taken``
        artifact_monster_dmg_hook = inp("artifact_monster_dmg_bonus")
        self.artifact_monster_dmg_bonus = artifact_monster_dmg_hook

        basic_lvl = self.sl.input_level(4)
        self.skill_coefficient_base = D.CRUEL_STAB_BASE * factors.get_factor(basic_lvl, 21) / 1000

        cruel_stab_mastery = gated(D.CRUEL_STAB_MASTERY)
        cruel_stab_boss_mastery = gated(D.CRUEL_STAB_BOSS_MASTERY)
        hits0, hits_lvl, hits1 = D.CRUEL_STAB_HITS
        cruel_stab_hits = hits1 if level >= hits_lvl else hits0

        # buff table with the level-dependent Dark Sight duration resolved
        self.buffs = BUFFS = {k: dict(v, duration=_lv(v["duration"], level)) for k, v in D.BUFFS.items()}
        dark_sight_duration = BUFFS["DARK_SIGHT_ATK"]["duration"]

        buff_pct = self.buff_pct
        dsc_pct, dsa_pct, id_pct, ss_pct = (buff_pct("DARK_SIGHT_CRIT"), buff_pct("DARK_SIGHT_ATK"), buff_pct("INTO_DARKNESS"),
                                            buff_pct("SMOKESCREEN"))

        # ---- Nimble Feet / Steal / Meso Mastery / Actions per second (none of them is engine-timed) ----
        nimble_feet_avg = buff_pct("NIMBLE_FEET") * buff_uptime(60, 15) if unlocked("NIMBLE_FEET") else 0.0
        as_bonus = nimble_feet_avg
        self.as_bonus = as_bonus
        self.actions_per_second = actions_per_second = dmg.actions_per_second(attack_speed_base + sens.get("attack_speed_extra", 0.0), as_bonus)   # (+ Agile Daggers' level delta / Athena's Gloves what-if, Sensitivity only)
        st = D.STEAL
        steal_pct = coeff_pct(st["base"], st["fidx"], True, st["step"]) if unlocked("STEAL") else 0.0
        self.steal_avg = steal_avg = steal_pct * st["stacks"] if unlocked("STEAL") else 0.0
        mm = D.MESO_MASTERY
        self.meso_mastery_avg = meso_mastery_avg = (
            (mm["attack"] * (1 - math.exp(-mm["rate"] * actions_per_second * mm["window"]))) if unlocked("MESO_MASTERY") else 0.0)

        # ---- Maple Hero (Shadower), Shadow Partner ----
        mh = D.MAPLE_HERO
        self.maple_hero_pct = maple_hero_pct = (coeff_pct(mh["base"], mh["fidx"], True, mh["step"])
                                                if unlocked("MAPLE_HERO_SHADOWER") else 0.0)
        sp = D.SHADOW_PARTNER
        sp_pct = (coeff_pct(sp["base"], sp["fidx"], True, sp["step"]) * (1 + gated(sp["gated"]) / 100)
                  if unlocked("SHADOW_PARTNER") else 0.0)
        sp_maple_ratio = D.MAPLE_HERO_SHADOWER_RATIOS["SHADOW_PARTNER"]
        sp_pct_with_maple = sp_pct * (1 + sp_maple_ratio * maple_hero_pct / 100)
        self.shadow_partner_mult = shadow_partner_mult = (
            1 + (sp_pct_with_maple * 1.0 * sp["proc"] / 100) / 100 if unlocked("SHADOW_PARTNER") else 1.0)

        # ---- Meso / Blood Money stacks, Assassinate (Murderous Intent) ----
        meso_chance = _lv(D.MESO_CHANCE, level)
        cd_meso = D.MESO_EXPLOSION_COOLDOWN
        self.meso_stack_avg = meso_stack_avg = min(D.MESO_STACK_MAX, meso_chance * actions_per_second * eff_cooldown(cd_meso, True))
        self.bm_stack_avg = bm_stack_avg = min(D.BLOOD_MONEY_STACK_MAX,
                                               D.BLOOD_MONEY_CHANCE * meso_chance * actions_per_second * eff_cooldown(cd_meso, True))
        asn = D.ASSASSINATE
        assassinate_eff_cd = eff_cooldown(asn["cooldown"], True)
        assassinate_rate_q = 1 / assassinate_eff_cd
        bm_rate_q = 1 / eff_cooldown(cd_meso, True)
        self.murderous_intent_mult = murderous_intent_mult = (
            1 + min(1, (bm_rate_q * asn["murderous_intent_trigger"]) / assassinate_rate_q) if unlocked("ASSASSINATE") and unlocked("BLOOD_MONEY")
            else (1.0 if unlocked("ASSASSINATE") else 0.0))
        fold_lvl, fold_pct = asn["fold"]
        asn_pct = (((coeff_pct(asn["base"], asn["fidx"], True, asn["step"]) + (fold_pct if level >= fold_lvl else 0))
                    + asn["finisher_share"] * coeff_pct(asn["finisher_base"], asn["finisher_fidx"], True, asn["finisher_step"]) * murderous_intent_mult)
                   if unlocked("ASSASSINATE") else 0.0)
        bm_target_mult = next((m for lvl, m in D.BLOOD_MONEY_TARGET_MULT if level >= lvl), 1)

        # ---- damage rows (level-resolved) ----
        SKILLS = self.skills = {}
        for key, t in D.DAMAGE_SKILLS.items():
            if key == "ASSASSINATE":
                pct = asn_pct
            elif t["mastery"]:
                pct = coeff_pct(t["base"], t["fidx"], True, t["step"]) * (1 + gated(t["mastery"]) / 100)
            else:
                pct = coeff_pct(t["base"], t["fidx"], True, t["step"])
            targets = t["targets"]
            if targets == "meso_stack_avg":
                targets = meso_stack_avg
            elif targets == "blood_money":
                targets = bm_stack_avg * bm_target_mult
            s = dict(cooldown=_lv(t["cooldown"], level), hits=_lv(t["hits"], level), pct=pct, costs_action=t["costs_action"], targets=targets)
            if "icd" in t:
                s["icd"], s["window"] = _lv(t["icd"], level), t["window"]
            s["mastery_boss"] = 0.0
            s["mastery_normal"] = 0.0
            s["maple_ratio"] = D.MAPLE_HERO_SHADOWER_RATIOS.get(key, 0.0)
            SKILLS[key] = s
        cruel_stab_targets = D.CRUEL_STAB_TARGET_BASE + basic_attack_target_increase

        # ---- Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`) ----
        choice, c_level = comp_mod.read_choice(inp)
        self.companion_choice, self.companion_level = choice, c_level

        pl_on = self.pl_on = any(unlocked(e["key"]) and level >= e["min_level"] for e in D.PLAYER_STUN)
        stun_info = comp_mod.stun_probe(ct, fight, pvp_len, choice, c_level, summon_time_inc)
        self.hasstun = hasstun = bool(stun_info and stun_info.get("hasstun")) or pl_on
        ko = content_mod.ko_windows(fight_duration)
        self.status_on = status_on = fixed_duration_active and normal_weight == 0 and (content_type in ko or hasstun)
        startup_plain = (sum(1 for k in BUFFS if BUFFS[k]["costs_action"] and unlocked(k)) / actions_per_second) if fixed_duration_active else 0.0
        t0_pl = 0.0 if status_on else startup_plain
        self.pst = pst = [dict(id=e["id"], typ=e["typ"], cd=eff_cooldown(e["cd"], True), dur=e["dur"], p=e["p"],
                               on=unlocked(e["key"]) and level >= e["min_level"], t0=t0_pl, tick=e["tick"], win=e["win"])
                          for e in D.PLAYER_STUN]
        stun_info, stun_pin = comp_mod.stun_windows(ct, fight, pvp_len, pst, choice, c_level, summon_time_inc, sens)
        self.stf_b = stun_pin["stunfracB"]
        self.stf_n = stun_pin["stunfracN"]
        self.engine_n = ENGINE_N = {}
        E_ENGINE = None
        self.phi_rows = {}
        self.phi_unif = 1.0
        E_FS = {}
        engine_bbuff_mean = None
        e1 = None
        if status_on:
            # (the verify script raises KeyError here when no companion is chosen and Phase Dash is locked, i.e. level < 63 in a KO content: the
            # companion model's early return carries no stun_vector.  The engine reads that as "no companion stun".)
            comp_stun = stun_info["stun_vector"](stl.NB_MAX) if "stun_vector" in stun_info else [0.0] * stl.NB_MAX
            stun_vec = [min(1.0, a + b) for a, b in zip(comp_stun, stl.pl_stun_vector([dict(e, t0=0.0) for e in pst], fight_duration, stl.NB_MAX))]
            ds_dur = eff_duration(BUFFS["DARK_SIGHT_ATK"]["duration"])
            ds_cd = eff_cooldown(BUFFS["DARK_SIGHT_ATK"]["cooldown"], True)
            id_dur = eff_duration(BUFFS["INTO_DARKNESS"]["duration"])
            id_cd = eff_cooldown(BUFFS["INTO_DARKNESS"]["cooldown"], True)
            ss_dur = eff_duration(BUFFS["SMOKESCREEN"]["duration"])
            ss_cd = eff_cooldown(BUFFS["SMOKESCREEN"]["cooldown"], True)
            # Smokescreen's strip effect carries Into Darkness's steady-state average (mean-field cross term, fd_cross_scale in the builder)
            cross = 1 + (id_pct * min(1.0, id_dur / id_cd) / 100 if unlocked("INTO_DARKNESS") else 0.0)
            buffs = [dict(id="DS", kind="atk", F=dsa_pct, dur=ds_dur, cd=ds_cd, on=unlocked("DARK_SIGHT_ATK")),
                     dict(id="ID", kind="ramp", F=id_pct, dur=min(id_dur, id_cd), cd=id_cd, on=unlocked("INTO_DARKNESS"), p0=1, p1=1, ramp_t=1, dur0=1),
                     dict(id="SS", kind="ramp", F=ss_pct * cross, dur=min(ss_dur, ss_cd), cd=ss_cd, on=unlocked("SMOKESCREEN"), p0=1, p1=1, ramp_t=1,
                          dur0=1)]
            eng_host = dict(T=fight_duration, S=status_effect_damage, ko=ko.get(content_type, []), hex_v=pre.hex_v, hex_period=20, hex_max=3,
                            A0=steal_avg + meso_mastery_avg + art_a0, charm_v=pre.charm_val, hex_avg=pre.hex_avg, c_slot=0.0, stun=stun_vec,
                            buffs=buffs, groups=[])
            e1 = sens["strip"][0] if "strip" in sens else stl.solve(eng_host)   # pass 1: the buff schedule (independent of the skill weights); Sensitivity may reuse the main strip
            engine_bbuff_mean = e1["Bbuff_mean"]
            for row, pfx in D.STATUS_CAST_PREFIX.items():
                if pfx.startswith("buff."):
                    ENGINE_N[row] = e1["buffs"][pfx[5:]]["n"]

        self.e1 = e1

        # ---- Global helper bonuses (with the engine on, the buff rows' uptimes use the engine's cast counts) ----
        self.dark_sight_crit_avg = dark_sight_crit_avg = (
            dsc_pct * buff_uptime(25, dark_sight_duration, casts=ENGINE_N.get("DARK_SIGHT_CRIT")) if unlocked("DARK_SIGHT_CRIT") else 0.0)
        self.dark_sight_atk_avg = dark_sight_atk_avg = (
            dsa_pct * buff_uptime(25, dark_sight_duration, casts=ENGINE_N.get("DARK_SIGHT_ATK")) if unlocked("DARK_SIGHT_ATK") else 0.0)
        self.into_darkness_avg = into_darkness_avg = (
            id_pct * buff_uptime(40, 13, casts=ENGINE_N.get("INTO_DARKNESS")) if unlocked("INTO_DARKNESS") else 0.0)
        self.smokescreen_avg = smokescreen_avg = (
            ss_pct * buff_uptime(45, 20, casts=ENGINE_N.get("SMOKESCREEN")) if unlocked("SMOKESCREEN") else 0.0)
        self.crit_rate_bonus = dark_sight_crit_avg
        self.monster_dmg_bonus = D.MONSTER_DMG_BONUS[1] if level >= D.MONSTER_DMG_BONUS[0] else 0
        sm_lvl, sm_crit = D.SMOKESCREEN_CRIT_DAMAGE
        self.crit_damage_bonus = (sm_crit * buff_uptime(45, 20, casts=ENGINE_N.get("SMOKESCREEN"))) if level >= sm_lvl else 0.0

        # Buff-Casting Startup Delay: in fixed-duration fights the character casts every currently-unlocked, actively-cast buff sequentially at fight
        # start (1/APS seconds each) before the first damage-skill cast.  With the engine on the buffs are cast when they pay: no start-up delay.
        if fixed_duration_active and not status_on:
            self.buff_cast_startup_time = sum(1 for k in BUFFS if BUFFS[k]["costs_action"] and unlocked(k)) / actions_per_second
        else:
            self.buff_cast_startup_time = 0.0
        fight.startup_time = self.buff_cast_startup_time

        # ---- artifact effects (full): everything that needs the action rate / startup delay / the timeline's status multiplier ----
        actx.aps, actx.startup = actions_per_second, self.buff_cast_startup_time
        # Companion!horn_uptime (computed whether or not Horn Flute is equipped, like the workbook): the share of the player's boss DAMAGE dealt while the
        # companion is out (candidate-0 timing, which already carries Phase Dash's own stun).  The summon timing is damage-independent, so the stub-host run
        # (with the player's stun entries) reports it.
        s0, w0, d_comp, period, ts_window = comp_mod.horn_window(actx, monster_type, fight_duration, pvp_len, summon_time_inc, stun_pin,
                                                                 choice, c_level)
        dw = art_mod.damage_weights(fight_duration, pre.hex_v, steal_avg + meso_mastery_avg + art_a0, pre.charm_val, e1["mult"] if status_on else None)
        actx.horn_uptime = art_mod.horn_flute_uptime(actx, dw, s0, w0, d_comp, period, ts_window)
        actx.crit_rate = crit_rate + self.crit_rate_bonus      # Ring of Cycles' threshold / Book of Ancient's base: Inputs + Dark Sight's live Crit Rate bonus
        eff = self.art_effects = art_mod.Effects(eq, actx, pre)
        self.art_crit_rate = eff.agg_crit_rate                                     # on top of the live bonuses
        self.art_crit_damage = eff.agg_crit_damage + sens_mod.boa_crit_damage_delta(    # (Book of Ancient equip what-if: pct x the crit-rate total, Sensitivity only)
            sens, crit_rate + self.crit_rate_bonus + self.art_crit_rate)
        self.crit_rate_total = crit_rate + self.crit_rate_bonus + self.art_crit_rate     # the FULL live crit-rate total
        self.art_boss_damage, self.art_normal_damage = eff.agg_boss_damage + sens.get("boss_damage_extra", 0.0), eff.agg_normal_damage   # (+ Star Rock what-if)
        self.art_enemy_taken = artifact_monster_dmg_hook + eff.agg_enemy_dmg_taken          # both branches, next to monster_dmg_bonus (Venom's Weaken)
        self.artifact_monster_dmg_bonus = self.art_enemy_taken
        self.art_final_damage = sens_mod.final_damage_bucket(eff.agg_final_damage, sens)   # (+ Sensitivity's baked-in Final Damage what-ifs: a factor on the whole product)
        self.art_joint_damage = eff.agg_damage                                     # Hexagon Damage%
        self.art_skill_damage, self.art_basic_attack_damage = eff.agg_skill_damage, eff.agg_basic_attack_damage
        self.extra_boss, self.extra_norm = eff.extras(
            actx, self.monster_defense, self.def_pen, crit_rate + self.crit_rate_bonus + self.art_crit_rate,
            self.crit_damage + self.crit_damage_bonus + self.art_crit_damage)
        # Hexagon / Charm differ between the two phases of Breakthrough / Hero Dungeon: per-phase timing factor (engine-off rows)
        self.attack_bucket_avg = dark_sight_atk_avg + steal_avg + meso_mastery_avg + art_attack_pct
        self.ph_b, self.ph_n = art_mod.phase_state_ratios(content_type, fight_duration, pre.hex_v, pre.hex_avg, self.attack_bucket_avg,
                                                          pre.charm_val, pre.charm_avg)

        if status_on:
            self.avg_buff_mult = engine_bbuff_mean
        else:
            self.avg_buff_mult = ((1 + (dark_sight_atk_avg + steal_avg + meso_mastery_avg + art_attack_pct) / 100) * (1 + into_darkness_avg / 100)
                                  * (1 + smokescreen_avg / 100))
        avg_buff_mult = self.avg_buff_mult

        # ---- Cruel Stab's hit ----
        cruel_stab_pct = self.skill_coefficient_base * (1 + cruel_stab_mastery / 100)
        cruel_stab_hit = self.hit_damage(cruel_stab_pct, True)

        # ---- Status/KO engine pass 2: the skills' casts.  Weight of one cast = its boss damage before any timing factor ----
        E_ENGINE = None
        if status_on:
            def percast(key):
                if not unlocked(key):
                    return 0.0
                sk = SKILLS[key]
                hd = self.hit_damage(sk["pct"], False, sk["maple_ratio"])
                hits = sk["hits"] * (fight_mod.ticks(capped_window(sk["window"]), sk["icd"]) if sk.get("icd") else 1)
                b_mult = self.boss_mult(sk["mastery_boss"])
                return hits * hd * b_mult
            c_slot = (cruel_stab_hits * cruel_stab_hit * self.boss_mult(cruel_stab_boss_mastery) if unlocked("CRUEL_STAB") else 0.0)
            groups = status_mod.build_groups(D, unlocked, SKILLS, percast, capped_window,
                                             lambda cast: eff_cooldown(SKILLS[cast]["cooldown"], SKILLS[cast]["costs_action"]),
                                             stun_keys={e["key"] for e in D.PLAYER_STUN})
            E_ENGINE = status_mod.solve_groups(self, D, eng_host, groups, c_slot, ENGINE_N, sens)
            E_FS = E_ENGINE["fs"]
        self.e_engine = E_ENGINE

        # ---- Cast rate (subtracted from Cruel Stab): every action-costing row, weighted by ActionsPerCast; engine on: the engine's cast counts ----
        if fixed_duration_active:
            cast_rate = sum(
                BUFFS[k]["actions_per_cast"] * (ENGINE_N[k] if k in ENGINE_N else fight.exact_casts(eff_cooldown(BUFFS[k]["cooldown"],
                                                                                                                BUFFS[k]["costs_action"])))
                for k in BUFFS if BUFFS[k]["costs_action"] and unlocked(k)
            )
            cast_rate += sum(
                (ENGINE_N[k] if k in ENGINE_N else fight.non_buff_casts(eff_cooldown(SKILLS[k]["cooldown"], SKILLS[k]["costs_action"])))
                for k in SKILLS if SKILLS[k]["costs_action"] and unlocked(k)
            )
            cast_rate /= fight_duration
        else:
            cast_rate = sum(
                BUFFS[k]["actions_per_cast"] / eff_cooldown(BUFFS[k]["cooldown"], BUFFS[k]["costs_action"])
                for k in BUFFS if BUFFS[k]["costs_action"] and unlocked(k)
            )
            cast_rate += sum(
                1 / eff_cooldown(SKILLS[k]["cooldown"], SKILLS[k]["costs_action"])
                for k in SKILLS if SKILLS[k]["costs_action"] and unlocked(k)
            )
        self.cast_rate = cast_rate
        self.cruel_stab_per_second = cruel_stab_per_second = max(0, actions_per_second - cast_rate)

        skill_dps = self.skill_dps = {}
        hit_rate = self.hit_rate = {}  # per-skill attacks/sec landing damage (target-multiplied), feeds Toxic Venom

        self.branch_pair("CRUEL_STAB", cruel_stab_per_second, cruel_stab_per_second, cruel_stab_hits * cruel_stab_hit, cruel_stab_boss_mastery, 0.0,
                         cruel_stab_targets)
        if not unlocked("CRUEL_STAB"):
            self.ledger.put_zero("CRUEL_STAB")
        skill_dps["CRUEL_STAB"] = self.blended(self.ledger.pair("CRUEL_STAB"))
        hit_rate["CRUEL_STAB"] = cruel_stab_per_second * target_count_mult(cruel_stab_targets) if unlocked("CRUEL_STAB") else 0.0

        for key, s in SKILLS.items():
            if not unlocked(key):
                skill_dps[key] = 0.0
                hit_rate[key] = 0.0
                self.ledger.put_zero(key)
                continue
            hd = self.hit_damage(s["pct"], False, s["maple_ratio"])
            eff_cd = eff_cooldown(s["cooldown"], s["costs_action"], exempt=key in D.CDR_EXEMPT)
            if status_on and key in ENGINE_N:
                # engine casts: a summon / DoT row's hits = hits per full window x effective casts (last window truncated at the fight end)
                per_cast = s["hits"] * (fight_mod.ticks(capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
                rate = per_cast * (E_FS[key] if key in D.STATUS_FS_KEYS else ENGINE_N[key]) / fight_duration
            elif fixed_duration_active:
                rate = fight.non_buff_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
            else:
                hits = s["hits"] * (fight_mod.ticks(capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
                rate = hits / eff_cd
            pb_, pn_ = self.branch_pair(key, rate, rate, hd, s["mastery_boss"], s["mastery_normal"], s["targets"])
            skill_dps[key] = self.blended((pb_, pn_))
            hit_rate[key] = rate / s["hits"] * target_count_mult(s["targets"])   # proc rolls: once per attack per enemy hit, not per damage line

        # ---- Toxic Venom: no ICD; trigger rate = combined per-second hit rate (already target-multiplied) of every triggering row ----
        self.total_hit_rate = 0.0
        if unlocked("TOXIC_VENOM"):
            tv = D.TOXIC_VENOM
            # (the verify script sums over a set literal; the engine uses its iteration order under PYTHONHASHSEED=0)
            self.total_hit_rate = total_hit_rate = sum(hit_rate[k] for k in D.TRIGGERS_TOXIC_VENOM)
            toxic_venom_pct = coeff_pct(tv["base"], tv["fidx"], True, tv["step"]) * (1 + gated(tv["gated"]) / 100)
            toxic_hd = self.hit_damage(toxic_venom_pct, False)
            rate_tv = tv["chance"] * total_hit_rate
            skill_dps["TOXIC_VENOM"] = self.blended(self.branch_pair("TOXIC_VENOM", rate_tv, rate_tv, toxic_hd, 0.0, 0.0, 1))
        else:
            skill_dps["TOXIC_VENOM"] = 0.0
            self.ledger.put_zero("TOXIC_VENOM")

        # ---- Shadow Shifter: counterattack driven by incoming_hit_rate ----
        if unlocked("SHADOW_SHIFTER"):
            ss = D.SHADOW_SHIFTER
            ss_counter_pct = coeff_pct(ss["base"], ss["fidx"], True, ss["step"])
            ss_hd = self.hit_damage(ss_counter_pct, False)
            rate_ss = incoming_hit_rate * ss["chance"]
            skill_dps["SHADOW_SHIFTER"] = self.blended(self.branch_pair("SHADOW_SHIFTER", rate_ss, rate_ss, ss_hd, 0.0, 0.0, 1))
        else:
            skill_dps["SHADOW_SHIFTER"] = 0.0
            self.ledger.put_zero("SHADOW_SHIFTER")
        self.cruel_stab_dps = skill_dps["CRUEL_STAB"]
        self.cruel_stab_hit = cruel_stab_hit
        self.player_dps = sum(skill_dps.values())

        # ---- player's boss-only / normal-only totals, summed in the ledger's insertion order exactly like the verify script ----
        pairs = self.ledger.pairs
        self.pb_total = sum(p[0] for p in pairs.values())
        self.pn_total = sum(p[1] for p in pairs.values())
        self.pu_total = sum(pairs[k][0] for k in D.STATUS_UNIFORM_ROWS)

        # ---- companion: src/companion_python_model.py fed with this model's own pipeline numbers ----
        self.begin_companion(summon_time_inc)          # (effective Summoning Time Increase % = Inputs + Arwen's Glass Shoes)
        if (choice != "None" and c_level >= 1) or pl_on or sens.get("want_comp_host"):   # (Sensitivity: the comparison tables need the host with no companion / stun too)
            basic_b, basic_n = pairs["CRUEL_STAB"][:2]
            boss_pct_c = boss_damage + self.art_boss_damage + self.monster_dmg_bonus + self.art_enemy_taken
            norm_pct_c = normal_damage + self.art_normal_damage + self.monster_dmg_bonus + self.art_enemy_taken
            fdpart = (1 + id_pct / 100) * (1 + ss_pct / 100)
            ds_full = dsa_pct
            comp_host = dict(comp_mod.host_common(self, pre, eff, basic_b, basic_n),
                unit=self.hit_damage(100.0, True) / 100 / shadow_partner_mult, sd=self.skill_damage + self.art_skill_damage, aps=actions_per_second,
                avgbuff=avg_buff_mult, attack_bucket_avg=self.attack_bucket_avg, agg_damage_avg=self.art_joint_damage,
                avgbuff_snap=lambda charm, extra: (1 + (ds_full + steal_avg + meso_mastery_avg + art_a0 + charm + extra) / 100) * fdpart,
                boss_pct=boss_pct_c, norm_pct=norm_pct_c, cr_total=crit_rate + self.crit_rate_bonus + self.art_crit_rate,
                cd_total=crit_damage + self.crit_damage_bonus + self.art_crit_damage, def_pen=def_pen,
                taken_bucket=0.0 if monster_type == "pvp" else (1 - normal_weight) * boss_pct_c + normal_weight * norm_pct_c, pst=pst)
            self.comp_host = comp_host
            self.run_companion(comp_host, choice, c_level, summon_time_inc, pl_on)
        self.total_dps = self.player_dps + self.companion_dps

    # ------------------------------------------------------------------------------------------------------------------
    def row_dps(self, key):
        return self.skill_dps.get(key, 0.0)

    def derived_extra(self):
        return dict(
            basic_attacks_per_second=self.cruel_stab_per_second, avg_buff_mult=self.avg_buff_mult, as_bonus=self.as_bonus,
            attack_bucket_avg=self.attack_bucket_avg, shadow_partner_mult=self.shadow_partner_mult,
            skill_coefficient_base=self.skill_coefficient_base, buff_cast_startup_time=self.buff_cast_startup_time,
            crit_damage_bonus=self.crit_damage_bonus, crit_rate_bonus=self.crit_rate_bonus,
            monster_dmg_bonus=self.monster_dmg_bonus, artifact_monster_dmg_bonus=self.artifact_monster_dmg_bonus,
            maple_hero_pct=self.maple_hero_pct, steal_avg=self.steal_avg, meso_mastery_avg=self.meso_mastery_avg,
            dark_sight_atk_avg=self.dark_sight_atk_avg, dark_sight_crit_avg=self.dark_sight_crit_avg,
            into_darkness_avg=self.into_darkness_avg, smokescreen_avg=self.smokescreen_avg,
            meso_stack_avg=self.meso_stack_avg, blood_money_stack_avg=self.bm_stack_avg,
            murderous_intent_mult=self.murderous_intent_mult, toxic_venom_trigger_rate=self.total_hit_rate,
            attack_rates=dict(self.hit_rate),
        )


fields, schema, defaults = classapi.make(CLASS_ID, CLASS_NAME, STAT_IDENTITY, _MAIN_STAT_FIELDS, D,
                                         extra_fields=[classapi.INCOMING_HIT_RATE], hooks=dict(artifact_monster_dmg_bonus=0.0))
artifact_schema = classapi.artifact_schema


def model(inputs):
    """The evaluated model object (everything ``compute`` reports plus the internals engine/sensitivity.py reads: ``comp_host``, ``e1`` /
    ``e_engine`` (the timeline strip), ``art_effects`` ...).  Same input dict as ``compute``; honours ``inputs["_sens"]`` (engine/common/sens.py)."""
    return _Model(inputs)


def compute(inputs):
    """DPS of one Shadower setup.  ``inputs``: dict (see module docstring / ``schema()``); returns a JSON-friendly dict:

    total_dps / player_dps / boss_dps / normal_dps / player_boss_dps / player_normal_dps, skills (per damage row: key, name, dps, share,
    boss_dps, normal_dps, unlocked), companion (None or dps/boss/normal/share + model details; choice "None" = the player's Phase Dash stun uplift
    only), engine_on (Status/KO timeline engine), engine (its cast counts and timing factors), derived (ATTACK, STAT_DAMAGE, actions/s, buff
    multipliers, computed Inputs rows ...).
    """
    return _Model(inputs).result()
