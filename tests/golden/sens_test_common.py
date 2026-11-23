"""Shared pieces of the sensitivity golden test (``test_sensitivity.py``: engine.sensitivity vs the class workbook's Sensitivity sheet,
``<class>_sensitivity_golden.json``): the builder loader, the inputs of the engine-only tests, the tests every class repeats (hooks are no-ops, API shape, equip-toggle
direction invariance loop, the plain Final Damage +1% sweeps, the baked-in constants / chain checks, the golden) and the command line.  The comparison logic itself is
``sens_compare_generic.py``; what is specific to a class (spec == builder tables, the baked-in artifact pairs, the class's own sweeps) lives in ``sens_extras/<class>.py``;
``registry.py`` says which classes exist and where their files are."""
import argparse
import importlib
import importlib.util
import json
import math
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
import sens_compare_generic as C  # noqa: E402
import registry  # noqa: E402
from engine import sensitivity  # noqa: E402


class SensTest:
    def __init__(self, class_id, class_module, golden, class_name):
        self.class_id, self.module, self.GOLDEN, self.class_name = class_id, class_module, golden, class_name
        self.run_golden = lambda rtol=1e-9, verbose=False, only=None: C.run_golden(self.module, self.GOLDEN, rtol, verbose, only)   # extras may replace it (FP-Mage)

    @classmethod
    def from_registry(cls, class_id):
        e = registry.CLASSES[class_id]
        return cls(class_id, e.engine(), e.sens_golden_path, e.name)

    def builder(self):
        """The class's builder module (module-level tables only; needs openpyxl, None without it)."""
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            return None
        sys.path.insert(0, str(REPO / "src"))
        spec = importlib.util.spec_from_file_location(f"{self.class_id}_bmod_sens", REPO / "src" / f"build_{self.class_id}_workbook.py")
        bm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bm)
        return bm

    def inputs(self, content, artifacts, **over):
        """Engine inputs of a stat-set-S character at Lv140 with Blaze Wizard and the given equipped artifacts (all 36 at their sens-case stars)."""
        from sens_cases import STARS
        make_inputs = importlib.import_module(f"{self.class_id}_cases").make_inputs
        STATS_S = importlib.import_module(f"{self.class_id}_sens_cases").STATS_S
        d = make_inputs(content, 140, STATS_S, "blaze", **over)
        d["artifacts"] = artifacts
        d["artifact_stars"] = dict(STARS)
        return d

    def test_hooks_are_noops_without_sens(self):
        """compute() is untouched by the hook plumbing: an explicit empty ``_sens`` is the same as none."""
        inp = self.inputs("World Boss", [{"key": "bottle_of_emotion", "star": 5}])
        a = self.module.compute(inp)["total_dps"]
        b = self.module.compute(dict(inp, _sens={}))["total_dps"]
        assert a == b

    def test_golden(self):
        if not self.GOLDEN.exists():
            return
        n_cases, n_values, bad = self.run_golden()
        assert not bad, {k: v[:5] for k, v in bad.items()}

    # ---- tests every class repeats (class-specific DATA comes from ``sens_extras/<class>.py``)
    def test_api_shape(self, api):
        """`which` selection, JSON-serialisable output, the no-effect flag, the potential-gain term, the live Shamaness row and the naive switch.
        ``api``: content (the fight the inputs are built for), shamaness ("positive": gain > 0, "nonzero": gain != 0), naive_rows (rows of the naive stat sweep),
        keys_prefix (the first stat keys), keys_absent (stat keys that must not exist), keys_last (optional: the last stat key)."""
        inp = self.inputs(api["content"], [{"key": "hexagon_necklace", "star": 5}])
        out = sensitivity.run(self.module, inp, which=["artifacts", "cdr"])
        assert set(out) >= {"artifacts", "cdr", "baseline_total"} and "stats" not in out and "companions" not in out and out["class_id"] == self.class_id
        json.dumps(out)
        rows = {r["key"]: r for r in out["artifacts"]["rows"]}
        assert rows["pigs_ribbon"]["no_dps_effect"] and rows["pigs_ribbon"]["dps_gain"] == 0.0 and rows["pigs_ribbon"]["pct_gain"] == 100.0
        assert rows["hexagon_necklace"]["equipped"] and rows["hexagon_necklace"]["dps_gain"] > 0
        gain = rows["shamaness_marble"]["dps_gain"]
        mode = api["shamaness"]           # "positive": gain > 0, "nonzero": gain != 0, "inert": gain == 0 (the class's blocks do not wire the Buff Duration what-if: SensSpec.bdi_toggle_wired False)
        assert (gain > 0 if mode == "positive" else gain == 0.0 if mode == "inert" else gain != 0.0) and not rows["shamaness_marble"]["no_dps_effect"]
        out2 = sensitivity.run(self.module, dict(inp, artifact_potential_gain={"pigs_ribbon": 1.0e9}), which="artifacts")
        assert {r["key"]: r for r in out2["artifacts"]["rows"]}["pigs_ribbon"]["dps_gain"] == 1.0e9
        naive = sensitivity.run(self.module, inp, which="stats", naive=True)
        assert naive["semantics"] == "naive" and len(naive["stats"]["rows"]) == api["naive_rows"]
        keys = [r["key"] for r in naive["stats"]["rows"]]
        assert keys[:len(api["keys_prefix"])] == api["keys_prefix"]
        for k in api["keys_absent"]:
            assert k not in keys
        if "keys_last" in api:
            assert keys[-1] == api["keys_last"]
        try:
            sensitivity.run(types.SimpleNamespace(CLASS_ID="no_such_class"), inp)
            raise AssertionError("a class without a spec must raise")
        except NotImplementedError:
            pass

    def check_toggle_pairs(self, pairs):
        """CLAUDE.md item 15 / checklist 8c, engine-only: for every ``(key, off_over, on_over, *live_artifacts)`` the same real state reached from the two
        directions reports the IDENTICAL DPS gain and % gain (World Boss: pure boss), and the adding gain equals the true Total delta."""
        from sens_cases import STARS
        for key, off_over, on_over, *live in pairs:
            base_slots = [{"key": k, "star": STARS[k]} for k in live]
            slot = base_slots + [{"key": key, "star": STARS[key]}]
            off = sensitivity.run(self.module, self.inputs("World Boss", base_slots, **off_over), which="artifacts")["artifacts"]["rows"]
            on = sensitivity.run(self.module, self.inputs("World Boss", slot, **on_over), which="artifacts")["artifacts"]["rows"]
            r_off = next(r for r in off if r["key"] == key)
            r_on = next(r for r in on if r["key"] == key)
            t_off = self.module.compute(self.inputs("World Boss", base_slots, **off_over))["total_dps"]
            t_on = self.module.compute(self.inputs("World Boss", slot, **on_over))["total_dps"]
            assert math.isclose(r_off["dps_gain"], t_on - t_off, rel_tol=1e-9), (key, r_off["dps_gain"], t_on - t_off)      # adding = the true delta
            assert math.isclose(r_on["dps_gain"], r_off["dps_gain"], rel_tol=1e-9), (key, r_off["dps_gain"], r_on["dps_gain"])
            assert math.isclose(r_off["pct_gain"], r_on["pct_gain"], rel_tol=1e-11), (key, r_off["pct_gain"], r_on["pct_gain"])

    def chain_invariance(self, prefix, chain, chain_pairs):
        """The golden's own chain states (``<class>_sens_cases.<chain>``, cases ``<prefix>/<suffix>``) run through the engine: every baked-in artifact of the chain
        reports the same gain / % gain adding and removing, equal to the true delta of the two states."""
        K = importlib.import_module(f"{self.class_id}_sens_cases")
        cases = {c["id"]: c for c in K.sens_cases()}
        tot, rows = {}, {}
        for suffix, _eq, _flags in getattr(K, chain):
            out = sensitivity.run(self.module, cases[f"{prefix}/{suffix}"]["inputs"], which="artifacts")
            tot[suffix] = out["baseline_total"]
            rows[suffix] = {r["key"]: r for r in out["artifacts"]["rows"]}
        for key, add, rem in getattr(K, chain_pairs):
            true = tot[rem] - tot[add]
            a, r = rows[add][key], rows[rem][key]
            assert math.isclose(a["dps_gain"], true, rel_tol=1e-9), (key, a["dps_gain"], true)             # adding = the true delta
            assert math.isclose(r["dps_gain"], true, rel_tol=1e-9), (key, r["dps_gain"], true)             # removing = the same value
            assert math.isclose(a["pct_gain"], r["pct_gain"], rel_tol=1e-11), (key, a["pct_gain"], r["pct_gain"])

    def final_damage_sweep(self, kind):
        """The +1% multiplicative Final Damage step bumps the FULL bucket (typed + the class's live additive Final Damage sources).  ``plain``: the ratio is exactly 1.01
        in pure boss content.  ``strip_under``: exactly 1.01 wherever nothing else moves (Chapter Hunt, no companion: no timeline strip); with the strip on (World Boss)
        a time-varying term of the engine's own bucket makes the ratio a little under 1.01 (the workbook does the same)."""
        if kind == "plain":
            out = sensitivity.run(self.module, self.inputs("World Boss", [{"key": "bottle_of_emotion", "star": 5}]), which="stats")["stats"]["rows"]
            r = next(x for x in out if x["key"] == "final_damage")
            assert math.isclose(r["pct_gain"], 101.0, rel_tol=1e-12), r["pct_gain"]
            assert r["current"] > 12.0 and r["new"] > r["current"]
            return
        assert kind == "strip_under", kind
        inp = self.inputs("Chapter Hunt", [{"key": "bottle_of_emotion", "star": 5}], status_effect_damage=0)
        inp.update(companion_choice="None", companion_level=0)
        out = sensitivity.run(self.module, inp, which="stats")["stats"]["rows"]
        r = next(x for x in out if x["key"] == "final_damage")
        assert math.isclose(r["pct_gain"], 101.0, rel_tol=1e-12), r["pct_gain"]
        assert r["current"] > 12.0 and r["new"] > r["current"]          # Current / New include the live Final Damage share (like the workbook's table)
        wb = sensitivity.run(self.module, self.inputs("World Boss", [{"key": "bottle_of_emotion", "star": 5}]), which="stats")["stats"]["rows"]
        assert 100.9 < next(x for x in wb if x["key"] == "final_damage")["pct_gain"] < 101.0

    def baked_values(self, full=True):
        """The constants of the case matrix (plain data) are the artifact tables' values at the case stars (``full``: also Cursed Doll's FD and Bottle of Emotion)."""
        from engine import artifacts as art
        from sens_cases import STARS
        K = importlib.import_module(f"{self.class_id}_sens_cases")
        assert art.sv("shamaness_marble_buff_duration_increase_pct", STARS["shamaness_marble"]) == K.SHAMANESS_BDI
        assert art.sv("athena_gloves_attack_speed", STARS["athena_gloves"]) == K.ATHENA_AS
        assert art.sv("athena_gloves_max_damage_pct_of_attack_speed", STARS["athena_gloves"]) == K.ATHENA_MAX_PCT
        assert art.sv("reindeer_spear_def_pen", STARS["reindeer_spear"]) == K.REINDEER_DEF_PEN
        if full:
            assert art.sv("cursed_doll_final_damage", STARS["cursed_doll"]) == K.CURSED_DOLL_FD
            assert art.sv("bottle_of_emotion_final_damage_per_3pct_as", STARS["bottle_of_emotion"]) == K.BOTTLE_PER_3PCT
            assert art.sv("bottle_of_emotion_final_damage_cap", STARS["bottle_of_emotion"]) == K.BOTTLE_CAP

    def baked_chain_golden(self, prefix, chain_pairs, shamaness_residual=False):
        """Workbook ground truth (cases ``<prefix>/*``): state k has the first k chain artifacts equipped with their baked-in stats typed into the Inputs; the toggle row
        of artifact k read in the state without it (adding) and in the state with it (removing) gives the identical gain and % Gain, equal to Summary Total(with) -
        Total(without).  ``shamaness_residual`` (Paladin): Shamaness Marble's Buff Duration moves Combat Orders' uptime (a documented +2.8% / +2.7% passive-delta residual),
        so that row is only bounded, not invariant."""
        if not self.GOLDEN.exists():
            return
        K = importlib.import_module(f"{self.class_id}_sens_cases")
        g = json.loads(self.GOLDEN.read_text())["cases"]
        for art, add_s, rem_s in getattr(K, chain_pairs):
            u, e = f"{prefix}/{add_s}", f"{prefix}/{rem_s}"
            if u not in g or e not in g:
                continue
            add, rem = g[u]["workbook"]["toggles"][art], g[e]["workbook"]["toggles"][art]
            true = g[e]["workbook"]["summary"]["total"] - g[u]["workbook"]["summary"]["total"]
            if shamaness_residual and art == "shamaness_marble":
                # Buff Duration moves Combat Orders' uptime in the block, and with it Parashock Guard's / Paladin Expert's skill-level factor (baked-in passives: the block adds the
                # delta, the typed toggled copy cannot): +2.8% / +2.7% of the gain, not direction-invariant (the engine test proves the residual is the ONLY difference)
                assert 1.0 < add["dps_gain"] / true < 1.05 and 1.0 < rem["dps_gain"] / true < 1.05, (add["dps_gain"] / true, rem["dps_gain"] / true)
                assert math.isclose(add["dps_gain"], rem["dps_gain"], rel_tol=5e-3), (art, add["dps_gain"], rem["dps_gain"])
                continue
            assert math.isclose(add["dps_gain"], rem["dps_gain"], rel_tol=1e-9), (art, add["dps_gain"], rem["dps_gain"])
            assert math.isclose(add["pct_gain"], rem["pct_gain"], rel_tol=1e-11), (art, add["pct_gain"], rem["pct_gain"])
            assert math.isclose(add["dps_gain"], true, rel_tol=1e-9), (art, add["dps_gain"], true)


