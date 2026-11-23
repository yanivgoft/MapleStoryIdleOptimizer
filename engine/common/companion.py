"""Companion plumbing shared by every class: the neutral 'stub' host used to probe a companion's stun windows, and the choice/level
normalisation.  The companion's own rules and kits stay in ``src/companion_python_model.py`` / ``src/companion_kits.py`` (single
source of truth, imported through the ``engine._src`` shim)."""
from .. import _src  # noqa: F401  (puts src/ on sys.path)
import companion_kits as ck  # noqa: E402
import companion_python_model as cpm  # noqa: E402
import status_timeline as stl  # noqa: E402

COMPANIONS_ORDER = list(ck.COMPANIONS_ORDER)
COMPANION_CHOICES = ["None"] + COMPANIONS_ORDER


# ---- pinned summon-time candidate (Sensitivity blocks) ---------------------------------------------------------------------------------------
# The workbook's Sensitivity blocks do not search the three summon-time candidates again (except the swept stats listed in COMPANION_FULL_SEARCH_KEYS):
# `cells(host, ncand=1, fixed_s, fixed_tend, fixed_e)` pins candidate 0 to the summon time / boss-phase extension the MAIN sheet chose.  src/
# companion_python_model.run has no such switch (and src/ is not to be edited), so the pinned variant is built once at import time from the
# module's own source with three guarded textual patches (an assertion fails loudly if the source ever changes shape):  `pin=(s, E)` sets
# candidate 0 = (s, E), W_0 from it, and evaluates that candidate only.
def _build_pinned_run():
    import inspect
    src = inspect.getsource(cpm)

    def patch(text, old, new):
        assert text.count(old) == 1, f"companion_python_model changed: cannot patch {old!r}"
        return text.replace(old, new)
    src = patch(src, "def run(host, choice, lvl, inc, grid_inc=None):", "def run(host, choice, lvl, inc, grid_inc=None, pin=None):")
    src = patch(src, "    W0 = D if steady else max(0.0, min(D, Teff + E0 - s0))\n",
                "    W0 = D if steady else max(0.0, min(D, Teff + E0 - s0))\n"
                "    if pin is not None:\n"
                "        s0, E0 = pin\n"
                "        W0 = D if steady else max(0.0, min(D, Teff + E0 - s0))\n")
    src = patch(src, "    cands = [(s0, E0)]\n    if steady:\n",
                "    cands = [(s0, E0)]\n    if pin is not None:\n        pass\n    elif steady:\n")
    ns = {"__name__": "companion_python_model_pinned", "__file__": cpm.__file__}
    exec(compile(src, "<companion_python_model + pin>", "exec"), ns)
    return ns["run"]


_pinned_run = None


def run(host, choice, lvl, inc, pin=None):
    """``companion_python_model.run`` (full 3-candidate search) or, with ``pin=(summon time s, boss-phase extension E)``, the pinned single
    candidate of a Sensitivity block."""
    global _pinned_run
    if pin is None:
        return cpm.run(host, choice, lvl, inc)
    if _pinned_run is None:
        _pinned_run = _build_pinned_run()
    return _pinned_run(host, choice, lvl, inc, pin=pin)


def normalise_companion(choice, level):
    """(choice, level) with the workbook's conventions: a missing / blank choice means "None"; a level that is not a number >= 1
    means "not unlocked" (level 0)."""
    if choice is None or choice == 0:
        choice = "None"
    try:
        lvl = int(float(level))
    except (TypeError, ValueError):
        lvl = 0
    return choice, lvl


def stub_host(content, fight, pvp_len):
    """Neutral host (all player-side values zero / one): only enough for the companion model to report its stun windows."""
    return dict(mt=content.monster_type, T=content.fight_duration, content=content.content_type, pvp_len=pvp_len, cap=fight.max_enemies_hit,
                w=content.normal_weight, unit=1.0,
                bad=0.0, sd=0.0, aps=1.5, avgbuff=1.0, attack_bucket_avg=0.0, charm_val=0.0, agg_damage_avg=0.0, hex_avg=0.0,
                hex_snap=lambda st: 0.0,
                avgbuff_snap=lambda charm, extra: 1.0, agg_fd_boss_only=0.0, agg_fd_norm_only=0.0, chalice_avg_boss=0.0,
                chalice_avg_norm=0.0,
                chalice_full=0.0, horn_avg=0.0, horn_full=0.0, boss_pct=0.0, norm_pct=0.0, extra_boss=1.0, extra_norm=1.0,
                player_boss=1.0, player_norm=1.0, player_uniform_boss=1.0,
                player_basic_boss=0.5, player_basic_norm=0.5, cr_total=0.0, cd_total=0.0, min_dmg=100.0, max_dmg=100.0, defense=0.0,
                def_pen=0.0, taken_bucket=0.0)


