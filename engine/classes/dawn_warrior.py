"""Dawn Warrior (Cygnus Knight, STR main / DEX sub): an ENGINE-NATIVE class - there is no workbook, builder or verify script for it.

    from engine.classes import dawn_warrior
    result = dawn_warrior.compute(dawn_warrior.defaults("World Boss"))

Built on Hero's model (same input dict, same artifacts / companion / Status Effect Damage + KO timeline plumbing, same Sensitivity hooks); the kit comes from the user's
in-game skill text (``engine/data/dawn_warrior.py``, every displayed number reproduced by ``tests/golden/test_dawn_warrior_displayed.py``).  Every judgement call is flagged in
``D.ROW_NOTES`` and in KNOWN_GAPS.md ("Dawn Warrior (engine-native, no workbook)").

Dawn Warrior specifics:

* **Basic attack = Celestial Vision III** (level 100+, absent below like every class).  Equinox Cycle makes each swing trigger **Luna Divide**.
* **Timed buffs** (duty-cycle averages, cast on cooldown): Soul Elemental (Attack% + Soul Blessing; Soul Blessing II Crit Rate / Crit Damage; Soul Blessing III Final Damage), Equinox
  Cycle (Attack% + Master of the Sword's pp; Equinox Mastery's Basic Attack Damage; Master of the Sword's +8 % Final Damage), Elemental Harmony (Attack Speed).  Rows that only
  exist inside the Cycle (Luna Divide, Equinox Slash, enhanced Sol Rush) get the Cycle's Attack % and Basic Attack Damage at FULL strength, everything else the average.
* **Damage-taken debuffs**: True Sight (+x % for 15 s, every row) and Impaling Rays' Weaken (+15 % on stun-immune enemies = the boss branch, 10 s) join the monster-damage-taken bucket.
* **Cosmic Shower** is a 0.3 s tick summon with a same-target decay (-20 % per strike, floor x0.2); **Impaling Rays** has a delayed pierce hit 5 s later on stun-immune enemies (boss branch only).
* **Always-on passives and stat masteries are NOT added** (the Inputs come from the in-game stat screen, which already contains them): see ``D.ROW_NOTES`` / KNOWN_GAPS.
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
from ..data import dawn_warrior as D
from .. import artifacts as art_mod
import status_timeline as stl  # noqa: E402  (src/status_timeline.py through the shim)

CLASS_ID = "dawn_warrior"
CLASS_NAME = "Dawn Warrior"
STAT_IDENTITY = {"main": "STR", "sub": "DEX"}

_MAIN_STAT_FIELDS = [
    schema_mod.field("flat_str", "Flat STR", "Main stats", "float", "flat", 0, help="Include Main Stat Enhancement's own +30 if unlocked."),
    schema_mod.field("str_pct", "STR %", "Main stats", "float", "%", 0),
    schema_mod.field("dex", "DEX", "Main stats", "float", "flat", 0),
]


def shower_decay_avg(n_enemies, ticks):
    """Average damage multiplier of one Cosmic Shower window of ``ticks`` strikes on a random target among ``n_enemies``: every strike on the same target as the previous one
    (probability 1 / n_enemies; the ticks are always within 5 s) lowers the next by 20 %, at most 4 times (floor x0.2); a different target resets it.  n = 1 (boss / PvP):
    1, 0.8, 0.6, 0.4, 0.2, 0.2 ...  Returns 1.0 for no ticks."""
    if ticks <= 0:
        return 1.0
    p = 1.0 / max(1.0, float(n_enemies))
    steps = D.SHOWER_DECAY_MAX_STEPS
    dist = [1.0] + [0.0] * steps                      # P(k consecutive same-target strikes so far), k = 0..4
    total = 0.0
    for _ in range(ticks):
        total += sum(dist[k] * (1 - D.SHOWER_DECAY_STEP * k) for k in range(steps + 1))
        new = [0.0] * (steps + 1)
        new[0] = (1 - p) * sum(dist)
        for k in range(steps + 1):
            new[min(k + 1, steps)] += p * dist[k]
        dist = new
    return total / ticks


class _Model(model_mod.ModelBase):
    DATA = D

    # ------------------------------------------------------------------------------------------------------------------
    # ---- per-hit pipeline ----
    def hit_damage(self, coeff_pct_val, is_basic, skill_fd_pct=0.0, ec=False):
        """Expected damage of one hit.  ``skill_fd_pct``: the row's own Final Damage multiplier (Call of Cygnus / Master of the Sword: 1 + pct/100, the Maple Hero convention);
        ``ec``: the row only exists while Equinox Cycle is up, so the Cycle's Attack / Basic Attack Damage count at full strength instead of the average."""
        base_damage = self.attack * (coeff_pct_val / 100)
        dmg_reduction = dmg.defense_reduction(self.monster_defense, self.def_pen_eff)
        fd_bucket = self.final_damage + self.final_damage_extra + (self.ec_fd_bump if ec else 0.0)
        final_mult = (1 + fd_bucket / 100) * (1 + self.art_final_damage / 100) * (1 + skill_fd_pct / 100)
        if is_basic:
            source_pct = self.basic_attack_damage + self.art_basic_attack_damage + (self.ec_ba_full if ec else self.ec_ba_avg)
        else:
            source_pct = self.skill_damage + self.art_skill_damage
        attack_mult = self.attack_bucket_mult * (self.ec_attack_ratio if ec else 1.0)
        # Boss/Normal Monster Damage% is deliberately NOT applied here - it is blended per branch (its own multiplier x its own target count)
        base_hit = (
            base_damage * (1 + self.stat_damage / 100) * (1 + self.damage / 100)
            * (1 + self.damage_amp / 100) * dmg_reduction * final_mult * (1 + source_pct / 100)
            * attack_mult * (1 + self.art_joint_damage / 100)
        )
        return dmg.expected_hit(base_hit, self.min_damage, self.max_damage, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate,
                                self.crit_damage + self.crit_damage_bonus)

    def skill_hit(self, key, s):
        """Expected damage of one hit of a damage skill (before the boss/normal branch multipliers).  A skill mastery MULTIPLIES the skill's damage (CLAUDE.md bug 2)."""
        pct = self.coeff_pct(s["base"], s["fidx"], True, s["step"]) * (1 + s.get("mastery", 0) / 100)
        return self.hit_damage(pct, s.get("is_basic", False), s.get("cygnus_pct", 0.0), ec=s.get("ec_only", False))

    # ---- targets and branch blending ----
    def branch_multipliers(self, mastery_boss, mastery_normal, targets):
        """(boss, normal) multiplier of a row; Impaling Rays' Weaken (stun-immune enemies = boss branch only) joins the boss term."""
        if self.monster_type == "pvp":
            return 1.0 * self.extra_boss, 1.0 * self.extra_norm
        targets = min(targets, self.fight.max_enemies_hit)
        boss_term = self.boss_damage + mastery_boss + self.monster_dmg_bonus + self.weaken_boss + self.art_boss_damage
        normal_term = self.normal_damage + mastery_normal + self.monster_dmg_bonus + self.art_normal_damage
        return (1 + boss_term / 100) * self.extra_boss, (1 + normal_term / 100) * targets * self.extra_norm

    def blend_row(self, key, boss_unit, normal_unit, mastery_boss, targets, boss_only=False):
        b, n = self.branch_multipliers(mastery_boss, 0, targets)
        if boss_only:
            n = 0.0
        fb, fn = self.timing_factors(key)
        return self.ledger.blend(key, boss_unit, normal_unit, b * fb, n * fn, True)

    # ---- Equinox Cycle windows (Equinox Slash can only be cast inside them) ----
    def slash_casts(self, c, window, cd_ec):
        """Equinox Slash casts: fixed fight -> the exact number inside the merged Equinox Cycle windows (first cast at the window start, then every ``c`` s);
        steady state / PvP -> casts per second."""
        fight = self.fight
        if self.fixed_duration_active:
            T = self.fight_duration
            n_ec = fight_mod.exact_casts(cd_ec, T)
            spans = []
            for j in range(n_ec):
                a = j * cd_ec
                b = min(a + window, T)
                if b <= a:
                    continue
                if spans and a <= spans[-1][1] + 1e-12:
                    spans[-1][1] = max(spans[-1][1], b)
                else:
                    spans.append([a, b])
            return sum(int((b - a) / c + 1e-9) + 1 for a, b in spans)
        if window >= cd_ec:
            return 1 / c
        return min(1 / c, (int(window / c + 1e-9) + 1) / cd_ec)

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
        self.attack = dmg.attack_value(flat_attack, attack_pct + sens.get("attack_mult_delta", 0.0))      # (+ Divine Hand's / Soul Pledge's level delta, Sensitivity only: baked into Inputs!attack_pct)
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
            # Sensitivity: a baked-in Final Damage artifact what-if is a factor on the TYPED value inside the additive bucket (``baked_fd_form="typed"``, as Hero)
            self.final_damage = ((1 + self.final_damage / 100) * sens["final_damage_factor"] - 1) * 100
        self.min_damage = inp("min_damage") + sens.get("min_damage_delta", 0.0)      # (+ Sword Mastery's level delta, Sensitivity only)
        self.max_damage = inp("max_damage") + sens.get("max_damage_delta", 0.0)      # (+ Student of the Blade's level delta / Athena's Gloves' dependent Max Damage, Sensitivity only)
        self.crit_rate_input = inp("crit_rate") + sens.get("crit_rate_threshold_extra", 0.0)
        self.crit_rate = self.crit_rate_input + sens.get("crit_rate_delta", 0.0)
        self.crit_damage = inp("crit_damage")
        attack_speed_base = inp("attack_speed")
        def_pen = sens_mod.def_pen_with_dose(inp("def_pen"), sens)
        self.def_pen_eff = def_pen
        self.basic_attack_damage = inp("basic_attack_damage") + sens.get("basic_attack_damage_delta", 0.0)   # (+ Physical Training's / Unpredictable's level delta, Sensitivity only)
        self.skill_damage = inp("skill_damage") + sens.get("skill_damage_delta", 0.0)      # (+ Student of the Blade's level delta, Sensitivity only)
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
        self.skill_coefficient_base = D.CV_BASE * self._factor(basic_lvl, 21) / 1000

        # ---- level-resolved rows (static part: cooldowns, targets, ticks, shares) ----
        SKILLS = self.skills = {}
        for key, t in D.DAMAGE_SKILLS.items():
            s = dict(step=t["step"], cooldown=self.haste(t["cooldown"], t.get("haste")), hits=t["hits"], base=t["base"], fidx=t["fidx"],
                     mastery=gated(t["mastery"]), mastery_boss=t["mastery_boss"], costs_action=t["costs_action"], targets=t["targets"],
                     ec_only=t.get("ec_only", False), boss_only=t.get("boss_only", False), cast_row=t.get("cast_row", key), share=1.0)
            if "extra_targets" in t and level >= t["extra_targets"][0]:
                s["targets"] = t["targets"] + t["extra_targets"][1]
            if "icd" in t:
                s["icd"], s["window"] = self.tier(t["icd"]), t["window"]
            elif "window" in t:
                s["window"] = t["window"]
            s["cygnus_pct"] = (coeff_pct(D.CALL_OF_CYGNUS[t["cygnus"]], D.CALL_OF_CYGNUS_FIDX, True, 4)
                               if ("cygnus" in t and unlocked("CALL_OF_CYGNUS")) else 0.0)
            SKILLS[key] = s
        self.normal_targets = {k: v["targets"] for k, v in SKILLS.items()}

        # ---- timed buffs: uptimes (cast on cooldown, duty-cycle averages) ----
        se, ec_b, eh = D.SOUL_ELEMENTAL, D.EQUINOX_CYCLE, D.ELEMENTAL_HARMONY
        se_dur = se["duration"] * (se["duration_mastery"][1] if level >= se["duration_mastery"][0] else 1.0)
        ec_dur = ec_b["duration"] * (ec_b["duration_mastery"][1] if level >= ec_b["duration_mastery"][0] else 1.0)
        self.se_up = se_up = fight.buff_uptime(se["cooldown"], se_dur, True) if unlocked("SOUL_ELEMENTAL") else 0.0
        self.ec_up = ec_up = fight.buff_uptime(ec_b["cooldown"], ec_dur, True) if unlocked("EQUINOX_CYCLE") else 0.0
        eh_up = fight.buff_uptime(eh["cooldown"], eh["duration"], True) if unlocked("ELEMENTAL_HARMONY") else 0.0

        # Soul Elemental: Attack% (+ Soul Blessing's pp); Soul Blessing II Crit Rate / Crit Damage; Soul Blessing III Final Damage
        sb = D.SOUL_BLESSING
        self.se_attack_full = se_attack_full = (coeff_pct(se["base"], se["fidx"], True, se["step"]) if unlocked("SOUL_ELEMENTAL") else 0.0) + \
            (coeff_pct(sb["base"], sb["fidx"], True, sb["step"]) if unlocked("SOUL_BLESSING") else 0.0)
        sb2r, sb2d, sb3 = D.SOUL_BLESSING_II_RATE, D.SOUL_BLESSING_II_DMG, D.SOUL_BLESSING_III
        sb2_rate_full = coeff_pct(sb2r["base"], sb2r["fidx"], True, sb2r["step"]) if unlocked("SOUL_BLESSING_II") else 0.0
        sb2_dmg_full = (coeff_pct(sb2d["base"], sb2d["fidx"], True, sb2d["step"]) + gated(sb2d["gated"])) if unlocked("SOUL_BLESSING_II") else 0.0
        sb3_fd_full = (coeff_pct(sb3["base"], sb3["fidx"], True, sb3["step"]) + gated(sb3["gated"])) if unlocked("SOUL_BLESSING_III") else 0.0
        # Equinox Cycle: Attack% (+ Master of the Sword's pp), Equinox Mastery's Basic Attack Damage, Master of the Sword's Final Damage (Lv134)
        ms_ec = D.MASTER_SWORD_EC_ATTACK
        self.ec_attack_full = ec_attack_full = (coeff_pct(ec_b["base"], ec_b["fidx"], True, ec_b["step"]) if unlocked("EQUINOX_CYCLE") else 0.0) + \
            (coeff_pct(ms_ec["base"], ms_ec["fidx"], True, ms_ec["step"]) if unlocked("MASTER_OF_THE_SWORD") else 0.0)
        emb = D.EQUINOX_MASTERY_BA
        self.ec_ba_full = coeff_pct(emb["base"], emb["fidx"], True, emb["step"]) if unlocked("EQUINOX_MASTERY") else 0.0
        self.ec_ba_avg = self.ec_ba_full * ec_up
        ec_fd_full = float(D.MASTER_SWORD_EC_FD[1]) if (unlocked("MASTER_OF_THE_SWORD") and level >= D.MASTER_SWORD_EC_FD[0]) else 0.0
        # (Master of the Sword's +8 Final Damage is counted at its time-average for the Equinox-only rows too: a full-strength bump outside the typed bucket would make the
        #  Final Damage +1 % sweep inexact; the difference is ~0.8 % of those rows' damage)
        self.ec_fd_bump = 0.0

        se_attack_avg, ec_attack_avg = se_attack_full * se_up, ec_attack_full * ec_up
        attack_delta = 0.0      # (the passives' Attack% level deltas are applied to Inputs!attack_pct above, not to the live bucket)
        self.attack_bucket_sum = attack_bucket_sum = se_attack_avg + ec_attack_avg
        self.attack_bucket_avg = attack_bucket_sum + pre.agg_attack_pct
        self.attack_bucket_mult = 1 + self.attack_bucket_avg / 100
        a_wo_ec = se_attack_avg + pre.agg_attack_pct
        self.ec_attack_ratio = (1 + (a_wo_ec + ec_attack_full) / 100) / (1 + (a_wo_ec + ec_attack_avg) / 100)

        self.crit_rate_bonus = sb2_rate_full * se_up
        crit_damage_bonus_live = sb2_dmg_full * se_up
        self.crit_damage_bonus = crit_damage_bonus_live
        self.final_damage_extra = (sb3_fd_full * se_up + ec_fd_full * ec_up + sens.get("final_damage_delta", 0.0))      # (+ Inner Shout's / Unpredictable's level delta, Sensitivity only)

        # ---- the monster-damage-taken bucket: True Sight's debuff (every row) + Impaling Rays' Weaken (stun-immune enemies = boss branch only) ----
        ts_d = D.TRUE_SIGHT_TAKEN
        ts_pct = coeff_pct(ts_d["base"], ts_d["fidx"], True, ts_d["step"]) if unlocked("TRUE_SIGHT") else 0.0
        self.true_sight_taken_avg = ts_taken_avg = ts_pct * fight.buff_uptime(SKILLS["TRUE_SIGHT"]["cooldown"], ts_d["duration"], True) if unlocked("TRUE_SIGHT") else 0.0
        self.monster_dmg_bonus = ts_taken_avg
        wk = D.IMPALING_WEAKEN
        self.weaken_boss = (wk["pct"] * fight.buff_uptime(SKILLS["IMPALING_RAYS"]["cooldown"], wk["duration"], True)
                            if (unlocked("IMPALING_RAYS") and level >= wk["level"]) else 0.0)

        # ---- Elemental Harmony (Attack Speed buff, duty-cycle averaged; not level-scaling) ----
        self.as_bonus = as_bonus = eh["attack_speed"] * eh_up
        self.actions_per_second = actions_per_second = dmg.actions_per_second(attack_speed_base + sens.get("attack_speed_extra", 0.0), as_bonus)

        # ---- Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`) ----
        choice, c_level = comp_mod.read_choice(inp)
        self.companion_choice, self.companion_level = choice, c_level
        sr_stun = D.SOL_RUSH_STUN
        player_stun = []
        for e in D.PLAYER_STUN:
            e = dict(e, cd=SKILLS[e["key"]]["cooldown"])
            if e["key"] == "SOL_RUSH":
                e["dur"] = sr_stun[0] * (1 - ec_up) + sr_stun[1] * ec_up         # the enhanced Sol Rush (Cycle up) stuns for 1.5 s instead of 1 s
            player_stun.append(e)
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
        actx.crit_rate = self.crit_rate + self.crit_rate_bonus       # Ring of Cycles' threshold / Book of Ancient's base: Inputs + Soul Blessing II's live Crit Rate
        eff = self.art_effects = art_mod.Effects(eq, actx, pre)
        self.art_crit_rate = eff.agg_crit_rate
        self.crit_damage_bonus = crit_damage_bonus_live + eff.agg_crit_damage
        self.crit_damage_bonus += sens.get("crit_damage_delta", 0.0)              # (Sensitivity: Soul Pledge's level delta / Book of Ancient's dependent Crit Damage while Crit Rate is swept)
        self.crit_damage_bonus += sens_mod.boa_crit_damage_delta(
            sens, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate)
        self.crit_rate_total = self.crit_rate + self.crit_rate_bonus + self.art_crit_rate
        self.art_boss_damage, self.art_normal_damage = eff.agg_boss_damage + sens.get("boss_damage_extra", 0.0), eff.agg_normal_damage
        self.art_final_damage = eff.agg_final_damage
        self.art_joint_damage = eff.agg_damage + eff.agg_enemy_dmg_taken
        self.art_skill_damage, self.art_basic_attack_damage = eff.agg_skill_damage, eff.agg_basic_attack_damage
        self.extra_boss, self.extra_norm = eff.extras(actx, self.monster_defense, self.def_pen_eff,
                                                      self.crit_rate + self.crit_rate_bonus + self.art_crit_rate, self.crit_damage + self.crit_damage_bonus)
        self.ph_b, self.ph_n = art_mod.phase_state_ratios(content_type, fight_duration, pre.hex_v, pre.hex_avg, self.attack_bucket_avg,
                                                          pre.charm_val, pre.charm_avg)

        # ---- Celestial Vision III (basic attack): its own damage chain + boss chain, hits, targets ----
        cv_mastery = gated(D.CV_MASTERY)
        self.cv_mastery_boss = cv_mastery_boss = gated(D.CV_BOSS_MASTERY)
        cv_pct = self.skill_coefficient_base * (1 + cv_mastery / 100)
        cv_targets = 6 + basic_attack_target_increase
        h0, hl, h1 = D.CV_HITS
        cv_hits = h1 if level >= hl else h0
        cv_hit = self.hit_damage(cv_pct, True)

        # ---- Luna Divide: damage / targets / Master of the Sword's Final Damage multiplier ----
        lb = self.tier(D.LUNA_BASE)
        luna_step = 3 if level >= D.LUNA_BASE[1][0] else 2
        luna_pct = coeff_pct(lb, D.LUNA_FIDX, True, luna_step) * (1 + gated(D.LUNA_MASTERY) / 100)
        luna_targets = D.LUNA_TARGETS + sum(n for lv, n in D.LUNA_TARGET_BONUS if level >= lv)
        ms = D.MASTER_SWORD_FD
        luna_fd_pct = (coeff_pct(ms["base"], ms["fidx"], True, ms["step"]) * (ms["boost"][1] if level >= ms["boost"][0] else 1.0)
                       if unlocked("MASTER_OF_THE_SWORD") else 0.0)
        self.luna_fd_pct = luna_fd_pct
        luna_hit = self.hit_damage(luna_pct, True, luna_fd_pct, ec=True)

        # ---- Cosmic Shower: tick count and the same-target decay of each branch ----
        cs = SKILLS["COSMIC_SHOWER"]
        cs_ticks = fight_mod.ticks(fight.capped_window(cs["window"]), cs["icd"])
        n_enemies = max(1, fight.max_enemies_hit)
        cs["decay_b"] = shower_decay_avg(1, cs_ticks)
        cs["decay_n"] = shower_decay_avg(n_enemies, cs_ticks)
        self.shower_decay = (cs["decay_b"], cs["decay_n"])

        # ---- Equinox Cycle windows -> Equinox Slash casts; Sol Rush's enhanced share ----
        SKILLS["SOL_RUSH"]["share"] = 1 - ec_up
        SKILLS["SOL_RUSH_ENHANCED"]["share"] = ec_up
        ec_window = eff_duration(ec_dur)
        ec_cd = eff_cooldown(ec_b["cooldown"], True)
        slash_cd = eff_cooldown(SKILLS["EQUINOX_SLASH"]["cooldown"], True)
        self.slash_cast_info = dict(window=ec_window, cooldown=ec_cd, slash_cooldown=slash_cd)
        slash_casts = self.slash_casts(slash_cd, ec_window, ec_cd) if (unlocked("EQUINOX_SLASH") and unlocked("EQUINOX_CYCLE")) else 0

        for key, s in SKILLS.items():
            s["is_basic"] = False
        # per-row hit damage
        hits_of = {key: self.skill_hit(key, s) for key, s in SKILLS.items()}

        # ---- Status/KO engine pass 2: the damage skills' casts (weight of one cast = its boss damage before any timing factor) ----
        E_ENGINE = None
        if status_on:
            def base_percast(key):
                if not unlocked(key):
                    return 0.0
                sk = SKILLS[key]
                hits = sk["hits"] * (fight_mod.ticks(fight.capped_window(sk["window"]), sk["icd"]) if sk.get("icd") else 1)
                if key == "COSMIC_SHOWER":
                    hits *= sk["decay_b"]
                return hits * hits_of[key] * sk["share"] * self.branch_multipliers(sk.get("mastery_boss", 0), 0, sk["targets"])[0]
            # the basic attack a cast replaces (nothing replaced below level 100: there is no basic attack to lose)
            b_cv = self.branch_multipliers(cv_mastery_boss, 0, cv_targets)[0]
            c_slot = (cv_hits * cv_hit * b_cv) if unlocked("CELESTIAL_VISION") else 0.0
            # True Sight's value to the optimiser = its own damage + the damage-taken debuff it puts on every OTHER row for its duration: (boss damage per second of the other
            # rows at the averaged cast rates, the weights' only use) x duration x pct / (100 + the boss damage-taken term).  Without it the optimiser would never cast True
            # Sight (a single hit is worth less than the swing it replaces) although a player keeps the debuff up.  The debuff's own uptime is set from the engine's cast count below.
            ts_bonus = 0.0
            if unlocked("TRUE_SIGHT"):
                est = 0.0
                cast_rate_est = 0.0
                for _gid, cast, ents in D.STATUS_GROUPS:
                    if cast == "TRUE_SIGHT" or not unlocked(cast):
                        continue
                    cd_c = eff_cooldown(SKILLS[cast]["cooldown"], True)
                    est += sum(base_percast(e[4]) for e in ents) / cd_c
                    cast_rate_est += 1 / cd_c
                if unlocked("EQUINOX_SLASH") and unlocked("EQUINOX_CYCLE"):
                    cast_rate_est += slash_casts / fight_duration
                if unlocked("CELESTIAL_VISION"):
                    est += cv_hits * cv_hit * b_cv * max(0.0, actions_per_second - cast_rate_est)
                term = self.boss_damage + self.monster_dmg_bonus + self.weaken_boss + self.art_boss_damage
                ts_bonus = est * eff_duration(ts_d["duration"]) * ts_pct / (100 + term)

            def percast(key):
                return base_percast(key) + (ts_bonus if (key == "TRUE_SIGHT" and unlocked(key)) else 0.0)
            groups = status_mod.build_groups(D, unlocked, SKILLS, percast, fight.capped_window,
                                             lambda cast: eff_cooldown(SKILLS[cast]["cooldown"], SKILLS[cast]["costs_action"]),
                                             # the stunning skills are cast on cooldown from t = 0 (fixed schedule)
                                             stun_keys={e["key"] for e in D.PLAYER_STUN})
            E_ENGINE = status_mod.solve_groups(self, D, eng_host, groups, c_slot, ENGINE_N, sens)
            E_FS = E_ENGINE["fs"]
            if unlocked("TRUE_SIGHT"):          # the debuff's uptime follows the engine's True Sight casts (spacing >= cooldown, exact last-window truncation)
                n_ts = ENGINE_N["TRUE_SIGHT"]
                self.true_sight_taken_avg = (ts_pct * fight.buff_uptime(SKILLS["TRUE_SIGHT"]["cooldown"], ts_d["duration"], True, casts=n_ts)) if n_ts > 0 else 0.0
                self.monster_dmg_bonus = self.true_sight_taken_avg
        self.e_engine = E_ENGINE

        # ---- Cast rate (subtracted from the basic attack) ----
        cost_action_rows = []
        for key in D.COST_ACTION_ORDER:
            if key in SKILLS:
                cost_action_rows.append((key, SKILLS[key]["cooldown"], True, 1))
            else:
                cost_action_rows.append((key, D.BUFF_COOLDOWNS[key], True, 1))

        def cast_count(k, cd, ca):
            if k in ENGINE_N:
                return ENGINE_N[k]
            if k == "EQUINOX_SLASH":
                return slash_casts
            return fight.exact_casts(eff_cooldown(cd, ca)) if k in D.BUFF_ROW_KEYS else fight.non_buff_casts(eff_cooldown(cd, ca))

        if fixed_duration_active:
            cast_rate = sum(cast_count(k, cd, ca) * aps for k, cd, ca, aps in cost_action_rows if ca and unlocked(k)) / fight_duration
        else:
            cast_rate = sum(((slash_casts if k == "EQUINOX_SLASH" else 1 / eff_cooldown(cd, ca)) * aps) for k, cd, ca, aps in cost_action_rows if ca and unlocked(k))
        self.cast_rate = cast_rate
        self.cv_per_second = cv_per_second = max(0, actions_per_second - cast_rate)

        # ---- Celestial Vision III (basic attack) DPS ----
        cv_unit = cv_hits * cv_hit * cv_per_second
        cv_dps = self.blend_row("CELESTIAL_VISION", cv_unit, cv_unit, cv_mastery_boss, cv_targets) if unlocked("CELESTIAL_VISION") else 0.0
        self.cv_dps = cv_dps
        # Luna Divide: one trigger per basic attack while the Cycle is up
        luna_unit = D.LUNA_HITS * luna_hit * cv_per_second * ec_up
        luna_dps = self.blend_row("LUNA_DIVIDE", luna_unit, luna_unit, 0, luna_targets) if unlocked("LUNA_DIVIDE") else 0.0
        self.luna_dps = luna_dps
        self.luna_targets = luna_targets

        skill_dps = {}
        for key, s in SKILLS.items():
            if not unlocked(key):
                skill_dps[key] = 0.0
                continue
            hd = hits_of[key]
            eff_cd = eff_cooldown(s["cooldown"], s["costs_action"])
            icd, window = s.get("icd"), s.get("window")
            T = fight_duration
            if key == "EQUINOX_SLASH":
                rate = s["hits"] * (slash_casts / T if fixed_duration_active else slash_casts)
            elif status_on and key in ENGINE_N:
                per_cast = s["hits"] * (fight_mod.ticks(fight.capped_window(window), icd) if icd else 1)
                rate = per_cast * (E_FS[key] if key in D.STATUS_FS_KEYS else ENGINE_N[key]) / T * s["share"]
            elif s["boss_only"]:           # Impaling Rays' pierce lands `window` s after the cast: casts whose pierce would fall after the fight ends are lost
                if fixed_duration_active:
                    avail = T - fight.startup_time - window
                    rate = s["hits"] * (fight.exact_casts(eff_cd, avail) if avail >= 0 else 0) / T
                else:
                    rate = s["hits"] / eff_cd
            elif fixed_duration_active:
                rate = fight.non_buff_total_hits(eff_cd, s["hits"], icd, window if icd else None) / T * s["share"]
            else:
                hits = s["hits"] * (fight_mod.ticks(fight.capped_window(window), icd) if icd else 1)
                rate = hits / eff_cd * s["share"]
            if key == "COSMIC_SHOWER":
                skill_dps[key] = self.blend_row(key, rate * hd * s["decay_b"], rate * hd * s["decay_n"], 0, s["targets"])
            elif s["boss_only"]:
                skill_dps[key] = self.blend_row(key, rate * hd, 0.0, s["mastery_boss"], s["targets"], boss_only=True)
            else:
                skill_dps[key] = self.blend_row(key, rate * hd, rate * hd, s["mastery_boss"], s["targets"])
        self.skill_dps = skill_dps
        self.player_dps = cv_dps + luna_dps + sum(skill_dps.values())

        # ---- player's boss-only / normal-only totals (the companion's damage-share weights) ----
        row_dps = [("CELESTIAL_VISION", cv_dps), ("LUNA_DIVIDE", luna_dps)] + list(skill_dps.items())
        self.pb_total, self.pn_total, self.pu_total = self.ledger.split_totals(row_dps, D.STATUS_UNIFORM_ROWS)

        # ---- companion: src/companion_python_model.py fed with this model's own pipeline numbers ----
        self.begin_companion(summon_time_inc)
        if (choice != "None" and c_level >= 1) or pl_on or sens.get("want_comp_host"):
            basic_b, basic_n = self.ledger.pairs.get("CELESTIAL_VISION", (0.0, 0.0))[:2]
            se_full, ec_full = se_attack_full, ec_attack_full
            comp_host = dict(comp_mod.host_common(self, pre, eff, basic_b, basic_n),
                unit=self.hit_damage(100.0, True) / 100, sd=self.skill_damage + self.art_skill_damage, aps=actions_per_second,
                avgbuff=self.attack_bucket_mult, attack_bucket_avg=self.attack_bucket_avg, agg_damage_avg=self.art_joint_damage,
                avgbuff_snap=lambda charm, extra: 1 + (se_full + ec_full + pre.agg_attack_pct - pre.charm_avg + charm + extra) / 100,
                boss_pct=self.boss_damage + self.art_boss_damage + self.monster_dmg_bonus + self.weaken_boss,
                norm_pct=self.normal_damage + self.art_normal_damage + self.monster_dmg_bonus,
                cr_total=self.crit_rate + self.crit_rate_bonus + self.art_crit_rate, cd_total=self.crit_damage + self.crit_damage_bonus,
                def_pen=self.def_pen_eff, taken_bucket=self.art_joint_damage, pst=pst)
            comp_host["bad"] = comp_host["bad"] + self.ec_ba_avg          # Equinox Mastery's Basic Attack Damage (time-averaged) belongs to the basic-attack bucket
            self.comp_host = comp_host
            self.run_companion(comp_host, choice, c_level, summon_time_inc, pl_on)
        self.total_dps = self.player_dps + self.companion_dps

    # ------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _factor(level, idx):
        from ..common import factors
        return factors.get_factor(level, idx)

    def row_dps(self, key):
        if key == "CELESTIAL_VISION":
            return self.cv_dps
        if key == "LUNA_DIVIDE":
            return self.luna_dps
        return self.skill_dps.get(key, 0.0)

    def derived_extra(self):
        return dict(
            basic_attacks_per_second=self.cv_per_second, avg_buff_mult=self.attack_bucket_mult, as_bonus=self.as_bonus,
            attack_bucket_mult=self.attack_bucket_mult, attack_bucket_sum=self.attack_bucket_sum,
            skill_coefficient_base=self.skill_coefficient_base, buff_cast_startup_time=self.buff_cast_startup_time,
            crit_rate_bonus=self.crit_rate_bonus, crit_damage_bonus=self.crit_damage_bonus, final_damage_extra=self.final_damage_extra,
            monster_dmg_bonus=self.monster_dmg_bonus, weaken_boss=self.weaken_boss, def_pen_effective=self.def_pen_eff,
            soul_elemental_uptime=self.se_up, equinox_cycle_uptime=self.ec_up, soul_elemental_attack=self.se_attack_full,
            equinox_cycle_attack=self.ec_attack_full, luna_divide_targets=self.luna_targets, luna_divide_final_damage_pct=self.luna_fd_pct,
            shower_decay_boss=self.shower_decay[0], shower_decay_normal=self.shower_decay[1],
            equinox_window=self.slash_cast_info["window"],
        )


fields, schema, defaults = classapi.make(CLASS_ID, CLASS_NAME, STAT_IDENTITY, _MAIN_STAT_FIELDS, D)
artifact_schema = classapi.artifact_schema


def model(inputs):
    """The evaluated model object (everything ``compute`` reports plus the internals engine/sensitivity.py reads: ``comp_host``, ``e1`` / ``e_engine`` (the timeline strip),
    ``art_effects`` ...).  Same input dict as ``compute``; honours ``inputs["_sens"]`` (engine/common/sens.py)."""
    return _Model(inputs)


def compute(inputs):
    """DPS of one Dawn Warrior setup.  ``inputs``: dict (see module docstring / ``schema()``); returns a JSON-friendly dict:

    total_dps / player_dps / boss_dps / normal_dps / player_boss_dps / player_normal_dps, skills (per damage row: key, name, dps, share, boss_dps, normal_dps, unlocked),
    companion (None or dps/boss/normal/share + model details; choice "None" = the player's stun uplift only), engine_on (Status/KO timeline engine), engine (its cast
    counts and timing factors), derived (ATTACK, STAT_DAMAGE, actions/s, buff uptimes and values, computed Inputs rows ...).
    """
    return _Model(inputs).result()
