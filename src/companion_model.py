"""Companion model shared by every class's build script: a table-driven formula generator.

A companion is an ally summoned for D = 30s * (1 + Companion Summoning Time Increase %) that deals damage using a SNAPSHOT of the
player's stats taken when it is summoned, multiplied by a companion-level factor.  Every companion's kit (src/companion_kits.py) is
DATA: one row per component, written to the `CompanionKits` sheet.  The formulas built here read that table through SUMPRODUCT masks on
the chosen companion (Inputs), so ONE chain of cells serves every companion (and every Sensitivity block can override the choice).

Rules (user-confirmed 2026-11-11 .. 2026-11-13, see KNOWN_GAPS.md "Companions"):
* one companion at a time; the summon cooldown is always 90 s counted from the summon; earliest summon 7 s into a fight; fixed-length
  content: summoned once and up until the end of the fight (s = max(7, T - D), or a later threshold time that wins a better snapshot);
  Chapter Hunt (steady state): period = max(D, 90);
* damage = the player's per-hit pipeline (the host's Basic Attack row: unit = N/F) for each coefficient of the kit, with snapshot
  corrections (buffs up, Hexagon stacks, Charm window, Chalice assumed procced), the companion's own stat effects as ratios on the
  player's buckets, x the level multiplier 60..90%; Final Damage skills (Lv5/8/10 x1.25 each) are kit rows;
* the same action economy as the player (snapshot Attack Speed; each cooldown skill cast uses an action slot, the rest are basic
  attacks); a cooldown skill's n-th cast happens at t0 + n x (cooldown + CAST_TIME) after the summon (the cooldown only starts counting when the
  cast is finished; t0 = START_DELAY + k x FIRST_SLOT for the k-th action skill of the kit; user's in-game measurement 2026-11-18, constants and the
  rule in companion_kits.py `schedule()`): the CompanionKits sheet carries the static columns `per` (period) and `t0`, every cast count / uptime /
  DoT window / stun window below reads them.  Casts of a window W: INT((W - 1e-9 - t0) / per) + 1  (0 when W <= t0);
* proc chances follow the per-attack-per-enemy-hit rule (CLAUDE.md);
* monster debuffs add into the host's existing buckets and boost the player's damage as well.

`cells(h)` returns an ordered list of (name, label, fn) with fn(c) -> formula body (no leading '='), where `c(name)` resolves another
cell of the SAME evaluation (main sheet / grid column / Sensitivity block).  `h` is the host dict (see HOST_KEYS and the FP builder).
"""
import math
import re

from openpyxl.utils import get_column_letter

import companion_kits as ck

COMPANIONS = list(ck.COMPANIONS_ORDER)
COMPANION_CHOICES = ["None"] + COMPANIONS
COMPANION_BASE_DURATION = 30.0
COMPANION_EARLIEST_SUMMON = 7.0
COMPANION_SUMMON_COOLDOWN = 90.0                           # always 90 s, counted from the summon (user, 2026-11-12)
COMPANION_MAX_LEVEL = 18                                   # levels 1-18; the multiplier is 90% from level 10 on
COMPANION_LEVEL_CHOICES = ["Not unlocked"] + [str(i) for i in range(1, COMPANION_MAX_LEVEL + 1)]
LEVEL_MULT = [60, 64, 68, 72, 75, 78, 81, 84, 87, 90]      # companion level 1..10 (level 10+ = 90)
NUM_CANDIDATES = 3
NUM_PROC_SLOTS = 4
NUM_STUN_SLOTS = ck.max_stun_rows()                       # one scalar slot per stunning/freezing hit row of a companion (keeps the per-bin stun formulas short)
DOT_CAST_TERMS = max(1, max(math.ceil(r["dur"] / r["per"] - 1e-9) for r in ck.rows_with_keys()
                            if r["kind"] == "dot" and r["cd"] < ck.NEVER and r["dur"] < ck.NEVER))
# ^ explicit per-cast terms in the whole-tick count of overlapping summons: the casts further from the end than ceil(dur / per) always last their full
#   duration (2 = Corsair's 30 s cannon on a 15.5 s period); derived from the kit table, so a longer-lasting dot row automatically gets more terms
GRID_POINTS = 121                                          # Companion sheet grid: Summoning Time Increase % = b0 + n, n = 0..120
# "Companion Summoning Time Increase %" potential lines (boots): value per rarity tier.  A potential's lines roll at the item's
# tier or the tier below (user, 2026-11-12), so e.g. 12% (legendary) and 5% (epic) never share a potential.
POTENTIAL_LINE_TIERS = [("Epic", 5), ("Unique", 8), ("Legendary", 12), ("Mystic", 20)]
POTENTIAL_MAX_LINES = 3


def potential_line_totals():
    """{total %: sorted list of 'Tier: a+b+c' descriptions} over every combination of 1-3 summoning-time lines that can
    share one potential (lines from the item's tier or the tier directly below)."""
    out = {}
    for i, (tier, v) in enumerate(POTENTIAL_LINE_TIERS):
        vals = sorted({v} | ({POTENTIAL_LINE_TIERS[i - 1][1]} if i > 0 else set()), reverse=True)

        def rec(prefix, start, remaining):
            if prefix:
                out.setdefault(sum(prefix), set()).add(f"{tier}: " + "+".join(str(x) for x in prefix))
            if remaining:
                for j in range(start, len(vals)):
                    rec(prefix + [vals[j]], j, remaining - 1)
        rec([], 0, POTENTIAL_MAX_LINES)
    return {k: sorted(v) for k, v in sorted(out.items())}


# ------------------------------------------------------------------------------------------------ kit table layout
KIT_SHEET = "CompanionKits"
SHEET_COLUMNS = ck.KIT_COLUMNS + ["idkey", "pkey", "tkf", "per", "t0", "skey"]
KIT_ROWS = ck.rows_with_keys()
KIT_FIRST_ROW = 2
KIT_LAST_ROW = KIT_FIRST_ROW + len(KIT_ROWS) - 1
_COL_LETTER = {c: get_column_letter(i + 1) for i, c in enumerate(SHEET_COLUMNS)}


def FULL(col):
    """The whole kit column (all companions)."""
    letter = _COL_LETTER[col]
    return f"{KIT_SHEET}!${letter}${KIT_FIRST_ROW}:${letter}${KIT_LAST_ROW}"


def K(col):
    """Token for the kit column restricted to the CHOSEN companion's rows (a ~14-row INDEX:INDEX range instead of the whole
    table - 16x cheaper SUMPRODUCTs); resolved by emit() with the evaluation's own kr0 / kn cells."""
    return f"@@{col}@@"


HOST_KEYS = [
    "choice", "inc", "lvl", "mt", "T", "content", "pvp_len", "cap", "w", "unit", "bad", "sd", "aps",
    "avgbuff", "attack_bucket_avg", "charm_val", "agg_damage_avg", "hex_avg", "agg_fd_boss_only", "agg_fd_norm_only",
    "chalice_avg_boss", "chalice_avg_norm", "chalice_full", "horn_avg", "horn_full", "boss_pct", "norm_pct", "extra_boss", "extra_norm",
    "player_boss", "player_norm", "player_uniform_boss", "player_basic_boss", "player_basic_norm",
    "cr_total", "cd_total", "min_dmg", "max_dmg", "defense", "def_pen", "taken_bucket",
]   # plus two callables: avgbuff_snap(charm_expr, extra_attack_pct) and hex_snap(stacks_expr)


def dummy_host():
    h = {k: "0" for k in HOST_KEYS}
    h.update(st_on="0", st_S="0", st_idx="0", st_mult="0", st_act="0", st_dw="0")
    h["avgbuff_snap"] = lambda charm_expr, extra: "0"
    h["hex_snap"] = lambda stacks: "0"
    return h


def cell_names():
    return [n for n, _, _ in cells(dummy_host())]


# ------------------------------------------------------------------------------------------------ small formula helpers
def minel(a, b):
    """Element-wise MIN usable inside SUMPRODUCT arrays (MIN() would aggregate the array)."""
    return f"((({a})+({b})-ABS(({a})-({b})))/2)"


def maxel(a, b):
    """Element-wise MAX usable inside SUMPRODUCT arrays."""
    return f"((({a})+({b})+ABS(({a})-({b})))/2)"


TIE = "0.000000001"


