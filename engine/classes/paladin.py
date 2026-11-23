"""Paladin: the DPS model of ``src/verify_paladin_workbook.py`` as a function of a plain inputs dict.

    from engine.classes import paladin
    result = paladin.compute(paladin.defaults("World Boss"))

``compute(inputs)`` is bit-identical to the verify script (same operations in the same order); the verify script stays the independent
reference, ``tests/golden/test_paladin.py`` compares the two (with no artifact equipped).  Artifact equip effects (``inputs["artifacts"]``, up to 4
slots) are ported in ``engine/artifacts.py`` (shared with FP-Mage / Hero; the Artifacts sheet of the builders is identical) and wired the way
``src/build_paladin_workbook.py`` wires them; the verify script does not model artifacts, so ``tests/golden/test_paladin_artifacts.py`` checks them
against the workbook itself (``tests/golden/paladin_artifacts_golden.json``, evaluated with ``formulas``).

Inputs dict: the workbook's Inputs keys already resolved for the chosen content type (see ``schema()``), plus ``companion_level`` (the
level of the chosen companion, 0 = not unlocked).  A missing / ``None`` value reads as 0, exactly like a blank workbook cell.

Paladin specifics (all in the verify script):

* Combat Orders is a temporary SKILL-LEVEL buff: every FactorTable lookup is time-averaged ``(1-u) F(D) + u F(D+bonus)`` (u = Combat Orders' uptime,
  bonus = its own 3rd-job value for 3rd-job skills, +18 for 4th-job skills from Lv104); Combat Orders' own Attack% half (+25, from Lv82) joins the Attack%
  bucket.  The uptime comes from the timeline engine's cast count when the engine is on and the buff is engine-timed (Lv82+), else from the averaged formula.
* Guardian / Divine Blessing / Divine Shield / Greater Vessel of Light are Final Damage buffs in ONE additive bucket with the Final Damage input;
  HP Recovery / Vessel of Light / Combat Orders are Attack% buffs.  With the engine on, HP Recovery, Combat Orders, Guardian and Divine Blessing are timed
  by the player (the Final Damage ones through ``fd_scale = 100 / (100 + FD + rest)``), Vessel of Light (a proc of the basic attack, uptime
  ``min(1, 10 s x P(proc per attack) x basic attacks/s)``) and Divine Shield stay duty-cycle averages.
* Rush (22 s, 15.4 s from Lv90) stuns 2.5 s: part of the Status Effect Damage / KO timeline and, in Breakthrough / Hero Dungeon, lengthens the boss phase,
  so from Lv63 a "companion" result exists even with no companion chosen (``choice == "None"``: only the stun uplift).
* Blast (the basic attack, 5 hits, 6 from Lv136) has Final Attack folded into its coefficient (no Advanced Final Attack in this kit) with Maple Hero's
  +150% share targeting Final Attack.  Divine Judgment is a rate-surrogate row (10 basic attacks, exempt from Cooldown Decrease) spread uniformly.
* Close Combat / Noble Demand / Divine Mark weakens are one global damage-taken bonus (``monster_dmg_bonus``) added to BOTH the Boss and the Normal
  Monster Damage terms and handed to the companion model as ``taken_bucket``.
* Artifacts: the Attack% artifacts (Old Music Box, Secret Map, Reindeer's Spear, Alliance Badge, Bottle of Emotion, Charm's average) join the Attack%
  bucket next to Vessel of Light / HP Recovery / Combat Orders; the Final Damage artifacts (Candle, Flaming Lava, Horn Flute) multiply on top of the
  Final Damage bucket (Guardian / Divine Blessing / Divine Shield / Greater Vessel are INSIDE that bucket); Peach Tree / Silver Pendant (enemy damage
  taken) are part of ``monster_dmg_bonus`` (added to both Boss and Normal Monster Damage terms, like the weakens); Soul Contract's cooldown decrease
  reaches every cooldown (Combat Orders' uptime, the weakens' windows, Rush) through ``Fight.cd_extra_pct``; Combat Orders' schedule (hence the
  skill-level averaging) depends on Hexagon Necklace's stacks (the strip's weights), so its own engine run carries the Hexagon values.
* ``cast_rate_avg`` / ``blast_per_second_avg``: the averaged model's cast rate (no engine counts) feeds Vessel of Light's uptime; the real cast rate then
  uses the engine's counts.
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
from ..data import paladin as D
from ..sens_specs import paladin as _sens_spec      # the passive rows whose level-dependent value is baked into the Inputs (Sensitivity only)
from .. import artifacts as art_mod
import status_timeline as stl  # noqa: E402  (src/status_timeline.py through the shim)

CLASS_ID = "paladin"
CLASS_NAME = "Paladin"
STAT_IDENTITY = {"main": "STR", "sub": "DEX"}

_MAIN_STAT_FIELDS = [
    schema_mod.field("flat_str", "Flat STR", "Main stats", "float", "flat", 0, help="Include Iron Body's own +30 if unlocked."),
    schema_mod.field("str_pct", "STR %", "Main stats", "float", "%", 0),
    schema_mod.field("dex", "DEX", "Main stats", "float", "flat", 0),
]


class _Model(model_mod.ModelBase):
    DATA = D

    # ------------------------------------------------------------------------------------------------------------------
    # ---- Combat Orders' temporary skill-level buff: FactorTable lookups time-averaged with its uptime ----
    def factor_eff(self, lvl, fidx, job_step, is_co=False):
        """FactorTable value time-averaged with Combat Orders' temporary skill-level bonus."""
        if is_co:
            return factors.get_factor(lvl, fidx)
        job4_level, job4_bonus = D.COMBAT_ORDERS_JOB4_BONUS
        bonus = self.co_f if job_step == 3 else (job4_bonus if (job_step == 4 and self.level >= job4_level) else 0)
        return (1 - self.co_u) * factors.get_factor(lvl, fidx) + self.co_u * factors.get_factor(lvl + bonus, fidx)

    def coeff_pct(self, base, fidx, scales, job_step, is_co=False):
        lvl = self.sl.input_level(job_step)
        if not scales:
            return base / 10
        return (base / 10) * (self.factor_eff(lvl, fidx, job_step, is_co) / 1000)

    # ---- per-hit pipeline ----
    def hit_damage(self, coeff_pct_val, is_basic, mastery_boss, mastery_normal, maple_ratio=0.0):
        base_damage = self.attack * (coeff_pct_val / 100)
        dmg_reduction = dmg.defense_reduction(self.monster_defense, self.def_pen)
        maple_mult = (1 + maple_ratio * self.maple_hero_pct / 100) if maple_ratio else 1.0
        final_mult = (1 + (self.final_damage + self.final_damage_extra) / 100) * (1 + self.art_final_damage / 100) * maple_mult
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
        return self.hit_damage(pct, False, s.get("mastery_boss", 0), s.get("mastery_normal", 0), maple_ratio=s.get("maple_ratio", 0.0))

    # ---- targets and branch blending ----
    def blend_branches(self, key, unit, mastery_boss, mastery_normal, targets):
        b, n = self.branch_multipliers(mastery_boss, mastery_normal, targets)
        fb, fn = self.timing_factors(key)
        return self.ledger.blend_unit(key, unit, b, n, fb, fn)

    def weaken_avg(self, pct, duration, cooldown):
        """Steady-state duty-cycle average of a Weaken-style debuff (always the simple duration / cooldown ratio, no CastsInFight branching)."""
        if self.monster_type == "pvp":
            scaled_duration = min(duration * (1 + self.fight.bdi / 100), self.pvp_len)
            return pct * scaled_duration / self.pvp_len
        scaled_duration = duration * (1 + self.fight.bdi / 100)
        return pct * min(1.0, scaled_duration / cooldown)

    def engine_buff(self, bid, F):
        key, kind, cd0, dur0 = D.BUFF_SPEC[bid]
        cd, dur = self.fight.eff_cooldown(cd0, True), self.fight.eff_duration(dur0)
        on = self.unlocked(key) and (key != "COMBAT_ORDERS" or self.level >= D.STATUS_ROW_MIN_LEVEL[key])
        if kind == "ramp":
            return dict(id=bid, kind=kind, F=F, dur=min(dur, cd), cd=cd, on=on, p0=1, p1=1, ramp_t=1, dur0=1)
        return dict(id=bid, kind=kind, F=F, dur=dur, cd=cd, on=on)

    def uptime_at(self, n, cooldown, buff_duration):
        """The workbook's exact-uptime formula at a GIVEN cast count n (fraction of the fight)."""
        return self.fight.exact_buff_uptime(cooldown, buff_duration, n) / self.fight_duration

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
        self.final_damage = final_damage = inp("final_damage")
        if sens.get("final_damage_factor") is not None:
            # Sensitivity: Paladin's workbook block retypes Inputs!final_damage INSIDE the additive Final Damage bucket (with Divine Shield / Guardian / Divine Blessing /
            # Greater Vessel) - a baked-in Final Damage artifact what-if is a factor on the TYPED value ((1 + F/100) x factor - 1), not on the live artifact bucket
            # (``baked_fd_form="typed"`` in engine/sens_specs/paladin.py); every later read (fd_scale, the companion's snapshot) sees the retyped value too
            self.final_damage = final_damage = ((1 + final_damage / 100) * sens["final_damage_factor"] - 1) * 100
        self.min_damage = inp("min_damage") + sens.get("min_damage_delta", 0.0)      # (+ Weapon Mastery's level delta, Sensitivity only)
        self.max_damage = inp("max_damage") + sens.get("max_damage_delta", 0.0)      # (+ Paladin Expert's level delta / Athena's Gloves' dependent Max Damage, Sensitivity only)
        # Book of Ancient's direct Crit Rate what-if feeds Ring of Cycles' threshold AND the live crit rate (this kit has no passive Crit Rate delta)
        self.crit_rate_input = inp("crit_rate") + sens.get("crit_rate_threshold_extra", 0.0)
        self.crit_rate = self.crit_rate_input + sens.get("crit_rate_delta", 0.0)
        self.crit_damage = inp("crit_damage")
        attack_speed_base = inp("attack_speed")
        self.def_pen = sens_mod.def_pen_with_dose(inp("def_pen"), sens)   # Sensitivity: Reindeer's Spear equip toggle folds one signed dose of its base Def Pen into the typed value (applied to the rows too since the 2026-11-22 builder fix)
        self.basic_attack_damage = inp("basic_attack_damage") + sens.get("basic_attack_damage_delta", 0.0)   # (+ Physical Training's level delta, Sensitivity only)
        self.skill_damage = inp("skill_damage") + sens.get("skill_damage_delta", 0.0)      # (+ Paladin Expert's level delta, Sensitivity only)
        basic_attack_target_increase = inp("basic_attack_target_increase")
        summon_time_inc = inp("companion_summon_time_increase_pct")
        self.pvp_len = pvp_len = inp("pvp_fight_length") or content_mod.DEFAULT_PVP_FIGHT_LENGTH
        fight = self.fight = fight_mod.Fight(ct, pvp_len, inp("skill_cooldown_decrease"), inp("buff_duration_increase_pct") + sens.get("bdi_extra", 0.0),
                                             inp("max_enemies_hit"))     # (+ Shamaness Marble what-if, Sensitivity only; every buff window / weaken reads fight.bdi)
        max_enemies_hit = fight.max_enemies_hit
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
        self.co_u = 0.0     # Combat Orders uptime
        self.co_f = 0.0     # Combat Orders' own scaling value = its 3rd-job skill-level bonus
        self.maple_hero_pct = 0.0

        # ---- Sensitivity: the passive rows whose level-dependent value is baked into the Inputs (Weapon Acceleration, Physical Training, Weapon Mastery, Parashock Guard,
        #      Paladin Expert).  The workbook block adds, per row, ``unlocked x (F of the block's own state - the MAIN sheet's F)`` - F is time-averaged with Combat Orders'
        #      skill-level bonus (job steps 3 / 4), so the delta also moves with the block's own Combat Orders uptime (Cooldown Decrease / Buff Duration sweeps: the documented
        #      ~1.6e-4 Parashock Guard residual).  ``passive_ref`` = the main model's values (engine/sensitivity.py ``_Base.block``); the 2nd-job rows (no Combat Orders
        #      bonus) are known now, the 3rd / 4th-job rows once the uptime is.
        passive_ref = sens.get("passive_ref")
        self.passive_values = pv = {}
        as_passive_delta = 0.0

        def passive_delta(p):
            pv[p.hook] = (self.coeff_pct(p.base, p.fidx, True, p.step) if (p.unlock is None or level >= p.unlock) else 0.0)
            return (pv[p.hook] - passive_ref.get(p.hook, 0.0)) if passive_ref is not None else 0.0
        for p in _sens_spec.PASSIVE_LEVELS:
            if p.step <= 2:
                d = passive_delta(p)
                if d:
                    if p.hook == "min_damage_delta":
                        self.min_damage += d
                    elif p.hook == "basic_attack_damage_delta":
                        self.basic_attack_damage += d
                    else:
                        assert p.hook == "attack_speed_extra", p.hook
                        as_passive_delta = d
        basic_lvl = self.sl.input_level(4)

        # ---- Nimble Feet (Attack Speed buff, duty-cycle averaged) - independent of everything below ----
        nf = D.NIMBLE_FEET
        nimble_feet_pct = nf["base"] / 10     # a non-scaling buff
        nimble_avg = fight.buff_uptime(nf["cooldown"], nf["duration"], True) * nimble_feet_pct if unlocked("NIMBLE_FEET") else 0.0
        self.as_bonus = as_bonus = nimble_avg
        # (+ Weapon Acceleration's level delta / Athena's Gloves' direct Attack Speed what-if, Sensitivity only: the block's Actions Per Second reads attack_speed_total_block)
        self.actions_per_second = actions_per_second = dmg.actions_per_second(attack_speed_base + sens.get("attack_speed_extra", 0.0) + as_passive_delta, as_bonus)

        # ---- Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`) ----
        choice, c_level = comp_mod.read_choice(inp)
        self.companion_choice, self.companion_level = choice, c_level
        # The player's own stunning skills (game table): Rush stuns for 2.5 s, cast on cooldown from the start
        rush = D.DAMAGE_SKILLS["RUSH"]
        rush_cooldown = self.haste(rush["cooldown"], rush["haste"])
        player_stun = [dict(e, cd=rush_cooldown) for e in D.PLAYER_STUN]
        pl_on = any(unlocked(e["key"]) for e in player_stun)
        stun_info = comp_mod.stun_probe(ct, fight, pvp_len, choice, c_level, summon_time_inc)
        hasstun = bool(stun_info and stun_info.get("hasstun")) or pl_on
        ko = content_mod.ko_windows(fight_duration)
        self.status_on = status_on = fixed_duration_active and normal_weight == 0 and (content_type in ko or hasstun)

        # Buff-Casting Startup Delay: in fixed-duration fights the character casts every unlocked, actively cast buff sequentially at fight
        # start (1/APS s each) before the first damage-skill cast (0 when the engine is on: buffs are cast when they pay).
        if fixed_duration_active and not status_on:
            self.buff_cast_startup_time = sum(1 for k in D.STARTUP_BUFFS if unlocked(k)) / actions_per_second
        else:
            self.buff_cast_startup_time = 0.0
        fight.startup_time = self.buff_cast_startup_time
        t0_pl = 0.0 if status_on else self.buff_cast_startup_time
        self.pst = pst = [dict(id=e["id"], typ=e["typ"], cd=eff_cooldown(e["cd"], True), dur=e["dur"],
                               p=e["p"], on=unlocked(e["key"]), t0=t0_pl, tick=1.0, win=0.0) for e in player_stun]
        stun_info, stun_pin = comp_mod.stun_windows(ct, fight, pvp_len, pst, choice, c_level, summon_time_inc, sens)
        self.stf_b = stun_pin["stunfracB"]
        self.stf_n = stun_pin["stunfracN"]

        # ---- the engine's buff list (engine pass 1) needs the buffs' cooldowns / durations / (later) their effect values ----
        self.engine_n = ENGINE_N = {}
        E_ENGINE = None
        self.phi_rows = {}
        self.phi_unif = 1.0
        E_FS = {}
        co_engine = False        # Combat Orders' casts come from the engine (level >= its Lv82 Damage Boost mastery)
        stun_vec = None
        if status_on:
            # (the verify script raises KeyError here when no companion is chosen and Rush is locked, i.e. level < 63 in a KO content: the
            # companion model's early return carries no stun_vector.  The engine reads that as "no companion stun" instead of crashing.)
            comp_stun = stun_info["stun_vector"](stl.NB_MAX) if "stun_vector" in stun_info else [0.0] * stl.NB_MAX
            stun_vec = [min(1.0, a + b) for a, b in zip(comp_stun, stl.pl_stun_vector([dict(e, t0=0.0) for e in pst], fight_duration, stl.NB_MAX))]
            co_engine = unlocked("COMBAT_ORDERS") and level >= D.STATUS_ROW_MIN_LEVEL["COMBAT_ORDERS"]
        eng_base = dict(T=fight_duration, S=status_effect_damage, ko=ko.get(content_type, []), hex_v=pre.hex_v, hex_period=20, hex_max=3,
                        hex_avg=pre.hex_avg, charm_v=pre.charm_val, c_slot=0.0, stun=stun_vec, groups=[])

        # ---- Combat Orders' uptime (feeds the +skill-level factor averaging of every row): the engine's cast count when it times Combat Orders ----
        co = D.COMBAT_ORDERS
        e_co = None
        if status_on and co_engine:
            if "strip" in sens:      # Sensitivity: a block that reuses the main strip reads the main strip's Combat Orders cast count (the workbook's R column)
                ENGINE_N["COMBAT_ORDERS"] = sens["strip"][0]["buffs"]["CO"]["n"]
            else:
                e_co = stl.solve(dict(eng_base, A0=pre.a0, buffs=[self.engine_buff("CO", D.COMBAT_ORDERS_ATTACK_PCT)]))
                ENGINE_N["COMBAT_ORDERS"] = e_co["buffs"]["CO"]["n"]

        # ---- Combat Orders (applies to the player too): +skill levels time-averaged via factor_eff ----
        if unlocked("COMBAT_ORDERS"):
            self.co_f = coeff_pct(co["base"], co["fidx"], True, co["step"], is_co=True)
            if "COMBAT_ORDERS" in ENGINE_N:
                self.co_u = self.uptime_at(ENGINE_N["COMBAT_ORDERS"], eff_cooldown(co["cooldown"], True), eff_duration(co["duration"]))
            else:
                self.co_u = fight.buff_uptime(co["cooldown"], co["duration"], True) * 1.0
        # late passives (job steps 3 / 4: time-averaged with Combat Orders' skill-level bonus, so they need its uptime): Parashock Guard joins the additive Attack% bucket
        # (below, next to Vessel of Light), Paladin Expert's Skill Damage / Max Damage the Skill Damage / Max Damage terms
        attack_mult_delta = 0.0
        for p in _sens_spec.PASSIVE_LEVELS:
            if p.step >= 3:
                d = passive_delta(p)
                if p.hook == "attack_mult_delta":
                    attack_mult_delta += d
                elif p.hook == "skill_damage_delta":
                    self.skill_damage += d
                else:
                    assert p.hook == "max_damage_delta", p.hook
                    self.max_damage += d
        self.skill_coefficient_base = D.BLAST_BASE * self.factor_eff(basic_lvl, 21, 4) / 1000
        combat_orders_attack_avg = (D.COMBAT_ORDERS_ATTACK_PCT * self.co_u) if level >= co["attack_min_level"] else 0.0

        # ---- Helper rows (Final Attack, Maple Hero): own coefficients only, no independent DPS ----
        fa = D.FINAL_ATTACK
        final_attack_pct = (coeff_pct(fa["base"], fa["fidx"], True, fa["step"]) * (1 + gated(fa["gated"]) / 100)
                            if unlocked("FINAL_ATTACK_HELPER") else 0.0)
        mh = D.MAPLE_HERO
        self.maple_hero_pct = maple_hero_pct = coeff_pct(mh["base"], mh["fidx"], True, mh["step"]) if unlocked("MAPLE_HERO_HELPER") else 0.0

        # Blast's own coefficient includes Final Attack folded in (single-stage), further multiplied by Maple Hero's +150% FD share targeting Final
        # Attack specifically, plus its own Damage / Boss Damage mastery chains
        blast_final_attack_addition = (
            final_attack_pct / 100 * D.FINAL_ATTACK_BLAST_SHARE * (1 + D.FINAL_ATTACK_MAPLE_SHARE * maple_hero_pct / 100)
            if unlocked("FINAL_ATTACK_HELPER") else 0.0
        )
        blast_mastery_damage = gated(D.BLAST_MASTERY)
        self.blast_mastery_boss_damage = blast_mastery_boss_damage = gated(D.BLAST_BOSS_MASTERY)
        blast_pct = self.skill_coefficient_base * (1 + blast_mastery_damage / 100) + blast_final_attack_addition
        blast_targets = 6 + basic_attack_target_increase
        hits0, hits_lvl, hits1 = D.BLAST_HITS
        blast_hits = hits1 if level >= hits_lvl else hits0

        # ---- Damage skills (level-resolved) ----
        SKILLS = self.skills = {}
        for key, t in D.DAMAGE_SKILLS.items():
            cooldown = (D.JUDGMENT_RATE_ATTACKS / actions_per_second) if key == "DIVINE_JUDGMENT" else self.haste(t["cooldown"], t.get("haste"))
            mb = t["mastery_boss"]
            if isinstance(mb, tuple):          # (base, level, extra from that level on)
                mb = mb[0] + (mb[2] if level >= mb[1] else 0)
            s = dict(step=t["step"], cooldown=cooldown, hits=t["hits"], base=t["base"], fidx=t["fidx"], mastery=gated(t["mastery"]),
                     mastery_boss=mb, mastery_normal=t["mastery_normal"], costs_action=t["costs_action"], targets=t["targets"])
            if "extra_targets" in t and level >= t["extra_targets"][0]:
                s["targets"] = t["targets"] + t["extra_targets"][1]
            if key in D.MAPLE_HERO_RATIOS:
                s["maple_ratio"] = D.MAPLE_HERO_RATIOS[key]
            SKILLS[key] = s
        self.normal_targets = {k: v["targets"] for k, v in SKILLS.items()}

        # ---- Cast rate (subtracted from Blast) ----
        cost_action_rows = []
        for key in D.COST_ACTION_ORDER:
            if key in SKILLS:
                cost_action_rows.append((key, SKILLS[key]["cooldown"], True, 1))
            else:
                cost_action_rows.append((key, D.BUFF_COOLDOWNS[key], True, 1))

        def cast_rate_with(counts):
            """Skill + buff cast rate; ``counts`` maps row key -> engine cast count (the engine's schedule), other rows use the averaged formulas."""
            if fixed_duration_active:
                return sum(
                    (counts[k] if k in counts else (fight.exact_casts(eff_cooldown(cd, ca)) if k in D.BUFF_ROW_KEYS
                                                    else fight.non_buff_casts(eff_cooldown(cd, ca)))) * aps
                    for k, cd, ca, aps in cost_action_rows if ca and unlocked(k)
                ) / fight_duration
            return sum((1 / eff_cooldown(cd, ca)) * aps for k, cd, ca, aps in cost_action_rows if ca and unlocked(k))

        # The AVERAGED model's cast rate / Blast rate (pre-engine cast counts): Vessel of Light's uptime reads this one
        self.cast_rate_avg = cast_rate_avg = cast_rate_with({})
        self.blast_per_second_avg = blast_per_second_avg = max(0, actions_per_second - cast_rate_avg)

        # ---- Vessel of Light (proc off basic attacks): uptime approximated as MIN(1, Duration x ProcChance% x Basic Attack Rate); Greater Vessel of
        #      Light has no own duty cycle and reuses this same uptime fraction directly ----
        vol = D.VESSEL_OF_LIGHT
        vessel_of_light_pct = (coeff_pct(vol["base"], vol["fidx"], True, vol["step"]) + gated(vol["gated"])) if unlocked("VESSEL_OF_LIGHT") else 0.0
        # PROC RULE (2026-11-04): the 15% rolls once per basic ATTACK per ENEMY HIT -> 1-(1-c)^N activations per attack
        # (boss / PvP N=1; normal N = 6+Basic Attack Target Increase capped by Max Enemies Hit), blended by time per branch.
        vol_n = min(6 + basic_attack_target_increase, max_enemies_hit)
        vol_u_boss = min(1.0, vol["duration"] * vol["proc_chance"] * blast_per_second_avg)
        vol_u_normal = min(1.0, vol["duration"] * (1 - (1 - vol["proc_chance"]) ** vol_n) * blast_per_second_avg)
        self.vessel_of_light_uptime = vessel_of_light_uptime = (
            (vol_u_boss if monster_type == "pvp" else (1 - normal_weight) * vol_u_boss + normal_weight * vol_u_normal)
            if unlocked("VESSEL_OF_LIGHT") else 0.0
        )
        vessel_of_light_avg = vessel_of_light_pct * vessel_of_light_uptime if unlocked("VESSEL_OF_LIGHT") else 0.0
        # Parashock Guard's level delta (Sensitivity only: its value is baked into Inputs!attack_pct) joins the same additive Attack% bucket as Vessel of Light everywhere the
        # workbook block sums it (the bucket, ``_bucket_avg_block``, the strip's A0, the companion's snapshot)
        vessel_of_light_avg = vessel_of_light_avg + attack_mult_delta
        gv = D.GREATER_VESSEL
        greater_vessel_pct = (coeff_pct(gv["base"], gv["fidx"], True, gv["step"]) + gated(gv["gated"])) if unlocked("GREATER_VESSEL_OF_LIGHT") else 0.0
        greater_vessel_avg = greater_vessel_pct * vessel_of_light_uptime if unlocked("GREATER_VESSEL_OF_LIGHT") else 0.0

        hp = D.HP_RECOVERY
        hp_recovery_pct = (coeff_pct(hp["base"], hp["fidx"], True, hp["step"]) + gated(hp["gated"])) if unlocked("HP_RECOVERY_ATK") else 0.0
        hp_recovery_avg = hp_recovery_pct * fight.buff_uptime(hp["cooldown"], hp["duration"], True) if unlocked("HP_RECOVERY_ATK") else 0.0

        # ---- Divine Shield (fixed-interval buff, treated as its own Cooldown(s)), Guardian, Divine Blessing (all live duty-cycled Final Damage buffs) ----
        ds, gu, db = D.DIVINE_SHIELD, D.GUARDIAN, D.DIVINE_BLESSING
        divine_shield_pct = coeff_pct(ds["base"], ds["fidx"], True, ds["step"]) if unlocked("DIVINE_SHIELD") else 0.0
        divine_shield_avg = divine_shield_pct * fight.buff_uptime(ds["cooldown"], ds["duration"], False) if unlocked("DIVINE_SHIELD") else 0.0
        guardian_pct = coeff_pct(gu["base"], gu["fidx"], True, gu["step"]) if unlocked("GUARDIAN") else 0.0
        guardian_avg = guardian_pct * fight.buff_uptime(gu["cooldown"], gu["duration"], True) if unlocked("GUARDIAN") else 0.0
        divine_blessing_pct = (coeff_pct(db["base"], db["fidx"], True, db["step"]) + gated(db["gated"])) if unlocked("DIVINE_BLESSING") else 0.0
        divine_blessing_avg = (divine_blessing_pct * fight.buff_uptime(db["cooldown"], db["duration"], True)
                               if unlocked("DIVINE_BLESSING") else 0.0)

        self.crit_rate_bonus = 0.0       # no live Crit-Rate-buff source exists in this kit
        self.crit_damage_bonus = 0.0     # no live Crit-Damage-buff source exists in this kit

        # ---- Engine pass 1: the buff schedule (independent of the skill weights) ----
        # artifact Attack% (Old Music Box, Secret Map, Reindeer's Spear, Alliance Badge, Bottle of Emotion, Charm's average) joins the same additive bucket
        self.attack_bucket_mult = 1 + (vessel_of_light_avg + hp_recovery_avg + combat_orders_attack_avg + pre.agg_attack_pct) / 100
        self.final_damage_extra = divine_shield_avg + guardian_avg + divine_blessing_avg + greater_vessel_avg
        final_damage_rest = divine_shield_avg + greater_vessel_avg
        eng_host = None
        e1 = None
        if status_on:
            fd_scale = 100 / (100 + final_damage + final_damage_rest)
            buffs = [
                self.engine_buff("HPR", hp_recovery_pct),
                self.engine_buff("CO", D.COMBAT_ORDERS_ATTACK_PCT),
                self.engine_buff("GU", guardian_pct * fd_scale),
                self.engine_buff("DB", divine_blessing_pct * fd_scale),
            ]
            eng_host = dict(eng_base, A0=vessel_of_light_avg + pre.a0, buffs=buffs)
            e1 = sens["strip"][0] if "strip" in sens else stl.solve(eng_host)   # pass 1: the buff schedule; Sensitivity may reuse the main strip
            self.attack_bucket_mult = e1["Bbuff_mean"]
            self.final_damage_extra = final_damage_rest
            for bid, (key, _kind, _cd0, _dur0) in D.BUFF_SPEC.items():
                if key == "COMBAT_ORDERS" and not co_engine:
                    continue
                ENGINE_N[key] = e1["buffs"][bid]["n"]
            if co_engine and e_co is not None:
                assert ENGINE_N["COMBAT_ORDERS"] == e_co["buffs"]["CO"]["n"], "Combat Orders' schedule must not depend on the other buffs"

        self.e1 = e1
        # Final Damage of all four buffs at the CURRENT cast counts (Summary R_FD_ALL: the engine's counts for Guardian / Divine Blessing when it is on): the bucket the
        # Sensitivity sheet's "mult"-kind Final Damage sweep bumps by 1% (``SensSpec.mult_extra``)
        self.final_damage_all = (divine_shield_avg
                                 + (guardian_pct * fight.buff_uptime(gu["cooldown"], gu["duration"], True, casts=ENGINE_N.get("GUARDIAN")) if unlocked("GUARDIAN") else 0.0)
                                 + (divine_blessing_pct * fight.buff_uptime(db["cooldown"], db["duration"], True, casts=ENGINE_N.get("DIVINE_BLESSING"))
                                    if unlocked("DIVINE_BLESSING") else 0.0)
                                 + greater_vessel_avg)

        # HP Recovery's average at the engine's cast count (what the workbook's host cells read): exact-uptime formula at the engine's n
        if not unlocked("HP_RECOVERY_ATK"):
            hp_recovery_avg_eng = 0.0
        elif "HP_RECOVERY_ATK" in ENGINE_N:
            hp_recovery_avg_eng = hp_recovery_pct * self.uptime_at(ENGINE_N["HP_RECOVERY_ATK"], eff_cooldown(hp["cooldown"], True),
                                                                   eff_duration(hp["duration"]))
        else:
            hp_recovery_avg_eng = hp_recovery_pct * fight.buff_uptime(hp["cooldown"], hp["duration"], True)
        # Attack% bucket (in %) the companion's snapshot sees on average
        self.attack_bucket_sum = attack_bucket_sum = vessel_of_light_avg + hp_recovery_avg_eng + combat_orders_attack_avg
        attack_bucket_mult = self.attack_bucket_mult

        # ---- artifact effects (full): everything that needs the action rate / startup delay / the timeline's status multiplier ----
        actx.aps, actx.startup = actions_per_second, self.buff_cast_startup_time
        # Companion!horn_uptime (computed whether or not Horn Flute is equipped, like the workbook): the share of the player's boss DAMAGE dealt
        # while the companion is out (candidate-0 timing, which already carries the player's own Rush stun in Breakthrough / Hero Dungeon).  The
        # summon timing is damage-independent, so the stub-host run (with the player's stun entries) reports it.
        s0, w0, d_comp, period, ts_window = comp_mod.horn_window(actx, monster_type, fight_duration, pvp_len, summon_time_inc, stun_pin,
                                                                 choice, c_level)
        dw = art_mod.damage_weights(fight_duration, pre.hex_v, vessel_of_light_avg + pre.a0, pre.charm_val, e1["mult"] if status_on else None)
        actx.horn_uptime = art_mod.horn_flute_uptime(actx, dw, s0, w0, d_comp, period, ts_window)
        eff = self.art_effects = art_mod.Effects(eq, actx, pre)
        self.art_crit_rate = eff.agg_crit_rate                                     # (no live Crit-Rate-buff source in this kit: ``crit_rate_bonus`` stays 0)
        self.crit_damage_bonus = eff.agg_crit_damage                               # (no other live Crit-Damage-buff source in this kit)
        self.crit_damage_bonus += sens.get("crit_damage_delta", 0.0)               # (Sensitivity: a crit-damage passive's level delta; none in this kit)
        self.crit_damage_bonus += sens_mod.boa_crit_damage_delta(                  # (Book of Ancient equip what-if: pct x the crit-rate total, Sensitivity only)
            sens, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate)
        # the FULL live crit-rate total (Inputs + artifact bucket; CLAUDE.md item 13): what the cube / equipment tables test against the 100% cap
        self.crit_rate_total = self.crit_rate + self.crit_rate_bonus + self.art_crit_rate
        self.art_boss_damage, self.art_normal_damage = eff.agg_boss_damage + sens.get("boss_damage_extra", 0.0), eff.agg_normal_damage   # (+ Star Rock what-if)
        self.art_final_damage = eff.agg_final_damage
        self.art_joint_damage = eff.agg_damage                                     # Hexagon Damage%; enemy damage taken sits in monster_dmg_bonus (below)
        self.art_skill_damage, self.art_basic_attack_damage = eff.agg_skill_damage, eff.agg_basic_attack_damage
        self.extra_boss, self.extra_norm = eff.extras(actx, self.monster_defense, self.def_pen,
                                                      self.crit_rate + self.crit_rate_bonus + self.art_crit_rate, self.crit_damage + self.crit_damage_bonus)
        # Hexagon / Charm differ between the two phases of Breakthrough / Hero Dungeon: per-phase timing factor (engine-off rows)
        self.attack_bucket_avg = attack_bucket_sum + pre.agg_attack_pct
        self.ph_b, self.ph_n = art_mod.phase_state_ratios(content_type, fight_duration, pre.hex_v, pre.hex_avg, self.attack_bucket_avg,
                                                          pre.charm_val, pre.charm_avg)

        # ---- Close Combat / Noble Demand / Divine Mark weakens: the Global Monster Damage-Taken Bonus% ----
        cw, nw, mw = D.CLOSE_COMBAT_WEAKEN, D.NOBLE_DEMAND_WEAKEN, D.DIVINE_MARK_WEAKEN
        close_combat_weaken = self.weaken_avg(cw["pct"], cw["duration"], eff_cooldown(cw["cooldown"], True)) if level >= cw["level"] else 0.0
        noble_demand_weaken = self.weaken_avg(nw["pct"], nw["duration"], eff_cooldown(self.haste(nw["cooldown"], nw["haste"]), True))
        divine_mark_weaken = self.weaken_avg(mw["pct"], mw["duration"], eff_cooldown(mw["cooldown"], True)) if level >= mw["level"] else 0.0
        # Peach Tree Herb Pouch / Silver Pendant (enemy damage taken) sit in the same global bucket (Summary R_MONSTER_DMG_BONUS)
        self.monster_dmg_bonus = close_combat_weaken + noble_demand_weaken + divine_mark_weaken + eff.agg_enemy_dmg_taken

        # ---- Blast (basic attack) hit (needed by the engine weights) ----
        blast_hit = self.hit_damage(blast_pct, True, blast_mastery_boss_damage, 0)

        # ---- Status/KO engine pass 2: the damage skills' casts (weight of one cast = its boss damage before any timing factor) ----
        if status_on:
            def percast(key):
                if not unlocked(key):
                    return 0.0
                sk = SKILLS[key]
                hits = sk["hits"] * (fight_mod.ticks(fight.capped_window(sk["window"]), sk["icd"]) if sk.get("icd") else 1)
                return hits * self.skill_hit(key, sk) * self.branch_multipliers(sk.get("mastery_boss", 0), sk.get("mastery_normal", 0),
                                                                                sk["targets"])[0]
            c_slot = blast_hits * blast_hit * self.branch_multipliers(blast_mastery_boss_damage, 0, blast_targets)[0]
            groups = status_mod.build_groups(D, unlocked, SKILLS, percast, fight.capped_window,
                                             lambda cast: eff_cooldown(SKILLS[cast]["cooldown"], SKILLS[cast]["costs_action"]),
                                             stun_keys={e["key"] for e in D.PLAYER_STUN})
            E_ENGINE = status_mod.solve_groups(self, D, eng_host, groups, c_slot, ENGINE_N, sens)
            E_FS = E_ENGINE["fs"]
        self.e_engine = E_ENGINE

        # ---- Cast rate with the engine's cast counts ----
        self.cast_rate = cast_rate = cast_rate_with(ENGINE_N)
        self.blast_per_second = blast_per_second = max(0, actions_per_second - cast_rate)

        # ---- Blast (basic attack) DPS ----
        self.blast_dps = blast_dps = (
            self.blend_branches("BLAST", blast_hits * blast_hit * blast_per_second, blast_mastery_boss_damage, 0, blast_targets)
            if unlocked("BLAST") else 0.0)

        skill_dps = {}
        for key, s in SKILLS.items():
            if not unlocked(key):
                skill_dps[key] = 0.0
                continue
            hd = self.skill_hit(key, s)
            proc_prob = 1.0
            eff_cd = eff_cooldown(s["cooldown"], s["costs_action"], exempt=key in D.CDR_EXEMPT)
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
        self.player_dps = blast_dps + sum(skill_dps.values())

        # ---- player's boss-only / normal-only totals (the companion's damage-share weights; rows in the verify script's insertion order) ----
        row_dps = [("BLAST", blast_dps)] + list(skill_dps.items())
        self.pb_total, self.pn_total, self.pu_total = self.ledger.split_totals(row_dps, D.STATUS_UNIFORM_ROWS)

        # ---- companion: src/companion_python_model.py fed with this model's own pipeline numbers ----
        self.begin_companion(summon_time_inc)          # (effective Summoning Time Increase % = Inputs + Arwen's Glass Shoes)
        if (choice != "None" and c_level >= 1) or pl_on or sens.get("want_comp_host"):   # (Sensitivity: the comparison tables need the host with no companion / stun too)
            basic_b, basic_n = self.ledger.pairs.get("BLAST", (0.0, 0.0))[:2]
            hpr_full = hp_recovery_pct
            co_full = D.COMBAT_ORDERS_ATTACK_PCT if (unlocked("COMBAT_ORDERS") and level >= co["attack_min_level"]) else 0.0
            fdpart = 1 + (final_damage + divine_shield_avg + (guardian_pct if unlocked("GUARDIAN") else 0.0)
                          + (divine_blessing_pct if unlocked("DIVINE_BLESSING") else 0.0) + greater_vessel_avg) / 100
            boss_pct = self.boss_damage + self.art_boss_damage + self.monster_dmg_bonus
            norm_pct = self.normal_damage + self.art_normal_damage + self.monster_dmg_bonus
            comp_host = dict(comp_mod.host_common(self, pre, eff, basic_b, basic_n),
                unit=self.hit_damage(100.0, True, 0, 0) / 100, sd=self.skill_damage + self.art_skill_damage, aps=actions_per_second,
                avgbuff=attack_bucket_mult * (1 + (final_damage + self.final_damage_extra) / 100), attack_bucket_avg=self.attack_bucket_avg,
                agg_damage_avg=self.art_joint_damage,
                avgbuff_snap=lambda charm, extra: (1 + (vessel_of_light_avg + hpr_full + co_full + pre.agg_attack_pct - pre.charm_avg + charm + extra) / 100) * fdpart,
                boss_pct=boss_pct, norm_pct=norm_pct, cr_total=self.crit_rate + self.crit_rate_bonus + self.art_crit_rate,
                cd_total=self.crit_damage + self.crit_damage_bonus, def_pen=self.def_pen,
                taken_bucket=0.0 if monster_type == "pvp" else ((1 - normal_weight) * boss_pct + normal_weight * norm_pct), pst=pst)
            self.comp_host = comp_host
            self.run_companion(comp_host, choice, c_level, summon_time_inc, pl_on)
        self.total_dps = self.player_dps + self.companion_dps

    # ------------------------------------------------------------------------------------------------------------------
    def row_dps(self, key):
        return self.blast_dps if key == "BLAST" else self.skill_dps.get(key, 0.0)

    def derived_extra(self):
        return dict(
            cast_rate_avg=self.cast_rate_avg, basic_attacks_per_second=self.blast_per_second,
            basic_attacks_per_second_avg=self.blast_per_second_avg, avg_buff_mult=self.attack_bucket_mult, as_bonus=self.as_bonus,
            attack_bucket_mult=self.attack_bucket_mult, attack_bucket_sum=self.attack_bucket_sum,
            skill_coefficient_base=self.skill_coefficient_base, buff_cast_startup_time=self.buff_cast_startup_time,
            crit_damage_bonus=self.crit_damage_bonus, final_damage_extra=self.final_damage_extra,
            monster_dmg_bonus=self.monster_dmg_bonus, def_pen_effective=self.def_pen, maple_hero_pct=self.maple_hero_pct,
            combat_orders_uptime=self.co_u, combat_orders_skill_level_bonus=self.co_f, vessel_of_light_uptime=self.vessel_of_light_uptime,
        )


fields, schema, defaults = classapi.make(CLASS_ID, CLASS_NAME, STAT_IDENTITY, _MAIN_STAT_FIELDS, D)
artifact_schema = classapi.artifact_schema


def model(inputs):
    """The evaluated model object (everything ``compute`` reports plus the internals engine/sensitivity.py reads: ``comp_host``, ``e1`` /
    ``e_engine`` (the timeline strip), ``art_effects`` ...).  Same input dict as ``compute``; honours ``inputs["_sens"]`` (engine/common/sens.py)."""
    return _Model(inputs)


def compute(inputs):
    """DPS of one Paladin setup.  ``inputs``: dict (see module docstring / ``schema()``); returns a JSON-friendly dict:

    total_dps / player_dps / boss_dps / normal_dps / player_boss_dps / player_normal_dps, skills (per damage row: key, name, dps, share,
    boss_dps, normal_dps, unlocked), companion (None or dps/boss/normal/share + model details; choice "None" = Rush stun uplift only),
    engine_on (Status/KO timeline engine), engine (its cast counts and timing factors), derived (ATTACK, STAT_DAMAGE, actions/s, buff
    multipliers, Combat Orders uptime, computed Inputs rows ...).
    """
    return _Model(inputs).result()
