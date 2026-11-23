"""Night Lord: the DPS model of ``src/verify_night_lord_workbook.py`` as a function of a plain inputs dict.

    from engine.classes import night_lord
    result = night_lord.compute(night_lord.defaults("World Boss"))

``compute(inputs)`` is bit-identical to the verify script (same operations in the same order); the verify script stays the independent
reference, ``tests/golden/test_night_lord.py`` compares the two (with no artifact equipped).  Artifact equip effects (``inputs["artifacts"]``, up to 4
slots) are ported in ``engine/artifacts.py`` (shared with the other classes; the Artifacts sheet of the builders is identical) and wired the way
``src/build_night_lord_workbook.py`` wires them; the verify script does not model artifacts, so ``tests/golden/test_night_lord_artifacts.py`` checks
them against the workbook itself (``tests/golden/night_lord_artifacts_golden.json``, evaluated with ``formulas``).  The explicit hook
``inputs["artifact_attack_pct"]`` (default 0) stays: extra Attack% added to the artifact Attack% in Dark Sight's additive bucket (the 2026-11-03
``R_AVGBUFF`` rule: Dark Sight + artifact Attack% are ONE additive bucket, Frailty Curse's and Alchemic Adrenaline's Final Damage stay their own factors).

Inputs dict: the workbook's Inputs keys already resolved for the chosen content type (see ``schema()``), plus ``companion_level`` (the
level of the chosen companion, 0 = not unlocked).  A missing / ``None`` value reads as 0, exactly like a blank workbook cell.

Night Lord specifics (all in the verify script): LUK main / DEX sub; Showdown is the basic attack (5 lines, 6 from Lv136; mastery chain + boss chain)
with no folded Final Attack; Gust Charm is the player's own stun (2 s, cooldown 24 s, from Lv35) feeding the Status Effect Damage / KO timeline and, in
Breakthrough / Hero Dungeon, lengthening the boss phase - so from Lv35 a "companion" result exists even with no companion chosen (choice "None": only the
stun uplift).  Dark Sight (Attack, 2 action slots per cast) and Frailty Curse (self Final Damage, flat profile) are the engine-timed buffs; Gust Charm, Triple
Throw, Dark Flare (dot), Quad Star and Sudden Raid (burst + dot) are the engine's cooldown groups; Showdown, Assassin's Mark, Venom, Toxic Venom and Shadow
Shifter are uniformly spread rows.  Alchemic Adrenaline (Final Damage / Attack Speed, an action-rate-driven proc), Nimble Feet, Dark Sight's Crit Rate,
the Frailty Curse enemy debuff (+ its Critical-Damage-Taken mastery) and Venom's Weaken keep averaged formulas.  Toxic Venom: 20% per attack per enemy hit
(no ICD), trigger rate = the target-blended attack rate of the eight triggering rows.  Shadow Shifter: ``incoming_hit_rate x 20%``.  Shadow Partner is an
average multiplier on every row; it is divided out of the companion's ``unit`` (the clone mirrors only the player's attacks, user-confirmed).

Artifacts (wired like the workbook): the Attack% artifacts (Old Music Box, Secret Map, Reindeer's Spear, Alliance Badge, Bottle of Emotion, Charm's average) join the
ONE additive Attack% bucket next to Dark Sight (engine off: ``(1 + (DarkSight + Art)/100)(1 + Frailty)(1 + Adrenalin)``; engine on: the timeline strip carries them as
``A0`` / Charm / Hexagon and the bucket is the strip's mean x Adrenalin's averaged Final Damage); Frailty Curse's and Alchemic Adrenaline's Final Damage stay their own
factors.  The Final Damage artifacts (Candle, Flaming Lava, Horn Flute) multiply on top of the Final Damage input, Hexagon's Damage% is the (1 + Damage%) factor next to
Shadow Partner, Peach Tree / Silver Pendant (enemy damage taken) add to BOTH the Boss and the Normal Monster Damage terms next to Venom's Weaken / the Frailty Curse
debuff, Ring of Cycles' / Rainbow Snail Shell's Crit Rate and Crit Damage add to the crit totals (next to Critical Throw / Dark Sight's Crit Rate and Frailty Curse's
Critical-Damage-Taken mastery), Reindeer's Spear / Contract of Darkness / the boss-only and normal-only Final Damage artifacts are the boss / normal branch extras, Soul
Contract's cooldown decrease reaches every cooldown through ``Fight.cd_extra_pct`` (Gust Charm, both buffs, the debuff windows, every skill), Horn Flute's uptime is read from the stub run's
candidate-0 timing, which already carries Gust Charm's own stun, Arwen's Glass Shoes adds to the Summoning Time Increase.  Shadow Partner's average multiplier is
divided out of the companion's ``unit`` with or without artifacts.
"""
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
from ..data import night_lord as D
from .. import artifacts as art_mod
import status_timeline as stl  # noqa: E402  (src/status_timeline.py through the shim)

CLASS_ID = "night_lord"
CLASS_NAME = "Night Lord"
STAT_IDENTITY = {"main": "LUK", "sub": "DEX"}

