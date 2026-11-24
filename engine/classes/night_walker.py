"""Night Walker (Cygnus Knight, LUK main / DEX sub thief): an ENGINE-NATIVE, PUBLISHED class - no workbook, builder or verify script exists for it.  Its skill SCALING is
confirmed by the user's higher-level in-game readings (character level 128, total skill level 151 / 219 / 279 / 322) and the live site table.

    from engine.classes import night_walker
    result = night_walker.compute(night_walker.defaults("World Boss"))

Built on Dawn Warrior's model (same input dict, same artifacts / companion / Status Effect Damage + KO timeline plumbing, same Sensitivity hooks) with Night Lord's proc rules; the kit comes
from the user's LEVEL-1 and higher-level in-game screenshots (``engine/data/night_walker.py``, ``data/cygnus/night_walker_ingame.md``, every displayed number reproduced by
``tests/golden/test_night_walker_displayed.py``) and the live site table.  ``D.PROVISIONAL`` is empty; every judgement call is flagged in ``D.ROW_NOTES`` and in KNOWN_GAPS.md.

Night Walker specifics:

* **Basic attack = Quintuple Star** (level 100+, absent below like every class).  Quad Star / Lucky Seven / Triple Throw / Shadow Jump are not modelled.
* **Shadow Bat** (20 % per attack per ENEMY HIT, 1 s ICD, any attack) and **Dark Omen**'s bats feed the bat rows (bat attacks, Bat Affinity II's first-attack explosion); **Mark of Darkness** is a
  proc-fed DoT that only exists while Dark Elemental is up (Poisson stack model, closed-form window integral); **Shadow Double** adds 20 % of Quintuple Star's damage while up (mirrors the
  player only, never companions).
* **Timed buffs** (duty-cycle averages, cast on cooldown from t = 0): Dark Elemental (Attack), Darkness Ascending (Attack), Dark Evasion (Final Damage), Shadow Double, Elemental Harmony (Attack
  Speed), Shadow Momentum (stack average from the cast rate: Attack Speed per stack, +10 Attack while up).  Shadow Spark's stun (from Lv49) is the player's own stun for the Status / KO timeline.
* **Always-on passives and stat masteries are NOT added** (the Inputs come from the in-game stat screen, which already contains them): only their Sensitivity level DELTAS are modelled.
"""
import math

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
from ..data import night_walker as D
from .. import artifacts as art_mod
import status_timeline as stl  # noqa: E402  (src/status_timeline.py through the shim)

PUBLISHED = True           # publish gate (CLAUDE.md): the user confirmed the skill scaling with higher-level in-game readings (2026-11-24) and approved publishing

CLASS_ID = "night_walker"
CLASS_NAME = "Night Walker"
STAT_IDENTITY = {"main": "LUK", "sub": "DEX"}

_MAIN_STAT_FIELDS = [
    schema_mod.field("flat_luk", "Flat LUK", "Main stats", "float", "flat", 0, help="Include Main Stat Enhancement's own +30 if unlocked."),
    schema_mod.field("luk_pct", "LUK %", "Main stats", "float", "%", 0),
    schema_mod.field("dex", "DEX", "Main stats", "float", "flat", 0),
]


# ----------------------------------------------------------------------------------------------------------------------------------------------------------
# Poisson helpers (Mark of Darkness stacks, Shadow Momentum stacks)
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
def _tail(M, i):
    """P(Poisson(M) >= i) for i >= 1, summed from the upper tail (no 1 - cdf cancellation for tiny M)."""
    if M <= 0:
        return 0.0
    M = min(M, 500.0)
    p = math.exp(-M)
    top = i + int(M + 10 * math.sqrt(M)) + 40
    total = 0.0
    for k in range(1, top + 1):
        p *= M / k
        if k >= i:
            total += p
    return total


def _emin(M, cap):
    """E[min(N, cap)] for N ~ Poisson(M): the expected number of simultaneously live stacks when at most ``cap`` fit."""
    return sum(_tail(M, j) for j in range(1, int(cap) + 1))


def _window_integrals(lam, d, horizon, cap):
    """ONE Dark Elemental window of length ``d`` s (marks arrive at ``lam`` per second while it is up, each lives ``D.MARK['duration']`` s, at most ``cap`` count), watched for ``horizon`` s:
    (integral of the expected number of live marks, integral of P(at least one live mark)) over time, in closed form: the number of marks that arrived within the last 5 s is
    Poisson(lam x L(t)) with L(t) piecewise linear (ramp up over min(d, 5) s, plateau, ramp down), and  integral_0^M E[min(N_mu, c)] dmu = c M - sum_{j<=c} E[min(N_M, j)]."""
    if lam <= 0 or d <= 0 or horizon <= 0:
        return 0.0, 0.0
    life = D.MARK["duration"]
    d = min(d, horizon)
    a, hi, end = min(d, life), max(d, life), d + life

    def integral(c):
        def phi(x):
            M = lam * x
            return (c * M - sum(_emin(M, j) for j in range(1, c + 1))) / lam
        total = phi(min(horizon, a)) + max(0.0, min(horizon, hi) - a) * _emin(lam * a, c)
        if horizon > hi:
            total += phi(a) - phi(end - min(horizon, end))
        return total
    return integral(int(cap)), integral(1)


def bat_attack_sum(attacks):
    """Sum of the per-attack damage multipliers of one bat: 1, then 25 % LESS than the first per further attack down to a floor of 25 % (1, .75, .5, .25, .25 ...)."""
    return sum(max(D.BAT_ATTACK_FLOOR, 1 - D.BAT_ATTACK_STEP * k) for k in range(attacks))


