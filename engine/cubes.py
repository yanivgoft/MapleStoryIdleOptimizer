"""Potential Cubes optimizer: the exact optimal-stopping core of ``src/potential_cubes_ev.py`` as pure functions (no workbook, no CLI).

    from engine import cubes
    pricing = cubes.pricing_from_sensitivity(sens_result, inputs)        # FP-Mage: engine.sensitivity.run(...) result + the compute inputs
    pricing = cubes.Pricing.from_dict({...})                              # any other class: priced directly (see Pricing)
    rows = cubes.recommend(gear_rows, pricing)                            # one dict per (slot, potential type) = one row of the script's CSV

``gear_rows``: list of ``{"slot", "potential_type", "rarity", "pity", "lines": [(stat, value) x 3]}`` (the PotentialCubes sheet; ``cubes.default_gear()``
lists the 15 slots x {Potential, Bonus Potential} at normal / pity 0 / no lines).  Per row the result carries what the CSV does: ``current_value``
(+ ``_pct``), ``smallest_n`` (first cube count with positive EV), ``n_for_50pct`` / ``n_for_75pct`` (cubes for that chance that AT LEAST ONE reroll beats
the current value), ``milestone_ev`` / ``milestone_ev_pct`` (EV at the 24 cube counts ``CUBE_MILESTONES``), rows ordered like the CSV (Potential first,
then Bonus Potential, each by ``smallest_n`` ascending, never-positive last).

Methodology = the script's (see its docstring): every cube re-rolls all 3 lines, so the decision value is the optimal-stopping value
``W_k(tier, pity)`` solved by backward induction (``E[max(roll, W_{k-1})]`` with the tier-upgrade pity mechanic), the per-roll distribution comes
from the full line1 x line2 x line3 enumeration (``combined_dps_gain``: same-stat lines add, different stats multiply), Skill Cooldown Decrease is priced
from the CDR milestone curve and Companion Summoning Time from the companion model (both step functions).  The engine reproduces the script's numerics
(golden: ``tests/golden/test_cubes.py``, rel 1e-9) - it is a re-implementation, not an import, because the script loads a workbook at import time.

Two backends with the same algorithm: numpy (the script's own vectorised form; used when numpy is importable) and pure Python (bisect loops;
``backend="python"``).  numpy is optional and used ONLY in this module.  Timing (30 rows, 1000 cubes, all starting at `normal`): see engine/README.md.

Data: ``data/cube_potential_data.json`` (roll tables, pity caps: Potential and Bonus Potential have SEPARATE caps - CLAUDE.md item 17) plus the slot
specials the builder hand-adds (``SLOT_SPECIAL_BLOCKS`` below, a copy of ``build_fp_mage_workbook.py``'s; ``tests/golden/test_cubes.py`` checks the
resulting roll table against the builder's ``CubeData`` rows).
"""
import bisect
import itertools
import json
import math
from pathlib import Path

try:  # optional: the numpy backend (same algorithm as the script); the engine package stays stdlib-only otherwise
    import numpy as _np
except ImportError:  # pragma: no cover
    _np = None

REPO_ROOT = Path(__file__).resolve().parent.parent
CUBE_DATA_JSON = REPO_ROOT / "data" / "cube_potential_data.json"

MAX_CUBES = 1000
CUBE_MILESTONES = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 125, 150, 175, 200, 250, 300, 400, 500, 1000]
RARITY_ORDER = ["normal", "rare", "epic", "unique", "legendary", "mystic"]
POTENTIAL_TYPES = ("Potential", "Bonus Potential")
CUBE_SLOTS = ["head", "cape", "chest", "shoulders", "legs", "belt", "gloves", "boots",
              "ring", "neck", "eye-accessory", "ring2", "face", "earrings", "pocket"]
SLOT_SPECIFIC_KEY = {"shoulders": "shoulder", "neck": "necklace"}      # CUBE_SLOTS id -> the JSON's own slot id
CDR_STAT = "Skill Cooldown Decrease (seconds)"
COMPANION_STAT = "Companion Summoning Time Increase %"
NONE_STAT = "(none)"
CSV_COLUMNS = (["Slot", "PotentialType", "Rarity", "Pity", "CurrentValue", "CurrentValue%", "SmallestNPositive", "NFor50PctChance", "NFor75PctChance"]
               + [f"EV@{n}" for n in CUBE_MILESTONES] + [f"EV%@{n}" for n in CUBE_MILESTONES])

# Slot specials the builder hand-adds on top of the JSON (stat, {tier: value}); every slot special is rolled the same way (_slot_specific_tier_block)
SLOT_SPECIAL_BLOCKS = {
    "ring2": ("Basic Attack Damage %", {"epic": 8, "unique": 14, "legendary": 21, "mystic": 30}),
    "face": ("Final Damage %", {"epic": 3, "unique": 5, "legendary": 8, "mystic": 12}),
    "earrings": ("Skill Damage %", {"epic": 8, "unique": 14, "legendary": 21, "mystic": 30}),
    "ring": ("All Skill Level", {"epic": 5, "unique": 8, "legendary": 12, "mystic": 16}),
    "necklace": ("All Skill Level", {"epic": 5, "unique": 8, "legendary": 12, "mystic": 16}),
    "head": (CDR_STAT, {"epic": 0.5, "unique": 1, "legendary": 1.5, "mystic": 2}),
    "chest": ("Basic Attack Target Increase", {"unique": 1, "legendary": 2, "mystic": 3}),            # no epic option (user-confirmed)
    "belt": ("Buff Duration Increase %", {"epic": 5, "unique": 8, "legendary": 12, "mystic": 20}),
    "boots": (COMPANION_STAT, {"epic": 5, "unique": 8, "legendary": 12, "mystic": 20}),
    "eye-accessory": ("Main Stat Per Level", {"epic": 10, "unique": 20, "legendary": 35, "mystic": 50}),
    "pocket": ("Main Stat % per 4 Levels", {"epic": 0.4, "unique": 0.6, "legendary": 0.8, "mystic": 1.2}),
}
# stats a character may already have equipped although they are not in the roll table (they stay selectable in the sheet's dropdown)
EXTRA_SELECTABLE_STATS = (CDR_STAT, "Buff Duration Increase %")