_MAIN_STAT_FIELDS = [
    schema_mod.field("flat_luk", "Flat LUK", "Main stats", "float", "flat", 0),
    schema_mod.field("luk_pct", "LUK %", "Main stats", "float", "%", 0),
    schema_mod.field("dex", "DEX", "Main stats", "float", "flat", 0),
]


def _lv(level, spec):
    """A level-gated value: a plain number, or ``(default, level, value from that level on)``."""
    if isinstance(spec, tuple):
        return spec[2] if level >= spec[1] else spec[0]
    return spec


def _hasted(level, value, haste):
    """``value`` (itself level-gated or a number) times the (level, multiplier) haste once the level is reached."""
    value = _lv(level, value)
    return value * haste[1] if (haste is not None and level >= haste[0]) else value


class _Model(model_mod.ModelBase):
    DATA = D

    # ------------------------------------------------------------------------------------------------------------------
    def target_count_mult(self, targets):
        """Damage%-FREE target-count blend for hit-count / proc-trigger rates (Toxic Venom rolls once per target hit)."""
        if self.monster_type == "pvp":
            return 1
        return (1 - self.normal_weight) + self.normal_weight * min(targets, self.fight.max_enemies_hit)

    def passive_row_pct(self, key, table):
        p = table[key]
        return self.coeff_pct(p["base"], p["fidx"], p["scales"], p["step"]) if self.unlocked(key) else 0.0

    # ---- per-hit pipeline ----
    def hit_damage(self, coeff_pct_val, is_basic, maple_mult_val, mastery, mastery_final):
        """Expected damage of one hit before the boss / normal branch multipliers (Boss/Normal Monster Damage% is applied per branch by ``branch_pair``)."""
        effective_coeff = coeff_pct_val * (1 + mastery / 100)    # a skill mastery MULTIPLIES the skill's damage (game-confirmed 2026-11-03)
        base_damage = self.attack * (effective_coeff / 100)
        dmg_reduction = dmg.defense_reduction(self.monster_defense, self.def_pen)
        final_mult = (1 + self.final_damage / 100) * (1 + mastery_final / 100) * (1 + self.art_final_damage / 100)
        source_pct = (self.basic_attack_damage + self.art_basic_attack_damage) if is_basic else (self.skill_damage + self.art_skill_damage)
        extra_mult = self.avg_buff_mult * self.shadow_partner_mult * (1 + self.art_joint_damage / 100) * maple_mult_val
        base_hit = (
            base_damage * (1 + self.stat_damage / 100) * (1 + self.damage / 100)
            * (1 + self.damage_amp / 100) * dmg_reduction * final_mult * (1 + source_pct / 100) * extra_mult
        )
        return dmg.expected_hit(base_hit, self.min_damage, self.max_damage, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate,
                                self.crit_damage + self.crit_damage_bonus + self.art_crit_damage)

    def row_hit(self, s, key):
        """Expected hit of one damage row (``s`` = its resolved dict)."""
        pct = self.coeff_pct(s["base"], s["fidx"], True, s["step"])
        return self.hit_damage(pct, False, self.maple_mult(key), s["mastery"], s["mastery_final"])

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
        self.boss_damage = boss_damage = inp("boss_damage") + sens.get("boss_damage_delta", 0.0)      # (+ Enveloping Darkness' level delta, Sensitivity only)
        self.normal_damage = normal_damage = inp("normal_damage")
        self.status_effect_damage = status_effect_damage = inp("status_effect_damage")
        self.final_damage = inp("final_damage") + sens.get("final_damage_delta", 0.0)      # (+ Dark Harmony's / Shadow Shifter's level deltas, Sensitivity only)
        self.min_damage = inp("min_damage") + sens.get("min_damage_delta", 0.0)            # (+ Claw Mastery's level delta, Sensitivity only)
        self.max_damage = inp("max_damage") + sens.get("max_damage_delta", 0.0)            # (Athena's Gloves' dependent Max Damage, Sensitivity only)
        # (Crit Rate: + Critical Throw's level delta, Book of Ancient's direct Crit Rate what-if - feeds Ring of Cycles' threshold and the live crit rate; Sensitivity only)
        self.crit_rate = crit_rate = inp("crit_rate") + sens.get("crit_rate_threshold_extra", 0.0) + sens.get("crit_rate_delta", 0.0)
        self.crit_damage = crit_damage = inp("crit_damage") + sens.get("crit_damage_delta", 0.0)      # (+ Critical Throw's level delta / Book of Ancient's dependent Crit Damage while Crit Rate is swept)
        attack_speed_base = inp("attack_speed")
        attack_speed_total = attack_speed_base + sens.get("attack_speed_extra", 0.0)      # (+ Agile Claws' level delta / Athena's Gloves what-if, Sensitivity only)
        self.def_pen = def_pen = sens_mod.def_pen_with_dose(inp("def_pen"), sens)         # Sensitivity: Reindeer's Spear equip toggle folds one signed dose of its base Def Pen in
        self.basic_attack_damage = inp("basic_attack_damage") + sens.get("basic_attack_damage_delta", 0.0)      # (+ Physical Training's level delta, Sensitivity only)
        self.skill_damage = inp("skill_damage") + sens.get("skill_damage_delta", 0.0)      # (+ Claw Expert's level delta, Sensitivity only)
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
                                          crit_rate=self.crit_rate, attack_speed=attack_speed_base)
        pre = self.art_pre = art_mod.Pre(eq, actx)
        # Arwen's Glass Shoes: the companion's effective Summoning Time Increase % = the Inputs value + the artifact (every use below)
        summon_time_inc += art_mod.summon_time_inc_pct(eq)
        fight.cd_extra_pct = art_mod.soul_contract_pct(eq, content_type)
        # Attack% the artifacts add to Dark Sight's additive bucket: the Attack% artifacts (AGG_ATTACK_PCT incl. Charm's average) + the explicit hook
        # (default 0, not modelled by the verify script).  ``art_a0`` = the same without Charm (the timeline strip's A0 and the companion's k1)
        hook = inp("artifact_attack_pct") + sens.get("attack_mult_delta", 0.0)     # (+ Expert Throwing Star Handling's level delta, Sensitivity only: it joins the additive Attack% bucket)
        self.artifact_attack_pct = art_attack_pct = hook + pre.agg_attack_pct
        art_a0 = hook + pre.a0
        # live artifact terms of the damage pipeline; zero / neutral until the full effects are known (after the buff-casting startup delay)
        self.art_final_damage = self.art_joint_damage = self.art_skill_damage = self.art_basic_attack_damage = 0.0
        self.art_boss_damage = self.art_normal_damage = self.art_crit_rate = self.art_crit_damage = self.art_enemy_taken = 0.0
        self.extra_boss = self.extra_norm = 1.0
        self.ph_b = self.ph_n = 1.0
        self.ledger = blend_mod.BranchLedger(normal_weight)
        eff_cooldown = fight.eff_cooldown
        capped_window = fight.capped_window
        sl = self.sl

        basic_lvl = sl.input_level(4)
        self.skill_coefficient_base = D.SHOWDOWN_BASE * factors.get_factor(basic_lvl, 21) / 1000

        # ---- level-resolved values of the rows ----
        SHOWDOWN_TARGETS = 6 + basic_attack_target_increase
        showdown_hits = _lv(level, D.SHOWDOWN_HITS)
        showdown_mastery = gated(D.SHOWDOWN_MASTERY)
        showdown_mastery_boss = gated(D.SHOWDOWN_MASTERY_BOSS)
        toxic_venom_mastery = gated(D.TOXIC_VENOM["mastery"])
        adrenalin_buff_duration = _lv(level, D.ADRENALIN_DURATION)
        nm = D.NIGHT_LORDS_MARK
        night_lords_mark_pct = coeff_pct(nm["base"], nm["fidx"], True, nm["step"]) if level >= nm["level"] else 0.0

        SKILLS = self.skills = {}        # DAMAGE_SKILLS after Showdown, resolved for this level (the verify script's DAMAGE_SKILLS minus Showdown)
        for key, t in D.DAMAGE_SKILLS.items():
            if "final" in t:
                f_lvl, f_base, f_fidx, f_step = t["final"]
                mastery_final = coeff_pct(f_base, f_fidx, True, f_step) if level >= f_lvl else 0.0
            else:
                mastery_final = 0.0
            s = dict(step=t["step"], cooldown=_hasted(level, t["cooldown"], t.get("haste")), hits=_lv(level, t["hits"]), base=t["base"], fidx=t["fidx"],
                     mastery=gated(t["mastery"]), mastery_boss=_lv(level, t["mastery_boss"]), mastery_normal=_lv(level, t["mastery_normal"]),
                     mastery_final=mastery_final, costs_action=t["costs_action"], targets=_lv(level, t["targets"]))
            if "icd" in t:
                s["icd"], s["window"] = _hasted(level, t["icd"], t.get("icd_haste")), t["window"]
            SKILLS[key] = s

        # ---- buffs ----
        BUFFS = {k: dict(b, duration=_lv(level, b["duration"])) for k, b in D.BUFFS.items()}
        self.buffs = BUFFS

        # ---- Nimble Feet / Alchemic Adrenaline / Actions per second (none of them is engine-timed) ----
        nf = BUFFS["NIMBLE_FEET"]
        nimble_feet_pct = coeff_pct(nf["base"], nf["fidx"], False, nf["step"])
        nimble_feet_uptime = fight.buff_uptime(nf["cooldown"], nf["duration"])
        nimble_feet_avg = nimble_feet_pct * nimble_feet_uptime
        self.nimble_feet_avg = nimble_feet_avg

        aps_pre_adrenalin = 1 + min(150, 150 * (1 - (1 - attack_speed_total / 150) * (1 - nimble_feet_avg / 150))) / 100
        self.aps_pre_adrenalin = aps_pre_adrenalin
        adrenalin_duration_scaled = fight.eff_duration(adrenalin_buff_duration)
        adrenalin_accumulate_time = D.ADRENALIN_ACTIVATIONS / aps_pre_adrenalin
        adrenalin_uptime = (adrenalin_duration_scaled / (adrenalin_duration_scaled + adrenalin_accumulate_time)
                            if unlocked("ADRENALIN_FD") else 0.0)
        self.adrenalin_uptime = adrenalin_uptime
        a_as, a_fd = D.ADRENALIN["ADRENALIN_AS"], D.ADRENALIN["ADRENALIN_FD"]
        adrenalin_as_pct = coeff_pct(a_as["base"], a_as["fidx"], True, a_as["step"]) if unlocked("ADRENALIN_AS") else 0.0
        adrenalin_fd_pct = (coeff_pct(a_fd["base"], a_fd["fidx"], True, a_fd["step"]) + gated(a_fd["gated"])) if unlocked("ADRENALIN_FD") else 0.0
        adrenalin_as_avg = adrenalin_as_pct * adrenalin_uptime
        self.adrenalin_fd_avg = adrenalin_fd_avg = adrenalin_fd_pct * adrenalin_uptime
        self.adrenalin_as_avg = adrenalin_as_avg

        as_bonus = nimble_feet_avg + adrenalin_as_avg
        self.as_bonus = as_bonus
        self.actions_per_second = actions_per_second = dmg.actions_per_second(attack_speed_total, as_bonus)

        # ---- Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`) ----
        choice, c_level = comp_mod.read_choice(inp)
        self.companion_choice, self.companion_level = choice, c_level

        pl_on = any(unlocked(e["key"]) and level >= e["min_level"] for e in D.PLAYER_STUN)
        self.pl_on = pl_on
        stun_info = comp_mod.stun_probe(ct, fight, pvp_len, choice, c_level, summon_time_inc)
        hasstun = bool(stun_info and stun_info.get("hasstun")) or pl_on
        self.hasstun = hasstun
        ko = content_mod.ko_windows(fight_duration)
        self.status_on = status_on = fixed_duration_active and normal_weight == 0 and (content_type in ko or hasstun)
        # the stun skill's first cast: t=0 with the engine on, otherwise after the buff-casting startup (Nimble Feet + Dark Sight + Frailty Curse)
        startup_buffs = sum(1 for k in BUFFS if BUFFS[k]["costs_action"] and unlocked(k))
        startup_plain = (startup_buffs / actions_per_second) if fixed_duration_active else 0.0
        t0_pl = 0.0 if status_on else startup_plain
        self.pst = pst = [dict(id=e["id"], typ=e["typ"], cd=eff_cooldown(e["cd"], True), dur=e["dur"], p=e["p"],
                               on=unlocked(e["key"]) and level >= e["min_level"], t0=t0_pl, tick=e["tick"], win=e["win"])
                          for e in D.PLAYER_STUN]
        stun_info, stun_pin = comp_mod.stun_windows(ct, fight, pvp_len, pst, choice, c_level, summon_time_inc, sens)
        self.stf_b = stf_b = stun_pin["stunfracB"]
        self.stf_n = stun_pin["stunfracN"]
        self.engine_n = ENGINE_N = {}
        E_ENGINE = None
        e1 = None
        self.phi_rows = {}
        self.phi_unif = 1.0
        E_FS = {}
        dark_sight_atk_pct = self.passive_row_pct("DARK_SIGHT_ATK", BUFFS)
        frailty_self_pct = self.passive_row_pct("FRAILTY_CURSE_SELF_FD", BUFFS)
        self.frailty_self_pct = frailty_self_pct
        engine_bbuff_mean = None
        if status_on:
            # (the verify script raises KeyError here when no companion is chosen and the player's stun is locked, i.e. level < 35 in a KO content:
            # the companion model's early return carries no stun_vector.  The engine reads that as "no companion stun".)
            comp_stun = stun_info["stun_vector"](stl.NB_MAX) if "stun_vector" in stun_info else [0.0] * stl.NB_MAX
            stun_vec = [min(1.0, a + b) for a, b in zip(comp_stun, stl.pl_stun_vector([dict(e, t0=0.0) for e in pst], fight_duration, stl.NB_MAX))]
            ds, fc = BUFFS["DARK_SIGHT_ATK"], BUFFS["FRAILTY_CURSE_SELF_FD"]
            ds_dur = ds["duration"] * (1 + buff_duration_increase_pct / 100)
            ds_cd = eff_cooldown(ds["cooldown"], True)
            fc_dur = fc["duration"] * (1 + buff_duration_increase_pct / 100)
            fc_cd = eff_cooldown(fc["cooldown"], True)
            buffs = [dict(id="DS", kind="atk", F=dark_sight_atk_pct, dur=ds_dur, cd=ds_cd, on=unlocked("DARK_SIGHT_ATK")),
                     dict(id="FC", kind="ramp", F=frailty_self_pct, dur=min(fc_dur, fc_cd), cd=fc_cd, on=unlocked("FRAILTY_CURSE_SELF_FD"),
                          p0=1, p1=1, ramp_t=1, dur0=1)]
            eng_host = dict(T=fight_duration, S=status_effect_damage, ko=ko.get(content_type, []), hex_v=pre.hex_v, hex_period=20, hex_max=3,
                            A0=art_a0, charm_v=pre.charm_val, hex_avg=pre.hex_avg, c_slot=0.0, stun=stun_vec, buffs=buffs, groups=[])
            e1 = sens["strip"][0] if "strip" in sens else stl.solve(eng_host)   # pass 1: the buff schedule (independent of the skill weights); Sensitivity may reuse the main strip
            engine_bbuff_mean = e1["Bbuff_mean"]
            for row, pfx in D.STATUS_CAST_PREFIX.items():
                if pfx.startswith("buff."):
                    ENGINE_N[row] = e1["buffs"][pfx[5:]]["n"]
        self.engine_bbuff_mean = engine_bbuff_mean
        self.e1 = e1

        # ---- global helper bonuses (Crit Rate / Monster damage taken / Crit Damage Taken / Average Buff Multiplier / Shadow Partner) ----
        dsc = BUFFS["DARK_SIGHT_CRIT"]
        dark_sight_crit_pct = self.passive_row_pct("DARK_SIGHT_CRIT", BUFFS) if unlocked("DARK_SIGHT_CRIT") else 0.0
        dark_sight_crit_uptime = fight.buff_uptime(dsc["cooldown"], dsc["duration"], casts=ENGINE_N.get("DARK_SIGHT_CRIT"))
        dark_sight_crit_avg = dark_sight_crit_pct * dark_sight_crit_uptime if unlocked("DARK_SIGHT_CRIT") else 0.0

        fd_ = BUFFS["FRAILTY_CURSE_DEBUFF"]
        frailty_debuff_pct = coeff_pct(fd_["base"], fd_["fidx"], True, fd_["step"]) if unlocked("FRAILTY_CURSE_DEBUFF") else 0.0
        frailty_debuff_uptime = fight.buff_uptime(fd_["cooldown"], fd_["duration"], casts=ENGINE_N.get("FRAILTY_CURSE_DEBUFF"))
        frailty_debuff_avg = frailty_debuff_pct * frailty_debuff_uptime if unlocked("FRAILTY_CURSE_DEBUFF") else 0.0
        # Mastery Lv.111 ("Frailty Curse - Critical"): +30% Critical Damage Taken x the debuff's uptime (the Critical Resistance half is not modelled)
        fc_lvl, fc_val = D.FRAILTY_CRIT_DAMAGE_TAKEN
        self.crit_damage_bonus = (fc_val * frailty_debuff_uptime) if level >= fc_lvl else 0.0

        cth_lvl, cth_val = D.CRITICAL_THROW_LV47
        critical_throw_lv47 = cth_val if level >= cth_lvl else 0.0
        vw_lvl, vw_val = D.VENOM_WEAKEN
        venom_lv82 = vw_val if level >= vw_lvl else 0.0

        self.crit_rate_bonus = critical_throw_lv47 + dark_sight_crit_avg
        self.monster_dmg_bonus = venom_lv82 + frailty_debuff_avg

        dsa = BUFFS["DARK_SIGHT_ATK"]
        dark_sight_atk_uptime = fight.buff_uptime(dsa["cooldown"], dsa["duration"], casts=ENGINE_N.get("DARK_SIGHT_ATK"))
        self.dark_sight_atk_avg = dark_sight_atk_avg = dark_sight_atk_pct * dark_sight_atk_uptime if unlocked("DARK_SIGHT_ATK") else 0.0

        fcs = BUFFS["FRAILTY_CURSE_SELF_FD"]
        frailty_self_uptime = fight.buff_uptime(fcs["cooldown"], fcs["duration"], casts=ENGINE_N.get("FRAILTY_CURSE_SELF_FD"))
        frailty_self_avg = frailty_self_pct * frailty_self_uptime if unlocked("FRAILTY_CURSE_SELF_FD") else 0.0
        self.frailty_self_avg = frailty_self_avg

        # Buff-Casting Startup Delay: in fixed-duration fights every unlocked, actively cast buff (Nimble Feet, Dark Sight x2, Frailty Curse) is cast
        # sequentially at the start (1/APS s each) before the first damage-skill cast; with the engine on the buffs are cast when they pay: none.
        if fixed_duration_active and not status_on:
            self.buff_cast_startup_time = sum(1 for k in BUFFS if BUFFS[k]["costs_action"] and unlocked(k)) / actions_per_second
        else:
            self.buff_cast_startup_time = 0.0
        fight.startup_time = self.buff_cast_startup_time

        # ---- artifact effects (full): everything that needs the action rate / startup delay / the timeline's status multiplier ----
        actx.aps, actx.startup = actions_per_second, self.buff_cast_startup_time
        # Companion!horn_uptime (computed whether or not Horn Flute is equipped, like the workbook): the share of the player's boss DAMAGE dealt while the
        # companion is out (candidate-0 timing, which already carries Gust Charm's own stun).  The summon timing is damage-independent, so the stub-host run
        # (with the player's stun entries) reports it.
        s0, w0, d_comp, period, ts_window = comp_mod.horn_window(actx, monster_type, fight_duration, pvp_len, summon_time_inc, stun_pin,
                                                                 choice, c_level)
        dw = art_mod.damage_weights(fight_duration, pre.hex_v, art_a0, pre.charm_val, e1["mult"] if status_on else None)
        actx.horn_uptime = art_mod.horn_flute_uptime(actx, dw, s0, w0, d_comp, period, ts_window)
        actx.crit_rate = self.crit_rate + self.crit_rate_bonus     # Ring of Cycles' threshold / Book of Ancient's base: Inputs + Critical Throw / Dark Sight's live bonus
        eff = self.art_effects = art_mod.Effects(eq, actx, pre)
        self.art_crit_rate, self.art_crit_damage = eff.agg_crit_rate, eff.agg_crit_damage    # on top of the live bonuses
        self.art_crit_damage += sens_mod.boa_crit_damage_delta(                              # (Book of Ancient equip what-if: pct x the crit-rate total, Sensitivity only)
            sens, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate)
        # the FULL live crit-rate total (Inputs + Critical Throw / Dark Sight + the artifact bucket; CLAUDE.md item 13): what the cube / equipment tables test against the 100% cap
        self.crit_rate_total = self.crit_rate + self.crit_rate_bonus + self.art_crit_rate
        self.art_boss_damage, self.art_normal_damage = eff.agg_boss_damage + sens.get("boss_damage_extra", 0.0), eff.agg_normal_damage   # (+ Star Rock what-if)
        self.art_enemy_taken = eff.agg_enemy_dmg_taken                              # both branches, next to monster_dmg_bonus (Venom Weaken + Frailty Curse debuff)
        self.art_final_damage = sens_mod.final_damage_bucket(eff.agg_final_damage, sens)   # (+ Sensitivity's baked-in Final Damage what-ifs: a factor on the whole product)
        self.art_joint_damage = eff.agg_damage                                     # Hexagon Damage%
        self.art_skill_damage, self.art_basic_attack_damage = eff.agg_skill_damage, eff.agg_basic_attack_damage
        self.extra_boss, self.extra_norm = eff.extras(
            actx, self.monster_defense, self.def_pen, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate,
            self.crit_damage + self.crit_damage_bonus + self.art_crit_damage)
        # Hexagon / Charm differ between the two phases of Breakthrough / Hero Dungeon: per-phase timing factor (engine-off rows)
        self.ph_b, self.ph_n = art_mod.phase_state_ratios(content_type, fight_duration, pre.hex_v, pre.hex_avg, dark_sight_atk_avg + art_attack_pct,
                                                          pre.charm_val, pre.charm_avg)

        # Average Buff Multiplier: Dark Sight's Attack% (additive bucket with the artifacts), Frailty Curse's and Adrenalin's Final Damage as own factors.
        # Engine on: its mean buff bucket (Dark Sight + Frailty Curse at the engine's cast times) x Adrenalin.
        if status_on:
            self.avg_buff_mult = engine_bbuff_mean * (1 + adrenalin_fd_avg / 100)
        else:
            self.avg_buff_mult = (1 + (dark_sight_atk_avg + art_attack_pct) / 100) * (1 + frailty_self_avg / 100) * (1 + adrenalin_fd_avg / 100)

        sp = D.SHADOW_PARTNER
        shadow_partner_mastery = gated(sp["mastery"])
        shadow_partner_pct = ((coeff_pct(sp["base"], sp["fidx"], True, sp["step"]) * (1 + shadow_partner_mastery / 100))
                              if unlocked("SHADOW_PARTNER") else 0.0)
        maple_lvl = sl.input_level(4)
        self.maple_factor = factors.get_factor(maple_lvl, D.MAPLE_FACTOR_IDX)
        shadow_partner_maple = self.maple_mult("SHADOW_PARTNER") if unlocked("SHADOW_PARTNER") else 1.0
        self.shadow_partner_mult = (1 + (shadow_partner_pct * shadow_partner_maple * sp["share"] / 100) / 100
                                    if unlocked("SHADOW_PARTNER") else 1.0)

        # ---- Showdown's hit ----
        showdown_hit = self.hit_damage(self.skill_coefficient_base, True, 1.0, showdown_mastery, 0.0)

        # ---- Status/KO engine pass 2: the skills' casts (weight of one cast = its boss damage before any timing factor) ----
        if status_on:
            def percast(key):
                if not unlocked(key):
                    return 0.0
                sk = SKILLS[key]
                hd = self.row_hit(sk, key)
                hits = sk["hits"] * (fight_mod.ticks(capped_window(sk["window"]), sk["icd"]) if sk.get("icd") else 1)
                return hits * hd * self.boss_mult(sk["mastery_boss"])
            c_slot = (showdown_hits * showdown_hit * self.boss_mult(showdown_mastery_boss)
                      if unlocked("SHOWDOWN") else 0.0)
            groups = status_mod.build_groups(D, unlocked, SKILLS, percast, capped_window,
                                             lambda cast: eff_cooldown(SKILLS[cast]["cooldown"], SKILLS[cast]["costs_action"]),
                                             stun_keys={e["key"] for e in D.PLAYER_STUN})
            E_ENGINE = status_mod.solve_groups(self, D, eng_host, groups, c_slot, ENGINE_N, sens)
            E_FS = E_ENGINE["fs"]
        self.e_engine = E_ENGINE

        # ---- Cast rate (subtracted from Showdown): every action-costing row, weighted by ActionsPerCast; engine on: the engine's cast counts ----
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
        self.showdown_per_second = showdown_per_second = max(0, actions_per_second - cast_rate)

        # ---- Showdown (basic attack) DPS (put in the ledger first: the verify script's _BRANCH_PAIRS insertion order) ----
        skill_dps = {}
        hit_rate = {}         # per-skill attacks/sec landing damage (target-multiplied), feeds Toxic Venom
        self.branch_pair("SHOWDOWN", showdown_per_second, showdown_per_second, showdown_hits * showdown_hit, showdown_mastery_boss, 0.0,
                         SHOWDOWN_TARGETS)
        if not unlocked("SHOWDOWN"):
            self.ledger.put_zero("SHOWDOWN")
        self.showdown_dps = showdown_dps = self.blended(self.ledger.pair("SHOWDOWN"))
        hit_rate["SHOWDOWN"] = showdown_per_second * self.target_count_mult(SHOWDOWN_TARGETS) if unlocked("SHOWDOWN") else 0.0
        skill_dps["SHOWDOWN"] = showdown_dps if unlocked("SHOWDOWN") else 0.0

        # ---- the other damage rows ----
        for key, s in SKILLS.items():
            if not unlocked(key):
                skill_dps[key] = 0.0
                hit_rate[key] = 0.0
                self.ledger.put_zero(key)
                continue
            hd = self.row_hit(s, key)
            eff_cd = eff_cooldown(s["cooldown"], s["costs_action"], exempt=key in D.CDR_EXEMPT)
            if status_on and key in ENGINE_N:
                # engine casts: a DoT row's hits = hits per full window x effective casts (last window truncated at the fight end)
                per_cast = s["hits"] * (fight_mod.ticks(capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
                rate = per_cast * (E_FS[key] if key in D.STATUS_FS_KEYS else ENGINE_N[key]) / fight_duration
            elif fixed_duration_active:
                rate = fight.non_buff_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
            else:
                hits = s["hits"] * (fight_mod.ticks(capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
                rate = hits / eff_cd
            pb_, pn_ = self.branch_pair(key, rate, rate, hd, s["mastery_boss"], s["mastery_normal"], s["targets"])
            skill_dps[key] = self.blended((pb_, pn_))
            hit_rate[key] = rate / s["hits"] * self.target_count_mult(s["targets"])     # proc rolls: once per attack per enemy hit, not per damage line

        # ---- Toxic Venom: no ICD; trigger rate = the combined per-second hit rate (already target-multiplied) of the triggering rows ----
        tv = D.TOXIC_VENOM
        self.total_hit_rate = 0.0
        if unlocked("TOXIC_VENOM"):
            total_hit_rate = self.total_hit_rate = sum(hit_rate[k] for k in D.TRIGGERS_TOXIC_VENOM)
            toxic_pct = coeff_pct(tv["base"], tv["fidx"], True, tv["step"])
            toxic_hd = self.hit_damage(toxic_pct, False, 1.0, toxic_venom_mastery, 0.0)
            rate_tv = tv["chance"] * total_hit_rate
            skill_dps["TOXIC_VENOM"] = self.blended(self.branch_pair("TOXIC_VENOM", rate_tv, rate_tv, toxic_hd, 0.0, 0.0, 1))
        else:
            skill_dps["TOXIC_VENOM"] = 0.0
            self.ledger.put_zero("TOXIC_VENOM")

        # ---- Shadow Shifter counterattack: driven by incoming_hit_rate, not the character's own cast rate ----
        ss = D.SHADOW_SHIFTER
        if unlocked("SHADOW_SHIFTER"):
            shifter_pct = coeff_pct(ss["base"], ss["fidx"], True, ss["step"])
            shifter_hd = self.hit_damage(shifter_pct, False, 1.0, 0.0, 0.0)
            rate_ss = incoming_hit_rate * ss["chance"]
            skill_dps["SHADOW_SHIFTER"] = self.blended(self.branch_pair("SHADOW_SHIFTER", rate_ss, rate_ss, shifter_hd, 0.0, 0.0, 1))
        else:
            skill_dps["SHADOW_SHIFTER"] = 0.0
            self.ledger.put_zero("SHADOW_SHIFTER")
        self.skill_dps = skill_dps
        self.hit_rate = hit_rate
        self.player_dps = sum(skill_dps.values())

        # ---- player's boss-only / normal-only totals, summed in the ledger's insertion order exactly like the verify script ----
        pairs = self.ledger.pairs
        self.pb_total = sum(p[0] for p in pairs.values())
        self.pn_total = sum(p[1] for p in pairs.values())
        self.pu_total = sum(pairs[k][0] for k in D.STATUS_UNIFORM_ROWS)

        # ---- companion: src/companion_python_model.py fed with this model's own pipeline numbers ----
        self.begin_companion(summon_time_inc)          # (effective Summoning Time Increase % = Inputs + Arwen's Glass Shoes)
        if (choice != "None" and c_level >= 1) or pl_on or sens.get("want_comp_host"):   # (Sensitivity: the comparison tables need the host with no companion / stun too)
            basic_b, basic_n = pairs["SHOWDOWN"][:2]
            boss_pct_c = boss_damage + self.art_boss_damage + self.monster_dmg_bonus + self.art_enemy_taken
            norm_pct_c = normal_damage + self.art_normal_damage + self.monster_dmg_bonus + self.art_enemy_taken
            fdpart = (1 + (frailty_self_pct if unlocked("FRAILTY_CURSE_SELF_FD") else 0.0) / 100) * (1 + adrenalin_fd_avg / 100)
            ds_full = dark_sight_atk_pct if unlocked("DARK_SIGHT_ATK") else 0.0
            shadow_partner_mult = self.shadow_partner_mult
            comp_host = dict(comp_mod.host_common(self, pre, eff, basic_b, basic_n),
                # the Shadow Partner clone mirrors only the player's own attacks, so its average multiplier is divided out of the companion's unit
                unit=self.hit_damage(100.0, True, 1.0, 0.0, 0.0) / 100 / shadow_partner_mult, sd=self.skill_damage + self.art_skill_damage,
                aps=actions_per_second, avgbuff=self.avg_buff_mult, attack_bucket_avg=dark_sight_atk_avg + art_attack_pct,
                agg_damage_avg=self.art_joint_damage, avgbuff_snap=lambda charm, extra: (1 + (ds_full + art_a0 + charm + extra) / 100) * fdpart,
                boss_pct=boss_pct_c, norm_pct=norm_pct_c, cr_total=crit_rate + self.crit_rate_bonus + self.art_crit_rate,
                cd_total=crit_damage + self.crit_damage_bonus + self.art_crit_damage, def_pen=def_pen,
                taken_bucket=0.0 if monster_type == "pvp" else (1 - normal_weight) * boss_pct_c + normal_weight * norm_pct_c, pst=pst)
            self.comp_host = comp_host
            self.run_companion(comp_host, choice, c_level, summon_time_inc, pl_on)
        self.total_dps = self.player_dps + self.companion_dps
        self.dark_sight_crit_avg = dark_sight_crit_avg
        self.dark_sight_atk_pct = dark_sight_atk_pct

    # ------------------------------------------------------------------------------------------------------------------
    def row_dps(self, key):
        return self.skill_dps.get(key, 0.0)

    def derived_extra(self):
        return dict(
            basic_attacks_per_second=self.showdown_per_second, avg_buff_mult=self.avg_buff_mult, as_bonus=self.as_bonus,
            skill_coefficient_base=self.skill_coefficient_base, buff_cast_startup_time=self.buff_cast_startup_time,
            crit_damage_bonus=self.crit_damage_bonus, crit_rate_bonus=self.crit_rate_bonus, monster_dmg_bonus=self.monster_dmg_bonus,
            shadow_partner_mult=self.shadow_partner_mult, dark_sight_attack_avg=self.dark_sight_atk_avg,
            dark_sight_crit_rate_avg=self.dark_sight_crit_avg, frailty_curse_self_fd_avg=self.frailty_self_avg,
            alchemic_adrenaline_uptime=self.adrenalin_uptime, alchemic_adrenaline_fd_avg=self.adrenalin_fd_avg,
            alchemic_adrenaline_as_avg=self.adrenalin_as_avg, nimble_feet_avg=self.nimble_feet_avg,
            actions_per_second_pre_adrenalin=self.aps_pre_adrenalin, artifact_attack_pct=self.artifact_attack_pct,
            toxic_venom_trigger_rate=self.total_hit_rate, attack_rates=dict(self.hit_rate),
        )


fields, schema, defaults = classapi.make(CLASS_ID, CLASS_NAME, STAT_IDENTITY, _MAIN_STAT_FIELDS, D,
                                         extra_fields=[classapi.INCOMING_HIT_RATE], hooks=dict(artifact_attack_pct=0.0))
artifact_schema = classapi.artifact_schema


def model(inputs):
    """The evaluated model object (everything ``compute`` reports plus the internals engine/sensitivity.py reads: ``comp_host``, ``e1`` /
    ``e_engine`` (the timeline strip), ``art_effects`` ...).  Same input dict as ``compute``; honours ``inputs["_sens"]`` (engine/common/sens.py)."""
    return _Model(inputs)


def compute(inputs):
    """DPS of one Night Lord setup.  ``inputs``: dict (see module docstring / ``schema()``); returns a JSON-friendly dict:

    total_dps / player_dps / boss_dps / normal_dps / player_boss_dps / player_normal_dps, skills (per damage row: key, name, dps, share,
    boss_dps, normal_dps, unlocked), companion (None or dps/boss/normal/share + model details; choice "None" = the player's stun uplift only),
    engine_on (Status/KO timeline engine), engine (its cast counts and timing factors), derived (ATTACK, STAT_DAMAGE, actions/s, buff
    multipliers, computed Inputs rows ...).
    """
    return _Model(inputs).result()
