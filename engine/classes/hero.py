"""Hero: the DPS model of ``src/verify_hero_workbook.py`` as a function of a plain inputs dict.

    from engine.classes import hero
    result = hero.compute(hero.defaults("World Boss"))

``compute(inputs)`` is bit-identical to the verify script (same operations in the same order); the verify script stays the independent
reference, ``tests/golden/test_hero.py`` compares the two (with no artifact equipped).  Artifact equip effects (``inputs["artifacts"]``, up to 4
slots) are ported in ``engine/artifacts.py`` (shared with FP-Mage; the Artifacts sheet of the two builders is identical) and wired the way
``src/build_hero_workbook.py`` wires them; the verify script does not model artifacts, so ``tests/golden/test_hero_artifacts.py`` checks them
against the workbook itself (``tests/golden/hero_artifacts_golden.json``, evaluated with ``formulas``).

Inputs dict: the workbook's Inputs keys already resolved for the chosen content type (see ``schema()``), plus ``companion_level`` (the
level of the chosen companion, 0 = not unlocked).  A missing / ``None`` value reads as 0, exactly like a blank workbook cell.

Hero specifics (all in the verify script): the player's own Rush stun (22 s -> 15.4 s from Lv90, 2.5 s stun) feeds the Status Effect Damage /
KO timeline and - in Breakthrough / Hero Dungeon - lengthens the boss phase, so a "companion" result exists from Lv63 even with no companion
chosen (choice "None": only the stun uplift, reported under ``companion`` with ``choice == "None"``); Spirit Blade (the only engine-timed
buff); Combo Attack / Combo Synergy at steady-state max stacks; Scaring Sword / Magic Crash / Puncture weakens as one global damage-taken
bonus added to both Boss / Normal Monster Damage terms; Advanced Combo's live Defense Penetration (Lv130+); Raging Blow as the basic attack
with Final Attack and Advanced Final Attack folded in.  The verify script's ``stl._dp`` "tie-aware" monkeypatch is a pure delegation to the
original function (the shared dynamic programme carries the 1e-9 relative tie tolerance itself), so it is not reproduced.
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
from ..data import hero as D
from .. import artifacts as art_mod
import status_timeline as stl  # noqa: E402  (src/status_timeline.py through the shim)

CLASS_ID = "hero"
CLASS_NAME = "Hero"
STAT_IDENTITY = {"main": "STR", "sub": "DEX"}

_MAIN_STAT_FIELDS = [
    schema_mod.field("flat_str", "Flat STR", "Main stats", "float", "flat", 0, help="Include Iron Body's own +30 if unlocked."),
    schema_mod.field("str_pct", "STR %", "Main stats", "float", "%", 0),
    schema_mod.field("dex", "DEX", "Main stats", "float", "flat", 0),
]


class _Model(model_mod.ModelBase):
    DATA = D

    # ------------------------------------------------------------------------------------------------------------------
    # ---- per-hit pipeline ----
    def hit_damage(self, coeff_pct_val, is_basic, mastery_boss, mastery_normal, maple_ratio=0.0, extra_fd_pct=0.0):
        base_damage = self.attack * (coeff_pct_val / 100)
        dmg_reduction = dmg.defense_reduction(self.monster_defense, self.def_pen_eff)
        maple_mult = (1 + maple_ratio * self.maple_hero_pct / 100) if maple_ratio else 1.0
        final_mult = ((1 + (self.final_damage + self.final_damage_extra) / 100) * (1 + self.art_final_damage / 100)
                      * maple_mult * (1 + extra_fd_pct / 100))
        source_pct = (self.basic_attack_damage + self.art_basic_attack_damage) if is_basic else (self.skill_damage + self.art_skill_damage)
        # Boss/Normal Monster Damage% is deliberately NOT applied here - it is blended per branch (its own multiplier x its own target count)
        base_hit = (
            base_damage * (1 + self.stat_damage / 100) * (1 + self.damage / 100)
            * (1 + self.damage_amp / 100) * dmg_reduction * final_mult * (1 + source_pct / 100)
            * self.attack_bucket_mult * (1 + self.art_joint_damage / 100)
        )
        return dmg.expected_hit(base_hit, self.min_damage, self.max_damage, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate,
                                self.crit_damage + self.crit_damage_bonus)

    def skill_hit(self, key, s):
        """Expected damage of one hit of a damage skill (before the boss/normal branch multipliers)."""
        # a skill mastery MULTIPLIES the skill's damage (game-confirmed 2026-11-03); fold-ins stay additive
        pct = self.coeff_pct(s["base"], s["fidx"], True, s["step"]) * (1 + s.get("mastery", 0) / 100) + s.get("fold", 0)
        combo_excess_fd = (D.ENHANCED_RB_COMBO_FD["per_stack"] * max(0, self.combo_stacks - D.ENHANCED_RB_COMBO_FD["free_stacks"])
                           if (key == "ENHANCED_RAGING_BLOW" and self.level >= D.ENHANCED_RB_COMBO_FD["level"]) else 0.0)
        return self.hit_damage(pct, False, s.get("mastery_boss", 0), s.get("mastery_normal", 0),
                               maple_ratio=s.get("maple_ratio", 0.0), extra_fd_pct=combo_excess_fd)

    # ---- targets and branch blending ----
    def blend_branches(self, key, unit, mastery_boss, mastery_normal, targets):
        b, n = self.branch_multipliers(mastery_boss, mastery_normal, targets)
        fb, fn = self.timing_factors(key)
        return self.ledger.blend_unit(key, unit, b, n, fb, fn)

    # ------------------------------------------------------------------------------------------------------------------
    def _build(self, inp):
        ct = self.read_content(inp)
        level = self.level
        sens = self.sens
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
        flat_str, str_pct, dex_stat = inp("flat_str"), inp("str_pct"), inp("dex")
        self.stat_damage = (flat_str * (1 + str_pct / 100)) * 0.01 + dex_stat * 0.0025
        self.damage = inp("damage")
        self.damage_amp = inp("damage_amp")
        self.boss_damage = inp("boss_damage")
        self.normal_damage = inp("normal_damage")
        self.status_effect_damage = status_effect_damage = inp("status_effect_damage")
        self.final_damage = inp("final_damage")
        if sens.get("final_damage_factor") is not None:
            # Sensitivity: Hero's workbook block retypes Inputs!final_damage INSIDE the additive Final Damage bucket - a baked-in Final Damage artifact what-if is a factor on the
            # TYPED value ((1 + F/100) x factor - 1), not on the live artifact bucket (``baked_fd_form="typed"`` in engine/sens_specs/hero.py)
            self.final_damage = ((1 + self.final_damage / 100) * sens["final_damage_factor"] - 1) * 100
        self.min_damage = inp("min_damage") + sens.get("min_damage_delta", 0.0)      # (+ Weapon Mastery's level delta, Sensitivity only)
        self.max_damage = inp("max_damage") + sens.get("max_damage_delta", 0.0)      # (+ Combat Mastery's level delta / Athena's Gloves' dependent Max Damage, Sensitivity only)
        # Book of Ancient's direct Crit Rate what-if feeds Ring of Cycles' threshold AND the live crit rate; Chance Attack's level delta only the live one: the workbook's block
        # threshold (`roc_threshold_cr_block`) has no passive Crit Rate delta (KNOWN_GAPS "Hero Sensitivity fixes", item "Not changed")
        self.crit_rate_input = inp("crit_rate") + sens.get("crit_rate_threshold_extra", 0.0)
        self.crit_rate = self.crit_rate_input + sens.get("crit_rate_delta", 0.0)
        self.crit_damage = inp("crit_damage")
        attack_speed_base = inp("attack_speed")
        def_pen = sens_mod.def_pen_with_dose(inp("def_pen"), sens)   # Sensitivity: Reindeer's Spear equip toggle folds one signed dose of its base Def Pen into the typed value (applied to the rows too in Hero's block)
        # Advanced Combo (Lv130): +1% Defense Penetration per combo stack, combined with the gear value (diminishing returns)
        live_defpen = ((8 if level >= 118 else (7 if level >= 110 else 5)) if level >= D.LIVE_DEFPEN[0] else 0)
        self.def_pen_eff = 100 - (100 - def_pen) * (1 - live_defpen / 100)
        self.basic_attack_damage = inp("basic_attack_damage") + sens.get("basic_attack_damage_delta", 0.0)   # (+ Physical Training's level delta, Sensitivity only)
        self.skill_damage = inp("skill_damage") + sens.get("skill_damage_delta", 0.0)      # (+ Combat Mastery's level delta, Sensitivity only)
        basic_attack_target_increase = inp("basic_attack_target_increase")
        buff_duration_increase_pct = inp("buff_duration_increase_pct") + sens.get("bdi_extra", 0.0)     # (+ Shamaness Marble what-if, Sensitivity only; Puncture's window reads it too)
        summon_time_inc = inp("companion_summon_time_increase_pct")
        self.pvp_len = pvp_len = inp("pvp_fight_length") or content_mod.DEFAULT_PVP_FIGHT_LENGTH
        fight = self.fight = fight_mod.Fight(ct, pvp_len, inp("skill_cooldown_decrease"), buff_duration_increase_pct,
                                             inp("max_enemies_hit"))
        self.ledger = blend_mod.BranchLedger(normal_weight)

        # ---- artifacts (equip effects): slots, the early quantities (Attack% bucket / Hexagon / Charm) and Soul Contract's cooldown decrease ----
        self.eq = eq = sens["eq"] if "eq" in sens else art_mod.resolve_slots(inp.raw("artifacts"))   # (Sensitivity: an equip-toggle what-if may exceed 4 slots)
        actx = self.art_ctx = art_mod.Ctx(self.content_type, monster_type, fight_duration, pvp_len, fixed_duration_active,
                                          crit_rate=self.crit_rate_input, attack_speed=attack_speed_base)
        pre = self.art_pre = art_mod.Pre(eq, actx)
        # Arwen's Glass Shoes: the companion's effective Summoning Time Increase % = the Inputs value + the artifact (every use below)
        summon_time_inc += art_mod.summon_time_inc_pct(eq)
        fight.cd_extra_pct = art_mod.soul_contract_pct(eq, self.content_type)
        # live artifact terms of the damage pipeline; zero / neutral until the full effects are known (after the buff-casting startup delay)
        self.art_final_damage = self.art_joint_damage = self.art_skill_damage = self.art_basic_attack_damage = 0.0
        self.art_boss_damage = self.art_normal_damage = self.art_crit_rate = 0.0
        self.extra_boss = self.extra_norm = 1.0
        self.ph_b = self.ph_n = 1.0
        eff_cooldown = fight.eff_cooldown
        eff_duration = fight.eff_duration

        basic_lvl = self.sl.input_level(4)
        self.skill_coefficient_base = D.RAGING_BLOW_BASE * factors.get_factor(basic_lvl, 21) / 1000

        # ---- Helper rows (Final Attack, Advanced Final Attack, Maple Hero): own coefficients only, no independent DPS ----
        fa, afa = D.FINAL_ATTACK, D.ADVANCED_FINAL_ATTACK
        final_attack_pct = (coeff_pct(fa["base"], fa["fidx"], True, fa["step"]) * (1 + gated(fa["gated"]) / 100)
                            if unlocked("FINAL_ATTACK_HELPER") else 0.0)
        advanced_final_attack_pct = (coeff_pct(afa["base"], afa["fidx"], True, afa["step"]) + gated(afa["gated"])
                                     if unlocked("ADVANCED_FINAL_ATTACK_HELPER") else 0.0)
        mh = D.MAPLE_HERO
        self.maple_hero_pct = coeff_pct(mh["base"], mh["fidx"], True, mh["step"]) if unlocked("MAPLE_HERO_HELPER") else 0.0

        # Raging Blow's own coefficient includes Final Attack + Advanced Final Attack folded in, plus its own Damage / Boss Damage chains
        raging_blow_final_attack_addition = (
            final_attack_pct / 100 * (1 + advanced_final_attack_pct / 100) * D.FINAL_ATTACK_RAGING_BLOW_SHARE
            if unlocked("FINAL_ATTACK_HELPER") else 0.0
        )
        raging_blow_mastery_damage = gated(D.RAGING_BLOW_MASTERY)
        self.raging_blow_mastery_boss_damage = raging_blow_mastery_boss_damage = gated(D.RAGING_BLOW_BOSS_MASTERY)
        raging_blow_pct = self.skill_coefficient_base * (1 + raging_blow_mastery_damage / 100) + raging_blow_final_attack_addition
        raging_blow_targets = 6 + basic_attack_target_increase
        hits0, hits_lvl, hits1 = D.RAGING_BLOW_HITS
        raging_blow_hits = hits1 if level >= hits_lvl else hits0

        # ---- Attack% bucket: Combo Attack (steady-state max stacks) + Spirit Blade (duty-cycle) ----
        self.combo_stacks = combo_stacks = 8 if level >= 118 else (7 if level >= 110 else 5)
        ca = D.COMBO_ATTACK
        combo_attack_pct = (coeff_pct(ca["base"], ca["fidx"], True, ca["step"]) + gated(ca["gated"])) if unlocked("COMBO_ATTACK") else 0.0
        combo_attack_avg = combo_attack_pct * combo_stacks if unlocked("COMBO_ATTACK") else 0.0
        sb = D.SPIRIT_BLADE
        spirit_blade_pct = coeff_pct(sb["base"], sb["fidx"], True, sb["step"]) if unlocked("SPIRIT_BLADE") else 0.0
        spirit_blade_cd = self.haste(sb["cooldown"], sb["haste"])
        spirit_blade_avg = (spirit_blade_pct * fight.buff_uptime(spirit_blade_cd, sb["duration"], True)
                            if unlocked("SPIRIT_BLADE") else 0.0)
        # artifact Attack% (Old Music Box, Secret Map, Reindeer's Spear, Alliance Badge, Bottle of Emotion, Charm's average) joins the same additive bucket
        self.attack_bucket_mult = 1 + (combo_attack_avg + spirit_blade_avg + pre.agg_attack_pct) / 100

        # ---- Combo Synergy (steady-state max stacks, Final Damage per stack) ----
        cs = D.COMBO_SYNERGY
        combo_synergy_pct = (coeff_pct(cs["base"], cs["fidx"], True, cs["step"]) + gated(cs["gated"])) if unlocked("COMBO_SYNERGY") else 0.0
        combo_synergy_avg = combo_synergy_pct * combo_stacks if unlocked("COMBO_SYNERGY") else 0.0

        # ---- Enrage (fires on its own fixed interval, treated as this row's own cooldown) ----
        efd, ecd = D.ENRAGE_FD, D.ENRAGE_CRITDMG
        enrage_fd_pct = coeff_pct(efd["base"], efd["fidx"], True, efd["step"]) if unlocked("ENRAGE_FD") else 0.0
        enrage_fd_avg = fight.buff_uptime(efd["cooldown"], efd["duration"], False) * enrage_fd_pct if unlocked("ENRAGE_FD") else 0.0
        enrage_critdmg_pct = coeff_pct(ecd["base"], ecd["fidx"], True, ecd["step"]) if unlocked("ENRAGE_CRITDMG") else 0.0
        enrage_critdmg_avg = (fight.buff_uptime(ecd["cooldown"], ecd["duration"], False) * enrage_critdmg_pct
                              if unlocked("ENRAGE_CRITDMG") else 0.0)

        self.crit_rate_bonus = 0.0       # no live Crit-Rate-buff source exists in this kit (the artifact crit-rate bucket is ``art_crit_rate``)
        self.crit_damage_bonus = enrage_critdmg_avg
        self.final_damage_extra = (enrage_fd_avg + combo_synergy_avg + (D.FLAT_FINAL_DAMAGE[1] if level >= D.FLAT_FINAL_DAMAGE[0] else 0)
                                   + sens.get("final_damage_delta", 0.0))      # (+ Power Stance's level delta, Sensitivity only)

        # ---- Scaring Sword (proc-chance x duty-cycle) + the weakens: the Global Monster Damage-Taken Bonus% ----
        ss = D.SCARING_SWORD
        scaring_sword_pct = (coeff_pct(ss["base"], ss["fidx"], True, ss["step"]) + gated(ss["gated"])) if unlocked("SCARING_SWORD") else 0.0
        scaring_sword_avg = (
            scaring_sword_pct * (ss["proc_chance"] / 100) * fight.buff_uptime(ss["uptime_cooldown"], ss["uptime_duration"], True)
            if unlocked("SCARING_SWORD") else 0.0
        )
        mc = D.MAGIC_CRASH_WEAKEN
        magic_crash_weaken_avg = ((mc["pct"] * min(1, mc["window"] / eff_cooldown(mc["cooldown"], True)))
                                  if (unlocked("MAGIC_CRASH") and level >= mc["level"]) else 0.0)
        pw = D.PUNCTURE_WEAKEN
        puncture_weaken_pct = coeff_pct(pw["base"], pw["fidx"], True, pw["step"]) * (pw["boost"][1] if level >= pw["boost"][0] else 1.0)
        puncture_weaken_avg = (
            puncture_weaken_pct * min(1.0, pw["window"] * (1 + buff_duration_increase_pct / 100) / eff_cooldown(pw["cooldown"], True))
            if unlocked("PUNCTURE") else 0.0
        )
        self.monster_dmg_bonus = scaring_sword_avg + magic_crash_weaken_avg + puncture_weaken_avg

        # ---- Nimble Feet (Attack Speed buff, duty-cycle averaged) ----
        nf = D.NIMBLE_FEET
        nimble_feet_pct = coeff_pct(nf["base"], nf["fidx"], False, nf["step"])
        nimble_avg = fight.buff_uptime(nf["cooldown"], nf["duration"], True) * nimble_feet_pct if unlocked("NIMBLE_FEET") else 0.0
        self.as_bonus = as_bonus = nimble_avg
        self.actions_per_second = actions_per_second = dmg.actions_per_second(attack_speed_base + sens.get("attack_speed_extra", 0.0), as_bonus)   # (+ Weapon Acceleration's level delta / Athena's Gloves what-if, Sensitivity only)

        # ---- Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`) ----
        choice, c_level = comp_mod.read_choice(inp)
        self.companion_choice, self.companion_level = choice, c_level
        # The player's own stunning skills (game table): Rush stuns for 2.5 s, cast on cooldown from the start
        player_stun = [dict(e, cd=self.haste(D.DAMAGE_SKILLS["RUSH"]["cooldown"], D.DAMAGE_SKILLS["RUSH"]["haste"])) for e in D.PLAYER_STUN]
        pl_on = any(unlocked(e["key"]) for e in player_stun)
        stun_info = comp_mod.stun_probe(ct, fight, pvp_len, choice, c_level, summon_time_inc)
        hasstun = bool(stun_info and stun_info.get("hasstun")) or pl_on
        ko = content_mod.ko_windows(fight_duration)
        self.status_on = status_on = fixed_duration_active and normal_weight == 0 and (content_type in ko or hasstun)
        t0_pl = 0.0 if status_on else ((sum(1 for k in D.STARTUP_BUFFS if unlocked(k)) / actions_per_second) if fixed_duration_active else 0.0)
        self.pst = pst = [dict(id=e["id"], typ=e["typ"], cd=eff_cooldown(e["cd"], True), dur=e["dur"],
                               p=e["p"], on=unlocked(e["key"]), t0=t0_pl, tick=1.0, win=0.0) for e in player_stun]
        stun_info, stun_pin = comp_mod.stun_windows(ct, fight, pvp_len, pst, choice, c_level, summon_time_inc, sens)
        self.stf_b = stun_pin["stunfracB"]
        self.stf_n = stun_pin["stunfracN"]
        attack_bucket_mult = self.attack_bucket_mult
        self.engine_n = ENGINE_N = {}
        E_ENGINE = None
        self.phi_rows = {}
        self.phi_unif = 1.0
        E_FS = {}
        attack_bucket_sum = combo_attack_avg + spirit_blade_avg      # Attack% bucket (in %, without artifacts) the companion's snapshot sees on average
        e1 = None
        if status_on:
            # (the verify script raises KeyError here when no companion is chosen and Rush is locked, i.e. level < 63 in a KO content: the
            # companion model's early return carries no stun_vector.  The engine reads that as "no companion stun" instead of crashing.)
            comp_stun = stun_info["stun_vector"](stl.NB_MAX) if "stun_vector" in stun_info else [0.0] * stl.NB_MAX
            stun_vec = [min(1.0, a + b) for a, b in zip(comp_stun, stl.pl_stun_vector([dict(e, t0=0.0) for e in pst], fight_duration, stl.NB_MAX))]
            buffs = [dict(id="SB", kind="atk", F=spirit_blade_pct, dur=eff_duration(sb["duration"]), cd=eff_cooldown(spirit_blade_cd, True),
                          on=unlocked("SPIRIT_BLADE"))]
            eng_host = dict(T=fight_duration, S=status_effect_damage, ko=ko.get(content_type, []), hex_v=pre.hex_v, hex_period=20, hex_max=3,
                            A0=combo_attack_avg + pre.a0, charm_v=pre.charm_val, hex_avg=pre.hex_avg, c_slot=0.0, stun=stun_vec, buffs=buffs,
                            groups=[])
            e1 = sens["strip"][0] if "strip" in sens else stl.solve(eng_host)   # pass 1: the buff schedule (independent of the skill weights); Sensitivity may reuse the main strip
            attack_bucket_mult = self.attack_bucket_mult = e1["Bbuff_mean"]
            ENGINE_N["SPIRIT_BLADE"] = e1["buffs"]["SB"]["n"]
            if unlocked("SPIRIT_BLADE"):
                n, cd, dur = ENGINE_N["SPIRIT_BLADE"], eff_cooldown(spirit_blade_cd, True), eff_duration(sb["duration"])
                up = ((n - 1) * min(dur, cd) + min(dur, max(0.0, fight_duration - (n - 1) * cd))) / fight_duration
                attack_bucket_sum = combo_attack_avg + spirit_blade_pct * up    # the host's exact-uptime formula at the engine's cast count

        self.e1 = e1

        # Buff-Casting Startup Delay: in fixed-duration fights the character casts every unlocked, actively cast buff sequentially at fight
        # start (1/APS s each) before the first damage-skill cast.
        if fixed_duration_active and not status_on:
            self.buff_cast_startup_time = sum(1 for k in D.STARTUP_BUFFS if unlocked(k)) / actions_per_second
        else:
            self.buff_cast_startup_time = 0.0
        fight.startup_time = self.buff_cast_startup_time

        # ---- artifact effects (full): everything that needs the action rate / startup delay / the timeline's status multiplier ----
        actx.aps, actx.startup = actions_per_second, self.buff_cast_startup_time
        # Companion!horn_uptime (computed whether or not Horn Flute is equipped, like the workbook): the share of the player's boss DAMAGE dealt
        # while the companion is out (candidate-0 timing, which already carries the player's own Rush stun in Breakthrough).  The summon timing
        # is damage-independent, so the stub-host run (with the player's stun entries) reports it.
        s0, w0, d_comp, period, ts_window = comp_mod.horn_window(actx, monster_type, fight_duration, pvp_len, summon_time_inc, stun_pin,
                                                                 choice, c_level)
        dw = art_mod.damage_weights(fight_duration, pre.hex_v, combo_attack_avg + pre.a0, pre.charm_val, e1["mult"] if status_on else None)
        actx.horn_uptime = art_mod.horn_flute_uptime(actx, dw, s0, w0, d_comp, period, ts_window)
        eff = self.art_effects = art_mod.Effects(eq, actx, pre)
        self.art_crit_rate = eff.agg_crit_rate                                     # (no live Crit-Rate-buff source in this kit: ``crit_rate_bonus`` stays 0)
        self.crit_damage_bonus = enrage_critdmg_avg + eff.agg_crit_damage
        self.crit_damage_bonus += sens.get("crit_damage_delta", 0.0)              # (Sensitivity: a crit-damage passive's level delta; none in this kit)
        self.crit_damage_bonus += sens_mod.boa_crit_damage_delta(                  # (Book of Ancient equip what-if: pct x the crit-rate total, Sensitivity only)
            sens, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate)
        # the FULL live crit-rate total (Inputs + artifact bucket; CLAUDE.md item 13): what the cube / equipment tables test against the 100% cap
        self.crit_rate_total = self.crit_rate + self.crit_rate_bonus + self.art_crit_rate
        self.art_boss_damage, self.art_normal_damage = eff.agg_boss_damage + sens.get("boss_damage_extra", 0.0), eff.agg_normal_damage   # (+ Star Rock what-if)
        self.art_final_damage = eff.agg_final_damage
        self.art_joint_damage = eff.agg_damage + eff.agg_enemy_dmg_taken            # Hexagon Damage% + Peach Tree / Silver Pendant: one K-column bucket
        self.art_skill_damage, self.art_basic_attack_damage = eff.agg_skill_damage, eff.agg_basic_attack_damage
        self.extra_boss, self.extra_norm = eff.extras(actx, self.monster_defense, self.def_pen_eff,
                                                      self.crit_rate + self.crit_rate_bonus + self.art_crit_rate, self.crit_damage + self.crit_damage_bonus)
        # Hexagon / Charm differ between the two phases of Breakthrough / Hero Dungeon: per-phase timing factor (engine-off rows)
        self.attack_bucket_avg = attack_bucket_sum + pre.agg_attack_pct
        self.ph_b, self.ph_n = art_mod.phase_state_ratios(content_type, fight_duration, pre.hex_v, pre.hex_avg, self.attack_bucket_avg,
                                                          pre.charm_val, pre.charm_avg)

        # ---- Raging Blow (basic attack) hit (needed by the engine weights) ----
        raging_blow_hit = self.hit_damage(raging_blow_pct, True, raging_blow_mastery_boss_damage, 0)

        # ---- Damage skills (level-resolved) ----
        SKILLS = self.skills = {}
        for key, t in D.DAMAGE_SKILLS.items():
            s = dict(step=t["step"], cooldown=self.haste(t["cooldown"], t.get("haste")), hits=t["hits"], base=t["base"],
                     fidx=t["fidx"], mastery=gated(t["mastery"]), mastery_boss=t["mastery_boss"], mastery_normal=t["mastery_normal"],
                     costs_action=t["costs_action"], targets=t["targets"])
            if "extra_hits" in t and level >= t["extra_hits"][0]:
                s["hits"] = t["hits"] + t["extra_hits"][1]
            if "extra_targets" in t and level >= t["extra_targets"][0]:
                s["targets"] = t["targets"] + t["extra_targets"][1]
            if "icd" in t:
                s["icd"], s["window"] = t["icd"], t["window"]
            if key in D.MAPLE_HERO_RATIOS:
                s["maple_ratio"] = D.MAPLE_HERO_RATIOS[key]
            SKILLS[key] = s
        self.normal_targets = {k: v["targets"] for k, v in SKILLS.items()}

        # ---- Status/KO engine pass 2: the damage skills' casts (weight of one cast = its boss damage before any timing factor) ----
        if status_on:
            def percast(key):
                if not unlocked(key):
                    return 0.0
                sk = SKILLS[key]
                hits = sk["hits"] * (fight_mod.ticks(fight.capped_window(sk["window"]), sk["icd"]) if sk.get("icd") else 1)
                return hits * self.skill_hit(key, sk) * self.branch_multipliers(sk.get("mastery_boss", 0), sk.get("mastery_normal", 0),
                                                                                sk["targets"])[0]
            c_slot = raging_blow_hits * raging_blow_hit * self.branch_multipliers(raging_blow_mastery_boss_damage, 0, raging_blow_targets)[0]
            groups = status_mod.build_groups(D, unlocked, SKILLS, percast, fight.capped_window,
                                             lambda cast: eff_cooldown(SKILLS[cast]["cooldown"], SKILLS[cast]["costs_action"]),
                                             stun_keys={e["key"] for e in D.PLAYER_STUN})
            E_ENGINE = status_mod.solve_groups(self, D, eng_host, groups, c_slot, ENGINE_N, sens)
            E_FS = E_ENGINE["fs"]
        self.e_engine = E_ENGINE

        # ---- Cast rate (subtracted from Raging Blow) ----
        cost_action_rows = []
        for key in D.COST_ACTION_ORDER:
            if key in SKILLS:
                cost_action_rows.append((key, SKILLS[key]["cooldown"], True, 1))
            else:
                base_cd, hst = D.BUFF_COOLDOWNS[key]
                cost_action_rows.append((key, self.haste(base_cd, hst), True, 1))

        def cast_count(k, cd, ca):
            if k in ENGINE_N:
                return ENGINE_N[k]
            return fight.exact_casts(eff_cooldown(cd, ca)) if k in D.BUFF_ROW_KEYS else fight.non_buff_casts(eff_cooldown(cd, ca))

        if fixed_duration_active:
            cast_rate = sum(cast_count(k, cd, ca) * aps for k, cd, ca, aps in cost_action_rows if ca and unlocked(k)) / fight_duration
        else:
            cast_rate = sum((1 / eff_cooldown(cd, ca)) * aps for k, cd, ca, aps in cost_action_rows if ca and unlocked(k))
        self.cast_rate = cast_rate
        self.raging_blow_per_second = raging_blow_per_second = max(0, actions_per_second - cast_rate)

        # ---- Raging Blow (basic attack) DPS ----
        self.raging_blow_dps = raging_blow_dps = (
            self.blend_branches("RAGING_BLOW", raging_blow_hits * raging_blow_hit * raging_blow_per_second, raging_blow_mastery_boss_damage, 0,
                                raging_blow_targets)
            if unlocked("RAGING_BLOW") else 0.0)

        skill_dps = {}
        for key, s in SKILLS.items():
            if not unlocked(key):
                skill_dps[key] = 0.0
                continue
            hd = self.skill_hit(key, s)
            proc_prob = 1.0
            eff_cd = eff_cooldown(s["cooldown"], s["costs_action"])
            if status_on and key in ENGINE_N:
                # engine casts: a DoT row's hits = hits per full window x effective casts (last window truncated at the fight end)
                per_cast = s["hits"] * (fight_mod.ticks(fight.capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
                rate = per_cast * (E_FS[key] if key in D.STATUS_FS_KEYS else ENGINE_N[key]) / fight_duration
            elif fixed_duration_active:
                rate = fight.non_buff_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
            else:
                hits = s["hits"] * (fight_mod.ticks(fight.capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
                rate = hits / eff_cd
            skill_dps[key] = self.blend_branches(key, proc_prob * rate * hd, s.get("mastery_boss", 0), s.get("mastery_normal", 0), s["targets"])
        self.skill_dps = skill_dps
        self.player_dps = raging_blow_dps + sum(skill_dps.values())
        self.attack_bucket_sum = attack_bucket_sum

        # ---- player's boss-only / normal-only totals (the companion's damage-share weights; rows in the verify script's insertion order) ----
        row_dps = [("RAGING_BLOW", raging_blow_dps)] + list(skill_dps.items())
        self.pb_total, self.pn_total, self.pu_total = self.ledger.split_totals(row_dps, D.STATUS_UNIFORM_ROWS)

        # ---- companion: src/companion_python_model.py fed with this model's own pipeline numbers ----
        self.begin_companion(summon_time_inc)          # (effective Summoning Time Increase % = Inputs + Arwen's Glass Shoes)
        if (choice != "None" and c_level >= 1) or pl_on or sens.get("want_comp_host"):   # (Sensitivity: the comparison tables need the host with no companion / stun too)
            basic_b, basic_n = self.ledger.pairs.get("RAGING_BLOW", (0.0, 0.0))[:2]
            sb_full = spirit_blade_pct if unlocked("SPIRIT_BLADE") else 0.0
            comp_host = dict(comp_mod.host_common(self, pre, eff, basic_b, basic_n),
                unit=self.hit_damage(100.0, True, 0, 0) / 100, sd=self.skill_damage + self.art_skill_damage, aps=actions_per_second,
                avgbuff=attack_bucket_mult, attack_bucket_avg=self.attack_bucket_avg, agg_damage_avg=self.art_joint_damage,
                avgbuff_snap=lambda charm, extra: 1 + (combo_attack_avg + sb_full + pre.agg_attack_pct - pre.charm_avg + charm + extra) / 100,
                boss_pct=self.boss_damage + self.art_boss_damage + self.monster_dmg_bonus,
                norm_pct=self.normal_damage + self.art_normal_damage + self.monster_dmg_bonus,
                cr_total=self.crit_rate + self.crit_rate_bonus + self.art_crit_rate, cd_total=self.crit_damage + self.crit_damage_bonus,
                def_pen=self.def_pen_eff, taken_bucket=self.art_joint_damage, pst=pst)
            self.comp_host = comp_host
            self.run_companion(comp_host, choice, c_level, summon_time_inc, pl_on)
        self.total_dps = self.player_dps + self.companion_dps

    # ------------------------------------------------------------------------------------------------------------------
    def row_dps(self, key):
        return self.raging_blow_dps if key == "RAGING_BLOW" else self.skill_dps.get(key, 0.0)

    def derived_extra(self):
        return dict(
            basic_attacks_per_second=self.raging_blow_per_second, avg_buff_mult=self.attack_bucket_mult, as_bonus=self.as_bonus,
            attack_bucket_mult=self.attack_bucket_mult, attack_bucket_sum=self.attack_bucket_sum,
            skill_coefficient_base=self.skill_coefficient_base, buff_cast_startup_time=self.buff_cast_startup_time,
            crit_damage_bonus=self.crit_damage_bonus, final_damage_extra=self.final_damage_extra,
            monster_dmg_bonus=self.monster_dmg_bonus, def_pen_effective=self.def_pen_eff, combo_stacks=self.combo_stacks,
            maple_hero_pct=self.maple_hero_pct,
        )


fields, schema, defaults = classapi.make(CLASS_ID, CLASS_NAME, STAT_IDENTITY, _MAIN_STAT_FIELDS, D)
artifact_schema = classapi.artifact_schema


def model(inputs):
    """The evaluated model object (everything ``compute`` reports plus the internals engine/sensitivity.py reads: ``comp_host``, ``e1`` /
    ``e_engine`` (the timeline strip), ``art_effects`` ...).  Same input dict as ``compute``; honours ``inputs["_sens"]`` (engine/common/sens.py)."""
    return _Model(inputs)


def compute(inputs):
    """DPS of one Hero setup.  ``inputs``: dict (see module docstring / ``schema()``); returns a JSON-friendly dict:

    total_dps / player_dps / boss_dps / normal_dps / player_boss_dps / player_normal_dps, skills (per damage row: key, name, dps, share,
    boss_dps, normal_dps, unlocked), companion (None or dps/boss/normal/share + model details; choice "None" = Rush stun uplift only),
    engine_on (Status/KO timeline engine), engine (its cast counts and timing factors), derived (ATTACK, STAT_DAMAGE, actions/s, buff
    multipliers, computed Inputs rows ...).
    """
    return _Model(inputs).result()