def _slot_special_block(stat, values_by_tier):
    """Port of the builder's ``_slot_specific_tier_block``: {tier: {line1/2/3: [entries]}}; the first tier present has no non-prime fallback."""
    out = {}
    tiers = [t for t in RARITY_ORDER if t in values_by_tier]
    for i, tier in enumerate(tiers):
        value = values_by_tier[tier]
        block = {"line1": [{"stat": stat, "value": value, "weight": 1, "prime": True}]}
        if i == 0:
            block["line2"] = [{"stat": stat, "value": value, "weight": 0.24, "prime": True}]
            block["line3"] = [{"stat": stat, "value": value, "weight": 0.08, "prime": True}]
        else:
            prev = values_by_tier[tiers[i - 1]]
            block["line2"] = [{"stat": stat, "value": value, "weight": 0.24, "prime": True}, {"stat": stat, "value": prev, "weight": 0.76, "prime": False}]
            block["line3"] = [{"stat": stat, "value": value, "weight": 0.08, "prime": True}, {"stat": stat, "value": prev, "weight": 0.92, "prime": False}]
        out[tier] = block
    return out


_DATA = None


def _load_data():
    """(rarity upgrade rates {potential type: {rarity: {rate, max}}}, roll table {(slot, rarity, line): [(stat, value, weight)]}, all stat names)."""
    global _DATA
    if _DATA is None:
        data = json.loads(CUBE_DATA_JSON.read_text())
        rates = data["RARITY_UPGRADE_RATES"]
        generic = data["EQUIPMENT_POTENTIAL_DATA"]
        specific = dict(data["SLOT_SPECIFIC_POTENTIALS"])
        for slot, (stat, values) in SLOT_SPECIAL_BLOCKS.items():
            specific[slot] = _slot_special_block(stat, values)
        table = {}
        for rarity in RARITY_ORDER:                         # the generic pool, shared by every slot
            for line in (1, 2, 3):
                for e in generic[rarity][f"line{line}"]:
                    table.setdefault(("ALL", rarity, line), []).append((e["stat"], float(e["value"]), float(e["weight"])))
        for slot in CUBE_SLOTS:                             # + the slot's own additions
            block = specific.get(SLOT_SPECIFIC_KEY.get(slot, slot))
            if not block:
                continue
            for rarity, lines in block.items():
                for line_name, entries in lines.items():
                    for e in entries:
                        table.setdefault((slot, rarity, int(line_name[-1])), []).append((e["stat"], float(e["value"]), float(e["weight"])))
        stats = sorted({s for entries in table.values() for s, _v, _w in entries} | set(EXTRA_SELECTABLE_STATS))
        _DATA = (rates, table, stats)
    return _DATA


def rarity_rates():
    """{potential type: {rarity: {"next", "rate", "max"}}} (max = pity cap: the cube count that forces the upgrade)."""
    return _load_data()[0]


def roll_table():
    """{(slot | "ALL", rarity, line): [(stat, value, weight)]} - what the workbook's CubeData A:G rows hold (same order)."""
    return _load_data()[1]


def all_potential_stats():
    """Every stat name that can sit on a potential line (the workbook's CubeData!J dropdown, without the leading "(none)")."""
    return list(_load_data()[2])


def default_gear():
    """The PotentialCubes sheet's blank state: every slot x potential type at ``normal``, pity 0, no lines."""
    return [dict(slot=s, potential_type=t, rarity="normal", pity=0, lines=[(NONE_STAT, 0.0)] * 3) for s in CUBE_SLOTS for t in POTENTIAL_TYPES]


# ----------------------------------------------------------------------------------------------------------------------------------------------
# pricing
# ----------------------------------------------------------------------------------------------------------------------------------------------
class CompanionPricing:
    """Companion Summoning Time Increase % pricing: ``run(inc)`` is the companion model at a TOTAL summoning time ``inc`` (a callable returning a dict with
    ``comp_boss_dps`` / ``comp_norm_dps``), ``b0`` = the Inputs value WITHOUT the summoning-time lines listed on the gear, ``w`` = normal-branch time weight,
    ``player_boss`` / ``player_norm`` = the player's boss-only / normal-only DPS.  ``factor(extra, base)`` = relative growth of ``extra`` % on top of ``base`` %
    (above b0), each branch's own growth blended by w - never dollar totals."""

    def __init__(self, run, b0, w, player_boss, player_norm, total=None, current_blend=None):
        self._run, self.b0, self.w = run, float(b0), float(w)
        self.player_boss, self.player_norm = float(player_boss), float(player_norm)
        self.total, self.current_blend = total, current_blend
        self._cache = {}

    def at(self, x):
        key = round(float(x), 6)
        if key not in self._cache:
            self._cache[key] = self._run(self.b0 + key)
        return self._cache[key]

    def factor(self, extra, base):
        pb, pn, w = self.player_boss, self.player_norm, self.w
        rb, rx = self.at(base), self.at(base + extra)
        boss = (pb + rx["comp_boss_dps"]) / (pb + rb["comp_boss_dps"]) if pb + rb["comp_boss_dps"] > 0 else 1.0
        norm = (pn + rx["comp_norm_dps"]) / (pn + rb["comp_norm_dps"]) if pn + rb["comp_norm_dps"] > 0 else 1.0
        return (1 - w) * boss + w * norm


