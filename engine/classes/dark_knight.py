"""Dark Knight: the DPS model of ``src/verify_dark_knight_workbook.py`` as a function of a plain inputs dict.

    from engine.classes import dark_knight
    result = dark_knight.compute(dark_knight.defaults("World Boss"))

``compute(inputs)`` is bit-identical to the verify script (same operations in the same order); the verify script stays the independent
reference, ``tests/golden/test_dark_knight.py`` compares the two (with no artifact equipped).  Artifact equip effects (``inputs["artifacts"]``, up to 4
slots) are ported in ``engine/artifacts.py`` (shared with FP-Mage / Hero / Paladin; the Artifacts sheet of the builders is identical) and wired the way
``src/build_dark_knight_workbook.py`` wires them; the verify script does not model artifacts, so ``tests/golden/test_artifacts.py --class dark_knight`` checks
them against the workbook itself (``tests/golden/dark_knight_artifacts_golden.json``, evaluated with ``formulas``).

Inputs dict: the workbook's Inputs keys already resolved for the chosen content type (see ``schema()``), plus ``companion_level`` (the
level of the chosen companion, 0 = not unlocked).  A missing / ``None`` value reads as 0, exactly like a blank workbook cell.

Dark Knight specifics (all in the verify script):

* Main stat STR / sub DEX, plus two Defense inputs: **Iron Wall** (Lv38+) converts ``10 x FactorTable[level][22] / 1000`` % of the TOTAL Defense
  (``defense x (1 + defense_pct / 100)``) into flat STR before STR % applies (``iron_wall_str_bonus``, part of STAT_DAMAGE).  The TOTAL Defense also stays the PvP opponent's Defense
  (monster defense fallback; the workbook's Inputs label: "PvP assumes the opponent has the same total Defense as you").
* Four Attack% buffs share ONE additive bucket: Hex of the Evil Eye (Lv69, cooldown 30 s / 21 s from Lv104), Dark Resonance (Lv115, 20 s / 28 s from
  Lv130), Cross Over Chains (Lv66), Hyper Body (Lv45).  With the Status/KO engine on they are timed by the player (cast counts from the timeline
  strip -> exact-uptime formula); otherwise duty-cycle averages.  The bucket is ``e1["Bbuff_mean"]`` with the engine on.
* Global monster damage-taken bonus (``monster_dmg_bonus``, added to BOTH the boss and the normal Monster-Damage term and handed to the companion
  model as ``taken_bucket``) = Evil Eye's debuff (duty cycle) + Magic Crash's Lv126 Weaken + Dark Resonance's +20% boss clause + Hex's Lv82 +20% boss
  clause (the two clauses are boss-branch only: ``monster_blend(20, 0)`` x the buff's uptime, i.e. diluted by the normal weight).
* TWO player stuns: Rush (22 s, 15.4 s from Lv90, 2.5 s) and Evil Eye Shock (18 s, 1.5 s, needs the Evil Eye summon: assumed up whenever unlocked).
  Both are fixed on-cooldown groups of the timeline engine and, in Breakthrough / Hero Dungeon, lengthen the boss phase, so from Lv40 a "companion"
  result exists even with no companion chosen (``choice == "None"``: only the stun uplift).  ``STATUS_GROUP_TAKES_SLOT``: the Evil Eye of Dominant
  group (a 1 s DoT tied to the Evil Eye summon) takes no action slot.
* Dark Impale (the basic attack, 5 hits, 6 from Lv136) has Final Attack x Advanced Final Attack folded into its coefficient (additive, x25).
  Evil Eye Shock folds its own Enhancement (+Final Damage curve) in after the multiplicative mastery.  Revenge of the Evil Eye is a uniformly
  spread self-triggered row with Lv138 Spectral Shadows folded in.  Lord of Darkness is a proc x duty-cycle Crit Rate / Crit Damage bonus.
* Artifacts: the Attack% artifacts (Old Music Box, Secret Map, Reindeer's Spear, Alliance Badge, Bottle of Emotion, Charm's average) join the ONE Attack%
  bucket next to the four timed buffs (the timeline strip carries them as ``A0`` / Charm / Hexagon: with the engine on the bucket is the strip's mean); the
  Final Damage artifacts (Candle, Flaming Lava, Horn Flute) multiply on top of the Final Damage input; Peach Tree / Silver Pendant (enemy damage taken) are part
  of ``monster_dmg_bonus`` (next to Evil Eye / Magic Crash's Weaken / the boss clauses: added to both the Boss and the Normal Monster Damage terms); Ring of
  Cycles' / Rainbow Snail Shell's Crit Rate and Crit Damage add to Lord of Darkness' bonus (the crit totals); Soul Contract's cooldown decrease reaches every
  cooldown through ``Fight.cd_extra_pct`` (both player stuns, the buffs, the Weaken window, ...); Horn Flute's uptime is read from the stub run's candidate-0
  timing, which already carries BOTH player stuns (Rush + Evil Eye Shock); Iron Wall / Defense are untouched by artifacts (only Reindeer's Spear's boss/PvP
  defence correction reads the monster Defense).
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
from ..data import dark_knight as D
from .. import artifacts as art_mod
import status_timeline as stl  # noqa: E402  (src/status_timeline.py through the shim)

CLASS_ID = "dark_knight"
CLASS_NAME = "Dark Knight"
STAT_IDENTITY = {"main": "STR", "sub": "DEX"}

_MAIN_STAT_FIELDS = [
    schema_mod.field("defense_pct", "Defense %", "Offense", "float", "%", 0,
                     help="Iron Wall (from Lv38) turns your TOTAL Defense (flat Defense x (1 + this %)) into STR. That STR is added for you: leave it out of Flat STR."),
    schema_mod.field("flat_str", "Flat STR", "Main stats", "float", "flat", 0),
    schema_mod.field("str_pct", "STR %", "Main stats", "float", "%", 0),
    schema_mod.field("dex", "DEX", "Main stats", "float", "flat", 0),
]


class _Model(model_mod.ModelBase):
    DATA = D

    # ------------------------------------------------------------------------------------------------------------------
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
                                self.crit_damage + self.crit_damage_bonus + self.art_crit_damage)

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

    # ---- Attack% buffs: engine cast counts when the engine is on, else the duty-cycle average ----
    def buff_uptime_n(self, duration, cooldown, n):
        """the workbook's exact-uptime formula at the engine's cast count n"""
        fight = self.fight
        cd, dur = fight.eff_cooldown(cooldown, True), fight.eff_duration(duration)
        return fight.exact_buff_uptime(cd, dur, n) / self.fight_duration

    def attack_buff_avg(self, key, pct, duration, cooldown, costs_action):
        if not self.unlocked(key):
            return 0.0
        if key in self.engine_n:
            return pct * self.buff_uptime_n(duration, cooldown, self.engine_n[key])
        return pct * self.fight.buff_uptime(cooldown, duration, costs_action)

    def buff_boss_clause_avg(self, key, duration, cooldown, costs_action):
        """boss-only +20% clause (Dark Resonance / Hex Lv82), duty-cycled by the buff's own uptime (engine cast counts when the engine is on)"""
        if not self.unlocked(key):
            return 0.0
        return self.monster_blend(D.BOSS_CLAUSE_PCT, 0) * self.attack_buff_avg(key, 1.0, duration, cooldown, costs_action)

    # ------------------------------------------------------------------------------------------------------------------
    def _build(self, inp):
        # (PvP: the opponent has the same TOTAL Defense as you, like the workbook's Monster Defense formula; fixed 2026-11-20, see the verify script)
        ct = self.read_content(inp, defense=inp("defense") * (1 + inp("defense_pct") / 100))
        level = self.level
        sens = self.sens
        content_type = self.content_type
        monster_type = self.monster_type
        normal_weight = self.normal_weight
        fight_duration = self.fight_duration
        fixed_duration_active = self.fixed_duration_active
        self.monster_defense = sens.get("monster_defense", ct.monster_defense)   # (Sensitivity: a Defense block keeps the PvP opponent's Defense at the main sheet's value)
        coeff_pct = self.coeff_pct
        gated = self.gated
        unlocked = self.unlocked
        flat_attack, attack_pct = inp("flat_attack"), inp("attack_pct")
        self.attack = dmg.attack_value(flat_attack, attack_pct)
        if sens.get("mainstat_attack_delta"):      # Sensitivity: the main/sub stat's flat-Attack channel (bug 7), applied before ATTACK%
            self.attack += sens["mainstat_attack_delta"] * (1 + attack_pct / 100)
        flat_str, str_pct, dex_stat = inp("flat_str"), inp("str_pct"), inp("dex")
        defense, defense_pct = inp("defense"), inp("defense_pct")
        # Iron Wall: a level-scaling share of the total Defense becomes flat STR (before STR %)
        iw = D.IRON_WALL
        self.total_defense = total_defense = defense * (1 + defense_pct / 100)
        iron_wall_conversion_rate = iw["rate_base"] * factors.get_factor(level, iw["rate_factor_idx"]) / 1000
        self.iron_wall_str_bonus = iron_wall_str_bonus = iron_wall_conversion_rate / 100 * total_defense if level >= iw["min_level"] else 0.0
        self.stat_damage = ((flat_str + iron_wall_str_bonus) * (1 + str_pct / 100)) * 0.01 + dex_stat * 0.0025
        self.damage = inp("damage")
        self.damage_amp = inp("damage_amp")
        self.boss_damage = inp("boss_damage") + sens.get("boss_damage_delta", 0.0)      # (+ a passive's level delta, Sensitivity only; none in this kit)
        self.normal_damage = inp("normal_damage")
        self.status_effect_damage = status_effect_damage = inp("status_effect_damage")
        self.final_damage = inp("final_damage")
        self.min_damage = inp("min_damage") + sens.get("min_damage_delta", 0.0)      # (+ Weapon Mastery's level delta, Sensitivity only)
        self.max_damage = inp("max_damage") + sens.get("max_damage_delta", 0.0)      # (+ Barricade Mastery's level delta / Athena's Gloves' dependent Max Damage, Sensitivity only)
        self.crit_rate = inp("crit_rate") + sens.get("crit_rate_threshold_extra", 0.0) + sens.get("crit_rate_delta", 0.0)   # (+ Book of Ancient's direct Crit Rate what-if / a passive's level delta, Sensitivity only)
        self.crit_damage = inp("crit_damage")
        attack_speed_base = inp("attack_speed")
        # Sensitivity: Reindeer's Spear equip toggle folds one signed dose of its base Def Pen into the typed value.  The dose reaches the rows' own defense reduction, the boss-branch
        # Reindeer correction and the companion's def pen (the builder's K formula reads `def_pen_total_block` since 2026-11-23; `def_pen_dose_rows=False` would reproduce
        # the old gap, the spec flag `reindeer_dose_in_rows` is True now).
        self.def_pen = inp("def_pen")
        self.def_pen_total = sens_mod.def_pen_with_dose(self.def_pen, sens)
        if sens.get("def_pen_dose_rows", True):
            self.def_pen = self.def_pen_total
        self.basic_attack_damage = inp("basic_attack_damage") + sens.get("basic_attack_damage_delta", 0.0)   # (+ a passive's level delta, Sensitivity only; none in this kit)
        self.skill_damage = inp("skill_damage") + sens.get("skill_damage_delta", 0.0)   # (+ Barricade Mastery's level delta, Sensitivity only)
        basic_attack_target_increase = inp("basic_attack_target_increase")
        summon_time_inc = inp("companion_summon_time_increase_pct")
        self.pvp_len = pvp_len = inp("pvp_fight_length") or content_mod.DEFAULT_PVP_FIGHT_LENGTH
        fight = self.fight = fight_mod.Fight(ct, pvp_len, inp("skill_cooldown_decrease"),
                                             inp("buff_duration_increase_pct") + sens.get("bdi_extra", 0.0),     # (+ Shamaness Marble what-if, Sensitivity only)
                                             inp("max_enemies_hit"))
        max_enemies_hit = fight.max_enemies_hit
        self.ledger = blend_mod.BranchLedger(normal_weight)

        # ---- artifacts (equip effects): slots, the early quantities (Attack% bucket / Hexagon / Charm) and Soul Contract's cooldown decrease ----
        self.eq = eq = sens["eq"] if "eq" in sens else art_mod.resolve_slots(inp.raw("artifacts"))   # (Sensitivity: an equip-toggle what-if may exceed 4 slots)
        actx = self.art_ctx = art_mod.Ctx(self.content_type, monster_type, fight_duration, pvp_len, fixed_duration_active,
                                          crit_rate=self.crit_rate, attack_speed=attack_speed_base)
        pre = self.art_pre = art_mod.Pre(eq, actx)
        # Arwen's Glass Shoes: the companion's effective Summoning Time Increase % = the Inputs value + the artifact (every use below)
        summon_time_inc += art_mod.summon_time_inc_pct(eq)
        fight.cd_extra_pct = art_mod.soul_contract_pct(eq, self.content_type)
        # live artifact terms of the damage pipeline; zero / neutral until the full effects are known (after the buff-casting startup delay)
        self.art_final_damage = self.art_joint_damage = self.art_skill_damage = self.art_basic_attack_damage = 0.0
        self.art_boss_damage = self.art_normal_damage = self.art_crit_rate = self.art_crit_damage = 0.0
        self.extra_boss = self.extra_norm = 1.0
        self.ph_b = self.ph_n = 1.0
        eff_cooldown = fight.eff_cooldown
        eff_duration = fight.eff_duration
        self.maple_hero_pct = 0.0
        self.monster_dmg_bonus = 0.0

        basic_lvl = self.sl.input_level(4)
        self.skill_coefficient_base = D.DARK_IMPALE_BASE * factors.get_factor(basic_lvl, 21) / 1000

        # ---- Helper rows (Final Attack, Advanced Final Attack, Maple Hero, Evil Eye Shock Enhancement): own coefficients only ----
        fa, afa, mh, ese = D.FINAL_ATTACK, D.ADVANCED_FINAL_ATTACK, D.MAPLE_HERO, D.EVIL_EYE_SHOCK_ENH
        self.final_attack_pct = final_attack_pct = (
            (coeff_pct(fa["base"], fa["fidx"], True, fa["step"]) * (1 + gated(fa["gated"]) / 100)) if unlocked("FINAL_ATTACK_HELPER") else 0.0)
        self.advanced_final_attack_pct = advanced_final_attack_pct = (
            coeff_pct(afa["base"], afa["fidx"], True, afa["step"]) + gated(afa["gated"])
            if unlocked("ADVANCED_FINAL_ATTACK_HELPER") else 0.0)
        self.maple_hero_pct = maple_hero_pct = coeff_pct(mh["base"], mh["fidx"], True, mh["step"]) if unlocked("MAPLE_HERO_HELPER") else 0.0
        self.evil_eye_shock_enh_pct = evil_eye_shock_enh_pct = (
            coeff_pct(ese["base"], ese["fidx"], True, ese["step"]) if unlocked("EVIL_EYE_SHOCK_ENH") else 0.0)

        # Dark Impale's own coefficient includes Final Attack + Advanced Final Attack folded in, PLUS its own Damage / Boss Damage mastery chains
        dark_impale_final_attack_addition = (
            final_attack_pct / 100 * (1 + advanced_final_attack_pct / 100) * D.FINAL_ATTACK_SHARE
            if unlocked("FINAL_ATTACK_HELPER") else 0.0)
        dark_impale_mastery_damage = gated(D.DARK_IMPALE_MASTERY)
        self.dark_impale_mastery_boss_damage = dark_impale_mastery_boss_damage = gated(D.DARK_IMPALE_BOSS_MASTERY)
        dark_impale_pct = self.skill_coefficient_base * (1 + dark_impale_mastery_damage / 100) + dark_impale_final_attack_addition
        dark_impale_targets = 6 + basic_attack_target_increase
        hits0, hits_lvl, hits1 = D.DARK_IMPALE_HITS
        dark_impale_hits = hits1 if level >= hits_lvl else hits0

        # ---- Attack% buffs: Hex of the Evil Eye + Dark Resonance + Cross Over Chains + Hyper Body (live Attack% buffs, summed additively) ----
        eye_base, eye_lvl, eye_mult = D.EVIL_EYE_COOLDOWN
        evil_eye_cd = (eye_base * eye_mult) if level >= eye_lvl else eye_base
        hx, dr, coc, hb = D.HEX, D.DARK_RESONANCE, D.CROSS_OVER_CHAINS, D.HYPER_BODY
        hex_pct = (coeff_pct(hx["base"], hx["fidx"], True, hx["step"]) + gated(hx["gated"])) if unlocked("HEX_OF_THE_EVIL_EYE") else 0.0
        dark_resonance_pct = coeff_pct(dr["base"], dr["fidx"], True, dr["step"]) if unlocked("DARK_RESONANCE") else 0.0
        dark_resonance_duration = dr["duration"] * dr["duration_mult"] if level >= dr["duration_level"] else dr["duration"]
        cross_over_chains_pct = (
            coeff_pct(coc["base"], coc["fidx"], True, coc["step"]) + gated(coc["gated"]) if unlocked("CROSS_OVER_CHAINS") else 0.0)
        hyper_body_pct = (coeff_pct(hb["base"], hb["fidx"], True, hb["step"]) + gated(hb["gated"])) if unlocked("HYPER_BODY") else 0.0
        attack_buffs = [   # (engine id, row key, Attack%, base duration, base cooldown)
            ("HEX", "HEX_OF_THE_EVIL_EYE", hex_pct, hx["duration"], evil_eye_cd),
            ("DR", "DARK_RESONANCE", dark_resonance_pct, dark_resonance_duration, dr["cooldown"]),
            ("COC", "CROSS_OVER_CHAINS", cross_over_chains_pct, coc["duration"], coc["cooldown"]),
            ("HB", "HYPER_BODY", hyper_body_pct, hb["duration"], hb["cooldown"]),
        ]

        # ---- Nimble Feet (Attack Speed buff, duty-cycle averaged) ----
        nf = D.NIMBLE_FEET
        nimble_feet_pct = coeff_pct(nf["base"], nf["fidx"], False, nf["step"])
        nimble_avg = fight.buff_uptime(nf["cooldown"], nf["duration"], True) * nimble_feet_pct if unlocked("NIMBLE_FEET") else 0.0
        self.as_bonus = as_bonus = nimble_avg
        self.actions_per_second = actions_per_second = dmg.actions_per_second(attack_speed_base + sens.get("attack_speed_extra", 0.0), as_bonus)   # (+ Weapon Acceleration's level delta / Athena's Gloves what-if)

        # ---- Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`) ----
        choice, c_level = comp_mod.read_choice(inp)
        self.companion_choice, self.companion_level = choice, c_level
        # The player's own stunning skills (game table): Rush 2.5 s and Evil Eye Shock 1.5 s, both cast on cooldown from the start
        rush = D.DAMAGE_SKILLS["RUSH"]
        rush_cooldown = self.haste(rush["cooldown"], rush["haste"])
        player_stun = [dict(e, cd=rush_cooldown) if e["key"] == "RUSH" else dict(e) for e in D.PLAYER_STUN]
        pl_on = any(unlocked(e["key"]) for e in player_stun)
        stun_info = comp_mod.stun_probe(ct, fight, pvp_len, choice, c_level, summon_time_inc)
        hasstun = bool(stun_info and stun_info.get("hasstun")) or pl_on
        ko = content_mod.ko_windows(fight_duration)
        self.status_on = status_on = fixed_duration_active and normal_weight == 0 and (content_type in ko or hasstun)
        startup_count = sum(1 for k in D.STARTUP_BUFFS if unlocked(k))
        t0_pl = 0.0 if status_on else ((startup_count / actions_per_second) if fixed_duration_active else 0.0)
        self.pst = pst = [dict(id=e["id"], typ=e["typ"], cd=eff_cooldown(e["cd"], True), dur=e["dur"],
                               p=e["p"], on=unlocked(e["key"]), t0=t0_pl, tick=1.0, win=0.0) for e in player_stun]
        stun_info, stun_pin = comp_mod.stun_windows(ct, fight, pvp_len, pst, choice, c_level, summon_time_inc, sens)
        self.stf_b = stun_pin["stunfracB"]
        self.stf_n = stun_pin["stunfracN"]
        self.engine_n = ENGINE_N = {}
        E_ENGINE = None
        E_FS = {}
        self.phi_rows = {}
        self.phi_unif = 1.0
        e1 = None
        if status_on:
            # (the verify script raises KeyError here when no companion is chosen and both player stuns are locked, i.e. level < 40 in a KO content:
            # the companion model's early return carries no stun_vector.  The engine reads that as "no companion stun" instead of crashing.)
            comp_stun = stun_info["stun_vector"](stl.NB_MAX) if "stun_vector" in stun_info else [0.0] * stl.NB_MAX
            stun_vec = [min(1.0, a + b) for a, b in zip(comp_stun, stl.pl_stun_vector([dict(e, t0=0.0) for e in pst], fight_duration, stl.NB_MAX))]
            buffs = [dict(id=bid, kind="atk", F=pct, dur=eff_duration(dur), cd=eff_cooldown(cd, True), on=unlocked(key))
                     for bid, key, pct, dur, cd in attack_buffs]
            eng_host = dict(T=fight_duration, S=status_effect_damage, ko=ko.get(content_type, []), hex_v=pre.hex_v, hex_period=20, hex_max=3,
                            A0=pre.a0, charm_v=pre.charm_val, hex_avg=pre.hex_avg, c_slot=0.0, stun=stun_vec, buffs=buffs, groups=[])
            e1 = sens["strip"][0] if "strip" in sens else stl.solve(eng_host)   # pass 1: the buff schedule (independent of the skill weights); Sensitivity may reuse the main strip
            for bid, key, _pct, _dur, _cd in attack_buffs:
                ENGINE_N[key] = e1["buffs"][bid]["n"]

        self.e1 = e1
        hex_avg = self.attack_buff_avg("HEX_OF_THE_EVIL_EYE", hex_pct, hx["duration"], evil_eye_cd, False)
        hex_boss_avg = (self.buff_boss_clause_avg("HEX_OF_THE_EVIL_EYE", hx["duration"], evil_eye_cd, False)
                        if level >= hx["boss_clause_level"] else 0.0)
        dark_resonance_avg = self.attack_buff_avg("DARK_RESONANCE", dark_resonance_pct, dark_resonance_duration, dr["cooldown"], True)
        dark_resonance_boss_avg = self.buff_boss_clause_avg("DARK_RESONANCE", dark_resonance_duration, dr["cooldown"], True)
        cross_over_chains_avg = self.attack_buff_avg("CROSS_OVER_CHAINS", cross_over_chains_pct, coc["duration"], coc["cooldown"], True)
        hyper_body_avg = self.attack_buff_avg("HYPER_BODY", hyper_body_pct, hb["duration"], hb["cooldown"], True)
        self.hex_avg, self.hex_boss_avg = hex_avg, hex_boss_avg
        self.dark_resonance_avg, self.dark_resonance_boss_avg = dark_resonance_avg, dark_resonance_boss_avg
        self.cross_over_chains_avg, self.hyper_body_avg = cross_over_chains_avg, hyper_body_avg
        # Attack% bucket (in %) the companion's snapshot sees on average
        self.attack_bucket_sum = attack_bucket_sum = hex_avg + dark_resonance_avg + cross_over_chains_avg + hyper_body_avg
        # artifact Attack% (Old Music Box, Secret Map, Reindeer's Spear, Alliance Badge, Bottle of Emotion, Charm's average) joins the same additive bucket
        self.attack_bucket_avg = attack_bucket_sum + pre.agg_attack_pct
        self.attack_bucket_mult = attack_bucket_mult = e1["Bbuff_mean"] if status_on else 1 + self.attack_bucket_avg / 100

        # ---- Lord of Darkness (proc-chance x duty-cycle, split Crit Rate / Crit Damage halves) ----
        lod = D.LORD_OF_DARKNESS
        lcr, lcd = D.LORD_OF_DARKNESS_CRITRATE, D.LORD_OF_DARKNESS_CRITDMG
        lord_critrate_pct = coeff_pct(lcr["base"], lcr["fidx"], True, lcr["step"]) if unlocked("LORD_OF_DARKNESS_CRITRATE") else 0.0
        lord_critrate_avg = (
            lord_critrate_pct * (lod["proc_chance"] / 100) * (fight.buff_uptime(lod["cooldown"], lod["duration"], False) * 1.0)
            if unlocked("LORD_OF_DARKNESS_CRITRATE") else 0.0)
        lord_critdmg_pct = coeff_pct(lcd["base"], lcd["fidx"], True, lcd["step"]) if unlocked("LORD_OF_DARKNESS_CRITDMG") else 0.0
        lord_critdmg_avg = (
            lord_critdmg_pct * (lod["proc_chance"] / 100) * (fight.buff_uptime(lod["cooldown"], lod["duration"], False) * 1.0)
            if unlocked("LORD_OF_DARKNESS_CRITDMG") else 0.0)
        self.lord_critrate_avg, self.lord_critdmg_avg = lord_critrate_avg, lord_critdmg_avg
        self.crit_rate_bonus = lord_critrate_avg
        self.crit_damage_bonus = lord_critdmg_avg
        self.final_damage_extra = sens.get("final_damage_delta", 0.0)      # no live Final-Damage-buff source exists in this kit (+ Power Stance / Final Pact level deltas, Sensitivity only)

        # Buff-Casting Startup Delay: in fixed-duration fights the character casts every unlocked, actively cast buff sequentially at fight start
        # (1/APS s each) before the first damage-skill cast (0 when the engine is on: buffs are cast when they pay).
        if fixed_duration_active and not status_on:
            self.buff_cast_startup_time = startup_count / actions_per_second
        else:
            self.buff_cast_startup_time = 0.0
        fight.startup_time = self.buff_cast_startup_time

        # ---- artifact effects (full): everything that needs the action rate / startup delay / the timeline's status multiplier ----
        actx.aps, actx.startup = actions_per_second, self.buff_cast_startup_time
        # Companion!horn_uptime (computed whether or not Horn Flute is equipped, like the workbook): the share of the player's boss DAMAGE dealt
        # while the companion is out (candidate-0 timing, which already carries BOTH player stuns, Rush + Evil Eye Shock, in Breakthrough / Hero
        # Dungeon).  The summon timing is damage-independent, so the stub-host run (with the player's stun entries) reports it.
        s0, w0, d_comp, period, ts_window = comp_mod.horn_window(actx, monster_type, fight_duration, pvp_len, summon_time_inc, stun_pin,
                                                                 choice, c_level)
        dw = art_mod.damage_weights(fight_duration, pre.hex_v, pre.a0, pre.charm_val, e1["mult"] if status_on else None)
        actx.horn_uptime = art_mod.horn_flute_uptime(actx, dw, s0, w0, d_comp, period, ts_window)
        actx.crit_rate = self.crit_rate + self.crit_rate_bonus     # Ring of Cycles' threshold / Book of Ancient's base: Inputs + Lord of Darkness' live bonus
        eff = self.art_effects = art_mod.Effects(eq, actx, pre)
        self.art_crit_rate, self.art_crit_damage = eff.agg_crit_rate, eff.agg_crit_damage    # on top of Lord of Darkness' live bonuses
        self.art_crit_damage += sens.get("crit_damage_delta", 0.0)       # (Book of Ancient's dependent Crit Damage while Crit Rate is swept, Sensitivity only)
        self.art_crit_damage += sens_mod.boa_crit_damage_delta(          # (Book of Ancient equip what-if: pct x the crit-rate total incl. Lord of Darkness, Sensitivity only)
            sens, self.crit_rate + self.crit_rate_bonus + eff.agg_crit_rate)
        # the FULL live crit-rate total (Inputs + Lord of Darkness + artifact bucket; CLAUDE.md item 13): what the cube / equipment tables test against the 100% cap
        self.crit_rate_total = self.crit_rate + self.crit_rate_bonus + self.art_crit_rate
        self.art_boss_damage, self.art_normal_damage = eff.agg_boss_damage + sens.get("boss_damage_extra", 0.0), eff.agg_normal_damage   # (+ Star Rock what-if)
        self.art_final_damage = sens_mod.final_damage_bucket(eff.agg_final_damage, sens)   # (Sensitivity: baked-in Final Damage what-ifs are a factor on the product)
        self.art_joint_damage = eff.agg_damage                                     # Hexagon Damage%; enemy damage taken sits in monster_dmg_bonus (below)
        self.art_skill_damage, self.art_basic_attack_damage = eff.agg_skill_damage, eff.agg_basic_attack_damage
        self.extra_boss, self.extra_norm = eff.extras(
            actx, self.monster_defense, self.def_pen_total, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate,
            self.crit_damage + self.crit_damage_bonus + self.art_crit_damage)
        # Hexagon / Charm differ between the two phases of Breakthrough / Hero Dungeon: per-phase timing factor (engine-off rows)
        self.ph_b, self.ph_n = art_mod.phase_state_ratios(content_type, fight_duration, pre.hex_v, pre.hex_avg, self.attack_bucket_avg,
                                                          pre.charm_val, pre.charm_avg)

        # ---- Evil Eye (duty-cycle, no proc-chance gate) + Dark Resonance's / Hex's boss-only clauses + Magic Crash's Weaken: the Global Monster
        #      Damage-Taken Bonus% bucket (not engine-timed; the engine's cast counts only set the uptimes of Hex / Dark Resonance) ----
        ee = D.EVIL_EYE
        mcw = D.MAGIC_CRASH_WEAKEN
        evil_eye_pct = (coeff_pct(ee["base"], ee["fidx"], True, ee["step"]) + gated(ee["gated"])) if unlocked("EVIL_EYE") else 0.0
        self.evil_eye_avg = evil_eye_avg = (evil_eye_pct * fight.buff_uptime(evil_eye_cd, ee["duration"], True)) if unlocked("EVIL_EYE") else 0.0
        self.magic_crash_weaken_avg = magic_crash_weaken_avg = (
            (mcw["pct"] * min(1, mcw["duration"] / eff_cooldown(mcw["cooldown"], True))) if (unlocked("MAGIC_CRASH") and level >= mcw["level"]) else 0.0)
        # Peach Tree Herb Pouch / Silver Pendant (enemy damage taken) sit in the same global bucket (Summary R_MONSTER_DMG_BONUS)
        self.monster_dmg_bonus = evil_eye_avg + magic_crash_weaken_avg + dark_resonance_boss_avg + hex_boss_avg + eff.agg_enemy_dmg_taken

        # ---- Dark Impale (basic attack) hit (needed by the engine weights) ----
        dark_impale_hit = self.hit_damage(dark_impale_pct, True, dark_impale_mastery_boss_damage, 0)

        # ---- Damage skills (level-resolved) ----
        SKILLS = self.skills = {}
        for key, t in D.DAMAGE_SKILLS.items():
            hits, base = t["hits"], t["base"]
            if "hits_gate" in t and level >= t["hits_gate"][0]:
                hits = t["hits_gate"][1]
            if "base_gate" in t and level >= t["base_gate"][0]:
                base = t["base_gate"][1]
            s = dict(step=t["step"], cooldown=self.haste(t["cooldown"], t.get("haste")), hits=hits, base=base, fidx=t["fidx"],
                     mastery=gated(t["mastery"]), mastery_boss=0, mastery_normal=0, costs_action=t["costs_action"], targets=t["targets"])
            if "extra_targets" in t and level >= t["extra_targets"][0]:
                s["targets"] = t["targets"] + t["extra_targets"][1]
            if "icd" in t:
                s["icd"], s["window"] = t["icd"], t["window"]
            if key == "EVIL_EYE_SHOCK":
                s["fold"] = evil_eye_shock_enh_pct if level >= t["fold_level"] else 0.0
            if key == "REVENGE_OF_THE_EVIL_EYE":
                rf = t["revenge_fold"]
                s["fold"] = (rf["base"] * (factors.get_factor(self.sl.input_level(4), rf["fidx"]) / 1000)) if level >= rf["level"] else 0.0
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
            c_slot = dark_impale_hits * dark_impale_hit * self.branch_multipliers(dark_impale_mastery_boss_damage, 0, dark_impale_targets)[0]
            groups = status_mod.build_groups(D, unlocked, SKILLS, percast, fight.capped_window,
                                             lambda cast: eff_cooldown(SKILLS[cast]["cooldown"], SKILLS[cast]["costs_action"]),
                                             stun_keys={e["key"] for e in D.PLAYER_STUN}, slot_of=lambda gid: D.STATUS_GROUP_TAKES_SLOT[gid])
            E_ENGINE = status_mod.solve_groups(self, D, eng_host, groups, c_slot, ENGINE_N, sens)
            E_FS = E_ENGINE["fs"]
        self.e_engine = E_ENGINE

        # ---- Cast rate (subtracted from Dark Impale) ----
        cost_action_rows = []
        for key, ca in D.COST_ACTION_ORDER:
            if key in SKILLS:
                cd = SKILLS[key]["cooldown"]
            else:
                cd = D.BUFF_COOLDOWNS[key]
                if cd == "EVIL_EYE_CD":
                    cd = evil_eye_cd
            cost_action_rows.append((key, cd, ca, 1))

        def cast_count(k, cd, ca):
            if k in ENGINE_N:
                return ENGINE_N[k]
            return fight.exact_casts(eff_cooldown(cd, ca)) if k in D.BUFF_ROW_KEYS else fight.non_buff_casts(eff_cooldown(cd, ca))

        if fixed_duration_active:
            self.cast_rate = cast_rate = sum(cast_count(k, cd, ca) * aps for k, cd, ca, aps in cost_action_rows if ca and unlocked(k)) / fight_duration
        else:
            self.cast_rate = cast_rate = sum((1 / eff_cooldown(cd, ca)) * aps for k, cd, ca, aps in cost_action_rows if ca and unlocked(k))
        self.dark_impale_per_second = dark_impale_per_second = max(0, actions_per_second - cast_rate)

        # ---- Dark Impale (basic attack) DPS ----
        self.dark_impale_dps = dark_impale_dps = (
            self.blend_branches("DARK_IMPALE", dark_impale_hits * dark_impale_hit * dark_impale_per_second, dark_impale_mastery_boss_damage, 0,
                                dark_impale_targets)
            if unlocked("DARK_IMPALE") else 0.0)

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
        self.player_dps = dark_impale_dps + sum(skill_dps.values())

        # ---- player's boss-only / normal-only totals (the companion's damage-share weights; rows in the verify script's insertion order) ----
        row_dps = [("DARK_IMPALE", dark_impale_dps)] + list(skill_dps.items())
        self.pb_total, self.pn_total, self.pu_total = self.ledger.split_totals(row_dps, D.STATUS_UNIFORM_ROWS)

        # ---- companion: src/companion_python_model.py fed with this model's own pipeline numbers ----
        self.begin_companion(summon_time_inc)          # (effective Summoning Time Increase % = Inputs + Arwen's Glass Shoes)
        if (choice != "None" and c_level >= 1) or pl_on or sens.get("want_comp_host"):   # (Sensitivity: the comparison tables need the host with no companion / stun too)
            basic_b, basic_n = self.ledger.pairs.get("DARK_IMPALE", (0.0, 0.0))[:2]

            def full(key, pct):
                return pct if unlocked(key) else 0.0
            k1 = (full("HEX_OF_THE_EVIL_EYE", hex_pct) + full("DARK_RESONANCE", dark_resonance_pct) + full("CROSS_OVER_CHAINS", cross_over_chains_pct)
                  + full("HYPER_BODY", hyper_body_pct) + pre.agg_attack_pct - pre.charm_avg)
            boss_pct = self.boss_damage + self.art_boss_damage + self.monster_dmg_bonus
            norm_pct = self.normal_damage + self.art_normal_damage + self.monster_dmg_bonus
            comp_host = dict(comp_mod.host_common(self, pre, eff, basic_b, basic_n),
                unit=self.hit_damage(100.0, True, 0, 0) / 100, sd=self.skill_damage + self.art_skill_damage, aps=actions_per_second,
                avgbuff=attack_bucket_mult, attack_bucket_avg=self.attack_bucket_avg, agg_damage_avg=self.art_joint_damage,
                avgbuff_snap=lambda charm, extra: 1 + (k1 + charm + extra) / 100, boss_pct=boss_pct, norm_pct=norm_pct,
                cr_total=self.crit_rate + self.crit_rate_bonus + self.art_crit_rate,
                cd_total=self.crit_damage + self.crit_damage_bonus + self.art_crit_damage, def_pen=self.def_pen_total,
                taken_bucket=0.0 if monster_type == "pvp" else (1 - normal_weight) * boss_pct + normal_weight * norm_pct, pst=pst)
            self.comp_host = comp_host
            self.run_companion(comp_host, choice, c_level, summon_time_inc, pl_on)
        self.total_dps = self.player_dps + self.companion_dps

    # ------------------------------------------------------------------------------------------------------------------
    def row_dps(self, key):
        return self.dark_impale_dps if key == "DARK_IMPALE" else self.skill_dps.get(key, 0.0)

    def derived_extra(self):
        return dict(
            basic_attacks_per_second=self.dark_impale_per_second, avg_buff_mult=self.attack_bucket_mult, as_bonus=self.as_bonus,
            attack_bucket_mult=self.attack_bucket_mult, attack_bucket_sum=self.attack_bucket_sum,
            skill_coefficient_base=self.skill_coefficient_base, buff_cast_startup_time=self.buff_cast_startup_time,
            crit_rate_bonus=self.crit_rate_bonus, crit_damage_bonus=self.crit_damage_bonus, final_damage_extra=self.final_damage_extra,
            monster_dmg_bonus=self.monster_dmg_bonus, def_pen_effective=self.def_pen, maple_hero_pct=self.maple_hero_pct,
            total_defense=self.total_defense, iron_wall_str_bonus=self.iron_wall_str_bonus,
            final_attack_pct=self.final_attack_pct, advanced_final_attack_pct=self.advanced_final_attack_pct,
            evil_eye_shock_enh_pct=self.evil_eye_shock_enh_pct,
            hex_avg=self.hex_avg, hex_boss_avg=self.hex_boss_avg, dark_resonance_avg=self.dark_resonance_avg,
            dark_resonance_boss_avg=self.dark_resonance_boss_avg, cross_over_chains_avg=self.cross_over_chains_avg,
            hyper_body_avg=self.hyper_body_avg, evil_eye_avg=self.evil_eye_avg, magic_crash_weaken_avg=self.magic_crash_weaken_avg,
            lord_critrate_avg=self.lord_critrate_avg, lord_critdmg_avg=self.lord_critdmg_avg,
        )


fields, schema, defaults = classapi.make(CLASS_ID, CLASS_NAME, STAT_IDENTITY, _MAIN_STAT_FIELDS, D)
artifact_schema = classapi.artifact_schema


def model(inputs):
    """The evaluated model object (everything ``compute`` reports plus the internals engine/sensitivity.py reads: ``comp_host``, ``e1`` /
    ``e_engine`` (the timeline strip), ``art_effects`` ...).  Same input dict as ``compute``; honours ``inputs["_sens"]`` (engine/common/sens.py)."""
    return _Model(inputs)


def compute(inputs):
    """DPS of one Dark Knight setup.  ``inputs``: dict (see module docstring / ``schema()``); returns a JSON-friendly dict:

    total_dps / player_dps / boss_dps / normal_dps / player_boss_dps / player_normal_dps, skills (per damage row: key, name, dps, share,
    boss_dps, normal_dps, unlocked), companion (None or dps/boss/normal/share + model details; choice "None" = player-stun uplift only),
    engine_on (Status/KO timeline engine), engine (its cast counts and timing factors), derived (ATTACK, STAT_DAMAGE incl. Iron Wall, actions/s,
    buff multipliers, computed Inputs rows ...).
    """
    return _Model(inputs).result()