def cnt_expr(win, per, t0):
    """casts of a skill (period `per`, first cast at `t0`) that start inside a window of `win` seconds: t0 + n*per < win (ties excluded).  t0 < per for every
    kit row (asserted in companion_kits), so the argument never drops below -1 and the count is never negative."""
    return f"(INT(({win}-{TIE}-{t0})/{per})+1)"


def uptime_expr(win, per, t0, dur, minf):
    """share of a window of `win` seconds that a timed effect (length `dur`, cast every `per` from t0) is up: the casts but the last are cut off by the next
    cast (`per`), the last by the window end.  m = win - t0 - tie; (casts - 1) = INT(m/per); the last cast has MOD(m, per) + tie seconds left.
    `minf` = elementwise MIN (minel inside SUMPRODUCT, MIN on scalars)."""
    m = f"({win}-{TIE}-{t0})"          # no MAX(0, .) here: t0 is an array inside SUMPRODUCT (MAX would aggregate it); the >=0 test zeroes the casts-less case
    return (f"(({win}-{TIE}-{t0}>=0)*(INT({m}/{per})*{minf(dur, per)}"
            f"+{minf(dur, f'MOD({m},{per})+{TIE}')}))/{win}")


def mask(c, h):
    return f"({K('unlock')}<={c('lvlc')})*({K('maxlvl')}>{c('lvlc')})"


def ct_gate(c):
    g = K("g_ct")
    return (f'(({g}="-")+({g}="BT")*{c("isBT")}+({g}="notBT")*(1-{c("isBT")})+({g}="CB")*{c("chboss")}'
            f'+({g}="PvP")*{c("pvp")}+({g}="notPvP")*(1-{c("pvp")}))')


def br_gate(branch):
    g = K("g_br")
    return f'(({g}="-")+({g}="{"boss" if branch == "b" else "nonboss"}"))'


def hp_gate(f):
    g = K("g_hp")
    return f'(({g}="-")+({g}="lt50")*({f})+({g}="ge50")*(1-({f})))'


def who_mask(group):
    w = K("who")
    return f'(({w}="{group}")+({w}="b"))'


def level_multiplier_expr(lvl):
    tbl = ",".join(str(v) for v in LEVEL_MULT)
    return f"(CHOOSE(MIN(10,MAX(1,{lvl})),{tbl})/100)"


def _pl_entries(h):
    return h.get("pst") or []


def _pl_terms(h, f):
    """Sum over the player's stunning skills of f(entry, vars) (each entry: id, typ 'cast'|'periodic', cd, dur, p, on, t0, tick, win - expressions)."""
    out = []
    for e in _pl_entries(h):
        v = {k: str(e.get(k, d)) for k, d in (("cd", "1000000000"), ("dur", "0"), ("p", "0"), ("on", "0"), ("t0", "0"), ("tick", "1"), ("win", "0"))}
        v["per"] = e.get("typ", "cast") == "periodic"
        out.append(f(v))
    return out


def _pl_frac(c, h):
    """Expected share of the fight the enemy is stunned/frozen by the PLAYER's own stunning skills (fixed schedule: cast on cooldown from t0)."""
    def f(v):
        cov_cast = f'{v["p"]}*MIN({v["dur"]},{v["cd"]})/{v["cd"]}'
        cov_per = f'{v["p"]}*{v["dur"]}/{v["tick"]}*MIN({v["win"]},{v["cd"]})/{v["cd"]}'
        n = f'MAX(0,INT(({c("Teff")}-({v["t0"]})-0.000000001)/{v["cd"]})+1)'
        fix_cast = f'{v["p"]}*{v["dur"]}*{n}/{c("Teff")}'
        fix_per = f'{v["p"]}*{v["dur"]}/{v["tick"]}*{v["win"]}*{n}/{c("Teff")}'
        return f'IF({v["on"]},IF({c("steady")}=1,{cov_per if v["per"] else cov_cast},{fix_per if v["per"] else fix_cast}),0)'
    terms = _pl_terms(h, f)
    return "0" if not terms else "MIN(1," + "+".join(terms) + ")"


def _pl_ext(c, h, t_expr):
    """Seconds the boss phase of Chapter Breakthrough is lengthened by the player's own stuns: every cast (t0 + j*cd) that lands while the boss is
    present (tb0 <= t < the extended fight end) adds its stun length x chance; a periodic summon adds p x dur/tick x its window."""
    def f(v):
        jmin = f'MAX(0,ROUNDUP(MAX(0,({c("tb0")})-({v["t0"]}))/{v["cd"]}-0.000000000001,0))'
        jmax = f'MAX(0,ROUNDUP(MAX(0,({t_expr})-({v["t0"]}))/{v["cd"]}-0.000000000001,0))'
        cnt = f'MAX(0,{jmax}-{jmin})'
        per_cast = f'{v["p"]}*{v["dur"]}/{v["tick"]}*{v["win"]}' if v["per"] else f'{v["p"]}*{v["dur"]}'
        return f'IF({v["on"]},{per_cast}*{cnt},0)'
    terms = _pl_terms(h, f)
    return "0" if not terms else "+".join(terms)


