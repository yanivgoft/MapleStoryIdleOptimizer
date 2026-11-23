"""Case builders shared by the cube golden generator (``cubes_reference.py``) and ``test_cubes.py``: gear states and synthetic pricing tables.

Everything is deterministic (no RNG).  Gear lines are drawn from the real roll table of the (slot, rarity), so every state is one the game could produce.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from engine import cubes  # noqa: E402

SYNTH_RATES = {"crit_rate": 1000.0, "crit_damage": 900.0, "damage": 1500.0, "final_damage": 3000.0, "min_damage": 500.0, "max_damage": 800.0,
               "def_pen": 400.0, "basic_attack_damage": 200.0, "skill_damage": 1200.0, "skill_cooldown_decrease": 3000.0, "int_pct": 2000.0,
               "flat_int": 10.0, "skill_lvl_all": 5000.0, "attack_speed": 700.0, "basic_attack_target_increase": 100.0, "buff_duration_increase_pct": 300.0}
SYNTH_CDR_TABLE = [(0.5, 1.012e6), (1.0, 1.031e6), (1.5, 1.036e6), (2.0, 1.074e6), (2.5, 1.079e6), (3.0, 1.093e6), (3.5, 1.131e6), (4.0, 1.137e6),
                   (4.5, 1.140e6), (5.0, 1.176e6)]


def _entries(slot, rarity, line):
    t = cubes.roll_table()
    return list(t.get(("ALL", rarity, line), [])) + list(t.get((slot, rarity, line), []))


def pick_lines(slot, rarity, seed):
    """3 current lines (stat, value) drawn deterministically from the roll pools; every 4th seed leaves line 3 empty, every 7th line 2 as well."""
    lines = []
    for n in (1, 2, 3):
        entries = _entries(slot, rarity, n)
        stat, value, _w = entries[(seed * (n + 3) + n * 5) % len(entries)]
        lines.append((stat, value))
    if seed % 4 == 0:
        lines[2] = (cubes.NONE_STAT, 0.0)
    if seed % 7 == 0:
        lines[1] = (cubes.NONE_STAT, 0.0)
    return lines


def gear_grid():
    """15 slots x 2 potential types x 6 rarities = 180 rows; pity rotates through 0 / cap//2 / cap-1."""
    rates = cubes.rarity_rates()
    rows = []
    for si, slot in enumerate(cubes.CUBE_SLOTS):
        for ti, pt in enumerate(cubes.POTENTIAL_TYPES):
            for ri, rarity in enumerate(cubes.RARITY_ORDER):
                cap = int(rates[pt][rarity]["max"])
                pity = 0 if rarity == "mystic" else [0, cap // 2, cap - 1][(si + ri + ti) % 3]
                rows.append(dict(slot=slot, potential_type=pt, rarity=rarity, pity=pity, lines=pick_lines(slot, rarity, si * 7 + ti * 3 + ri + 1)))
    return rows


def gear_pity_extra():
    """Pity edge values (1 and cap-2) on three slots (one with CDR, one with summoning time, one with a per-level stat)."""
    rates = cubes.rarity_rates()
    rows = []
    for slot in ("head", "boots", "eye-accessory"):
        for pt in cubes.POTENTIAL_TYPES:
            for rarity in ("normal", "epic", "legendary"):
                cap = int(rates[pt][rarity]["max"])
                for pity in (1, cap - 2):
                    rows.append(dict(slot=slot, potential_type=pt, rarity=rarity, pity=pity, lines=pick_lines(slot, rarity, len(rows) + 2)))
    return rows


def gear_cdr_companion():
    """The blank 30-row sheet with CDR lines on the head rows and Companion Summoning Time lines on the boots rows (so those rows are priced against
    their own baselines: CDR on top of the OTHER lines' CDR, summoning time on top of the other row's)."""
    g = cubes.default_gear()
    by = {(r["slot"], r["potential_type"]): r for r in g}
    C, S = cubes.CDR_STAT, cubes.COMPANION_STAT
    by[("head", "Potential")].update(rarity="legendary", pity=100, lines=[(C, 1.5), ("Damage %", 15.0), (C, 1.0)])
    by[("head", "Bonus Potential")].update(rarity="unique", pity=10, lines=[(C, 1.0), (C, 0.5), (cubes.NONE_STAT, 0.0)])
    by[("boots", "Potential")].update(rarity="legendary", pity=300, lines=[(S, 12.0), (S, 12.0), ("Final Damage %", 8.0)])
    by[("boots", "Bonus Potential")].update(rarity="epic", pity=20, lines=[(S, 5.0), (S, 5.0), ("Critical Rate %", 3.0)])
    by[("belt", "Potential")].update(rarity="epic", pity=0, lines=[("Buff Duration Increase %", 5.0), ("Damage %", 9.0), ("Damage %", 9.0)])
    by[("ring", "Potential")].update(rarity="unique", pity=50, lines=[("All Skill Level", 8.0), ("Skill Damage %", 12.0), ("Int %", 5.0)])
    return g


def every(rows, k, offset=0):
    return rows[offset::k]


def synth_pricing(name):
    """Synthetic pricing dicts (JSON-friendly): name -> dict(baseline_dps, dps_per_unit, cdr_current, cdr_table | None, cdr_exact_slope | None)."""
    base = 1.0e6
    table = cubes.dps_per_unit_table(SYNTH_RATES, level=150, companion_standin=2500.0)
    p = dict(baseline_dps=base, dps_per_unit=table, cdr_current=0.0, cdr_table=[list(x) for x in SYNTH_CDR_TABLE], cdr_exact_slope=None)
    if name == "s1_cdr_table":
        return p
    if name == "s2_cdr_current2_exact":          # head rows hold all of the CDR: baselines fall below the table's first step -> exact re-evaluation
        p.update(cdr_current=2.0, cdr_exact_slope=0.02)
        return p
    if name == "s2b_cdr_current2_no_exact":      # ... and without the exact fallback: the +1 s rate below the table
        p.update(cdr_current=2.0)
        return p
    if name == "s3_linear_cdr":                  # no milestone table: the linear +1 s rate everywhere
        p.update(cdr_table=None, cdr_current=1.0)
        return p
    if name == "s4_cap_crit_damage_priced":      # Critical Rate priced like Critical Damage (what the cap rule produces)
        p["dps_per_unit"] = dict(table, **{"Critical Rate %": table["Critical Damage %"]})
        p.update(cdr_current=0.5)
        return p
    raise KeyError(name)


def make_cdr_exact(spec):
    s = spec.get("cdr_exact_slope")
    if s is None:
        return None
    base, cur = spec["baseline_dps"], spec["cdr_current"]
    return lambda cdr: base * (1.0 + s * (cdr - cur))      # fewer CDR seconds -> lower Total DPS


def companion_from_spec(spec):
    """CompanionPricing whose model is a lookup table {extra summoning time above b0 -> boss / normal companion DPS} (the real model is not needed to
    test the optimizer: the table IS what the model returned)."""
    if not spec:
        return None
    runs = {round(float(k), 6): v for k, v in spec["runs"].items()}
    b0 = float(spec["b0"])

    def run(inc):
        boss, norm = runs[round(inc - b0, 6)]
        return {"comp_boss_dps": boss, "comp_norm_dps": norm, "comp_blend_dps": (1 - spec["w"]) * boss + spec["w"] * norm}
    return cubes.CompanionPricing(run, b0, spec["w"], spec["player_boss"], spec["player_norm"], spec.get("total"), spec.get("current_blend"))


def pricing_from_spec(spec):
    return cubes.Pricing(spec["baseline_dps"], spec["dps_per_unit"], spec.get("cdr_current", 0.0), spec.get("cdr_table"), make_cdr_exact(spec),
                         companion_from_spec(spec.get("companion")))