class Pricing:
    """What a stat is worth, for one character state (the workbook's CubeData!J:K + Sensitivity CDR table + Companion sheet).

    ``baseline_dps``  current Total DPS.
    ``dps_per_unit``  {stat name: DPS gained per +1 unit}: potential-line stat names; unlisted / ``"(none)"`` = 0.  Class-specific rules (Main Stat Per Level x level, Critical
                      Rate at the 100% cap priced as Critical Damage, ...) are already baked in - ``dps_per_unit_table`` builds it from Sensitivity rates.
    ``cdr_current``   Inputs Skill Cooldown Decrease (s), already includes the CDR on the gear.
    ``cdr_table``     [(cdr seconds, Total DPS)] from the CDR milestone sweep (None = linear +1 s rate); the (cdr_current, baseline_dps) point is added.
    ``cdr_exact``     optional callable(cdr) -> Total DPS, used once per value when a row's CDR baseline falls below the table's first step (None = +1 s rate).
    ``companion``     optional CompanionPricing (None = linear rate of ``dps_per_unit["Companion Summoning Time Increase %"]``).
    """

    def __init__(self, baseline_dps, dps_per_unit, cdr_current=0.0, cdr_table=None, cdr_exact=None, companion=None):
        self.baseline_dps = float(baseline_dps)
        self.dps_per_unit = dict(dps_per_unit)
        self.cdr_current = float(cdr_current)
        self.cdr_exact = cdr_exact
        self.companion = companion
        self.cdr_points = None
        if cdr_table:
            pts = {float(x): float(t) for x, t in cdr_table}
            pts[self.cdr_current] = self.baseline_dps       # the live model state is exact, wherever it falls on the grid
            self.cdr_points = sorted(pts.items())

    @classmethod
    def from_dict(cls, d):
        """``{"baseline_dps", "dps_per_unit", "cdr_current", "cdr_table": [[x, total], ...] | None}`` (no companion / exact-CDR callables)."""
        return cls(d["baseline_dps"], d["dps_per_unit"], d.get("cdr_current", 0.0), d.get("cdr_table"))


def as_pricing(p):
    return p if isinstance(p, Pricing) else Pricing.from_dict(p)