def cells(h, ncand=NUM_CANDIDATES, fixed_s=None, fixed_tend=None, fixed_e=None):
    """ncand = number of summon-time candidates evaluated; fixed_s (an expression) pins candidate 0's summon time (used by the
    Sensitivity blocks, which take the summon time the main sheet chose instead of searching again)."""
    out = []

    def add(name, label, fn):
        out.append((name, label, fn))

    # ---- shared (non-candidate) cells -------------------------------------------------------------
    add("lvlc", "Level of the chosen companion (0 = not unlocked)", lambda c: h["lvl"])
    add("kr0", "Kit table: first row index of the chosen companion", lambda c: f'IFERROR(MATCH({h["choice"]},{FULL("comp")},0),1)')
    add("kn", "Kit table: number of rows of the chosen companion", lambda c: f'MAX(1,COUNTIF({FULL("comp")},{h["choice"]}))')
    add("sel", "Companion summoned (1 = chosen AND unlocked AND in the catalog)",
        lambda c: f'IF(AND({h["choice"]}<>"None",COUNTIF({FULL("comp")},{h["choice"]})>0,{c("lvlc")}>=1),1,0)')
    add("D", "Companion duration D (s) = 30 x (1 + Summoning Time Increase %)",
        lambda c: f'{COMPANION_BASE_DURATION}*(1+{h["inc"]}/100)')
    add("pvp", "PvP fight (1/0)", lambda c: f'IF({h["mt"]}="pvp",1,0)')
    add("steady", "Steady-state content (Chapter Hunt) (1/0)", lambda c: f'IF(AND({c("pvp")}=0,{h["T"]}=0),1,0)')
    add("Teff", "Fight length T (s; PvP = PvP fight length)", lambda c: f'IF({c("pvp")}=1,{h["pvp_len"]},{h["T"]})')
    add("period", "Averaging period (s) (steady state: max(D, 90); fixed: fight length)",
        lambda c: f'IF({c("steady")}=1,MAX({c("D")},{COMPANION_SUMMON_COOLDOWN}),{c("Teff")})')
    add("lvlmult", "Companion level damage multiplier", lambda c: level_multiplier_expr(c("lvlc")))
    add("isBT", "Chapter Breakthrough (1/0)", lambda c: f'IF({h["content"]}="Breakthrough",1,0)')
    add("chboss", "Chapter Boss content (1/0)", lambda c: f'IF({h["content"]}="Chapter Boss",1,0)')
    add("Tbp", "Boss-phase length of the base fight (s)", lambda c: f'MAX(0.000001,IF({c("tb0")}>0,{c("Teff")}-{c("tb0")},1))')
    add("tb0", "Boss appears at (s)", lambda c: f'IF({h["content"]}="Breakthrough",20,IF({h["content"]}="Hero Dungeon",30,0))')
    add("cap", "Max enemies in range (at least 1: Excel returns #NUM! for 0^0, which a 100% proc chance over 0 targets would hit in boss/PvP content where this input is blank)",
        lambda c: f'MAX(1,{h["cap"]})')
    add("tbasic", "Basic attack targets (capped)",
        lambda c: f'MIN(SUMPRODUCT({mask(c, h)}*({K("kind")}="basic")*{K("tgt")}),{c("cap")})')
    add("skratio", "Skill vs Basic damage bucket ratio", lambda c: f'(1+{h["sd"]}/100)/(1+{h["bad"]}/100)')
    add("pb", "Player Boss-only DPS (excl. companion)", lambda c: h["player_boss"])
    add("pn", "Player Normal-only DPS (excl. companion)", lambda c: h["player_norm"])
    add("shB", "Player boss DPS share from Basic Attack", lambda c: f'IF({c("pb")}>0,{h["player_basic_boss"]}/{c("pb")},0)')
    add("shN", "Player normal DPS share from Basic Attack", lambda c: f'IF({c("pn")}>0,{h["player_basic_norm"]}/{c("pn")},0)')
    add("unitB", "Expected damage per 1% coefficient (basic-type hit, fight-average state)", lambda c: h["unit"])
    for j in range(1, NUM_PROC_SLOTS + 1):
        add(f"prow{j}", f"Proc slot {j}: kit row (0 = none)",
            lambda c, j=j: f'IFERROR(MATCH({h["choice"]}&"|proc|{j}",{FULL("pkey")},0),0)')
    add("rrow", "Ramp slot 1: kit row (0 = none)", lambda c: f'IFERROR(MATCH({h["choice"]}&"|ramp|1",{FULL("pkey")},0),0)')

    # ---- stun / freeze exposure (Status Effect Damage) --------------------------------------------
    MSK0 = lambda c: mask(c, h)

    def _stun_slot(j):
        """scalar cells of the j-th stunning hit row of the chosen companion (kit key comp|stun|j): existence gates (level, content, boss / normal
        branch), stun chance, stun length (Chapter Breakthrough's own length where the kit has one), cast period, first cast, casts skipped"""
        def F(col, c, default="0"):
            return f'IF({c(f"srow{j}")}=0,{default},INDEX({FULL(col)},{c(f"srow{j}")}))'

        def ok(c, br):
            g, gb = F("g_ct", c, '"-"'), F("g_br", c, '"-"')
            ct = (f'IF(OR({g}="-",AND({g}="BT",{c("isBT")}=1),AND({g}="notBT",{c("isBT")}=0),AND({g}="CB",{c("chboss")}=1),'
                  f'AND({g}="PvP",{c("pvp")}=1),AND({g}="notPvP",{c("pvp")}=0)),1,0)')
            brk = f'IF(OR({gb}="-",{gb}="{"boss" if br == "b" else "nonboss"}"),1,0)'
            return (f'IF({c(f"srow{j}")}=0,0,IF(AND({F("unlock", c)}<={c("lvlc")},{F("maxlvl", c, "99")}>{c("lvlc")}),1,0))*{ct}*{brk}')
        add(f"srow{j}", f"Stun slot {j}: kit row of the companion's {j}-th stunning hit row (0 = none)",
            lambda c: f'IFERROR(MATCH({h["choice"]}&"|stun|{j}",{FULL("skey")},0),0)')
        add(f"sgb{j}", f"Stun slot {j}: exists (level, content) - boss branch", lambda c: ok(c, "b"))
        add(f"sgn{j}", f"Stun slot {j}: exists (level, content) - normal branch", lambda c: ok(c, "n"))
        add(f"sp{j}", f"Stun slot {j}: stun chance per cast", lambda c: F("stun_p", c))
        add(f"sdur{j}", f"Stun slot {j}: stun length (s; Chapter Breakthrough's own where the kit has one)",
            lambda c: f'IF(AND({c("isBT")}=1,{F("stun_bt", c)}>0),{F("stun_bt", c)},{F("stun", c)})')
        add(f"sper{j}", f"Stun slot {j}: period between casts (s)", lambda c: F("per", c, "1000000000"))
        add(f"st0{j}", f"Stun slot {j}: first cast after the summon (s)", lambda c: F("t0", c))
        add(f"sskip{j}", f"Stun slot {j}: casts that do not stun yet", lambda c: F("stun_skip", c))

    for j in range(1, NUM_STUN_SLOTS + 1):
        _stun_slot(j)

    _pl_on = "+".join(f'IF({e.get("on", 0)},1,0)' for e in _pl_entries(h)) or "0"
    add("hasstun", "The chosen companion or the player's own skills stun/freeze something (1/0)",
        lambda c: f'IF(OR(SUMPRODUCT({MSK0(c)}*{ct_gate(c)}*({K("kind")}="hit")*({K("stun")}>0))>0,{_pl_on}>0),1,0)')
    add("plfrac", "Expected share of the fight the enemy is stunned/frozen by the player's own skills", lambda c: _pl_frac(c, h))
    def _stunfrac(c, brk):
        W0 = c("W_0")
        body = "+".join(f'{c(f"sg{brk}{j}")}*{c(f"sp{j}")}*{c(f"sdur{j}")}*MAX(0,{cnt_expr(W0, c(f"sper{j}"), c(f"st0{j}"))}-{c(f"sskip{j}")})'
                        for j in range(1, NUM_STUN_SLOTS + 1))
        comp = f'IF({c("sel")}=0,0,MIN(1,({body})/{c("period")}))'
        return f'MIN(1,{comp}+{c("plfrac")})' if _pl_entries(h) else comp
    add("stunfracB", "Expected share of the fight the enemy is stunned/frozen by the companion (boss; casts inside the summon window)",
        lambda c: _stunfrac(c, "b"))
    add("stunfracN", "Expected share of the fight the enemy is stunned/frozen by the companion (normal monsters)",
        lambda c: _stunfrac(c, "n"))

    # ---- candidate summon times -------------------------------------------------------------------
    MSKS = lambda c: mask(c, h)

    def Efn(c, s_expr, t_expr):
        """Chapter Breakthrough only: seconds the boss phase is lengthened because the boss stands still while stunned/frozen.
        Every stunning cast of the companion that starts while the boss is present (tb0 <= t < the extended fight end) adds its
        stun duration (x chance); the stun duration of Chapter Breakthrough ('stun_bt') replaces the normal one there."""
        w_ = f'MIN({c("D")},{t_expr}-({s_expr}))'
        terms = []
        for j in range(1, NUM_STUN_SLOTS + 1):
            per, t0k, skip = c(f"sper{j}"), c(f"st0{j}"), c(f"sskip{j}")
            n_casts = cnt_expr(f'({w_})', per, t0k)         # casts t0 + n*per < W; they all start before the extended fight end (W <= t_expr - s)
            # first cast that lands while the boss stands there (t >= tb0); stun_skip >= 0 also floors the index at 0
            jmin = f'MAX(ROUNDUP(({c("tb0")}-({s_expr})-{t0k})/{per},0),{skip})'
            terms.append(f'{c(f"sgb{j}")}*{c(f"sp{j}")}*{c(f"sdur{j}")}*MAX(0,{n_casts}-{jmin})')
        comp = "+".join(terms)
        if _pl_entries(h):      # the player's own stuns lengthen the boss phase with or without a companion
            return f'IF(OR({c("isBT")}=0,{c("steady")}=1),0,IF({c("sel")}=0,0,{comp})+{_pl_ext(c, h, t_expr)})'
        return f'IF(OR({c("isBT")}=0,{c("steady")}=1,{c("sel")}=0),0,{comp})'

    if fixed_s is not None:
        add("s_0", "Summon time (taken from the main Companion sheet)", lambda c: fixed_s)
        add("E_0", "Boss-phase extension from stuns/freezes (s) (taken from the main Companion sheet)", lambda c: fixed_e)
        add("Tend_0", "Extended fight length (s) (taken from the main Companion sheet)", lambda c: fixed_tend)
    else:
        # self-consistent fight length: stuns lengthen the fight, a longer fight moves the summon (s = T - D) earlier, which can
        # allow another stunning cast - three unrolled iterations
        add("s_a", "Summon time guess 0", lambda c: f'IF({c("steady")}=1,0,MAX({COMPANION_EARLIEST_SUMMON},{c("Teff")}-{c("D")}))')
        add("E_a", "Fight extension, iteration 1 (s)", lambda c: Efn(c, c("s_a"), c("Teff")))
        add("s_b", "Summon time, iteration 1",
            lambda c: f'IF({c("steady")}=1,0,MAX({COMPANION_EARLIEST_SUMMON},{c("Teff")}+{c("E_a")}-{c("D")}))')
        add("E_b", "Fight extension, iteration 2 (s)", lambda c: Efn(c, c("s_b"), f'({c("Teff")}+{c("E_a")})'))
        add("s_c", "Summon time, iteration 2",
            lambda c: f'IF({c("steady")}=1,0,MAX({COMPANION_EARLIEST_SUMMON},{c("Teff")}+{c("E_b")}-{c("D")}))')
        add("E_0", "Boss-phase extension from stuns/freezes (s)", lambda c: Efn(c, c("s_c"), f'({c("Teff")}+{c("E_b")})'))
        add("Tend_0", "Extended fight length (s)", lambda c: f'{c("Teff")}+{c("E_0")}')
        add("s_0", "Candidate 0: summon time s (full coverage of the extended fight)",
            lambda c: f'IF({c("steady")}=1,0,MAX({COMPANION_EARLIEST_SUMMON},{c("Tend_0")}-{c("D")}))')
    # Horn Flute (Final Damage while a companion is out): share of the fight covered by the full-coverage summon (candidate 0), used by the
    # Artifacts sheet for the character's own portion; and the companion's own snapshot ratio (flute fully active at the summon)
    def _horn_share(c):
        """share of the player's boss DAMAGE (not of the time) dealt while the companion is out: the damage rate is not flat - Hexagon Necklace stacks, Charm of the
        Undead and the KO / stun windows make the late fight hit harder - so a 30 s window at the end of a 70 s fight holds well over 43% of the damage"""
        idx, dw = h["st_idx"], h["st_dw"]
        s0, w0 = c("s_0"), c("W_0")
        ov = maxel("0", minel(f"{idx}+1", f"{s0}+{w0}") + "-" + maxel(idx, s0))
        time_share = f'MIN(1,MAX(0,MIN({c("D")},{c("Tend_0")}-{s0}))/{c("period")})'
        return (f'IF({c("steady")}=1,MIN(1,{c("D")}/{c("period")}),'
                f'IF(SUM({dw})>0,SUMPRODUCT({dw}*{ov})/SUM({dw}),{time_share}))')
    add("horn_uptime", "Horn Flute share: the part of the player's boss damage dealt while the summoned companion is out (candidate 0 timing; falls back to the time share where no fixed fight length exists)",
        _horn_share)
    add("rhoH", "Snapshot ratio: Horn Flute (fully active at the summon vs its fight average)",
        lambda c: f'(1+{h["horn_full"]}/100)/(1+{h["horn_avg"]}/100)')

    if ncand > 1:
        # later candidates: the next two Hexagon Necklace stack times (20 / 40 / 60 s) after s0 - a later summon trades window for stacks
        add("s_1", "Candidate 1: first Hexagon Necklace stack time after s0",
            lambda c: (f'IF(AND({c("steady")}=0,{c("s_0")}<60),IF({c("s_0")}<20,20,IF({c("s_0")}<40,40,60)),{c("s_0")})'))
        add("s_2", "Candidate 2: earliest summon (the companion is out for as much of the early fight as possible; it need not last to the fight end)",
            lambda c: f'IF({c("steady")}=1,0,{COMPANION_EARLIEST_SUMMON})')
        for kk in (1, 2):
            add(f"Ea_{kk}", f"Candidate {kk}: fight extension, iteration 1 (s)", lambda c, kk=kk: Efn(c, c(f"s_{kk}"), c("Teff")))
            add(f"E_{kk}", f"Candidate {kk}: boss-phase extension (s)",
                lambda c, kk=kk: Efn(c, c(f"s_{kk}"), f'({c("Teff")}+{c(f"Ea_{kk}")})'))
            add(f"Tend_{kk}", f"Candidate {kk}: extended fight length (s)", lambda c, kk=kk: f'{c("Teff")}+{c(f"E_{kk}")}')

    for k in range(ncand):
        _candidate_cells(add, k, h)

    # ---- pick the best candidate -------------------------------------------------------------------
    scores = lambda c: ",".join(c(f"score_{k}") for k in range(ncand))
    add("maxscore", "Best candidate score", lambda c: f'MAX({scores(c)})')
    if ncand > 1:
        add("best", "Best candidate index (1-based)",
            lambda c: "IF(" + c("score_0") + "=" + c("maxscore") + ",1,IF(" + c("score_1") + "=" + c("maxscore") + ",2,3))")
    else:
        add("best", "Best candidate index (1-based)", lambda c: "1")
    for nm, lab, base in (("best_s", "Chosen summon time s* (s)", "s"), ("best_W", "Chosen active window W* (s)", "W"),
                          ("best_dmg_b", "Chosen companion damage, boss branch", "dmgb"),
                          ("best_dmg_n", "Chosen companion damage, normal branch", "dmgn"),
                          ("best_upl_b", "Chosen player uplift damage, boss branch", "uplb"),
                          ("best_upl_n", "Chosen player uplift damage, normal branch", "upln"),
                          ("best_ext", "Chosen damage in the fight extension (boss)", "ext"),
                          ("best_E", "Chosen boss-phase extension (s)", "E"),
                          ("best_Tend", "Chosen extended fight length (s)", "Tend")):
        add(nm, lab, lambda c, base=base: f'CHOOSE({c("best")},{",".join(c(f"{base}_{k}") for k in range(ncand))})')
    add("comp_boss_dps", "Companion DPS (damage + player uplift + the boss-phase extension), boss-only, averaged over the fight",
        lambda c: (f'IF(OR({c("sel")}=1,{c("best_ext")}>0),IF({c("tb0")}>0,({c("best_dmg_b")}+{c("best_upl_b")}+{c("best_ext")})/{c("Tbp")},'
                   f'({c("best_dmg_b")}+{c("best_upl_b")}+IF({h["w"]}<1,{c("best_ext")}/(1-{h["w"]}),0))/{c("period")}),0)'))
    add("comp_norm_dps", "Companion DPS (damage + player uplift), normal-only, averaged over the fight",
        lambda c: (f'IF({c("sel")}=1,IF({c("tb0")}>0,({c("best_dmg_n")}+{c("best_upl_n")})/{c("tb0")},'
                   f'({c("best_dmg_n")}+{c("best_upl_n")})/{c("period")}),0)'))
    add("comp_blend_dps", "Companion DPS, time-weighted boss/normal blend (what Total DPS gains)",
        lambda c: f'(1-{h["w"]})*{c("comp_boss_dps")}+{h["w"]}*{c("comp_norm_dps")}')
    return out


