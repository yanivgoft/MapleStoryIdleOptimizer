"""Shared body of ``test_<class>_artifacts.py``: ``engine.classes.<class>.compute`` WITH artifacts equipped against the class's WORKBOOK (evaluated with
``formulas`` by ``<class>_artifact_reference.py``; numbers frozen in tests/golden/<class>_artifacts_golden.json).  Plain ``python3`` runnable
(``--rtol 1e-6 -v``), also pytest-collectable.

Compared per case: total / boss-only / normal-only DPS, every damage row (Calc O plus the boss-only / normal-only columns), the companion's DPS, the
Artifacts sheet's aggregate buckets and per-artifact rows, Summary values and ``Companion!horn_uptime``.  Plus the equip-toggle deltas (with - without)
of the matched pairs and Arwen's Glass Shoes' equivalence pairs.  A class passes its Calc boss / normal columns, its Summary checks and any extra checks.
"""
import json
import sys

# engine report bucket -> Artifacts-sheet AGG row of the workbook
BUCKETS = {"attack_pct": "AGG_ATTACK_PCT", "final_damage": "AGG_FINAL_DAMAGE", "damage": "AGG_DAMAGE", "skill_damage": "AGG_SKILL_DAMAGE",
           "basic_attack_damage": "AGG_BASIC_ATTACK_DAMAGE", "crit_rate": "AGG_CRIT_RATE", "crit_damage": "AGG_CRIT_DAMAGE",
           "boss_damage": "AGG_BOSS_DAMAGE", "normal_damage": "AGG_NORMAL_DAMAGE", "enemy_damage_taken": "AGG_ENEMY_DMG_TAKEN",
           "final_damage_normal_only": "AGG_FINAL_DAMAGE_NORMAL_ONLY", "final_damage_boss_only": "AGG_FINAL_DAMAGE_BOSS_ONLY",
           "soul_contract_cooldown_decrease_pct": "soul_contract_pct", "contract_of_darkness_boss_crit_rate": "contract_of_darkness_crit_rate_bonus",
           "reindeer_spear_extra_def_pen_unit": "reindeer_spear_base_def_pen_reference"}
# Artifacts-sheet rows compared one by one (the engine names them like the sheet)
ROWS = ["roc_threshold_cr", "roc_crit_rate", "roc_skill_damage", "roc_excess_points", "roc_basic_attack_damage", "candle_final_damage",
        "candle_boss_damage", "peach_enemy_dmg_taken", "silver_enemy_dmg_taken", "hexagon_avg_stacks", "hexagon_damage", "rainbow_crit_rate",
        "rainbow_crit_damage", "old_music_box_attack_pct", "flaming_lava", "icy_soul_rock", "secret_map_attack_pct", "secret_map_final_dmg_normal",
        "reindeer_spear_attack_pct", "horn_flute", "bottle_of_emotion_attack_pct", "alliance_badge", "sayrams_necklace_normal",
        "arwens_glass_shoes_summon_time_increase_pct",
        "sayrams_necklace_boss", "fire_flower_normal", "fire_flower_boss", "chalice_normal", "chalice_boss", "charm_of_the_undead"]
# Summary values compared besides the class's own: (label, key of the workbook's Summary row under golden["rows"], key of the engine's ``derived``)
SUMMARY = (("avg_buff_mult", "avgbuff", "avg_buff_mult"), ("cast_rate", "castrate", "cast_rate"), ("actions_per_second", "aps", "actions_per_second"),
           ("startup", "startup", "buff_cast_startup_time"))


def close(a, b, rtol):
    if a == b:
        return True
    if a is None or b is None or isinstance(a, str) or isinstance(b, str):
        return a == b
    scale = max(abs(a), abs(b))
    return abs(a - b) <= rtol * scale + 1e-12


def rtol_arg(default=1e-9):
    return float(sys.argv[sys.argv.index("--rtol") + 1]) if "--rtol" in sys.argv else default


