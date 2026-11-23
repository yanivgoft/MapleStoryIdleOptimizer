"""Equipment Compare (the workbook's ``Equipment Compare`` sheet): which of two equips is the bigger upgrade, as a DPS % delta.

    from engine import equipment
    out = equipment.compare({"attack": 1500, "lines": [("Damage %", 14), ("Critical Rate %", 3)]},
                            {"attack": 2200, "lines": [("Final Damage %", 6), ("Min Damage %", 15)]}, rates, total_dps)
    out["delta_pct"]            # new % of Total DPS - current % of Total DPS

Each equip = a fixed ``Attack (flat)`` line plus up to 5 lines whose stat comes from the 21-stat dropdown (``DROPDOWN_STATS``) + a typed value.  The gain of a line
is ``value x DPS per unit of its stat`` (``rates`` = {sweep key: DPS of +1} = the Sensitivity sheet's column H, ``cubes.sweep_rates(sens_result)``); lines
on the SAME stat add (including a dropdown line on "Attack (flat)", which merges into the fixed Attack line), different stats compound multiplicatively:
``gain = Total x (prod over distinct stats (1 + group / Total) - 1)``, ``pct = gain / Total x 100``.  Exact for two concrete sets of lines, not an
approximation of an open-ended reroll.  Stat rates are the builder's ``equip_compare_per_unit_rate_expr``: the sweep row of the stat's key, 0 when the class has
no such sweep (e.g. Defense (flat)), and for "Critical Rate %" the cube rule - priced as Critical Damage % once the live crit total (Inputs + artifact bucket) is
at / above 100%, unless Ring of Cycles or Book of Ancient is equipped (``stat_rates`` arguments).
Golden: ``tests/golden/test_equipment.py`` (the real sheet in a tiny workbook, ``tiny_reference.py``).
"""
ATTACK_STAT = "Attack (flat)"
NONE_STAT = "(none)"
# dropdown stat -> Sensitivity sweep key (FP-Mage: INT main stat; the builder's EQUIP_COMPARE_STAT_TO_SWEEP_KEY - other classes use their own main-stat keys)
STAT_TO_SWEEP_KEY = {
    "Main Stat (flat)": "flat_int",
    "Main Stat %": "int_pct",
    "Attack (flat)": "flat_attack",
    "Min Damage %": "min_damage",
    "Max Damage %": "max_damage",
    "Damage %": "damage",
    "Critical Rate %": "crit_rate",
    "Critical Damage %": "crit_damage",
    "Boss Monster Damage %": "boss_damage",
    "Normal Monster Damage %": "normal_damage",
    "Defense Penetration %": "def_pen",
    "Defense (flat)": "defense",
    "Skill Level Bonus — 1st Job": "skill_lvl_1st",
    "Skill Level Bonus — 2nd Job": "skill_lvl_2nd",
    "Skill Level Bonus — 3rd Job": "skill_lvl_3rd",
    "Skill Level Bonus — 4th Job": "skill_lvl_4th",
    "Skill Level Bonus — All Skills": "skill_lvl_all",
    "Final Damage %": "final_damage",
    "Basic Attack Damage %": "basic_attack_damage",
    "Skill Damage %": "skill_damage",
    "Attack Speed %": "attack_speed",
}
DROPDOWN_STATS = list(STAT_TO_SWEEP_KEY)        # the 21 stats of the dropdown
N_LINES = 5                                     # dropdown lines per equip (rows 6-10; row 5 is the fixed Attack line)


def stat_rates(rates, crit_rate_total=0.0, ring_of_cycles_equipped=False, book_of_ancient_equipped=False, stat_to_key=None):
    """{dropdown stat: DPS per unit} from Sensitivity ``rates`` {sweep key: DPS gain of +1}; unmapped / missing sweeps = 0."""
    mapping = stat_to_key or STAT_TO_SWEEP_KEY
    out = {}
    for stat, key in mapping.items():
        out[stat] = float(rates.get(key, 0.0))
    capped = crit_rate_total >= 100 and not ring_of_cycles_equipped and not book_of_ancient_equipped
    if "Critical Rate %" in out:
        out["Critical Rate %"] = float(rates.get("crit_damage" if capped else "crit_rate", 0.0))
    return out


def _same(a, b):
    return str(a).casefold() == str(b).casefold()      # COUNTIF / SUMIF / = on text ignore case


def evaluate_equip(attack, lines, rate_by_stat, total_dps):
    """One side of the sheet: ``rows`` (the fixed Attack line + 5 dropdown lines, each with stat, value, gain, first, group, factor), ``total_gain``, ``pct``."""
    if not total_dps or total_dps <= 0:
        raise ValueError("Total DPS must be positive")
    items = [(ATTACK_STAT, float(attack or 0))]
    lines = list(lines or [])[:N_LINES]
    for stat, val in lines:
        items.append((stat if stat else NONE_STAT, float(val or 0)))
    while len(items) < 1 + N_LINES:
        items.append((NONE_STAT, 0.0))
    rows = []
    for i, (stat, val) in enumerate(items):
        gain = val * rate_by_stat.get(stat, 0.0) if i == 0 else (0 if stat == NONE_STAT else val * rate_by_stat.get(stat, 0.0))
        rows.append(dict(stat=stat, value=val, gain=gain))
    for i, r in enumerate(rows):
        # "first occurrence" of a real stat among the rows above (row 5, the Attack line, counts); row 5 itself is always first
        r["first"] = True if i == 0 else (r["stat"] != NONE_STAT and not any(_same(rows[j]["stat"], r["stat"]) for j in range(i)))
        r["group"] = sum(o["gain"] for o in rows if _same(o["stat"], r["stat"]))
        r["factor"] = 1 + r["group"] / total_dps if r["first"] else 1
    prod = 1.0
    for r in rows:
        prod *= r["factor"]
    total_gain = total_dps * (prod - 1)
    return dict(rows=rows, total_gain=total_gain, pct=total_gain / total_dps * 100)


def compare(current, new, rates, total_dps, crit_rate_total=0.0, ring_of_cycles_equipped=False, book_of_ancient_equipped=False, stat_to_key=None, rate_by_stat=None):
    """Current vs New: ``current`` / ``new`` = ``{"attack": float, "lines": [(stat, value) x <=5]}``.  Returns ``current`` / ``new`` (see ``evaluate_equip``),
    ``delta_pct`` (new % - current %, the sheet's "New vs Current - DPS % Delta"), ``delta_dps`` and ``better`` ("new" | "current" | "equal").
    ``rates`` = {sweep key: DPS gain of +1}; pass ``rate_by_stat`` instead to price the 21 stats directly."""
    rbs = rate_by_stat if rate_by_stat is not None else stat_rates(rates, crit_rate_total, ring_of_cycles_equipped, book_of_ancient_equipped, stat_to_key)
    cur = evaluate_equip(current.get("attack"), current.get("lines"), rbs, total_dps)
    nw = evaluate_equip(new.get("attack"), new.get("lines"), rbs, total_dps)
    delta = nw["pct"] - cur["pct"]
    return dict(current=cur, new=nw, delta_pct=delta, delta_dps=nw["total_gain"] - cur["total_gain"],
                better="new" if delta > 0 else "current" if delta < 0 else "equal")