STAT_CODES = ["atk", "fd", "crit_rate", "crit_dmg", "skill_dmg", "bad", "norm_dmg", "boss_dmg", "max_dmg", "def_pen", "as"]
MONSTER_CODES = ["dmg_taken", "dmg_taken_b", "dmg_taken_n", "mon_def", "mon_def_b", "mon_def_n"]


def _candidate_cells(add, k, h):
    n = lambda base: f"{base}_{k}"
    kit = K
    _status_mult_cells(add, k, h, n)

    W = lambda c: c(n("W"))
    PER, T0 = kit("per"), kit("t0")
    CST = lambda c: cnt_expr(W(c), PER, T0)             # casts of each kit row inside the window (cast n at t0 + n*per)

    DUR, TICK = kit("dur"), kit("tick")

    def UP(c):
        return uptime_expr(W(c), PER, T0, DUR, minel)

    def TKS(c):
        """Whole ticks of every cast in the window (overlapping summons allowed).  The i-th cast from the end (i = 0 is the last) has
        x + i*per seconds left, x = MOD(W - t0 - tie, per) + tie (0 < x <= per): casts with i >= DOT_CAST_TERMS always last their full duration
        (DOT_CAST_TERMS = max over the dot rows of ceil(dur / per)), the last DOT_CAST_TERMS are evaluated one by one."""
        m = f"({W(c)}-{TIE}-{T0})"                         # (T0 is an array: no MAX(0, .) - see uptime_expr)
        nm1 = f"INT({m}/{PER})"                            # = casts - 1 (-1 when the window ends before the first cast)
        x = f"(MOD({m},{PER})+{TIE})"
        parts = [maxel("0", f"{nm1}+1-{DOT_CAST_TERMS}") + "*" + kit("tkf")]
        for i in range(DOT_CAST_TERMS):
            parts.append(f"({nm1}>={i})*INT(" + minel(DUR, f"{x}+{i}*{PER}") + "/" + TICK + ")")
        return "(" + "+".join(parts) + ")"

    def GATE(c, branch):
        f = c(n("f50b")) if branch == "b" else "0.5"
        return f"{ct_gate(c)}*{br_gate(branch)}*{hp_gate(f)}"

    GS = lambda c: f'{ct_gate(c)}*{hp_gate(c(n("f50s")))}'          # stat-like rows: branch-independent sums, blended HP share
    MSK = lambda c: mask(c, h)
    tgt_n = lambda c: minel(kit("tgt"), c("cap"))

    # Chapter Breakthrough / Hero Dungeon: the normal-monster phase comes first (the boss appears at tb0).  A window's damage is split by the
    # PHASE each cast / tick lands in: cooldown casts and DoT casts per row (cast times s + j*cd), everything else by time share.
    def PH(c, br):
        # csn <= cst always (Wn <= W), so no MIN is needed; ph = 1 where the content has phases, else the factor is 1
        wn, ph = c(n("Wn")), c(n("phase"))
        cst = CST(c)
        share = f'({ph}*({wn}>0)*{cnt_expr(wn, PER, T0)}/({cst}+({cst}=0)))'
        return f'(1-{share})' if br == "b" else f'(1-{ph}+{share})'

    def DOTPH(c, br):
        """whole ticks that land in the normal phase (every cast before tb0 ticks its full length) / the rest of the window's ticks"""
        wn, ph = c(n("Wn")), c(n("phase"))
        return f'({ph}*({wn}>0)*{cnt_expr(wn, PER, T0)}*{kit("tkf")})'

    # ---- window, snapshot ---------------------------------------------------------------------------
    add(n("phase"), f"[{k}] Content has a normal-monster phase before the boss (1/0)", lambda c: f'IF({c("tb0")}>0,1,0)')
    add(n("Wn"), f"[{k}] Seconds of the window in the normal-monster phase (content with a boss that appears later)",
        lambda c: f'IF(AND({c("tb0")}>0,{c(n("W"))}>0),MAX(0,MIN({c(n("s"))}+{c(n("W"))},{c("tb0")})-{c(n("s"))}),0)')
    add(n("tfb"), f"[{k}] Time share of the window against the boss (1 where the content has no phases)",
        lambda c: f'IF({c("tb0")}>0,IF({c(n("W"))}>0,1-{c(n("Wn"))}/{c(n("W"))},0),1)')
    add(n("tfn"), f"[{k}] Time share of the window against normal monsters (1 where the content has no phases)",
        lambda c: f'IF({c("tb0")}>0,IF({c(n("W"))}>0,{c(n("Wn"))}/{c(n("W"))},0),1)')
    add(n("W"), f"[{k}] Active window W (s)",
        lambda c: f'IF({c("sel")}=0,0,IF({c("steady")}=1,{c("D")},MAX(0,MIN({c("D")},{c(n("Tend"))}-{c(n("s"))}))))')
    add(n("stacks"), f"[{k}] Hexagon Necklace stacks at summon",
        lambda c: f'IF({c("steady")}=1,3,MIN(3,INT({c(n("s"))}/20)))')
    add(n("charm"), f"[{k}] Charm of the Undead on at summon (0-1)",
        lambda c: f'IF({c("steady")}=1,0.5,IF(AND({c(n("s"))}>=10,MOD({c(n("s"))},10)<5),1,0))')
    add(n("f50b"), f"[{k}] Share of the window the boss is below 50% HP (damage assumed uniform until the buzzer)",
        lambda c: (f'IF(OR({W(c)}<=0,{c("steady")}=1),0.5,MAX(0,MIN(1,({c(n("s"))}+{W(c)}'
                   f'-MAX({c(n("s"))},{c("tb0")}+({c(n("Tend"))}-{c("tb0")})/2))/{W(c)})))'))
    add(n("f50s"), f"[{k}] HP<50% share used by stat rows (boss/normal blend)",
        lambda c: f'(1-{h["w"]})*{c(n("f50b"))}+{h["w"]}*0.5')

    # ---- action economy ------------------------------------------------------------------------------
    add(n("ACT"), f"[{k}] Cooldown skill casts in the window (each uses an action slot)",
        lambda c: f'IF({W(c)}>0,SUMPRODUCT({MSK(c)}*{ct_gate(c)}*({kit("action")}=1)*{CST(c)}),0)')
    add(n("asc"), f"[{k}] Companion attack speed bonus (companion + both; stacking rows excluded)",
        lambda c: _stat_sum(c, h, n, MSK(c), "as", "c", UP(c), GS(c), stacks=False))
    add(n("aps"), f"[{k}] Companion actions per second (snapshot Attack Speed + the companion's own Attack Speed effects)",
        lambda c: f'1+MIN(150,150*(1-(1-({h["aps"]}-1)*100/150)*(1-{c(n("asc"))}/150)))/100')
    add(n("ba"), f"[{k}] Basic attacks in the window",
        lambda c: f'IF({W(c)}>0,MAX(0,{W(c)}*{c(n("aps"))}-{c(n("ACT"))}-1),0)')
    add(n("atkc"), f"[{k}] Attacks by cooldown-skill hits in the window (proc triggers)",
        lambda c: f'IF({W(c)}>0,SUMPRODUCT({MSK(c)}*{ct_gate(c)}*({kit("kind")}="hit")*{CST(c)}*{kit("atk")}),0)')

    # ---- direct damage sums (coefficient-% x lines x targets) ----------------------------------------
    # Content with a normal-monster phase first: the basic attacks of each phase = that phase's seconds x actions/s minus the casts made in it
    add(n("ACTn"), f"[{k}] Cooldown skill casts in the normal-monster phase of the window",
        lambda c: (f'IF(AND({W(c)}>0,{c(n("Wn"))}>0),SUMPRODUCT({MSK(c)}*{ct_gate(c)}*({kit("action")}=1)'
                   f'*{cnt_expr(c(n("Wn")), PER, T0)}),0)'))
    add(n("baB"), f"[{k}] Basic attacks against the boss (phase-aware)",
        lambda c: (f'IF({W(c)}>0,IF({c(n("phase"))}=1,MAX(0,({W(c)}-{c(n("Wn"))})*{c(n("aps"))}-({c(n("ACT"))}-{c(n("ACTn"))})-1),{c(n("ba"))}),0)'))
    add(n("baN"), f"[{k}] Basic attacks against normal monsters (phase-aware)",
        lambda c: (f'IF({W(c)}>0,IF({c(n("phase"))}=1,MAX(0,{c(n("Wn"))}*{c(n("aps"))}-{c(n("ACTn"))}),{c(n("ba"))}),0)'))
    add(n("BAB"), f"[{k}] Basic attack coefficient-hits (boss)",
        lambda c: f'{c(n("baB"))}*SUMPRODUCT({MSK(c)}*({kit("kind")}="basic")*{kit("lines")}*{kit("pct")})')
    add(n("BAN"), f"[{k}] Basic attack coefficient-hits (normal)",
        lambda c: f'{c(n("baN"))}*SUMPRODUCT({MSK(c)}*({kit("kind")}="basic")*{kit("lines")}*{kit("pct")})*{c("tbasic")}')
    for br in ("b", "n"):
        lab = "boss" if br == "b" else "normal"
        tg = lambda c, br=br: kit("tgt_boss") if br == "b" else tgt_n(c)
        add(n(f"HIT{br}"), f"[{k}] Cooldown-hit coefficient-hits ({lab})",
            lambda c, br=br, tg=tg: (f'IF({W(c)}>0,SUMPRODUCT({MSK(c)}*{GATE(c, br)}*({kit("kind")}="hit")*{CST(c)}*{PH(c, br)}'
                                     f'*{kit("lines")}*{kit("pct")}*{tg(c)}),0)'))
        add(n(f"DOT{br}"), f"[{k}] Damage-over-time coefficient-hits ({lab})",
            lambda c, br=br, tg=tg: (f'IF({W(c)}>0,SUMPRODUCT({MSK(c)}*{GATE(c, br)}*({kit("kind")}="dot")*({TKS(c)}'
                                     + (f'-{DOTPH(c, "b")}' if br == "b" else f'*(1-{c(n("phase"))})+{DOTPH(c, "n")}') + ')'
                                     f'*{kit("lines")}*{kit("pct")}*{tg(c)}),0)'))
        add(n(f"ECH{br}"), f"[{k}] Echo (extra spirit arrows) coefficient-hits ({lab})",
            lambda c, br=br: (f'IF({W(c)}>0,SUMPRODUCT({MSK(c)}*{GATE(c, br)}*({kit("kind")}="echo")'
                              f'*(({kit("echo_all")}=1)*({c(n("ACT"))}+1)+({kit("echo_all")}=0)*{CST(c)})'
                              f'*{kit("lines")}*{kit("pct")}),0)'))
        # stun/freeze applications (Shadower Lv3): casts of stunning hit rows x enemies hit, times the stun-trigger hit
        add(n(f"STN{br}"), f"[{k}] Stun-trigger damage coefficient-hits ({lab})",
            lambda c, br=br, tg=tg: (f'IF({W(c)}>0,SUMPRODUCT({MSK(c)}*({kit("kind")}="stunhit")*{kit("lines")}*{kit("pct")})'
                                     f'*SUMPRODUCT({MSK(c)}*{GATE(c, br)}*({kit("kind")}="hit")*({kit("stun")}>0)'
                                     f'*{maxel("0", CST(c) + "-" + kit("stun_skip"))}*{kit("stun_p")}*{tg(c)}),0)'))

    # ---- proc slots ------------------------------------------------------------------------------------
    for j in range(1, NUM_PROC_SLOTS + 1):
        _proc_slot(add, k, j, h, n, W, CST)

    # ---- stat sums (companion-effective c/b and player-effective p/b) ------------------------------------
    for grp in ("c", "p"):
        for code in STAT_CODES:
            if code == "as" and grp == "c":
                continue          # n("asc") above, computed without the stacking rows (avoids a circular reference)
            add(n(f"{code}_{grp}"), f"[{k}] Stat sum {code} ({'companion' if grp == 'c' else 'player'})",
                lambda c, code=code, grp=grp: _stat_sum(c, h, n, MSK(c), code, grp, UP(c), GS(c), stacks=True, ln=(code == "fd")))
        add(n(f"fdpt_{grp}_b"), f"[{k}] Final Damage per nearby target ({grp}, boss: 1 target)",
            lambda c, grp=grp: _stat_sum(c, h, n, MSK(c), "fd_pt", grp, UP(c), GS(c), stacks=False, per_tgt_n="1"))
        add(n(f"fdpt_{grp}_n"), f"[{k}] Final Damage per nearby target ({grp}, normal)",
            lambda c, grp=grp: _stat_sum(c, h, n, MSK(c), "fd_pt", grp, UP(c), GS(c), stacks=False, per_tgt_n=c("cap")))
    for code in MONSTER_CODES:
        add(n(f"m_{code}"), f"[{k}] Monster-side effect {code}",
            lambda c, code=code: _stat_sum(c, h, n, MSK(c), code, "m", UP(c), GS(c), stacks=False))
    add(n("rampexp"), f"[{k}] Average compounding Final Damage multiplier of an exponential ramp (companion)",
        lambda c: _ramp_exp(c, n, W))

    # ---- snapshot ratios ------------------------------------------------------------------------------------
    add(n("rhoA"), f"[{k}] Snapshot ratio: Attack% bucket (buffs up + companion Attack effects)",
        lambda c: f'{h["avgbuff_snap"]("(" + h["charm_val"] + ")*" + c(n("charm")), c(n("atk_c")))}/{h["avgbuff"]}')
    add(n("rhoD"), f"[{k}] Snapshot ratio: Hexagon Necklace Damage%",
        lambda c: f'(1+({h["agg_damage_avg"]}-{h["hex_avg"]}+{h["hex_snap"](c(n("stacks")))})/100)/(1+{h["agg_damage_avg"]}/100)')
    add(n("rhoFb"), f"[{k}] Snapshot ratio: Chalice (boss branch)",
        lambda c: f'(1+({h["agg_fd_boss_only"]}-{h["chalice_avg_boss"]}+{h["chalice_full"]})/100)/(1+{h["agg_fd_boss_only"]}/100)')
    add(n("rhoFn"), f"[{k}] Snapshot ratio: Chalice (normal branch)",
        lambda c: f'(1+({h["agg_fd_norm_only"]}-{h["chalice_avg_norm"]}+{h["chalice_full"]})/100)/(1+{h["agg_fd_norm_only"]}/100)')
    for grp in ("c", "p"):
        _ratio_cells(add, k, h, n, grp)

    # ---- companion damage and player uplift -------------------------------------------------------------------
    for br in ("b", "n"):
        _damage_cells(add, k, h, n, br, W)
    for br in ("b", "n"):
        pl, sh = ("pb", "shB") if br == "b" else ("pn", "shN")
        lab = "boss" if br == "b" else "normal"
        add(n(f"ratioP{br}"), f"[{k}] Player damage ratio while the companion is out ({lab})",
            lambda c, br=br, sh=sh: (f'{c(n(f"coreP{br}"))}*({c(sh)}*{c(n("bdRp"))}*{c(n("asRatioP"))}'
                                     f'+(1-{c(sh)})*{c(n("sdRp"))})'))
        add(n(f"upl{br}"), f"[{k}] Player uplift damage over the window ({lab})",
            lambda c, br=br, pl=pl: f'{c(pl)}*{W(c)}*({c(n(f"ratioP{br}"))}-1)*{c(n("tfb") if br == "b" else n("tfn"))}')
    add(n("rhoDe"), f"[{k}] Hexagon Necklace state during the fight extension vs the fight average (stacks at the end of the base fight)",
        lambda c: _hex_ext_ratio(c, h, n))
    add(n("ext"), f"[{k}] Player's own damage in the fight extension (boss; basic-attack-type rows only - no extra skill casts are assumed to fit - at the Hexagon stacks of that moment; the companion's and the uplift's share is already inside the window)",
        lambda c: f'IF(OR({W(c)}>0,{c(n("E"))}>0),{c(n("E"))}*{h["player_uniform_boss"]}*{c(n("rhoDe"))},0)')
    # Where the content has phases the phase-split damages already add up (wb = wn = 1); elsewhere the content's own boss/normal weight.
    # Boss-only / normal-only DPS scale of a content with phases: boss damage / boss-phase length, normal damage / normal-phase length, then weighted by
    # the content's emphasis w (the user's rule: a weight is a weight on RELATIVE gains, so +18% boss time is worth (1-w) x 18%).
    add(n("score"), f"[{k}] Score (weighted boss-only / normal-only DPS incl. uplift and the fight extension)",
        lambda c: (f'IF({c("tb0")}>0,(1-{h["w"]})*({c(n("dmgb"))}+{c(n("uplb"))}+{c(n("ext"))})/{c("Tbp")}+{h["w"]}*({c(n("dmgn"))}+{c(n("upln"))})/{c("tb0")},'
                   f'(1-{h["w"]})*({c(n("dmgb"))}+{c(n("uplb"))})+{h["w"]}*({c(n("dmgn"))}+{c(n("upln"))})+{c(n("ext"))})'))