# ---- the test plan of one class: the shared tests + the class's extras module (``sens_extras/<class>.py``)
COMMON = ("static", "hooks_are_noops_without_sens", "api_shape", "final_damage_sweep_is_exactly_one_percent", "toggle_direction_invariance", "golden")


def plan(cid):
    """{name: callable} of every engine-only test of the class in running order (``extras`` = the class's own test_* functions, run after the shared ones) and
    ``golden_extras`` / ``golden`` (they need the golden file).  The extras module declares: ``test_static`` (required), ``API`` (data of the shared API-shape
    test) or ``test_api_shape``, ``toggle_pairs()`` or ``test_toggle_direction_invariance`` (a class-specific replacement), ``FD_SWEEP`` ("plain" | "strip_under" |
    the class's own test function), ``HOOKS`` (default True), ``EXTRA`` / ``GOLDEN_EXTRA`` (lists of test functions), ``TEST`` (the SensTest)."""
    X = registry.CLASSES[cid].sens_extras_module()
    T = X.TEST
    p = {"static": X.test_static}
    if getattr(X, "HOOKS", True):
        p["hooks_are_noops_without_sens"] = T.test_hooks_are_noops_without_sens
    p["api_shape"] = getattr(X, "test_api_shape", None) or (lambda: T.test_api_shape(X.API))
    fd = getattr(X, "FD_SWEEP", None)
    if fd is not None:
        p["final_damage_sweep_is_exactly_one_percent"] = (lambda: T.final_damage_sweep(fd)) if isinstance(fd, str) else fd
    if hasattr(X, "test_toggle_direction_invariance"):
        p["toggle_direction_invariance"] = X.test_toggle_direction_invariance
    else:
        p["toggle_direction_invariance"] = lambda: T.check_toggle_pairs(X.toggle_pairs())
    p["golden"] = T.test_golden
    return p, [(f.__name__, f) for f in getattr(X, "EXTRA", [])], [(f.__name__, f) for f in getattr(X, "GOLDEN_EXTRA", [])], T