# ----------------------------------------------------------------------------------------------------------------------------------------------
# the optimizer
# ----------------------------------------------------------------------------------------------------------------------------------------------
class CubeModel:
    """One pricing + one roll table: roll distributions (cached), the optimal-stopping trace and the improvement-probability chain."""

    def __init__(self, pricing, backend=None, rates=None, table=None):
        self.pricing = as_pricing(pricing)
        self.rates = rates if rates is not None else rarity_rates()
        self.table = table if table is not None else roll_table()
        if backend is None:
            backend = "numpy" if _np is not None else "python"
        if backend == "numpy" and _np is None:
            raise RuntimeError("numpy backend requested but numpy is not installed")
        self.backend = backend
        self.cdr_points = [tuple(p) for p in self.pricing.cdr_points] if self.pricing.cdr_points else None
        self._cdr_exact_failed = set()
        self.notes = set()
        self._dist_cache = {}
        self._prep_cache = {}

    # ---- pricing of lines -------------------------------------------------------------------------------------------------
    def dps_per_unit(self, stat):
        return self.pricing.dps_per_unit.get(stat, 0.0)

    def cdr_total_dps(self, cdr):
        """Total DPS at a TOTAL Skill Cooldown Decrease: piecewise-linear through the table; beyond the top step the last slope continues; below the first
        step (one row holding all of the character's CDR) the model is re-evaluated once (``pricing.cdr_exact``), else the +1 s rate is used."""
        pts = self.cdr_points
        xs = [x for x, _ in pts]
        if cdr < xs[0] and not any(abs(cdr - x) < 1e-9 for x in xs):
            exact = self._exact_total_at_cdr(cdr)
            if exact is not None:
                pts.append((float(cdr), exact))
                pts.sort()
                return self.cdr_total_dps(cdr)
        if cdr <= xs[0]:
            if cdr < xs[0]:
                self.notes.add("below")
            return max(0.0, pts[0][1] - (xs[0] - cdr) * self.pricing.dps_per_unit.get(CDR_STAT, 0.0))
        if cdr >= xs[-1]:
            if cdr > xs[-1]:
                self.notes.add("above")
            (x0, t0), (x1, t1) = pts[-2], pts[-1]
            return t1 + (cdr - x1) * max(0.0, (t1 - t0) / (x1 - x0))
        i = bisect.bisect_right(xs, cdr)
        (x0, t0), (x1, t1) = pts[i - 1], pts[i]
        return t0 + (t1 - t0) * (cdr - x0) / (x1 - x0)

    def _exact_total_at_cdr(self, cdr):
        fn = self.pricing.cdr_exact
        if fn is None or cdr in self._cdr_exact_failed:
            return None
        self._cdr_exact_failed.add(cdr)         # cleared again on success, so a failure is only ever attempted once
        try:
            value = fn(cdr)
        except Exception:                       # fall back to the +1 s rate rather than failing the whole run
            return None
        if value is None:
            return None
        self._cdr_exact_failed.discard(cdr)
        return float(value)

    def cdr_factor(self, extra_cdr, baseline_cdr):
        if self.cdr_points is None:             # no milestone table: the linear +1 s rate
            return 1.0 + extra_cdr * self.pricing.dps_per_unit.get(CDR_STAT, 0.0) / self.pricing.baseline_dps
        base = self.cdr_total_dps(baseline_cdr)
        return self.cdr_total_dps(baseline_cdr + extra_cdr) / base if base > 0 else 1.0

    def row_cdr_baseline(self, state):
        """Total CDR the character would have WITHOUT this row's own current CDR lines (note when the lines exceed the Inputs CDR)."""
        own = sum(v for stat, v in state["lines"] if stat == CDR_STAT)
        if own > self.pricing.cdr_current + 1e-9:
            self.notes.add(f"cdr_lines_exceed_inputs:{state['slot']}/{state['potential_type']}")
        return max(0.0, self.pricing.cdr_current - own)

    @staticmethod
    def row_companion_base(state, all_rows):
        """Summoning time (%) on every OTHER row's current lines, i.e. what stays equipped while this row is rerolled."""
        return sum(v for other in all_rows if other is not state for stat, v in other["lines"] if stat == COMPANION_STAT)

    def combined_dps_gain(self, stat_value_pairs, cdr_baseline=None, companion_base=0.0):
        """Absolute DPS delta of a set of lines: same-stat lines add before any DPS math, different stats multiply (1.01 x 1.01 - 1), CDR via the milestone
        curve on top of ``cdr_baseline`` (default: all current CDR), Companion Summoning Time via the companion model on top of ``companion_base``."""
        grouped = {}
        for stat, value in stat_value_pairs:
            if not stat or stat == NONE_STAT:
                continue
            grouped[stat] = grouped.get(stat, 0.0) + value
        base = self.pricing.baseline_dps
        factor = 1.0
        for stat, total_value in grouped.items():
            if stat == CDR_STAT:
                factor *= self.cdr_factor(total_value, self.pricing.cdr_current if cdr_baseline is None else cdr_baseline)
            elif stat == COMPANION_STAT and self.pricing.companion is not None:
                factor *= self.pricing.companion.factor(total_value, companion_base)
            else:
                factor *= 1.0 + (total_value * self.dps_per_unit(stat)) / base
        return base * (factor - 1.0)

    def current_value(self, lines, cdr_baseline=None, companion_base=0.0):
        return self.combined_dps_gain(lines, cdr_baseline, companion_base)

    # ---- one roll's distribution ------------------------------------------------------------------------------------------
    def _line_pools(self, rarity, slot):
        pools = []
        for line in (1, 2, 3):
            entries = list(self.table.get(("ALL", rarity, line), [])) + list(self.table.get((slot, rarity, line), []))
            total = sum(w for _, _, w in entries)
            pools.append([(stat, v, w / total) for stat, v, w in entries])
        return pools

    def roll_distribution(self, rarity, slot, cdr_baseline=None, companion_base=0.0):
        """(values ascending, cdf) of one roll's combined DPS value at (rarity, slot): the full line1 x line2 x line3 enumeration collapsed by identical
        value.  Lines on distinct, plainly priced stats take a precomputed-factor fast path (bit-identical to ``combined_dps_gain``)."""
        key = (rarity, slot, None if cdr_baseline is None else round(cdr_baseline, 6), round(companion_base, 6))
        hit = self._dist_cache.get(key)
        if hit is not None:
            return hit
        base = self.pricing.baseline_dps
        comp_live = self.pricing.companion is not None

        def special(stat):
            return stat == CDR_STAT or (stat == COMPANION_STAT and comp_live)

        def prep(pool):
            # (stat, value, p, term, special?)  term = the stat's factor when it stands alone: 1.0 + (0.0 + v) * rate / baseline
            return [(s, v, p, 1.0 + ((0.0 + v) * self.dps_per_unit(s)) / base if (s and s != NONE_STAT and not special(s)) else None, special(s) or not s or s == NONE_STAT)
                    for s, v, p in pool]
        p1, p2, p3 = (prep(p) for p in self._line_pools(rarity, slot))
        gen = self.combined_dps_gain
        combos = {}
        get = combos.get
        for s1, v1, w1, t1, sp1 in p1:
            for s2, v2, w2, t2, sp2 in p2:
                pair_fast = not (sp1 or sp2 or s1 == s2)
                pre = 1.0 * t1 * t2 if pair_fast else None
                w12 = w1 * w2
                for s3, v3, w3, t3, sp3 in p3:
                    if pair_fast and not sp3 and s3 != s1 and s3 != s2:
                        v = base * (pre * t3 - 1.0)
                    else:
                        v = gen([(s1, v1), (s2, v2), (s3, v3)], cdr_baseline, companion_base)
                    combos[v] = get(v, 0.0) + w12 * w3
        values = sorted(combos)
        cdf = list(itertools.accumulate(combos[v] for v in values))
        cdf[-1] = 1.0  # guard against float drift so F(v) is exactly 1 at the top of the support
        self._dist_cache[key] = (values, cdf)
        return values, cdf

    # ---- tier tables ----------------------------------------------------------------------------------------------------
    def _tail_tables(self, rarity, slot, cdr_baseline, companion_base):
        """(values, tail_prob, tail_exp) of a tier's roll distribution: tail_prob[i] = P(roll >= values[i]), tail_exp[i] = E[roll 1{roll >= values[i]}], 0 appended."""
        key = ("tail", rarity, slot, None if cdr_baseline is None else round(cdr_baseline, 6), round(companion_base, 6), self.backend)
        hit = self._prep_cache.get(key)
        if hit is None:
            values, cdf = self.roll_distribution(rarity, slot, cdr_baseline, companion_base)
            probs = [cdf[0] - 0.0] + [cdf[i] - cdf[i - 1] for i in range(1, len(cdf))]
            tp = list(itertools.accumulate(reversed(probs)))[::-1] + [0.0]
            te = list(itertools.accumulate(v * p for v, p in zip(reversed(values), reversed(probs))))[::-1] + [0.0]
            if self.backend == "numpy":
                hit = (_np.array(values), _np.array(tp), _np.array(te))
            else:
                hit = (values, tp, te)
            self._prep_cache[key] = hit
        return hit

    # ---- optimal stopping (backward induction) -----------------------------------------------------------------------------
    def optimal_stopping_trace(self, start_rarity, start_pity, slot, current_value, potential_type, max_cubes=MAX_CUBES, cdr_baseline=None, companion_base=0.0):
        """trace[k] = max(current_value, W_k(start tier, start pity)) = the value held after optimally spending up to k cubes (trace[0] = current_value)."""
        rates = self.rates[potential_type]
        tiers = RARITY_ORDER[RARITY_ORDER.index(start_rarity):]
        tails = [self._tail_tables(t, slot, cdr_baseline, companion_base) for t in tiers]
        start_bucket = min(max(int(start_pity), 0), max(int(rates[start_rarity]["max"]), 1) - 1) if start_rarity != tiers[-1] else 0
        if self.backend == "numpy":
            return self._trace_numpy(tiers, tails, rates, start_bucket, current_value, max_cubes)
        return self._trace_python(tiers, tails, rates, start_bucket, current_value, max_cubes)

    @staticmethod
    def _trace_numpy(tiers, tails, rates, start_bucket, current_value, max_cubes):
        np = _np

        def emax(tail, c):
            values, tail_prob, tail_exp = tail
            idx = np.searchsorted(values, c, side="right")
            surv_prob, surv_exp = tail_prob[idx], tail_exp[idx]
            with np.errstate(invalid="ignore"):
                general = c + (surv_exp - c * surv_prob)
            return np.where(np.isneginf(c), surv_exp, general)      # c=-inf: no continuation, forced to accept this roll
        n_t = len(tiers)
        W_prev = [np.full(max(int(rates[t]["max"]), 1), -np.inf) for t in tiers]
        trace = np.empty(max_cubes + 1)
        trace[0] = current_value
        for k in range(1, max_cubes + 1):
            W_cur = []
            for ti, t in enumerate(tiers):
                if ti == n_t - 1 or rates[t]["max"] <= 0:
                    W_cur.append(emax(tails[ti], W_prev[ti]))
                    continue
                rate, max_pity = rates[t]["rate"], int(rates[t]["max"])
                n = len(W_prev[ti])
                prob_upgrade = np.where(np.arange(n) + 1 >= max_pity, 1.0, rate)
                c_stay = np.empty(n)
                c_stay[:-1] = W_prev[ti][1:]
                c_stay[-1] = -np.inf
                e_stay = emax(tails[ti], c_stay)
                e_up = emax(tails[ti + 1], W_prev[ti + 1][0:1])[0]
                W_cur.append((1 - prob_upgrade) * e_stay + prob_upgrade * e_up)
            W_prev = W_cur
            trace[k] = max(current_value, W_prev[0][start_bucket])
        return trace.tolist()

    @staticmethod
    def _trace_python(tiers, tails, rates, start_bucket, current_value, max_cubes):
        br = bisect.bisect_right
        n_t = len(tiers)
        info = []
        for ti, t in enumerate(tiers):
            terminal = ti == n_t - 1 or rates[t]["max"] <= 0
            n = max(int(rates[t]["max"]), 1)
            info.append((terminal, n, rates[t]["rate"]))
        trace = [0.0] * (max_cubes + 1)
        trace[0] = current_value
        # k = 1: W_0 = -inf everywhere, E[max(roll, -inf)] = E[roll] = tail_exp[0]
        W_prev = []
        for ti in range(n_t):
            terminal, n, rate = info[ti]
            e = tails[ti][2][0]
            if terminal:
                W_prev.append([e] * n)
            else:
                e_up = tails[ti + 1][2][0]
                W_prev.append([(1 - (rate if i + 1 < n else 1.0)) * e + (rate if i + 1 < n else 1.0) * e_up for i in range(n)])
        trace[1] = max(current_value, W_prev[0][start_bucket])
        for k in range(2, max_cubes + 1):
            W_cur = []
            for ti in range(n_t):
                terminal, n, rate = info[ti]
                V, TP, TE = tails[ti]
                wp = W_prev[ti]
                if terminal:
                    out = []
                    ap = out.append
                    for c in wp:
                        j = br(V, c)
                        ap(c + (TE[j] - c * TP[j]))
                    W_cur.append(out)
                    continue
                Vn, TPn, TEn = tails[ti + 1]
                c = W_prev[ti + 1][0]
                j = br(Vn, c)
                e_up = c + (TEn[j] - c * TPn[j])
                keep, up = 1 - rate, rate * e_up
                out = []
                ap = out.append
                for i in range(n - 1):              # the last bucket is the forced upgrade: W = e_up exactly
                    c = wp[i + 1]
                    j = br(V, c)
                    ap(keep * (c + (TE[j] - c * TP[j])) + up)
                ap(e_up)
                W_cur.append(out)
            W_prev = W_cur
            v = W_prev[0][start_bucket]
            trace[k] = v if v > current_value else current_value
        return trace

    @staticmethod
    def smallest_n_positive(trace, current_value):
        """First cube count whose EV is positive (the optimal-stopping value never decreases with more cubes), None if never within the trace."""
        for k in range(1, len(trace)):
            if trace[k] > current_value:
                return k
        return None

    # ---- P(at least one roll beats the current value within N cubes) -------------------------------------------------------
    def roll_beat_probability(self, rarity, slot, current_value, cdr_baseline=None, companion_base=0.0):
        values, cdf = self.roll_distribution(rarity, slot, cdr_baseline, companion_base)
        idx = bisect.bisect_right(values, current_value) - 1
        return 1.0 - (cdf[idx] if idx >= 0 else 0.0)

    def probability_any_better_roll(self, start_rarity, start_pity, slot, current_value, potential_type, max_cubes=MAX_CUBES, cdr_baseline=None, companion_base=0.0):
        """prob_any[k] = P(some one of the first k rerolls beats ``current_value``): an absorbing chain over (tier, pity) - tier-upgrade timing does not
        depend on roll outcomes - with every cube checked against the ORIGINAL value (no continuation value)."""
        rates = self.rates[potential_type]
        tiers = RARITY_ORDER[RARITY_ORDER.index(start_rarity):]
        n_t = len(tiers)
        p = [self.roll_beat_probability(t, slot, current_value, cdr_baseline, companion_base) for t in tiers]
        sizes = [max(int(rates[t]["max"]), 1) for t in tiers]
        terminal = [ti == n_t - 1 or rates[t]["max"] <= 0 for ti, t in enumerate(tiers)]
        start_bucket = min(max(int(start_pity), 0), sizes[0] - 1) if not terminal[0] else 0
        prob_any = [0.0] * (max_cubes + 1)
        if self.backend == "numpy":
            np = _np
            surv = [np.zeros(s) for s in sizes]
            surv[0][start_bucket] = 1.0
            for k in range(1, max_cubes + 1):
                new = [np.zeros_like(a) for a in surv]
                for ti in range(n_t):
                    arr = surv[ti]
                    if terminal[ti]:
                        new[ti][0] += float(arr.sum()) * (1 - p[ti])
                        continue
                    rate, max_pity = rates[tiers[ti]]["rate"], int(rates[tiers[ti]]["max"])
                    prob_upgrade = np.where(np.arange(len(arr)) + 1 >= max_pity, 1.0, rate)
                    stay_mass, upgrade_mass = arr * (1 - prob_upgrade), arr * prob_upgrade
                    new[ti][1:] += (stay_mass * (1 - p[ti]))[:-1]
                    new[ti + 1][0] += float(np.sum(upgrade_mass * (1 - p[ti + 1])))
                surv = new
                prob_any[k] = 1.0 - sum(float(a.sum()) for a in surv)
            return prob_any
        surv = [[0.0] * s for s in sizes]
        surv[0][start_bucket] = 1.0
        for k in range(1, max_cubes + 1):
            new = [[0.0] * s for s in sizes]
            total = 0.0
            for ti in range(n_t):
                arr = surv[ti]
                if terminal[ti]:
                    new[ti][0] += math.fsum(arr) * (1 - p[ti])
                    continue
                rate = rates[tiers[ti]]["rate"]
                n = len(arr)
                f = (1 - rate) * (1 - p[ti])
                dst = new[ti]
                dst[1:n] = [x * f for x in arr[:n - 1]]                  # += onto zeros (the previous tier's upgrade mass only ever lands on bucket 0)
                up = (math.fsum(arr[:n - 1]) * rate + arr[n - 1]) * (1 - p[ti + 1])
                new[ti + 1][0] += up
            for ti in range(n_t):
                total += math.fsum(new[ti])
            surv = new
            prob_any[k] = 1.0 - total
        return prob_any

    @staticmethod
    def smallest_n_for_probability(prob_any, threshold):
        for k in range(1, len(prob_any)):
            if prob_any[k] >= threshold:
                return k
        return None