def _avg_array(c, n, UPexpr, stacks):
    """Average effective value of every stat-like row: val x (timed uptime | average stacks | ramp average)."""
    W = c(n("W"))
    kind = K("kind")
    parts = [f'({kind}="stat")*{UPexpr}']
    if stacks:
        sdur = f'({K("sdur")}+({K("sdur")}=0))'
        atkr = (f'(({K("trig")}="skill")*{c(n("ACT"))}/{W}+({K("trig")}="basic")*{c(n("ba"))}/{W}'
                f'+({K("trig")}="any")*({c(n("ba"))}+{c(n("atkc"))})/{W})')
        x = f'({K("chance")}*{atkr})'
        rate = f'({x}/(1+{K("icd")}*{x}))'
        stk = minel(K("smax"), f'{rate}*{K("sdur")}')
        ramp = f'(({W}>={sdur})*(1-{sdur}/(2*{W}))+({W}<{sdur})*({W}/(2*{sdur})))'
        parts.append(f'({kind}="stack")*{stk}*{ramp}')
    parts.append(f'({kind}="ramp")*({K("ramp_mode")}="lin")*{W}/2')
    return "(" + "+".join(parts) + f")*{K('val')}"


def _stat_sum(c, h, n, msk, code, grp, UPexpr, gs, stacks, ln=False, per_tgt_n=None):
    W = c(n("W"))
    avg = _avg_array(c, n, UPexpr, stacks)
    sel = f'({K("stat")}="{code}")'
    wm = f'({K("who")}="m")' if grp == "m" else who_mask(grp)
    if ln:
        # Final Damage sources multiply: sum of logs of (1+value/100); exp() is taken in the ratio cell
        return f'IF({W}>0,SUMPRODUCT({msk}*{gs}*{sel}*{wm}*LN(1+{avg}/100)),0)'
    ptf = f'*{minel(K("per_tgt"), per_tgt_n)}' if code == "fd_pt" else ""
    return f'IF({W}>0,SUMPRODUCT({msk}*{gs}*{sel}*{wm}*{avg}{ptf}),0)'


