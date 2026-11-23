"""Boss / normal branch blending shared by every class.

Total DPS blends two branches by the normal-monster time weight ``w`` (0 = pure boss, 1 = pure normal; Chapter Breakthrough /
Hero Dungeon use the emphasis weight): ``(1-w) * boss_unit * b + w * normal_unit * n`` with ``b`` / ``n`` the branch multipliers
(Boss/Normal Monster Damage%, target count, timing factor).  The ledger remembers every row's two branch values; they feed the
companion host (player boss/normal DPS) and the result's boss-only / normal-only totals.
"""


class BranchLedger:
    def __init__(self, normal_weight):
        self.w = normal_weight
        # key -> (boss DPS, normal DPS, explicit per-branch units?, boss multiplier, normal multiplier) of the last blend of that key
        self.pairs = {}

    def blend(self, key, boss_unit, normal_unit, b, n, explicit):
        """Time-weighted DPS of one row.  ``b``/``n`` already include the row's timing factors."""
        w = self.w
        self.pairs[key] = (boss_unit * b, normal_unit * n, explicit, b, n)
        return (1 - w) * boss_unit * b + w * normal_unit * n

    # ---- explicit rows: the row stores its finished per-branch DPS, so split totals / branch shares just read it ----
    def blend_unit(self, key, unit, b, n, fb, fn):
        """``(1-w) * unit * b * fb + w * unit * n * fn`` left to right (the timing factors fb / fn are NOT pre-multiplied into b / n, which changes
        the float association relative to ``blend``).  Every such row has the same unit in both branches."""
        w = self.w
        self.pairs[key] = (unit * b * fb, unit * n * fn, True, b * fb, n * fn)
        return (1 - w) * unit * b * fb + w * unit * n * fn

    def blend_pair(self, key, pair, boss_b, norm_b, fb, fn):
        """A finished (boss DPS, normal DPS) pair blended ``(1-w) * pair_b + w * pair_n``."""
        self.pairs[key] = (pair[0], pair[1], True, boss_b * fb, norm_b * fn)
        return (1 - self.w) * pair[0] + self.w * pair[1]

    def put(self, key, rate_boss, rate_normal, hd, b, n, fb, fn):
        """``pair = (rate_b * hit * b * fb, rate_n * hit * n * fn)`` (the verify scripts' ``branch_pair``); returns the pair."""
        pair = (rate_boss * hd * b * fb, rate_normal * hd * n * fn)
        self.pairs[key] = (pair[0], pair[1], True, b * fb, n * fn)
        return pair

    def put_zero(self, key):
        self.pairs[key] = (0.0, 0.0, True, 1.0, 1.0)

    def pair(self, key):
        p = self.pairs[key]
        return p[0], p[1]

    def split_totals(self, row_dps, uniform_keys=()):
        """(boss-only total, normal-only total, uniform-row boss total) of the player's rows - the damage-share weights of the
        companion's uplift.  ``row_dps`` = ordered [(key, blended DPS), ...].  Multiplier-style rows (same rate in both branches)
        have DPS = K x ((1-w) b + w n), so their boss DPS is K b = DPS x b / ((1-w) b + w n)."""
        w = self.w
        pb = pn = pu = 0.0
        for key, val in row_dps:
            pair = self.pairs.get(key)
            if pair is None:
                continue
            bd, nd, explicit, bm_, nm_ = pair
            if explicit:
                pb += bd
                pn += nd
                bd_row = bd
            else:
                denom = (1 - w) * bm_ + w * nm_
                if denom == 0:           # degenerate (both multipliers 0): the row contributes nothing in either branch
                    continue
                pb += val * bm_ / denom
                pn += val * nm_ / denom
                bd_row = val * bm_ / denom
            if key in uniform_keys:
                pu += bd_row
        return pb, pn, pu

    def branch_share(self, key, val):
        """(boss, normal) DPS of one row in the same units as split_totals (used for per-skill breakdowns)."""
        pair = self.pairs.get(key)
        if pair is None:
            return None
        bd, nd, explicit, bm_, nm_ = pair
        if explicit:
            return bd, nd
        w = self.w
        denom = (1 - w) * bm_ + w * nm_
        if denom == 0:
            return 0.0, 0.0
        return val * bm_ / denom, val * nm_ / denom
