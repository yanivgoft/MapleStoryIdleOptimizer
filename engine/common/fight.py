"""Cooldown / duration / exact-cast helpers shared by every class (identical in the FP-Mage, Hero and Shadower verify scripts).

The pure functions take every dependency as an argument; ``Fight`` binds them to one fight (content + Cooldown Decrease + Buff
Duration + PvP length) so a class model can call ``fight.eff_cooldown(cd)`` without threading five parameters through.
"""
import math


def ticks(window, icd):
    """Whole ticks only: a summon / DoT cannot land a fractional hit (mirrors the workbook's INT(window/ICD+1e-9))."""
    return math.floor(window / icd + 1e-9)


def capped_window(window, monster_type, pvp_len):
    """PvP fights last ``pvp_len`` seconds, so a longer summon / DoT window can only tick that long."""
    return min(window, pvp_len) if monster_type == "pvp" else window


def eff_cooldown(cooldown, monster_type, pvp_len, cdr, exempt=False):
    """Effective cooldown.  Skill Cooldown Decrease applies to EVERY real cooldown (user decision 2026-10-21); ``exempt`` marks the
    trigger-rate / internal-interval surrogate rows (the build script's CDR_EXEMPT_ROW_KEYS).  PvP: one cast per fight."""
    if monster_type == "pvp":
        return pvp_len
    return max(0.1, cooldown - (0 if exempt else cdr))


def eff_duration(duration, buff_duration_increase_pct):
    return duration * (1 + buff_duration_increase_pct / 100)


def exact_casts(cooldown, d):
    """Exact number of casts inside a fixed fight of ``d`` seconds: one at t=0, then one every effective cooldown as long as it
    starts before the fight ends."""
    return math.floor(d / cooldown) + 1


def exact_total_hits(cooldown, hits_per_cast, icd, window, d):
    """Exact total tick/hit count across a fixed-duration fight: every cast except the last gets a full window of ticks; the last
    cast's window is truncated to the fight time remaining.  Collapses to casts*hits_per_cast for non-DoT rows (icd falsy)."""
    casts = exact_casts(cooldown, d)
    remaining_after_last = max(0.0, d - (casts - 1) * cooldown)
    if icd:
        full_window_ticks = ticks(window, icd)
        last_cast_ticks = ticks(min(window, remaining_after_last), icd)
    else:
        full_window_ticks = 1
        last_cast_ticks = 1
    return hits_per_cast * ((casts - 1) * full_window_ticks + last_cast_ticks)


def exact_buff_uptime(cooldown, buff_duration, d, casts=None):
    """Exact total buff-active seconds across a fixed fight (same last-cast truncation as exact_total_hits).  ``casts`` = an
    externally decided cast count (the Status/KO timeline engine's), None = the averaged model's own."""
    casts = exact_casts(cooldown, d) if casts is None else casts
    remaining_after_last = max(0.0, d - (casts - 1) * cooldown)
    last_uptime = min(buff_duration, remaining_after_last)
    return (casts - 1) * min(buff_duration, cooldown) + last_uptime


