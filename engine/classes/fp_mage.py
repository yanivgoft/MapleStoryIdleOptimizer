"""Fire/Poison Arch Mage (FP-Mage): the DPS model of ``src/verify_fp_mage_workbook.py`` as a function of a plain inputs dict.

    from engine.classes import fp_mage
    result = fp_mage.compute(fp_mage.defaults("World Boss"))

``compute(inputs)`` is bit-identical to the verify script (same operations in the same order); the verify script stays the independent
reference, ``tests/golden/test_fp_mage.py`` compares the two (with no artifact equipped).  Artifact equip effects (``inputs["artifacts"]``,
up to 4 slots) are ported in ``engine/artifacts.py``; the verify scripts do not model them, so ``tests/golden/test_artifacts.py --class fp_mage``
checks them against the workbook itself.

Inputs dict: the workbook's Inputs keys already resolved for the chosen content type (see ``schema()``), plus ``companion_level`` (the
level of the chosen companion, 0 = not unlocked).  A missing / ``None`` value reads as 0, exactly like a blank workbook cell (that is
how fields that do not apply to the content type behave: Max Enemies In Range is 0 outside normal-monster content, which zeroes the
normal-monster branch there - it never contributes because that branch has weight 0 in those contents).
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
from ..data import fp_mage as D
from .. import artifacts as art_mod
import status_timeline as stl  # noqa: E402  (src/status_timeline.py through the shim)

CLASS_ID = "fp_mage"
CLASS_NAME = "Fire/Poison Arch Mage"
STAT_IDENTITY = {"main": "INT", "sub": "LUK"}

_MAIN_STAT_FIELDS = [
    schema_mod.field("flat_int", "Flat INT", "Main stats", "float", "flat", 0),
    schema_mod.field("int_pct", "INT %", "Main stats", "float", "%", 0),
    schema_mod.field("luk", "LUK", "Main stats", "float", "flat", 0),
]


class _Model(model_mod.ModelBase):
    DATA = D

    # ------------------------------------------------------------------------------------------------------------------
    # ---- per-hit pipeline ----
    def hit_damage(self, coeff_pct_val, is_basic, maple_mult_val, s):
        effective_coeff = coeff_pct_val * (1 + s["mastery"] / 100)   # a skill mastery MULTIPLIES the skill's damage (game-confirmed 2026-11-03)
        base_damage = self.attack * (effective_coeff / 100)
        dmg_reduction = dmg.defense_reduction(self.monster_defense, self.def_pen)
        final_mult = ((1 + self.final_damage / 100) * (1 + self.art_final_damage / 100) * (1 + self.element_amp_pct / 100)
                      * (1 + self.arcane_aim_pct / 100) ** 5)
        source_pct = (self.basic_attack_damage + self.art_basic_attack_damage if is_basic
                      else self.skill_damage + self.art_skill_damage + self.fervent_drain_pct * 5)
        extra_mult = (self.burning_magic_mult * self.elemental_decrease_mult * self.avg_buff_mult * (1 + self.art_damage / 100)
                      * maple_mult_val)
        # Boss/Normal Monster Damage% is deliberately NOT applied here - it is blended per branch in blend_branches
        base_hit = (
            base_damage * (1 + self.stat_damage / 100) * (1 + self.damage / 100)
            * (1 + self.damage_amp / 100) * dmg_reduction * final_mult * (1 + source_pct / 100) * extra_mult
        )
        return dmg.expected_hit(base_hit, self.min_damage, self.max_damage, self.crit_rate, self.crit_damage)

    # ---- targets and branch blending ----
    def enemies_hit(self, key):
        """Enemies one attack of this skill hits: 1 vs boss/PvP, the skill's own target count (capped by Max Enemies In Range) vs normal."""
        if self.monster_type == "pvp":
            return 1
        if key == "BASIC_ATTACK":
            targets = 6 + self.basic_attack_target_increase + (1 if self.level >= 136 else 0)
        else:
            targets = self.normal_targets.get(key, 1)
        return self.fight.cap_targets(targets)

    def branch_multipliers(self, key, s):
        """(boss-branch, normal-branch) multiplier: Boss/Normal Monster Damage% and target count (PvP: single target, neither bonus)."""
        # outside the Boss/Normal Damage% buckets the artifacts add boss-only / normal-only multipliers (Reindeer's Spear, Contract of Darkness,
        # branch Final Damage), applied even in PvP (extra_boss / extra_norm are exactly 1.0 with no such artifact equipped)
        if self.monster_type == "pvp":
            return 1.0 * self.extra_boss, 1.0 * self.extra_norm
        boss_term = self.boss_damage + s["mastery_boss"]
        normal_term = self.normal_damage + s["mastery_normal"]
        return (1 + boss_term / 100) * self.extra_boss, (1 + normal_term / 100) * self.enemies_hit(key) * self.extra_norm

    def blend_branches(self, key, s, boss_unit, normal_unit=None):
        explicit = normal_unit is not None
        if normal_unit is None:
            normal_unit = boss_unit
        b, n = self.branch_multipliers(key, s)
        fb, fn = self.timing_factors(key)
        b, n = b * fb, n * fn
        return self.ledger.blend(key, boss_unit, normal_unit, b, n, explicit)

    def boss_normal_multiplier(self, key, s):
        return self.blend_branches(key, s, 1.0)

    def q_roll(self, chance, key, branch):
        n = 1 if branch == "boss" else self.enemies_hit(key)
        return dmg.q_roll(chance, n)

    # ------------------------------------------------------------------------------------------------------------------
    def _build(self, inp):
        ct = self.read_content(inp)
        level = self.level
        sens = self.sens
        flat_attack, attack_pct = inp("flat_attack"), inp("attack_pct")
        self.attack = dmg.attack_value(flat_attack, attack_pct)
        if sens.get("mainstat_attack_delta"):      # Sensitivity: the main/sub stat's flat-Attack channel (bug 7), applied before ATTACK%
            self.attack += sens["mainstat_attack_delta"] * (1 + attack_pct / 100)
        flat_int, int_pct, luk = inp("flat_int"), inp("int_pct"), inp("luk")
        self.stat_damage = (flat_int * (1 + int_pct / 100)) * 0.01 + luk * 0.0025
        self.damage = inp("damage")
        self.damage_amp = inp("damage_amp")
        self.boss_damage = inp("boss_damage")
        self.normal_damage = inp("normal_damage")
        self.status_effect_damage = inp("status_effect_damage")
        self.final_damage = inp("final_damage")
        self.min_damage = inp("min_damage") + sens.get("min_damage_delta", 0.0)      # (+ Spell Mastery's level delta, Sensitivity only)
        self.max_damage = inp("max_damage") + sens.get("max_damage_delta", 0.0)      # (+ Athena's Gloves' dependent Max Damage, Sensitivity only)
        self.crit_rate = inp("crit_rate")
        self.crit_damage = inp("crit_damage")
        attack_speed_base = inp("attack_speed")
        self.def_pen = inp("def_pen")
        self.def_pen = sens_mod.def_pen_with_dose(self.def_pen, sens)   # Sensitivity: Reindeer's Spear equip toggle folds one signed dose of its base Def Pen into Inputs' value
        self.basic_attack_damage = inp("basic_attack_damage")
        self.skill_damage = inp("skill_damage")
        self.basic_attack_target_increase = inp("basic_attack_target_increase")
        summon_time_inc = inp("companion_summon_time_increase_pct")
        self.pvp_len = inp("pvp_fight_length") or content_mod.DEFAULT_PVP_FIGHT_LENGTH
        fight = self.fight = fight_mod.Fight(ct, self.pvp_len, inp("skill_cooldown_decrease"),
                                             inp("buff_duration_increase_pct") + sens.get("bdi_extra", 0.0),     # (+ Shamaness Marble what-if, Sensitivity only)
                                             inp("max_enemies_hit"))
        self.ledger = blend_mod.BranchLedger(self.normal_weight)
        unlocked = self.unlocked

        # ---- artifacts (equip effects): slots, the early quantities (Attack% bucket / Hexagon / Charm) and Soul Contract's cooldown decrease ----
        self.eq = eq = sens["eq"] if "eq" in sens else art_mod.resolve_slots(inp.raw("artifacts"))   # (Sensitivity: an equip-toggle what-if may exceed 4 slots)
        # Sensitivity: Book of Ancient's what-if adds its direct Crit Rate to the threshold Ring of Cycles tests (and to the live crit rate below)
        self.crit_rate_input, self.attack_speed_input = self.crit_rate + sens.get("crit_rate_threshold_extra", 0.0), attack_speed_base
        actx = self.art_ctx = art_mod.Ctx(self.content_type, self.monster_type, self.fight_duration, self.pvp_len, self.fixed_duration_active,
                                          crit_rate=self.crit_rate_input, attack_speed=attack_speed_base)
        pre = self.art_pre = art_mod.Pre(eq, actx)
        # Arwen's Glass Shoes: the companion's effective Summoning Time Increase % = the Inputs value + the artifact (every use below)
        summon_time_inc += art_mod.summon_time_inc_pct(eq)
        fight.cd_extra_pct = art_mod.soul_contract_pct(eq, self.content_type)
        # live artifact terms of the damage pipeline; zero / neutral until the full effects are known (after the buff-casting startup delay)
        self.art_final_damage = self.art_damage = self.art_skill_damage = self.art_basic_attack_damage = 0.0
        self.extra_boss = self.extra_norm = 1.0
        self.ph_b = self.ph_n = 1.0

        # ---- Basic Attack coefficient (before Skill Mastery) ----
        basic_lvl = self.sl.input_level(4)
        self.skill_coefficient_base = D.BASIC_ATTACK_BASE * factors.get_factor(basic_lvl, 21) / 1000

        # ---- level-gated skill constants ----
        gated = lambda pairs: factors.level_gated_sum(level, pairs)  # noqa: E731
        basic_attack_mastery = gated(D.BASIC_ATTACK_MASTERY)
        basic_attack_boss_mastery = gated(D.BASIC_ATTACK_BOSS_MASTERY)
        mist_eruption_hits_normal = 4 if level >= 108 else 3
        mist_eruption_mastery = 100 if level >= 122 else 0
        meteor_shower_mastery = 50 if level >= 134 else 0
        poison_mist_dot_icd = 0.4 if level >= 104 else 0.8
        ifrit_window = 40 if level >= 138 else 30
        ifrit_targets = 6 if level >= 138 else 3
        # Mist Eruption's explosion count and Flame Haze DoT's burn window differ by boss vs normal monster; Breakthrough blends by weight
        w = self.normal_weight
        mist_eruption_hits = 0.0 if self.monster_type == "pvp" else (1 - w) * 1 + w * mist_eruption_hits_normal
        flame_haze_dot_window = 10.0 if self.monster_type == "pvp" else (1 - w) * 20 + w * 10

        skills = {"BASIC_ATTACK": dict(job_step=4, cooldown=None, hits=D.BASIC_ATTACK_HITS, base=None, fidx=None, scales=True,
                                       mastery=basic_attack_mastery, mastery_boss=basic_attack_boss_mastery, mastery_normal=0,
                                       costs_action=False)}
        for key in D.SKILL_ORDER:
            s = dict(D.SKILL_TEMPLATES[key])
            s["scales"] = True
            skills[key] = s
        skills["POISON_MIST_DOT"]["icd"] = poison_mist_dot_icd
        skills["FLAME_HAZE_FOG"]["icd"] = poison_mist_dot_icd
        skills["MIST_ERUPTION"].update(hits=mist_eruption_hits, mastery=mist_eruption_mastery)
        skills["METEOR_SHOWER_BURST"]["mastery"] = meteor_shower_mastery
        skills["FLAME_HAZE_DOT"]["window"] = flame_haze_dot_window
        skills["IFRIT"]["window"] = ifrit_window
        self.skills = SKILLS = skills
        BUFFS = D.BUFFS
        self.normal_targets = dict(D.NORMAL_MONSTER_TARGETS, IFRIT=ifrit_targets)
        self.cdr_exempt = set(D.CDR_EXEMPT)

        # ---- passives / always-on multipliers ----
        self.buff_mastery_pct = self.passive_pct("BUFF_MASTERY")
        self.arcane_aim_pct = self.passive_pct("ARCANE_AIM")
        self.fervent_drain_pct = self.passive_pct("FERVENT_DRAIN")
        bm_pct = self.coeff_pct(50, 0, False, 3) * 5                    # Burning Magic
        self.burning_magic_mult = 1 + bm_pct / 100
        # Elemental Decrease: always-on (50% chance per hit, 7 s duration -> reapplied well before expiry; confirmed by the user)
        ed_pct = self.coeff_pct(120, 22, True, 3)
        # Element Amplification: its own always-on Final Damage source, multiplicative with the Final Damage input
        self.element_amp_pct = self.coeff_pct(150, 22, True, 4)
        self.ed_pct = ed_pct
        self.elemental_decrease_mult = 1 + ed_pct / 100        # + artifact enemy-damage-taken sources once the effects are known

        # ---- average buff multiplier (Attack + Final Damage) and attack-speed bonus ----
        # Same-bucket Attack% sources (Meditation + Magic Guard) sum before one multiplication; Final Damage (Infinity) stays its own factor.
        attack_bucket_sum = 0.0
        final_damage_mult = 1.0
        as_bonus = 0.0
        for key, b in BUFFS.items():
            if not unlocked(key):
                continue
            pct = self.coeff_pct(b["base"], b["fidx"], b["scales"], b["job_step"])
            uptime_fraction = fight.buff_uptime(b["cooldown"], b["duration"], b["costs_action"])
            avg_pct = pct * uptime_fraction
            if b["target"] == "ATTACK_SPEED":
                as_bonus += avg_pct
            elif b["target"] == "ATTACK":
                attack_bucket_sum += avg_pct
            else:
                final_damage_mult *= 1 + avg_pct / 100
        # Artifact Attack% (Old Music Box, Secret Map, Reindeer's Spear, Alliance Badge, Bottle of Emotion, Charm's average) joins the same additive bucket
        self.avg_buff_mult = (1 + (attack_bucket_sum + pre.agg_attack_pct) / 100) * final_damage_mult
        self.as_bonus = as_bonus

        # ---- Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`) ----
        choice, c_level = comp_mod.read_choice(inp, zero_none=False)
        self.companion_choice, self.companion_level = choice, c_level
        stun_info = comp_mod.stun_probe(ct, fight, self.pvp_len, choice, c_level, summon_time_inc)
        # Sensitivity blocks pin candidate 0 to the summon time the MAIN sheet chose: the block's own stunned share / Horn Flute window use the pinned
        # timing, the timeline strip's stun vector keeps the unpinned candidate-0 timing of `stun_info` (exactly as the workbook's blocks do)
        _pin = sens.get("comp_pin")
        stun_pin = comp_mod.stun_probe(ct, fight, self.pvp_len, choice, c_level, summon_time_inc, pin=_pin) if _pin is not None else stun_info
        self.hasstun = bool(stun_info and stun_info.get("hasstun"))
        self.stf_b = stun_pin["stunfracB"] if stun_pin else 0.0
        self.stf_n = stun_pin["stunfracN"] if stun_pin else 0.0
        ko = content_mod.ko_windows(self.fight_duration)
        self.status_on = self.fixed_duration_active and self.normal_weight == 0 and (self.content_type in ko or self.hasstun)
        status_on = self.status_on
        self.engine_n = ENGINE_N = {}
        E_ENGINE = None
        self.e1 = None
        eng_host = None
        if status_on:
            stun_vec = stun_info["stun_vector"](stl.NB_MAX) if stun_info else None
            buffs = []
            for bid, key, kind in D.STATUS_BUFFS:
                b = BUFFS[key]
                bd = dict(id=bid, kind=kind, F=self.coeff_pct(b["base"], b["fidx"], b["scales"], b["job_step"]),
                          dur=fight.eff_duration(b["duration"]), cd=fight.eff_cooldown(b["cooldown"], b["costs_action"]), on=unlocked(key))
                if kind == "ramp":
                    bd.update(D.INFINITY_RAMP)
                buffs.append(bd)
            eng_host = dict(T=self.fight_duration, S=self.status_effect_damage, ko=ko.get(self.content_type, []), hex_v=pre.hex_v, hex_period=20,
                            hex_max=3, A0=pre.a0, charm_v=pre.charm_val, hex_avg=pre.hex_avg, c_slot=0.0, stun=stun_vec, buffs=buffs, groups=[])
            e1 = sens["strip"][0] if "strip" in sens else stl.solve(eng_host)   # pass 1: the buff schedule (independent of the skill weights); Sensitivity may reuse the main strip
            self.e1 = e1
            self.avg_buff_mult = e1["Bbuff_mean"]
            for bid, key, kind in D.STATUS_BUFFS:
                ENGINE_N[key] = e1["buffs"][bid]["n"]
            # Excel's attack_bucket_avg for the companion snapshot: F x exact-uptime formula at the engine's cast count
            attack_bucket_sum = 0.0
            for bid, key, kind in D.STATUS_BUFFS:
                if kind != "atk" or not unlocked(key):
                    continue
                b = BUFFS[key]
                n, cd, dur = ENGINE_N[key], fight.eff_cooldown(b["cooldown"], b["costs_action"]), fight.eff_duration(b["duration"])
                up = ((n - 1) * min(dur, cd) + min(dur, max(0.0, self.fight_duration - (n - 1) * cd))) / self.fight_duration
                attack_bucket_sum += self.coeff_pct(b["base"], b["fidx"], b["scales"], b["job_step"]) * up

        self.actions_per_second = dmg.actions_per_second(attack_speed_base + sens.get("attack_speed_extra", 0.0), as_bonus)   # (+ Athena's Gloves what-if)

        # Buff-Casting Startup Delay: in fixed-duration fights the character casts every unlocked, actively cast buff sequentially at
        # fight start (1/APS s each) before the first damage-skill cast.
        if self.fixed_duration_active and not status_on:
            self.buff_cast_startup_time = sum(1 for key, b in BUFFS.items() if b["costs_action"] and unlocked(key)) / self.actions_per_second
        else:
            self.buff_cast_startup_time = 0.0
        fight.startup_time = self.buff_cast_startup_time

        # ---- artifact effects (full): everything that needs the action rate / startup delay / the timeline's status multiplier ----
        actx.aps, actx.startup = self.actions_per_second, self.buff_cast_startup_time
        if True:
            # Companion!horn_uptime (computed whether or not Horn Flute is equipped, like the workbook: it only matters when it is): the share of the player's boss DAMAGE dealt while the companion is out (candidate-0 timing).  The companion
            # model only needs the (damage-independent) summon timing, which the stub-host stun probe already reports.
            d_comp = 30.0 * (1 + summon_time_inc / 100)
            steady = actx.steady
            t_eff = self.pvp_len if self.monster_type == "pvp" else self.fight_duration
            period = max(d_comp, 90.0) if steady else t_eff
            if stun_pin is not None:
                s0, w0 = stun_pin["s0"], stun_pin["W0"]
                ts_window = w0                              # max(0, min(D, Tend0 - s0)) of the workbook with a companion chosen
            else:                                           # no companion: the workbook still computes s_0 (E_0 = 0) but its window W_0 is 0
                s0 = 0.0 if steady else max(7.0, t_eff - d_comp)
                w0 = 0.0
                ts_window = max(0.0, min(d_comp, t_eff - s0))
            dw = art_mod.damage_weights(self.fight_duration, pre.hex_v, pre.a0, pre.charm_val, e1["mult"] if status_on else None)
            horn_uptime = art_mod.horn_flute_uptime(actx, dw, s0, w0, d_comp, period, ts_window)
        actx.horn_uptime = horn_uptime
        eff = self.art_effects = art_mod.Effects(eq, actx, pre)
        self.crit_rate = self.crit_rate_input + sens.get("crit_rate_delta", 0.0) + eff.agg_crit_rate    # (+ Magic Critical's level delta, Sensitivity only)
        self.crit_damage = self.crit_damage + sens.get("crit_damage_delta", 0.0) + eff.agg_crit_damage  # (+ Magic Critical Damage's level delta)
        self.crit_damage += sens_mod.boa_crit_damage_delta(sens, self.crit_rate_input + eff.agg_crit_rate)   # Book of Ancient what-if (Sensitivity only)
        self.boss_damage = self.boss_damage + eff.agg_boss_damage + sens.get("boss_damage_extra", 0.0)   # (+ Star Rock what-if)
        self.normal_damage = self.normal_damage + eff.agg_normal_damage
        self.art_final_damage, self.art_damage = eff.agg_final_damage, eff.agg_damage
        # Sensitivity only: a baked-in Final Damage what-if (its value is typed into Inputs!final_damage) multiplies the whole product - factor (1 + x/100) when
        # adding the artifact, 1/(1 + x/100) when removing it, (1 + new)/(1 + old) for the Attack-Speed-dependent Bottle of Emotion value
        self.art_final_damage = sens_mod.final_damage_bucket(self.art_final_damage, sens)
        self.art_skill_damage, self.art_basic_attack_damage = eff.agg_skill_damage, eff.agg_basic_attack_damage
        self.elemental_decrease_mult = 1 + (self.ed_pct + eff.agg_enemy_dmg_taken) / 100
        self.extra_boss, self.extra_norm = eff.extras(actx, self.monster_defense, self.def_pen,
                                                      self.crit_rate, self.crit_damage)

        # Hexagon / Charm differ between the two phases of Breakthrough / Hero Dungeon: per-phase timing factor (engine-off rows)
        self.attack_bucket_avg = attack_bucket_sum + pre.agg_attack_pct
        self.ph_b, self.ph_n = art_mod.phase_state_ratios(self.content_type, self.fight_duration, pre.hex_v, pre.hex_avg, self.attack_bucket_avg,
                                                          pre.charm_val, pre.charm_avg)

        maple_lvl = self.sl.input_level(4)
        self.maple_factor = factors.get_factor(maple_lvl, 23)

        # ---- status engine pass 2: the skills' casts ----
        self.phi_rows = {}
        self.phi_unif = 1.0
        E_FS = {}
        if status_on:
            def percast(key):
                if not unlocked(key):
                    return 0.0
                sk = SKILLS[key]
                pct = self.coeff_pct(sk["base"], sk["fidx"], sk["scales"], sk["job_step"])
                hd = self.hit_damage(pct, False, self.maple_mult(key), sk)
                hits = sk["hits"] * (fight_mod.ticks(fight.capped_window(sk["window"]), sk["icd"]) if sk.get("icd") else 1)
                return hits * hd * self.branch_multipliers(key, sk)[0]
            basic_s0 = SKILLS["BASIC_ATTACK"]
            c_slot = basic_s0["hits"] * self.hit_damage(self.skill_coefficient_base, True, 1.0, basic_s0) * self.branch_multipliers("BASIC_ATTACK", basic_s0)[0]
            groups = status_mod.build_groups(D, unlocked, SKILLS, percast, fight.capped_window,
                                             lambda cast: fight.eff_cooldown(SKILLS[cast]["cooldown"], SKILLS[cast]["costs_action"], exempt=cast in self.cdr_exempt))
            E_ENGINE = status_mod.solve_groups(self, D, eng_host, groups, c_slot, ENGINE_N, sens)
            E_FS = E_ENGINE["fs"]
        self.e_engine = E_ENGINE

        # ---- action economy ----
        if fight.fixed_duration_active:
            cast_rate = sum(ENGINE_N.get(k, None) if k in ENGINE_N else fight.non_buff_casts(fight.eff_cooldown(SKILLS[k]["cooldown"], s["costs_action"]))
                            for k, s in SKILLS.items() if s["costs_action"] and unlocked(k))
            cast_rate += sum((ENGINE_N[key] if key in ENGINE_N else fight.exact_casts(fight.eff_cooldown(b["cooldown"], b["costs_action"])))
                             for key, b in BUFFS.items() if b["costs_action"] and unlocked(key))
            cast_rate /= self.fight_duration
        else:
            cast_rate = sum(1 / fight.eff_cooldown(SKILLS[k]["cooldown"], s["costs_action"]) for k, s in SKILLS.items() if s["costs_action"] and unlocked(k))
            cast_rate += sum(1 / fight.eff_cooldown(b["cooldown"], b["costs_action"]) for key, b in BUFFS.items() if b["costs_action"] and unlocked(key))
        self.cast_rate = cast_rate
        self.basic_attacks_per_second = max(0, self.actions_per_second - cast_rate)

        basic_s = SKILLS["BASIC_ATTACK"]
        basic_hit = self.hit_damage(self.skill_coefficient_base, True, 1.0, basic_s)
        self.basic_dps = 5 * basic_hit * self.basic_attacks_per_second * self.boss_normal_multiplier("BASIC_ATTACK", basic_s)

        # ---- damage rows ----
        skill_dps = {}
        branch_unit = {}
        ignite_unit_dps = None
        for key, s in SKILLS.items():
            if key == "BASIC_ATTACK":
                continue
            if not unlocked(key):
                skill_dps[key] = 0.0
                continue
            pct = self.coeff_pct(s["base"], s["fidx"], s["scales"], s["job_step"])
            proc = 1 - (1 - s.get("chance", 100) / 100) ** s.get("rolls", 1)
            hd = self.hit_damage(pct, False, self.maple_mult(key), s)
            # Mist Eruption's own costs_action is False, but CDR on Poison Mist carries over to it (CDR_COSTS_ACTION_ROW in the workbook)
            cdr_costs_action = SKILLS["POISON_MIST_BURST"]["costs_action"] if key == "MIST_ERUPTION" else s["costs_action"]
            eff_cd = fight.eff_cooldown(s["cooldown"], cdr_costs_action, exempt=key in self.cdr_exempt)
            if status_on and key in ENGINE_N:
                # engine casts: a DoT / eruption row's hits = hits per full window x effective casts (last window / eruption truncated)
                per_cast = s["hits"] * (fight_mod.ticks(fight.capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
                rate = per_cast * (E_FS[key] if key in D.STATUS_FS_KEYS else ENGINE_N[key]) / self.fight_duration
            elif fight.fixed_duration_active:
                rate = fight.non_buff_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / self.fight_duration
            else:
                hits = s["hits"] * (fight_mod.ticks(fight.capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
                rate = hits / eff_cd
            if key == "IGNITE":
                ignite_unit_dps = proc * hd  # damage per wall tick on one target, expected; branch multipliers applied below
            if key == "MIST_ERUPTION" and unlocked("FLAME_HAZE_FOG") and not status_on:
                # From level 118 every Flame Haze cast also creates a Poison Mist fog, and each fog gets its own explosions.
                fog_eff_cd = fight.eff_cooldown(SKILLS["FLAME_HAZE_FOG"]["cooldown"], False)
                fog_casts_per_s = (fight.non_buff_casts(fog_eff_cd) / self.fight_duration) if fight.fixed_duration_active else 1 / fog_eff_cd
                rate += s["hits"] * fog_casts_per_s
            skill_dps[key] = rate * proc * hd * self.boss_normal_multiplier(key, s)
            if key in ("FLAME_HAZE_DOT", "IFRIT"):
                # these two get a branch-dependent stack multiplier below (it reads the Meteor Proc rate)
                branch_unit[key] = rate * proc * hd

        # ---- Meteor Proc: per-attack-per-enemy-hit rolls, shared 1 s ICD ----
        meteor_chance = D.METEOR_PROC_CHANCE / 100

        def meteor_attempts(branch):
            x = self.basic_attacks_per_second * self.q_roll(meteor_chance, "BASIC_ATTACK", branch)
            for k in D.TRIGGERS_METEOR:
                if unlocked(k):
                    x += D.METEOR_PROC_TRIGGERS_PER_CAST.get(k, 1) * self.cast_rate_py(k) * self.q_roll(meteor_chance, k, branch)
            return x

        self.meteor_x = {br: meteor_attempts(br) for br in ("boss", "normal")}
        self.meteor_proc_rate = meteor_proc_rate = {br: x / (1 + D.METEOR_PROC_ICD * x) for br, x in self.meteor_x.items()}
        meteor_pct = self.coeff_pct(D.METEOR_PROC_BASE, D.METEOR_PROC_FIDX, True, 4)
        meteor_s = dict(mastery=0, mastery_boss=0, mastery_normal=0)
        meteor_hit = self.hit_damage(meteor_pct, False, self.maple_mult("METEOR_PROC"), meteor_s)
        skill_dps["METEOR_PROC"] = (
            self.blend_branches("METEOR_PROC", meteor_s, meteor_proc_rate["boss"] * meteor_hit, meteor_proc_rate["normal"] * meteor_hit)
            if unlocked("METEOR_PROC") else 0.0
        )

        # ---- level 126/130 Flame Haze burn-stacking mastery (Little's Law) ----
        meteor_shower_rate = 1 / fight.eff_cooldown(SKILLS["METEOR_SHOWER_BURST"]["cooldown"], SKILLS["METEOR_SHOWER_BURST"]["costs_action"])
        ifrit_rate = 1 / fight.eff_cooldown(SKILLS["IFRIT"]["cooldown"], SKILLS["IFRIT"]["costs_action"])
        flame_haze_burst_cooldown = fight.eff_cooldown(SKILLS["FLAME_HAZE_BURST"]["cooldown"], True)
        flame_haze_extra_rate, flame_haze_dot_stack_multiplier, flame_haze_total_stacks = {}, {}, {}
        for br in ("boss", "normal"):
            flame_haze_extra_rate[br] = (
                0.05 * (self.basic_attacks_per_second + meteor_shower_rate + meteor_proc_rate[br] + ifrit_rate) if level >= 126 else 0.0
            )
            flame_haze_dot_stack_multiplier[br] = 1 + flame_haze_extra_rate[br] * flame_haze_burst_cooldown
            flame_haze_total_stacks[br] = (
                SKILLS["FLAME_HAZE_DOT"]["window"] / flame_haze_burst_cooldown + flame_haze_extra_rate[br] * SKILLS["FLAME_HAZE_DOT"]["window"]
            )
        self.flame_haze_dot_stack_multiplier = flame_haze_dot_stack_multiplier
        self.flame_haze_total_stacks = flame_haze_total_stacks
        if unlocked("FLAME_HAZE_DOT"):
            skill_dps["FLAME_HAZE_DOT"] = self.blend_branches(
                "FLAME_HAZE_DOT", SKILLS["FLAME_HAZE_DOT"],
                branch_unit["FLAME_HAZE_DOT"] * flame_haze_dot_stack_multiplier["boss"],
                branch_unit["FLAME_HAZE_DOT"] * flame_haze_dot_stack_multiplier["normal"],
            )
        if unlocked("IFRIT"):
            ifrit_stack = {br: (1 + 0.2 * flame_haze_total_stacks[br]) if level >= 130 else 1.0 for br in ("boss", "normal")}
            skill_dps["IFRIT"] = self.blend_branches(
                "IFRIT", SKILLS["IFRIT"], branch_unit["IFRIT"] * ifrit_stack["boss"], branch_unit["IFRIT"] * ifrit_stack["normal"],
            )

        # ---- Ignite: 50% per enemy hit to create a wall (2.5 s ICD after a success), up to 3 walls ticking once per second ----
        ifrit_attacks_per_cast = SKILLS["IFRIT"]["hits"] * fight_mod.ticks(fight.capped_window(SKILLS["IFRIT"]["window"]), SKILLS["IFRIT"]["icd"])
        IGNITE_TICK = SKILLS["IGNITE"]["cooldown"]
        pvp_len, monster_type, fight_duration = self.pvp_len, self.monster_type, self.fight_duration

        def ignite_ticks(branch):
            if monster_type != "pvp" and fight_duration == 0:
                return D.IGNITE_WALLS / IGNITE_TICK
            fire_rate = self.basic_attacks_per_second * self.q_roll(D.IGNITE_CHANCE, "BASIC_ATTACK", branch)
            if unlocked("FLAME_HAZE_BURST"):
                fire_rate += self.cast_rate_py("FLAME_HAZE_BURST") * self.q_roll(D.IGNITE_CHANCE, "FLAME_HAZE_BURST", branch)
            if unlocked("METEOR_SHOWER_BURST"):
                fire_rate += (self.cast_rate_py("METEOR_SHOWER_BURST") * D.METEOR_PROC_TRIGGERS_PER_CAST["METEOR_SHOWER_BURST"]
                              * self.q_roll(D.IGNITE_CHANCE, "METEOR_SHOWER_BURST", branch))
            if unlocked("METEOR_PROC"):
                fire_rate += meteor_proc_rate[branch] * self.q_roll(D.IGNITE_CHANCE, "METEOR_PROC", branch)
            if unlocked("IFRIT"):
                fire_rate += ifrit_attacks_per_cast * self.cast_rate_py("IFRIT") * self.q_roll(D.IGNITE_CHANCE, "IFRIT", branch)
            total = pvp_len if monster_type == "pvp" else fight_duration
            avail = pvp_len if monster_type == "pvp" else max(0.0, fight_duration - self.buff_cast_startup_time)
            wait = 1 / fire_rate if fire_rate > 0 else 1e6
            n_ticks = sum(
                math.floor(max(0.0, avail - (k * wait + (k - 1) * D.IGNITE_ICD)) / IGNITE_TICK + 1e-9)
                for k in range(1, D.IGNITE_WALLS + 1)
            )
            return n_ticks / total

        self.ignite_ticks_per_s = ignite_ticks_per_s = {br: ignite_ticks(br) for br in ("boss", "normal")}
        skill_dps["IGNITE"] = self.blend_branches(
            "IGNITE", SKILLS["IGNITE"], ignite_ticks_per_s["boss"] * ignite_unit_dps, ignite_ticks_per_s["normal"] * ignite_unit_dps,
        )
        self.skill_dps = skill_dps
        self.ignite_unit_dps = ignite_unit_dps
        self.player_dps = self.basic_dps + sum(skill_dps.values())
        self.attack_bucket_sum = attack_bucket_sum

        # ---- player's boss-only / normal-only totals (the companion's damage-share weights) ----
        row_dps = list(skill_dps.items()) + [("BASIC_ATTACK", self.basic_dps)]
        self.pb_total, self.pn_total, self.pu_total = self.ledger.split_totals(row_dps, D.STATUS_UNIFORM_ROWS)

        # ---- companion: src/companion_python_model.py fed with this model's own pipeline numbers ----
        self.companion_result = None
        self.companion_dps = 0.0
        self.comp_host = None
        self.summon_time_inc = summon_time_inc          # effective Summoning Time Increase % (Inputs + Arwen's Glass Shoes)
        if (choice != "None" and c_level >= 1) or sens.get("want_comp_host"):    # (Sensitivity: the comparison tables need the host with no companion chosen too)
            pairs = self.ledger.pairs
            pb_total, pn_total, pu_total = self.pb_total, self.pn_total, self.pu_total
            basic_pair = pairs["BASIC_ATTACK"]
            den = (1 - w) * basic_pair[3] + w * basic_pair[4]
            basic_b = self.basic_dps * basic_pair[3] / den
            basic_n = self.basic_dps * basic_pair[4] / den
            att_full, fd_full = 0.0, 1.0
            for key, b in BUFFS.items():
                if not unlocked(key):
                    continue
                pct = self.coeff_pct(b["base"], b["fidx"], b["scales"], b["job_step"])
                if b["target"] == "ATTACK":
                    att_full += pct
                elif b["target"] != "ATTACK_SPEED":
                    fd_full *= 1 + pct / 100
            ed_bucket = (self.elemental_decrease_mult - 1) * 100
            ex_b, ex_n = self.extra_boss, self.extra_norm
            agg_att, charm_avg, hex_v = pre.agg_attack_pct, pre.charm_avg, pre.hex_v
            comp_host = dict(comp_mod.host_common(self, pre, eff, basic_b, basic_n),
                unit=self.hit_damage(100.0, True, 1.0, dict(mastery=0)) / 100,
                sd=self.skill_damage + self.art_skill_damage + self.fervent_drain_pct * 5, aps=self.actions_per_second, avgbuff=self.avg_buff_mult,
                attack_bucket_avg=self.attack_bucket_avg, agg_damage_avg=eff.agg_damage,
                avgbuff_snap=lambda charm, extra: (1 + (att_full + agg_att - charm_avg + charm + extra) / 100) * fd_full, boss_pct=self.boss_damage,
                norm_pct=self.normal_damage, cr_total=self.crit_rate, cd_total=self.crit_damage, def_pen=self.def_pen, taken_bucket=ed_bucket)
            self.comp_host = comp_host
            if choice != "None" and c_level >= 1:
                self.companion_result = comp_mod.run(comp_host, choice, c_level, summon_time_inc, pin=_pin)
                self.companion_dps = self.companion_result["comp_blend_dps"]
        self.total_dps = self.player_dps + self.companion_dps

    # ------------------------------------------------------------------------------------------------------------------
    def row_dps(self, key):
        return self.basic_dps if key == "BASIC_ATTACK" else self.skill_dps.get(key, 0.0)

    def derived_extra(self):
        return dict(
            basic_attacks_per_second=self.basic_attacks_per_second, avg_buff_mult=self.avg_buff_mult, as_bonus=self.as_bonus,
            burning_magic_mult=self.burning_magic_mult, elemental_decrease_mult=self.elemental_decrease_mult,
            element_amp_pct=self.element_amp_pct, arcane_aim_pct=self.arcane_aim_pct, fervent_drain_pct=self.fervent_drain_pct,
            buff_mastery_pct=self.buff_mastery_pct, skill_coefficient_base=self.skill_coefficient_base,
            buff_cast_startup_time=self.buff_cast_startup_time, attack_bucket_sum=self.attack_bucket_sum,
            meteor_attempts_per_s=self.meteor_x, meteor_proc_rate=self.meteor_proc_rate, ignite_ticks_per_s=self.ignite_ticks_per_s,
            flame_haze_dot_stack_multiplier=self.flame_haze_dot_stack_multiplier, flame_haze_total_stacks=self.flame_haze_total_stacks,
        )


fields, schema, defaults = classapi.make(CLASS_ID, CLASS_NAME, STAT_IDENTITY, _MAIN_STAT_FIELDS, D)
artifact_schema = classapi.artifact_schema


def model(inputs):
    """The evaluated model object (everything ``compute`` reports plus the internals engine/sensitivity.py reads: ``comp_host``, ``e1`` /
    ``e_engine`` (the timeline strip), ``art_effects`` ...).  Same input dict as ``compute``."""
    return _Model(inputs)


def compute(inputs):
    """DPS of one FP-Mage setup.  ``inputs``: dict (see module docstring / ``schema()``); returns a JSON-friendly dict:

    total_dps / player_dps / boss_dps / normal_dps / player_boss_dps / player_normal_dps, skills (per damage row: key, name, dps, share,
    boss_dps, normal_dps, unlocked), companion (None or dps/boss/normal/share + model details), engine_on (Status/KO timeline engine),
    engine (its cast counts and timing factors), derived (ATTACK, STAT_DAMAGE, actions/s, buff multipliers, computed Inputs rows ...).
    """
    return _Model(inputs).result()