def _ramp_exp(c, n, W):
    r = c("rrow")
    Wv = W(c)
    rate = f'INDEX({FULL("val")},{r})/100'
    cap = f'INDEX({FULL("ramp_cap")},{r})'
    lnr = f'LN(1+{rate})'
    short = f'((EXP({lnr}*{Wv})-1)/({lnr}*{Wv}))'
    long_ = f'(((EXP({lnr}*{cap})-1)/{lnr}+({Wv}-{cap})*EXP({lnr}*{cap}))/{Wv})'
    return (f'IF(OR({r}=0,{Wv}<=0),1,IF(INDEX({FULL("ramp_mode")},{r})<>"exp",1,IF({Wv}<={cap},{short},{long_})))')


def _proc_slot(add, k, j, h, n, W, CST):
    kit = K
    nn = lambda base: n(f"{base}{j}")

    def F(col, c, default="0"):
        return f'IF({c(f"prow{j}")}=0,{default},INDEX({FULL(col)},{c(f"prow{j}")}))'

    def ok(c):
        return f'IF({c(f"prow{j}")}=0,0,IF(AND({F("unlock", c)}<={c("lvlc")},{F("maxlvl", c, "99")}>{c("lvlc")}),1,0))'

    def ctg(c):
        g = F("g_ct", c, '"-"')
        return (f'IF(OR({g}="-",AND({g}="BT",{c("isBT")}=1),AND({g}="notBT",{c("isBT")}=0),AND({g}="CB",{c("chboss")}=1),'
                f'AND({g}="PvP",{c("pvp")}=1),AND({g}="notPvP",{c("pvp")}=0)),1,0)')

    def brg(c, br):
        g = F("g_br", c, '"-"')
        return f'IF(OR({g}="-",{g}="{"boss" if br == "b" else "nonboss"}"),1,0)'

    add(nn("pg_b"), f"[{k}] Proc {j}: exists (level, gates) - boss", lambda c: f'{ok(c)}*{ctg(c)}*{brg(c, "b")}')
    add(nn("pg_n"), f"[{k}] Proc {j}: exists (level, gates) - normal", lambda c: f'{ok(c)}*{ctg(c)}*{brg(c, "n")}')

    # time share of the window during which the proc chance is boosted (Buccaneer: Serpent Assault 100% during the Lv1 active)
    def boost_u(c):
        bs = F("boost_src", c, '"-"')
        rb = f'IFERROR(MATCH({h["choice"]}&"|"&{bs},{FULL("idkey")},0),0)'
        per, t0, dur = (f'INDEX({FULL(col)},{rb})' for col in ("per", "t0", "dur"))
        up = uptime_expr(W(c), per, t0, dur, lambda a, b: f"MIN({a},{b})")
        return f'IF(OR({bs}="-",{W(c)}<=0,{rb}=0),0,MIN(1,{up}))'

    add(nn("pc"), f"[{k}] Proc {j}: effective chance",
        lambda c: f'{F("chance", c)}*(1-{boost_u(c)})+{F("boost_chance", c)}*{boost_u(c)}')

    def X_boss(c):
        ce = c(nn("pc"))
        trig_any = f'IF({F("trig", c, chr(34) + "-" + chr(34))}="any",{c(n("atkc"))},0)'
        return f'IF(OR({W(c)}<=0,{c(nn("pg_b"))}=0),0,{ce}*({c(n("ba"))}+{trig_any})/{W(c)})'

    def X_norm(c):
        ce = c(nn("pc"))
        icd0 = f'{F("icd", c)}=0'
        tb = c("tbasic")
        tgn = minel(kit("tgt"), c("cap"))
        hitmask = f'{mask(c, h)}*{ct_gate(c)}*({kit("kind")}="hit")*{CST(c)}*{kit("atk")}'
        basic = f'IF({icd0},{ce}*{c(n("ba"))}*{tb},{c(n("ba"))}*(1-(1-{ce})^{tb}))'
        hits = (f'IF({icd0},{ce}*SUMPRODUCT({hitmask}*{tgn}),SUMPRODUCT({hitmask}*(1-(1-{ce})^{tgn})))')
        trig_any = f'IF({F("trig", c, chr(34) + "-" + chr(34))}="any",{hits},0)'
        return f'IF(OR({W(c)}<=0,{c(nn("pg_n"))}=0),0,({basic}+{trig_any})/{W(c)})'

    add(nn("px_b"), f"[{k}] Proc {j}: successful rolls per second before the cooldown (boss)", X_boss)
    add(nn("px_n"), f"[{k}] Proc {j}: successful rolls per second before the cooldown (normal)", X_norm)
    for br in ("b", "n"):
        add(nn(f"pr_{br}"), f"[{k}] Proc {j}: procs in the window ({'boss' if br == 'b' else 'normal'})",
            lambda c, br=br: f'{W(c)}*{c(nn(f"px_{br}"))}/(1+{F("icd", c)}*{c(nn(f"px_{br}"))})')
    echo = lambda c: (f'SUMPRODUCT({mask(c, h)}*{ct_gate(c)}*({kit("kind")}="echoproc")*({kit("src")}="{j}")'
                      f'*{kit("lines")}*{kit("pct")})')
    add(nn("pd_b"), f"[{k}] Proc {j}: damage coefficient-hits incl. echoes (boss)",
        lambda c: f'{c(nn("pr_b"))}*({F("lines", c)}*{F("pct", c)}*{F("tgt_boss", c, "1")}+{echo(c)})')
    add(nn("pd_n"), f"[{k}] Proc {j}: damage coefficient-hits incl. echoes (normal)",
        lambda c: f'{c(nn("pr_n"))}*({F("lines", c)}*{F("pct", c)}*MIN({F("tgt", c, "1")},{c("cap")})+{echo(c)})')