class _Model(model_mod.ModelBase):
    DATA = D

    # ------------------------------------------------------------------------------------------------------------------
    # ---- curves ----
    def curve_pct(self, key):
        """Scaled value (in %) of a CURVES entry at the character's skill levels."""
        base, fidx, step = D.CURVES[key]
        return self.coeff_pct(base, fidx, fidx is not None, step)

    def tier_key(self, tiers):
        """Key of the last (from level, key) tier the level has reached (None before the first)."""
        pick = None
        for lv, key in tiers:
            if self.level >= lv:
                pick = key
        return pick

    # ---- per-hit pipeline ----
    def hit_damage(self, coeff_pct_val, is_basic, skill_fd_pct=0.0, ba_full=False):
        """Expected damage of one hit.  ``skill_fd_pct``: the row's own Final Damage multiplier (Call of Cygnus / Bat Affinity III / Adaptive Darkness III: 1 + pct/100, the Maple Hero
        convention); ``ba_full``: the row only exists while Shadow Double is up, so its Basic Attack Damage +10 counts at full strength instead of the average."""
        base_damage = self.attack * (coeff_pct_val / 100)
        dmg_reduction = dmg.defense_reduction(self.monster_defense, self.def_pen_eff)
        fd_bucket = self.final_damage + self.final_damage_extra
        final_mult = (1 + fd_bucket / 100) * (1 + self.art_final_damage / 100) * (1 + skill_fd_pct / 100)
        if is_basic:
            source_pct = self.basic_attack_damage + self.art_basic_attack_damage + (self.sd_ba_full if ba_full else self.sd_ba_avg)
        else:
            source_pct = self.skill_damage + self.art_skill_damage
        base_hit = (
            base_damage * (1 + self.stat_damage / 100) * (1 + self.damage / 100)
            * (1 + self.damage_amp / 100) * dmg_reduction * final_mult * (1 + source_pct / 100)
            * self.attack_bucket_mult * (1 + self.art_joint_damage / 100)
        )
        return dmg.expected_hit(base_hit, self.min_damage, self.max_damage, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate,
                                self.crit_damage + self.crit_damage_bonus)

    def skill_hit(self, key, s):
        """Expected damage of one hit of a damage skill (before the boss / normal branch multipliers).  A skill mastery MULTIPLIES the skill's damage (CLAUDE.md bug 2)."""
        pct = self.coeff_pct(s["base"], s["fidx"], True, s["step"]) * (1 + s.get("mastery", 0) / 100)
        return self.hit_damage(pct, False, s.get("cygnus_pct", 0.0))

    # ---- targets and branch blending ----
    def branch_multipliers(self, mastery_boss, mastery_normal, targets):
        """(boss, normal) multiplier of a row; Adaptive Darkness III's Weaken (target damage taken +5 % while it carries a mark) joins each branch's own term."""
        if self.monster_type == "pvp":
            return 1.0 * self.extra_boss, 1.0 * self.extra_norm
        targets = min(targets, self.fight.max_enemies_hit)
        boss_term = self.boss_damage + mastery_boss + self.monster_dmg_bonus + self.weaken_boss + self.art_boss_damage
        normal_term = self.normal_damage + mastery_normal + self.monster_dmg_bonus + self.weaken_norm + self.art_normal_damage
        return (1 + boss_term / 100) * self.extra_boss, (1 + normal_term / 100) * targets * self.extra_norm

    def blend_row(self, key, boss_unit, normal_unit, mastery_boss, targets):
        b, n = self.branch_multipliers(mastery_boss, 0, targets)
        fb, fn = self.timing_factors(key)
        return self.ledger.blend(key, boss_unit, normal_unit, b * fb, n * fn, True)

    # ---- Shadow Bat's roll: once per attack per ENEMY HIT, internal cooldown ----
    def proc_rate(self, chance, icd, sources):
        """(boss / PvP rate, normal rate) of an on-attack proc: X = sum(attacks/s x P(at least one of the N enemies hit rolls a success)), rate = X / (1 + ICD x X).  Boss: N = 1."""
        cap = self.fight.max_enemies_hit
        x_boss = chance * sum(r for r, _ in sources)
        x_norm = sum(r * dmg.q_roll(chance, min(t, cap)) for r, t in sources)
        return x_boss / (1 + icd * x_boss), x_norm / (1 + icd * x_norm)

    # ---- Mark of Darkness: Poisson stack model over the Dark Elemental windows ----
    def window_rates(self, lam):
        """(live mark-seconds per second = ticks per second, share of time with at least one mark) of ONE enemy for ``lam`` marks per second while Dark Elemental is up."""
        if lam <= 0:
            return 0.0, 0.0
        fight, m = self.fight, self.mark_max
        life, tick = D.MARK["duration"], D.MARK["tick"]
        d, cd = self.de_window, self.de_cd_eff
        if fight.monster_type == "pvp":                        # one cast at t = 0 in a fight of ``pvp_len`` s
            T = fight.pvp_len
            a, b = _window_integrals(lam, d, T, m)
            return a / tick / T, b / T
        if d >= cd:                                            # windows overlap: Dark Elemental is up the whole time, the stack count is stationary
            M = lam * life
            return self.de_up * _emin(M, m) / tick, self.de_up * (1 - math.exp(-M))
        if fight.fixed_duration_active:
            T = fight.fight_duration
            n = fight.exact_casts(cd)
            a1, b1 = _window_integrals(lam, d, 1e9, m)
            a2, b2 = _window_integrals(lam, d, T - (n - 1) * cd, m)
            return ((n - 1) * a1 + a2) / tick / T, ((n - 1) * b1 + b2) / T
        a1, b1 = _window_integrals(lam, d, 1e9, m)
        return a1 / tick / cd, b1 / cd

    def mark_model(self, sources):
        """The mark statistics for the attack ``sources`` = [(attacks/s, targets of the attack)]: boss / PvP branch (one enemy) and normal branch (every enemy in range, the attacks
        spread over them).  -> dict(boss_ticks, boss_any, norm_ticks (summed over the enemies), norm_any (per enemy))."""
        out = dict(boss_ticks=0.0, boss_any=0.0, norm_ticks=0.0, norm_any=0.0, boss_lam=0.0, norm_lam=0.0)
        if not (self.unlocked("MARK_OF_DARKNESS") and sources):
            return out
        chance = D.MARK["chance"] / 100
        mult = D.MARK["chance_normal_mult"][1] if self.level >= D.MARK["chance_normal_mult"][0] else 1.0
        c_norm = min(1.0, chance * mult)
        cap = max(1, self.fight.max_enemies_hit)
        lam_b = chance * sum(r for r, _ in sources)
        lam_n = c_norm * sum(r * min(t, cap) / cap for r, t in sources)         # marks per second landing on ONE of the ``cap`` enemies
        tb, ab = self.window_rates(lam_b)
        tn, an = self.window_rates(lam_n)
        out.update(boss_ticks=tb, boss_any=ab, norm_ticks=cap * tn, norm_any=an, boss_lam=lam_b, norm_lam=lam_n)
        return out

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
        self.attack = dmg.attack_value(flat_attack, attack_pct + sens.get("attack_mult_delta", 0.0))      # (+ Spirit Projection's / Vitality Siphon's level delta, Sensitivity only: baked into Inputs!attack_pct)
        if sens.get("mainstat_attack_delta"):      # Sensitivity: the main/sub stat's flat-Attack channel (bug 7), applied before ATTACK%
            self.attack += sens["mainstat_attack_delta"] * (1 + attack_pct / 100)
        flat_luk, luk_pct, dex_stat = inp("flat_luk"), inp("luk_pct"), inp("dex")
        self.stat_damage = (flat_luk * (1 + luk_pct / 100)) * 0.01 + dex_stat * 0.0025
        self.damage = inp("damage")
        self.damage_amp = inp("damage_amp")
        self.boss_damage = inp("boss_damage") + sens.get("boss_damage_delta", 0.0)      # (+ Enveloping Darkness' level delta, Sensitivity only)
        self.normal_damage = inp("normal_damage")
        self.status_effect_damage = status_effect_damage = inp("status_effect_damage")
        self.final_damage = inp("final_damage")
        if sens.get("final_damage_factor") is not None:
            # Sensitivity: a baked-in Final Damage artifact what-if is a factor on the TYPED value inside the additive bucket (``baked_fd_form="typed"``, as Dawn Warrior / Hero)
            self.final_damage = ((1 + self.final_damage / 100) * sens["final_damage_factor"] - 1) * 100
        self.min_damage = inp("min_damage") + sens.get("min_damage_delta", 0.0)      # (+ Throwing Mastery's level delta, Sensitivity only)
        self.max_damage = inp("max_damage") + sens.get("max_damage_delta", 0.0)      # (+ Throwing Expert's level delta / Athena's Gloves' dependent Max Damage, Sensitivity only)
        self.crit_rate_input = inp("crit_rate") + sens.get("crit_rate_threshold_extra", 0.0)
        self.crit_rate = self.crit_rate_input + sens.get("crit_rate_delta", 0.0)      # (+ Critical Throw's level delta, Sensitivity only)
        self.crit_damage = inp("crit_damage")
        attack_speed_base = inp("attack_speed")
        def_pen = sens_mod.def_pen_with_dose(inp("def_pen") + sens.get("def_pen_delta", 0.0), sens)      # (+ Dark Blessing's level delta, Sensitivity only)
        self.def_pen_eff = def_pen
        self.basic_attack_damage = inp("basic_attack_damage") + sens.get("basic_attack_damage_delta", 0.0)   # (+ Physical Training's level delta, Sensitivity only)
        self.skill_damage = inp("skill_damage") + sens.get("skill_damage_delta", 0.0)      # (+ Throwing Expert's level delta, Sensitivity only)
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

        # ---- curves of the scaled effects ----
        self.skill_coefficient_base = self.curve_pct("QUINTUPLE_STAR")

        # ---- level-resolved cooldown rows (static part: cooldowns, targets, Call of Cygnus) ----
        SKILLS = self.skills = {}
        for key, t in D.DAMAGE_SKILLS.items():
            base, fidx, step = D.CURVES[t["curve"]]
            s = dict(step=step, cooldown=self.haste(t["cooldown"], t.get("haste")), hits=t["hits"], base=base, fidx=fidx, mastery=gated(t["mastery"]),
                     mastery_boss=0, costs_action=t["costs_action"], targets=t["targets"], cast_row=t.get("cast_row", key))
            s["cygnus_pct"] = self.curve_pct(t["cygnus"]) if ("cygnus" in t and unlocked("CALL_OF_CYGNUS")) else 0.0
            SKILLS[key] = s
        self.normal_targets = {k: v["targets"] for k, v in SKILLS.items()}

        # ---- timed buffs: uptimes (cast on cooldown from t = 0, duty-cycle averages; Buff Duration Increase extends them) ----
        de, da, dev, sdb, eh = D.DARK_ELEMENTAL, D.DARKNESS_ASCENDING, D.DARK_EVASION, D.SHADOW_DOUBLE, D.ELEMENTAL_HARMONY
        de_dur = de["duration"] * (de["duration_mastery"][1] if level >= de["duration_mastery"][0] else 1.0)
        da_cd = self.haste(da["cooldown"], da.get("haste"))
        dev_dur = dev["duration"] * (dev["duration_mastery"][1] if level >= dev["duration_mastery"][0] else 1.0)
        sd_dur = sdb["duration"] * (sdb["duration_mastery"][1] if level >= sdb["duration_mastery"][0] else 1.0)
        self.de_window = eff_duration(de_dur)
        self.de_cd_eff = eff_cooldown(de["cooldown"], True)
        self.de_up = de_up = fight.buff_uptime(de["cooldown"], de_dur, True) if unlocked("DARK_ELEMENTAL") else 0.0
        self.da_up = da_up = fight.buff_uptime(da_cd, da["duration"], True) if unlocked("DARKNESS_ASCENDING") else 0.0
        self.dev_up = dev_up = fight.buff_uptime(dev["cooldown"], dev_dur, True) if unlocked("DARK_EVASION") else 0.0
        self.sd_up = sd_up = fight.buff_uptime(sdb["cooldown"], sd_dur, True) if unlocked("SHADOW_DOUBLE") else 0.0
        eh_up = fight.buff_uptime(eh["cooldown"], eh["duration"], True) if unlocked("ELEMENTAL_HARMONY") else 0.0

        self.de_attack_full = de_attack_full = self.curve_pct("DARK_ELEMENTAL_ATTACK") if unlocked("DARK_ELEMENTAL") else 0.0
        self.da_attack_full = da_attack_full = self.curve_pct("DARKNESS_ASCENDING_ATTACK") if unlocked("DARKNESS_ASCENDING") else 0.0
        self.dev_fd_full = dev_fd_full = self.curve_pct("DARK_EVASION_FD") if unlocked("DARK_EVASION") else 0.0
        eh_as_avg = self.curve_pct("ELEMENTAL_HARMONY_AS") * eh_up if unlocked("ELEMENTAL_HARMONY") else 0.0

        # Shadow Double: Basic Attack Damage +10 (Lv68) while up - the average on Quintuple Star, full strength on the clone's own row
        self.sd_ba_full = float(sdb["ba_mastery"][1]) if (unlocked("SHADOW_DOUBLE") and level >= sdb["ba_mastery"][0]) else 0.0
        self.sd_ba_avg = self.sd_ba_full * sd_up
        self.sd_frac = self.curve_pct("SHADOW_DOUBLE_SHARE") / 100 if unlocked("SHADOW_DOUBLE") else 0.0

        # Shadow Momentum: every skill activation (an action-costing cooldown cast) adds a stack for 2 s (max 5).  Casts arrive at the steady-state rate; each stack lives 2 s on its own,
        # so the live count is Poisson(2 x rate) capped at 5 (M/G/inf): Attack Speed x mean stacks, Attack +10 while at least one stack is up.
        cd_of = dict(SHADOW_SPARK=SKILLS["SHADOW_SPARK"]["cooldown"], SHADOW_STITCH=SKILLS["SHADOW_STITCH"]["cooldown"], DARK_OMEN=D.DARK_OMEN["cooldown"],
                     DARK_ELEMENTAL=de["cooldown"], DARKNESS_ASCENDING=da_cd, DARK_EVASION=dev["cooldown"], SHADOW_DOUBLE=sdb["cooldown"], ELEMENTAL_HARMONY=eh["cooldown"])
        self.cd_of = cd_of
        activation_rate = sum(1 / eff_cooldown(cd_of[k], True) for k in D.COST_ACTION_ORDER if unlocked(k))
        sm = D.SHADOW_MOMENTUM
        sm_mean = sm_any = 0.0
        if unlocked("SHADOW_MOMENTUM"):
            M_sm = sm["duration"] * activation_rate
            sm_mean = _emin(M_sm, sm["max_stacks"])
            sm_any = 1 - math.exp(-M_sm)
        self.momentum_stacks = sm_mean
        self.momentum_up = sm_any
        mom_as_avg = self.curve_pct("SHADOW_MOMENTUM_AS") * sm_mean if unlocked("SHADOW_MOMENTUM") else 0.0
        mom_attack_full = float(sm["attack_mastery"][1]) if (unlocked("SHADOW_MOMENTUM") and level >= sm["attack_mastery"][0]) else 0.0
        mom_attack_avg = mom_attack_full * sm_any

        de_attack_avg, da_attack_avg = de_attack_full * de_up, da_attack_full * da_up
        self.attack_bucket_sum = attack_bucket_sum = de_attack_avg + da_attack_avg + mom_attack_avg
        self.attack_bucket_avg = attack_bucket_sum + pre.agg_attack_pct
        self.attack_bucket_mult = 1 + self.attack_bucket_avg / 100

        self.crit_rate_bonus = 0.0
        self.crit_damage_bonus = 0.0
        self.final_damage_extra = dev_fd_full * dev_up + sens.get("final_damage_delta", 0.0)      # (+ Dark Blessing's level delta, Sensitivity only)
        self.monster_dmg_bonus = 0.0
        self.weaken_boss = self.weaken_norm = 0.0

        # ---- Attack Speed: Elemental Harmony + Shadow Momentum's average stacks (additive bonus side of the diminishing returns) ----
        self.as_bonus = as_bonus = eh_as_avg + mom_as_avg
        self.actions_per_second = actions_per_second = dmg.actions_per_second(attack_speed_base + sens.get("attack_speed_extra", 0.0), as_bonus)

        # ---- Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`) ----
        choice, c_level = comp_mod.read_choice(inp)
        self.companion_choice, self.companion_level = choice, c_level
        pl_active = [e for e in D.PLAYER_STUN if unlocked(e["key"]) and level >= e["min_level"]]
        pl_on = bool(pl_active)
        self.pl_on = pl_on
        stun_info = comp_mod.stun_probe(ct, fight, pvp_len, choice, c_level, summon_time_inc)
        hasstun = bool(stun_info and stun_info.get("hasstun")) or pl_on
        ko = content_mod.ko_windows(fight_duration)
        self.status_on = status_on = fixed_duration_active and normal_weight == 0 and (content_type in ko or hasstun)
        startup_count = sum(1 for k in D.STARTUP_BUFFS if unlocked(k))
        t0_pl = 0.0 if status_on else ((startup_count / actions_per_second) if fixed_duration_active else 0.0)
        self.pst = pst = [dict(id=e["id"], typ=e["typ"], cd=eff_cooldown(SKILLS[e["key"]]["cooldown"], True), dur=e["dur"], p=e["p"],
                               on=unlocked(e["key"]) and level >= e["min_level"], t0=t0_pl, tick=e["tick"], win=e["win"]) for e in D.PLAYER_STUN]
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
                            A0=attack_bucket_sum + pre.a0, charm_v=pre.charm_val, hex_avg=pre.hex_avg, c_slot=0.0, stun=stun_vec, buffs=[], groups=[])
            e1 = sens["strip"][0] if "strip" in sens else stl.solve(eng_host)   # pass 1 (no engine-timed buff: only the constant Attack% term and the windows)
            self.attack_bucket_mult = e1["Bbuff_mean"]
        self.e1 = e1

        # Buff-Casting Startup Delay: in fixed-duration fights the character casts every unlocked, actively cast buff sequentially at fight start before the first damage-skill cast.
        self.buff_cast_startup_time = (startup_count / actions_per_second) if (fixed_duration_active and not status_on) else 0.0
        fight.startup_time = self.buff_cast_startup_time

        # ---- artifact effects (full) ----
        actx.aps, actx.startup = actions_per_second, self.buff_cast_startup_time
        s0, w0, d_comp, period, ts_window = comp_mod.horn_window(actx, monster_type, fight_duration, pvp_len, summon_time_inc, stun_pin, choice, c_level)
        dw = art_mod.damage_weights(fight_duration, pre.hex_v, attack_bucket_sum + pre.a0, pre.charm_val, e1["mult"] if status_on else None)
        actx.horn_uptime = art_mod.horn_flute_uptime(actx, dw, s0, w0, d_comp, period, ts_window)
        actx.crit_rate = self.crit_rate + self.crit_rate_bonus
        eff = self.art_effects = art_mod.Effects(eq, actx, pre)
        self.art_crit_rate = eff.agg_crit_rate
        self.crit_damage_bonus = eff.agg_crit_damage
        self.crit_damage_bonus += sens.get("crit_damage_delta", 0.0)              # (Sensitivity: Critical Throw's level delta / Book of Ancient's dependent Crit Damage while Crit Rate is swept)
        self.crit_damage_bonus += sens_mod.boa_crit_damage_delta(sens, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate)
        self.crit_rate_total = self.crit_rate + self.crit_rate_bonus + self.art_crit_rate
        self.art_boss_damage, self.art_normal_damage = eff.agg_boss_damage + sens.get("boss_damage_extra", 0.0), eff.agg_normal_damage
        self.art_final_damage = eff.agg_final_damage
        self.art_joint_damage = eff.agg_damage + eff.agg_enemy_dmg_taken
        self.art_skill_damage, self.art_basic_attack_damage = eff.agg_skill_damage, eff.agg_basic_attack_damage
        self.extra_boss, self.extra_norm = eff.extras(actx, self.monster_defense, self.def_pen_eff,
                                                      self.crit_rate + self.crit_rate_bonus + self.art_crit_rate, self.crit_damage + self.crit_damage_bonus)
        self.ph_b, self.ph_n = art_mod.phase_state_ratios(content_type, fight_duration, pre.hex_v, pre.hex_avg, self.attack_bucket_avg, pre.charm_val, pre.charm_avg)

        # ---- Quintuple Star (basic attack): its own damage chain + boss chain, hits, targets ----
        qs_mastery = gated(D.QS_MASTERY)
        self.qs_mastery_boss = qs_mastery_boss = gated(D.QS_BOSS_MASTERY)
        qs_pct = self.skill_coefficient_base * (1 + qs_mastery / 100)
        qs_targets = 6 + basic_attack_target_increase
        h0, hl, h1 = D.QS_HITS
        qs_hits = h1 if level >= hl else h0
        qs_hit = self.hit_damage(qs_pct, True)

        # ---- per-row hit damage of the cooldown rows ----
        hits_of = {key: self.skill_hit(key, s) for key, s in SKILLS.items()}

        self.mark_max = D.MARK["max_stacks"] + sum(n for lv, n in D.MARK["stacks"] if level >= lv)

        # ---- the attacks that roll Shadow Bat / Mark of Darkness: (rate per second, targets) of Quintuple Star and the action-costing damage skills ----
        def steady_rate(k):
            return 1 / eff_cooldown(cd_of[k], True)

        def sources_for(qs_ps, rate_of):
            src = []
            if unlocked("QUINTUPLE_STAR"):
                src.append((qs_ps, qs_targets))
            src += [(rate_of(k), SKILLS[k]["targets"]) for k in D.TRIGGER_ROWS if unlocked(k)]
            return src

        def set_weaken(marks):
            wk_lvl, wk_pct = D.MARK["weaken"]
            if unlocked("ADAPTIVE_DARKNESS_III") and level >= wk_lvl:
                self.weaken_boss, self.weaken_norm = wk_pct * marks["boss_any"], wk_pct * marks["norm_any"]
            else:
                self.weaken_boss = self.weaken_norm = 0.0

        if status_on and unlocked("MARK_OF_DARKNESS"):
            # the engine's cast weights need the Weaken term, which needs the attack rates, which need the engine's casts: pre-estimate it with the steady-state rates
            est_cast_rate = sum(steady_rate(k) for k in D.COST_ACTION_ORDER if unlocked(k))
            set_weaken(self.mark_model(sources_for(max(0.0, actions_per_second - est_cast_rate), steady_rate)))

        # ---- Status/KO engine pass 2: the damage skills' casts (weight of one cast = its boss damage before any timing factor) ----
        E_ENGINE = None
        if status_on:
            def percast(key):
                if not unlocked(key):
                    return 0.0
                sk = SKILLS[key]
                return sk["hits"] * hits_of[key] * self.branch_multipliers(sk.get("mastery_boss", 0), 0, sk["targets"])[0]
            b_qs = self.branch_multipliers(qs_mastery_boss, 0, qs_targets)[0]
            c_slot = (qs_hits * qs_hit * b_qs) if unlocked("QUINTUPLE_STAR") else 0.0
            groups = status_mod.build_groups(D, unlocked, SKILLS, percast, fight.capped_window,
                                             lambda cast: eff_cooldown(SKILLS[cast]["cooldown"], SKILLS[cast]["costs_action"]),
                                             stun_keys={e["key"] for e in pl_active})      # a stunning skill is cast on cooldown from t = 0 (fixed schedule)
            E_ENGINE = status_mod.solve_groups(self, D, eng_host, groups, c_slot, ENGINE_N, sens)
            E_FS = E_ENGINE["fs"]
        self.e_engine = E_ENGINE

        # ---- Cast rate (subtracted from the basic attack) ----
        def cast_count(k):
            if k in ENGINE_N:
                return ENGINE_N[k]
            cd_eff = eff_cooldown(cd_of[k], True)
            return fight.exact_casts(cd_eff) if k in D.BUFF_ROW_KEYS else fight.non_buff_casts(cd_eff)

        def cast_rate_of(k):
            return (cast_count(k) / fight_duration) if fixed_duration_active else steady_rate(k)

        self.cast_rate = cast_rate = sum(cast_rate_of(k) for k in D.COST_ACTION_ORDER if unlocked(k))
        self.qs_per_second = qs_per_second = max(0, actions_per_second - cast_rate)

        # ---- the trigger sources and the Mark of Darkness model (final rates) ----
        sources = sources_for(qs_per_second, cast_rate_of)
        self.trigger_sources = sources
        marks = self.mark_model(sources)
        self.marks = marks
        set_weaken(marks)

        # ---- Quintuple Star (basic attack) DPS ----
        qs_unit = qs_hits * qs_hit * qs_per_second
        self.qs_dps = qs_dps = self.blend_row("QUINTUPLE_STAR", qs_unit, qs_unit, qs_mastery_boss, qs_targets) if unlocked("QUINTUPLE_STAR") else 0.0

        # ---- Shadow Double: the clone's extra 20 % x factor of Quintuple Star's damage while up (Basic Attack Damage +10 at full strength: it only exists then) ----
        sd_hit = self.hit_damage(qs_pct, True, ba_full=True) * self.sd_frac
        sd_unit = qs_hits * sd_hit * qs_per_second * sd_up
        self.sd_dps = sd_dps = (self.blend_row("SHADOW_DOUBLE", sd_unit, sd_unit, qs_mastery_boss, qs_targets)
                                if (unlocked("SHADOW_DOUBLE") and unlocked("QUINTUPLE_STAR")) else 0.0)

        # ---- the cooldown rows ----
        skill_dps = {}
        for key, s in SKILLS.items():
            if not unlocked(key):
                skill_dps[key] = 0.0
                continue
            eff_cd = eff_cooldown(s["cooldown"], s["costs_action"])
            T = fight_duration
            if status_on and key in ENGINE_N:
                rate = s["hits"] * ENGINE_N[key] / T
            elif fixed_duration_active:
                rate = fight.non_buff_total_hits(eff_cd, s["hits"], None, None) / T
            else:
                rate = s["hits"] / eff_cd
            skill_dps[key] = self.blend_row(key, rate * hits_of[key], rate * hits_of[key], s["mastery_boss"], s["targets"])

        # ---- Shadow Bat (attack proc, 1 s ICD) + Dark Omen's bats ----
        bat_proc_b = bat_proc_n = 0.0
        if unlocked("SHADOW_BAT"):
            sp = D.SHADOW_BAT_PROC
            chance = (sp["chance"] + (sp["chance_mastery"][1] if level >= sp["chance_mastery"][0] else 0)) / 100
            bat_proc_b, bat_proc_n = self.proc_rate(chance, sp["icd"], sources)
        om = D.DARK_OMEN
        omen_bats_per_cast = omen_rate = 0.0
        if unlocked("DARK_OMEN"):
            interval = om["interval_mastery"][1] if level >= om["interval_mastery"][0] else om["interval"]
            omen_bats_per_cast = fight_mod.ticks(fight.capped_window(om["window"]), interval) + (om["burst"][1] if level >= om["burst"][0] else 0)
            omen_rate = cast_rate_of("DARK_OMEN")
        omen_bats = omen_rate * omen_bats_per_cast
        bats_b, bats_n = (bat_proc_b + omen_bats if unlocked("SHADOW_BAT") else 0.0), (bat_proc_n + omen_bats if unlocked("SHADOW_BAT") else 0.0)
        self.bat_rates = dict(proc_boss=bat_proc_b, proc_normal=bat_proc_n, omen=omen_bats, boss=bats_b, normal=bats_n)

        bat_tier = self.tier_key(D.BAT_TIERS)
        ba_ = D.BAT_ATTACKS
        bat_attacks = ba_["base"] + (ba_["bat_affinity"] if unlocked("BAT_AFFINITY") else 0) + (ba_["mastery"][1] if level >= ba_["mastery"][0] else 0)
        self.bat_attacks = bat_attacks
        self.bat_sum = bat_sum = bat_attack_sum(bat_attacks)
        bat_pct = (self.curve_pct(bat_tier) * (1 + (D.BAT_DAMAGE_MASTERY[1] / 100 if level >= D.BAT_DAMAGE_MASTERY[0] else 0.0))) if bat_tier else 0.0
        bat_cyg = self.curve_pct("CALL_OF_CYGNUS_BAT") if unlocked("CALL_OF_CYGNUS") else 0.0
        bat_hit = self.hit_damage(bat_pct, False, bat_cyg)
        self.bat_dps = bat_dps = (self.blend_row("SHADOW_BAT", bats_b * bat_sum * bat_hit, bats_n * bat_sum * bat_hit, 0, 1)
                                  if unlocked("SHADOW_BAT") else 0.0)

        # ---- Bat Affinity II: the first attack of every bat explodes (also Dark Omen's) ----
        ex = D.BAT_EXPLOSION
        ex_targets = ex["targets"] + (ex["targets_mastery"][1] if level >= ex["targets_mastery"][0] else 0)
        ex_pct = self.curve_pct("BAT_AFFINITY_II_EXPLOSION") * (1 + (ex["mastery"][1] / 100 if level >= ex["mastery"][0] else 0.0))
        ex_fd = (self.curve_pct("BAT_AFFINITY_III_FD") * (ex["boost"][1] if level >= ex["boost"][0] else 1.0)) if unlocked("BAT_AFFINITY_III") else 0.0
        self.bat_explosion_fd_pct = ex_fd
        ex_hit = self.hit_damage(ex_pct, False, ex_fd)
        self.explosion_targets = ex_targets
        self.explosion_dps = explosion_dps = (self.blend_row("BAT_EXPLOSION", bats_b * ex_hit, bats_n * ex_hit, 0, ex_targets)
                                              if (unlocked("BAT_EXPLOSION") and unlocked("SHADOW_BAT")) else 0.0)

        # ---- Mark of Darkness: ticks per second of the live marks ----
        mk = D.MARK
        mark_tier = self.tier_key(D.MARK_TIERS)
        mark_pct = (self.curve_pct(mark_tier) * (1 + (mk["mastery"][1] / 100 if (level >= mk["mastery"][0] and mark_tier == "ADAPTIVE_DARKNESS_II") else 0.0))) if mark_tier else 0.0
        mark_fd = (self.curve_pct("ADAPTIVE_DARKNESS_III_FD") * (mk["boost"][1] if level >= mk["boost"][0] else 1.0)) if unlocked("ADAPTIVE_DARKNESS_III") else 0.0
        self.mark_fd_pct = mark_fd
        mark_hit = self.hit_damage(mark_pct, False, mark_fd)
        self.mark_hit_pct = mark_pct
        self.mark_dps = mark_dps = (self.blend_row("MARK_OF_DARKNESS", marks["boss_ticks"] * mark_hit, marks["norm_ticks"] * mark_hit, 0, 1)
                                    if unlocked("MARK_OF_DARKNESS") else 0.0)

        skill_dps["SHADOW_BAT"] = bat_dps
        skill_dps["BAT_EXPLOSION"] = explosion_dps
        skill_dps["MARK_OF_DARKNESS"] = mark_dps
        self.skill_dps = skill_dps
        self.player_dps = qs_dps + sd_dps + sum(skill_dps.values())

        # ---- player's boss-only / normal-only totals (the companion's damage-share weights) ----
        row_dps = [("QUINTUPLE_STAR", qs_dps), ("SHADOW_DOUBLE", sd_dps)] + list(skill_dps.items())
        self.pb_total, self.pn_total, self.pu_total = self.ledger.split_totals(row_dps, D.STATUS_UNIFORM_ROWS)

        # ---- companion: src/companion_python_model.py fed with this model's own pipeline numbers ----
        self.begin_companion(summon_time_inc)
        if (choice != "None" and c_level >= 1) or pl_on or sens.get("want_comp_host"):
            basic_b, basic_n = self.ledger.pairs.get("QUINTUPLE_STAR", (0.0, 0.0))[:2]
            snap_full = de_attack_full + da_attack_full + mom_attack_full
            comp_host = dict(comp_mod.host_common(self, pre, eff, basic_b, basic_n),
                # the Shadow Double clone mirrors only the player's own attacks (its row is separate): the companion's unit is the plain Quintuple Star hit
                unit=self.hit_damage(100.0, True) / 100, sd=self.skill_damage + self.art_skill_damage, aps=actions_per_second,
                avgbuff=self.attack_bucket_mult, attack_bucket_avg=self.attack_bucket_avg, agg_damage_avg=self.art_joint_damage,
                avgbuff_snap=lambda charm, extra: 1 + (snap_full + pre.agg_attack_pct - pre.charm_avg + charm + extra) / 100,
                boss_pct=self.boss_damage + self.art_boss_damage + self.monster_dmg_bonus + self.weaken_boss,
                norm_pct=self.normal_damage + self.art_normal_damage + self.monster_dmg_bonus + self.weaken_norm,
                cr_total=self.crit_rate + self.crit_rate_bonus + self.art_crit_rate, cd_total=self.crit_damage + self.crit_damage_bonus,
                def_pen=self.def_pen_eff, taken_bucket=self.art_joint_damage, pst=pst)
            comp_host["bad"] = comp_host["bad"] + self.sd_ba_avg          # Shadow Double's Basic Attack Damage (time-averaged) belongs to the basic-attack bucket the unit carries
            self.comp_host = comp_host
            self.run_companion(comp_host, choice, c_level, summon_time_inc, pl_on)
        self.total_dps = self.player_dps + self.companion_dps

    # ------------------------------------------------------------------------------------------------------------------
    def row_dps(self, key):
        if key == "QUINTUPLE_STAR":
            return self.qs_dps
        if key == "SHADOW_DOUBLE":
            return self.sd_dps
        return self.skill_dps.get(key, 0.0)

    def derived_extra(self):
        m = self.marks
        return dict(
            basic_attacks_per_second=self.qs_per_second, avg_buff_mult=self.attack_bucket_mult, as_bonus=self.as_bonus,
            attack_bucket_mult=self.attack_bucket_mult, attack_bucket_sum=self.attack_bucket_sum,
            skill_coefficient_base=self.skill_coefficient_base, buff_cast_startup_time=self.buff_cast_startup_time,
            crit_rate_bonus=self.crit_rate_bonus, crit_damage_bonus=self.crit_damage_bonus, final_damage_extra=self.final_damage_extra,
            monster_dmg_bonus=self.monster_dmg_bonus, weaken_boss=self.weaken_boss, weaken_normal=self.weaken_norm, def_pen_effective=self.def_pen_eff,
            dark_elemental_uptime=self.de_up, darkness_ascending_uptime=self.da_up, dark_evasion_uptime=self.dev_up, shadow_double_uptime=self.sd_up,
            shadow_double_share=self.sd_frac, shadow_momentum_mean_stacks=self.momentum_stacks, shadow_momentum_uptime=self.momentum_up,
            dark_elemental_attack=self.de_attack_full, darkness_ascending_attack=self.da_attack_full, dark_evasion_final_damage=self.dev_fd_full,
            shadow_bat_attacks=self.bat_attacks, shadow_bat_attack_sum=self.bat_sum, shadow_bat_rates=dict(self.bat_rates),
            bat_explosion_targets=self.explosion_targets, bat_explosion_final_damage_pct=self.bat_explosion_fd_pct,
            mark_max_stacks=self.mark_max, mark_damage_pct=self.mark_hit_pct, mark_final_damage_pct=self.mark_fd_pct,
            mark_ticks_per_second_boss=m["boss_ticks"], mark_ticks_per_second_normal=m["norm_ticks"], mark_marked_share_boss=m["boss_any"],
            mark_marked_share_normal=m["norm_any"], attack_rates=[[r, t] for r, t in self.trigger_sources],
        )


fields, schema, defaults = classapi.make(CLASS_ID, CLASS_NAME, STAT_IDENTITY, _MAIN_STAT_FIELDS, D)
artifact_schema = classapi.artifact_schema


def model(inputs):
    """The evaluated model object (everything ``compute`` reports plus the internals engine/sensitivity.py reads: ``comp_host``, ``e1`` / ``e_engine`` (the timeline strip),
    ``art_effects`` ...).  Same input dict as ``compute``; honours ``inputs["_sens"]`` (engine/common/sens.py)."""
    return _Model(inputs)


def compute(inputs):
    """DPS of one Night Walker setup.  ``inputs``: dict (see module docstring / ``schema()``); returns a JSON-friendly dict:

    total_dps / player_dps / boss_dps / normal_dps / player_boss_dps / player_normal_dps, skills (per damage row: key, name, dps, share, boss_dps, normal_dps, unlocked),
    companion (None or dps/boss/normal/share + model details; choice "None" = the player's stun uplift only), engine_on (Status/KO timeline engine), engine (its cast
    counts and timing factors), derived (ATTACK, STAT_DAMAGE, actions/s, buff uptimes and values, computed Inputs rows ...).
    """
    return _Model(inputs).result()