def run_cli(cid, rtol=1e-9, verbose=False, case=None):
    """The command line of one class: the engine-only tests, the golden-dependent extras (only when the golden file exists), the golden itself.  Returns the exit code."""
    p, extras, golden_extras, T = plan(cid)
    for name in ("static",):
        p[name]()
    for _n, f in extras:
        f()
    for name in ("hooks_are_noops_without_sens", "api_shape", "final_damage_sweep_is_exactly_one_percent", "toggle_direction_invariance"):
        if name in p:
            p[name]()
    if T.GOLDEN.exists():
        for _n, f in golden_extras:
            f()
    fd = "Final Damage +1% exact, " if "final_damage_sweep_is_exactly_one_percent" in p else ""
    print(f"ok: spec == builder, hooks are no-ops, API shape, {fd}toggle direction invariance (engine + workbook golden)" if "hooks_are_noops_without_sens" in p
          else "ok: static pieces, API shape, toggle direction invariance (engine + workbook golden)")      # (FP-Mage has no spec / hooks)
    if not T.GOLDEN.exists():
        print("no golden file yet")
        return 1
    n_cases, n_values, bad = T.run_golden(rtol, verbose, case)
    for gid, diffs in bad.items():
        for name, wbv, eng in diffs[:25]:
            rel = abs(wbv - eng) / max(abs(wbv), abs(eng), 1e-300) if isinstance(wbv, (int, float)) and isinstance(eng, (int, float)) else float("nan")
            print(f"  {gid}: {name}: workbook {wbv!r} engine {eng!r} rel {rel:.2e}")
    print(f"{'OK' if not bad else 'FAIL'}: {n_cases} cases, {n_values} values compared, {sum(len(v) for v in bad.values())} differences (rtol {rtol})")
    return 1 if bad else 0