def _ratio_cells(add, k, h, n, grp):
    """Ratios of the companion ('c') / player ('p') stat buckets once the companion's kit effects apply, vs. the fight average."""
    cr, cdm = h["cr_total"], h["cd_total"]
    lab = "companion" if grp == "c" else "player"
    for br in ("b", "n"):
        add(n(f"fdR{grp}{br}"), f"[{k}] Final Damage ratio ({lab}, {'boss' if br == 'b' else 'normal'})",
            lambda c, br=br: (f'EXP({c(n(f"fd_{grp}"))})*{c(n("rampexp")) if grp == "c" else 1}'
                              f'*(1+{c(n(f"fdpt_{grp}_{br}"))}/100)'))
    add(n(f"crR{grp}"), f"[{k}] Crit ratio ({lab})",
        lambda c: (f'(1+MIN(1,({cr}+{c(n(f"crit_rate_{grp}"))})/100)*({cdm}+{c(n(f"crit_dmg_{grp}"))})/100)'
                   f'/(1+MIN(1,{cr}/100)*{cdm}/100)'))
    add(n(f"mxR{grp}"), f"[{k}] Max Damage multiplier ratio ({lab})",
        lambda c: (f'(MIN({h["min_dmg"]},{h["max_dmg"]}+{c(n(f"max_dmg_{grp}"))})+{h["max_dmg"]}+{c(n(f"max_dmg_{grp}"))})'
                   f'/(MIN({h["min_dmg"]},{h["max_dmg"]})+{h["max_dmg"]})'))
    for br in ("b", "n"):
        dp, D = h["def_pen"], h["defense"]
        add(n(f"dfR{grp}{br}"), f"[{k}] Defense ratio ({lab}, {'boss' if br == 'b' else 'normal'})",
            lambda c, br=br, dp=dp, D=D: (
                f'(6000+{D}*(1-{dp}/100))/(6000+{D}*(1-MIN(0.95,({c(n("m_mon_def"))}+{c(n("m_mon_def_" + br))})/100))'
                f'*(1-{dp}/100)*(1-{c(n(f"def_pen_{grp}"))}/100))'))
        add(n(f"tkR{grp}{br}"), f"[{k}] Damage-taken bucket ratio ({'boss' if br == 'b' else 'normal'})",
            lambda c, br=br: (f'(1+({h["taken_bucket"]}+{c(n("m_dmg_taken"))}+{c(n("m_dmg_taken_" + br))})/100)'
                              f'/(1+{h["taken_bucket"]}/100)'))
        pct = h["boss_pct"] if br == "b" else h["norm_pct"]
        code = "boss_dmg" if br == "b" else "norm_dmg"
        add(n(f"pcR{grp}{br}"), f"[{k}] {'Boss' if br == 'b' else 'Normal'} Monster Damage bucket ratio ({lab})",
            lambda c, pct=pct, code=code: f'IF({c("pvp")}=1,1,(1+({pct}+{c(n(f"{code}_{grp}"))})/100)/(1+{pct}/100))')
    add(n(f"sdR{grp}"), f"[{k}] Skill Damage bucket ratio ({lab})",
        lambda c: f'(1+({h["sd"]}+{c(n(f"skill_dmg_{grp}"))})/100)/(1+{h["sd"]}/100)')
    add(n(f"bdR{grp}"), f"[{k}] Basic Attack Damage bucket ratio ({lab})",
        lambda c: f'(1+({h["bad"]}+{c(n(f"bad_{grp}"))})/100)/(1+{h["bad"]}/100)')
    if grp == "p":
        add(n("asRatioP"), f"[{k}] Player Attack Speed ratio (applied to the Basic Attack part of the player's damage)",
            lambda c: (f'(1+MIN(150,150*(1-(1-({h["aps"]}-1)*100/150)*(1-{c(n("as_p"))}/150)))/100)/{h["aps"]}'))
        for br in ("b", "n"):
            add(n(f"coreP{br}"), f"[{k}] Player core damage ratio ({'boss' if br == 'b' else 'normal'}; excl. skill/basic/speed parts)",
                lambda c, br=br: (f'(1+({h["attack_bucket_avg"]}+{c(n("atk_p"))})/100)/(1+{h["attack_bucket_avg"]}/100)'
                                  f'*{c(n(f"fdRp{br}"))}*{c(n("crRp"))}*{c(n("mxRp"))}*{c(n(f"dfRp{br}"))}'
                                  f'*{c(n(f"tkRp{br}"))}*{c(n(f"pcRp{br}"))}'))


