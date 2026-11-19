"""Status-effect / KO timeline model (time-resolved, 1-second bins).

Why it exists: the rest of the workbook is a time-AVERAGED model.  Status Effect Damage (damage while the enemy is frozen/stunned) and the
KO phases of World Boss / Enhancement Dungeon (boss takes x2 while knocked out) only matter in the moments they happen, so the player's
timing matters: buffs are aligned to the windows, cooldown skills are held for them, Hexagon Necklace's stacks line up with them.

This module has two halves that must agree cell-for-cell:
  * `solve(h)`   - plain-Python reference (loops, no spreadsheet tricks); used by verify scripts and as the spec;
  * `cells(h)`   - Excel formula generator (one "strip" of NB_MAX bin rows), see the bottom of the file.

Model (boss/single-target branch; the normal-monster branch only gets a uniform factor, see the builders):
  bin i covers [i, i+1) seconds; act_i = share of the bin inside the fight.
  status multiplier  mult_i = (1-k_i)*(1 + S/100*stun_i) + k_i*2*(1 + S/100)      (k_i = share of the bin inside a KO window;
                                                                                    KO also uses the Status Effect Damage input - user 2026-11-14)
  hexagon factor     hexf_i = 1 + hex_v*MIN(hex_max, INT(i/hex_period))/100
  every buff / cooldown skill is cast at the times that maximise  sum(value)  subject to cast spacing >= its cooldown (dynamic programme over
  the bins, `dp[t] = MAX(dp[t-1], v[t] + dp[t-cd])`); buffs first (value = coverage weighted by mult*hexf), then the skills (value of a cast =
  burst: Wt[t]; dot: mean of Wt over the dot window; end-of-window effect (Mist Eruption): Wt[t+L]; minus the basic attack the cast replaces),
  where Wt_i = mult_i * B_i (buff Attack%/Infinity state with the CHOSEN buff casts, and Hexagon).
  Rows that are not cooldown casts (Basic Attack, procs, Ignite walls, ...) are spread uniformly over the fight.
Outputs are TIMING FACTORS relative to the averaged model (B_model = mean buff bucket * (1 + Hexagon average)):
  phi_row  = sum(cast_t * V_row(t)) / (sum(cast_t * V0_row(t)) * B_model)      (V0 = same shape with Wt == 1)
  phi_unif = sum(Wt_i * act_i) / (sum(act_i) * B_model)
"""
import math

NB_MAX = 75              # bins (1 s each): the longest fixed fight is World Boss, 75 s
EPS = 1e-9


def _cd_bins(cd):
    return max(1, int(math.ceil(cd - 1e-9)))


def _cov(t0, i, dur):
    """share of bin i covered by an effect of length `dur` starting at t0 (0 before t0)"""
    if i < t0:
        return 0.0
    return max(0.0, min(1.0, t0 + dur - i))


def _dp(v, cdb, nb):
    """returns (dp, take, cast) for values v[0..nb-1] and spacing cdb (bins)"""
    dp = [0.0] * nb
    take = [0] * nb
    for t in range(nb):
        prev = dp[t - 1] if t > 0 else 0.0
        cand = v[t] + (dp[t - cdb] if t - cdb >= 0 else 0.0)
        dp[t] = max(prev, cand)
        # a gain below floating-point noise is not a gain (exact ties between placements must resolve the same way in Excel and Python)
        take[t] = 1 if dp[t] > prev + 1e-9 * max(1.0, abs(prev)) else 0
    cast = [0] * nb
    for t in range(nb - 1, -1, -1):
        later = sum(cast[t + 1: min(nb, t + cdb)])
        cast[t] = 1 if (take[t] and later == 0) else 0
    return dp, take, cast


def ramp_profile(b, tau):
    """Infinity-style ramp: p0 -> p1 over ramp_t seconds then held, scaled so the average over the BASE duration equals 1"""
    p0, p1, rt, d0 = b["p0"], b["p1"], b["ramp_t"], b["dur0"]
    avg = ((p0 + p1) / 2 * rt + p1 * max(0.0, d0 - rt)) / d0
    return (p0 + (p1 - p0) * min(tau, rt) / rt) / avg


