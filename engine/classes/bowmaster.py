"""Bowmaster: the DPS model of ``src/verify_bowmaster_workbook.py`` as a function of a plain inputs dict.

    from engine.classes import bowmaster
    result = bowmaster.compute(bowmaster.defaults("World Boss"))

``compute(inputs)`` is bit-identical to the verify script (same operations in the same order); the verify script stays the independent
reference, ``tests/golden/test_bowmaster.py`` compares the two (with no artifact equipped).  Artifact equip effects (``inputs["artifacts"]``, up to 4
slots) are ported in ``engine/artifacts.py`` (shared with FP-Mage / Hero; the Artifacts sheet of the builders is identical) and wired the way
``src/build_bowmaster_workbook.py`` wires them; the verify script does not model artifacts, so ``tests/golden/test_artifacts.py --class bowmaster``
checks them against the workbook itself (``tests/golden/bowmaster_artifacts_golden.json``, evaluated with ``formulas``).

Inputs dict: the workbook's Inputs keys already resolved for the chosen content type (see ``schema()``), plus ``companion_level`` (the
level of the chosen companion, 0 = not unlocked).  A missing / ``None`` value reads as 0, exactly like a blank workbook cell.

Bowmaster specifics (all in the verify script): DEX main / STR sub; Arrow Stream is the basic attack (5 lines, 6 from Lv136); Covering Fire
stuns for 1 s (cooldown 19 s) from the Lv49 mastery on - that stun feeds the Status Effect Damage / KO timeline and, in Breakthrough / Hero
Dungeon, lengthens the boss phase, so a "companion" result exists from Lv49 even with no companion chosen (choice "None": only the stun
uplift, reported under ``companion`` with ``choice == "None"``); Illusion Step is the only engine-timed buff (Attack%); Marksmanship (Attack%,
conditional part boss-only), Sharp Eyes (Crit Damage, uptime), Concentration (Crit Damage, 7 steady stacks), Mortal Blow (Final Damage) and
Nimble Feet (Attack Speed) are averaged; Quiver Cartridge / Enchanted Quiver tick at an attack-speed-scaled interval; Final Attack: Bow and Flash
Mirage are chance procs (one roll per attack per enemy hit, Flash Mirage with its real internal cooldown).  Unlike Hero there is no live
Defense Penetration, no global damage-taken source and the boss / normal blend is ``(1-w) * (rate*hit*b*fb) + w * (rate*hit*n*fn)`` per row.
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
from ..data import bowmaster as D
from .. import artifacts as art_mod
import status_timeline as stl  # noqa: E402  (src/status_timeline.py through the shim)

CLASS_ID = "bowmaster"
CLASS_NAME = "Bowmaster"
STAT_IDENTITY = {"main": "DEX", "sub": "STR"}

_MAIN_STAT_FIELDS = [
    schema_mod.field("flat_dex", "Flat DEX", "Main stats", "float", "flat", 0),
    schema_mod.field("dex_pct", "DEX %", "Main stats", "float", "%", 0),
    schema_mod.field("str", "STR", "Main stats", "float", "flat", 0),
]


class _Model(model_mod.ModelBase):
    DATA = D

    # ------------------------------------------------------------------------------------------------------------------
    # ---- per-hit pipeline ----
    def hit_damage(self, coeff_pct_val, is_basic, maple_ratio=0.0, extra_fd_pct=0.0):
        base_damage = self.attack * (coeff_pct_val / 100)
        dmg_reduction = dmg.defense_reduction(self.monster_defense, self.def_pen)
        maple_mult = (1 + maple_ratio * self.maple_hero_pct / 100) if maple_ratio else 1.0
        extra_fd_mult = (1 + extra_fd_pct / 100)
        final_mult = (1 + (self.final_damage + self.mortal_blow_bonus) / 100) * (1 + self.art_final_damage / 100) * maple_mult * extra_fd_mult
        source_pct = (self.basic_attack_damage + self.art_basic_attack_damage) if is_basic else (self.skill_damage + self.art_skill_damage)
        # Boss/Normal Monster Damage% is deliberately NOT applied here - it is blended per branch (its own multiplier x its own target count)
        base_hit = (
            base_damage * (1 + self.stat_damage / 100) * (1 + self.damage / 100)
            * (1 + self.damage_amp / 100) * dmg_reduction * final_mult * (1 + source_pct / 100)
            * self.attack_bucket_mult * (1 + self.art_damage / 100)
        )
        return dmg.expected_hit(base_hit, self.min_damage, self.max_damage, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate,
                                self.crit_damage + self.crit_damage_bonus)

    def skill_hit(self, s):
        """Expected damage of one hit of a damage skill (before the boss/normal branch multipliers)."""
        # a skill mastery MULTIPLIES the skill's damage (game-confirmed 2026-11-03); fold-ins stay additive
        pct = self.coeff_pct(s["base"], s["fidx"], True, s["step"]) * (1 + s.get("mastery", 0) / 100) + s.get("fold", 0)
        return self.hit_damage(pct, False, maple_ratio=s.get("maple_ratio", 0.0), extra_fd_pct=s.get("extra_fd", 0.0))

    # ---- targets and branch blending ----
    def boss_mult(self, mastery_boss):
        """Boss branch multiplier of a row (1 in PvP), times the artifacts' boss-only multiplier (Reindeer's Spear / Contract of Darkness / boss-only
        Final Damage; exactly 1.0 with none equipped, applied in PvP too)."""
        if self.monster_type == "pvp":
            return 1.0 * self.extra_boss
        return (1 + (self.boss_damage + mastery_boss + self.monster_dmg_bonus + self.art_boss_damage) / 100) * self.extra_boss

    def branch_pair(self, key, rate_boss, rate_normal, hd_, mastery_boss, mastery_normal, targets):
        """Boss and normal DPS of one row (before weighting): rate x hit x its own branch multiplier x the row's timing factor."""
        fb, fn = self.timing_factors(key)
        if self.monster_type == "pvp":
            b, n = 1.0 * self.extra_boss, 1.0 * self.extra_norm
        else:
            b = (1 + (self.boss_damage + mastery_boss + self.monster_dmg_bonus + self.art_boss_damage) / 100) * self.extra_boss
            n = ((1 + (self.normal_damage + mastery_normal + self.monster_dmg_bonus + self.art_normal_damage) / 100)
                 * min(targets, self.fight.max_enemies_hit) * self.extra_norm)
        return self.ledger.put(key, rate_boss, rate_normal, hd_, b, n, fb, fn)

    def branch_blend(self, key, rate_boss, rate_normal, hd_, mastery_boss, mastery_normal, targets):
        pb, pn = self.branch_pair(key, rate_boss, rate_normal, hd_, mastery_boss, mastery_normal, targets)
        return (1 - self.normal_weight) * pb + self.normal_weight * pn

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
        flat_dex, dex_pct, str_stat = inp("flat_dex"), inp("dex_pct"), inp("str")
        self.stat_damage = (flat_dex * (1 + dex_pct / 100)) * 0.01 + str_stat * 0.0025
        self.damage = inp("damage")
        self.damage_amp = inp("damage_amp")
        self.boss_damage = boss_damage = inp("boss_damage")
        self.normal_damage = normal_damage = inp("normal_damage")
        self.status_effect_damage = status_effect_damage = inp("status_effect_damage")
        self.final_damage = inp("final_damage") + sens.get("final_damage_delta", 0.0)      # (+ Reckless Hunt's / Armor Break's level deltas, Sensitivity only)
        self.min_damage = inp("min_damage") + sens.get("min_damage_delta", 0.0)      # (+ Bow Mastery's level delta, Sensitivity only)
        self.max_damage = inp("max_damage") + sens.get("max_damage_delta", 0.0)      # (+ Bow Expert's level delta / Athena's Gloves' dependent Max Damage, Sensitivity only)
        # (+ Book of Ancient's direct Crit Rate what-if / Critical Shot's level delta, Sensitivity only: the workbook's Ring of Cycles threshold includes both)
        self.crit_rate = crit_rate = inp("crit_rate") + sens.get("crit_rate_threshold_extra", 0.0) + sens.get("crit_rate_delta", 0.0)
        self.crit_damage = crit_damage = inp("crit_damage")
        attack_speed_base = inp("attack_speed")
        # Sensitivity: Armor Break's Defense Penetration level delta joins the typed value, then Reindeer's Spear equip toggle folds one signed dose of its base Def Pen in
        # (diminishing returns; the block's K formula and boss-branch correction both read ``def_pen_total_block``)
        self.def_pen = def_pen = sens_mod.def_pen_with_dose(inp("def_pen") + sens.get("def_pen_delta", 0.0), sens)
        self.basic_attack_damage = inp("basic_attack_damage") + sens.get("basic_attack_damage_delta", 0.0)   # (+ Physical Training's level delta, Sensitivity only)
        self.skill_damage = inp("skill_damage") + sens.get("skill_damage_delta", 0.0)      # (+ Bow Expert's level delta, Sensitivity only)
        basic_attack_target_increase = inp("basic_attack_target_increase")
        buff_duration_increase_pct = inp("buff_duration_increase_pct") + sens.get("bdi_extra", 0.0)     # (+ Shamaness Marble what-if, Sensitivity only)
        summon_time_inc = inp("companion_summon_time_increase_pct")
        self.pvp_len = pvp_len = inp("pvp_fight_length") or content_mod.DEFAULT_PVP_FIGHT_LENGTH
        fight = self.fight = fight_mod.Fight(ct, pvp_len, inp("skill_cooldown_decrease"), buff_duration_increase_pct,
                                             inp("max_enemies_hit"))
        max_enemies_hit = fight.max_enemies_hit
        self.ledger = blend_mod.BranchLedger(normal_weight)

        # ---- artifacts (equip effects): slots, the early quantities (Attack% bucket / Hexagon / Charm) and Soul Contract's cooldown decrease ----
        self.eq = art_eq = sens["eq"] if "eq" in sens else art_mod.resolve_slots(inp.raw("artifacts"))   # (not `eq`: that name is Enchanted Quiver below; Sensitivity: an equip-toggle what-if may exceed 4 slots)
        actx = self.art_ctx = art_mod.Ctx(self.content_type, monster_type, fight_duration, pvp_len, fixed_duration_active,
                                          crit_rate=self.crit_rate, attack_speed=attack_speed_base)
        pre = self.art_pre = art_mod.Pre(art_eq, actx)
        # Arwen's Glass Shoes: the companion's effective Summoning Time Increase % = the Inputs value + the artifact (every use below)
        summon_time_inc += art_mod.summon_time_inc_pct(art_eq)
        fight.cd_extra_pct = art_mod.soul_contract_pct(art_eq, self.content_type)
        # live artifact terms of the damage pipeline; zero / neutral until the full effects are known (after the buff-casting startup delay)
        self.art_final_damage = self.art_damage = self.art_skill_damage = self.art_basic_attack_damage = 0.0
        self.art_boss_damage = self.art_normal_damage = self.art_crit_rate = 0.0
        self.extra_boss = self.extra_norm = 1.0
        self.ph_b = self.ph_n = 1.0
        eff_cooldown = fight.eff_cooldown
        eff_duration = fight.eff_duration
        capped_window = fight.capped_window
        buff_avg = self.buff_avg

        basic_lvl = self.sl.input_level(4)
        self.skill_coefficient_base = D.ARROW_STREAM_BASE * factors.get_factor(basic_lvl, 21) / 1000

        # ---- Helper rows (Final Attack: Bow's coefficient is its own damage row now; Advanced Final Attack, Enchanted Quiver, Maple Hero,
        #      Flash Mirage II): own coefficients only, they feed another row's extra Final Damage term ----
        fab = D.FINAL_ATTACK_BOW
        final_attack_bow_pct = (coeff_pct(fab["base"], fab["fidx"], True, fab["step"]) * (1 + gated(fab["gated"]) / 100)
                                if unlocked("FINAL_ATTACK_BOW") else 0.0)
        afa = D.ADVANCED_FINAL_ATTACK
        advanced_final_attack_pct = (coeff_pct(afa["base"], afa["fidx"], True, afa["step"]) + gated(afa["gated"])
                                     if unlocked("ADVANCED_FINAL_ATTACK_HELPER") else 0.0)
        eq = D.ENCHANTED_QUIVER
        enchanted_quiver_pct = coeff_pct(eq["base"], eq["fidx"], True, eq["step"]) if unlocked("ENCHANTED_QUIVER_HELPER") else 0.0
        mh = D.MAPLE_HERO
        self.maple_hero_pct = maple_hero_pct = coeff_pct(mh["base"], mh["fidx"], True, mh["step"]) if unlocked("MAPLE_HERO_HELPER") else 0.0
        fm2 = D.FLASH_MIRAGE_II
        flash_mirage_ii_pct = coeff_pct(fm2["base"], fm2["fidx"], True, fm2["step"]) if unlocked("FLASH_MIRAGE_II_HELPER") else 0.0
        helper_pct = {"ENCHANTED_QUIVER_HELPER": enchanted_quiver_pct, "FLASH_MIRAGE_II_HELPER": flash_mirage_ii_pct,
                      "ADVANCED_FINAL_ATTACK_HELPER": advanced_final_attack_pct}

        # ---- Attack% bucket: Marksmanship (base + conditional) + Illusion Step, summed additively ----
        mk = D.MARKSMANSHIP
        marksmanship_base_pct = coeff_pct(mk["base"], mk["fidx"], True, mk["step"]) if unlocked("MARKSMANSHIP_BASE") else 0.0
        marksmanship_cond_pct_raw = coeff_pct(mk["base"], mk["fidx"], True, mk["step"]) if unlocked("MARKSMANSHIP_COND") else 0.0
        marksmanship_cond_avg = self.monster_blend(marksmanship_cond_pct_raw, 0.0) if unlocked("MARKSMANSHIP_COND") else 0.0
        ist = D.ILLUSION_STEP
        is_boost_lvl, is_boost = ist["boost"]
        is_dur0, is_dur_lvl, is_dur1 = ist["duration"]
        is_duration = is_dur1 if level >= is_dur_lvl else is_dur0
        illusion_step_pct = (
            coeff_pct(ist["base"], ist["fidx"], True, ist["step"])
            + (is_boost * coeff_pct(ist["base"], ist["fidx"], True, ist["step"]) if level >= is_boost_lvl else 0.0)
        ) if unlocked("ILLUSION_STEP") else 0.0
        illusion_step_avg = buff_avg(illusion_step_pct, is_duration, ist["cooldown"], False) if unlocked("ILLUSION_STEP") else 0.0

        # artifact Attack% (Old Music Box, Secret Map, Reindeer's Spear, Alliance Badge, Bottle of Emotion, Charm's average) joins the same additive bucket
        attack_mult_delta = sens.get("attack_mult_delta", 0.0)      # (+ Soul Arrow: Bow's level delta, Sensitivity only: it joins the additive Attack% bucket)
        self.attack_bucket_mult = 1 + (marksmanship_base_pct + marksmanship_cond_avg + illusion_step_avg + attack_mult_delta + pre.agg_attack_pct) / 100

        # ---- Sharp Eyes (self-inclusive ally buff: Crit Damage; no Crit Rate component) ----
        se = D.SHARP_EYES
        sharp_eyes_crit_damage_pct = coeff_pct(se["base"], se["fidx"], True, se["step"]) if unlocked("SHARP_EYES") else 0.0
        se_dur0, se_dur_lvl, se_dur1 = se["duration"]
        sharp_eyes_uptime = (
            buff_avg(1.0, se_dur1 if level >= se_dur_lvl else se_dur0, se["cooldown"], True) if unlocked("SHARP_EYES") else 0.0
        )
        self.crit_rate_bonus = 0.0
        sharp_eyes_crit_damage_avg = sharp_eyes_crit_damage_pct * sharp_eyes_uptime if unlocked("SHARP_EYES") else 0.0

        # ---- Concentration (steady-state max stacks) ----
        cn = D.CONCENTRATION
        concentration_crit_damage = (cn["stacks"] * coeff_pct(cn["base"], cn["fidx"], True, cn["step"])) if unlocked("CONCENTRATION") else 0.0
        self.crit_damage_bonus = sharp_eyes_crit_damage_avg + concentration_crit_damage

        self.monster_dmg_bonus = 0.0      # no global monster-damage-taken source exists in this kit

        # ---- Mortal Blow (steady-state always-active Final Damage bonus) ----
        mb = D.MORTAL_BLOW
        mortal_blow_pct = coeff_pct(mb["base"], mb["fidx"], True, mb["step"]) if unlocked("MORTAL_BLOW") else 0.0
        self.mortal_blow_bonus = mortal_blow_pct if unlocked("MORTAL_BLOW") else 0.0

        # ---- Nimble Feet (Attack Speed buff, duty-cycle averaged) ----
        nf = D.NIMBLE_FEET
        nimble_feet_pct = coeff_pct(nf["base"], nf["fidx"], False, nf["step"])
        nimble_avg = buff_avg(nimble_feet_pct, nf["duration"], nf["cooldown"], True) if unlocked("NIMBLE_FEET") else 0.0
        self.as_bonus = nimble_avg
        self.actions_per_second = actions_per_second = dmg.actions_per_second(attack_speed_base + sens.get("attack_speed_extra", 0.0), nimble_avg)   # (+ Archer Mastery's / Bow Acceleration's level delta / Athena's Gloves what-if, Sensitivity only)

        # ---- Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`) ----
        choice, c_level = comp_mod.read_choice(inp)
        self.companion_choice, self.companion_level = choice, c_level
        # The player's own stunning skills (game table): Covering Fire stuns for 1 s (cooldown 19 s), from the Lv49 mastery on
        pl_on = any(unlocked(e["key"]) and level >= e["min_level"] for e in D.PLAYER_STUN)
        stun_info = comp_mod.stun_probe(ct, fight, pvp_len, choice, c_level, summon_time_inc)
        hasstun = bool(stun_info and stun_info.get("hasstun")) or pl_on
        ko = content_mod.ko_windows(fight_duration)
        self.status_on = status_on = fixed_duration_active and normal_weight == 0 and (content_type in ko or hasstun)
        startup_plain = (sum(1 for k in D.STARTUP_BUFFS if unlocked(k)) / actions_per_second) if fixed_duration_active else 0.0
        t0_pl = 0.0 if status_on else startup_plain
        self.pst = pst = [dict(id=e["id"], typ=e["typ"], cd=eff_cooldown(e["cd"], True), dur=e["dur"], p=e["p"],
                               on=unlocked(e["key"]) and level >= e["min_level"], t0=t0_pl, tick=1.0, win=0.0) for e in D.PLAYER_STUN]
        stun_info, stun_pin = comp_mod.stun_windows(ct, fight, pvp_len, pst, choice, c_level, summon_time_inc, sens)
        self.stf_b = stun_pin["stunfracB"]
        self.stf_n = stun_pin["stunfracN"]
        attack_bucket_mult = self.attack_bucket_mult
        self.engine_n = ENGINE_N = {}
        E_ENGINE = None
        self.phi_rows = {}
        self.phi_unif = 1.0
        E_FS = {}
        attack_bucket_sum = marksmanship_base_pct + marksmanship_cond_avg + illusion_step_avg + attack_mult_delta   # the averaged Attack% bucket (in %, without artifacts)
        e1 = None
        if status_on:
            # (the verify script raises KeyError here when no companion is chosen and Covering Fire's stun is locked, i.e. level < 49 in a
            # KO content: the companion model's early return carries no stun_vector.  The engine reads that as "no companion stun".)
            comp_stun = stun_info["stun_vector"](stl.NB_MAX) if "stun_vector" in stun_info else [0.0] * stl.NB_MAX
            stun_vec = [min(1.0, a + b) for a, b in zip(comp_stun, stl.pl_stun_vector([dict(e, t0=0.0) for e in pst], fight_duration, stl.NB_MAX))]
            is_dur, is_cd = eff_duration(is_duration), eff_cooldown(ist["cooldown"], False)
            buffs = [dict(id="IS", kind="atk", F=illusion_step_pct, dur=is_dur, cd=is_cd, on=unlocked("ILLUSION_STEP"))]
            eng_host = dict(T=fight_duration, S=status_effect_damage, ko=ko.get(content_type, []), hex_v=pre.hex_v, hex_period=20, hex_max=3,
                            A0=marksmanship_base_pct + marksmanship_cond_avg + attack_mult_delta + pre.a0, charm_v=pre.charm_val, hex_avg=pre.hex_avg,
                            c_slot=0.0, stun=stun_vec, buffs=buffs, groups=[])
            e1 = sens["strip"][0] if "strip" in sens else stl.solve(eng_host)   # pass 1: the buff schedule (independent of the skill weights); Sensitivity may reuse the main strip
            attack_bucket_mult = self.attack_bucket_mult = e1["Bbuff_mean"]
            ENGINE_N["ILLUSION_STEP"] = e1["buffs"]["IS"]["n"]
            # Excel's attack_bucket_avg for the companion snapshot: F x exact-uptime formula at the engine's cast count
            if unlocked("ILLUSION_STEP"):
                n = ENGINE_N["ILLUSION_STEP"]
                up = ((n - 1) * min(is_dur, is_cd) + min(is_dur, max(0.0, fight_duration - (n - 1) * is_cd))) / fight_duration
                attack_bucket_sum = marksmanship_base_pct + marksmanship_cond_avg + attack_mult_delta + illusion_step_pct * up

        self.e1 = e1

        # Buff-Casting Startup Delay: in fixed-duration fights the character casts every unlocked, actively cast buff (Sharp Eyes, Nimble
        # Feet; Illusion Step costs no action) sequentially at fight start (1/APS s each) before the first damage-skill cast.
        if fixed_duration_active and not status_on:
            self.buff_cast_startup_time = sum(1 for k in D.STARTUP_BUFFS if unlocked(k)) / actions_per_second
        else:
            self.buff_cast_startup_time = 0.0
        buff_cast_startup_time = self.buff_cast_startup_time
        fight.startup_time = buff_cast_startup_time

        # ---- artifact effects (full): everything that needs the action rate / startup delay / the timeline's status multiplier ----
        actx.aps, actx.startup = actions_per_second, buff_cast_startup_time
        # Companion!horn_uptime (computed whether or not Horn Flute is equipped, like the workbook): the share of the player's boss DAMAGE dealt
        # while the companion is out (candidate-0 timing, which already carries Covering Fire's stun in Breakthrough).  The summon timing is
        # damage-independent, so the stub-host run (with the player's stun entries) reports it.
        s0, w0, d_comp, period, ts_window = comp_mod.horn_window(actx, monster_type, fight_duration, pvp_len, summon_time_inc, stun_pin,
                                                                 choice, c_level)
        dw = art_mod.damage_weights(fight_duration, pre.hex_v, marksmanship_base_pct + marksmanship_cond_avg + attack_mult_delta + pre.a0, pre.charm_val,
                                    e1["mult"] if status_on else None)
        actx.horn_uptime = art_mod.horn_flute_uptime(actx, dw, s0, w0, d_comp, period, ts_window)
        eff = self.art_effects = art_mod.Effects(art_eq, actx, pre)
        self.art_crit_rate = eff.agg_crit_rate                                     # (Sharp Eyes has no Crit Rate component: ``crit_rate_bonus`` stays 0, the artifact bucket is ``art_crit_rate``)
        self.crit_damage_bonus = sharp_eyes_crit_damage_avg + concentration_crit_damage + eff.agg_crit_damage
        self.crit_damage_bonus += sens.get("crit_damage_delta", 0.0)              # (Sensitivity: Book of Ancient's dependent Crit Damage while Crit Rate is swept)
        self.crit_damage_bonus += sens_mod.boa_crit_damage_delta(                  # (Book of Ancient equip what-if: pct x the crit-rate total, Sensitivity only)
            sens, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate)
        # the FULL live crit-rate total (Inputs + artifact bucket; CLAUDE.md item 13): what the cube / equipment tables test against the 100% cap
        self.crit_rate_total = self.crit_rate + self.crit_rate_bonus + self.art_crit_rate
        self.art_boss_damage, self.art_normal_damage = eff.agg_boss_damage + sens.get("boss_damage_extra", 0.0), eff.agg_normal_damage   # (+ Star Rock what-if)
        self.art_final_damage = sens_mod.final_damage_bucket(eff.agg_final_damage, sens)   # (+ Sensitivity's baked-in Final Damage what-ifs: a factor on the whole product)
        self.art_damage = eff.agg_damage                                           # Hexagon Damage%
        self.monster_dmg_bonus = eff.agg_enemy_dmg_taken                           # Peach Tree / Silver Pendant: Summary's Global Monster Damage-Taken Bonus%
        self.art_skill_damage, self.art_basic_attack_damage = eff.agg_skill_damage, eff.agg_basic_attack_damage
        self.extra_boss, self.extra_norm = eff.extras(actx, self.monster_defense, self.def_pen,
                                                      self.crit_rate + self.crit_rate_bonus + self.art_crit_rate, self.crit_damage + self.crit_damage_bonus)
        # Hexagon / Charm differ between the two phases of Breakthrough / Hero Dungeon: per-phase timing factor (engine-off rows)
        self.attack_bucket_avg = attack_bucket_sum + pre.agg_attack_pct
        self.ph_b, self.ph_n = art_mod.phase_state_ratios(content_type, fight_duration, pre.hex_v, pre.hex_avg, self.attack_bucket_avg,
                                                          pre.charm_val, pre.charm_avg)

        # Quiver Cartridge's own AS-scaled tick rate ("up to 0.4 times based on Attack Speed"), same 150%-AS cap as actions_per_second
        qc = D.QUIVER_CD
        self.quiver_cartridge_cooldown = quiver_cartridge_cooldown = (
            qc["base"] - qc["scale"] * min(qc["cap"], (actions_per_second - 1) / qc["aps_span"]))

        # ---- Arrow Stream (basic attack) ----
        self.arrow_stream_mastery_damage = gated(D.ARROW_STREAM_MASTERY)
        self.arrow_stream_mastery_boss_damage = arrow_stream_mastery_boss_damage = gated(D.ARROW_STREAM_BOSS_MASTERY)
        arrow_stream_pct = self.skill_coefficient_base * (1 + self.arrow_stream_mastery_damage / 100)
        arrow_stream_targets = 6 + basic_attack_target_increase
        arrow_stream_hit = self.hit_damage(arrow_stream_pct, True)
        hits0, hits_lvl, hits1 = D.ARROW_STREAM_HITS
        ARROW_STREAM_HITS = hits1 if level >= hits_lvl else hits0

        # ---- Damage skills (level-resolved) ----
        SKILLS = self.skills = {}
        for key, t in D.DAMAGE_SKILLS.items():
            cooldown = t["cooldown"]
            if cooldown == "quiver":
                cooldown = quiver_cartridge_cooldown
            elif "haste" in t:
                cooldown = (cooldown * t["haste"][1]) if level >= t["haste"][0] else cooldown
            elif "cooldown_alt" in t:
                cooldown = t["cooldown_alt"][1] if level >= t["cooldown_alt"][0] else cooldown
            targets = t["targets"]
            for lvl_t, add_t in t["extra_targets"]:
                if level >= lvl_t:
                    targets = targets + add_t
            mastery_normal = t["mastery_normal"]
            if isinstance(mastery_normal, tuple):
                mastery_normal = mastery_normal[1] if level >= mastery_normal[0] else 0
            s = dict(step=t["step"], cooldown=cooldown, hits=t["hits"], base=t["base"], fidx=t["fidx"], mastery=gated(t["mastery"]),
                     mastery_boss=t["mastery_boss"], mastery_normal=mastery_normal, costs_action=t["costs_action"], targets=targets)
            if "extra_hits" in t and level >= t["extra_hits"][0]:
                s["hits"] = t["hits"] + t["extra_hits"][1]
            if "icd" in t:
                icd = t["icd"]
                if "icd_haste" in t and level >= t["icd_haste"][0]:
                    icd = t["icd"] * t["icd_haste"][1]
                s["icd"], s["window"] = icd, t["window"]
            if "proc_chance" in t:
                s["proc_chance"] = t["proc_chance"]
            if key in D.MAPLE_HERO_RATIOS:
                s["maple_ratio"] = D.MAPLE_HERO_RATIOS[key]
            if "extra_fd" in t:
                s["extra_fd"] = helper_pct[t["extra_fd"]] if unlocked(t["extra_fd"]) else 0.0
            SKILLS[key] = s
        self.normal_targets = {k: v["targets"] for k, v in SKILLS.items()}

        # ---- Status/KO engine pass 2: the damage skills' casts (weight of one cast = its boss damage before any timing factor) ----
        self.phi_rows_engine = {}
        if status_on:
            def percast(key):
                if not unlocked(key):
                    return 0.0
                sk = SKILLS[key]
                hd = self.skill_hit(sk)
                hits = sk["hits"] * (fight_mod.ticks(capped_window(sk["window"]), sk["icd"]) if sk.get("icd") else 1)
                b_mult = self.boss_mult(sk.get("mastery_boss", 0))
                return sk.get("proc_chance", 100) / 100 * hits * hd * b_mult
            c_slot = (ARROW_STREAM_HITS * arrow_stream_hit * self.boss_mult(arrow_stream_mastery_boss_damage))
            groups = status_mod.build_groups(D, unlocked, SKILLS, percast, capped_window,
                                             lambda cast: eff_cooldown(SKILLS[cast]["cooldown"], SKILLS[cast]["costs_action"], exempt=cast in D.CDR_EXEMPT),
                                             stun_keys={e["key"] for e in D.PLAYER_STUN})
            E_ENGINE = status_mod.solve_groups(self, D, eng_host, groups, c_slot, ENGINE_N, sens)
            E_FS = E_ENGINE["fs"]
        self.e_engine = E_ENGINE
        self.attack_bucket_sum = attack_bucket_sum

        # ---- Cast rate (subtracted from Arrow Stream) ----
        cost_action_rows = []
        for key in D.COST_ACTION_ORDER:
            if key in SKILLS:
                cost_action_rows.append((key, SKILLS[key]["cooldown"], True, 1))
            else:
                cost_action_rows.append((key, D.BUFF_COOLDOWNS[key], True, 1))

        def cast_count(k, cd, ca):
            if k in ENGINE_N:
                return ENGINE_N[k]
            return fight.exact_casts(eff_cooldown(cd, ca)) if k in D.BUFF_KEYS_STARTUP else fight.non_buff_casts(eff_cooldown(cd, ca))

        if fixed_duration_active:
            cast_rate = sum(cast_count(k, cd, ca) * aps for k, cd, ca, aps in cost_action_rows if ca and unlocked(k)) / fight_duration
        else:
            cast_rate = sum((1 / eff_cooldown(cd, ca)) * aps for k, cd, ca, aps in cost_action_rows if ca and unlocked(k))
        self.cast_rate = cast_rate
        self.arrow_stream_per_second = arrow_stream_per_second = max(0, actions_per_second - cast_rate)

        # ---- Arrow Stream DPS (always put in the ledger first: the verify script's _BRANCH_PAIRS insertion order) ----
        self.branch_pair("ARROW_STREAM", arrow_stream_per_second, arrow_stream_per_second, ARROW_STREAM_HITS * arrow_stream_hit,
                         arrow_stream_mastery_boss_damage, 0, arrow_stream_targets)
        if not unlocked("ARROW_STREAM"):
            self.ledger.put_zero("ARROW_STREAM")
        as_pair = self.ledger.pair("ARROW_STREAM")
        self.arrow_stream_dps = arrow_stream_dps = (1 - normal_weight) * as_pair[0] + normal_weight * as_pair[1]

        # ---- PROC RULE (user, 2026-11-04): a chance proc rolls once per ATTACK per ENEMY HIT, never per damage line ----
        attacks_per_cast = {k: 1 for k in D.TRIGGER_CAST_ROWS}
        attacks_per_cast["HURRICANE"] = SKILLS["HURRICANE"]["hits"]      # each arrow is its own attack
        trigger_attacks = []     # (attacks per second, enemies hit per attack in the normal branch)
        if unlocked("ARROW_STREAM"):
            trigger_attacks.append((arrow_stream_per_second, min(arrow_stream_targets, max_enemies_hit)))
        for k in D.TRIGGER_CAST_ROWS:
            if not unlocked(k):
                continue
            s_ = SKILLS[k]
            cd_ = eff_cooldown(s_["cooldown"], s_["costs_action"])
            casts_per_sec = ((ENGINE_N[k] if k in ENGINE_N else fight.non_buff_casts(cd_)) / fight_duration) if fixed_duration_active else (1 / cd_)
            trigger_attacks.append((casts_per_sec * attacks_per_cast[k], min(s_["targets"], max_enemies_hit)))
        self.trig_attacks_total = trig_attacks_total = sum(a for a, n in trigger_attacks)
        self.trig_enemy_rolls = trig_enemy_rolls = sum(a * n for a, n in trigger_attacks)
        fc = D.FM_CHANCE
        self.fm_chance = fm_chance = (fc["base"] + fc["per"] * (actions_per_second - 1) * 100 / fc["span"]) / 100
        self.fm_x_boss = fm_x_boss = fm_chance * trig_attacks_total
        self.fm_x_normal = fm_x_normal = sum(a * dmg.q_roll(fm_chance, n) for a, n in trigger_attacks)

        def flash_mirage_rate(x):
            icd = SKILLS["FLASH_MIRAGE"]["cooldown"]   # real ICD: Skill Cooldown Decrease does not apply (user, 2026-11-04)
            if x <= 0:
                return 0.0
            cycle = icd + 1 / x
            if fixed_duration_active:
                avail = max(0.0, fight_duration - buff_cast_startup_time)
                casts = 0 if avail <= 0 else math.floor(avail / cycle) + 1
                return casts / fight_duration
            return 1 / cycle

        # ---- Damage rows ----
        skill_dps = {}
        for key, s in SKILLS.items():
            if not unlocked(key):
                skill_dps[key] = 0.0
                self.ledger.put_zero(key)
                continue
            hd = self.skill_hit(s)
            proc_prob = 1 - (1 - s.get("proc_chance", 100) / 100) ** 1
            if key == "FINAL_ATTACK_BOW":
                # no ICD: expected procs per attack = c (one enemy) or c x N (every enemy hit rolls); each proc hits only the enemy it rolled for
                skill_dps[key] = self.branch_blend(key, proc_prob * trig_attacks_total, proc_prob * trig_enemy_rolls, hd, 0, 0, 1)
                continue
            if key == "FLASH_MIRAGE":
                skill_dps[key] = self.branch_blend(key, s["hits"] * flash_mirage_rate(fm_x_boss), s["hits"] * flash_mirage_rate(fm_x_normal),
                                                   hd * proc_prob, 0, 0, s["targets"])
                continue
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
            skill_dps[key] = self.branch_blend(key, rate, rate, hd * proc_prob, s.get("mastery_boss", 0), s.get("mastery_normal", 0),
                                               s["targets"])
        self.skill_dps = skill_dps
        self.player_dps = player_dps = arrow_stream_dps + sum(skill_dps.values())

        # ---- player's boss-only / normal-only totals, summed in the ledger's insertion order exactly like the verify script ----
        pairs = self.ledger.pairs
        self.pb_total = sum(p[0] for p in pairs.values())
        self.pn_total = sum(p[1] for p in pairs.values())
        self.pu_total = sum(pairs[k][0] for k in D.STATUS_UNIFORM_ROWS)

        # ---- companion: src/companion_python_model.py fed with this model's own pipeline numbers ----
        self.begin_companion(summon_time_inc)          # (effective Summoning Time Increase % = Inputs + Arwen's Glass Shoes)
        if (choice != "None" and c_level >= 1) or pl_on or sens.get("want_comp_host"):   # (Sensitivity: the comparison tables need the host with no companion / stun too)
            basic_b, basic_n = pairs["ARROW_STREAM"][:2]
            boss_pct_c = boss_damage + self.art_boss_damage + self.monster_dmg_bonus
            norm_pct_c = normal_damage + self.art_normal_damage + self.monster_dmg_bonus
            comp_host = dict(comp_mod.host_common(self, pre, eff, basic_b, basic_n),
                unit=self.hit_damage(100.0, True) / 100, sd=self.skill_damage + self.art_skill_damage, aps=actions_per_second,
                avgbuff=attack_bucket_mult, attack_bucket_avg=self.attack_bucket_avg, agg_damage_avg=self.art_damage,
                avgbuff_snap=lambda charm, extra: 1 + (marksmanship_base_pct + marksmanship_cond_avg + illusion_step_pct + attack_mult_delta + pre.agg_attack_pct
                                                       - pre.charm_avg + charm + extra) / 100,
                boss_pct=boss_pct_c, norm_pct=norm_pct_c, cr_total=crit_rate + self.crit_rate_bonus + self.art_crit_rate,
                cd_total=crit_damage + self.crit_damage_bonus, def_pen=def_pen,
                taken_bucket=0.0 if monster_type == "pvp" else (1 - normal_weight) * boss_pct_c + normal_weight * norm_pct_c, pst=pst)
            self.comp_host = comp_host
            self.run_companion(comp_host, choice, c_level, summon_time_inc, pl_on)
        self.total_dps = player_dps + self.companion_dps
        # extra scalars for the golden test / UI
        self.sharp_eyes_uptime = sharp_eyes_uptime
        self.illusion_step_avg = illusion_step_avg
        self.marksmanship_base_pct = marksmanship_base_pct
        self.marksmanship_cond_avg = marksmanship_cond_avg

    # ------------------------------------------------------------------------------------------------------------------
    def row_dps(self, key):
        return self.arrow_stream_dps if key == "ARROW_STREAM" else self.skill_dps.get(key, 0.0)

    def derived_extra(self):
        return dict(
            basic_attacks_per_second=self.arrow_stream_per_second, avg_buff_mult=self.attack_bucket_mult, as_bonus=self.as_bonus,
            attack_bucket_mult=self.attack_bucket_mult, attack_bucket_sum=self.attack_bucket_sum,
            skill_coefficient_base=self.skill_coefficient_base, buff_cast_startup_time=self.buff_cast_startup_time,
            crit_damage_bonus=self.crit_damage_bonus, crit_rate_bonus=self.crit_rate_bonus + self.art_crit_rate,
            mortal_blow_bonus=self.mortal_blow_bonus, monster_dmg_bonus=self.monster_dmg_bonus,
            maple_hero_pct=self.maple_hero_pct, quiver_cartridge_cooldown=self.quiver_cartridge_cooldown,
            trigger_attacks_per_second=self.trig_attacks_total, trigger_enemy_rolls_per_second=self.trig_enemy_rolls,
            flash_mirage_chance=self.fm_chance, flash_mirage_trigger_rate_boss=self.fm_x_boss,
            flash_mirage_trigger_rate_normal=self.fm_x_normal,
        )


fields, schema, defaults = classapi.make(CLASS_ID, CLASS_NAME, STAT_IDENTITY, _MAIN_STAT_FIELDS, D)
artifact_schema = classapi.artifact_schema


def model(inputs):
    """The evaluated model object (everything ``compute`` reports plus the internals engine/sensitivity.py reads: ``comp_host``, ``e1`` /
    ``e_engine`` (the timeline strip), ``art_effects`` ...).  Same input dict as ``compute``; honours ``inputs["_sens"]`` (engine/common/sens.py)."""
    return _Model(inputs)


def compute(inputs):
    """DPS of one Bowmaster setup.  ``inputs``: dict (see module docstring / ``schema()``); returns a JSON-friendly dict:

    total_dps / player_dps / boss_dps / normal_dps / player_boss_dps / player_normal_dps, skills (per damage row: key, name, dps, share,
    boss_dps, normal_dps, unlocked), companion (None or dps/boss/normal/share + model details; choice "None" = Covering Fire stun uplift only),
    engine_on (Status/KO timeline engine), engine (its cast counts and timing factors), derived (ATTACK, STAT_DAMAGE, actions/s, buff
    multipliers, computed Inputs rows ...).
    """
    return _Model(inputs).result()
