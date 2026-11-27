"""Plain-Python port of the companion model (src/companion_model.py), used by the verify scripts as the INDEPENDENT check of the
spreadsheet formulas: it loops over the kit rows with ordinary conditionals instead of SUMPRODUCT masks and counts every cast of an
overlapping summon one by one.  It takes NUMERIC host values (the verify script's own port of the player's pipeline) and returns the
same quantities as the Companion sheet.

Cast timing (user's in-game measurement, 2026-11-18; constants START_DELAY / CAST_TIME / FIRST_SLOT live in companion_kits.py, the rule in
companion_kits.schedule()): a cooldown action skill is cast at s + t0 + n * (cd + CAST_TIME), n = 0, 1, ..., so a window W holds
`int((W - 1e-9 - t0) // per) + 1` casts of it (0 when W <= t0).  Here the schedule is recomputed from the ACTIVE rows (level + content), the sheet
reads the static `per` / `t0` columns of CompanionKits; stat rows, DoT windows, procs boosted by a skill, echo rows keyed to a cast, stun windows and
the Chapter Breakthrough extension all use the same cast times.  Summoning effects (cd = NEVER) happen at the summon; passives with their own timer
keep period = cd and t0 = 0.
"""
import math

import companion_kits as ck

NEVER = ck.NEVER
LEVEL_MULT = [60, 64, 68, 72, 75, 78, 81, 84, 87, 90]
SUMMON_COOLDOWN = 90.0
EARLIEST_SUMMON = 7.0


def _min(a, b):
    return a if a < b else b


def _aps_after(aps, delta_pct):
    return 1 + min(150.0, 150.0 * (1 - (1 - (aps - 1) * 100 / 150) * (1 - delta_pct / 150))) / 100