def pl_stun_vector(rows, T, nb):
    """Expected share of each bin the enemy is stunned/frozen by the PLAYER's own stunning skills.  rows: dicts {typ 'cast'|'periodic', cd, dur, p, t0, on,
    tick, win}; casts at t0 + j*cd (j < casts within T).  'cast' = one stun of `dur` per cast; 'periodic' = a summon that rolls chance p for a `dur` stun every
    `tick` seconds during `win` seconds after each cast (Marksman's Frostprey)."""
    out = []
    for i in range(nb):
        tot = 0.0
        for r in rows:
            if not r.get("on", 1):
                continue
            cd, t0 = r["cd"], r["t0"]
            n = max(0, int((T - t0 - 1e-9) // cd) + 1)
            x = max(0.0, (i + 1 - t0) - 1e-9)
            jj = int(x // cd)
            if (i + 1 - t0) > 1e-9 and jj < n:
                tj = t0 + jj * cd
                if r.get("typ", "cast") == "cast":
                    tot += r["p"] * max(0.0, min(i + 1, tj + r["dur"]) - max(i, tj))
                else:
                    tot += r["p"] * r["dur"] / r["tick"] * max(0.0, min(i + 1, tj + r["win"]) - max(i, tj))
        out.append(tot)
    return out


def solve(h):
    T = h["T"]
    nb = int(math.ceil(T - 1e-9))
    S = h["S"]
    act = [max(0.0, min(1.0, T - i)) for i in range(nb)]
    stun = h.get("stun") or [0.0] * nb
    ko = h.get("ko") or []
    kap = [sum(max(0.0, min(i + 1, b) - max(i, a)) for a, b in ko) for i in range(nb)]
    mult = [(1 - kap[i]) * (1 + S / 100 * stun[i]) + kap[i] * 2 * (1 + S / 100) for i in range(nb)]
    hexf = [1 + h["hex_v"] * min(h["hex_max"], int(i // h["hex_period"])) / 100 for i in range(nb)]
    mh = [mult[i] * hexf[i] * act[i] for i in range(nb)]

    # ---- buffs
    out = dict(nb=nb, act=act, mult=mult, hexf=hexf, buffs={}, groups={}, rows={})
    atk_sum = [0.0] * nb
    inf_sum = [0.0] * nb
    for b in h["buffs"]:
        cdb = _cd_bins(b["cd"])
        if not b["on"]:
            out["buffs"][b["id"]] = dict(cast=[0] * nb, cover=[0.0] * nb, n=0)
            continue

        def prof(t0, i, b=b):
            if b["kind"] == "atk":
                return b["F"]
            return b["F"] * ramp_profile(b, i + 0.5 - t0)
        v = [sum(mh[m] * _cov(t0, m, b["dur"]) * prof(t0, m) for m in range(t0, nb)) for t0 in range(nb)]
        dp, take, cast = _dp(v, cdb, nb)
        cover = [min(1.0, sum(cast[t0] * _cov(t0, i, b["dur"]) for t0 in range(i + 1))) for i in range(nb)]
        eff = [(cover[i] * b["F"] if b["kind"] == "atk" else sum(cast[t0] * _cov(t0, i, b["dur"]) * prof(t0, i) for t0 in range(i + 1)))
               for i in range(nb)]       # an Attack% buff recast while still up counts once (capped at 100% cover), like the Excel strip
        out["buffs"][b["id"]] = dict(cast=cast, cover=cover, n=sum(cast), v=v, dp=dp, take=take)
        if b["kind"] == "atk":
            atk_sum = [atk_sum[i] + eff[i] if b["kind"] == "atk" else atk_sum[i] for i in range(nb)]
            out["buffs"][b["id"]]["eff"] = eff
        else:
            inf_sum = [inf_sum[i] + eff[i] for i in range(nb)]
            out["buffs"][b["id"]]["eff"] = eff
    # attack buffs overlap-capped through their own cover (F * cover); Infinity multiplicative
    charm = [h.get("charm_v", 0.0) if (i >= 10 and (i - 10) % 10 < 5) else 0.0 for i in range(nb)]
    Bbuff = [(1 + (h["A0"] + charm[i] + atk_sum[i]) / 100) * (1 + inf_sum[i] / 100) for i in range(nb)]
    n_act = sum(act)
    Bbuff_mean = sum(Bbuff[i] * act[i] for i in range(nb)) / n_act
    Bmodel = Bbuff_mean * (1 + h["hex_avg"] / 100)
    Wt = [mult[i] * Bbuff[i] * hexf[i] * act[i] for i in range(nb)]
    out.update(Bbuff=Bbuff, Bbuff_mean=Bbuff_mean, Bmodel=Bmodel, Wt=Wt)

    # ---- skill groups
    def shape(typ, w, L, t, vec):
        """value of one cast at bin t for an entry (vec = Wt, or act for the unweighted version)"""
        if typ == "burst":
            return w * vec[t]
        if typ == "dot":
            return w / L * sum(vec[m] * _cov(t, m, L) for m in range(t, nb))
        if typ == "end":
            k = int(t + L + 1e-9)
            return w * vec[k] if k < nb else 0.0
        raise ValueError(typ)
    ones = act
    num = {}
    den = {}
    fs = {}
    for g in h["groups"]:
        cdb = _cd_bins(g["cd"])
        if not g["on"]:
            out["groups"][g["id"]] = dict(cast=[0] * nb, n=0)
            continue
        v = []
        for t in range(nb):
            val = sum(shape(e["typ"], e["w"], e.get("L", 0), t, Wt) for e in g["entries"])
            if g.get("slot"):
                val -= h["c_slot"] * Wt[t]
            v.append(val)
        dp, take, cast = _dp(v, cdb, nb)
        if g.get("fixed"):      # a stunning skill cast on cooldown from t0 (its stun windows must not depend on the optimiser)
            cast = [max(0, math.ceil(max(0.0, i + 1 - g["t0"]) / g["cd"] - 1e-12)) - max(0, math.ceil(max(0.0, i - g["t0"]) / g["cd"] - 1e-12))
                    for i in range(nb)]
        out["groups"][g["id"]] = dict(cast=cast, n=sum(cast), v=v, dp=dp, take=take)
        for e in g["entries"]:
            vn = sum(cast[t] * shape(e["typ"], e["w"], e.get("L", 0), t, Wt) for t in range(nb))
            fs_e = e.get("on", 1) * sum(cast[t] * shape(e["typ"], 1.0, e.get("L", 0), t, ones) for t in range(nb))
            num[e["row"]] = num.get(e["row"], 0.0) + vn
            den[e["row"]] = den.get(e["row"], 0.0) + e["w"] * fs_e
            fs[e["row"]] = fs.get(e["row"], 0.0) + fs_e
    out["fs"] = fs
    for row in num:
        out["rows"][row] = (num[row] / (den[row] * Bmodel)) if den[row] > 0 else 1.0
    out["phi_unif"] = sum(Wt) / (n_act * Bmodel)
    out["mult_mean"] = sum(mult[i] * act[i] for i in range(nb)) / n_act
    return out


# ======================================================================================================================
# Excel generator
# ======================================================================================================================
def _minel(a, b):
    return f"((({a})+({b})-ABS(({a})-({b})))/2)"


def _maxel(a, b):
    return f"((({a})+({b})+ABS(({a})-({b})))/2)"


class Item:
    def __init__(self, kind, name, label, fn):
        self.kind, self.name, self.label, self.fn = kind, name, label, fn


def cells(h):
    """Excel cell list for ONE evaluation strip.  `h` carries Excel EXPRESSIONS (strings or numbers) with the same keys as solve():
    on (engine switch), T, S, ko=[(a,b),(a,b)] (0,0 when absent), hex_v, hex_period, hex_max, A0, hex_avg, c_slot,
    stun (callable i -> expr, or None),
    buffs=[{id,kind,dur,cd,F,on, p0,p1,ramp_t,dur0 (ramp kind: numbers)}], groups=[{id,cd,on,slot,entries=[{row,typ,w,L}]}].
    Items: kind 's' (scalar, fn(R) -> formula) or 'v' (vector over NB_MAX bins, fn(R, i) -> formula); R.s(name), R.at(name, i), R.rng(name)."""
    items = []

    def S_(name, label, fn):
        items.append(Item("s", name, label, fn))

    def V_(name, label, fn):
        items.append(Item("v", name, label, fn))

    N = NB_MAX
    S_("on", "Engine on (1/0): fixed-length fight with status windows, single-target branch", lambda R: str(h["on"]))
    S_("T", "Fight length T (s)", lambda R: str(h["T"]))
    S_("S", "Status Effect Damage %", lambda R: str(h["S"]))
    (a1, b1), (a2, b2) = h["ko"]
    S_("ko1a", "KO window 1 start (s)", lambda R: str(a1))
    S_("ko1b", "KO window 1 end (s)", lambda R: str(b1))
    S_("ko2a", "KO window 2 start (s)", lambda R: str(a2))
    S_("ko2b", "KO window 2 end (s)", lambda R: str(b2))
    S_("hex_v", "Hexagon Necklace Damage % per stack (0 = not equipped)", lambda R: str(h["hex_v"]))
    S_("hex_period", "Hexagon: seconds per stack", lambda R: str(h["hex_period"]))
    S_("hex_max", "Hexagon: max stacks", lambda R: str(h["hex_max"]))
    S_("A0", "Attack % bucket without the cast buffs and without Charm (artifacts, averaged)", lambda R: str(h["A0"]))
    S_("hex_avg", "Hexagon average used by the averaged model (%)", lambda R: str(h["hex_avg"]))
    S_("charm_v", "Charm of the Undead: Attack % while active (0 = not equipped)", lambda R: str(h.get("charm_v", 0)))
    S_("c_slot", "Basic attack replaced by a cast (boss damage per action)", lambda R: str(h["c_slot"]))
    S_("nact", "Fight seconds (sum of act; at least a hair above 0 so PvP / steady-state content, where the engine is off, stays error-free)",
       lambda R: f'MAX(0.000001,SUM({R.rng("act")}))')

    V_("idx", "bin index (s)", lambda R, i: str(i))
    V_("act", "share of the bin inside the fight", lambda R, i: f'MAX(0,MIN(1,{R.s("T")}-{i}))')
    V_("kap", "share of the bin spent KO'd",
       lambda R, i: (f'MAX(0,MIN({i}+1,{R.s("ko1b")})-MAX({i},{R.s("ko1a")}))+MAX(0,MIN({i}+1,{R.s("ko2b")})-MAX({i},{R.s("ko2a")}))'))
    stun = h.get("stun")
    pst = h.get("pl_stun") or []
    for k, e in enumerate(pst):
        for fld in ("cd", "dur", "p", "on", "t0", "tick", "win"):
            S_(f"pst.{k}.{fld}", f'Player stun {e["id"]}: {fld}', lambda R, e=e, fld=fld: str(e.get(fld, {"tick": 1, "win": 0, "on": 1}.get(fld, 0))))
        S_(f"pst.{k}.n", f'Player stun {e["id"]}: casts in the fight',
           lambda R, k=k: f'MAX(0,INT(({R.s("T")}-{R.s(f"pst.{k}.t0")}-0.000000001)/{R.s(f"pst.{k}.cd")})+1)')

    def pl_term(R, i, k, e):
        cd, t0 = R.s(f"pst.{k}.cd"), R.s(f"pst.{k}.t0")
        jj = f'INT(MAX(0,({i}+1-{t0})-0.000000001)/{cd})'
        tj = f'({t0}+{jj}*{cd})'
        valid = f'((({i}+1-{t0})>0.000000001)*({jj}<{R.s(f"pst.{k}.n")}))'
        if e.get("typ", "cast") == "cast":
            body = f'{R.s(f"pst.{k}.p")}*MAX(0,MIN({i}+1,{tj}+{R.s(f"pst.{k}.dur")})-MAX({i},{tj}))'
        else:
            body = (f'{R.s(f"pst.{k}.p")}*{R.s(f"pst.{k}.dur")}/{R.s(f"pst.{k}.tick")}'
                    f'*MAX(0,MIN({i}+1,{tj}+{R.s(f"pst.{k}.win")})-MAX({i},{tj}))')
        return f'{R.s(f"pst.{k}.on")}*{valid}*{body}'

    def stun_fn(R, i):
        parts = [str(stun(i)) if stun else "0"] + [pl_term(R, i, k, e) for k, e in enumerate(pst)]
        return "0" if len(parts) == 1 and parts[0] == "0" else f'MIN(1,{"+".join(parts)})'
    V_("stun", "expected share of the bin the enemy is stunned/frozen (companion + the player's own stunning skills)", stun_fn)
    V_("mult", "status multiplier on damage dealt in the bin",
       lambda R, i: (f'(1-{R.at("kap", i)})*(1+{R.s("S")}/100*{R.at("stun", i)})+{R.at("kap", i)}*2*(1+{R.s("S")}/100)'))
    V_("charm", "Charm of the Undead Attack % in the bin (5 s on, 5 s off, from second 10)",
       lambda R, i: f'IF(AND({i}>=10,MOD({i}-10,10)<5),{R.s("charm_v")},0)')
    V_("hexf", "Hexagon Necklace factor",
       lambda R, i: f'1+{R.s("hex_v")}*MIN({R.s("hex_max")},INT({i}/{R.s("hex_period")}))/100')
    V_("dw", "Damage weight of the bin from the explicit time-dependent state (Hexagon, Charm, KO/stun windows): act x hexf x (1 + Attack%) x mult",
       lambda R, i: (f'{R.at("act", i)}*{R.at("hexf", i)}*(1+({R.s("A0")}+{R.at("charm", i)})/100)*IF({R.s("on")}=1,{R.at("mult", i)},1)'))
    V_("mh", "mult * hexf * act", lambda R, i: f'{R.at("mult", i)}*{R.at("hexf", i)}*{R.at("act", i)}')

    def plan(pfx, label):
        def fn(R):
            terms = "&".join(f'IF({R.at(f"{pfx}.cast", i)}=1,"{i} ","")' for i in range(N))
            return f'TRIM({terms})'
        S_(f"{pfx}.plan", f"{label}: cast at (s)", fn)

    def dp_cols(pfx, label, vfn, cd, on, fixed_t0=None):
        """value column vfn(R,i), DP, take, cast and the cast count for one cooldown thing"""
        S_(f"{pfx}.cd", f"{label}: effective cooldown (s)", lambda R: f'{cd}')
        S_(f"{pfx}.on", f"{label}: available (1/0)", lambda R: f'IF({on},1,0)')
        S_(f"{pfx}.cdb", f"{label}: cooldown in bins", lambda R: f'MAX(1,ROUNDUP({R.s(f"{pfx}.cd")}-0.000000001,0))')
        V_(f"{pfx}.v", f"{label}: value of a cast starting in the bin", lambda R, i: f'IF({R.s(f"{pfx}.on")}=1,{vfn(R, i)},0)')
        V_(f"{pfx}.dp", f"{label}: best total up to the bin",
           lambda R, i: (f'MAX(0,{R.at(f"{pfx}.v", i)})' if i == 0 else
                         f'MAX({R.at(f"{pfx}.dp", i - 1)},{R.at(f"{pfx}.v", i)}'
                         f'+IF({i}>={R.s(f"{pfx}.cdb")},INDEX({R.rows(f"{pfx}.dp", 0, i - 1)},{i}-{R.s(f"{pfx}.cdb")}+1),0))'))
        V_(f"{pfx}.take", f"{label}: the best total rose here",
           lambda R, i: (f'IF({R.at(f"{pfx}.dp", i)}>{R.at(f"{pfx}.dp", i - 1) if i > 0 else 0}'
                         f'+0.000000001*MAX(1,ABS({R.at(f"{pfx}.dp", i - 1) if i > 0 else 0})),1,0)'))

        def cast_fn(R, i, pfx=pfx):
            if i >= N - 1:
                later = "0"
            else:
                rr = R.rows(f"{pfx}.cast", i + 1, N - 1)
                later = (f'IF({R.s(f"{pfx}.cdb")}>=2,SUM(INDEX({rr},1):'
                         f'INDEX({rr},MIN({N - 1 - i},{R.s(f"{pfx}.cdb")}-1))),0)')
            return f'IF(AND({R.at(f"{pfx}.take", i)}=1,{later}=0),1,0)'

        def fixed_cast_fn(R, i, pfx=pfx):
            cd, t0 = R.s(f"{pfx}.cd"), fixed_t0
            return (f'IF(AND({R.s(f"{pfx}.on")}=1,{R.at("act", i)}>0),MAX(0,ROUNDUP(MAX(0,{i}+1-{t0})/{cd}-0.000000000001,0))-MAX(0,ROUNDUP(MAX(0,{i}-{t0})/{cd}-0.000000000001,0)),0)')
        V_(f"{pfx}.cast", f"{label}: cast in the bin (1/0)" + (" - FIXED schedule (cooldown from t0)" if fixed_t0 is not None else ""),
           fixed_cast_fn if fixed_t0 is not None else cast_fn)
        S_(f"{pfx}.n", f"{label}: casts", lambda R: f'SUM({R.rng(f"{pfx}.cast")})')
        plan(pfx, label)

    # ---- buffs
    for b in h["buffs"]:
        pfx = f'buff.{b["id"]}'
        S_(f"{pfx}.F", f'Buff {b["id"]}: effect (Attack % while up / average Final Damage %)', lambda R, b=b: str(b["F"]))
        S_(f"{pfx}.dur", f'Buff {b["id"]}: duration (s)', lambda R, b=b: str(b["dur"]))
        if b["kind"] != "atk":
            p0, p1, rt, d0 = b["p0"], b["p1"], b["ramp_t"], b["dur0"]
            avg = ((p0 + p1) / 2 * rt + p1 * max(0.0, d0 - rt)) / d0

        def vfn(R, i, b=b, pfx=pfx):
            idx = R.rng("idx")
            cov = _minel("1", _maxel("0", f'{i}+{R.s(f"{pfx}.dur")}-{idx}'))
            F = R.s(f"{pfx}.F")
            if b["kind"] == "atk":
                return f'{F}*SUMPRODUCT(({idx}>={i})*{R.rng("mh")}*{cov})'
            p0, p1, rt, d0 = b["p0"], b["p1"], b["ramp_t"], b["dur0"]
            avg = ((p0 + p1) / 2 * rt + p1 * max(0.0, d0 - rt)) / d0
            prof = f'({p0}+({p1}-{p0})*{_minel(f"{idx}+0.5-{i}", str(rt))}/{rt})/{avg}'
            return f'{F}*SUMPRODUCT(({idx}>={i})*{R.rng("mh")}*{cov}*{prof})'
        dp_cols(pfx, f'Buff {b["id"]}', vfn, b["cd"], b["on"])

        def eff(R, i, b=b, pfx=pfx):
            idx = R.rng("idx")
            cov = _minel("1", _maxel("0", f'{idx}+{R.s(f"{pfx}.dur")}-{i}'))
            F = R.s(f"{pfx}.F")
            if b["kind"] == "atk":
                return f'MIN(1,SUMPRODUCT(({idx}<={i})*{R.rng(f"{pfx}.cast")}*{cov}))*{F}'
            p0, p1, rt, d0 = b["p0"], b["p1"], b["ramp_t"], b["dur0"]
            avg = ((p0 + p1) / 2 * rt + p1 * max(0.0, d0 - rt)) / d0
            prof = f'({p0}+({p1}-{p0})*{_minel(f"{i}+0.5-{idx}", str(rt))}/{rt})/{avg}'
            return f'{F}*SUMPRODUCT(({idx}<={i})*{R.rng(f"{pfx}.cast")}*{cov}*{prof})'
        V_(f"{pfx}.eff", f'Buff {b["id"]}: effect in the bin (Attack % / Final Damage %)', eff)
    atk_ids = [b["id"] for b in h["buffs"] if b["kind"] == "atk"]
    inf_ids = [b["id"] for b in h["buffs"] if b["kind"] != "atk"]
    V_("atk_sum", "Attack % from the cast buffs",
       lambda R, i: "+".join(R.at(f"buff.{k}.eff", i) for k in atk_ids) if atk_ids else "0")
    V_("inf_sum", "Final Damage % from ramping buffs",
       lambda R, i: "+".join(R.at(f"buff.{k}.eff", i) for k in inf_ids) if inf_ids else "0")
    V_("Bbuff", "Buff bucket (Attack %, Infinity)",
       lambda R, i: f'(1+({R.s("A0")}+{R.at("charm", i)}+{R.at("atk_sum", i)})/100)*(1+{R.at("inf_sum", i)}/100)')
    S_("Bbuff_mean", "Mean buff bucket over the fight", lambda R: f'SUMPRODUCT({R.rng("Bbuff")},{R.rng("act")})/{R.s("nact")}')
    S_("Bmodel", "Averaged model's buff x Hexagon bucket", lambda R: f'MAX(0.000001,{R.s("Bbuff_mean")}*(1+{R.s("hex_avg")}/100))')
    V_("Wt", "Damage weight of the bin (status x buffs x Hexagon)",
       lambda R, i: f'{R.at("mult", i)}*{R.at("Bbuff", i)}*{R.at("hexf", i)}*{R.at("act", i)}')

    # ---- cooldown skills
    rows_num, rows_den, rows_fs = {}, {}, {}
    for g in h["groups"]:
        gp = f'grp.{g["id"]}'
        ents = g["entries"]

        def shape(R, i, k, e, weight_vec, unit=False, gp=gp):
            typ = e["typ"]
            w = "1" if unit else R.s(f"{gp}.e{k}.w")
            L = R.s(f"{gp}.e{k}.L")
            if typ == "burst":
                return f'{w}*{R.at(weight_vec, i)}'
            if typ == "dot":
                idx = R.rng("idx")
                return f'{w}/{L}*SUMPRODUCT(({idx}>={i})*{R.rng(weight_vec)}*{_minel("1", _maxel("0", f"{i}+{L}-{idx}"))})'
            if typ == "end":
                kk = f'INT({i}+{L}+0.000000001)'
                return f'IF({kk}<{N},{w}*INDEX({R.rng(weight_vec)},{kk}+1),0)'
            raise ValueError(typ)
        for k, e in enumerate(ents):
            S_(f"{gp}.e{k}.w", f'{g["id"]} / {e["row"]}: damage of one cast ({e["typ"]}), before timing', lambda R, e=e: str(e["w"]))
            S_(f"{gp}.e{k}.L", f'{g["id"]} / {e["row"]}: window length (s)', lambda R, e=e: str(e.get("L", 1)))
            S_(f"{gp}.e{k}.on", f'{g["id"]} / {e["row"]}: counts (1/0)', lambda R, e=e: f'IF({e.get("on", 1)},1,0)')
            V_(f"{gp}.e{k}.V", f'{g["id"]} / {e["row"]} ({e["typ"]}): weighted value of a cast',
               lambda R, i, k=k, e=e, gp=gp, shape=shape: shape(R, i, k, e, "Wt", gp=gp))
            V_(f"{gp}.e{k}.V0", f'{g["id"]} / {e["row"]} ({e["typ"]}): unit-weight value of a cast (share of the cast that lands inside the fight)',
               lambda R, i, k=k, e=e, gp=gp, shape=shape: shape(R, i, k, e, "act", unit=True, gp=gp))

        def gv(R, i, g=g, gp=gp, ents=ents):
            tot = "+".join(R.at(f"{gp}.e{k}.V", i) for k in range(len(ents)))
            if g.get("slot"):
                tot += f'-{R.s("c_slot")}*{R.at("Wt", i)}'
            return tot
        dp_cols(gp, f'Skill {g["id"]}', gv, g["cd"], g["on"], fixed_t0=(g["t0"] if g.get("fixed") else None))
        for k, e in enumerate(ents):
            rows_num.setdefault(e["row"], []).append(lambda R, gp=gp, k=k: f'SUMPRODUCT({R.rng(f"{gp}.cast")},{R.rng(f"{gp}.e{k}.V")})')
            rows_den.setdefault(e["row"], []).append(
                lambda R, gp=gp, k=k: f'{R.s(f"{gp}.e{k}.w")}*SUMPRODUCT({R.rng(f"{gp}.cast")},{R.rng(f"{gp}.e{k}.V0")})')
            rows_fs.setdefault(e["row"], []).append(
                lambda R, gp=gp, k=k: f'{R.s(f"{gp}.e{k}.on")}*SUMPRODUCT({R.rng(f"{gp}.cast")},{R.rng(f"{gp}.e{k}.V0")})')
    for row in rows_num:
        S_(f"phi.{row}", f"Timing factor {row}",
           lambda R, row=row: (f'IF(({"+".join(f(R) for f in rows_den[row])})>0,({"+".join(f(R) for f in rows_num[row])})/'
                               f'(({"+".join(f(R) for f in rows_den[row])})*{R.s("Bmodel")}),1)'))
        S_(f"fs.{row}", f"Effective casts of {row} that land inside the fight (cast count, last DoT window / eruption truncated)",
           lambda R, row=row: "+".join(f(R) for f in rows_fs[row]))
    S_("phi_unif", "Timing factor for uniformly spread damage", lambda R: f'SUM({R.rng("Wt")})/({R.s("nact")}*{R.s("Bmodel")})')
    S_("mult_mean", "Mean status multiplier over the fight", lambda R: f'SUMPRODUCT({R.rng("mult")},{R.rng("act")})/{R.s("nact")}')
    return items


class Layout:
    """Places a strip: scalars in one column (label | value) from `row0`, then the bin table (one column per vector, NB_MAX rows).
    `sheet` (optional) qualifies every reference so another sheet can read the strip."""

    def __init__(self, items, row0, col0, sheet=None):
        from openpyxl.utils import get_column_letter as L
        self.items, self.row0, self.col0, self.sheet = items, row0, col0, sheet
        self.scalars = [it for it in items if it.kind == "s"]
        self.vectors = [it for it in items if it.kind == "v"]
        self.srow = {it.name: row0 + 1 + k for k, it in enumerate(self.scalars)}
        self.vhead = row0 + len(self.scalars) + 3
        self.vcol = {it.name: col0 + 2 + k for k, it in enumerate(self.vectors)}
        self.L = L
        self.height = len(self.scalars) + 3 + NB_MAX + 1

    def _q(self, ref):
        return f"'{self.sheet}'!{ref}" if self.sheet else ref

    def s(self, name):
        return self._q(f"${self.L(self.col0 + 1)}${self.srow[name]}")

    def at(self, name, i):
        return self._q(f"${self.L(self.vcol[name])}${self.vhead + 1 + i}")

    def rng(self, name):
        c = self.L(self.vcol[name])
        return self._q(f"${c}${self.vhead + 1}:${c}${self.vhead + NB_MAX}")

    def rows(self, name, i0, i1):
        c = self.L(self.vcol[name])
        return self._q(f"${c}${self.vhead + 1 + i0}:${c}${self.vhead + 1 + i1}")

    def write(self, ws):
        """write labels + formulas into worksheet `ws` (references unqualified when the strip lives on `ws`)"""
        for it in self.scalars:
            ws.cell(row=self.srow[it.name], column=self.col0, value=it.label)
            ws.cell(row=self.srow[it.name], column=self.col0 + 1, value="=" + it.fn(self))
        for it in self.vectors:
            ws.cell(row=self.vhead, column=self.vcol[it.name], value=it.name)
            for i in range(NB_MAX):
                ws.cell(row=self.vhead + 1 + i, column=self.vcol[it.name], value="=" + it.fn(self, i))


# ======================================================================================================================
# The PLAYER's own stunning / freezing skills (class builders)
# ======================================================================================================================
def player_stun_entries(spec, cell, t0, level_expr="0"):
    """Excel host entries (`pst`) for the companion chain / the strip's `pl_stun`.
    spec: list of {id, row (Calc row key of the cast), typ 'cast'|'periodic', dur, p, [tick, win], [min_level]}.  cell(letter, key) = that Calc(-twin) cell.
    The skill is cast on cooldown from t0 (its row's effective cooldown 1/Q); `on` = the row is unlocked (and the stun mastery's level reached)."""
    out = []
    for e in spec:
        gate = f'{cell("C", e["row"])}=TRUE'
        if e.get("min_level"):
            gate = f'AND({gate},{level_expr}>={e["min_level"]})'
        d = dict(id=e["id"], typ=e.get("typ", "cast"), cd=f'IFERROR(1/{cell("Q", e["row"])},1000000)', dur=str(e["dur"]), p=str(e.get("p", 1.0)),
                 on=gate, t0=t0)
        if d["typ"] == "periodic":
            d["tick"], d["win"] = str(e["tick"]), str(e["win"])
        out.append(d)
    return out


def player_stun_export(entries):
    """(key, expression) pairs for the Companion sheet's exported host values (potential_cubes_ev.py rebuilds `pst` from pst<k>_...)."""
    out = []
    for k, e in enumerate(entries):
        out += [(f"pst{k}_cd", e["cd"]), (f"pst{k}_dur", e["dur"]), (f"pst{k}_p", e["p"]), (f"pst{k}_on", f'IF({e["on"]},1,0)'),
                (f"pst{k}_t0", e["t0"]), (f"pst{k}_tick", e.get("tick", "1")), (f"pst{k}_win", e.get("win", "0")),
                (f"pst{k}_per", "1" if e["typ"] == "periodic" else "0")]
    return out