# ----------------------------------------------------------------------------------------------------------------------------------------------
# recommendations
# ----------------------------------------------------------------------------------------------------------------------------------------------
def _normalise_row(row):
    lines = []
    for ln in list(row.get("lines") or [])[:3]:
        stat, val = (ln["stat"], ln.get("value")) if isinstance(ln, dict) else ln
        lines.append((stat if stat else NONE_STAT, float(val) if val is not None else 0.0))
    while len(lines) < 3:
        lines.append((NONE_STAT, 0.0))
    return dict(slot=row["slot"], potential_type=row.get("potential_type", "Potential"), rarity=row.get("rarity", "normal"),
                pity=float(row.get("pity") or 0), lines=lines)


def recommend(gear_rows, pricing, milestones=None, max_cubes=MAX_CUBES, backend=None, include_trace=False, sort=True, model=None, only=None):
    """One result row per gear row, the script's CSV columns: ``current_value`` / ``current_value_pct``, ``smallest_n``, ``n_for_50pct``, ``n_for_75pct``,
    ``milestone_ev`` {n: EV} and ``milestone_ev_pct`` {n: EV as % of the current Total DPS} (+ ``trace`` with ``include_trace``).  Rows are ordered like the CSV
    unless ``sort=False``.  ``milestones`` default ``CUBE_MILESTONES`` (each must be <= ``max_cubes``).  ``only``: compute just some rows - a set of indices
    into ``gear_rows`` or a callable(row dict) -> bool; the other rows still count for the cross-row baselines (summoning time on the OTHER rows)."""
    milestones = list(CUBE_MILESTONES if milestones is None else milestones)
    if max(milestones, default=0) > max_cubes:
        raise ValueError("every milestone must be <= max_cubes")
    model = model or CubeModel(pricing, backend=backend)
    base = model.pricing.baseline_dps
    rows = [_normalise_row(r) for r in gear_rows]
    out = []
    for idx, state in enumerate(rows):
        if only is not None and not (only(state) if callable(only) else idx in only):
            continue
        if state["potential_type"] not in model.rates:
            raise ValueError(f"unknown potential type {state['potential_type']!r}")
        if state["rarity"] not in RARITY_ORDER:
            raise ValueError(f"unknown rarity {state['rarity']!r}")
        cbase = model.row_companion_base(state, rows)
        cdr_base = model.row_cdr_baseline(state)
        cur = model.current_value(state["lines"], cdr_base, cbase)
        trace = model.optimal_stopping_trace(state["rarity"], state["pity"], state["slot"], cur, state["potential_type"], max_cubes, cdr_base, cbase)
        prob_any = model.probability_any_better_roll(state["rarity"], state["pity"], state["slot"], cur, state["potential_type"], max_cubes, cdr_base, cbase)
        ev = {n: trace[n] - cur for n in milestones}
        row = dict(state, lines=[list(x) for x in state["lines"]], current_value=cur, current_value_pct=cur / base * 100 if base else 0.0,
                   smallest_n=model.smallest_n_positive(trace, cur), n_for_50pct=model.smallest_n_for_probability(prob_any, 0.5),
                   n_for_75pct=model.smallest_n_for_probability(prob_any, 0.75), milestone_ev=ev,
                   milestone_ev_pct={n: (v / base * 100 if base else 0.0) for n, v in ev.items()})
        if include_trace:
            row["trace"] = list(trace)
            row["prob_any"] = list(prob_any)
        out.append(row)
    if sort:
        order = {"Potential": 0, "Bonus Potential": 1}
        out.sort(key=lambda r: (order.get(r["potential_type"], 2), r["smallest_n"] if r["smallest_n"] is not None else float("inf")))
    return out


