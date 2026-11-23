"""Ice/Lightning Arch Mage (ILM): the DPS model of ``src/verify_ice_lightning_mage_workbook.py`` as a function of a plain inputs dict.

    from engine.classes import ice_lightning_mage
    result = ice_lightning_mage.compute(ice_lightning_mage.defaults("World Boss"))

``compute(inputs)`` is bit-identical to the verify script (same operations in the same order); the verify script stays the independent
reference, ``tests/golden/test_ice_lightning_mage.py`` compares the two (with no artifact equipped).  Artifact equip effects
(``inputs["artifacts"]``, up to 4 slots) are ported in ``engine/artifacts.py`` (shared with FP-Mage / Hero; the Artifacts sheet of the builders is
identical) and wired the way ``src/build_ice_lightning_mage_workbook.py`` wires them; the verify script does not model artifacts, so
``tests/golden/test_ice_lightning_mage_artifacts.py`` checks them against the workbook itself (``ice_lightning_mage_artifacts_golden.json``,
evaluated with ``formulas``).

Inputs dict: the workbook's Inputs keys already resolved for the chosen content type (see ``schema()``), plus ``companion_level`` (the
level of the chosen companion, 0 = not unlocked).  A missing / ``None`` value reads as 0, exactly like a blank workbook cell.

ILM specifics (all in the verify script): Chain Lightning is the basic attack (5 hits, 6 from Lv136; target count ``6 + increase``);
Glacier Wall is the player's own stun (2 s freeze, 22 s cooldown / 15.4 s from Lv90) feeding the Status Effect Damage / KO timeline and -
in Breakthrough / Hero Dungeon - lengthening the boss phase, so from Lv63 a "companion" result exists even with no companion chosen
(choice "None": only the stun uplift, reported under ``companion`` with ``choice == "None"``); Meditation / Magic Guard / Infinity are the
engine-timed buffs (Infinity's Final Damage is the time-average of its ramp, x64/45); Freezing Breath's Weaken (Lv118) and Elemental Reset
are one global damage-taken bonus added to both Boss / Normal Monster Damage terms; Frozen Break / Frost Clutch are flat Damage%;
Blizzard - Final Attack is a per-enemy-hit multi-trigger proc with a shared 1 s ICD; Frozen Orb halves its damage on a single target.
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
from ..data import ice_lightning_mage as D
from .. import artifacts as art_mod
import status_timeline as stl  # noqa: E402  (src/status_timeline.py through the shim)

CLASS_ID = "ice_lightning_mage"
CLASS_NAME = "Ice/Lightning Arch Mage"
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
        elem_amp = self.element_amp_pct if self.unlocked("ELEMENT_AMPLIFICATION") else 0.0
        arcane = self.arcane_aim_pct if self.unlocked("ARCANE_AIM") else 0.0
        final_mult = (1 + self.final_damage / 100) * (1 + self.art_final_damage / 100) * (1 + elem_amp / 100) * (1 + arcane / 100) ** 5
        source_pct = (self.basic_attack_damage + self.art_basic_attack_damage) if is_basic else (self.skill_damage + self.art_skill_damage)
        # Boss/Normal Monster Damage% is deliberately NOT applied here - it is blended per branch in blend_branches
        extra_mult = self.avg_buff_mult * (1 + self.art_damage / 100) * maple_mult_val
        base_hit = (
            base_damage * (1 + self.stat_damage / 100) * (1 + (self.damage + self.damage_bonus) / 100)
            * (1 + self.damage_amp / 100) * dmg_reduction * final_mult * (1 + source_pct / 100) * extra_mult
        )
        return dmg.expected_hit(base_hit, self.min_damage, self.max_damage, self.crit_rate + self.art_crit_rate,
                                self.crit_damage + self.crit_damage_bonus)

    # ---- targets and branch blending ----
    def enemies_hit(self, key):
        """Enemies one attack of this skill hits: 1 vs boss/PvP, the skill's own target count (capped by Max Enemies In Range) vs normal."""
        if self.monster_type == "pvp":
            return 1
        targets = 6 + self.basic_attack_target_increase if key == "CHAIN_LIGHTNING" else self.normal_targets.get(key, 1)
        return self.fight.cap_targets(targets)

    def branch_multipliers(self, key, s):
        """(boss-branch, normal-branch) multiplier: Boss/Normal Monster Damage% and target count (PvP: single target, neither bonus).
        Frozen Orb halves its damage against a single target (boss / PvP), applied inside the boss branch."""
        # outside the Boss/Normal Damage% buckets the artifacts add boss-only / normal-only multipliers (Reindeer's Spear, Contract of Darkness,
        # branch Final Damage), applied even in PvP (extra_boss / extra_norm are exactly 1.0 with no such artifact equipped)
        if self.monster_type == "pvp":
            return (D.FROZEN_ORB_SINGLE_TARGET_FACTOR if key == "FROZEN_ORB" else 1.0) * self.extra_boss, 1.0 * self.extra_norm
        boss_term = self.boss_damage + s.get("mastery_boss", 0) + self.monster_dmg_bonus + self.art_boss_damage
        normal_term = self.normal_damage + s.get("mastery_normal", 0) + self.monster_dmg_bonus + self.art_normal_damage
        boss = 1 + boss_term / 100
        if key == "FROZEN_ORB":
            boss *= D.FROZEN_ORB_SINGLE_TARGET_FACTOR
        return boss * self.extra_boss, (1 + normal_term / 100) * self.enemies_hit(key) * self.extra_norm

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
        ct = self.read_content(inp)
        level = self.level
        content_type = self.content_type
        sens = self.sens
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
        self.stat_damage = (flat_int * (1 + int_pct / 100)) * 0.01 + luk * 0.0025
        self.damage = inp("damage")
        self.damage_amp = inp("damage_amp")
        self.boss_damage = inp("boss_damage")
        self.normal_damage = inp("normal_damage")
        self.status_effect_damage = status_effect_damage = inp("status_effect_damage")
        self.final_damage = inp("final_damage")
        self.min_damage = inp("min_damage") + sens.get("min_damage_delta", 0.0)      # (+ Spell Mastery's level delta, Sensitivity only)
        self.max_damage = inp("max_damage") + sens.get("max_damage_delta", 0.0)      # (+ Athena's Gloves' dependent Max Damage, Sensitivity only)
        # (+ Book of Ancient's direct Crit Rate what-if and High Wisdom / Magic Critical (Crit Rate)'s level deltas, Sensitivity only: they feed Ring of Cycles' threshold
        # and the live crit rate alike)
        self.crit_rate = inp("crit_rate") + sens.get("crit_rate_threshold_extra", 0.0) + sens.get("crit_rate_delta", 0.0)
        self.crit_damage = inp("crit_damage") + sens.get("crit_damage_delta", 0.0)     # (+ Magic Critical (Crit Damage)'s level delta / Book of Ancient's dependent Crit Damage while Crit Rate is swept)
        attack_speed_base = inp("attack_speed")
        self.def_pen = sens_mod.def_pen_with_dose(inp("def_pen"), sens)   # Sensitivity: Reindeer's Spear equip toggle folds one signed dose of its base Def Pen into Inputs' value
        self.basic_attack_damage = inp("basic_attack_damage")
        self.skill_damage = inp("skill_damage")
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
                                          crit_rate=self.crit_rate, attack_speed=attack_speed_base)
        pre = self.art_pre = art_mod.Pre(eq, actx)
        # Arwen's Glass Shoes: the companion's effective Summoning Time Increase % = the Inputs value + the artifact (every use below)
        summon_time_inc += art_mod.summon_time_inc_pct(eq)
        fight.cd_extra_pct = art_mod.soul_contract_pct(eq, self.content_type)
        # live artifact terms of the damage pipeline; zero / neutral until the full effects are known (after the buff-casting startup delay)
        self.art_final_damage = self.art_damage = self.art_skill_damage = self.art_basic_attack_damage = 0.0
        self.art_boss_damage = self.art_normal_damage = 0.0
        self.art_crit_rate = self.crit_damage_bonus = 0.0     # (live artifact crit sources; ILM has no live Crit buff, ``crit_rate_bonus`` below is 0)
        self.crit_rate_bonus = 0.0
        self.extra_boss = self.extra_norm = 1.0
        self.ph_b = self.ph_n = 1.0
        eff_cooldown = fight.eff_cooldown
        eff_duration = fight.eff_duration

        basic_lvl = self.sl.input_level(4)
        self.skill_coefficient_base = D.CHAIN_LIGHTNING_BASE * factors.get_factor(basic_lvl, 21) / 1000

        # ---- Chain Lightning (basic attack) and the level-resolved damage rows ----
        chain_lightning_mastery = gated(D.CHAIN_LIGHTNING_MASTERY)
        chain_lightning_boss_mastery = gated(D.CHAIN_LIGHTNING_BOSS_MASTERY)
        chain_lightning_hits = self.tier(D.CHAIN_LIGHTNING_HITS)
        self.chain_lightning_hits = chain_lightning_hits
        SKILLS = self.skills = {
            "CHAIN_LIGHTNING": dict(job_step=4, cooldown=None, hits=chain_lightning_hits, base=None, fidx=None, scales=True,
                                    mastery=chain_lightning_mastery, mastery_boss=chain_lightning_boss_mastery, mastery_normal=0,
                                    costs_action=False),
        }
        for key, t in D.SKILL_TEMPLATES.items():
            s = dict(job_step=t["job_step"], cooldown=self.tier(t["cooldown"]), hits=t["hits"], base=t["base"], fidx=t["fidx"], scales=True,
                     mastery=gated(t["mastery"]), mastery_boss=t["mastery_boss"], mastery_normal=self.tier(t["mastery_normal"]),
                     costs_action=t["costs_action"])
            if "icd" in t:
                s["icd"] = self.tier(t["icd"])
            if "window" in t:
                s["window"] = t["window"]
            if "chance" in t:
                s["chance"], s["rolls"] = t["chance"], t["rolls"]
            SKILLS[key] = s
        self.normal_targets = dict(D.NORMAL_MONSTER_TARGETS, ELQUINES=self.tier(D.ELQUINES_TARGETS))

        # ---- passives / always-on terms ----
        self.buff_mastery_pct = self.passive_pct("BUFF_MASTERY")
        self.arcane_aim_pct = self.passive_pct("ARCANE_AIM")
        self.element_amp_pct = self.passive_pct("ELEMENT_AMPLIFICATION")
        elemental_reset_pct = self.passive_pct("ELEMENTAL_RESET")
        mp_eater_as_pct = self.passive_pct("MP_EATER_MP_BOOST")

        # Freezing Breath - Weaken (Mastery Lv.118): +15% Damage Taken, duty-cycle averaged off Freezing Breath's own cooldown (steady state
        # only); Elemental Reset's Damage Taken bonus sums into the same bucket.
        fbw = D.FREEZING_BREATH_WEAKEN
        if level >= fbw["level"]:
            fb_eff_cd = eff_cooldown(fbw["cooldown"], True)
            if monster_type == "pvp":
                weaken_uptime = min(eff_duration(fbw["duration"]), pvp_len) / pvp_len
            else:
                weaken_uptime = min(1.0, eff_duration(fbw["duration"]) / fb_eff_cd)
            self.monster_dmg_bonus = fbw["pct"] * weaken_uptime
        else:
            self.monster_dmg_bonus = 0.0
        self.monster_dmg_bonus += elemental_reset_pct

        # Frozen Break + Frost Clutch - flat, level-gated additive Damage%
        (l1, v1), (l2, v2), (l3, v3) = D.DAMAGE_BONUS
        self.damage_bonus = (v1 if level >= l1 else 0) + (v2 if level >= l2 else 0) + (v3 if level >= l3 else 0)

        # ---- average buff multiplier: Magic Guard + Meditation (Attack%) sum into one bucket, Infinity (Final Damage) its own factor ----
        BUFFS = {}
        for key, t in D.BUFFS.items():
            b = dict(t)
            b["cooldown"], b["duration"] = self.tier(t["cooldown"]), self.tier(t["duration"])
            BUFFS[key] = b
        attack_bucket_sum = 0.0
        final_damage_mult = 1.0
        for key, b in BUFFS.items():
            if not unlocked(key):
                continue
            pct = self.coeff_pct(b["base"], b["fidx"], b["scales"], b["job_step"])
            if "ramp_mult" in b:
                pct *= b["ramp_mult"]
            uptime_fraction = fight.buff_uptime(b["cooldown"], b["duration"], b["costs_action"])
            avg_pct = pct * uptime_fraction
            if b["target"] == "ATTACK":
                attack_bucket_sum += avg_pct
            else:
                final_damage_mult *= 1 + avg_pct / 100
        # artifact Attack% (Old Music Box, Secret Map, Reindeer's Spear, Alliance Badge, Bottle of Emotion, Charm's average) joins the same additive bucket
        self.avg_buff_mult = (1 + (attack_bucket_sum + pre.agg_attack_pct) / 100) * final_damage_mult

        # MP Eater: flat Attack Speed once unlocked; Nimble Feet: duty-cycle averaged (Attack Speed combines by diminishing returns)
        nf = D.NIMBLE_FEET
        nimble_feet_pct = self.coeff_pct(nf["base"], nf["fidx"], nf["scales"], nf["job_step"])
        nimble_feet_uptime = fight.buff_uptime(nf["cooldown"], nf["duration"], True)
        nimble_feet_avg = nimble_feet_pct * nimble_feet_uptime if unlocked("NIMBLE_FEET") else 0.0
        # (Sensitivity: Magic Acceleration's level delta joins MP Eater's flat Attack Speed - the workbook block gates it on MP Eater's unlock - and Athena's Gloves'
        # direct Attack Speed joins the typed value; the two combine differently through the diminishing-returns formula)
        self.as_bonus = as_bonus = ((mp_eater_as_pct + sens.get("as_bonus_extra", 0.0)) if unlocked("MP_EATER_MP_BOOST") else 0.0) + nimble_feet_avg
        self.actions_per_second = actions_per_second = dmg.actions_per_second(attack_speed_base + sens.get("attack_speed_extra", 0.0), as_bonus)

        # ---- Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`) ----
        choice, c_level = comp_mod.read_choice(inp)
        self.companion_choice, self.companion_level = choice, c_level
        # The player's own stunning skills (game table): Glacier Wall freezes for 2 s, cast on cooldown from the start
        player_stun = [dict(e, cd=SKILLS[e["key"]]["cooldown"]) for e in D.PLAYER_STUN]
        pl_on = any(unlocked(e["key"]) for e in player_stun)
        stun_info = comp_mod.stun_probe(ct, fight, pvp_len, choice, c_level, summon_time_inc)
        hasstun = bool(stun_info and stun_info.get("hasstun")) or pl_on
        ko = content_mod.ko_windows(fight_duration)
        self.status_on = status_on = fixed_duration_active and w == 0 and (content_type in ko or hasstun)
        startup_buffs = [k for k, b in BUFFS.items() if b["costs_action"] and unlocked(k)]
        n_startup = len(startup_buffs) + (1 if unlocked("NIMBLE_FEET") else 0)
        t0_pl = 0.0 if status_on else ((n_startup / actions_per_second) if fixed_duration_active else 0.0)
        self.pst = pst = [dict(id=e["id"], typ=e["typ"], cd=eff_cooldown(e["cd"], True), dur=e["dur"], p=e["p"], on=unlocked(e["key"]),
                               t0=t0_pl, tick=1.0, win=0.0) for e in player_stun]
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
            # (the verify script raises KeyError here when no companion is chosen and Glacier Wall is locked, i.e. level < 63 in a KO content:
            # the companion model's early return carries no stun_vector.  The engine reads that as "no companion stun" instead of crashing.)
            comp_stun = stun_info["stun_vector"](stl.NB_MAX) if "stun_vector" in stun_info else [0.0] * stl.NB_MAX
            stun_vec = [min(1.0, a + b) for a, b in zip(comp_stun, stl.pl_stun_vector([dict(e, t0=0.0) for e in pst], fight_duration, stl.NB_MAX))]
            buffs = []
            for bid, key, kind in D.STATUS_BUFFS:
                b = BUFFS[key]
                bd = dict(id=bid, kind=kind,
                          F=self.coeff_pct(b["base"], b["fidx"], b["scales"], b["job_step"]) * b.get("ramp_mult", 1.0),   # Infinity: time-average (x64/45)
                          dur=eff_duration(b["duration"]), cd=eff_cooldown(b["cooldown"], b["costs_action"]), on=unlocked(key))
                if kind == "ramp":
                    bd.update(D.INFINITY_RAMP)
                buffs.append(bd)
            eng_host = dict(T=fight_duration, S=status_effect_damage, ko=ko.get(content_type, []), hex_v=pre.hex_v, hex_period=20, hex_max=3,
                            A0=pre.a0, charm_v=pre.charm_val, hex_avg=pre.hex_avg, c_slot=0.0, stun=stun_vec, buffs=buffs, groups=[])
            e1 = sens["strip"][0] if "strip" in sens else stl.solve(eng_host)   # pass 1: the buff schedule (independent of the skill weights); Sensitivity may reuse the main strip
            self.avg_buff_mult = e1["Bbuff_mean"]
            for bid, key, kind in D.STATUS_BUFFS:
                ENGINE_N[key] = e1["buffs"][bid]["n"]
            # Excel's attack_bucket_avg for the companion snapshot: F x exact-uptime formula at the engine's cast count
            attack_bucket_sum = 0.0
            for bid, key, kind in D.STATUS_BUFFS:
                if kind != "atk" or not unlocked(key):
                    continue
                b = BUFFS[key]
                n, cd, dur = ENGINE_N[key], eff_cooldown(b["cooldown"], b["costs_action"]), eff_duration(b["duration"])
                up = ((n - 1) * min(dur, cd) + min(dur, max(0.0, fight_duration - (n - 1) * cd))) / fight_duration
                attack_bucket_sum += self.coeff_pct(b["base"], b["fidx"], b["scales"], b["job_step"]) * up

        self.e1 = e1

        # Buff-Casting Startup Delay: in fixed-duration fights the character casts every unlocked, actively cast buff sequentially at fight
        # start (1/APS s each) before the first damage-skill cast.
        if fixed_duration_active and not status_on:
            self.buff_cast_startup_time = n_startup / actions_per_second
        else:
            self.buff_cast_startup_time = 0.0
        fight.startup_time = self.buff_cast_startup_time

        # ---- artifact effects (full): everything that needs the action rate / startup delay / the timeline's status multiplier ----
        actx.aps, actx.startup = actions_per_second, self.buff_cast_startup_time
        # Companion!horn_uptime (computed whether or not Horn Flute is equipped, like the workbook): the share of the player's boss DAMAGE dealt
        # while the companion is out (candidate-0 timing, which already carries the player's own Glacier Wall stun in Breakthrough).  The summon
        # timing is damage-independent, so the stub-host run (with the player's stun entries) reports it.
        s0, w0, d_comp, period, ts_window = comp_mod.horn_window(actx, monster_type, fight_duration, pvp_len, summon_time_inc, stun_pin,
                                                                 choice, c_level)
        dw = art_mod.damage_weights(fight_duration, pre.hex_v, pre.a0, pre.charm_val, e1["mult"] if status_on else None)
        actx.horn_uptime = art_mod.horn_flute_uptime(actx, dw, s0, w0, d_comp, period, ts_window)
        eff = self.art_effects = art_mod.Effects(eq, actx, pre)
        self.art_crit_rate = eff.agg_crit_rate                                     # (no live Crit-Rate-buff source in this kit)
        self.crit_damage_bonus = eff.agg_crit_damage                               # (no live Crit-Damage-buff source in this kit)
        self.crit_damage_bonus += sens_mod.boa_crit_damage_delta(sens, self.crit_rate + eff.agg_crit_rate)   # Book of Ancient equip what-if (Sensitivity only)
        # the FULL live crit-rate total (Inputs + artifact bucket; CLAUDE.md item 13): what the cube / equipment tables test against the 100% cap
        self.crit_rate_total = self.crit_rate + self.art_crit_rate
        self.art_boss_damage, self.art_normal_damage = eff.agg_boss_damage + sens.get("boss_damage_extra", 0.0), eff.agg_normal_damage   # (+ Star Rock what-if)
        self.art_final_damage, self.art_damage = sens_mod.final_damage_bucket(eff.agg_final_damage, sens), eff.agg_damage    # Hexagon Damage% is its own multiplicative term next to the buffs
        self.art_skill_damage, self.art_basic_attack_damage = eff.agg_skill_damage, eff.agg_basic_attack_damage
        # Peach Tree / Silver Pendant enemy damage taken: summed into the monster damage-taken bucket (Weaken + Elemental Reset), both branches
        self.monster_dmg_bonus += eff.agg_enemy_dmg_taken
        self.extra_boss, self.extra_norm = eff.extras(actx, self.monster_defense, self.def_pen,
                                                      self.crit_rate + self.art_crit_rate, self.crit_damage + self.crit_damage_bonus)
        # Hexagon / Charm differ between the two phases of Breakthrough / Hero Dungeon: per-phase timing factor (engine-off rows)
        self.attack_bucket_avg = attack_bucket_sum + pre.agg_attack_pct
        self.ph_b, self.ph_n = art_mod.phase_state_ratios(content_type, fight_duration, pre.hex_v, pre.hex_avg, self.attack_bucket_avg,
                                                          pre.charm_val, pre.charm_avg)

        maple_lvl = self.sl.input_level(4)
        self.maple_factor = factors.get_factor(maple_lvl, 23)
        chain_s = SKILLS["CHAIN_LIGHTNING"]

        # ---- status engine pass 2: the skills' casts (weight of one cast = its boss damage before any timing factor) ----
        if status_on:
            def percast(key):
                if not unlocked(key):
                    return 0.0
                sk = SKILLS[key]
                pct = self.coeff_pct(sk["base"], sk["fidx"], sk["scales"], sk["job_step"])
                hd = self.hit_damage(pct, False, self.maple_mult(key), sk)
                hits = sk["hits"] * (fight_mod.ticks(fight.capped_window(sk["window"]), sk["icd"]) if sk.get("icd") else 1)
                return hits * hd * self.branch_multipliers(key, sk)[0]
            c_slot = (chain_lightning_hits * self.hit_damage(self.skill_coefficient_base, True, 1.0, chain_s)
                      * self.branch_multipliers("CHAIN_LIGHTNING", chain_s)[0])
            groups = status_mod.build_groups(D, unlocked, SKILLS, percast, fight.capped_window,
                                             lambda cast: eff_cooldown(SKILLS[cast]["cooldown"], SKILLS[cast]["costs_action"]),
                                             stun_keys={e["key"] for e in D.PLAYER_STUN})
            E_ENGINE = status_mod.solve_groups(self, D, eng_host, groups, c_slot, ENGINE_N, sens)
            E_FS = E_ENGINE["fs"]
        self.e_engine = E_ENGINE

        # ---- action economy (cast rate subtracted from Chain Lightning) ----
        if fixed_duration_active:
            cast_rate = sum(
                ENGINE_N[k] if k in ENGINE_N else fight.non_buff_casts(eff_cooldown(s["cooldown"], s["costs_action"]))
                for k, s in SKILLS.items() if s["costs_action"] and unlocked(k)
            )
            cast_rate += sum(
                ENGINE_N[key] if key in ENGINE_N else fight.exact_casts(eff_cooldown(b["cooldown"], b["costs_action"]))
                for key, b in BUFFS.items() if b["costs_action"] and unlocked(key)
            )
            if unlocked("NIMBLE_FEET"):
                cast_rate += fight.exact_casts(eff_cooldown(nf["cooldown"], True))
            cast_rate /= fight_duration
        else:
            cast_rate = sum(
                1 / eff_cooldown(s["cooldown"], s["costs_action"])
                for k, s in SKILLS.items() if s["costs_action"] and unlocked(k)
            )
            cast_rate += sum(
                1 / eff_cooldown(b["cooldown"], b["costs_action"])
                for key, b in BUFFS.items() if b["costs_action"] and unlocked(key)
            )
            if unlocked("NIMBLE_FEET"):
                cast_rate += 1 / eff_cooldown(nf["cooldown"], True)
        self.cast_rate = cast_rate
        self.chain_lightning_per_second = chain_lightning_per_second = max(0, actions_per_second - cast_rate)

        chain_hit = self.hit_damage(self.skill_coefficient_base, True, 1.0, chain_s)
        self.chain_dps = chain_dps = self.blend_branches(
            "CHAIN_LIGHTNING", chain_s,
            chain_lightning_hits * chain_hit * chain_lightning_per_second if unlocked("CHAIN_LIGHTNING") else 0.0)

        # ---- damage rows ----
        skill_dps = {}
        self.blizzard_fa_trigger = {}
        for key, s in SKILLS.items():
            if key == "CHAIN_LIGHTNING":
                continue
            if not unlocked(key):
                skill_dps[key] = 0.0
                continue
            pct = self.coeff_pct(s["base"], s["fidx"], s["scales"], s["job_step"])
            proc = 1 - (1 - s.get("chance", 100) / 100) ** s.get("rolls", 1)
            hd = self.hit_damage(pct, False, self.maple_mult(key), s)
            if key == "BLIZZARD_FINAL_ATTACK":
                # Multi-trigger proc (any attack, 30% per ENEMY HIT per attack, 1 s ICD): an attack hitting N enemies triggers with
                # q = 1-(1-c)^N (one proc per attack at most, shared ICD).  Steady-state rate X/(1+ICD*X), X = sum(attack rate x triggers per
                # cast x q), per branch (boss/PvP N=1, normal N=min(attack's targets, max_enemies_hit)), time-weighted like every other row.
                def trig_x(normal_branch):
                    def q(targets):
                        n = fight.cap_targets(targets) if (normal_branch and monster_type != "pvp") else 1
                        return dmg.q_roll(proc, n)
                    x = chain_lightning_per_second * q(6 + self.basic_attack_target_increase)
                    for tk, tn in D.BLIZZARD_PROC_TRIGGERS.items():
                        if not unlocked(tk):
                            continue
                        x += tn * self.cast_rate_py(tk) * q(D.NORMAL_MONSTER_TARGETS[tk])
                    return x
                xb, xn = trig_x(False), trig_x(True)
                rate_b = xb / (1 + s["icd"] * xb)
                rate_n = xn / (1 + s["icd"] * xn)
                self.blizzard_fa_trigger = dict(boss_attempts_per_s=xb, normal_attempts_per_s=xn, boss_rate=rate_b, normal_rate=rate_n)
                skill_dps[key] = self.blend_branches(key, s, rate_b * hd, rate_n * hd)
                continue
            eff_cd = eff_cooldown(s["cooldown"], s["costs_action"])
            if status_on and key in ENGINE_N:
                # engine casts: a DoT / summon row's hits = hits per full window x effective casts (last window truncated at the fight end)
                per_cast = s["hits"] * (fight_mod.ticks(fight.capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
                rate = per_cast * (E_FS[key] if key in D.STATUS_FS_KEYS else ENGINE_N[key]) / fight_duration
            elif fixed_duration_active:
                rate = fight.non_buff_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
            else:
                hits = s["hits"] * (fight_mod.ticks(fight.capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
                rate = hits / eff_cd
            skill_dps[key] = self.blend_branches(key, s, rate * proc * hd)
        self.skill_dps = skill_dps
        self.player_dps = chain_dps + sum(skill_dps.values())
        self.attack_bucket_sum = attack_bucket_sum

        # ---- player's boss-only / normal-only totals (the companion's damage-share weights; rows in the verify script's insertion order) ----
        row_dps = list(skill_dps.items()) + [("CHAIN_LIGHTNING", chain_dps)]
        self.pb_total, self.pn_total, self.pu_total = self.ledger.split_totals(row_dps, D.STATUS_UNIFORM_ROWS)

        # ---- companion: src/companion_python_model.py fed with this model's own pipeline numbers ----
        self.begin_companion(summon_time_inc)          # (effective Summoning Time Increase % = Inputs + Arwen's Glass Shoes)
        if (choice != "None" and c_level >= 1) or pl_on or sens.get("want_comp_host"):   # (Sensitivity: the comparison tables need the host with no companion / stun too)
            basic_pair = self.ledger.pairs["CHAIN_LIGHTNING"]
            den = (1 - w) * basic_pair[3] + w * basic_pair[4]
            basic_b = chain_dps * basic_pair[3] / den
            basic_n = chain_dps * basic_pair[4] / den
            att_full, fd_full = 0.0, 1.0
            for key, b in BUFFS.items():
                if not unlocked(key):
                    continue
                pct = self.coeff_pct(b["base"], b["fidx"], b["scales"], b["job_step"]) * b.get("ramp_mult", 1.0)
                if b["target"] == "ATTACK":
                    att_full += pct
                elif b["target"] != "ATTACK_SPEED":
                    fd_full *= 1 + pct / 100
            # the monster damage-taken bonus (Weaken + Elemental Reset + Peach Tree / Silver Pendant) sits in this class's additive Boss/Normal
            # Monster Damage bucket
            boss_pct = self.boss_damage + self.art_boss_damage + self.monster_dmg_bonus
            norm_pct = self.normal_damage + self.art_normal_damage + self.monster_dmg_bonus
            comp_host = dict(comp_mod.host_common(self, pre, eff, basic_b, basic_n),
                unit=self.hit_damage(100.0, True, 1.0, dict(mastery=0)) / 100, sd=self.skill_damage + self.art_skill_damage, aps=actions_per_second,
                avgbuff=self.avg_buff_mult, attack_bucket_avg=self.attack_bucket_avg, agg_damage_avg=eff.agg_damage,
                avgbuff_snap=lambda charm, extra: (1 + (att_full + pre.agg_attack_pct - pre.charm_avg + charm + extra) / 100) * fd_full,
                boss_pct=boss_pct, norm_pct=norm_pct, cr_total=self.crit_rate + self.art_crit_rate,
                cd_total=self.crit_damage + self.crit_damage_bonus, def_pen=self.def_pen, pst=pst,
                taken_bucket=0.0 if monster_type == "pvp" else (1 - w) * boss_pct + w * norm_pct)
            self.comp_host = comp_host
            self.run_companion(comp_host, choice, c_level, summon_time_inc, pl_on)
        self.total_dps = self.player_dps + self.companion_dps

    # ------------------------------------------------------------------------------------------------------------------
    def row_dps(self, key):
        return self.chain_dps if key == "CHAIN_LIGHTNING" else self.skill_dps.get(key, 0.0)

    def derived_extra(self):
        return dict(
            basic_attacks_per_second=self.chain_lightning_per_second, avg_buff_mult=self.avg_buff_mult, as_bonus=self.as_bonus,
            element_amp_pct=self.element_amp_pct, arcane_aim_pct=self.arcane_aim_pct, buff_mastery_pct=self.buff_mastery_pct,
            skill_coefficient_base=self.skill_coefficient_base, buff_cast_startup_time=self.buff_cast_startup_time,
            attack_bucket_sum=self.attack_bucket_sum, monster_dmg_bonus=self.monster_dmg_bonus, damage_bonus=self.damage_bonus,
            chain_lightning_hits=self.chain_lightning_hits, blizzard_final_attack=dict(self.blizzard_fa_trigger),
        )


fields, schema, defaults = classapi.make(CLASS_ID, CLASS_NAME, STAT_IDENTITY, _MAIN_STAT_FIELDS, D)
artifact_schema = classapi.artifact_schema


def model(inputs):
    """The evaluated model object (everything ``compute`` reports plus the internals engine/sensitivity.py reads: ``comp_host``, ``e1`` /
    ``e_engine`` (the timeline strip), ``art_effects`` ...).  Same input dict as ``compute``; honours ``inputs["_sens"]`` (engine/common/sens.py)."""
    return _Model(inputs)


def compute(inputs):
    """DPS of one Ice/Lightning Mage setup.  ``inputs``: dict (see module docstring / ``schema()``); returns a JSON-friendly dict:

    total_dps / player_dps / boss_dps / normal_dps / player_boss_dps / player_normal_dps, skills (per damage row: key, name, dps, share,
    boss_dps, normal_dps, unlocked), companion (None or dps/boss/normal/share + model details; choice "None" = Glacier Wall stun uplift
    only), engine_on (Status/KO timeline engine), engine (its cast counts and timing factors), derived (ATTACK, STAT_DAMAGE, actions/s,
    buff multipliers, computed Inputs rows ...).
    """
    return _Model(inputs).result()
