"""Wind Archer (Cygnus Knight, DEX main / STR sub bowman): an ENGINE-NATIVE, PROVISIONAL, UNPUBLISHED class - there is no workbook, builder or verify script for it.

    from engine.classes import wind_archer
    result = wind_archer.compute(wind_archer.defaults("World Boss"))

``PUBLISHED = False``: the API hides the class (and the live site never serves it) until the user has supplied the skill SCALING data (one higher-level reading per skill) and the provisional
curves of ``engine/data/wind_archer.py`` (``CURVES`` / ``PROVISIONAL``: every factor index is a convention, the bases are the user's level-1 values) are resolved.  The independent check is the
user's level-1 text: ``tests/golden/test_wind_archer_displayed.py``.

Built on Blaze Wizard's model (same input dict, artifacts / companion / Status Effect Damage + KO timeline plumbing, Sensitivity hooks).  Wind Archer specifics:

* **Basic attack = Fairy Spiral** (level 100+, absent below like every class).
* **Spirit Arrows**: Trifling Wind (I Lv40 -> II Lv66 -> III Lv105) creates 3-7 arrows whenever a skill is activated (2 s cooldown), Song of Heaven creates 2-5 per volley (13 volleys); against ONE target
  the arrows of a burst follow the consecutive-strike ladder (-20 % each, floor 20 %), in a pack they are assumed to spread.  **Storm Bringer**: a skill activation starts a 15 s storm with 50 %
  (25 s cooldown); during it attacks roll 30 % (+30 pp at Lv138) per enemy hit for a 1100 % giant arrow on 12 targets (0.5 s cooldown).
* **Timed effects** (cast on cooldown from t = 0, averaged by uptime): Storm Elemental (Attack, Damage), Sharp Eyes (own Critical Damage), Elemental Harmony and Second Wind (Attack Speed; Second Wind
  needs 8 skill activations, 4 from Lv82, then lasts 8 s + 4 s dead time), Emerald Flower (boss damage taken +15 %) with Emerald Dust (damage taken +8 %, own Final Damage as a standalone 20 s buff, Buff Duration
  applies: patch 2026-11-26) and Pinpoint Pierce's Lv94 weaken (+10 % damage taken for 12 s, boss / PvP only).
* **Stuns**: Spiraling Vortex 1.5 s (Lv49) feeds the player-stun timeline.
* **Always-on passives and stat masteries are NOT added** (the Inputs come from the in-game stat screen): see ``D.STAT_SCREEN_EFFECTS``.
Every judgement call is flagged in ``D.ROW_NOTES`` / ``D.FLAGS`` and in KNOWN_GAPS.md ("Wind Archer").
"""
from .. import _src  # noqa: F401
from ..common import blend as blend_mod
from ..common import classapi
from ..common import companion as comp_mod
from ..common import content as content_mod
from ..common import damage as dmg
from ..common import fight as fight_mod
from ..common import model as model_mod
from ..common import schema as schema_mod
from ..common import sens as sens_mod
from ..common import status as status_mod
from ..data import wind_archer as D
from .. import artifacts as art_mod
import status_timeline as stl  # noqa: E402  (src/status_timeline.py through the shim)

CLASS_ID = "wind_archer"
CLASS_NAME = "Wind Archer"
STAT_IDENTITY = {"main": "DEX", "sub": "STR"}
PUBLISHED = False          # publish gate: flip only after the user confirmed the skill scaling in game (CLAUDE.md "Adding an engine-native class" step 6)

_MAIN_STAT_FIELDS = [
    schema_mod.field("flat_dex", "Flat DEX", "Main stats", "float", "flat", 0),
    schema_mod.field("dex_pct", "DEX %", "Main stats", "float", "%", 0),
    schema_mod.field("str", "STR", "Main stats", "float", "flat", 0),
]


def combine_def_pen(a, b):
    """Two Defense Penetration sources combine by diminishing returns."""
    return 100 * (1 - (1 - a / 100) * (1 - b / 100))


def ladder_mean(n, ladder=D.TRIFLING_WIND["ladder"]):
    """Average damage multiplier of ``n`` Spirit Arrows that strike ONE target one after the other within 0.5 s: 1, .8, .6, .4, .2, .2, ... (each strike -20 %, at most -80 %)."""
    if n <= 0:
        return 1.0
    return sum(ladder[min(i, len(ladder) - 1)] for i in range(int(n))) / int(n)