def csv_row(row, milestones=None):
    """A result row in the script's CSV column order (``CSV_COLUMNS``)."""
    ms = list(CUBE_MILESTONES if milestones is None else milestones)
    return ([row["slot"], row["potential_type"], row["rarity"], row["pity"], row["current_value"], row["current_value_pct"],
             row["smallest_n"], row["n_for_50pct"], row["n_for_75pct"]] + [row["milestone_ev"][n] for n in ms] + [row["milestone_ev_pct"][n] for n in ms])


def companion_lines_pct(gear_rows):
    """Total Companion Summoning Time Increase % on the gear's current lines (feed it to ``sensitivity.run`` as ``companion_potential_lines_pct``: the
    summoning-time baseline b0 excludes exactly these lines)."""
    return sum(float(v or 0) for r in gear_rows for ln in (r.get("lines") or []) for stat, v in [(ln["stat"], ln.get("value")) if isinstance(ln, dict) else ln]
               if stat == COMPANION_STAT)


# ----------------------------------------------------------------------------------------------------------------------------------------------
# stat -> DPS-per-unit table (CubeData!J:K) and the adapter from engine.sensitivity
# ----------------------------------------------------------------------------------------------------------------------------------------------
# potential-line stat name -> Sensitivity sweep key (FP-Mage: INT main stat; Str / Dex / Luk lines and the other unmodelled stats are worth 0).  Other
# classes map their own main stat (their builder's POTENTIAL_STAT_TO_SWEEP_KEY / POTENTIAL_SUB_STAT_PCT_LINES): pass ``stat_to_key``.
POTENTIAL_STAT_TO_SWEEP_KEY = {
    "Critical Rate %": "crit_rate", "Critical Damage %": "crit_damage", "Attack Speed %": "attack_speed", "Damage %": "damage",
    "Final Damage %": "final_damage", "Min Damage Multiplier %": "min_damage", "Max Damage Multiplier %": "max_damage",
    "Defense Penetration": "def_pen", "Basic Attack Damage %": "basic_attack_damage", "Skill Damage %": "skill_damage",
    "Skill Cooldown Decrease (seconds)": "skill_cooldown_decrease", "Buff Duration Increase %": "buff_duration_increase_pct",
    "All Skill Level": "skill_lvl_all", "Basic Attack Target Increase": "basic_attack_target_increase", "Int %": "int_pct", "Int": "flat_int",
}


