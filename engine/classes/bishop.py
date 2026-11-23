"""Bishop: the DPS model of ``src/verify_bishop_workbook.py`` as a function of a plain inputs dict.

    from engine.classes import bishop
    result = bishop.compute(bishop.defaults("World Boss"))

``compute(inputs)`` is bit-identical to the verify script (same operations in the same order); the verify script stays the independent
reference, ``tests/golden/test_bishop.py`` compares the two (with no artifact equipped).  Artifact equip effects (``inputs["artifacts"]``, up to 4
slots) are ported in ``engine/artifacts.py`` (shared with the other classes; the Artifacts sheet of the builders is identical) and wired the way
``src/build_bishop_workbook.py`` wires them; the verify script does not model artifacts, so ``tests/golden/test_bishop_artifacts.py`` checks them
against the workbook itself (``tests/golden/bishop_artifacts_golden.json``, evaluated with ``formulas``).

Inputs dict: the workbook's Inputs keys already resolved for the chosen content type (see ``schema()``), plus ``companion_level`` (the
level of the chosen companion, 0 = not unlocked).  A missing / ``None`` value reads as 0, exactly like a blank workbook cell.

Bishop specifics (all in the verify script):

* INT-main / LUK-sub.  Defense is a stat: ``total_defense = Defense x (1 + (Defense % + Divine Protection's averaged bonus) / 100)``; Invincible (Lv35+)
  converts ``10 x factor22(level) / 1000`` percent of it into INT before the INT % multiplier (STAT_DAMAGE), and PvP assumes the opponent has the same
  total Defense (``monster_defense``).
* Big Bang is the basic attack (5 hits, 6 from Lv136; target count ``6 + increase``).  Angel Ray (stuns 1 s from Lv103, on cooldown from the start) is
  the player's own stun, part of the Status Effect Damage / KO timeline and - in Breakthrough / Hero Dungeon - lengthening the boss phase, so from Lv103
  a "companion" result exists even with no companion chosen (choice "None": only the stun uplift).  Angel Ray - Boss Monster Damage (Lv122) fires on every
  Angel Ray cast, boss branch only.  Genesis (10 targets), Bahamut (30 s summon, 4 s ticks, 3 targets / 6 from Lv130).
* Magic Guard / Heal / Bless / Holy Magic Shell are Attack% buffs (one additive bucket), Advanced Blessing / Infinity Final Damage buffs (own factors;
  Infinity = time-average of its ramp x64/45; in the timeline strip Advanced Blessing carries Infinity's steady-state average, the mean-field cross term).
  All six are engine-timed.  Nimble Feet, Holy Fountain, Holy Symbol and Divine Protection stay duty-cycle averages.
* Triumph Feather: bespoke two-stage chance proc (per attack per enemy hit, 1 s ICD on stage 2), uniformly spread, with Maple Hero's share as an extra
  Final Damage factor.  Holy Symbol: Normal Monster Damage (averaged) + flat Damage Boost (Lv90).  Holy Fountain: Boss Monster Damage (averaged).
* Damage% is ONE additive bucket (Damage input + Holy Symbol's Damage Boost); the companion host reads it as ``agg_damage_avg`` and ``taken_bucket``.
* Artifacts: Hexagon Necklace's average and the enemy-damage-taken artifacts (Peach Tree Herb Pouch, Silver Pendant) join that SAME additive Damage%
  bucket (so the companion's Hexagon snapshot ratio and damage-taken debuff read the joint bucket incl. them); Old Music Box / Secret Map / Reindeer's
  Spear / Alliance Badge / Bottle of Emotion / Charm's average join the Attack% bucket of Magic Guard / Heal / Bless / Holy Magic Shell (strip ``A0``);
  the Final Damage artifacts multiply on top of the Final Damage input; Soul Contract's cooldown decrease reaches every cooldown through
  ``Fight.cd_extra_pct``; Horn Flute's uptime comes from the stub-host run (candidate-0 timing, which already carries Angel Ray's stun).
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
from ..data import bishop as D
from .. import artifacts as art_mod
import status_timeline as stl  # noqa: E402  (src/status_timeline.py through the shim)

CLASS_ID = "bishop"
CLASS_NAME = "Bishop"
STAT_IDENTITY = {"main": "INT", "sub": "LUK"}

_MAIN_STAT_FIELDS = [
    schema_mod.field("flat_int", "Flat INT", "Main stats", "float", "flat", 0),
    schema_mod.field("int_pct", "INT %", "Main stats", "float", "%", 0),
    schema_mod.field("luk", "LUK", "Main stats", "float", "flat", 0),
    schema_mod.field("defense_pct", "Defense %", "Offense", "float", "%", 0,
                     help="Invincible converts total Defense (incl. this % and Divine Protection) into INT at a level-scaling rate."),
]


class _Model(model_mod.ModelBase):
    DATA = D

    # ------------------------------------------------------------------------------------------------------------------
    def buff_pct(self, key):
        """Calc!F of a buff row: the factor-curve value (Infinity: x64/45, the time-average of its ramp) + the row's own mastery (percentage points)."""
        b = self.buffs[key]
        pct = self.coeff_pct(b["base"], b["fidx"], b["scales"], b["job_step"])
        if "ramp_mult" in b:
            pct *= b["ramp_mult"]
        return pct + b.get("mastery", 0)

    # ---- per-hit pipeline ----
    def hit_damage(self, coeff_pct_val, is_basic, s, key):
        effective_coeff = coeff_pct_val * (1 + s.get("mastery", 0) / 100)   # a skill mastery MULTIPLIES the skill's damage (game-confirmed 2026-11-03)
        base_damage = self.attack * (effective_coeff / 100)
        dmg_reduction = dmg.defense_reduction(self.monster_defense, self.def_pen)
        elem_amp = self.element_amp_pct if self.unlocked("ELEMENT_AMPLIFICATION") else 0.0
        blood_divine = self.blood_divine_pct if self.unlocked("BLOOD_OF_THE_DIVINE") else 0.0
        arcane = self.arcane_aim_pct if self.unlocked("ARCANE_AIM") else 0.0
        triumph_maple = self.maple_hero_bishop_pct if (key == "TRIUMPH_FEATHER" and self.unlocked("MAPLE_HERO_BISHOP")) else 0.0
        final_mult = (
            (1 + self.final_damage / 100) * (1 + self.art_final_damage / 100) * (1 + elem_amp / 100) * (1 + blood_divine / 100)
            * (1 + triumph_maple / 100) * (1 + arcane / 100) ** 5
        )
        source_pct = (self.basic_attack_damage + self.art_basic_attack_damage) if is_basic else (self.skill_damage + self.art_skill_damage)
        extra_mult = self.avg_buff_mult
        # Boss/Normal Monster Damage% is deliberately NOT applied here - it is blended per branch in blend_branches
        base_hit = (
            base_damage * (1 + self.stat_damage / 100) * (1 + (self.damage + self.damage_bonus + self.art_damage + self.art_enemy_taken) / 100)
            * (1 + self.damage_amp / 100) * dmg_reduction * final_mult * (1 + source_pct / 100) * extra_mult
        )
        return dmg.expected_hit(base_hit, self.min_damage, self.max_damage, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate,
                                self.crit_damage + self.crit_damage_bonus + self.art_crit_damage)

    # ---- targets and branch blending ----
    def enemies_hit(self, key):
        """Enemies one attack of this skill hits: 1 vs boss/PvP, the skill's own target count (capped by Max Enemies In Range) vs normal."""
        if self.monster_type == "pvp":
            return 1
        targets = 6 + self.basic_attack_target_increase if key == "BIG_BANG" else self.normal_targets.get(key, 1)
        return self.fight.cap_targets(targets)

    def branch_multipliers(self, key, s):
        """(boss-branch, normal-branch) multiplier: Boss/Normal Monster Damage% and target count (PvP: single target, neither bonus)."""
        # outside the Boss/Normal Damage% buckets the artifacts add boss-only / normal-only multipliers (Reindeer's Spear, Contract of Darkness,
        # branch Final Damage), applied even in PvP (extra_boss / extra_norm are exactly 1.0 with no such artifact equipped)
        if self.monster_type == "pvp":
            return 1.0 * self.extra_boss, 1.0 * self.extra_norm
        boss_term = self.boss_damage + s.get("mastery_boss", 0) + self.monster_dmg_bonus + self.art_boss_damage
        normal_term = self.normal_damage + s.get("mastery_normal", 0) + self.normal_dmg_bonus + self.art_normal_damage
        return (1 + boss_term / 100) * self.extra_boss, (1 + normal_term / 100) * self.enemies_hit(key) * self.extra_norm

    def blend_branches(self, key, s, boss_unit, normal_unit=None):
        """Time-weighted DPS of one skill: (1-w)*boss_unit*boss_branch + w*normal_unit*normal_branch (timing factor folded into each branch)."""
        explicit = normal_unit is not None
        if normal_unit is None:
            normal_unit = boss_unit
        b, n = self.branch_multipliers(key, s)
        fb, fn = self.timing_factors(key)
        b, n = b * fb, n * fn
        return self.ledger.blend(key, boss_unit, normal_unit, b, n, explicit)

    # ------------------------------------------------------------------------------------------------------------------
    def _build(self, inp):
        # (the PvP monster defense is the character's own TOTAL defense, known only below: Content is built with 0 and corrected afterwards)
        ct = self.read_content(inp, defense=0)
        level = self.level
        sens = self.sens
        content_type = self.content_type
        monster_type = self.monster_type
        w = self.normal_weight
        fight_duration = self.fight_duration
        fixed_duration_active = self.fixed_duration_active
        unlocked = self.unlocked
        gated = lambda pairs: factors.level_gated_sum(level, pairs)  # noqa: E731
        flat_attack, attack_pct = inp("flat_attack"), inp("attack_pct")
        self.attack = dmg.attack_value(flat_attack, attack_pct)
        if sens.get("mainstat_attack_delta"):      # Sensitivity: the main/sub stat's flat-Attack channel (bug 7), applied before ATTACK%
            self.attack += sens["mainstat_attack_delta"] * (1 + attack_pct / 100)
        flat_int, int_pct, luk = inp("flat_int"), inp("int_pct"), inp("luk")
        defense, defense_pct = inp("defense"), inp("defense_pct")
        self.damage = inp("damage")
        self.damage_amp = inp("damage_amp")
        self.boss_damage = inp("boss_damage")
        self.normal_damage = inp("normal_damage")
        self.status_effect_damage = status_effect_damage = inp("status_effect_damage")
        self.final_damage = inp("final_damage") + sens.get("final_damage_delta", 0.0)     # (+ a passive's level delta, Sensitivity only; none in this kit)
        self.min_damage = inp("min_damage") + sens.get("min_damage_delta", 0.0)      # (+ Spell Mastery's level delta, Sensitivity only)
        self.max_damage = inp("max_damage") + sens.get("max_damage_delta", 0.0)      # (+ Athena's Gloves' dependent Max Damage, Sensitivity only)
        # Ring of Cycles' threshold reads the Inputs crit rate (+ Book of Ancient's direct what-if) WITHOUT the Magic Critical / High Wisdom level delta (the block's
        # ``roc_threshold_cr_block`` has no passive delta), the rows' own crit rate carries it
        self.crit_rate_input = inp("crit_rate") + sens.get("crit_rate_threshold_extra", 0.0)
        self.crit_rate = self.crit_rate_input + sens.get("crit_rate_delta", 0.0)      # (+ Book of Ancient's direct Crit Rate what-if / a passive's level delta, Sensitivity only)
        self.crit_damage = inp("crit_damage") + sens.get("crit_damage_delta", 0.0)    # (+ Magic Critical (Crit Damage)'s level delta / Book of Ancient's dependent Crit Damage while Crit Rate is swept)
        attack_speed_base = inp("attack_speed")
        self.def_pen = sens_mod.def_pen_with_dose(inp("def_pen"), sens)   # Sensitivity: Reindeer's Spear equip toggle folds one signed dose of its base Def Pen into Inputs' value (the block's rows read it too)
        self.basic_attack_damage = inp("basic_attack_damage") + sens.get("basic_attack_damage_delta", 0.0)   # (+ a passive's level delta, Sensitivity only; none in this kit)
        self.skill_damage = inp("skill_damage") + sens.get("skill_damage_delta", 0.0)      # (+ a passive's level delta, Sensitivity only; none in this kit)
        self.basic_attack_target_increase = inp("basic_attack_target_increase")
        summon_time_inc = inp("companion_summon_time_increase_pct")
        self.pvp_len = pvp_len = inp("pvp_fight_length") or content_mod.DEFAULT_PVP_FIGHT_LENGTH
        fight = self.fight = fight_mod.Fight(ct, pvp_len, inp("skill_cooldown_decrease"),
                                             inp("buff_duration_increase_pct") + sens.get("bdi_extra", 0.0),     # (+ Shamaness Marble what-if, Sensitivity only)
                                             inp("max_enemies_hit"))
        self.ledger = blend_mod.BranchLedger(w)

        # ---- artifacts (equip effects): slots, the early quantities (Attack% bucket / Hexagon / Charm) and Soul Contract's cooldown decrease ----
        self.eq = eq = sens["eq"] if "eq" in sens else art_mod.resolve_slots(inp.raw("artifacts"))   # (Sensitivity: an equip-toggle what-if may exceed 4 slots)
        actx = self.art_ctx = art_mod.Ctx(self.content_type, monster_type, fight_duration, pvp_len, fixed_duration_active,
                                          crit_rate=self.crit_rate_input, attack_speed=attack_speed_base)
        pre = self.art_pre = art_mod.Pre(eq, actx)
        # Arwen's Glass Shoes: the companion's effective Summoning Time Increase % = the Inputs value + the artifact (every use below)
        summon_time_inc += art_mod.summon_time_inc_pct(eq)
        fight.cd_extra_pct = art_mod.soul_contract_pct(eq, self.content_type)
        # live artifact terms of the damage pipeline; zero / neutral until the full effects are known (after the buff-casting startup delay)
        self.art_final_damage = self.art_damage = self.art_enemy_taken = self.art_skill_damage = self.art_basic_attack_damage = 0.0
        self.art_boss_damage = self.art_normal_damage = 0.0
        self.crit_rate_bonus = self.art_crit_rate = self.art_crit_damage = 0.0     # crit_rate_bonus: a live crit-rate SKILL source (none in this kit); art_crit_rate: the artifact bucket
        self.extra_boss = self.extra_norm = 1.0
        self.ph_b = self.ph_n = 1.0
        eff_cooldown = fight.eff_cooldown
        eff_duration = fight.eff_duration

        basic_lvl = self.sl.input_level(4)
        self.skill_coefficient_base = D.BIG_BANG_BASE * factors.get_factor(basic_lvl, 21) / 1000

        # ---- Big Bang (basic attack) and the level-resolved damage rows ----
        big_bang_mastery = gated(D.BIG_BANG_MASTERY)
        big_bang_boss_mastery = gated(D.BIG_BANG_BOSS_MASTERY)
        big_bang_hits = self.big_bang_hits = self.tier(D.BIG_BANG_HITS)
        SKILLS = self.skills = {}
        self.normal_targets = {}
        for key, t in D.SKILL_TEMPLATES.items():
            s = dict(job_step=t["job_step"], cooldown=self.tier(t["cooldown"]), hits=t["hits"], base=t["base"], fidx=t["fidx"], scales=True,
                     mastery=gated(t["mastery"]), mastery_boss=0, mastery_normal=0, costs_action=t["costs_action"],
                     targets=self.tier(t["targets"]))
            if "icd" in t:
                s["icd"] = t["icd"]
            if "window" in t:
                s["window"] = t["window"]
            SKILLS[key] = s
            self.normal_targets[key] = s["targets"]
        BUFFS = self.buffs = {}
        for key, t in D.BUFFS.items():
            b = dict(t)
            b["cooldown"], b["duration"] = self.tier(t["cooldown"]), self.tier(t["duration"])
            if "mastery" in t:
                b["mastery"] = gated(t["mastery"])
            BUFFS[key] = b

        # ---- passives / always-on terms ----
        self.buff_mastery_pct = self.passive_pct("BUFF_MASTERY")
        self.arcane_aim_pct = self.passive_pct("ARCANE_AIM")
        self.element_amp_pct = self.passive_pct("ELEMENT_AMPLIFICATION")
        mp_eater_as_pct = self.passive_pct("MP_EATER_MP_BOOST")
        self.blood_divine_pct = self.passive_pct("BLOOD_OF_THE_DIVINE")
        self.maple_hero_bishop_pct = self.passive_pct("MAPLE_HERO_BISHOP")
        holy_symbol_pct = self.passive_pct("HOLY_SYMBOL")
        holy_symbol_mastery_pct = gated(D.HOLY_SYMBOL_MASTERY) if unlocked("HOLY_SYMBOL") else 0.0
        holy_symbol_duration = self.tier(D.HOLY_SYMBOL_DURATION)

        # Divine Protection: auto-triggering Defense buff, duty-cycle-averaged (fixed-duration exact branch like any buff row)
        dp = D.DIVINE_PROTECTION
        divine_protection_pct = self.coeff_pct(dp["base"], dp["fidx"], True, dp["job_step"]) if unlocked("DIVINE_PROTECTION") else 0.0
        if unlocked("DIVINE_PROTECTION"):
            dp_uptime = fight.buff_uptime(dp["cooldown"], dp["duration"], False)
            divine_protection_bonus = divine_protection_pct * dp_uptime
        else:
            divine_protection_bonus = 0.0
        self.divine_protection_bonus = divine_protection_bonus

        self.total_defense = total_defense = defense * (1 + (defense_pct + divine_protection_bonus) / 100)
        inv = D.INVINCIBLE
        self.invincible_conversion_rate = invincible_conversion_rate = inv["base"] * factors.get_factor(level, inv["fidx"]) / 1000
        self.invincible_int_bonus = invincible_int_bonus = (
            invincible_conversion_rate / 100 * total_defense if level >= inv["level"] else 0.0)
        self.stat_damage = ((flat_int + invincible_int_bonus) * (1 + int_pct / 100)) * 0.01 + luk * 0.0025
        # (Sensitivity: a Defense block keeps the PvP opponent's Defense at the main sheet's value - the workbook block's ``ib("monster_defense")`` is the baseline Inputs cell)
        self.monster_defense = ct.monster_defense = sens.get("monster_defense", content_mod.compute_monster_defense(content_type, ct.chapter, ct.stage, total_defense))

        # Holy Fountain - Boss Monster Damage: flat, duty-cycle averaged off Holy Fountain's own cooldown (steady state only, no exact branch)
        hf = D.HOLY_FOUNTAIN
        if level >= hf["level"]:
            hf_eff_cd = eff_cooldown(hf["cooldown"], True)
            if monster_type == "pvp":
                hf_uptime = min(eff_duration(hf["duration"]), pvp_len) / pvp_len
            else:
                hf_uptime = min(1.0, eff_duration(hf["duration"]) / hf_eff_cd)
            self.monster_dmg_bonus = hf["pct"] * hf_uptime
        else:
            self.monster_dmg_bonus = 0.0

        # Holy Symbol's own base effect (Normal Monster Damage only), a real buff row: exact fixed-duration uptime branch
        if unlocked("HOLY_SYMBOL"):
            hsym_uptime = fight.buff_uptime(D.HOLY_SYMBOL_COOLDOWN, holy_symbol_duration, False)
            self.normal_dmg_bonus = holy_symbol_pct * hsym_uptime
        else:
            self.normal_dmg_bonus = 0.0

        # Holy Symbol's Mastery Lv.90 "Damage Boost" - solo-always-true
        self.damage_bonus = holy_symbol_mastery_pct
        # Blood of the Divine: assumed 100% HP -> +20% Crit Damage (4x its own Final-Damage value)
        self.crit_damage_bonus = D.BLOOD_OF_THE_DIVINE_CRIT_FACTOR * self.blood_divine_pct

        # MP Eater + the flat Lv134 Attack Speed, plus Nimble Feet (duty-cycle averaged; Attack Speed combines by diminishing returns)
        nf = D.NIMBLE_FEET
        nimble_feet_pct = self.coeff_pct(nf["base"], nf["fidx"], nf["scales"], nf["job_step"])
        nimble_feet_eff_cd = eff_cooldown(nf["cooldown"], True)
        nimble_feet_uptime = fight.buff_uptime(nf["cooldown"], nf["duration"], True)
        nimble_feet_avg = nimble_feet_pct * nimble_feet_uptime if unlocked("NIMBLE_FEET") else 0.0
        as_level, as_value = D.FLAT_AS_BONUS
        self.as_bonus = as_bonus = (((mp_eater_as_pct + sens.get("as_bonus_extra", 0.0)) if unlocked("MP_EATER_MP_BOOST") else 0.0)    # (+ Magic Acceleration's level delta, Sensitivity only: counted while MP Eater is unlocked)
                                    + (as_value if level >= as_level else 0) + nimble_feet_avg)
        self.actions_per_second = actions_per_second = dmg.actions_per_second(attack_speed_base + sens.get("attack_speed_extra", 0.0), as_bonus)   # (+ Athena's Gloves what-if, Sensitivity only)

        # ---- Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`) ----
        choice, c_level = comp_mod.read_choice(inp)
        self.companion_choice, self.companion_level = choice, c_level
        # The player's own stunning skill (game table): Angel Ray stuns for 1 s, cast on cooldown from the start
        player_stun = D.PLAYER_STUN
        pl_on = any(unlocked(e["key"]) and level >= e["min_level"] for e in player_stun)
        stun_info = comp_mod.stun_probe(ct, fight, pvp_len, choice, c_level, summon_time_inc)
        hasstun = bool(stun_info and stun_info.get("hasstun")) or pl_on
        ko = content_mod.ko_windows(fight_duration)
        self.status_on = status_on = fixed_duration_active and w == 0 and (content_type in ko or hasstun)
        n_startup = (sum(1 for _k, b in BUFFS.items() if b["costs_action"] and unlocked(_k)) + (1 if unlocked("NIMBLE_FEET") else 0))
        t0_pl = 0.0 if status_on else ((n_startup / actions_per_second) if fixed_duration_active else 0.0)
        self.pst = pst = [dict(id=e["id"], typ=e["typ"], cd=eff_cooldown(e["cd"], True), dur=e["dur"], p=e["p"],
                               on=unlocked(e["key"]) and level >= e["min_level"], t0=t0_pl, tick=e["tick"], win=e["win"]) for e in player_stun]
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
            # (the verify script raises KeyError here when no companion stun exists and Angel Ray is locked, i.e. level < 103 in a KO content:
            # the companion model's early return carries no stun_vector.  The engine reads that as "no companion stun" instead of crashing.)
            comp_stun = stun_info["stun_vector"](stl.NB_MAX) if "stun_vector" in stun_info else [0.0] * stl.NB_MAX
            stun_vec = [min(1.0, a + b) for a, b in zip(comp_stun, stl.pl_stun_vector([dict(e, t0=0.0) for e in pst], fight_duration, stl.NB_MAX))]
            inf_dur, inf_cd = eff_duration(BUFFS["INFINITY"]["duration"]), eff_cooldown(BUFFS["INFINITY"]["cooldown"], True)
            # Advanced Blessing's strip effect carries Infinity's steady-state average (mean-field cross term, see fd_cross_scale in the builder)
            cross = 1 + (self.buff_pct("INFINITY") * min(1.0, inf_dur / inf_cd) / 100 if unlocked("INFINITY") else 0.0)
            buffs = []
            for bid, key, kind in D.STATUS_BUFFS:
                b = BUFFS[key]
                dur, cd = eff_duration(b["duration"]), eff_cooldown(b["cooldown"], b["costs_action"])
                bd = dict(id=bid, kind=kind, F=self.buff_pct(key), dur=dur, cd=cd, on=unlocked(key))
                if bid == "AB":
                    bd.update(F=self.buff_pct(key) * cross, dur=min(dur, cd), **D.ADVANCED_BLESSING_RAMP)
                elif kind == "ramp":
                    bd.update(D.INFINITY_RAMP)
                buffs.append(bd)
            eng_host = dict(T=fight_duration, S=status_effect_damage, ko=ko.get(content_type, []), hex_v=pre.hex_v, hex_period=20, hex_max=3,
                            A0=pre.a0, charm_v=pre.charm_val, hex_avg=pre.hex_avg, c_slot=0.0, stun=stun_vec, buffs=buffs, groups=[])
            e1 = sens["strip"][0] if "strip" in sens else stl.solve(eng_host)   # pass 1: the buff schedule (independent of the skill weights); Sensitivity may reuse the main strip
            engine_bbuff_mean = e1["Bbuff_mean"]
            for bid, key, kind in D.STATUS_BUFFS:
                ENGINE_N[key] = e1["buffs"][bid]["n"]
        self.e1 = e1

        # Buff-Casting Startup Delay: in fixed-duration fights the character casts every unlocked, actively cast buff sequentially at fight
        # start (1/APS s each) before the first damage-skill cast.  With the engine on the buffs are cast when they pay: no start-up delay.
        if fixed_duration_active and not status_on:
            self.buff_cast_startup_time = n_startup / actions_per_second
        else:
            self.buff_cast_startup_time = 0.0
        fight.startup_time = self.buff_cast_startup_time

        # ---- average buff multiplier: Magic Guard / Heal / Bless / Holy Magic Shell (Attack%) sum into one bucket, Advanced Blessing and
        # Infinity (Final Damage) stay separate factors.  With the engine on every buff's uptime comes from the engine's cast count. ----
        attack_bucket_sum = 0.0
        final_damage_mult = 1.0
        for key, b in BUFFS.items():
            if not unlocked(key):
                continue
            pct = self.buff_pct(key)
            uptime_fraction = fight.buff_uptime(b["cooldown"], b["duration"], b["costs_action"],
                                                ENGINE_N.get(key) if fixed_duration_active else None)
            avg_pct = pct * uptime_fraction
            if b["target"] == "ATTACK":
                attack_bucket_sum += avg_pct
            else:
                final_damage_mult *= 1 + avg_pct / 100
        # artifact Attack% (Old Music Box, Secret Map, Reindeer's Spear, Alliance Badge, Bottle of Emotion, Charm's average) joins the same additive bucket
        self.avg_buff_mult = engine_bbuff_mean if status_on else (1 + (attack_bucket_sum + pre.agg_attack_pct) / 100) * final_damage_mult
        self.attack_bucket_sum = attack_bucket_sum
        self.attack_bucket_avg = attack_bucket_sum + pre.agg_attack_pct

        # ---- artifact effects (full): everything that needs the action rate / startup delay / the timeline's status multiplier ----
        actx.aps, actx.startup = actions_per_second, self.buff_cast_startup_time
        # Companion!horn_uptime (computed whether or not Horn Flute is equipped, like the workbook): the share of the player's boss DAMAGE dealt
        # while the companion is out (candidate-0 timing, which already carries Angel Ray's stun in Breakthrough / Hero Dungeon).  The summon
        # timing is damage-independent, so the stub-host run (with the player's stun entries) reports it.
        s0, w0, d_comp, period, ts_window = comp_mod.horn_window(actx, monster_type, fight_duration, pvp_len, summon_time_inc, stun_pin,
                                                                 choice, c_level)
        dw = art_mod.damage_weights(fight_duration, pre.hex_v, pre.a0, pre.charm_val, e1["mult"] if status_on else None)
        actx.horn_uptime = art_mod.horn_flute_uptime(actx, dw, s0, w0, d_comp, period, ts_window)
        eff = self.art_effects = art_mod.Effects(eq, actx, pre)
        self.art_crit_rate = eff.agg_crit_rate                                     # (no live Crit-Rate SKILL source in this kit: ``crit_rate_bonus`` stays 0)
        self.art_crit_damage = eff.agg_crit_damage                                 # (Blood of the Divine's Crit Damage stays in crit_damage_bonus)
        self.art_crit_damage += sens_mod.boa_crit_damage_delta(                    # (Book of Ancient equip what-if: pct x the crit-rate total, Sensitivity only)
            sens, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate)
        self.art_boss_damage, self.art_normal_damage = eff.agg_boss_damage + sens.get("boss_damage_extra", 0.0), eff.agg_normal_damage   # (+ Star Rock what-if)
        self.art_final_damage = sens_mod.final_damage_bucket(eff.agg_final_damage, sens)   # (Sensitivity: baked-in Final Damage what-ifs are a factor on the product)
        # Hexagon Damage% and Peach Tree / Silver Pendant (enemy damage taken) sit in the ONE additive Damage% bucket (Calc!K, Summary DAMAGE_BONUS)
        self.art_damage, self.art_enemy_taken = eff.agg_damage, eff.agg_enemy_dmg_taken
        self.art_skill_damage, self.art_basic_attack_damage = eff.agg_skill_damage, eff.agg_basic_attack_damage
        self.extra_boss, self.extra_norm = eff.extras(actx, self.monster_defense, self.def_pen, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate,
                                                      self.crit_damage + self.crit_damage_bonus + self.art_crit_damage)
        # Hexagon / Charm differ between the two phases of Breakthrough / Hero Dungeon: per-phase timing factor (engine-off rows)
        self.ph_b, self.ph_n = art_mod.phase_state_ratios(content_type, fight_duration, pre.hex_v, pre.hex_avg, self.attack_bucket_avg,
                                                          pre.charm_val, pre.charm_avg)

        # ---- status engine pass 2: the skills' casts (weight of one cast = its boss damage before any timing factor) ----
        bb_s = dict(mastery=big_bang_mastery, mastery_boss=big_bang_boss_mastery)
        if status_on:
            def percast(key):
                if not unlocked(key):
                    return 0.0
                sk = SKILLS[key]
                pct = self.coeff_pct(sk["base"], sk["fidx"], sk["scales"], sk["job_step"])
                hd = self.hit_damage(pct, False, sk, key)
                hits = sk["hits"] * (fight_mod.ticks(fight.capped_window(sk["window"]), sk["icd"]) if sk.get("icd") else 1)
                return hits * hd * self.branch_multipliers(key, sk)[0]
            c_slot = (big_bang_hits * self.hit_damage(self.skill_coefficient_base, True, bb_s, "BIG_BANG")
                      * self.branch_multipliers("BIG_BANG", bb_s)[0]
                      if unlocked("BIG_BANG") else 0.0)
            groups = status_mod.build_groups(D, unlocked, SKILLS, percast, fight.capped_window,
                                             lambda cast: eff_cooldown(SKILLS[cast]["cooldown"], SKILLS[cast]["costs_action"]),
                                             stun_keys={e["key"] for e in player_stun})
            E_ENGINE = status_mod.solve_groups(self, D, eng_host, groups, c_slot, ENGINE_N, sens)
            E_FS = E_ENGINE["fs"]
        self.e_engine = E_ENGINE

        # ---- action economy (cast rate subtracted from Big Bang) ----
        if fixed_duration_active:
            cast_rate = sum(ENGINE_N[k] if k in ENGINE_N else fight.non_buff_casts(eff_cooldown(s["cooldown"], s["costs_action"]))
                            for k, s in SKILLS.items() if s["costs_action"] and unlocked(k))
            cast_rate += sum(ENGINE_N[key] if key in ENGINE_N else fight.exact_casts(eff_cooldown(b["cooldown"], b["costs_action"]))
                             for key, b in BUFFS.items() if b["costs_action"] and unlocked(key))
            cast_rate += fight.non_buff_casts(eff_cooldown(hf["cooldown"], True)) if unlocked("HOLY_FOUNTAIN") else 0
            cast_rate += fight.exact_casts(nimble_feet_eff_cd) if unlocked("NIMBLE_FEET") else 0
            cast_rate /= fight_duration
        else:
            cast_rate = sum(1 / eff_cooldown(SKILLS[k]["cooldown"], s["costs_action"]) for k, s in SKILLS.items() if s["costs_action"] and unlocked(k))
            cast_rate += sum(1 / eff_cooldown(b["cooldown"], b["costs_action"]) for key, b in BUFFS.items() if b["costs_action"] and unlocked(key))
            cast_rate += (1 / eff_cooldown(hf["cooldown"], True)) if unlocked("HOLY_FOUNTAIN") else 0
            cast_rate += (1 / nimble_feet_eff_cd) if unlocked("NIMBLE_FEET") else 0
        self.cast_rate = cast_rate
        self.big_bang_per_second = big_bang_per_second = max(0, actions_per_second - cast_rate)

        big_bang_hit = self.hit_damage(self.skill_coefficient_base, True, bb_s, "BIG_BANG")
        self.big_bang_dps = big_bang_dps = (
            self.blend_branches("BIG_BANG", bb_s, big_bang_hits * big_bang_hit * big_bang_per_second) if unlocked("BIG_BANG") else 0.0)

        # ---- damage rows ----
        skill_dps = {}
        for key, s in SKILLS.items():
            if not unlocked(key):
                skill_dps[key] = 0.0
                continue
            pct = self.coeff_pct(s["base"], s["fidx"], s["scales"], s["job_step"])
            hd = self.hit_damage(pct, False, s, key)
            if key == "ANGEL_RAY_BOSS_PROC":
                if status_on and key in ENGINE_N:
                    rate = s["hits"] * ENGINE_N[key] / fight_duration
                else:
                    eff_cd = eff_cooldown(SKILLS["ANGEL_RAY"]["cooldown"], SKILLS["ANGEL_RAY"]["costs_action"])
                    if fixed_duration_active:
                        rate = fight.non_buff_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
                    else:
                        hits = s["hits"] * (fight_mod.ticks(fight.capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
                        rate = hits / eff_cd
                # Boss-only effect: scales with the boss branch alone (normal unit 0); PvP keeps boss/normal damage% out like every other row
                skill_dps[key] = self.blend_branches(key, s, rate * hd, 0.0)
                continue
            eff_cd = eff_cooldown(s["cooldown"], s["costs_action"])
            if status_on and key in ENGINE_N:
                # engine casts: a summon row's hits = hits per full window x effective casts (last window truncated at the fight end)
                per_cast = s["hits"] * (fight_mod.ticks(fight.capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
                rate = per_cast * (E_FS[key] if key in D.STATUS_FS_KEYS else ENGINE_N[key]) / fight_duration
            elif fixed_duration_active:
                rate = fight.non_buff_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
            else:
                hits = s["hits"] * (fight_mod.ticks(fight.capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
                rate = hits / eff_cd
            skill_dps[key] = self.blend_branches(key, s, rate * hd)

        # ---- Triumph Feather: bespoke two-stage steady-state proc; R = the character's total attack rate ----
        self.triumph_feather = {}
        if unlocked("TRIUMPH_FEATHER"):
            tf = D.TRIUMPH_FEATHER
            tf_mastery = gated(tf["mastery"])
            tf_hd = self.hit_damage(self.coeff_pct(tf["base"], tf["fidx"], True, tf["job_step"]), False, dict(mastery=tf_mastery), "TRIUMPH_FEATHER")
            p1 = self.tier(tf["p1"])
            d1 = tf["d1"]
            tf_cd = eff_cooldown(tf["cooldown"], True)
            p2 = tf["p2"]
            icd2 = tf["icd2"]

            # Both stages roll "When attacking, X% chance" once per ATTACK per ENEMY HIT: an action that hits N enemies triggers a stage with
            # q = 1-(1-c)^N.  Action stream = Big Bang (6+bti targets) + every action-slot cast; only Angel Ray / Genesis casts hit a known enemy count,
            # every other cast (buffs, Bahamut's summon cast) is a single roll.  Rates are per branch (boss/PvP: N=1; normal: N=min(targets, cap)).
            def tf_hit_rate(k):
                if not (SKILLS[k]["costs_action"] and unlocked(k)):
                    return 0.0
                return self.cast_rate_py(k)

            def tf_x(chance, normal_branch):
                def q(targets):
                    n = fight.cap_targets(targets) if (normal_branch and monster_type != "pvp") else 1
                    return dmg.q_roll(chance, n)
                hit_rates = {k: tf_hit_rate(k) for k in ("ANGEL_RAY", "GENESIS")}
                x = big_bang_per_second * q(6 + self.basic_attack_target_increase)
                x += (cast_rate - sum(hit_rates.values())) * chance
                x += sum(rt * q(self.normal_targets[k]) for k, rt in hit_rates.items())
                return x

            def tf_branch_rate(normal_branch):
                x1, x2 = tf_x(p1 / 100, normal_branch), tf_x(p2 / 100, normal_branch)
                return (x1 * d1) / (1 + x1 * tf_cd) * x2 / (1 + icd2 * x2)

            tf_targets = self.tier(tf["targets"])
            tf_hits = self.tier(tf["hits"])
            # the branch multipliers use the row's own target count (1, or 7 from Lv.94), capped by Max Enemies
            tf_s = dict(mastery=tf_mastery)
            self.normal_targets["TRIUMPH_FEATHER"] = tf_targets
            rb, rn = tf_branch_rate(False), tf_branch_rate(True)
            self.triumph_feather = dict(boss_rate=rb, normal_rate=rn, hits=tf_hits, targets=tf_targets, stage1_chance_pct=p1)
            skill_dps["TRIUMPH_FEATHER"] = self.blend_branches("TRIUMPH_FEATHER", tf_s, tf_hits * tf_hd * rb, tf_hits * tf_hd * rn)
        else:
            skill_dps["TRIUMPH_FEATHER"] = 0.0
        self.skill_dps = skill_dps
        self.player_dps = big_bang_dps + sum(skill_dps.values())

        # ---- player's boss-only / normal-only totals (the companion's damage-share weights; rows in the verify script's insertion order) ----
        row_dps = list(skill_dps.items()) + [("BIG_BANG", big_bang_dps)]
        self.pb_total, self.pn_total, self.pu_total = self.ledger.split_totals(row_dps, D.STATUS_UNIFORM_ROWS)

        # ---- companion: src/companion_python_model.py fed with this model's own pipeline numbers ----
        self.begin_companion(summon_time_inc)          # (effective Summoning Time Increase % = Inputs + Arwen's Glass Shoes)
        self.crit_rate_total = self.crit_rate + self.crit_rate_bonus + self.art_crit_rate     # the FULL live crit-rate total
        if (choice != "None" and c_level >= 1) or pl_on or sens.get("want_comp_host"):   # (Sensitivity: the comparison tables need the host with no companion / stun too)
            basic_pair = self.ledger.pairs.get("BIG_BANG")
            if basic_pair is None:
                basic_b = basic_n = 0.0
            else:
                den = (1 - w) * basic_pair[3] + w * basic_pair[4]
                basic_b = big_bang_dps * basic_pair[3] / den
                basic_n = big_bang_dps * basic_pair[4] / den
            att_full, fd_full = 0.0, 1.0
            for key, b in BUFFS.items():
                if not unlocked(key):
                    continue
                if b["target"] == "ATTACK":
                    att_full += self.buff_pct(key)
                elif b["target"] != "ATTACK_SPEED":
                    fd_full *= 1 + self.buff_pct(key) / 100
            # Bishop's Damage% bucket is one additive sum (Damage input + Holy Symbol's Damage Boost): the companion's debuffs and the Hexagon
            # snapshot ratio use it
            joint = self.damage + self.damage_bonus + self.art_damage + self.art_enemy_taken
            boss_pct = self.boss_damage + self.art_boss_damage + self.monster_dmg_bonus
            norm_pct = self.normal_damage + self.art_normal_damage + self.normal_dmg_bonus
            comp_host = dict(comp_mod.host_common(self, pre, eff, basic_b, basic_n),
                unit=self.hit_damage(100.0, True, dict(mastery=0), "BIG_BANG") / 100, sd=self.skill_damage + self.art_skill_damage,
                aps=actions_per_second, avgbuff=self.avg_buff_mult, attack_bucket_avg=self.attack_bucket_avg, agg_damage_avg=joint,
                avgbuff_snap=lambda charm, extra: (1 + (att_full + pre.agg_attack_pct - pre.charm_avg + charm + extra) / 100) * fd_full,
                boss_pct=boss_pct, norm_pct=norm_pct, cr_total=self.crit_rate + self.crit_rate_bonus + self.art_crit_rate,
                cd_total=self.crit_damage + self.crit_damage_bonus + self.art_crit_damage, def_pen=self.def_pen, pst=pst, taken_bucket=joint)
            self.comp_host = comp_host
            self.run_companion(comp_host, choice, c_level, summon_time_inc, pl_on)
        self.total_dps = big_bang_dps + sum(skill_dps.values())
        self.total_dps += self.companion_dps

    # ------------------------------------------------------------------------------------------------------------------
    def row_dps(self, key):
        return self.big_bang_dps if key == "BIG_BANG" else self.skill_dps.get(key, 0.0)

    def derived_extra(self):
        return dict(
            basic_attacks_per_second=self.big_bang_per_second, avg_buff_mult=self.avg_buff_mult, as_bonus=self.as_bonus,
            element_amp_pct=self.element_amp_pct, arcane_aim_pct=self.arcane_aim_pct, buff_mastery_pct=self.buff_mastery_pct,
            skill_coefficient_base=self.skill_coefficient_base, buff_cast_startup_time=self.buff_cast_startup_time,
            attack_bucket_sum=self.attack_bucket_sum, monster_dmg_bonus=self.monster_dmg_bonus, normal_dmg_bonus=self.normal_dmg_bonus,
            damage_bonus=self.damage_bonus, crit_damage_bonus=self.crit_damage_bonus, big_bang_hits=self.big_bang_hits,
            total_defense=self.total_defense, divine_protection_bonus=self.divine_protection_bonus,
            invincible_conversion_rate=self.invincible_conversion_rate, invincible_int_bonus=self.invincible_int_bonus,
            triumph_feather=dict(self.triumph_feather),
        )


fields, schema, defaults = classapi.make(CLASS_ID, CLASS_NAME, STAT_IDENTITY, _MAIN_STAT_FIELDS, D)
artifact_schema = classapi.artifact_schema


def model(inputs):
    """The evaluated model object (everything ``compute`` reports plus the internals engine/sensitivity.py reads: ``comp_host``, ``e1`` /
    ``e_engine`` (the timeline strip), ``art_effects`` ...).  Same input dict as ``compute``; honours ``inputs["_sens"]`` (engine/common/sens.py)."""
    return _Model(inputs)


def compute(inputs):
    """DPS of one Bishop setup.  ``inputs``: dict (see module docstring / ``schema()``); returns a JSON-friendly dict:

    total_dps / player_dps / boss_dps / normal_dps / player_boss_dps / player_normal_dps, skills (per damage row: key, name, dps, share,
    boss_dps, normal_dps, unlocked), companion (None or dps/boss/normal/share + model details; choice "None" = Angel Ray stun uplift only),
    engine_on (Status/KO timeline engine), engine (its cast counts and timing factors), derived (ATTACK, STAT_DAMAGE, actions/s, buff multipliers,
    total Defense, computed Inputs rows ...).
    """
    return _Model(inputs).result()