class _Model(model_mod.ModelBase):
    DATA = D

    # ------------------------------------------------------------------------------------------------------------------
    # ---- per-hit pipeline ----
    def hit_damage(self, coeff_pct_val, is_basic, skill_fd_pct=0.0, branch="boss"):
        """Expected damage of one hit in a branch ("boss" = boss / PvP, "normal", "comp" = the companion host's Defense Penetration).  ``skill_fd_pct``: the row's own Final Damage
        multiplier (Call of Cygnus / Trifling Wind III: 1 + pct/100, the Maple Hero convention)."""
        base_damage = self.attack * (coeff_pct_val / 100)
        dp = self.def_pen_n if branch == "normal" else (self.def_pen_c if branch == "comp" else self.def_pen_b)
        dmg_reduction = dmg.defense_reduction(self.monster_defense, dp)
        fd_bucket = self.final_damage + self.final_damage_extra
        final_mult = (1 + fd_bucket / 100) * (1 + self.art_final_damage / 100) * (1 + skill_fd_pct / 100)
        source_pct = (self.basic_attack_damage + self.art_basic_attack_damage) if is_basic else (self.skill_damage + self.art_skill_damage)
        # Boss/Normal Monster Damage% is deliberately NOT applied here - it is blended per branch (its own multiplier x its own target count)
        base_hit = (
            base_damage * (1 + self.stat_damage / 100) * (1 + self.damage / 100)
            * (1 + self.damage_amp / 100) * dmg_reduction * final_mult * (1 + source_pct / 100)
            * self.attack_bucket_mult * (1 + self.art_joint_damage / 100)
        )
        return dmg.expected_hit(base_hit, self.min_damage, self.max_damage, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate,
                                self.crit_damage + self.crit_damage_bonus)

    def skill_hit(self, s):
        """(boss, normal) expected damage of one hit of a damage skill (before the branch multipliers).  A skill mastery MULTIPLIES the skill's damage (CLAUDE.md bug 2)."""
        pct = self.coeff_pct(s["base"], s["fidx"], True, s["step"]) * (1 + s.get("mastery", 0) / 100)
        return (self.hit_damage(pct, False, s.get("cygnus_pct", 0.0), "boss"), self.hit_damage(pct, False, s.get("cygnus_pct", 0.0), "normal"))

    # ---- targets and branch blending ----
    def branch_multipliers(self, mastery_boss, mastery_normal, targets):
        """(boss, normal) multiplier of a row.  The monster-damage-taken terms differ per branch (Emerald Flower's boss +15 %, Pinpoint Pierce's weaken: boss / PvP only)."""
        if self.monster_type == "pvp":
            return 1.0 * self.extra_boss, 1.0 * self.extra_norm
        targets = min(targets, self.fight.max_enemies_hit)
        boss_term = self.boss_damage + mastery_boss + self.taken_boss + self.art_boss_damage
        normal_term = self.normal_damage + mastery_normal + self.taken_normal + self.art_normal_damage
        return (1 + boss_term / 100) * self.extra_boss, (1 + normal_term / 100) * targets * self.extra_norm

    def blend_row(self, key, boss_unit, normal_unit, mastery_boss, targets, mastery_normal=0):
        b, n = self.branch_multipliers(mastery_boss, mastery_normal, targets)
        fb, fn = self.timing_factors(key)
        return self.ledger.blend(key, boss_unit, normal_unit, b * fb, n * fn, True)

    def timed_uptime(self, eff_cd, eff_dur):
        """Uptime of an effect that lasts ``eff_dur`` s every ``eff_cd`` s from t = 0, with the periods used as given (no Skill Cooldown Decrease / Buff Duration here):
        exact windows in a fixed fight, one window in PvP, the steady-state ratio capped at 100 % otherwise."""
        f = self.fight
        if f.fixed_duration_active:
            return f.exact_buff_uptime(eff_cd, eff_dur) / f.fight_duration
        if f.monster_type == "pvp":
            return min(eff_dur, f.pvp_len) / f.pvp_len
        return min(1.0, eff_dur / eff_cd)

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
        CV = D.CURVES
        flat_attack, attack_pct = inp("flat_attack"), inp("attack_pct")
        self.attack = dmg.attack_value(flat_attack, attack_pct + sens.get("attack_mult_delta", 0.0))      # (+ Whispers' / Sylvan Aid's / Second Wind's / Touch of the Wind's level delta, Sensitivity only)
        if sens.get("mainstat_attack_delta"):      # Sensitivity: the main/sub stat's flat-Attack channel (bug 7), applied before ATTACK%
            self.attack += sens["mainstat_attack_delta"] * (1 + attack_pct / 100)
        flat_dex, dex_pct, str_ = inp("flat_dex"), inp("dex_pct"), inp("str")
        self.stat_damage = (flat_dex * (1 + dex_pct / 100)) * 0.01 + str_ * 0.0025
        self.damage_input = inp("damage") + sens.get("damage_delta", 0.0)          # (+ Featherweight's level delta, Sensitivity only)
        self.damage_amp = inp("damage_amp")
        self.boss_damage = inp("boss_damage") + sens.get("boss_damage_delta", 0.0)      # (+ Featherweight - Boss Monster Damage's level delta / Star Rock...)
        self.normal_damage = inp("normal_damage") + sens.get("normal_damage_delta", 0.0)      # (+ Featherweight's level delta, Sensitivity only)
        self.status_effect_damage = status_effect_damage = inp("status_effect_damage")
        self.final_damage = inp("final_damage")
        if sens.get("final_damage_factor") is not None:
            # Sensitivity: a baked-in Final Damage artifact what-if is a factor on the TYPED value inside the additive bucket (``baked_fd_form="typed"``, as Hero / Dawn Warrior)
            self.final_damage = ((1 + self.final_damage / 100) * sens["final_damage_factor"] - 1) * 100
        self.min_damage = inp("min_damage") + sens.get("min_damage_delta", 0.0)      # (+ Bow Mastery's level delta, Sensitivity only)
        self.max_damage = inp("max_damage") + sens.get("max_damage_delta", 0.0)      # (+ Bow Expert's level delta / Athena's Gloves' dependent Max Damage, Sensitivity only)
        self.crit_rate_input = inp("crit_rate") + sens.get("crit_rate_threshold_extra", 0.0)
        self.crit_rate = self.crit_rate_input + sens.get("crit_rate_delta", 0.0)      # (+ Sylvan Aid's level delta, Sensitivity only)
        self.crit_damage = inp("crit_damage")
        attack_speed_base = inp("attack_speed")
        def_pen_typed = sens_mod.def_pen_with_dose(inp("def_pen") + sens.get("def_pen_delta", 0.0), sens)      # (+ Albatross Max's level delta, Sensitivity only)
        self.basic_attack_damage = inp("basic_attack_damage") + sens.get("basic_attack_damage_delta", 0.0)      # (+ Physical Training's level delta, Sensitivity only)
        self.skill_damage = inp("skill_damage") + sens.get("skill_damage_delta", 0.0)      # (+ Bow Expert's level delta, Sensitivity only)
        basic_attack_target_increase = inp("basic_attack_target_increase")
        buff_duration_increase_pct = inp("buff_duration_increase_pct") + sens.get("bdi_extra", 0.0)
        summon_time_inc = inp("companion_summon_time_increase_pct")
        self.pvp_len = pvp_len = inp("pvp_fight_length") or content_mod.DEFAULT_PVP_FIGHT_LENGTH
        fight = self.fight = fight_mod.Fight(ct, pvp_len, inp("skill_cooldown_decrease"), buff_duration_increase_pct,
                                             inp("max_enemies_hit"))
        self.ledger = blend_mod.BranchLedger(normal_weight)

        # ---- artifacts (equip effects): slots, the early quantities (Attack% bucket / Hexagon / Charm) and Soul Contract's cooldown decrease ----
        self.eq = eq = sens["eq"] if "eq" in sens else art_mod.resolve_slots(inp.raw("artifacts"))
        actx = self.art_ctx = art_mod.Ctx(self.content_type, monster_type, fight_duration, pvp_len, fixed_duration_active,
                                          crit_rate=self.crit_rate_input, attack_speed=attack_speed_base)
        pre = self.art_pre = art_mod.Pre(eq, actx)
        summon_time_inc += art_mod.summon_time_inc_pct(eq)
        fight.cd_extra_pct = art_mod.soul_contract_pct(eq, self.content_type)
        self.art_final_damage = self.art_joint_damage = self.art_skill_damage = self.art_basic_attack_damage = 0.0
        self.art_boss_damage = self.art_normal_damage = self.art_crit_rate = 0.0
        self.extra_boss = self.extra_norm = 1.0
        self.ph_b = self.ph_n = 1.0
        eff_cooldown = fight.eff_cooldown
        eff_duration = fight.eff_duration

        basic_lvl = self.sl.input_level(4)
        fs_curve = CV["FAIRY_SPIRAL"]
        self.skill_coefficient_base = (fs_curve.base / 10) * self._factor(basic_lvl, fs_curve.fidx) / 1000

        # ---- level-resolved rows (static part: cooldowns, targets) ----
        SKILLS = self.skills = {}
        for key, t in D.DAMAGE_SKILLS.items():
            c = CV[t["curve"]]
            s = dict(step=c.step, cooldown=t["cooldown"], hits=t["hits"], base=c.base, fidx=c.fidx, mastery=gated(t["mastery"]), mastery_normal=0,
                     costs_action=t["costs_action"], targets=t["targets"], branch="both", cast_row=t.get("cast_row", key), coef_pct=coeff_pct(c.base, c.fidx, True, c.step))
            cyg = t.get("cygnus")
            s["cygnus_pct"] = coeff_pct(CV[cyg].base, CV[cyg].fidx, True, CV[cyg].step) if (cyg and unlocked("CALL_OF_CYGNUS")) else 0.0
            SKILLS[key] = s
        self.normal_targets = {k: v["targets"] for k, v in SKILLS.items()}
        self.normal_targets["STORM_BRINGER"] = D.STORM_BRINGER_RULES["targets"]

        # ---- timed buffs: uptimes (cast on cooldown from t = 0, duty-cycle averages) ----
        se, eh, sye, ef, ed, sw = D.STORM_ELEMENTAL, D.ELEMENTAL_HARMONY, D.SHARP_EYES, D.EMERALD_FLOWER, D.EMERALD_DUST, D.SECOND_WIND
        se_dur = se["duration"] * (se["duration_mastery"][1] if level >= se["duration_mastery"][0] else 1.0)
        self.se_up = se_up = fight.buff_uptime(se["cooldown"], se_dur, True) if unlocked("STORM_ELEMENTAL") else 0.0
        eh_up = fight.buff_uptime(eh["cooldown"], eh["duration"], True) if unlocked("ELEMENTAL_HARMONY") else 0.0
        sye_dur = sye["duration"] * (sye["duration_mastery"][1] if level >= sye["duration_mastery"][0] else 1.0)
        self.sye_up = sye_up = fight.buff_uptime(sye["cooldown"], sye_dur, True) if unlocked("SHARP_EYES") else 0.0
        ef_cd = D.BUFF_COOLDOWNS["EMERALD_FLOWER"] * (ef["cooldown_mastery"][1] if level >= ef["cooldown_mastery"][0] else 1.0)
        self.ef_cd_base = ef_cd
        self.ef_up = ef_up = self.timed_uptime(eff_cooldown(ef_cd, True), ef["duration"]) if unlocked("EMERALD_FLOWER") else 0.0       # the flower's own 20 s window (damage taken)
        dust_on = unlocked("EMERALD_DUST") and unlocked("EMERALD_FLOWER")
        self.ed_up = ed_up = fight.buff_uptime(ef_cd, ed["fd_duration"], True) if dust_on else 0.0      # Dust's Final Damage: a standalone 20 s buff (Buff Duration applies)

        sa, sd_ = CV["STORM_ELEMENTAL_ATTACK"], CV["STORM_ELEMENTAL_DAMAGE"]
        self.se_attack_full = se_attack_full = coeff_pct(sa.base, sa.fidx, True, sa.step) if unlocked("STORM_ELEMENTAL") else 0.0
        self.se_damage_full = se_damage_full = coeff_pct(sd_.base, sd_.fidx, True, sd_.step) if unlocked("STORM_ELEMENTAL") else 0.0
        sec = CV["SHARP_EYES_CRIT_DAMAGE"]
        self.sye_crit_full = sye_crit_full = coeff_pct(sec.base, sec.fidx, True, sec.step) if unlocked("SHARP_EYES") else 0.0
        efb, edt, edf = CV["EMERALD_FLOWER_BOSS_TAKEN"], CV["EMERALD_DUST_TAKEN"], CV["EMERALD_DUST_FD"]
        self.ef_boss_taken_full = coeff_pct(efb.base, efb.fidx, True, efb.step) if unlocked("EMERALD_FLOWER") else 0.0
        self.ed_taken_full = coeff_pct(edt.base, edt.fidx, True, edt.step) if dust_on else 0.0
        self.ed_fd_full = (coeff_pct(edf.base, edf.fidx, True, edf.step) + gated(ed["fd_mastery"])) if dust_on else 0.0

        self.damage = self.damage_input + se_damage_full * se_up          # Storm Elemental's "damage" is the Damage % bucket
        se_attack_avg = se_attack_full * se_up
        self.attack_bucket_sum = attack_bucket_sum = se_attack_avg
        self.attack_bucket_avg = attack_bucket_sum + pre.agg_attack_pct
        self.attack_bucket_mult = 1 + self.attack_bucket_avg / 100

        self.crit_rate_bonus = 0.0                                      # (no live Crit Rate source: Sylvan Aid is a stat-screen passive)
        crit_damage_bonus_live = sye_crit_full * sye_up                 # Sharp Eyes: YOUR Critical Damage +40 % while it lasts
        self.crit_damage_bonus = crit_damage_bonus_live
        self.final_damage_extra = self.ed_fd_full * ed_up + sens.get("final_damage_delta", 0.0)      # (+ Eagle Eye's / Albatross Max's level delta, Sensitivity only)

        self.def_pen_n = def_pen_n = def_pen_typed
        self.def_pen_b = def_pen_typed
        self.def_pen_c = def_pen_typed
        self.def_pen_eff = def_pen_typed

        # ---- the monster-damage-taken terms per branch: Emerald Flower (boss +15 %) and Emerald Dust (+8 % in range, ADDED), Pinpoint Pierce's weaken (+10 % for 12 s: one target = boss / PvP) ----
        pw = D.PINPOINT_WEAKEN
        pinpoint_cd = SKILLS["PINPOINT_PIERCE_ARROW1"]["cooldown"]
        self.pinpoint_weaken_avg = (pw["pct"] * self.timed_uptime(eff_cooldown(pinpoint_cd, True), pw["duration"])
                                    if (unlocked("PINPOINT_PIERCE_ARROW1") and level >= pw["level"]) else 0.0)
        self.taken_boss = (self.ef_boss_taken_full + self.ed_taken_full) * ef_up + self.pinpoint_weaken_avg
        self.taken_normal = self.ed_taken_full * ef_up
        self.monster_dmg_bonus = (1 - normal_weight) * self.taken_boss + normal_weight * self.taken_normal

        # ---- Attack Speed: Elemental Harmony (duty cycle) + Second Wind (8 s after N skill activations, then 4 s dead time) ----
        steady_cast_rate = sum(1 / eff_cooldown(ef_cd if k == "EMERALD_FLOWER" else (D.BUFF_COOLDOWNS[k] if k in D.BUFF_COOLDOWNS else SKILLS[k]["cooldown"]), True)
                               for k in D.COST_ACTION_ORDER if unlocked(k))
        sw_n = sw["activations_mastery"][1] if level >= sw["activations_mastery"][0] else sw["activations"]
        self.sw_up = sw_up = (sw["duration"] / (sw["duration"] + sw["dead_time"] + sw_n / steady_cast_rate)) if (unlocked("SECOND_WIND") and steady_cast_rate > 0) else 0.0
        swc = CV["SECOND_WIND_AS"]
        self.sw_as_full = sw_as_full = coeff_pct(swc.base, swc.fidx, True, swc.step) if unlocked("SECOND_WIND") else 0.0
        self.as_bonus = as_bonus = eh["attack_speed"] * eh_up + sw_as_full * sw_up
        self.actions_per_second = actions_per_second = dmg.actions_per_second(attack_speed_base + sens.get("attack_speed_extra", 0.0), as_bonus)

        # ---- Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`) ----
        choice, c_level = comp_mod.read_choice(inp)
        self.companion_choice, self.companion_level = choice, c_level
        player_stun = []
        for e in D.PLAYER_STUN:
            e = dict(e, cd=SKILLS[e["key"]]["cooldown"], on=(unlocked(e["key"]) and level >= e.get("level", 0)))
            player_stun.append(e)
        pl_on = any(e["on"] for e in player_stun)
        stun_info = comp_mod.stun_probe(ct, fight, pvp_len, choice, c_level, summon_time_inc)
        hasstun = bool(stun_info and stun_info.get("hasstun")) or pl_on
        ko = content_mod.ko_windows(fight_duration)
        self.status_on = status_on = fixed_duration_active and normal_weight == 0 and (content_type in ko or hasstun)
        startup_count = sum(1 for k in D.STARTUP_BUFFS if unlocked(k))
        t0_pl = 0.0 if status_on else ((startup_count / actions_per_second) if fixed_duration_active else 0.0)
        self.pst = pst = [dict(id=e["id"], typ=e["typ"], cd=eff_cooldown(e["cd"], True), dur=e["dur"],
                               p=e["p"], on=e["on"], t0=t0_pl, tick=1.0, win=0.0) for e in player_stun]
        stun_info, stun_pin = comp_mod.stun_windows(ct, fight, pvp_len, pst, choice, c_level, summon_time_inc, sens)
        self.stf_b = stun_pin["stunfracB"]
        self.stf_n = stun_pin["stunfracN"]
        self.engine_n = ENGINE_N = {}
        E_ENGINE = None
        self.phi_rows = {}
        self.phi_unif = 1.0
        E_FS = {}
        e1 = None
        if status_on:
            comp_stun = stun_info["stun_vector"](stl.NB_MAX) if "stun_vector" in stun_info else [0.0] * stl.NB_MAX
            stun_vec = [min(1.0, a + b) for a, b in zip(comp_stun, stl.pl_stun_vector([dict(e, t0=0.0) for e in pst], fight_duration, stl.NB_MAX))]
            eng_host = dict(T=fight_duration, S=status_effect_damage, ko=ko.get(content_type, []), hex_v=pre.hex_v, hex_period=20, hex_max=3,
                            A0=attack_bucket_sum + pre.a0, charm_v=pre.charm_val, hex_avg=pre.hex_avg, c_slot=0.0, stun=stun_vec, buffs=[],
                            groups=[])
            e1 = sens["strip"][0] if "strip" in sens else stl.solve(eng_host)   # pass 1 (no engine-timed buff: only the constant Attack% term and the windows)
            self.attack_bucket_mult = e1["Bbuff_mean"]
        self.e1 = e1

        # Buff-Casting Startup Delay: in fixed-duration fights the character casts every unlocked, actively cast buff sequentially at fight start before the first damage-skill cast.
        self.buff_cast_startup_time = (startup_count / actions_per_second) if (fixed_duration_active and not status_on) else 0.0
        fight.startup_time = self.buff_cast_startup_time

        # ---- artifact effects (full) ----
        actx.aps, actx.startup = actions_per_second, self.buff_cast_startup_time
        s0, w0, d_comp, period, ts_window = comp_mod.horn_window(actx, monster_type, fight_duration, pvp_len, summon_time_inc, stun_pin,
                                                                 choice, c_level)
        dw = art_mod.damage_weights(fight_duration, pre.hex_v, attack_bucket_sum + pre.a0, pre.charm_val, e1["mult"] if status_on else None)
        actx.horn_uptime = art_mod.horn_flute_uptime(actx, dw, s0, w0, d_comp, period, ts_window)
        actx.crit_rate = self.crit_rate + self.crit_rate_bonus
        eff = self.art_effects = art_mod.Effects(eq, actx, pre)
        self.art_crit_rate = eff.agg_crit_rate
        self.crit_damage_bonus = crit_damage_bonus_live + eff.agg_crit_damage
        self.crit_damage_bonus += sens.get("crit_damage_delta", 0.0)              # (Sensitivity: Book of Ancient's dependent Crit Damage while Crit Rate is swept)
        self.crit_damage_bonus += sens_mod.boa_crit_damage_delta(
            sens, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate)
        self.crit_rate_total = self.crit_rate + self.crit_rate_bonus + self.art_crit_rate
        self.art_boss_damage, self.art_normal_damage = eff.agg_boss_damage + sens.get("boss_damage_extra", 0.0), eff.agg_normal_damage
        self.art_final_damage = eff.agg_final_damage
        self.art_joint_damage = eff.agg_damage + eff.agg_enemy_dmg_taken
        self.art_skill_damage, self.art_basic_attack_damage = eff.agg_skill_damage, eff.agg_basic_attack_damage
        self.extra_boss, self.extra_norm = eff.extras(actx, self.monster_defense, self.def_pen_b,
                                                      self.crit_rate + self.crit_rate_bonus + self.art_crit_rate, self.crit_damage + self.crit_damage_bonus)
        self.ph_b, self.ph_n = art_mod.phase_state_ratios(content_type, fight_duration, pre.hex_v, pre.hex_avg, self.attack_bucket_avg,
                                                          pre.charm_val, pre.charm_avg)

        # ---- Fairy Spiral (basic attack): its own damage chain + boss chain, hits, targets ----
        fs_mastery = gated(D.FS_MASTERY)
        self.fs_mastery_boss = fs_mastery_boss = gated(D.FS_BOSS_MASTERY)
        fs_pct = self.skill_coefficient_base * (1 + fs_mastery / 100)
        self.fs_targets = D.FS_BASE_TARGETS + basic_attack_target_increase
        h0, hl, h1 = D.FS_HITS
        fs_hits = h1 if level >= hl else h0
        fs_hit_b, fs_hit_n = self.hit_damage(fs_pct, True, 0.0, "boss"), self.hit_damage(fs_pct, True, 0.0, "normal")

        hits_of = {key: self.skill_hit(s) for key, s in SKILLS.items()}

        # ---- Status/KO engine pass 2: the damage skills' casts (weight of one cast = its boss damage before any timing factor) ----
        if status_on:
            def percast(key):
                if not unlocked(key):
                    return 0.0
                sk = SKILLS[key]
                return sk["hits"] * hits_of[key][0] * self.branch_multipliers(0, 0, sk["targets"])[0]
            b_fs = self.branch_multipliers(fs_mastery_boss, 0, self.fs_targets)[0]
            c_slot = (fs_hits * fs_hit_b * b_fs) if unlocked("FAIRY_SPIRAL") else 0.0
            groups = status_mod.build_groups(D, unlocked, SKILLS, percast, fight.capped_window,
                                             lambda cast: eff_cooldown(SKILLS[cast]["cooldown"], SKILLS[cast]["costs_action"]),
                                             stun_keys={e["key"] for e in D.PLAYER_STUN})
            E_ENGINE = status_mod.solve_groups(self, D, eng_host, groups, c_slot, ENGINE_N, sens)
            E_FS = E_ENGINE["fs"]
        self.e_engine = E_ENGINE

        # ---- Cast rate (subtracted from the basic attack) ----
        eff_cd_of = {}
        for key in D.COST_ACTION_ORDER:
            if key in SKILLS:
                eff_cd_of[key] = eff_cooldown(SKILLS[key]["cooldown"], True)
            elif key == "EMERALD_FLOWER":
                eff_cd_of[key] = eff_cooldown(ef_cd, True)
            else:
                eff_cd_of[key] = eff_cooldown(D.BUFF_COOLDOWNS[key], True)

        def cast_count(k):
            if k in ENGINE_N:
                return ENGINE_N[k]
            return fight.exact_casts(eff_cd_of[k]) if k in D.BUFF_ROW_KEYS else fight.non_buff_casts(eff_cd_of[k])

        def cast_rate_of(k):
            return (cast_count(k) / fight_duration) if fixed_duration_active else (1 / eff_cd_of[k])

        cast_rate = sum(cast_rate_of(k) for k in D.COST_ACTION_ORDER if unlocked(k))
        self.cast_rate = cast_rate
        self.fs_per_second = fs_per_second = max(0, actions_per_second - cast_rate)

        # ---- Fairy Spiral (basic attack) DPS ----
        fs_on = unlocked("FAIRY_SPIRAL")
        fs_dps = (self.blend_row("FAIRY_SPIRAL", fs_hits * fs_hit_b * fs_per_second, fs_hits * fs_hit_n * fs_per_second, fs_mastery_boss, self.fs_targets) if fs_on else 0.0)
        self.fs_dps = fs_dps

        # ---- Spirit Arrows (Trifling Wind I -> II -> III): damage of ONE arrow, the arrows of a skill activation / of Song of Heaven ----
        tw = D.TRIFLING_WIND
        tw_on = unlocked("TRIFLING_WIND_I")
        tw_curve = CV["TRIFLING_WIND_II"] if unlocked("TRIFLING_WIND_II") else CV["TRIFLING_WIND_I"]
        tw_chance = (tw["double_chance"] + gated(tw["double_chance_bonus"])) if unlocked("TRIFLING_WIND_II") else 0.0
        tw_pct = coeff_pct(tw_curve.base, tw_curve.fidx, True, tw_curve.step) * (1 + gated(tw["mastery"]) / 100) * (1 + tw_chance / 100)
        tw_fd_c = CV["TRIFLING_WIND_III_FD"]
        tw_fd = (coeff_pct(tw_fd_c.base, tw_fd_c.fidx, True, tw_fd_c.step) + gated(tw["fd_bonus"])) if unlocked("TRIFLING_WIND_III") else 0.0
        self.tw_arrow_pct, self.tw_fd = tw_pct, tw_fd
        arrow_b, arrow_n = self.hit_damage(tw_pct, False, tw_fd, "boss"), self.hit_damage(tw_pct, False, tw_fd, "normal")
        n_tw = tw["arrows"] + gated(dict(tw["arrows_bonus"]))
        self.tw_arrows_per_cast = n_tw
        act_rate = cast_rate / (1 + tw["icd"] * cast_rate)          # skill activations per second, at most one per 2 s (cooldown of the passive)
        tw_dps = (self.blend_row("TRIFLING_WIND", act_rate * n_tw * arrow_b * ladder_mean(n_tw), act_rate * n_tw * arrow_n, 0, 1)
                  if (tw_on and cast_rate > 0) else 0.0)
        self.tw_dps = tw_dps
        sp = D.SONG_SPIRIT
        n_song = sp["volleys"] * (sp["per_volley"] + gated(dict(sp["per_volley_bonus"])))
        self.song_arrows_per_cast = n_song
        song_on = unlocked("SONG_OF_HEAVEN") and tw_on
        song_rate = cast_rate_of("SONG_OF_HEAVEN") if song_on else 0.0
        song_arrow_dps = (self.blend_row("SONG_SPIRIT_ARROWS", song_rate * n_song * arrow_b * ladder_mean(n_song), song_rate * n_song * arrow_n, 0, 1) if song_on else 0.0)
        self.song_arrow_dps = song_arrow_dps

        # ---- Storm Bringer: a skill activation starts a 15 s storm (50 %, 25 s cooldown); during it attacks roll for the giant arrow ----
        sb = D.STORM_BRINGER_RULES
        sb_on = unlocked("STORM_BRINGER")
        sbc = CV["STORM_BRINGER"]
        sb_pct = coeff_pct(sbc.base, sbc.fidx, True, sbc.step) * (1 + gated(sb["mastery"]) / 100)
        sb_hit_b, sb_hit_n = self.hit_damage(sb_pct, False, 0.0, "boss"), self.hit_damage(sb_pct, False, 0.0, "normal")
        sb_chance = sb["chance"] + gated(sb["chance_bonus"])
        wait = (1 / (sb["trigger_chance"] * steady_cast_rate)) if steady_cast_rate > 0 else 1e9
        self.sb_up = sb_up = min(1.0, sb["duration"] / (eff_cooldown(sb["cooldown"], True) + wait)) if (sb_on and steady_cast_rate > 0) else 0.0
        attack_sources = [(fs_per_second if fs_on else 0.0, fight.cap_targets(self.fs_targets))]
        for k in ("SPIRALING_VORTEX", "PINPOINT_PIERCE_ARROW1", "SONG_OF_HEAVEN"):
            if unlocked(k):
                attack_sources.append((cast_rate_of(k), min(SKILLS[k]["targets"], fight.max_enemies_hit)))
        x_boss = sb_chance * sum(r for r, _ in attack_sources)
        x_norm = sum(r * dmg.q_roll(sb_chance, t) for r, t in attack_sources)
        self.sb_rate = {"boss": sb_up * x_boss / (1 + sb["icd"] * x_boss), "normal": sb_up * x_norm / (1 + sb["icd"] * x_norm)}
        sb_dps = (self.blend_row("STORM_BRINGER", sb["hits"] * self.sb_rate["boss"] * sb_hit_b, sb["hits"] * self.sb_rate["normal"] * sb_hit_n, 0, sb["targets"])
                  if sb_on else 0.0)
        self.sb_dps = sb_dps

        skill_dps = {}
        for key, s in SKILLS.items():
            if not unlocked(key):
                skill_dps[key] = 0.0
                continue
            hd_b, hd_n = hits_of[key]
            eff_cd = eff_cooldown(s["cooldown"], s["costs_action"])
            T = fight_duration
            if status_on and key in ENGINE_N:
                rate = s["hits"] * ENGINE_N[key] / T
            elif fixed_duration_active:
                rate = fight.non_buff_total_hits(eff_cd, s["hits"], None, None) / T
            else:
                rate = s["hits"] / eff_cd
            skill_dps[key] = self.blend_row(key, rate * hd_b, rate * hd_n, 0, s["targets"], s["mastery_normal"])
        self.skill_dps = skill_dps
        self.player_dps = fs_dps + tw_dps + song_arrow_dps + sb_dps + sum(skill_dps.values())

        # ---- player's boss-only / normal-only totals (the companion's damage-share weights) ----
        row_dps = [("FAIRY_SPIRAL", fs_dps), ("TRIFLING_WIND", tw_dps), ("SONG_SPIRIT_ARROWS", song_arrow_dps), ("STORM_BRINGER", sb_dps)] + list(skill_dps.items())
        self.pb_total, self.pn_total, self.pu_total = self.ledger.split_totals(row_dps, D.STATUS_UNIFORM_ROWS)

        # ---- companion: src/companion_python_model.py fed with this model's own pipeline numbers ----
        self.begin_companion(summon_time_inc)
        if (choice != "None" and c_level >= 1) or pl_on or sens.get("want_comp_host"):
            basic_b, basic_n = self.ledger.pairs.get("FAIRY_SPIRAL", (0.0, 0.0))[:2]
            se_full = se_attack_full
            comp_host = dict(comp_mod.host_common(self, pre, eff, basic_b, basic_n),
                unit=self.hit_damage(100.0, True, 0.0, "comp") / 100, sd=self.skill_damage + self.art_skill_damage, aps=actions_per_second,
                avgbuff=self.attack_bucket_mult, attack_bucket_avg=self.attack_bucket_avg, agg_damage_avg=self.art_joint_damage,
                avgbuff_snap=lambda charm, extra: 1 + (se_full + pre.agg_attack_pct - pre.charm_avg + charm + extra) / 100,
                boss_pct=self.boss_damage + self.art_boss_damage + self.taken_boss,
                norm_pct=self.normal_damage + self.art_normal_damage + self.taken_normal,
                cr_total=self.crit_rate + self.crit_rate_bonus + self.art_crit_rate, cd_total=self.crit_damage + self.crit_damage_bonus,
                def_pen=self.def_pen_c, taken_bucket=self.art_joint_damage, pst=pst)
            self.comp_host = comp_host
            self.run_companion(comp_host, choice, c_level, summon_time_inc, pl_on)
        self.total_dps = self.player_dps + self.companion_dps

    # ------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _factor(level, idx):
        from ..common import factors
        return factors.get_factor(level, idx)

    def row_dps(self, key):
        if key == "FAIRY_SPIRAL":
            return self.fs_dps
        if key == "TRIFLING_WIND":
            return self.tw_dps
        if key == "SONG_SPIRIT_ARROWS":
            return self.song_arrow_dps
        if key == "STORM_BRINGER":
            return self.sb_dps
        return self.skill_dps.get(key, 0.0)

    def derived_extra(self):
        return dict(
            basic_attacks_per_second=self.fs_per_second, avg_buff_mult=self.attack_bucket_mult, as_bonus=self.as_bonus,
            attack_bucket_mult=self.attack_bucket_mult, attack_bucket_sum=self.attack_bucket_sum,
            skill_coefficient_base=self.skill_coefficient_base, buff_cast_startup_time=self.buff_cast_startup_time,
            crit_rate_bonus=self.crit_rate_bonus, crit_damage_bonus=self.crit_damage_bonus, final_damage_extra=self.final_damage_extra,
            monster_dmg_bonus=self.monster_dmg_bonus, monster_damage_taken_boss=self.taken_boss, monster_damage_taken_normal=self.taken_normal,
            def_pen_effective=self.def_pen_eff,
            storm_elemental_uptime=self.se_up, sharp_eyes_uptime=self.sye_up, emerald_flower_uptime=self.ef_up, emerald_dust_uptime=self.ed_up, second_wind_uptime=self.sw_up,
            storm_elemental_attack=self.se_attack_full, storm_elemental_damage=self.se_damage_full, sharp_eyes_crit_damage=self.sye_crit_full,
            emerald_dust_final_damage=self.ed_fd_full, pinpoint_weaken_average=self.pinpoint_weaken_avg,
            trifling_wind_arrow_pct=self.tw_arrow_pct, trifling_wind_final_damage=self.tw_fd, trifling_wind_arrows_per_cast=self.tw_arrows_per_cast,
            song_arrows_per_cast=self.song_arrows_per_cast,
            storm_bringer_uptime=self.sb_up, storm_bringer_rate_boss=self.sb_rate["boss"], storm_bringer_rate_normal=self.sb_rate["normal"],
            basic_attack_targets=self.fs_targets,
        )


fields, schema, defaults = classapi.make(CLASS_ID, CLASS_NAME, STAT_IDENTITY, _MAIN_STAT_FIELDS, D)
artifact_schema = classapi.artifact_schema


def model(inputs):
    """The evaluated model object (everything ``compute`` reports plus the internals engine/sensitivity.py reads: ``comp_host``, ``e1`` / ``e_engine`` (the timeline strip),
    ``art_effects`` ...).  Same input dict as ``compute``; honours ``inputs["_sens"]`` (engine/common/sens.py)."""
    return _Model(inputs)


def compute(inputs):
    """DPS of one Wind Archer setup.  ``inputs``: dict (see module docstring / ``schema()``); returns a JSON-friendly dict:

    total_dps / player_dps / boss_dps / normal_dps / player_boss_dps / player_normal_dps, skills (per damage row: key, name, dps, share, boss_dps, normal_dps, unlocked),
    companion (None or dps/boss/normal/share + model details; choice "None" = the player's stun uplift only), engine_on (Status/KO timeline engine), engine (its cast
    counts and timing factors), derived (ATTACK, STAT_DAMAGE, actions/s, buff uptimes and values, computed Inputs rows ...).
    """
    return _Model(inputs).result()