def dps_per_unit_table(rates, level=0, crit_rate_total=0.0, ring_of_cycles_equipped=False, book_of_ancient_equipped=False,
                       companion_standin=0.0, stat_to_key=None, main_stat_key="flat_int", main_stat_pct_key="int_pct", sub_stat_pct_lines=None,
                       input_values=None):
    """CubeData!J:K: {stat name: DPS per unit} from Sensitivity ``rates`` {sweep key: DPS gain of one +1 step} (the sheet's column H).  The builder's
    ``dps_per_unit_expr`` rules: Main Stat Per Level = flat-main-stat rate x character level; Main Stat % per 4 Levels = main-stat-% rate x floor(level / 4);
    Critical Rate % at / above the 100% cap (``crit_rate_total`` = Inputs crit rate + the artifact crit-rate bucket - the FULL live total, CLAUDE.md item 13) is
    priced as Critical Damage % UNLESS Ring of Cycles or Book of Ancient is equipped (their dependent mechanics keep scaling with raw crit rate: the literal rate
    is used); the Companion line's linear stand-in (display only; the real value comes from the companion model); unmapped stats = 0.
    ``sub_stat_pct_lines`` {stat name: (sweep key, Inputs key)} = the builder's POTENTIAL_SUB_STAT_PCT_LINES (Dark Knight: "Dex %" -> rate(dex) x Inputs dex / 100;
    ``input_values`` = the compute inputs the Inputs key is read from)."""
    mapping = stat_to_key or POTENTIAL_STAT_TO_SWEEP_KEY
    sub_lines = sub_stat_pct_lines or {}
    input_values = input_values or {}

    def rate(key):
        return float(rates.get(key, 0.0))
    table = {NONE_STAT: 0.0}
    for stat in all_potential_stats():
        if stat == "Main Stat Per Level":
            table[stat] = rate(main_stat_key) * level
        elif stat == "Main Stat % per 4 Levels":
            table[stat] = rate(main_stat_pct_key) * int(level / 4)
        elif stat == "Critical Rate %":
            capped = crit_rate_total >= 100 and not ring_of_cycles_equipped and not book_of_ancient_equipped
            table[stat] = rate("crit_damage") if capped else rate("crit_rate")
        elif stat == COMPANION_STAT:
            table[stat] = float(companion_standin)
        elif stat in sub_lines:
            sweep_key, inputs_key = sub_lines[stat]
            table[stat] = rate(sweep_key) * float(input_values.get(inputs_key) or 0) / 100
        else:
            key = mapping.get(stat)
            table[stat] = rate(key) if key is not None and key in rates else 0.0
    return table