def ramp_avg_gain_pct(duration, per_stack_pct, max_stacks, interval=1.0):
    """Average over ``duration`` s of the compounded gain ``((1 + p)^n - 1) x 100`` of a buff with n stacks (one more every ``interval`` s from t = 0, at most ``max_stacks``)."""
    if duration <= 0:
        return 0.0
    f = 1 + per_stack_pct / 100
    n = min(int(duration // interval), max_stacks)          # whole stacks gained within the window
    total = interval * sum(f ** k for k in range(n)) + (duration - n * interval) * f ** n        # stacks 0..n-1 for one interval each, then n stacks for the rest
    return (total / duration - 1) * 100


class Fight:
    """Bound view of one fight: content timing + the two modifiers that scale cooldowns and buff durations."""

    __slots__ = ("monster_type", "fight_duration", "fixed_duration_active", "pvp_len", "cdr", "bdi", "normal_weight",
                 "max_enemies_hit", "startup_time", "cd_extra_pct")

    def __init__(self, content, pvp_len, cdr, bdi, max_enemies_hit):
        self.monster_type = content.monster_type
        self.fight_duration = content.fight_duration
        self.fixed_duration_active = content.fixed_duration_active
        self.normal_weight = content.normal_weight
        self.pvp_len = pvp_len
        self.cdr = cdr
        self.bdi = bdi
        self.max_enemies_hit = max_enemies_hit
        # Buff-casting startup delay (seconds before the first damage-skill cast); set by the class model once the action rate is known
        self.startup_time = 0.0
        # Extra % cooldown decrease applied multiplicatively AFTER the 0.1 s floor, to every row's effective cooldown (Soul Contract, Chapter Hunt only)
        self.cd_extra_pct = 0.0

    # ---- thin bindings of the pure functions ----
    def capped_window(self, window):
        return capped_window(window, self.monster_type, self.pvp_len)

    def eff_cooldown(self, cooldown, costs_action=None, exempt=False):
        # `costs_action` is kept for call-site compatibility with the verify scripts (CDR no longer depends on it)
        eff = eff_cooldown(cooldown, self.monster_type, self.pvp_len, self.cdr, exempt)
        return eff * (1 - self.cd_extra_pct / 100) if self.cd_extra_pct else eff

    def eff_duration(self, duration):
        return eff_duration(duration, self.bdi)

    def exact_casts(self, cooldown, duration=None):
        return exact_casts(cooldown, self.fight_duration if duration is None else duration)

    def exact_total_hits(self, cooldown, hits_per_cast, icd, window, duration=None):
        return exact_total_hits(cooldown, hits_per_cast, icd, window, self.fight_duration if duration is None else duration)

    def exact_buff_uptime(self, cooldown, buff_duration, casts=None):
        return exact_buff_uptime(cooldown, buff_duration, self.fight_duration, casts)

    def buff_uptime(self, cooldown, duration, costs_action=True, casts=None):
        """Uptime fraction (0..1) of a cast buff: exact in fixed-duration fights, one cast at t=0 in PvP, steady-state ratio capped
        at 100% otherwise."""
        eff_cd = self.eff_cooldown(cooldown, costs_action)
        if self.fixed_duration_active:
            return self.exact_buff_uptime(eff_cd, self.eff_duration(duration), casts) / self.fight_duration
        if self.monster_type == "pvp":
            return min(self.eff_duration(duration), self.pvp_len) / self.pvp_len
        return min(1.0, self.eff_duration(duration) / eff_cd)

    def ramp_avg_gain_pct(self, per_stack_pct, max_stacks, interval=1.0):
        """Average Final Damage % of a buff that gains one stack worth ``per_stack_pct`` every ``interval`` s from the start of the battle up to ``max_stacks`` (Dark Knight's Final
        Pact, Blaze Wizard's Phoenix Run).  Every stack is its own Final Damage factor, so the stacks COMPOUND ((1 + p)^n - 1; user, 2026-11-26: "another 4.8 % every 3 s, that is
        compounding per FD rules", like Arcane Aim).  Timed fights and PvP: the exact average over the fight; continuous hunting: the buff is at its maximum."""
        if self.fixed_duration_active:
            return ramp_avg_gain_pct(self.fight_duration, per_stack_pct, max_stacks, interval)
        if self.monster_type == "pvp":
            return ramp_avg_gain_pct(self.pvp_len, per_stack_pct, max_stacks, interval)
        return ((1 + per_stack_pct / 100) ** max_stacks - 1) * 100

    # ---- damage skills under the buff-casting startup delay ----
    def non_buff_casts(self, cooldown):
        """CastsInFight of a non-buff (damage) skill, reduced by the buff-casting startup delay."""
        if self.startup_time >= self.fight_duration:
            return 0
        return self.exact_casts(cooldown, max(0.0, self.fight_duration - self.startup_time))

    def non_buff_total_hits(self, cooldown, hits_per_cast, icd, window):
        if self.startup_time >= self.fight_duration:
            return 0.0
        return self.exact_total_hits(cooldown, hits_per_cast, icd, window, max(0.0, self.fight_duration - self.startup_time))

    # ---- enemy count ----
    def cap_targets(self, targets):
        """A skill that could hit more targets than are in range only hits what is there (capped before the Breakthrough blend)."""
        return min(targets, self.max_enemies_hit)