def _ramp_avg_factor(duration, max_stacks, interval, per_pct):
    """Average over ``duration`` s of the compounded factor (1 + p/100)^n of a buff gaining one stack worth ``p`` % every ``interval`` s from t = 0 up to ``max_stacks``
    (same as engine.common.fight.ramp_avg_gain_pct, as a factor)."""
    if duration <= 0:
        return 1.0
    f = 1 + per_pct / 100
    n = min(int(duration // interval), max_stacks)
    return (interval * sum(f ** k for k in range(n)) + (duration - n * interval) * f ** n) / duration


def run(host, choice, lvl, inc, grid_inc=None):
    """host: numeric dict (see HOST_KEYS in companion_model.py; functions avgbuff_snap(charm, extra) and hex_snap(stacks) are
    Python callables).  Returns {'comp_boss_dps', 'comp_norm_dps', 'comp_blend_dps', 'best', ...}."""
    h = host
    rows = [r for r in ck.rows_with_keys() if r["comp"] == choice and r["unlock"] <= lvl and r["maxlvl"] > lvl]
    sel = choice != "None" and lvl >= 1 and any(r["comp"] == choice for r in ck.ROWS)
    pst = [e for e in (h.get("pst") or []) if e.get("on", 1)]
    if not sel:
        rows = []
        if not pst:
            return dict(comp_boss_dps=0.0, comp_norm_dps=0.0, comp_blend_dps=0.0, own_boss_dps=0.0, own_norm_dps=0.0, best=1, s=0, W=0, dmg_b=0.0, dmg_n=0.0, upl_b=0.0, upl_n=0.0,
                        stunfracB=0.0, stunfracN=0.0, hasstun=0, horn_uptime=0.0, E=0.0, ext=0.0)
    D = 30.0 * (1 + inc / 100)
    pvp = h["mt"] == "pvp"
    steady = (not pvp) and h["T"] == 0
    Teff = h["pvp_len"] if pvp else h["T"]
    period = max(D, SUMMON_COOLDOWN) if steady else Teff
    lvlmult = LEVEL_MULT[min(10, max(1, lvl)) - 1] / 100
    isBT = 1 if h["content"] == "Breakthrough" else 0
    chboss = 1 if h["content"] == "Chapter Boss" else 0
    tb0 = 20 if h["content"] == "Breakthrough" else (30 if h["content"] == "Hero Dungeon" else 0)
    cap = max(1, h["cap"])
    w = h["w"]

    def ct_ok(r):
        g = r["g_ct"]
        return (g == "-" or (g == "BT" and isBT) or (g == "notBT" and not isBT) or (g == "CB" and chboss)
                or (g == "PvP" and pvp) or (g == "notPvP" and not pvp))

    rows = [dict(r) for r in rows]
    _sch = ck.schedule([r for r in rows if ct_ok(r)])
    for r in rows:                              # rows of the other content variant keep the static (sheet) timing; they never count anyway
        if r["id"] in _sch:
            r["per"], r["t0"] = _sch[r["id"]]

    tbasic = _min(sum(r["tgt"] for r in rows if r["kind"] == "basic"), cap)
    skratio = (1 + h["sd"] / 100) / (1 + h["bad"] / 100)

    def casts_of(r, W):
        return _casts(r, W)

    def pl_ext(t_end):
        """the player's own stuns: casts t0 + j*cd with tb0 <= t < the extended fight end (periodic summons: p x dur/tick x window per cast)"""
        total = 0.0
        for e in pst:
            cd, t0 = e["cd"], e["t0"]
            jmin = max(0, math.ceil(max(0.0, tb0 - t0) / cd - 1e-12))
            jmax = max(0, math.ceil(max(0.0, t_end - t0) / cd - 1e-12))
            per_cast = (e["p"] * e["dur"] / e["tick"] * e["win"]) if e.get("typ", "cast") == "periodic" else e["p"] * e["dur"]
            total += per_cast * max(0, jmax - jmin)
        return total

    def pl_frac():
        tot = 0.0
        for e in pst:
            cd, t0 = e["cd"], e["t0"]
            per = e.get("typ", "cast") == "periodic"
            if steady:
                tot += (e["p"] * e["dur"] / e["tick"] * min(e["win"], cd) / cd) if per else e["p"] * min(e["dur"], cd) / cd
            else:
                n = max(0, int((Teff - t0 - 1e-9) // cd) + 1)
                tot += (e["p"] * e["dur"] / e["tick"] * e["win"] * n / Teff) if per else e["p"] * e["dur"] * n / Teff
        return min(1.0, tot)

    def extension(s, t_end):
        """Chapter Breakthrough: every stunning/freezing cast that lands while the boss stands there (t >= tb0, t < the fight end)
        keeps the boss alive that much longer - counted cast by cast."""
        if not isBT or steady:
            return 0.0
        W = max(0.0, min(D, t_end - s))
        total = pl_ext(t_end)
        if not sel:
            return total
        for r in rows:
            if r["kind"] != "hit" or r["stun"] <= 0 or not ct_ok(r) or r["g_br"] == "nonboss":
                continue
            dur = r["stun_bt"] if r["stun_bt"] > 0 else r["stun"]
            for j in range(casts_of(r, W)):
                t = s + r["t0"] + j * r["per"]
                if j >= r["stun_skip"] and t >= tb0 and t < t_end:
                    total += r["stun_p"] * dur
        return total

    def ext_for(s_first):
        """three unrolled iterations of  s = T_end - D,  T_end = T + E(s)  (same as the sheet)"""
        sa = s_first
        Ea = extension(sa, Teff)
        sb = max(EARLIEST_SUMMON, Teff + Ea - D)
        Eb = extension(sb, Teff + Ea)
        sc = max(EARLIEST_SUMMON, Teff + Eb - D)
        return extension(sc, Teff + Eb), Eb

    s_a = 0.0 if steady else max(EARLIEST_SUMMON, Teff - D)
    E0, E_prev = ext_for(s_a)
    s0 = 0.0 if steady else max(EARLIEST_SUMMON, Teff + E0 - D)
    W0 = D if steady else max(0.0, min(D, Teff + E0 - s0))

    # ---- stun / freeze exposure (Status Effect Damage), candidate-0 timing
    def stun_dur(r):
        return r["stun_bt"] if (isBT and r["stun_bt"] > 0) else r["stun"]

    def stunners(branch):
        return [r for r in rows if r["kind"] == "hit" and r["stun"] > 0 and ct_ok(r)
                and (r["g_br"] == "-" or (r["g_br"] == "boss" and branch == "b") or (r["g_br"] == "nonboss" and branch == "n"))]

    def stunfrac(branch):
        tot = sum(r["stun_p"] * stun_dur(r) * max(0, _casts(r, W0) - r["stun_skip"]) for r in stunners(branch))
        return min(1.0, tot / period)

    def stun_vector(nb):
        out = []
        for i in range(nb):
            tot = 0.0
            for r in stunners("b"):
                u = i + 1 - s0 - r["t0"]
                jj = int(max(0.0, u - 1e-9) // r["per"])
                if u > 1e-9 and jj >= r["stun_skip"] and jj <= _casts(r, W0) - 1:
                    t = s0 + r["t0"] + jj * r["per"]
                    tot += r["stun_p"] * max(0.0, min(i + 1, t + stun_dur(r)) - max(i, t))
            out.append(min(1.0, tot))
        return out
    plf = pl_frac()
    stf_b = min(1.0, (stunfrac("b") if sel else 0.0) + plf) if pst else (stunfrac("b") if sel else 0.0)
    stf_n = min(1.0, (stunfrac("n") if sel else 0.0) + plf) if pst else (stunfrac("n") if sel else 0.0)
    st = h.get("st")
    S_pct = st["S"] if st else 0.0

    def st_mult(branch, s_, W_):
        if branch == "n":
            return 1 + S_pct / 100 * stf_n
        if W_ <= 0:
            return 1.0
        if st and st["on"]:
            end = s_ + W_
            tot = sum(st["mult"][i] * st["act"][i] * max(0.0, min(i + 1, end) - max(i, s_)) for i in range(len(st["mult"])))
            return tot / W_
        return 1 + S_pct / 100 * stf_b

    cands = [(s0, E0)]
    if steady:
        cands += [(0.0, 0.0), (0.0, 0.0)]
    else:
        c1 = (20 if s0 < 20 else 40 if s0 < 40 else 60) if s0 < 60 else s0
        c2 = EARLIEST_SUMMON
        for cs in (c1, c2):
            Ea = extension(cs, Teff)
            cands.append((cs, extension(cs, Teff + Ea)))

    def ext_value(E):
        stacks_e = min(3, int((Teff + E / 2) // 20))
        if tb0 > 0:
            boss_avg = (max(0, Teff - max(tb0, 20)) + max(0, Teff - max(tb0, 40)) + max(0, Teff - max(tb0, 60))) / (Teff - tb0)
            rho_de = (1 + h["hex_snap"](stacks_e) / 100) / (1 + h["hex_snap"](boss_avg) / 100)
        else:
            rho_de = (1 + (h["agg_damage_avg"] - h["hex_avg"] + h["hex_snap"](stacks_e)) / 100) / (1 + h["agg_damage_avg"] / 100)
        return E * h["player_uniform_boss"] * rho_de

    best = None
    for idx, (s, E) in enumerate(cands):
        Tend = Teff + E
        W = (D if steady else max(0.0, min(D, Tend - s))) if sel else 0.0
        if W <= 0:
            res = (0.0, 0.0, 0.0, 0.0, 0.0)
        else:
            res = _evaluate(h, rows, W, s, steady, pvp, isBT, chboss, tb0, Tend, cap, w, tbasic, skratio, lvlmult, ct_ok, lvl, choice,
                            st_mult("b", s, W), st_mult("n", s, W))
        dmg_b, dmg_n, upl_b, upl_n = res[:4]
        ext = ext_value(E) if (W > 0 or E > 0) else 0.0
        if tb0 > 0:
            score = (1 - w) * (dmg_b + upl_b + ext) / max(1e-6, Teff - tb0) + w * (dmg_n + upl_n) / tb0
        else:
            score = (1 - w) * (dmg_b + upl_b) + w * (dmg_n + upl_n) + ext
        if W <= 0 and E <= 0:
            score = 0.0
        if best is None or score > best[0]:
            best = (score, idx, s, W, res, E, ext)
    score, idx, s, W, res, E, ext = best
    dmg_b, dmg_n, upl_b, upl_n = res[:4]
    horn_uptime = min(1.0, D / period) if steady else min(1.0, max(0.0, min(D, Teff + E0 - s0)) / period)
    if tb0 > 0:
        comp_b = (dmg_b + upl_b + ext) / max(1e-6, Teff - tb0)
        comp_n = (dmg_n + upl_n) / tb0
    else:
        comp_b = (dmg_b + upl_b + (ext / (1 - w) if w < 1 else 0.0)) / period
        comp_n = (dmg_n + upl_n) / period
    if tb0 > 0:             # the companion's OWN damage (the rest of comp_*_dps is what it does for the player: stun uplift, Hexagon / Charm snapshots, boss-phase extension)
        own_b, own_n = dmg_b / max(1e-6, Teff - tb0), dmg_n / tb0
    else:
        own_b, own_n = dmg_b / period, dmg_n / period
    return dict(comp_boss_dps=comp_b, comp_norm_dps=comp_n, comp_blend_dps=(1 - w) * comp_b + w * comp_n, own_boss_dps=own_b, own_norm_dps=own_n,
                best=idx + 1, s=s, W=W, E=E, ext=ext, horn_uptime=horn_uptime, s0=s0, W0=W0, stunfracB=stf_b, stunfracN=stf_n,
                hasstun=1 if ((sel and stunners('b')) or pst) else 0, stun_vector=stun_vector,
                dmg_b=dmg_b, dmg_n=dmg_n, upl_b=upl_b, upl_n=upl_n)


def _evaluate(h, rows, W, s, steady, pvp, isBT, chboss, tb0, Teff, cap, w, tbasic, skratio, lvlmult, ct_ok, lvl, choice, stm_b=1.0, stm_n=1.0):
    stacks_hex = 3 if steady else min(3, int(s // 20))
    charm = 0.5 if steady else (1 if (s >= 10 and s % 10 < 5) else 0)
    Wn = max(0.0, min(s + W, tb0) - s) if (tb0 > 0 and W > 0) else 0.0
    tf_b = (1 - Wn / W if W > 0 else 0.0) if tb0 > 0 else 1.0
    tf_n = ((Wn / W) if W > 0 else 0.0) if tb0 > 0 else 1.0

    def phase(r, branch):
        """share of this row's casts that land in the phase of `branch` (1 where the content has no phases)"""
        if tb0 <= 0:
            return 1.0
        cst = _casts(r, W)
        csn = min(cst, _casts(r, Wn)) if Wn > 0 else 0
        if cst == 0:
            return 1.0 if branch == "b" else 0.0
        return csn / cst if branch == "n" else 1 - csn / cst

    f50b = 0.5 if (steady) else max(0.0, min(1.0, (s + W - max(s, tb0 + (Teff - tb0) / 2)) / W))
    f50s = (1 - w) * f50b + w * 0.5

    def hp_f(r, branch_f):
        g = r["g_hp"]
        return 1.0 if g == "-" else (branch_f if g == "lt50" else 1 - branch_f)

    def br_ok(r, branch):
        g = r["g_br"]
        return g == "-" or (g == "boss" and branch == "b") or (g == "nonboss" and branch == "n")

    def casts(r):
        return _casts(r, W)

    def tgt_n(r):
        return _min(r["tgt"], cap)

    # action economy
    ACT = sum(casts(r) for r in rows if r["action"] == 1 and ct_ok(r))

    # stat-like rows: average effective value per code and group
    def row_avg(r, ba=None, atkc=None):
        k = r["kind"]
        if k == "stat":
            N = casts(r)
            up = _uptime(r, N, W)
            return r["val"] * up
        if k == "stack":
            if r["trig"] == "skill":
                rate_att = ACT / W
            elif r["trig"] == "basic":
                rate_att = ba / W
            else:
                rate_att = (ba + atkc) / W
            x = r["chance"] * rate_att
            rate = x / (1 + r["icd"] * x)
            stk = min(r["smax"], rate * r["sdur"])
            sd_ = r["sdur"]
            ramp = (1 - sd_ / (2 * W)) if W >= sd_ else W / (2 * sd_)
            return r["val"] * stk * ramp
        if k == "ramp" and r["ramp_mode"] == "lin":
            return r["val"] * W / 2
        return 0.0

    def stat_sum(code, groups, ba=None, atkc=None, fd_log=False, per_tgt_n=None):
        total = 0.0
        for r in rows:
            if r["stat"] != code or r["kind"] not in ("stat", "stack", "ramp"):
                continue
            if r["who"] not in groups:
                continue
            if not ct_ok(r):
                continue
            hpf = hp_f(r, f50s)
            avg = row_avg(r, ba, atkc)
            if fd_log:
                total += hpf * math.log(1 + avg / 100) if hpf else 0.0
            else:
                v = hpf * avg
                if code == "fd_pt":
                    v *= min(r["per_tgt"], per_tgt_n)
                total += v
        return total

    # companion attack speed (non-stack rows), aps, basic attacks
    asc = stat_sum("as", ("c", "b"), ba=0, atkc=0) if True else 0.0
    # (stack rows have no c-group Attack Speed in any kit; recompute ba after aps)
    aps_c = _aps_after(h["aps"], asc)
    ba = max(0.0, W * aps_c - ACT - 1)
    atkc = sum(casts(r) * r["atk"] for r in rows if r["kind"] == "hit" and ct_ok(r))

    _bl = sum(r["lines"] * r["pct"] for r in rows if r["kind"] == "basic")
    if tb0 > 0:
        actn = sum(_casts(r, Wn) for r in rows if r["action"] == 1 and ct_ok(r)) if Wn > 0 else 0
        ba_b = max(0.0, (W - Wn) * aps_c - (ACT - actn) - 1)
        ba_n = max(0.0, Wn * aps_c - actn)
    else:
        ba_b = ba_n = ba
    BAB = ba_b * _bl
    BAN = ba_n * _bl * tbasic

    def coef_sums(branch):
        f = f50b if branch == "b" else 0.5
        tg = (lambda r: r["tgt_boss"]) if branch == "b" else tgt_n
        hit = dot = ech = 0.0
        for r in rows:
            if not (ct_ok(r) and br_ok(r, branch)):
                continue
            hf = hp_f(r, f)
            if r["kind"] == "hit":
                hit += hf * casts(r) * phase(r, branch) * r["lines"] * r["pct"] * tg(r)
            elif r["kind"] == "dot":
                ticks = 0
                for j in range(casts(r)):
                    rem = min(r["dur"], W - r["t0"] - j * r["per"])
                    ticks += int(rem // r["tick"])
                if tb0 > 0:
                    nt = _casts(r, Wn) * r["tkf"] if Wn > 0 else 0
                    ticks = (ticks - nt) if branch == "b" else nt
                dot += hf * ticks * r["lines"] * r["pct"] * tg(r)
            elif r["kind"] == "echo":
                cnt = (ACT + 1) if r["echo_all"] == 1 else casts(r)
                ech += hf * cnt * r["lines"] * r["pct"]
        stn_hit = sum(r["lines"] * r["pct"] for r in rows if r["kind"] == "stunhit")
        events = 0.0
        for r in rows:
            if r["kind"] == "hit" and r["stun"] > 0 and ct_ok(r) and br_ok(r, branch):
                events += hp_f(r, f) * (casts(r) - r["stun_skip"]) * r["stun_p"] * tg(r)
        return hit, dot, ech, stn_hit * events

    # proc slots
    def proc_damage(branch):
        total = 0.0
        procs_rows = [r for r in rows if r["kind"] == "proc"]
        for r in procs_rows:
            if not (ct_ok(r) and br_ok(r, branch)):
                continue
            ce = r["chance"]
            if r["boost_src"] != "-":
                b = next(x for x in rows if x["id"] == r["boost_src"])
                Nb = _casts(b, W)
                u = min(1.0, _uptime(b, Nb, W))
                ce = r["chance"] * (1 - u) + r["boost_chance"] * u
            hits = [x for x in rows if x["kind"] == "hit" and ct_ok(x)]
            if branch == "b":
                x_ = ce * (ba + (atkc if r["trig"] == "any" else 0)) / W
                tg = r["tgt_boss"]
            else:
                if r["icd"] == 0:
                    n_roll = ce * ba * tbasic
                    if r["trig"] == "any":
                        n_roll += ce * sum(casts(x) * x["atk"] * tgt_n(x) for x in hits)
                else:
                    n_roll = ba * (1 - (1 - ce) ** tbasic)
                    if r["trig"] == "any":
                        n_roll += sum(casts(x) * x["atk"] * (1 - (1 - ce) ** tgt_n(x)) for x in hits)
                x_ = n_roll / W
                tg = tgt_n(r)
            procs = W * x_ / (1 + r["icd"] * x_)
            echo = sum(e["lines"] * e["pct"] for e in rows if e["kind"] == "echoproc" and e["src"] == str(r["slot"]) and ct_ok(e))
            total += procs * (r["lines"] * r["pct"] * tg + echo)
        return total

    # ratio pieces
    def groups_for(grp):
        return (grp, "b")

    def ratios(grp, branch):
        gr = groups_for(grp)
        fd = math.exp(stat_sum("fd", gr, ba=ba, atkc=atkc, fd_log=True))
        fdpt = stat_sum("fd_pt", gr, per_tgt_n=(1 if branch == "b" else cap))
        ramp_exp = _ramp_exp(rows, W) if grp == "c" else 1.0
        fdR = fd * ramp_exp * (1 + fdpt / 100)
        atk = stat_sum("atk", gr, ba=ba, atkc=atkc)
        crr = stat_sum("crit_rate", gr, ba=ba, atkc=atkc)
        cdd = stat_sum("crit_dmg", gr, ba=ba, atkc=atkc)
        crR = ((1 + min(1.0, (h["cr_total"] + crr) / 100) * (h["cd_total"] + cdd) / 100)
               / (1 + min(1.0, h["cr_total"] / 100) * h["cd_total"] / 100))
        mx = stat_sum("max_dmg", gr, ba=ba, atkc=atkc)
        mxR = ((min(h["min_dmg"], h["max_dmg"] + mx) + h["max_dmg"] + mx) / (min(h["min_dmg"], h["max_dmg"]) + h["max_dmg"]))
        dpd = stat_sum("def_pen", gr, ba=ba, atkc=atkc)
        mdef = stat_sum("mon_def", ("m",)) + stat_sum("mon_def_" + branch, ("m",))
        dp, D_ = h["def_pen"], h["defense"]
        dfR = (6000 + D_ * (1 - dp / 100)) / (6000 + D_ * (1 - min(0.95, mdef / 100)) * (1 - dp / 100) * (1 - dpd / 100))
        taken = stat_sum("dmg_taken", ("m",)) + stat_sum("dmg_taken_" + branch, ("m",))
        tkR = (1 + (h["taken_bucket"] + taken) / 100) / (1 + h["taken_bucket"] / 100)
        pct = h["boss_pct"] if branch == "b" else h["norm_pct"]
        code = "boss_dmg" if branch == "b" else "norm_dmg"
        pcR = 1.0 if pvp else (1 + (pct + stat_sum(code, gr, ba=ba, atkc=atkc)) / 100) / (1 + pct / 100)
        sdR = (1 + (h["sd"] + stat_sum("skill_dmg", gr, ba=ba, atkc=atkc)) / 100) / (1 + h["sd"] / 100)
        bdR = (1 + (h["bad"] + stat_sum("bad", gr, ba=ba, atkc=atkc)) / 100) / (1 + h["bad"] / 100)
        asd = stat_sum("as", gr, ba=ba, atkc=atkc)
        return dict(fdR=fdR, atk=atk, crR=crR, mxR=mxR, dfR=dfR, tkR=tkR, pcR=pcR, sdR=sdR, bdR=bdR, asd=asd)

    out = {}
    for branch in ("b", "n"):
        hit, dot, ech, stn = coef_sums(branch)
        procs_d = proc_damage(branch)
        rc = ratios("c", branch)
        rhoA = h["avgbuff_snap"](h["charm_val"] * charm, rc["atk"]) / h["avgbuff"]
        rhoD = (1 + (h["agg_damage_avg"] - h["hex_avg"] + h["hex_snap"](stacks_hex)) / 100) / (1 + h["agg_damage_avg"] / 100)
        if branch == "b":
            rhoF = (1 + (h["agg_fd_boss_only"] - h["chalice_avg_boss"] + h["chalice_full"]) / 100) / (1 + h["agg_fd_boss_only"] / 100)
            extra, pct = h["extra_boss"], h["boss_pct"]
            BAS = BAB
        else:
            rhoF = (1 + (h["agg_fd_norm_only"] - h["chalice_avg_norm"] + h["chalice_full"]) / 100) / (1 + h["agg_fd_norm_only"] / 100)
            extra, pct = h["extra_norm"], h["norm_pct"]
            BAS = BAN
        rhoH = (1 + h["horn_full"] / 100) / (1 + h["horn_avg"] / 100)
        core = (rhoA * rhoD * rhoF * rhoH * rc["fdR"] * rc["crR"] * rc["mxR"] * rc["dfR"] * rc["tkR"] * rc["pcR"] * lvlmult
                * (stm_b if branch == "b" else stm_n))
        if h.get("watch_per"):          # Shiny Watch (patch 2026-11-26, app only: the frozen workbooks never set it): the companion's own Final Damage ramp (compounding stacks) over its window W
            core *= _ramp_avg_factor(W, h["watch_max"], h["watch_interval"], h["watch_per"])      # every stack is its own Final Damage factor: they compound
        tf = tf_b if branch == "b" else tf_n
        dmg = h["unit"] * core * (BAS * rc["bdR"] + skratio * rc["sdR"] * (hit + dot + tf * (ech + stn + procs_d)))
        dmg *= (1 if pvp else 1 + pct / 100) * extra
        # player uplift
        rp = ratios("p", branch)
        core_p = (((1 + (h["attack_bucket_avg"] + rp["atk"]) / 100) / (1 + h["attack_bucket_avg"] / 100)) * rp["fdR"] * rp["crR"]
                  * rp["mxR"] * rp["dfR"] * rp["tkR"] * rp["pcR"])
        as_ratio = _aps_after(h["aps"], rp["asd"]) / h["aps"]
        pl = h["player_boss"] if branch == "b" else h["player_norm"]
        pb = h["player_basic_boss"] if branch == "b" else h["player_basic_norm"]
        share = pb / pl if pl > 0 else 0.0
        ratio_p = core_p * (share * rp["bdR"] * as_ratio + (1 - share) * rp["sdR"])
        out[branch] = (dmg, pl * W * (ratio_p - 1) * tf)
    return out["b"][0], out["n"][0], out["b"][1], out["n"][1], 0.0


def _casts(r, W):
    """casts of a row that start inside a window of W seconds: s + t0 + n*per, n = 0, 1, ... with t0 + n*per < W (ties excluded, 1e-9 tolerance)"""
    return int((W - 1e-9 - r["t0"]) // r["per"]) + 1


def _uptime(r, N, W):
    """share of the window a timed effect (duration `dur`, cast every `per` from t0) is up, N = its casts in the window (cast N-1 may be cut off by the
    window end; casts further apart than `dur` never overlap)"""
    if N <= 0:
        return 0.0
    return ((N - 1) * min(r["dur"], r["per"]) + min(r["dur"], W - r["t0"] - (N - 1) * r["per"])) / W


def _ramp_exp(rows, W):
    for r in rows:
        if r["kind"] == "ramp" and r["ramp_mode"] == "exp":
            lnr = math.log(1 + r["val"] / 100)
            cap = r["ramp_cap"]
            if W <= cap:
                return (math.exp(lnr * W) - 1) / (lnr * W)
            return ((math.exp(lnr * cap) - 1) / lnr + (W - cap) * math.exp(lnr * cap)) / W
    return 1.0