def sweep_rates(sens_result):
    """{sweep key: DPS gain of one +1 step} = the Sensitivity sheet's column H, from an ``engine.sensitivity.run(...)`` result with the ``stats`` part."""
    return {r["key"]: r["dps_gain"] for r in sens_result["stats"]["rows"]}


def pricing_from_sensitivity(sens_result, inputs=None, class_module=None, *, level=None, crit_rate_total=None, ring_of_cycles_equipped=None,
                             book_of_ancient_equipped=None, companion=None, cdr_exact="auto", stat_to_key=None, sub_stat_pct_lines=None):
    """Pricing for ``recommend`` from ``engine.sensitivity.run(class_module, inputs, which=["stats", "cdr", ...])``'s result.  ``inputs`` (the compute input dict)
    supplies what the sensitivity result does not carry: the character level, the live crit-rate total (Inputs + artifact bucket), whether Ring of Cycles /
    Book of Ancient is equipped, the companion host (the chosen companion's model) and the exact-CDR fallback; each can be given explicitly instead.  Needs the
    ``stats`` and ``cdr`` parts (the ``summon_time`` part supplies b0 when present).  Any class with a Sensitivity spec (``class_module.model`` is its entry; the main-stat
    keys come from the spec's ``mainstat``; ``class_module`` defaults to FP-Mage)."""
    rates = sweep_rates(sens_result)
    cdr = sens_result.get("cdr")
    model = None
    from . import sens_specs
    if class_module is None:
        from .classes import fp_mage as class_module
    spec = sens_specs.get(getattr(class_module, "CLASS_ID", None))
    main_keys = dict(main_stat_key=spec.mainstat.flat, main_stat_pct_key=spec.mainstat.pct) if spec is not None else {}
    if inputs is not None:
        model = class_module.model(dict(inputs, _sens={"want_comp_host": True}))
        if level is None:
            level = inputs.get("level")
        if crit_rate_total is None:
            crit_rate_total = getattr(model, "crit_rate_total", model.crit_rate)      # the FULL live total (a class with a live crit source exposes ``crit_rate_total``)
        eq = model.eq
        if ring_of_cycles_equipped is None:
            ring_of_cycles_equipped = "ring_of_cycles" in eq
        if book_of_ancient_equipped is None:
            book_of_ancient_equipped = "book_of_ancient" in eq
    level = 0 if level is None else level
    crit_rate_total = 0.0 if crit_rate_total is None else crit_rate_total
    if companion is None and model is not None and model.comp_host is not None and model.companion_choice not in (None, "None", "") and model.companion_level >= 1:
        companion = _companion_pricing(model, inputs, sens_result)
    baseline = sens_result["baseline_total"]
    standin = 0.0
    if companion is not None:
        # CubeData's linear stand-in: average DPS per 1% over a +20% roll, (Total - current companion blend + blend at b0) x (weighted ratio - 1) / 20
        cur_blend = companion.current_blend if companion.current_blend is not None else 0.0
        standin = (baseline - cur_blend + companion.at(0)["comp_blend_dps"]) * (companion.factor(20, 0) - 1) / 20
    table = dps_per_unit_table(rates, level, crit_rate_total, bool(ring_of_cycles_equipped), bool(book_of_ancient_equipped), standin, stat_to_key,
                               sub_stat_pct_lines=sub_stat_pct_lines, input_values=inputs, **main_keys)
    cdr_table = [(r["cdr"], r["total_dps"]) for r in cdr["rows"]] if cdr else None
    cdr_current = cdr["current_cdr"] if cdr else 0.0
    if cdr_exact == "auto":
        cdr_exact = _exact_cdr_fn(inputs, class_module) if inputs is not None else None
    return Pricing(baseline, table, cdr_current, cdr_table, cdr_exact, companion)


def _companion_pricing(model, inputs, sens_result):
    from .common import companion as comp_mod
    from . import artifacts as art_mod
    host, choice, lvl = model.comp_host, model.companion_choice, model.companion_level
    st = sens_result.get("summon_time")
    if st is not None:
        b0 = st["b0"]
    else:
        own = inputs.get("companion_potential_lines_pct") or 0
        b0 = max(0, (inputs.get("companion_summon_time_increase_pct") or 0) - own) + art_mod.summon_time_inc_pct(model.eq)
    return CompanionPricing(lambda inc: comp_mod.run(host, choice, lvl, inc), b0, host["w"], host["player_boss"], host["player_norm"],
                            total=model.total_dps, current_blend=model.companion_dps)


def _exact_cdr_fn(inputs, class_module):
    state = {}

    def exact(cdr):
        if "base" not in state:
            from . import sensitivity
            state["base"] = sensitivity._Base(inputs, class_module=class_module)
        return state["base"].block({"skill_cooldown_decrease": cdr}, {}, rebuild=True, full_search=True)[0]
    return exact
