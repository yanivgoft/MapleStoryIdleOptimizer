"""Blaze Wizard (Cygnus Knight, INT main / LUK sub mage): an ENGINE-NATIVE, PUBLISHED class (scaling confirmed 2026-11-27, published by the user the same day) - there is no workbook, builder or verify script for it.

    from engine.classes import blaze_wizard
    result = blaze_wizard.compute(blaze_wizard.defaults("World Boss"))

Published (no ``PUBLISHED`` flag).  The skill SCALING is confirmed (the user's higher-level readings of
2026-11-27, ``CONFIRMED_BY_READINGS`` in ``engine/data/blaze_wizard.py``).  The independent check is the user's text and readings: ``tests/golden/test_blaze_wizard_displayed.py``.

Built on Dawn Warrior's model (same input dict, artifacts / companion / Status Effect Damage + KO timeline plumbing, Sensitivity hooks).  Blaze Wizard specifics:

* **Basic attack = Final Orbital Flame** (level 100+, absent below like every class).  **Orbital Explosion** (passive, unlock 45): during 15 s of fire energy every 30 s each basic
  attack rolls 60 % per enemy hit (1 s ICD) for 50 % additional damage on 5 targets x 2.
* **Flame Elemental** (timed Attack buff) carries Greater (Damage %), Grand (Basic Attack Damage, Skill Damage) and Final Flame Elemental (Def Pen, Crit Damage, Final Damage) effects
  that count for its uptime; Flashfire (Attack %, 30 s mark) and Burning Conduit (own Final Damage) are timed too.  All are cast on cooldown from t = 0 and averaged by uptime.
* **Fires of Creation**: the Fire Lion (Normal Monster Damage, Basic Attack target +1, Blazing Extinction / Towering Inferno Lion variants) is the NORMAL-monster branch, the Flame Fox
  (Boss Monster Damage, Def Pen, Fox variants incl. Towering Inferno's boss flame strikes) the BOSS / PvP branch: per-branch damage rows and per-branch Defense Penetration.
* **Stuns**: Cinder Maelstrom 1.5 s, Flame Tempest 1 s (from Lv90) feed the player-stun timeline; Cinder Maelstrom's weaken (+9 % damage taken, Lv98) is a damage-taken term.
* **Always-on passives and stat masteries are NOT added** (the Inputs come from the in-game stat screen): see ``D.STAT_SCREEN_EFFECTS`` / the known-gaps file.
Every judgement call is flagged in ``D.ROW_NOTES`` and ``data/cygnus/blaze_wizard_known_gaps.md``.
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
from ..data import blaze_wizard as D
from .. import artifacts as art_mod
import status_timeline as stl  # noqa: E402  (src/status_timeline.py through the shim)

CLASS_ID = "blaze_wizard"
CLASS_NAME = "Blaze Wizard"
STAT_IDENTITY = {"main": "INT", "sub": "LUK"}

_MAIN_STAT_FIELDS = [
    schema_mod.field("flat_int", "Flat INT", "Main stats", "float", "flat", 0),
    schema_mod.field("int_pct", "INT %", "Main stats", "float", "%", 0),
    schema_mod.field("luk", "LUK", "Main stats", "float", "flat", 0),
]


def combine_def_pen(a, b):
    """Two Defense Penetration sources combine by diminishing returns."""
    return 100 * (1 - (1 - a / 100) * (1 - b / 100))


class _Model(model_mod.ModelBase):
    DATA = D

    # ------------------------------------------------------------------------------------------------------------------
    # ---- per-hit pipeline ----
    def hit_damage(self, coeff_pct_val, is_basic, skill_fd_pct=0.0, branch="boss"):
        """Expected damage of one hit in a branch ("boss" = boss / PvP, "normal", "comp" = the companion host's blended Defense Penetration).  ``skill_fd_pct``: the row's own Final
        Damage multiplier (Call of Cygnus: 1 + pct/100, the Maple Hero convention)."""
        base_damage = self.attack * (coeff_pct_val / 100)
        dp = self.def_pen_n if branch == "normal" else (self.def_pen_c if branch == "comp" else self.def_pen_b)
        dmg_reduction = dmg.defense_reduction(self.monster_defense, dp)
        fd_bucket = self.final_damage + self.final_damage_extra
        final_mult = (1 + fd_bucket / 100) * (1 + self.art_final_damage / 100) * (1 + skill_fd_pct / 100)
        if is_basic:
            source_pct = self.basic_attack_damage + self.art_basic_attack_damage + self.gfe_basic_avg
        else:
            source_pct = self.skill_damage + self.art_skill_damage + self.gfe_skill_avg
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
        """(boss, normal) multiplier of a row.  Flame Fox's Boss Monster Damage joins the boss term and Fire Lion's Normal Monster Damage the normal term (per branch: Fox vs a boss,
        Lion otherwise); Cinder Maelstrom's weaken (``monster_dmg_bonus``) joins both."""
        if self.monster_type == "pvp":
            return 1.0 * self.extra_boss, 1.0 * self.extra_norm
        targets = min(targets, self.fight.max_enemies_hit)
        boss_term = self.boss_damage + mastery_boss + self.monster_dmg_bonus + self.art_boss_damage + self.fox_boss_damage
        normal_term = self.normal_damage + mastery_normal + self.monster_dmg_bonus + self.art_normal_damage + self.lion_normal_damage
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
        self.attack = dmg.attack_value(flat_attack, attack_pct + sens.get("attack_mult_delta", 0.0))      # (+ Fire Repulsion's / Flame Barrier's level delta, Sensitivity only: baked into Inputs!attack_pct)
        if sens.get("mainstat_attack_delta"):      # Sensitivity: the main/sub stat's flat-Attack channel (bug 7), applied before ATTACK%
            self.attack += sens["mainstat_attack_delta"] * (1 + attack_pct / 100)
        flat_int, int_pct, luk = inp("flat_int"), inp("int_pct"), inp("luk")
        self.stat_damage = (flat_int * (1 + int_pct / 100)) * 0.01 + luk * 0.0025
        self.damage_input = inp("damage")
        self.damage_amp = inp("damage_amp")
        self.boss_damage = inp("boss_damage")
        self.normal_damage = inp("normal_damage")
        self.status_effect_damage = status_effect_damage = inp("status_effect_damage")
        self.final_damage = inp("final_damage")
        if sens.get("final_damage_factor") is not None:
            # Sensitivity: a baked-in Final Damage artifact what-if is a factor on the TYPED value inside the additive bucket (``baked_fd_form="typed"``, as Hero / Dawn Warrior)
            self.final_damage = ((1 + self.final_damage / 100) * sens["final_damage_factor"] - 1) * 100
        self.min_damage = inp("min_damage") + sens.get("min_damage_delta", 0.0)      # (+ Spell Control's / Brilliant Enlightenment's level delta, Sensitivity only)
        self.max_damage = inp("max_damage") + sens.get("max_damage_delta", 0.0)      # (+ Brilliant Enlightenment's / Pure Magic's level delta / Athena's Gloves' dependent Max Damage)
        self.crit_rate_input = inp("crit_rate") + sens.get("crit_rate_threshold_extra", 0.0)
        self.crit_rate = self.crit_rate_input + sens.get("crit_rate_delta", 0.0)      # (+ Burning Focus' level delta, Sensitivity only)
        self.crit_damage = inp("crit_damage")
        attack_speed_base = inp("attack_speed")
        def_pen_typed = sens_mod.def_pen_with_dose(inp("def_pen"), sens)
        self.basic_attack_damage = inp("basic_attack_damage") + sens.get("basic_attack_damage_delta", 0.0)
        self.skill_damage = inp("skill_damage") + sens.get("skill_damage_delta", 0.0)      # (+ Pure Magic's level delta, Sensitivity only)
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
        fof_curve = CV["FINAL_ORBITAL_FLAME"]
        self.skill_coefficient_base = (fof_curve.base / 10) * self._factor(basic_lvl, fof_curve.fidx) / 1000

        # ---- level-resolved rows (static part: cooldowns, targets, ticks) ----
        SKILLS = self.skills = {}
        for key, t in D.DAMAGE_SKILLS.items():
            c = CV[t["curve"]]
            hits = t["hits"]
            if hits is None:                         # Towering Inferno's boss flame strikes: N strikes of FOX_TOWERING_STRIKE_HITS hits
                n0, lv, n1 = D.FOX_TOWERING_STRIKES
                hits = (n1 if level >= lv else n0) * D.FOX_TOWERING_STRIKE_HITS
            s = dict(step=c.step, cooldown=t["cooldown"], hits=hits, base=c.base, fidx=c.fidx, mastery=gated(t["mastery"]),
                     mastery_normal=gated(t.get("mastery_normal", {})), costs_action=t["costs_action"], targets=t["targets"],
                     branch=t.get("branch", "both"), cast_row=t.get("cast_row", key), coef_pct=coeff_pct(c.base, c.fidx, True, c.step))
            if "icd" in t:
                s["icd"], s["window"] = self.tier(t["icd"]), t["window"]
            cyg = t.get("cygnus")
            s["cygnus_pct"] = coeff_pct(CV[cyg].base, CV[cyg].fidx, True, CV[cyg].step) if (cyg and unlocked("CALL_OF_CYGNUS")) else 0.0
            SKILLS[key] = s
        self.normal_targets = {k: v["targets"] for k, v in SKILLS.items()}

        # ---- Fires of Creation: the incarnate of each branch (the game summons the Fox against a boss, the Lion otherwise) ----
        fires = unlocked("FIRES_OF_CREATION")
        lion_c, fox_c = CV["FIRES_LION_NORMAL_DAMAGE"], CV["FIRES_FOX_BOSS_DAMAGE"]
        self.lion_normal_damage = coeff_pct(lion_c.base, lion_c.fidx, True, lion_c.step) if fires else 0.0
        self.fox_boss_damage = coeff_pct(fox_c.base, fox_c.fidx, True, fox_c.step) if fires else 0.0
        self.fox_def_pen = float(gated(D.FOX_DEF_PEN)) if fires else 0.0
        lion_basic_target = D.LION_BASIC_TARGET[1] if (fires and level >= D.LION_BASIC_TARGET[0]) else 0

        # ---- timed buffs: uptimes (cast on cooldown from t = 0, duty-cycle averages) ----
        fe, ff, bc, eh = D.FLAME_ELEMENTAL, D.FLASHFIRE, D.BURNING_CONDUIT, D.ELEMENTAL_HARMONY
        fe_dur = fe["duration"] * (fe["duration_mastery"][1] if level >= fe["duration_mastery"][0] else 1.0)
        self.fe_up = fe_up = fight.buff_uptime(fe["cooldown"], fe_dur, True) if unlocked("FLAME_ELEMENTAL") else 0.0
        # Flashfire: the mark lasts 30 s and a recast would TELEPORT to it (and remove it), so it is recast when the mark expires, not on cooldown (period = max(cooldown, duration))
        ff_eff_dur = eff_duration(ff["duration"])
        self.ff_period = ff_period = max(eff_cooldown(ff["cooldown"], True), ff_eff_dur)
        self.ff_up = ff_up = self.timed_uptime(ff_period, ff_eff_dur) if unlocked("FLASHFIRE") else 0.0
        self.bc_up = bc_up = fight.buff_uptime(bc["cooldown"], bc["duration"], True) if unlocked("BURNING_CONDUIT") else 0.0
        eh_up = fight.buff_uptime(eh["cooldown"], eh["duration"], True) if unlocked("ELEMENTAL_HARMONY") else 0.0

        fa, ffa = CV["FLAME_ELEMENTAL_ATTACK"], CV["FLASHFIRE_ATTACK"]
        self.fe_attack_full = fe_attack_full = coeff_pct(fa.base, fa.fidx, True, fa.step) if unlocked("FLAME_ELEMENTAL") else 0.0
        self.ff_attack_full = ff_attack_full = coeff_pct(ffa.base, ffa.fidx, True, ffa.step) if unlocked("FLASHFIRE") else 0.0
        # Greater / Grand / Final Flame Elemental: effects that count for Flame Elemental's uptime
        g = CV["GREATER_FE_DAMAGE"]
        self.gfe_damage_full = (coeff_pct(g.base, g.fidx, True, g.step) + gated(D.GREATER_FE_MASTERY)) if unlocked("GREATER_FLAME_ELEMENTAL") else 0.0
        gr = CV["GRAND_FE_BASIC_ATTACK"]
        self.gfe_basic_full = coeff_pct(gr.base, gr.fidx, True, gr.step) if unlocked("GRAND_FLAME_ELEMENTAL") else 0.0
        self.gfe_skill_full = float(gated(D.GRAND_FE_SKILL_DAMAGE)) if unlocked("GRAND_FLAME_ELEMENTAL") else 0.0
        fdp, fcd = CV["FINAL_FE_DEF_PEN"], CV["FINAL_FE_CRIT_DAMAGE"]
        ffe_on = unlocked("FINAL_FLAME_ELEMENTAL")
        self.ffe_def_pen_full = coeff_pct(fdp.base, fdp.fidx, True, fdp.step) if ffe_on else 0.0
        self.ffe_crit_damage_full = coeff_pct(fcd.base, fcd.fidx, True, fcd.step) if ffe_on else 0.0
        self.ffe_fd_full = float(gated(D.FINAL_FE_FD)) if ffe_on else 0.0
        bcf = CV["BURNING_CONDUIT_FD"]
        self.bc_fd_full = coeff_pct(bcf.base, bcf.fidx, True, bcf.step) if unlocked("BURNING_CONDUIT") else 0.0

        self.gfe_damage_avg = self.gfe_damage_full * fe_up
        self.gfe_basic_avg = self.gfe_basic_full * fe_up
        self.gfe_skill_avg = self.gfe_skill_full * fe_up
        self.damage = self.damage_input + self.gfe_damage_avg          # Greater Flame Elemental's "damage" is the Damage % bucket
        fe_attack_avg, ff_attack_avg = fe_attack_full * fe_up, ff_attack_full * ff_up
        self.attack_bucket_sum = attack_bucket_sum = fe_attack_avg + ff_attack_avg
        self.attack_bucket_avg = attack_bucket_sum + pre.agg_attack_pct
        self.attack_bucket_mult = 1 + self.attack_bucket_avg / 100

        self.crit_rate_bonus = 0.0                                      # (no live Crit Rate source: Burning Focus is a stat-screen passive)
        crit_damage_bonus_live = self.ffe_crit_damage_full * fe_up
        self.crit_damage_bonus = crit_damage_bonus_live
        # Phoenix Run (patch 2026-11-26): +1% Final Damage per second from the battle start, up to 12 stacks (the Lv118 mastery doubles it): fight-average gain of the compounding stacks
        pr, prs = D.CURVES["PHOENIX_RUN_FD"], D.PHOENIX_RUN_STACKS
        pr_stack_pct = (coeff_pct(pr.base, pr.fidx, True, pr.step) * (prs["boost"] if unlocked("PHOENIX_RUN_BOOST") else 1.0)
                        + sens.get("phoenix_run_stack_delta", 0.0))      # (+ its level delta, Sensitivity only)
        self.phoenix_run_avg = fight.ramp_avg_gain_pct(pr_stack_pct, prs["max_stacks"], prs["interval"]) if unlocked("PHOENIX_RUN") else 0.0
        self.final_damage_extra = (self.ffe_fd_full * fe_up + self.bc_fd_full * bc_up + self.phoenix_run_avg
                                   + sens.get("final_damage_delta", 0.0))      # (+ Liberated Magic's / Wild Blaze's level delta, Sensitivity only)

        # ---- Defense Penetration per branch: typed (+ Final Flame Elemental's, time-averaged) in both, + the Flame Fox's in the boss / PvP branch ----
        self.def_pen_n = def_pen_n = combine_def_pen(def_pen_typed, self.ffe_def_pen_full * fe_up)
        self.def_pen_b = combine_def_pen(def_pen_n, self.fox_def_pen)
        self.def_pen_c = (1 - normal_weight) * self.def_pen_b + normal_weight * self.def_pen_n          # the companion host has ONE value
        self.def_pen_eff = self.def_pen_b

        # ---- the monster-damage-taken bucket: Cinder Maelstrom's weaken (+9 % for 14 s from Lv98, joins both branches) ----
        cw = D.CINDER_WEAKEN
        self.weaken_avg = (cw["pct"] * fight.buff_uptime(SKILLS["CINDER_MAELSTROM"]["cooldown"], cw["duration"], True)
                           if (unlocked("CINDER_MAELSTROM") and level >= cw["level"]) else 0.0)
        self.monster_dmg_bonus = self.weaken_avg

        # ---- Elemental Harmony (Attack Speed buff, duty-cycle averaged; not level-scaling) ----
        self.as_bonus = as_bonus = eh["attack_speed"] * eh_up
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
        self.crit_damage_bonus += sens.get("crit_damage_delta", 0.0)              # (Sensitivity: Burning Focus' level delta / Book of Ancient's dependent Crit Damage while Crit Rate is swept)
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

        # ---- Final Orbital Flame (basic attack): its own damage chain + boss chain, hits, targets per branch ----
        fof_mastery = gated(D.FOF_MASTERY)
        self.fof_mastery_boss = fof_mastery_boss = gated(D.FOF_BOSS_MASTERY)
        fof_pct = self.skill_coefficient_base * (1 + fof_mastery / 100)
        self.fof_targets_boss = D.FOF_BASE_TARGETS + basic_attack_target_increase
        self.fof_targets_normal = D.FOF_BASE_TARGETS + basic_attack_target_increase + lion_basic_target
        h0, hl, h1 = D.FOF_HITS
        fof_hits = h1 if level >= hl else h0
        fof_hit_b, fof_hit_n = self.hit_damage(fof_pct, True, 0.0, "boss"), self.hit_damage(fof_pct, True, 0.0, "normal")

        for key, s in SKILLS.items():
            s["is_basic"] = False
        # per-row hit damage (boss, normal)
        hits_of = {key: self.skill_hit(s) for key, s in SKILLS.items()}

        # ---- Status/KO engine pass 2: the damage skills' casts (weight of one cast = its boss damage before any timing factor) ----
        if status_on:
            def percast(key):
                if not unlocked(key):
                    return 0.0
                sk = SKILLS[key]
                hits = sk["hits"] * (fight_mod.ticks(fight.capped_window(sk["window"]), sk["icd"]) if sk.get("icd") else 1)
                return hits * hits_of[key][0] * self.branch_multipliers(sk.get("mastery_boss", 0), 0, sk["targets"])[0]
            # the basic attack a cast replaces (nothing replaced below level 100: there is no basic attack to lose)
            b_fof = self.branch_multipliers(fof_mastery_boss, 0, self.fof_targets_boss)[0]
            c_slot = (fof_hits * fof_hit_b * b_fof) if unlocked("FINAL_ORBITAL_FLAME") else 0.0
            groups = status_mod.build_groups(D, unlocked, SKILLS, percast, fight.capped_window,
                                             lambda cast: eff_cooldown(SKILLS[cast]["cooldown"], SKILLS[cast]["costs_action"]),
                                             # the stunning skills are cast on cooldown from t = 0 (fixed schedule; Flame Tempest also below Lv90, where it does not stun yet: the stun entry
                                             # is simply off, and keeping the schedule fixed at every level avoids a spurious DPS drop at Lv90, Dawn Warrior / Hero convention)
                                             stun_keys={e["key"] for e in D.PLAYER_STUN})
            E_ENGINE = status_mod.solve_groups(self, D, eng_host, groups, c_slot, ENGINE_N, sens)
            E_FS = E_ENGINE["fs"]
        self.e_engine = E_ENGINE

        # ---- Cast rate (subtracted from the basic attack) ----
        eff_cd_of = {}
        for key in D.COST_ACTION_ORDER:
            if key in SKILLS:
                eff_cd_of[key] = eff_cooldown(SKILLS[key]["cooldown"], True)
            elif key == "FLASHFIRE":
                eff_cd_of[key] = ff_period
            else:
                eff_cd_of[key] = eff_cooldown(D.BUFF_COOLDOWNS[key], True)

        def cast_count(k):
            if k in ENGINE_N:
                return ENGINE_N[k]
            return fight.exact_casts(eff_cd_of[k]) if k in D.BUFF_ROW_KEYS else fight.non_buff_casts(eff_cd_of[k])

        if fixed_duration_active:
            cast_rate = sum(cast_count(k) for k in D.COST_ACTION_ORDER if unlocked(k)) / fight_duration
        else:
            cast_rate = sum(1 / eff_cd_of[k] for k in D.COST_ACTION_ORDER if unlocked(k))
        self.cast_rate = cast_rate
        self.fof_per_second = fof_per_second = max(0, actions_per_second - cast_rate)

        # ---- Final Orbital Flame (basic attack) DPS ----
        fof_on = unlocked("FINAL_ORBITAL_FLAME")
        fof_dps = (self.blend_row("FINAL_ORBITAL_FLAME", fof_hits * fof_hit_b * fof_per_second, fof_hits * fof_hit_n * fof_per_second, fof_mastery_boss,
                                  self.fof_targets_normal) if fof_on else 0.0)
        self.fof_dps = fof_dps

        # ---- Orbital Explosion: while the fire energy is up each basic attack rolls per enemy hit, one explosion per ICD ----
        oe = D.ORBITAL_EXPLOSION
        oc = CV["ORBITAL_EXPLOSION"]
        oe_pct = coeff_pct(oc.base, oc.fidx, True, oc.step) * (1 + gated(oe["mastery"]) / 100)
        cyg = CV[D.ORBITAL_EXPLOSION_CYGNUS]
        oe_cyg = coeff_pct(cyg.base, cyg.fidx, True, cyg.step) if unlocked("CALL_OF_CYGNUS") else 0.0
        oe_hit_b, oe_hit_n = self.hit_damage(oe_pct, False, oe_cyg, "boss"), self.hit_damage(oe_pct, False, oe_cyg, "normal")
        self.oe_uptime = oe_up = self.timed_uptime(oe["period"], oe["window"])
        chance = oe["chance"] / 100
        n_basic_normal = fight.cap_targets(self.fof_targets_normal)
        self.oe_attempts = {"boss": fof_per_second * dmg.q_roll(chance, 1), "normal": fof_per_second * dmg.q_roll(chance, n_basic_normal)}
        self.oe_rate = {br: oe_up * x / (1 + oe["icd"] * x) for br, x in self.oe_attempts.items()}      # explosions per second averaged over the fight
        oe_on = unlocked("ORBITAL_EXPLOSION") and fof_on
        oe_dps = (self.blend_row("ORBITAL_EXPLOSION", oe["hits"] * self.oe_rate["boss"] * oe_hit_b, oe["hits"] * self.oe_rate["normal"] * oe_hit_n, 0, oe["targets"])
                  if oe_on else 0.0)
        self.oe_dps = oe_dps

        skill_dps = {}
        for key, s in SKILLS.items():
            if not unlocked(key):
                skill_dps[key] = 0.0
                continue
            hd_b, hd_n = hits_of[key]
            eff_cd = eff_cooldown(s["cooldown"], s["costs_action"])
            icd, window = s.get("icd"), s.get("window")
            T = fight_duration
            if status_on and key in ENGINE_N:
                per_cast = s["hits"] * (fight_mod.ticks(fight.capped_window(window), icd) if icd else 1)
                rate = per_cast * (E_FS[key] if key in D.STATUS_FS_KEYS else ENGINE_N[key]) / T
            elif fixed_duration_active:
                rate = fight.non_buff_total_hits(eff_cd, s["hits"], icd, window if icd else None) / T
            else:
                hits = s["hits"] * (fight_mod.ticks(fight.capped_window(window), icd) if icd else 1)
                rate = hits / eff_cd
            boss_unit = 0.0 if s["branch"] == "normal" else rate * hd_b
            normal_unit = 0.0 if s["branch"] == "boss" else rate * hd_n
            skill_dps[key] = self.blend_row(key, boss_unit, normal_unit, 0, s["targets"], s["mastery_normal"])
        self.skill_dps = skill_dps
        self.player_dps = fof_dps + oe_dps + sum(skill_dps.values())

        # ---- player's boss-only / normal-only totals (the companion's damage-share weights) ----
        row_dps = [("FINAL_ORBITAL_FLAME", fof_dps), ("ORBITAL_EXPLOSION", oe_dps)] + list(skill_dps.items())
        self.pb_total, self.pn_total, self.pu_total = self.ledger.split_totals(row_dps, D.STATUS_UNIFORM_ROWS)

        # ---- companion: src/companion_python_model.py fed with this model's own pipeline numbers ----
        self.begin_companion(summon_time_inc)
        if (choice != "None" and c_level >= 1) or pl_on or sens.get("want_comp_host"):
            basic_b, basic_n = self.ledger.pairs.get("FINAL_ORBITAL_FLAME", (0.0, 0.0))[:2]
            fe_full, ff_full = fe_attack_full, ff_attack_full
            comp_host = dict(comp_mod.host_common(self, pre, eff, basic_b, basic_n),
                unit=self.hit_damage(100.0, True, 0.0, "comp") / 100, sd=self.skill_damage + self.art_skill_damage + self.gfe_skill_avg, aps=actions_per_second,
                avgbuff=self.attack_bucket_mult, attack_bucket_avg=self.attack_bucket_avg, agg_damage_avg=self.art_joint_damage,
                avgbuff_snap=lambda charm, extra: 1 + (fe_full + ff_full + pre.agg_attack_pct - pre.charm_avg + charm + extra) / 100,
                boss_pct=self.boss_damage + self.art_boss_damage + self.monster_dmg_bonus + self.fox_boss_damage,
                norm_pct=self.normal_damage + self.art_normal_damage + self.monster_dmg_bonus + self.lion_normal_damage,
                cr_total=self.crit_rate + self.crit_rate_bonus + self.art_crit_rate, cd_total=self.crit_damage + self.crit_damage_bonus,
                def_pen=self.def_pen_c, taken_bucket=self.art_joint_damage, pst=pst)
            comp_host["bad"] = comp_host["bad"] + self.gfe_basic_avg          # Grand Flame Elemental's Basic Attack Damage (time-averaged) belongs to the basic-attack bucket
            self.comp_host = comp_host
            self.run_companion(comp_host, choice, c_level, summon_time_inc, pl_on)
        self.total_dps = self.player_dps + self.companion_dps

    # ------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _factor(level, idx):
        from ..common import factors
        return factors.get_factor(level, idx)

    def row_dps(self, key):
        if key == "FINAL_ORBITAL_FLAME":
            return self.fof_dps
        if key == "ORBITAL_EXPLOSION":
            return self.oe_dps
        return self.skill_dps.get(key, 0.0)

    def derived_extra(self):
        return dict(
            basic_attacks_per_second=self.fof_per_second, avg_buff_mult=self.attack_bucket_mult, as_bonus=self.as_bonus,
            attack_bucket_mult=self.attack_bucket_mult, attack_bucket_sum=self.attack_bucket_sum,
            skill_coefficient_base=self.skill_coefficient_base, buff_cast_startup_time=self.buff_cast_startup_time,
            crit_rate_bonus=self.crit_rate_bonus, crit_damage_bonus=self.crit_damage_bonus, final_damage_extra=self.final_damage_extra,
            monster_dmg_bonus=self.monster_dmg_bonus, def_pen_effective=self.def_pen_eff, def_pen_boss=self.def_pen_b, def_pen_normal=self.def_pen_n,
            flame_elemental_uptime=self.fe_up, flashfire_uptime=self.ff_up, burning_conduit_uptime=self.bc_up, flashfire_period=self.ff_period,
            flame_elemental_attack=self.fe_attack_full, flashfire_attack=self.ff_attack_full,
            greater_fe_damage_avg=self.gfe_damage_avg, grand_fe_basic_avg=self.gfe_basic_avg, grand_fe_skill_avg=self.gfe_skill_avg,
            lion_normal_damage=self.lion_normal_damage, fox_boss_damage=self.fox_boss_damage, fox_def_pen=self.fox_def_pen,
            orbital_explosion_uptime=self.oe_uptime, orbital_explosion_rate_boss=self.oe_rate["boss"], orbital_explosion_rate_normal=self.oe_rate["normal"],
            basic_attack_targets_normal=self.fof_targets_normal,
        )


fields, schema, defaults = classapi.make(CLASS_ID, CLASS_NAME, STAT_IDENTITY, _MAIN_STAT_FIELDS, D)
artifact_schema = classapi.artifact_schema


def model(inputs):
    """The evaluated model object (everything ``compute`` reports plus the internals engine/sensitivity.py reads: ``comp_host``, ``e1`` / ``e_engine`` (the timeline strip),
    ``art_effects`` ...).  Same input dict as ``compute``; honours ``inputs["_sens"]`` (engine/common/sens.py)."""
    return _Model(inputs)


def compute(inputs):
    """DPS of one Blaze Wizard setup.  ``inputs``: dict (see module docstring / ``schema()``); returns a JSON-friendly dict:

    total_dps / player_dps / boss_dps / normal_dps / player_boss_dps / player_normal_dps, skills (per damage row: key, name, dps, share, boss_dps, normal_dps, unlocked),
    companion (None or dps/boss/normal/share + model details; choice "None" = the player's stun uplift only), engine_on (Status/KO timeline engine), engine (its cast
    counts and timing factors), derived (ATTACK, STAT_DAMAGE, actions/s, buff uptimes and values, computed Inputs rows ...).
    """
    return _Model(inputs).result()