def _hex_ext_ratio(c, h, n):
    """Hexagon state during the fight extension relative to the player's boss DPS baseline: in contents with a boss phase the baseline is that phase's average
    (stacks averaged over [tb0, T]), elsewhere the fight average."""
    teff, e, tb0 = c("Teff"), c(n("E")), c("tb0")
    stacks = f"MIN(3,INT(({teff}+{e}/2)/20))"
    boss_avg = (f"((MAX(0,{teff}-MAX({tb0},20))+MAX(0,{teff}-MAX({tb0},40))+MAX(0,{teff}-MAX({tb0},60)))/({teff}-{tb0}))")
    old = f'(1+({h["agg_damage_avg"]}-{h["hex_avg"]}+{h["hex_snap"](stacks)})/100)/(1+{h["agg_damage_avg"]}/100)'
    new = f'(1+{h["hex_snap"](stacks)}/100)/(1+{h["hex_snap"](boss_avg)}/100)'
    return f'IF({tb0}>0,{new},{old})'


def _status_mult_cells(add, k, h, n):
    """Mean Status-Effect/KO multiplier on the companion's damage over its window: the timeline strip's per-second multiplier when the engine is on
    (boss branch), otherwise the uniform 1 + S x stunned share."""
    idx, mult_r, act_r = h["st_idx"], h["st_mult"], h["st_act"]

    def mean_mult(c):
        s_, W_ = c(n("s")), c(n("W"))
        end = f"{s_}+{W_}"
        ov = maxel("0", minel(f"{idx}+1", end) + "-" + maxel(idx, s_))
        return f"SUMPRODUCT({mult_r}*{act_r}*{ov})/{W_}"
    on_, S_ = h["st_on"], h["st_S"]
    add(n("stMb"), f"[{k}] Status-effect multiplier on the companion's damage (boss branch)",
        lambda c: f'IF({c(n("W"))}<=0,1,IF({on_}=1,{mean_mult(c)},1+{S_}/100*{c("stunfracB")}))')
    add(n("stMn"), f"[{k}] Status-effect multiplier on the companion's damage (normal branch)",
        lambda c: f'1+{S_}/100*{c("stunfracN")}')


def stun_bin_expr(i, c, h):
    """Expected share of bin i ([i, i+1) s) the enemy is stunned/frozen by the companion's casts (candidate-0 timing, so it cannot depend on the
    damage numbers).  Cast n of a stunning row starts at s0 + t0 + n*per; one cast per row can touch a bin (every stun is shorter than its period minus
    a second): the latest cast that starts before the bin's end.  With u = i+1 - s0 - t0 and jj = INT((u - tie)/per), the bin end lies
    r = MOD(u - tie, per) + tie seconds after that cast's start, so the stun [t, t + dur) overlaps the bin by MAX(0, MIN(1, r) - MAX(0, r - dur)).
    One term per stun slot (scalar cells of the Companion chain)."""
    s0, W0 = c("s_0"), c("W_0")
    terms = []
    for j in range(1, NUM_STUN_SLOTS + 1):
        per, t0, skip, dur = c(f"sper{j}"), c(f"st0{j}"), c(f"sskip{j}"), c(f"sdur{j}")
        u = f'({i}+1-{s0}-{t0})'
        um = f'MAX(0,{u}-{TIE})'
        jj = f'INT({um}/{per})'
        r = f'(MOD({um},{per})+{TIE})'
        # cast jj exists inside the window iff t0 + jj*per < W0 - tie  <=>  jj <= casts - 1
        valid = f'({u}>{TIE})*({jj}>={skip})*({jj}<={cnt_expr(W0, per, t0)}-1)'
        terms.append(f'{c(f"sgb{j}")}*{c(f"sp{j}")}*{valid}*MAX(0,MIN(1,{r})-MAX(0,{r}-{dur}))')
    return f'MIN(1,{"+".join(terms)})'


def _damage_cells(add, k, h, n, br, W):
    BAS = n("BAB") if br == "b" else n("BAN")
    rhoF = n("rhoFb") if br == "b" else n("rhoFn")
    pct = h["boss_pct"] if br == "b" else h["norm_pct"]
    extra = h["extra_boss"] if br == "b" else h["extra_norm"]

    def core(c):
        return (f'{c(n("rhoA"))}*{c(n("rhoD"))}*{c(rhoF)}*{c("rhoH")}*{c(n(f"fdRc{br}"))}*{c(n("crRc"))}*{c(n("mxRc"))}*{c(n(f"dfRc{br}"))}'
                f'*{c(n(f"tkRc{br}"))}*{c(n(f"pcRc{br}"))}*{c("lvlmult")}*{c(n("stM" + ("b" if br == "b" else "n")))}')

    tf = n("tfb") if br == "b" else n("tfn")

    def skill_hits(c):
        procs = "+".join(c(n(f"pd_{br}{j}")) for j in range(1, NUM_PROC_SLOTS + 1))
        return f'{c(n(f"HIT{br}"))}+{c(n(f"DOT{br}"))}+{c(tf)}*({c(n(f"ECH{br}"))}+{c(n(f"STN{br}"))}+{procs})'

    add(n("dmgb") if br == "b" else n("dmgn"), f"[{k}] Companion damage over the window ({'boss' if br == 'b' else 'normal'})",
        lambda c: (f'IF({W(c)}>0,{c("unitB")}*{core(c)}*({c(BAS)}*{c(n("bdRc"))}+{c("skratio")}*{c(n("sdRc"))}*({skill_hits(c)}))'
                   f'*IF({c("pvp")}=1,1,1+{pct}/100)*{extra},0)'))


_TOKEN = re.compile(r"@@(\w+)@@")


def resolve_tokens(expr, addr_of):
    """Kit-column tokens (@@col@@) of an expression built outside the chain -> INDEX(col,kr0):INDEX(col,kr0+kn-1)"""
    r0, nrows = addr_of("kr0"), addr_of("kn")
    return _TOKEN.sub(lambda m: f"INDEX({FULL(m.group(1))},{r0}):INDEX({FULL(m.group(1))},{r0}+{nrows}-1)", expr)


def emit(cell_list, addr_of, write):
    """Resolve every cell: write(name, label, '=...formula').  Kit-column tokens become INDEX(col,kr0):INDEX(col,kr0+kn-1)."""
    r0, nrows = addr_of("kr0"), addr_of("kn")

    def rng(m):
        col = FULL(m.group(1))
        return f"INDEX({col},{r0}):INDEX({col},{r0}+{nrows}-1)"

    for name, label, fn in cell_list:
        write(name, label, "=" + _TOKEN.sub(rng, fn(addr_of)))
