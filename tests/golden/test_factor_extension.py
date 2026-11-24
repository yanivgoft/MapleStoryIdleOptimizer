#!/usr/bin/env python3
"""The growth-curve extension past skill level 300 (``engine/common/factors.py``: production = extended, ``legacy_clamp`` = the frozen workbooks' 300-clamp), for every PUBLISHED class.

(a) a character whose every skill total level is <= 300 (level 105, zero skill-level bonuses): extended mode == legacy mode, BIT-EXACT (the extension changes nothing below 300);
(b) a late-game character (level 200, large skill-level bonuses: 4th job = (200-100)*3 + bonus ...): extended total DPS >= legacy, and STRICTLY greater for every class whose compute
    actually read a growing (non-flat) curve at a level above 300 (detected by instrumenting ``get_factor``; the classes are printed).

    python3 tests/golden/test_factor_extension.py        # also pytest-collectable
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
import snapshot_common as SN  # noqa: E402
import factor_mode  # noqa: E402
import engine  # noqa: E402
from engine.common import factors  # noqa: E402

FACTOR_MODE = factor_mode.pin("extended")

CONTENTS = ("World Boss", "Chapter Hunt")
EARLY = dict(level=105, skill_lvl_1st=0, skill_lvl_2nd=0, skill_lvl_3rd=0, skill_lvl_4th=0, skill_lvl_all=0)
LATE = dict(level=200, skill_lvl_1st=150, skill_lvl_2nd=150, skill_lvl_3rd=150, skill_lvl_4th=150, skill_lvl_all=30)


def growing(idx):
    """The curve keeps growing past 300 (a LINEAR_CURVES entry whose last slope is > 0)."""
    return idx in factors.LINEAR_CURVES and factors.LINEAR_CURVES[idx][-1][1] > 0


def inputs(module, content, levels):
    d = SN.make_inputs(module, content, "late", content == "Chapter Hunt")
    d.update({k: v for k, v in levels.items() if k in d or k == "level"})
    return d


def total(module, d, legacy):
    with factors.legacy_clamp(legacy):
        return module.compute(dict(d))["total_dps"]


def classes():
    import importlib
    return [(cid, importlib.import_module(f"engine.classes.{cid}")) for cid in engine.published_classes()]


def test_below_300_extended_equals_legacy_bit_exactly():
    n = 0
    for cid, mod in classes():
        for content in CONTENTS:
            d = inputs(mod, content, EARLY)
            a, b = total(mod, d, False), total(mod, d, True)
            assert a == b and a > 0, (cid, content, a, b)
            n += 1
    return n


def late_game():
    """[(class, content, extended, legacy, read a growing curve above 300)]."""
    rows = []
    real = factors.get_factor
    for cid, mod in classes():
        for content in CONTENTS:
            d = inputs(mod, content, LATE)
            hits = []

            def spy(level, idx, _real=real, _hits=hits):
                if round(level) > 300 and growing(idx):
                    _hits.append((round(level), idx))
                return _real(level, idx)
            factors.get_factor = spy
            try:
                ext = total(mod, d, False)
            finally:
                factors.get_factor = real
            rows.append((cid, content, ext, total(mod, d, True), sorted({i for _, i in hits})))
    return rows


def test_late_game_extended_is_at_least_legacy_and_strictly_more_where_curves_above_300_are_read():
    rows = late_game()
    for cid, content, ext, leg, curves in rows:
        assert ext >= leg, (cid, content, ext, leg)
        if curves:
            assert ext > leg, (cid, content, ext, leg, curves)
    return rows


def main():
    n = test_below_300_extended_equals_legacy_bit_exactly()
    rows = test_late_game_extended_is_at_least_legacy_and_strictly_more_where_curves_above_300_are_read()
    more = sorted({c for c, _, e, l, _ in rows if e > l})
    same = sorted({c for c, _, e, l, _ in rows} - set(more))
    print(f"OK: {n} (class, content) cases at total level <= 300 are bit-identical extended vs legacy; late game (level 200, bonuses 150/150/150/150/+30): extended > legacy for "
          f"{len(more)} classes ({', '.join(more)}), equal for {len(same)} ({', '.join(same) or '-'})")
    for c, content, e, l, curves in rows:
        print(f"  {c:20s} {content:12s} extended/legacy = {e / l:.6f}  curves read above 300: {curves}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