class ArtifactsTest:
    """``boss_col`` / ``normal_col``: the Calc columns holding the boss-only / normal-only DPS of a row (FP-Mage / Bishop / Ice-Lightning: S / U, the others
    T / V); ``summary``: the Summary values compared (``SUMMARY``); ``summary_rows``: {label: (Summary row number, engine ``derived`` key)} of further
    Summary rows; ``extra_summary(chk, wb, s, d)``: class-specific further Summary checks; ``special(rtol, verbose)`` -> (n, {name: diffs}): a second
    golden file (FP-Mage)."""

    def __init__(self, class_module, golden, boss_col="T", normal_col="V", summary=SUMMARY, summary_rows=None, extra_summary=None, special=None):
        self.module, self.GOLDEN = class_module, golden
        self.boss_col, self.normal_col, self.summary = boss_col, normal_col, summary
        self.summary_rows, self.extra_summary, self.special = summary_rows or {}, extra_summary, special
        self.equiv = []

    def compare(self, case, res, rtol):
        wb = case["workbook"]
        diffs = []

        def chk(name, wbv, eng):
            if not close(wbv, eng, rtol):
                diffs.append((name, wbv, eng))
        chk("total_dps", wb["total_dps"], res["total_dps"])
        chk("boss_only_total", wb["boss_only_total"], res["boss_dps"])
        chk("normal_only_total", wb["normal_only_total"], res["normal_dps"])
        rows = {r["key"]: r for r in res["skills"]}
        for key, c in wb["calc"].items():
            if key not in rows:
                continue
            chk(f"calc.O[{key}]", c["O"], rows[key]["dps"])
            chk(f"calc.{self.boss_col}[{key}]", c[self.boss_col], rows[key]["boss_dps"])
            chk(f"calc.{self.normal_col}[{key}]", c[self.normal_col], rows[key]["normal_dps"])
        comp = res["companion"]
        wc = wb["companion"]
        chk("companion.blend", wc["comp_blend_dps"] or 0.0, comp["dps"] if comp else 0.0)
        chk("companion.boss", wc["comp_boss_dps"] or 0.0, comp["boss_dps"] if comp else 0.0)
        chk("companion.normal", wc["comp_norm_dps"] or 0.0, comp["normal_dps"] if comp else 0.0)
        art = res["artifacts"]
        for b, wk in BUCKETS.items():
            chk(f"bucket.{b}", wb["artifacts"][wk], art["buckets"][b])
        for k in ROWS:
            chk(f"row.{k}", wb["artifacts"][k], art["rows"][k])
        chk("horn_uptime", wc["horn_uptime"], art["horn_flute_uptime"])
        s, d = wb["summary"], res["derived"]
        r = wb["rows"]
        for label, rkey, dkey in self.summary:
            chk(f"summary.{label}", s[str(r[rkey])], d[dkey])
        for name, (row, dkey) in self.summary_rows.items():
            chk(f"summary.{name}", s[str(row)], d[dkey])
        if self.extra_summary is not None:
            self.extra_summary(chk, wb, s, d)
        chk("engine_on", bool(wb["timeline_on"]), res["engine_on"])
        return diffs

    def run(self, rtol=1e-9, verbose=False):
        golden = json.loads(self.GOLDEN.read_text())
        bad, totals = {}, {}
        for cid, case in golden["cases"].items():
            res = self.module.compute(case["inputs"])
            totals[cid] = res["total_dps"]
            diffs = self.compare(case, res, rtol)
            if verbose:
                wbt = case["workbook"]["total_dps"]
                print(f"{'ok  ' if not diffs else 'DIFF'} {cid:55s} workbook {wbt:.12e} engine {res['total_dps']:.12e} rel {abs(wbt - res['total_dps']) / (wbt or 1.0):.1e}")
            if diffs:
                bad[cid] = diffs
        # equip-toggle deltas
        toggles, equiv = [], []
        for with_id, without_id, label in golden["toggle_pairs"]:
            if with_id not in golden["cases"] or without_id not in golden["cases"]:
                continue
            wb_delta = golden["cases"][with_id]["workbook"]["total_dps"] - golden["cases"][without_id]["workbook"]["total_dps"]
            eng_delta = totals[with_id] - totals[without_id]
            scale = golden["cases"][without_id]["workbook"]["total_dps"]
            ok = abs(wb_delta - eng_delta) <= rtol * abs(wb_delta) + 1e-12 * scale
            toggles.append((label, wb_delta, eng_delta, ok))
        # Arwen's Glass Shoes equivalence: artifact at Inputs x == no artifact at Inputs x + star value, in the workbook AND in the engine (identical totals)
        for with_id, ref_id, label in golden.get("equiv_pairs", []):
            if with_id not in golden["cases"] or ref_id not in golden["cases"]:
                continue
            w_a, w_b = golden["cases"][with_id]["workbook"]["total_dps"], golden["cases"][ref_id]["workbook"]["total_dps"]
            e_a, e_b = totals[with_id], totals[ref_id]
            ok = close(w_a, w_b, 1e-12) and close(e_a, e_b, 1e-12)
            equiv.append((label, w_a, w_b, e_a, e_b, ok))
        self.equiv = equiv
        return len(golden["cases"]), bad, toggles

    def assert_matches(self):
        """The pytest test body."""
        n, bad, toggles = self.run(1e-9)
        assert n > 0 and not bad, f"{len(bad)} of {n} artifact golden cases differ"
        assert all(t[3] for t in toggles), toggles
        assert all(e[5] for e in self.equiv), self.equiv
        if self.special is not None:
            n2, bad2 = self.special(1e-9)
            assert not bad2, f"{len(bad2)} of {n2} special artifact cases differ"

    def main(self):
        rtol = rtol_arg()
        verbose = "-v" in sys.argv
        n, bad, toggles = self.run(rtol, verbose)
        for cid, diffs in bad.items():
            print(f"MISMATCH {cid}: {len(diffs)} field(s)")
            for name, g, e in diffs[:8]:
                print(f"    {name}: workbook {g!r} engine {e!r}")
        n2, bad2 = self.special(rtol, verbose) if self.special is not None else (0, {})
        for name, diffs in bad2.items():
            print(f"MISMATCH special/{name}: {len(diffs)} field(s)")
            for fname, g, e in diffs:
                print(f"    {fname}: workbook {g!r} engine {e!r}")
        for label, w_a, w_b, e_a, e_b, ok in self.equiv:
            print(f"equiv  {label:46s} workbook {w_a:.15e} vs {w_b:.15e} engine {e_a:.15e} vs {e_b:.15e} {'OK' if ok else 'DIFF'}")
        for label, wbd, engd, ok in toggles:
            print(f"toggle {label:28s} workbook delta {wbd:.12e} engine delta {engd:.12e} rel {abs(wbd - engd) / abs(wbd) if wbd else 0:.1e} {'OK' if ok else 'DIFF'}")
        if bad or bad2 or not all(t[3] for t in toggles) or not all(e[5] for e in self.equiv):
            print(f"FAILED: {len(bad)} of {n} cases" + (f" (+ {len(bad2)} of {n2} special)" if self.special is not None else "") + f" differ (rtol={rtol})")
            sys.exit(1)
        print(f"OK: {n} artifact golden cases match the workbook within rel {rtol:g}; {len(toggles)} equip-toggle deltas match; {len(self.equiv)} Arwen equivalence pairs identical"
              + (((f"; {n2} special cases match" if n2 else "; special cases: none (file missing)")) if self.special is not None else ""))
