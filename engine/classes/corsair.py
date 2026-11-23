"""Corsair: the DPS model of ``src/verify_corsair_workbook.py`` as a function of a plain inputs dict.

    from engine.classes import corsair
    result = corsair.compute(corsair.defaults("World Boss"))

``compute(inputs)`` is bit-identical to the verify script (same operations in the same order); the verify script stays the independent
reference, ``tests/golden/test_corsair.py`` compares the two (with no artifact equipped).  Artifact equip effects (``inputs["artifacts"]``, up to 4
slots) are ported in ``engine/artifacts.py`` (shared with FP-Mage / Hero / ...; the Artifacts sheet of the builders is identical) and wired the way
``src/build_corsair_workbook.py`` wires them; the verify script does not model artifacts, so ``tests/golden/test_corsair_artifacts.py`` checks them
against the workbook itself (``tests/golden/corsair_artifacts_golden.json``, evaluated with ``formulas``).

Inputs dict: the workbook's Inputs keys already resolved for the chosen content type (see ``schema()``), plus ``companion_level`` (the
level of the chosen companion, 0 = not unlocked).  A missing / ``None`` value reads as 0, exactly like a blank workbook cell.

Corsair specifics (all in the verify script): DEX main / STR sub; Eight-Legs Easton is the basic attack (5 lines, 6 from Lv136; Quickdraw from
Lv125 doubles every 3rd cast => x(1 + 1/3) and shortens Brain Scrambler's / Rapid Fire's cooldowns by a closed-form fixed point of the basic-attack
rate); the player's own Blackboot Bill (Lv66, 2 s stun every 23 s) feeds the Status Effect Damage / KO timeline and - in Breakthrough / Hero
Dungeon - lengthens the boss phase, so a "companion" result exists from Lv66 even with no companion chosen (choice "None": only the stun uplift,
reported under ``companion`` with ``choice == "None"``); Jolly Roger (Final Damage) is the only engine-timed buff; Roll of the Dice's dice
component (Attack%), Nimble Feet (Attack Speed), Swift Fire's Weaken (global damage-taken bonus on both branches) and Ahoy Mateys' Final Damage
proc stay duty-cycle averages; Scurvy Summons / All Aboard are crew windows (``crew_window``), Broadside is a burst + a sustained turret / bombardment
window; Nautilus Strike - Final Attack and Majestic Presence are chance procs (one roll per attack per enemy hit, with their internal cooldowns).
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
from ..data import corsair as D
from .. import artifacts as art_mod
import status_timeline as stl  # noqa: E402  (src/status_timeline.py through the shim)

CLASS_ID = "corsair"
CLASS_NAME = "Corsair"
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
    def hit_damage(self, coeff_pct_val, is_basic, maple_ratio=0.0, ahoy_ratio=0.0):
        base_damage = self.attack * (coeff_pct_val / 100)
        dmg_reduction = dmg.defense_reduction(self.monster_defense, self.def_pen)
        helper_mult = 1.0
        if maple_ratio:
            helper_mult *= (1 + maple_ratio * self.maple_hero_pct / 100)
        if ahoy_ratio:
            helper_mult *= (1 + ahoy_ratio * self.ahoy_mateys_pct / 100)
        # Final Damage: the additive bracket (Inputs + Jolly Roger + Ahoy Mateys) x the multiplicative artifact bucket (Candle / Flaming Lava / Horn Flute)
        final_mult = (1 + (self.final_damage + self.final_damage_extra) / 100) * (1 + self.art_final_damage / 100) * helper_mult
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
        return self.hit_damage(pct, False, maple_ratio=s.get("maple_ratio", 0.0), ahoy_ratio=s.get("ahoy_ratio", 0.0))

    # ---- targets and branch blending ----
    def blend_branches(self, key, unit, targets, mastery_boss=0, mastery_normal=0):
        """Time-weighted DPS of one row: (1-w)*unit*boss_branch*timing_boss + w*unit*normal_branch*timing_normal."""
        b, n = self.branch_multipliers(mastery_boss, mastery_normal, targets)
        fb, fn = self.timing_factors(key)
        return self.ledger.blend_unit(key, unit, b, n, fb, fn)

    def proc_branch_dps(self, key, chance, icd, sources, payoff_hit, payoff_targets):
        """A 'When attacking ... X% chance' proc rolls once per attack per ENEMY HIT (user decision 2026-11-04).  sources = [(attack_rate_per_s,
        targets_of_that_attack)].  Boss/PvP branch: 1 enemy => X = c*sum(rate); normal branch: X = sum(rate*(1-(1-c)^N)).  Proc rate = X/(1+ICD*X)."""
        cap = self.fight.max_enemies_hit
        x_boss = chance * sum(r for r, _ in sources)
        x_norm = sum(r * dmg.q_roll(chance, min(t, cap)) for r, t in sources)
        boss_b, norm_b = self.branch_multipliers(0, 0, payoff_targets)
        rate_boss = x_boss / (1 + icd * x_boss)
        rate_norm = x_norm / (1 + icd * x_norm)
        fb, fn = self.timing_factors(key)
        pair = (rate_boss * payoff_hit * boss_b * fb, rate_norm * payoff_hit * norm_b * fn)
        return self.ledger.blend_pair(key, pair, boss_b, norm_b, fb, fn)

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
        flat_dex, dex_pct, str_stat = inp("flat_dex"), inp("dex_pct"), inp("str")
        self.stat_damage = (flat_dex * (1 + dex_pct / 100)) * 0.01 + str_stat * 0.0025
        self.damage = inp("damage")
        self.damage_amp = inp("damage_amp")
        self.boss_damage = boss_damage = inp("boss_damage")
        self.normal_damage = normal_damage = inp("normal_damage")
        self.status_effect_damage = status_effect_damage = inp("status_effect_damage")
        final_damage = inp("final_damage")
        if sens.get("final_damage_factor") is not None:
            # Sensitivity: Corsair's workbook block shifts Inputs!final_damage INSIDE the additive Final Damage bracket (Inputs + Jolly Roger + Ahoy Mateys) - a baked-in
            # Final Damage artifact what-if is a factor on the TYPED value ((1 + F/100) x factor - 1), not on the live artifact bucket (``baked_fd_form="typed"``
            # in engine/sens_specs/corsair.py); every reader of the Input (K, the companion's Final Damage part, the strip's Jolly Roger scale) sees the shifted value
            final_damage = ((1 + final_damage / 100) * sens["final_damage_factor"] - 1) * 100
        final_damage += sens.get("final_damage_delta", 0.0)      # (+ Cross Cut Blast's level delta, Sensitivity only; the block adds it next to the typed value)
        self.final_damage = final_damage
        self.min_damage = inp("min_damage") + sens.get("min_damage_delta", 0.0)      # (+ Gun Mastery's level delta, Sensitivity only)
        self.max_damage = inp("max_damage") + sens.get("max_damage_delta", 0.0)      # (Athena's Gloves' dependent Max Damage, Sensitivity only)
        # Book of Ancient's direct Crit Rate what-if and Shadow Heart's level delta: the workbook block's Ring of Cycles threshold carries both
        self.crit_rate = crit_rate = inp("crit_rate") + sens.get("crit_rate_threshold_extra", 0.0) + sens.get("crit_rate_delta", 0.0)
        self.crit_damage = crit_damage = inp("crit_damage")
        attack_speed_base = inp("attack_speed")
        # Sensitivity: Reindeer's Spear equip toggle folds one signed dose of its base Def Pen into the typed value
        self.def_pen = def_pen = sens_mod.def_pen_with_dose(inp("def_pen"), sens)
        self.basic_attack_damage = inp("basic_attack_damage") + sens.get("basic_attack_damage_delta", 0.0)     # (+ Physical Training's / Quickdraw's level deltas)
        self.skill_damage = inp("skill_damage")
        basic_attack_target_increase = inp("basic_attack_target_increase")
        summon_time_inc = inp("companion_summon_time_increase_pct")
        self.pvp_len = pvp_len = inp("pvp_fight_length") or content_mod.DEFAULT_PVP_FIGHT_LENGTH
        fight = self.fight = fight_mod.Fight(ct, pvp_len, inp("skill_cooldown_decrease"), inp("buff_duration_increase_pct") + sens.get("bdi_extra", 0.0),
                                             inp("max_enemies_hit"))     # (+ Shamaness Marble what-if, Sensitivity only)
        buff_duration_increase_pct = fight.bdi
        self.ledger = blend_mod.BranchLedger(normal_weight)

        # ---- artifacts (equip effects): slots, the early quantities (Attack% bucket / Hexagon / Charm) and Soul Contract's cooldown decrease ----
        self.eq = art_eq = sens["eq"] if "eq" in sens else art_mod.resolve_slots(inp.raw("artifacts"))   # (Sensitivity: an equip-toggle what-if may exceed 4 slots)
        actx = self.art_ctx = art_mod.Ctx(self.content_type, monster_type, fight_duration, pvp_len, fixed_duration_active,
                                          crit_rate=self.crit_rate, attack_speed=attack_speed_base)
        pre = self.art_pre = art_mod.Pre(art_eq, actx)
        # Arwen's Glass Shoes: the companion's effective Summoning Time Increase % = the Inputs value + the artifact (every use below)
        summon_time_inc += art_mod.summon_time_inc_pct(art_eq)
        # Soul Contract (Chapter Hunt): every real cooldown is multiplied by (1 - pct/100) AFTER the flat decrease and its 0.1 s floor - Fight.eff_cooldown is
        # the single place every cooldown below goes through (skills, buffs, the Quickdraw closed form, Swift Fire's Weaken, Ahoy Mateys, Blackboot Bill)
        fight.cd_extra_pct = art_mod.soul_contract_pct(art_eq, self.content_type)
        # live artifact terms of the damage pipeline; neutral until the full effects are known (after the buff-casting startup delay)
        self.art_final_damage = self.art_damage = self.art_skill_damage = self.art_basic_attack_damage = 0.0
        self.art_boss_damage = self.art_normal_damage = self.art_crit_rate = 0.0
        self.extra_boss = self.extra_norm = 1.0
        self.ph_b = self.ph_n = 1.0
        eff_cooldown = fight.eff_cooldown
        eff_duration = fight.eff_duration
        capped_window = fight.capped_window
        duty_cycle_uptime = fight.buff_uptime        # (cooldown, duration, costs_action=True): the verify script's duty_cycle_uptime
        self.crit_rate_bonus = 0.0
        self.crit_damage_bonus = 0.0

        basic_lvl = self.sl.input_level(4)
        self.skill_coefficient_base = D.EASTON_BASE * factors.get_factor(basic_lvl, 21) / 1000

        # ---- Maple Hero + Ahoy Mateys helpers (own coefficients; they multiply the rows named in the ratio tables) ----
        mh, am = D.MAPLE_HERO, D.AHOY_MATEYS
        self.maple_hero_pct = coeff_pct(mh["base"], mh["fidx"], True, mh["step"]) if unlocked("MAPLE_HERO_HELPER") else 0.0
        self.ahoy_mateys_pct = coeff_pct(am["base"], am["fidx"], True, am["step"]) if unlocked("AHOY_MATEYS_HELPER") else 0.0

        # ---- Actions Per Second: raw Attack Speed combined with Nimble Feet's duty-cycle averaged bonus (diminishing-returns stack) ----
        nf = D.NIMBLE_FEET
        if not unlocked("NIMBLE_FEET"):
            nimble_feet_as_bonus = 0.0
        else:
            nimble_feet_as_bonus = coeff_pct(nf["base"], nf["fidx"], False, nf["step"]) * duty_cycle_uptime(nf["cooldown"], nf["duration"], True)
        self.as_bonus = nimble_feet_as_bonus
        # (+ Quick Motion / Agile Guns level deltas and Athena's Gloves' direct Attack Speed what-if, Sensitivity only: the block's Actions Per Second, its Quickdraw
        #  divisor, Peach Tree / Silver Pendant and the companion snapshot all read ``Inputs!attack_speed + delta [+ Athena]``)
        self.actions_per_second = actions_per_second = dmg.actions_per_second(attack_speed_base + sens.get("attack_speed_extra", 0.0), nimble_feet_as_bonus)

        # ---- Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`) ----
        choice, c_level = comp_mod.read_choice(inp)
        self.companion_choice, self.companion_level = choice, c_level
        # The player's own stunning skills (game table): Blackboot Bill stuns for 2 s (cooldown 23 s), cast on cooldown from the start
        pl_on = any(unlocked(e["key"]) for e in D.PLAYER_STUN)
        stun_info = comp_mod.stun_probe(ct, fight, pvp_len, choice, c_level, summon_time_inc)
        hasstun = bool(stun_info and stun_info.get("hasstun")) or pl_on
        ko = content_mod.ko_windows(fight_duration)
        self.status_on = status_on = fixed_duration_active and normal_weight == 0 and (content_type in ko or hasstun)

        # Buff-Casting Startup Delay: in fixed-duration fights the character casts every unlocked, actively cast buff (Nimble Feet, Jolly Roger)
        # sequentially at fight start (1/APS s each) before its first damage-skill cast (0 when the engine is on: buffs are cast when they pay).
        if fixed_duration_active and not status_on:
            self.buff_cast_startup_time = (
                (1 if unlocked("NIMBLE_FEET") else 0) + (1 if unlocked("JOLLY_ROGER_FD") else 0)
            ) / actions_per_second
        else:
            self.buff_cast_startup_time = 0.0
        buff_cast_startup_time = self.buff_cast_startup_time
        fight.startup_time = buff_cast_startup_time
        t0_pl = 0.0 if status_on else buff_cast_startup_time
        self.pst = pst = [dict(id=e["id"], typ=e["typ"], cd=eff_cooldown(e["cd"], True), dur=e["dur"], p=e["p"],
                               on=unlocked(e["key"]), t0=t0_pl, tick=1.0, win=0.0) for e in D.PLAYER_STUN]
        stun_info, stun_pin = comp_mod.stun_windows(ct, fight, pvp_len, pst, choice, c_level, summon_time_inc, sens)
        self.stf_b = stf_b = stun_pin["stunfracB"]
        self.stf_n = stf_n = stun_pin["stunfracN"]

        # ---- Basic attack (Eight-Legs Easton) ----
        eight_legs_easton_targets = 6 + basic_attack_target_increase
        hits0, hits_lvl, hits1 = D.EASTON_HITS
        EIGHT_LEGS_EASTON_HITS = hits1 if level >= hits_lvl else hits0
        eight_legs_easton_mastery_damage = gated(D.EASTON_MASTERY)
        self.easton_boss_mastery = eight_legs_easton_mastery_boss_damage = gated(D.EASTON_BOSS_MASTERY)
        eight_legs_easton_pct = self.skill_coefficient_base * (1 + eight_legs_easton_mastery_damage / 100)

        # ---- Quickdraw (Lv125) closed-form fixed point: B* = (APS - c0 - x0)/(1 + K*x0); f = 1 + K*B* ----
        cost_rows = D.COST_ACTION_ROWS
        qd_keys = D.QD_COOLDOWN_KEYS
        QD_K = D.QD_K
        if unlocked("QUICKDRAW_BAD") and monster_type != "pvp":
            c0 = sum((1 / eff_cooldown(cd, ca)) * aps for k, cd, ca, aps in cost_rows if ca and unlocked(k) and k not in qd_keys)
            c0 += (1 / eff_cooldown(60, True)) if unlocked("NIMBLE_FEET") else 0
            c0 += (1 / eff_cooldown(42, True)) if unlocked("JOLLY_ROGER_FD") else 0
            x0 = sum(1 / eff_cooldown(cd, ca) for k, cd, ca, aps in cost_rows if k in qd_keys and unlocked(k))
            qd_factor = 1 + QD_K * max(0.0, (actions_per_second - c0 - x0) / (1 + QD_K * x0))
        else:
            qd_factor = 1.0
        self.qd_factor = qd_factor

        def eff_cd_of(key, cd, ca):
            return eff_cooldown(cd, ca) / (qd_factor if key in qd_keys else 1.0)

        def non_buff_casts(cooldown):
            return fight.non_buff_casts(cooldown)

        # ---- Swift Fire - Weaken (Lv54): 3 strikes x 3% (max 3 stacks = 9%) for 8 s per cast ----
        sw = D.SWIFT_WEAKEN
        swift_weaken_bonus = (
            sw["pct"] * min(1.0, sw["duration"] * (1 + buff_duration_increase_pct / 100) / eff_cooldown(sw["cooldown"], True))
            if (level >= sw["level"] and unlocked("SWIFT_FIRE")) else 0.0
        )
        self.monster_dmg_bonus = swift_weaken_bonus      # + the artifacts' enemy-damage-taken terms (Peach Tree / Silver Pendant) once known

        # ---- Global Final Damage bucket: Jolly Roger (42 s / 18 s duty cycle) + Ahoy Mateys - Final Damage proc (Mastery Lv122) ----
        jr = D.JOLLY_ROGER
        self.jolly_roger_full = jolly_roger_full = coeff_pct(jr["base"], jr["fidx"], True, jr["step"]) if unlocked("JOLLY_ROGER_FD") else 0.0
        af = D.AHOY_FD_PROC
        if level >= af["level"]:
            # uptime_fraction_steady: steady-state duty cycle (NOT the fixed-duration-exact one)
            scaled_duration = af["duration"] * (1 + buff_duration_increase_pct / 100)
            if monster_type == "pvp":
                ahoy_uptime = min(scaled_duration, pvp_len) / pvp_len
            else:
                ahoy_uptime = min(1.0, scaled_duration / eff_cooldown(af["cooldown"], True))
            self.ahoy_mateys_proc_fd = ahoy_mateys_proc_fd = af["pct"] * ahoy_uptime
        else:
            self.ahoy_mateys_proc_fd = ahoy_mateys_proc_fd = 0.0
        self.final_damage_rest = final_damage_rest = ahoy_mateys_proc_fd             # the Final Damage the engine does not time
        jolly_roger_pct = jolly_roger_full * duty_cycle_uptime(jr["cooldown"], jr["duration"], True) if unlocked("JOLLY_ROGER_FD") else 0.0
        self.jolly_roger_pct = jolly_roger_pct
        self.final_damage_extra = final_damage_extra = jolly_roger_pct + ahoy_mateys_proc_fd      # averaged model (engine off)

        # ---- Attack% bucket: Roll of the Dice's dice component only ----
        rd = D.ROLL_OF_THE_DICE
        self.roll_of_dice_pct = roll_of_dice_pct = (
            coeff_pct(rd["base"], rd["fidx"], True, rd["step"]) * rd["num"] / rd["den"] if unlocked("ROLL_OF_THE_DICE_DICE") else 0.0)
        # Infinity Blast's level delta (Sensitivity only: its value is baked into Inputs!attack_pct) joins the same additive Attack% bucket as the dice component
        # everywhere the workbook block sums it (``bucket_avg_block``, the strip's A0, the companion's snapshot)
        roll_of_dice_pct = roll_of_dice_pct + sens.get("attack_mult_delta", 0.0)
        # artifact Attack% (Old Music Box, Secret Map, Reindeer's Spear, Alliance Badge, Bottle of Emotion, Charm's average) joins the same additive bucket
        self.attack_bucket_mult = attack_bucket_mult = 1 + (roll_of_dice_pct + pre.agg_attack_pct) / 100

        # ---- Engine pass 1: the buff schedule (independent of the skill weights) ----
        self.engine_n = ENGINE_N = {}
        E_ENGINE = None
        E_FS = {}
        self.phi_rows = {}
        self.phi_unif = 1.0
        e1 = None
        if status_on:
            # (the verify script raises KeyError here when no companion is chosen and Blackboot Bill's stun is locked, i.e. level < 66 in a KO content:
            # the companion model's early return carries no stun_vector.  The engine reads that as "no companion stun".)
            comp_stun = stun_info["stun_vector"](stl.NB_MAX) if "stun_vector" in stun_info else [0.0] * stl.NB_MAX
            stun_vec = [min(1.0, a + b) for a, b in zip(comp_stun, stl.pl_stun_vector([dict(e, t0=0.0) for e in pst], fight_duration, stl.NB_MAX))]
            eng_base = dict(T=fight_duration, S=status_effect_damage, ko=ko.get(content_type, []), hex_v=0.0, hex_period=20, hex_max=3,
                            hex_avg=0.0, charm_v=0.0, c_slot=0.0, stun=stun_vec, groups=[])
            cd_jr, dur_jr = eff_cooldown(jr["cooldown"], True), eff_duration(jr["duration"])
            fd_scale = 100 / (100 + final_damage + final_damage_rest)
            buffs = [dict(id="JR", kind="ramp", F=jolly_roger_full * fd_scale, dur=min(dur_jr, cd_jr), cd=cd_jr, on=unlocked("JOLLY_ROGER_FD"),
                          p0=1, p1=1, ramp_t=1, dur0=1)]
            eng_base.update(hex_v=pre.hex_v, hex_avg=pre.hex_avg, charm_v=pre.charm_val)
            eng_host = dict(eng_base, A0=roll_of_dice_pct + pre.a0, buffs=buffs)
            e1 = sens["strip"][0] if "strip" in sens else stl.solve(eng_host)   # pass 1: the buff schedule; Sensitivity may reuse the main strip
            self.attack_bucket_mult = attack_bucket_mult = e1["Bbuff_mean"]
            self.final_damage_extra = final_damage_extra = final_damage_rest
            ENGINE_N["JOLLY_ROGER_FD"] = e1["buffs"]["JR"]["n"]
        self.e1 = e1
        # Final Damage of both sources at the CURRENT cast counts (Summary R_FD_ALL: the engine's Jolly Roger count when it is on) + the Ahoy Mateys proc: the bucket
        # the Sensitivity sheet's "mult"-kind Final Damage sweep bumps by 1% (``SensSpec.mult_extra``)
        self.final_damage_all = ((jolly_roger_full * fight.buff_uptime(jr["cooldown"], jr["duration"], True, casts=ENGINE_N.get("JOLLY_ROGER_FD"))
                                  if unlocked("JOLLY_ROGER_FD") else 0.0) + ahoy_mateys_proc_fd)

        # ---- artifact effects (full): everything that needs the action rate / startup delay / the timeline's status multiplier ----
        actx.aps, actx.startup = actions_per_second, buff_cast_startup_time
        # Companion!horn_uptime (computed whether or not Horn Flute is equipped, like the workbook): the share of the player's boss DAMAGE dealt while the
        # companion is out (candidate-0 timing, which already carries Blackboot Bill's stun in Breakthrough / Hero Dungeon).  The summon timing is
        # damage-independent, so the stub-host run (with the player's stun entries) reports it.
        s0, w0, d_comp, period, ts_window = comp_mod.horn_window(actx, monster_type, fight_duration, pvp_len, summon_time_inc, stun_pin,
                                                                 choice, c_level)
        dw = art_mod.damage_weights(fight_duration, pre.hex_v, roll_of_dice_pct + pre.a0, pre.charm_val, e1["mult"] if status_on else None)
        actx.horn_uptime = art_mod.horn_flute_uptime(actx, dw, s0, w0, d_comp, period, ts_window)
        eff = self.art_effects = art_mod.Effects(art_eq, actx, pre)
        self.art_crit_rate = eff.agg_crit_rate                                     # (no live Crit-Rate-buff source in this kit: ``crit_rate_bonus`` stays 0)
        self.crit_damage_bonus = eff.agg_crit_damage
        self.crit_damage_bonus += sens.get("crit_damage_delta", 0.0)               # (Sensitivity: Book of Ancient's dependent Crit Damage / Fullmetal Jacket's level delta)
        self.crit_damage_bonus += sens_mod.boa_crit_damage_delta(                  # (Book of Ancient equip what-if: pct x the crit-rate total, Sensitivity only)
            sens, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate)
        # the FULL live crit-rate total (Inputs + artifact bucket; CLAUDE.md item 13): what the cube / equipment tables test against the 100% cap
        self.crit_rate_total = self.crit_rate + self.crit_rate_bonus + self.art_crit_rate
        self.art_boss_damage, self.art_normal_damage = eff.agg_boss_damage + sens.get("boss_damage_extra", 0.0), eff.agg_normal_damage   # (+ Star Rock what-if)
        self.art_final_damage = eff.agg_final_damage
        self.art_damage = eff.agg_damage                                           # Hexagon Damage%
        self.monster_dmg_bonus = swift_weaken_bonus + eff.agg_enemy_dmg_taken      # Summary R_MONSTER_DMG_BONUS: Swift Fire's Weaken + Peach Tree / Silver Pendant
        self.art_skill_damage, self.art_basic_attack_damage = eff.agg_skill_damage, eff.agg_basic_attack_damage
        self.extra_boss, self.extra_norm = eff.extras(actx, self.monster_defense, self.def_pen,
                                                      self.crit_rate + self.crit_rate_bonus + self.art_crit_rate, self.crit_damage + self.crit_damage_bonus)
        # Hexagon / Charm differ between the two phases of Breakthrough / Hero Dungeon: per-phase timing factor (engine-off rows)
        self.attack_bucket_avg = roll_of_dice_pct + pre.agg_attack_pct
        self.ph_b, self.ph_n = art_mod.phase_state_ratios(content_type, fight_duration, pre.hex_v, pre.hex_avg, self.attack_bucket_avg,
                                                          pre.charm_val, pre.charm_avg)

        # ---- Eight-Legs Easton (basic attack) hit (needed by the engine weights); Quickdraw doubles every 3rd cast => x(1 + 1/3) ----
        eight_legs_easton_hit = self.hit_damage(eight_legs_easton_pct, True)
        qd_damage_mult = D.EASTON_QUICKDRAW_MULT if unlocked("QUICKDRAW_BAD") else 1.0
        self.qd_damage_mult = qd_damage_mult

        # ---- Other damage skills (level-resolved) ----
        cr_ = D.CREW
        crew_window = min(cr_["cap"], cr_["base_window"] * (1 + buff_duration_increase_pct / 100)) if level >= cr_["persistence_level"] else cr_["base_window"]
        self.crew_window = crew_window
        scurvy_icd = cr_["scurvy_icd"] * cr_["strike_mult"] if level >= cr_["strike_level"] else cr_["scurvy_icd"]
        all_aboard_icd = cr_["all_aboard_icd"] * cr_["strike_mult"] if level >= cr_["strike_level"] else cr_["all_aboard_icd"]
        sw0, sw_lvl, sw1 = D.SIEGE_WINDOW
        siege_window = sw1 if level >= sw_lvl else sw0
        named_icd = {"crew_scurvy": scurvy_icd, "crew_all_aboard": all_aboard_icd}
        named_window = {"crew": crew_window, "siege": siege_window}

        def at_level(v):
            """``(threshold, below, at_or_above)`` tuple -> the level-resolved value; plain values pass through."""
            if isinstance(v, tuple):
                return v[2] if level >= v[0] else v[1]
            return v

        SKILLS = self.skills = {}
        for key, t in D.DAMAGE_SKILLS.items():
            s = dict(step=t["step"], cooldown=t["cooldown"], hits=at_level(t["hits"]), base=at_level(t["base"]), fidx=t["fidx"],
                     mastery=gated(t["mastery"]), mastery_boss=0, mastery_normal=0, costs_action=t["costs_action"],
                     targets=at_level(t["targets"]))
            if "icd" in t:
                icd = t["icd"]
                s["icd"] = named_icd[icd] if isinstance(icd, str) else icd
                window = t["window"]
                s["window"] = named_window[window] if isinstance(window, str) else at_level(window)
            if key in D.MAPLE_HERO_RATIOS:
                s["maple_ratio"] = D.MAPLE_HERO_RATIOS[key]
            if key in D.AHOY_MATEYS_RATIOS:
                s["ahoy_ratio"] = D.AHOY_MATEYS_RATIOS[key]
            SKILLS[key] = s
        self.normal_targets = {k: v["targets"] for k, v in SKILLS.items()}

        # ---- Status/KO engine pass 2: the damage skills' casts (weight of one cast = its boss damage before any timing factor) ----
        PHI_ROWS = {}
        if status_on:
            def percast(key):
                if not unlocked(key):
                    return 0.0
                sk = SKILLS[key]
                hits = sk["hits"] * (fight_mod.ticks(capped_window(sk["window"]), sk["icd"]) if sk.get("icd") else 1)
                return hits * self.skill_hit(sk) * self.branch_multipliers(sk.get("mastery_boss", 0), sk.get("mastery_normal", 0), sk["targets"])[0]
            c_slot = (EIGHT_LEGS_EASTON_HITS * eight_legs_easton_hit * qd_damage_mult
                      * self.branch_multipliers(eight_legs_easton_mastery_boss_damage, 0, eight_legs_easton_targets)[0])
            groups = status_mod.build_groups(D, unlocked, SKILLS, percast, capped_window,
                                             lambda cast: eff_cd_of(cast, SKILLS[cast]["cooldown"], True),
                                             stun_keys={e["key"] for e in D.PLAYER_STUN})
            E_ENGINE = status_mod.solve_groups(self, D, eng_host, groups, c_slot, ENGINE_N, sens)
            PHI_ROWS = self.phi_rows
            E_FS = E_ENGINE["fs"]
        self.e_engine = E_ENGINE

        # ---- Cast rate with the engine's cast counts (Skill + buff cast rate subtracted from Eight-Legs Easton) ----
        def cast_rate_with(counts):
            """`counts` maps row key -> engine cast count (the engine's schedule), other rows use the averaged formulas."""
            if fixed_duration_active:
                tot = 0.0
                for k, cd, ca, aps in cost_rows:
                    if ca and unlocked(k):
                        tot += (counts[k] if k in counts else non_buff_casts(eff_cd_of(k, cd, ca))) * aps
                if unlocked("NIMBLE_FEET"):
                    tot += counts["NIMBLE_FEET"] if "NIMBLE_FEET" in counts else fight.exact_casts(eff_cooldown(60, True))
                if unlocked("JOLLY_ROGER_FD"):
                    tot += counts["JOLLY_ROGER_FD"] if "JOLLY_ROGER_FD" in counts else fight.exact_casts(eff_cooldown(42, True))
                return tot / fight_duration
            r = sum((1 / eff_cd_of(k, cd, ca)) * aps for k, cd, ca, aps in cost_rows if ca and unlocked(k))
            r += (1 / eff_cooldown(60, True)) if unlocked("NIMBLE_FEET") else 0
            r += (1 / eff_cooldown(42, True)) if unlocked("JOLLY_ROGER_FD") else 0
            return r

        cost_keys = {c[0] for c in cost_rows} | {"JOLLY_ROGER_FD"}
        self.cast_rate_avg = cast_rate_with({})
        self.cast_rate = cast_rate = cast_rate_with({k: v for k, v in ENGINE_N.items() if k in cost_keys})
        self.eight_legs_easton_per_second = eight_legs_easton_per_second = max(0, actions_per_second - cast_rate)

        # ---- Eight-Legs Easton (basic attack) DPS (first row put in the ledger: the verify script's _BRANCH_PAIRS insertion order) ----
        self.eight_legs_easton_dps = eight_legs_easton_dps = (
            self.blend_branches("EIGHT_LEGS_EASTON", EIGHT_LEGS_EASTON_HITS * eight_legs_easton_hit * eight_legs_easton_per_second * qd_damage_mult,
                                eight_legs_easton_targets, eight_legs_easton_mastery_boss_damage, 0)
            if unlocked("EIGHT_LEGS_EASTON") else 0.0
        )

        def cast_count(key):
            """Casts of an action-costing damage skill in the fight (engine schedule or the averaged exact count)."""
            if status_on and key in ENGINE_N:
                return ENGINE_N[key]
            return non_buff_casts(eff_cd_of(key, SKILLS[key]["cooldown"], SKILLS[key]["costs_action"]))

        def skill_rate(key, s):
            if status_on and key in ENGINE_N:
                # engine casts: a DoT row's hits = hits per full window x effective casts (last window truncated at the fight end)
                per_cast = s["hits"] * (fight_mod.ticks(capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
                return per_cast * (E_FS[key] if key in D.STATUS_FS_KEYS else ENGINE_N[key]) / fight_duration
            eff_cd = eff_cd_of(key, s["cooldown"], s["costs_action"])
            if fixed_duration_active:
                return fight.non_buff_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
            hits = s["hits"] * (fight_mod.ticks(capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
            return hits / eff_cd

        skill_dps = {}
        for key, s in SKILLS.items():
            if not unlocked(key):
                skill_dps[key] = 0.0
                continue
            skill_dps[key] = self.blend_branches(key, skill_rate(key, s) * self.skill_hit(s), s["targets"], s.get("mastery_boss", 0),
                                                 s.get("mastery_normal", 0))

        # ---- Nautilus Strike - Final Attack: any attack, 30% chance, 1 s ICD => (c*R)/(1+ICD*c*R) with R = the combined cast rate of Easton + the
        #      direct-attack action-costing skills ----
        naf = D.NAUTILUS_FA
        if unlocked("NAUTILUS_FINAL_ATTACK"):
            sources = [(eight_legs_easton_per_second, eight_legs_easton_targets)]
            for k in D.NAUTILUS_FA_TRIGGERS:
                if unlocked(k):
                    cd = eff_cd_of(k, SKILLS[k]["cooldown"], SKILLS[k]["costs_action"])
                    sources.append((((cast_count(k) / fight_duration) if fixed_duration_active else (1 / cd)), SKILLS[k]["targets"]))
            skill_dps["NAUTILUS_FINAL_ATTACK"] = self.proc_branch_dps(
                "NAUTILUS_FINAL_ATTACK", naf["chance"], naf["icd"], sources,
                self.hit_damage(coeff_pct(naf["base"], naf["fidx"], True, naf["step"]), False), naf["targets"])
        else:
            skill_dps["NAUTILUS_FINAL_ATTACK"] = 0.0

        # ---- Majestic Presence (procs off Basic Attack + Brain Scrambler + Rapid Fire; 25% per attack per enemy hit with a 0.5 s ICD) ----
        mp = D.MAJESTIC_PRESENCE
        if unlocked("MAJESTIC_PRESENCE"):
            mp_pct = coeff_pct(mp["base"], mp["fidx"], True, mp["step"]) * (1 + gated(mp["mastery"]) / 100)
            mp_hit = self.hit_damage(mp_pct, False)

            def source_rate(key):
                if not unlocked(key):
                    return 0.0
                return skill_rate(key, SKILLS[key])

            mp_sources = [(eight_legs_easton_per_second, eight_legs_easton_targets)]
            for k in D.MAJESTIC_SOURCES:
                mp_sources.append((source_rate(k), SKILLS[k]["targets"]))
            majestic_presence_dps = self.proc_branch_dps("MAJESTIC_PRESENCE", mp["chance"], mp["icd"], mp_sources, mp_hit, mp["targets"])
        else:
            majestic_presence_dps = 0.0
        skill_dps["MAJESTIC_PRESENCE"] = majestic_presence_dps
        self.skill_dps = skill_dps
        self.player_dps = player_dps = eight_legs_easton_dps + sum(skill_dps.values())

        # ---- player's boss-only / normal-only totals, summed in the ledger's insertion order exactly like the verify script ----
        pairs = self.ledger.pairs
        self.pb_total = sum(v[0] for v in pairs.values())
        self.pn_total = sum(v[1] for v in pairs.values())
        self.pu_total = sum(pairs[k][0] for k in D.STATUS_UNIFORM_ROWS if k in pairs)

        # ---- companion: src/companion_python_model.py fed with this model's own pipeline numbers ----
        self.begin_companion(summon_time_inc)          # (effective Summoning Time Increase % = Inputs + Arwen's Glass Shoes)
        if (choice != "None" and c_level >= 1) or pl_on or sens.get("want_comp_host"):   # (Sensitivity: the comparison tables need the host with no companion / stun too)
            basic_b, basic_n = pairs["EIGHT_LEGS_EASTON"][:2] if "EIGHT_LEGS_EASTON" in pairs else (0.0, 0.0)
            fdpart = 1 + (final_damage + ahoy_mateys_proc_fd + jolly_roger_full) / 100
            boss_pct_c = boss_damage + self.art_boss_damage + self.monster_dmg_bonus
            norm_pct_c = normal_damage + self.art_normal_damage + self.monster_dmg_bonus
            comp_host = dict(comp_mod.host_common(self, pre, eff, basic_b, basic_n),
                unit=self.hit_damage(100.0, True) / 100, sd=self.skill_damage + self.art_skill_damage, aps=actions_per_second,
                avgbuff=attack_bucket_mult * (1 + (final_damage + final_damage_extra) / 100), attack_bucket_avg=self.attack_bucket_avg,
                agg_damage_avg=self.art_damage,
                avgbuff_snap=lambda charm, extra: (1 + (roll_of_dice_pct + pre.agg_attack_pct - pre.charm_avg + charm + extra) / 100) * fdpart,
                boss_pct=boss_pct_c, norm_pct=norm_pct_c, cr_total=self.crit_rate + self.crit_rate_bonus + self.art_crit_rate,
                cd_total=crit_damage + self.crit_damage_bonus, def_pen=def_pen,
                taken_bucket=0.0 if monster_type == "pvp" else ((1 - normal_weight) * boss_pct_c + normal_weight * norm_pct_c), pst=pst)
            self.comp_host = comp_host
            self.run_companion(comp_host, choice, c_level, summon_time_inc, pl_on)
        self.total_dps = player_dps + self.companion_dps

    # ------------------------------------------------------------------------------------------------------------------
    def row_dps(self, key):
        return self.eight_legs_easton_dps if key == "EIGHT_LEGS_EASTON" else self.skill_dps.get(key, 0.0)

    def derived_extra(self):
        return dict(
            basic_attacks_per_second=self.eight_legs_easton_per_second, avg_buff_mult=self.attack_bucket_mult, as_bonus=self.as_bonus,
            attack_bucket_mult=self.attack_bucket_mult, skill_coefficient_base=self.skill_coefficient_base,
            buff_cast_startup_time=self.buff_cast_startup_time, final_damage_extra=self.final_damage_extra,
            final_damage_rest=self.final_damage_rest, crit_damage_bonus=self.crit_damage_bonus, crit_rate_bonus=self.crit_rate_bonus + self.art_crit_rate,
            monster_dmg_bonus=self.monster_dmg_bonus, maple_hero_pct=self.maple_hero_pct, ahoy_mateys_pct=self.ahoy_mateys_pct,
            ahoy_mateys_proc_fd=self.ahoy_mateys_proc_fd, jolly_roger_pct=self.jolly_roger_pct, jolly_roger_full=self.jolly_roger_full,
            roll_of_dice_pct=self.roll_of_dice_pct, quickdraw_factor=self.qd_factor, quickdraw_damage_mult=self.qd_damage_mult,
            crew_window=self.crew_window,
        )


fields, schema, defaults = classapi.make(CLASS_ID, CLASS_NAME, STAT_IDENTITY, _MAIN_STAT_FIELDS, D)
artifact_schema = classapi.artifact_schema


def model(inputs):
    """The evaluated model object (everything ``compute`` reports plus the internals engine/sensitivity.py reads: ``comp_host``, ``e1`` /
    ``e_engine`` (the timeline strip), ``art_effects`` ...).  Same input dict as ``compute``; honours ``inputs["_sens"]`` (engine/common/sens.py)."""
    return _Model(inputs)


def compute(inputs):
    """DPS of one Corsair setup.  ``inputs``: dict (see module docstring / ``schema()``); returns a JSON-friendly dict:

    total_dps / player_dps / boss_dps / normal_dps / player_boss_dps / player_normal_dps, skills (per damage row: key, name, dps, share,
    boss_dps, normal_dps, unlocked), companion (None or dps/boss/normal/share + model details; choice "None" = Blackboot Bill stun uplift only),
    engine_on (Status/KO timeline engine), engine (its cast counts and timing factors), derived (ATTACK, STAT_DAMAGE, actions/s, buff
    multipliers, Quickdraw factor, computed Inputs rows ...).
    """
    return _Model(inputs).result()