def stun_probe(content, fight, pvp_len, choice, level, summon_time_increase_pct, pin=None):
    """The companion model's stun summary for the chosen companion (None when no companion is active)."""
    if choice != "None" and level >= 1:
        return run(stub_host(content, fight, pvp_len), choice, level, summon_time_increase_pct, pin=pin)
    return None


def read_choice(inp, zero_none=True):
    """The chosen companion and its level from the inputs (validated).  ``zero_none``: the workbook's CompanionsInput has no "None" row, so
    its level reads as not unlocked (0)."""
    choice, c_level = normalise_companion(inp.raw("companion_choice"), inp.raw("companion_level"))
    if choice not in COMPANION_CHOICES:
        raise ValueError(f"unknown companion_choice {choice!r}")
    if zero_none and choice == "None":
        c_level = 0
    return choice, c_level


def stun_windows(content, fight, pvp_len, pst, choice, c_level, summon_time_inc, sens):
    """(stun_info, stun_pin): the companion model's summary run on the stub host that carries the player's own stun entries ``pst`` (the timeline
    strip's stun vector reads ``stun_info``).  Sensitivity blocks pin candidate 0 to the summon time the MAIN sheet chose: the block's own stunned
    share / Horn Flute window use ``stun_pin`` (pinned timing), exactly as the workbook's blocks do; without a pin both are the same run."""
    stub = stub_host(content, fight, pvp_len)
    stub["pst"] = pst
    chosen = choice if (choice != "None" and c_level >= 1) else "None"
    stun_info = run(stub, chosen, c_level, summon_time_inc)
    _pin = sens.get("comp_pin")
    stun_pin = run(stub, chosen, c_level, summon_time_inc, pin=_pin) if _pin is not None else stun_info
    return stun_info, stun_pin


def horn_window(actx, monster_type, fight_duration, pvp_len, summon_time_inc, stun_pin, choice, c_level):
    """Companion!horn_uptime's timing inputs (s0, w0, d_comp, period, ts_window): the share of the player's boss DAMAGE dealt while the companion
    is out, from the candidate-0 timing of the stub-host run (which already carries the player's own stun in Breakthrough / Hero Dungeon)."""
    d_comp = 30.0 * (1 + summon_time_inc / 100)
    steady = actx.steady
    t_eff = pvp_len if monster_type == "pvp" else fight_duration
    period = max(d_comp, 90.0) if steady else t_eff
    if "s0" in stun_pin:
        s0 = stun_pin["s0"]
        w0 = stun_pin["W0"] if (choice != "None" and c_level >= 1) else 0.0     # the workbook's W_0 is 0 with no companion chosen
        ts_window = stun_pin["W0"]                                            # max(0, min(D, Tend_0 - s0)) either way
    else:                                           # no companion and no player stun: E_0 = 0 and W_0 = 0
        s0 = 0.0 if steady else max(7.0, t_eff - d_comp)
        w0 = 0.0
        ts_window = max(0.0, min(d_comp, t_eff - s0))
    return s0, w0, d_comp, period, ts_window


def host_common(m, pre, eff, basic_b, basic_n):
    """The entries of the companion host every class fills the same way from its model state ``m`` (``pre`` / ``eff`` = the artifact Pre / Effects,
    ``basic_b`` / ``basic_n`` = the basic attack's boss / normal DPS); the class adds its own player-side values (``unit``, ``sd``, ``aps``, ...)."""
    strip = m.e_engine
    return dict(
        mt=m.monster_type, T=m.fight_duration, content=m.content_type, pvp_len=m.pvp_len, cap=m.fight.max_enemies_hit, w=m.normal_weight,
        bad=m.basic_attack_damage + m.art_basic_attack_damage,
        charm_val=pre.charm_val, hex_avg=pre.hex_avg, hex_snap=lambda st: pre.hex_v * st,
        agg_fd_boss_only=eff.agg_fd_boss_only, agg_fd_norm_only=eff.agg_fd_normal_only,
        chalice_avg_boss=eff.rows["chalice_boss"], chalice_avg_norm=eff.rows["chalice_normal"], chalice_full=eff.chalice_full,
        horn_avg=eff.rows["horn_flute"], horn_full=eff.horn_full,
        extra_boss=m.extra_boss, extra_norm=m.extra_norm, player_boss=m.pb_total, player_norm=m.pn_total,
        player_uniform_boss=m.pu_total, player_basic_boss=basic_b, player_basic_norm=basic_n,
        min_dmg=m.min_damage, max_dmg=m.max_damage, defense=m.monster_defense,
        st=dict(on=m.status_on, S=m.status_effect_damage,
                mult=(list(strip["mult"]) + [1.0] * (stl.NB_MAX - strip["nb"])) if m.status_on else None,
                act=(list(strip["act"]) + [0.0] * (stl.NB_MAX - strip["nb"])) if m.status_on else None),
    )
