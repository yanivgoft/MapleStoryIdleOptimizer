"""Artifact Potential lines (the workbook's ``ArtifactsInput`` sheet): per artifact up to 3 lines (rarity + stat), each worth ``value(stat, rarity) x DPS per
unit(stat)`` DPS, gated by the artifact's Star Level, plus the artifact's Total Potential DPS Gain - the number ``engine.sensitivity`` adds to an equip row
(``inputs["artifact_potential_gain"]``).

    from engine import potentials
    gains = potentials.potential_gains(state, rates, total_dps)          # {artifact id: Total Potential DPS Gain}   (the sensitivity hook)
    detail = potentials.artifact_potential("book_of_ancient", 5, [("Legendary", "Damage %"), ("Epic", "Damage %")], rates, total_dps)

``state`` = ``{artifact id: {"star": 0..5 | "Not Unlocked" | None, "lines": [(rarity, stat), ...]}}`` (the ArtifactsInput table; missing artifact = the
workbook default: star by rank, every line Rare / "(none)").  ``rates`` = {sweep key: DPS of one +1 step} = the Sensitivity sheet's column H =
``cubes.sweep_rates(sens_result)``.  Potentials are a reference calculator: the gain is NOT part of the live DPS (the user folds a kept roll into Inputs); the
equip-toggle row adds it unsigned in both directions.

Rules (ported from ``build_artifacts_input_sheet`` / ``artifact_potential_gain_expr``):
* Epic / Unique artifacts have 2 lines, Legendary 3; line n is active from Star Level 1 / 2 / 5 (``LINE_MIN_STAR``); an inactive line is worth 0.
* line gain = value(stat, rarity) x rate(stat's sweep key); stats without a DPS bucket (Damage Taken Decrease, Defense %, Accuracy, Status Effect Damage)
  and "(none)" are worth 0.  The Critical Rate line uses the LITERAL ``crit_rate`` rate (no cap substitution here, unlike cube lines).
* Total: lines on the SAME stat add, different stats' groups multiply: ``Total x (prod(1 + group / Total) - 1)`` over the distinct stats.
* ``Equipped?`` = the artifact's name is one of the equip-slot pickers (the workbook has 4, the engine up to 5); ``Star Level, resolved`` = 0 for "Not Unlocked".
The class-specific part is ``stat_to_key`` (``Main Stat %`` -> int_pct for the INT mages; default = the data table copied from the FP-Mage builder).
"""
from .data import artifacts as AD

RARITIES = list(AD.ARTIFACT_POTENTIAL_RARITIES)
VALUES = AD.ARTIFACT_POTENTIAL_VALUES
STAT_TO_KEY = AD.ARTIFACT_POTENTIAL_STAT_TO_SWEEP_KEY
POTENTIAL_STATS = list(VALUES)                      # the ArtifactsInput stat dropdown (after "(none)")
NONE_STAT = "(none)"
LINE_MIN_STAR = (1, 2, 5)                           # Star Level at which line 1 / 2 / 3 become active
DEFAULT_RARITY = "Rare"


def num_lines(art):
    """3 lines for Legendary artifacts, 2 for Epic / Unique (regardless of Star Level)."""
    return 3 if AD.ARTIFACT_RANK[art] == "Legendary" else 2


def resolve_star(star):
    """ArtifactsInput column N: 'Not Unlocked' (or blank) reads as star 0."""
    return 0 if star is None or star == "Not Unlocked" else int(star)


def default_star(art):
    return AD.ARTIFACT_RANK_DEFAULT_STAR[AD.ARTIFACT_RANK[art]]


def resolve_equipped(slots, art):
    """ArtifactsInput column M: is the artifact (by id or by its workbook name) picked in one of the equip slots (<= 5)?"""
    label = AD.ARTIFACT_LABELS[art]
    return any(s is not None and str(s).casefold() in (label.casefold(), art.casefold()) for s in (slots or []))


def _same(a, b):
    return str(a).casefold() == str(b).casefold()      # Excel's = on text is case-insensitive


def line_gain(rarity, stat, star, line_index, rates, stat_to_key=None):
    """One line's DPS Gain (ArtifactsInput E / H / K).  ``star`` = the resolved Star Level, ``line_index`` 0..2."""
    if resolve_star(star) < LINE_MIN_STAR[line_index]:
        return 0.0
    if stat is None or stat == NONE_STAT or stat not in VALUES:
        return 0.0
    key = (stat_to_key or STAT_TO_KEY).get(stat)
    if key is None:
        return 0.0                                     # no DPS bucket: 0 whatever the rarity
    if rarity not in VALUES[stat]:
        raise ValueError(f"unknown artifact potential rarity {rarity!r} (choose from {RARITIES})")
    return VALUES[stat][rarity] * float(rates.get(key, 0.0))


def artifact_potential(art, star, lines, rates, total_dps, stat_to_key=None):
    """{"lines": [{rarity, stat, active, gain}], "total": Total Potential DPS Gain, "star": resolved star} of one artifact."""
    n = num_lines(art)
    star_r = resolve_star(star)
    lines = [tuple(x) for x in (lines or [])][:n]
    while len(lines) < n:
        lines.append((DEFAULT_RARITY, NONE_STAT))
    gains = [line_gain(r, s, star_r, i, rates, stat_to_key) for i, (r, s) in enumerate(lines)]
    stats = [s for _r, s in lines]
    # ArtifactsInput L: group by stat first (same-stat lines add), then multiply the distinct stats' factors - factor_i is 1 for "(none)" and for a line whose
    # stat already appeared in an earlier line (its gain went into that line's group).  Line 3 absent (Epic / Unique) = blank.
    factor = 1.0
    for i in range(n):
        if stats[i] == NONE_STAT or any(_same(stats[i], stats[j]) for j in range(i)):
            continue
        grouped = gains[i] + sum(gains[j] for j in range(i + 1, n) if _same(stats[j], stats[i]))
        factor *= 1 + grouped / total_dps
    total = total_dps * (factor - 1)
    return dict(star=star_r, lines=[dict(rarity=r, stat=s, active=star_r >= LINE_MIN_STAR[i], gain=g) for i, ((r, s), g) in enumerate(zip(lines, gains))],
                total=total)


def potential_gains(state, rates, total_dps, stat_to_key=None):
    """{artifact id: Total Potential DPS Gain} for EVERY artifact (0.0 where nothing is rolled / unlocked) - the value ``engine.sensitivity`` takes as
    ``inputs["artifact_potential_gain"]`` and adds (unsigned) to the artifact's equip-toggle row."""
    state = state or {}
    out = {}
    for art in AD.ARTIFACT_LABELS:
        s = state.get(art) or {}
        star = s["star"] if "star" in s else default_star(art)
        out[art] = artifact_potential(art, star, s.get("lines"), rates, total_dps, stat_to_key)["total"]
    return out


def potential_table(state, rates, total_dps, equipped_slots=None, stat_to_key=None):
    """The whole ArtifactsInput table: one dict per artifact (key, label, rank, equipped, star, lines, total), in the sheet's order."""
    state = state or {}
    rows = []
    for art, label in AD.ARTIFACT_LABELS.items():
        s = state.get(art) or {}
        star = s["star"] if "star" in s else default_star(art)
        d = artifact_potential(art, star, s.get("lines"), rates, total_dps, stat_to_key)
        rows.append(dict(key=art, label=label, rank=AD.ARTIFACT_RANK[art], equipped=resolve_equipped(equipped_slots, art), **d))
    return rows


def hook_for(class_module, inputs, state, stat_to_key=None):
    """Convenience: run the sensitivity ``stats`` part of ``inputs`` once and return ``(gains, rates, total_dps)`` where ``gains`` is ready to be put into
    ``inputs["artifact_potential_gain"]`` for a following ``sensitivity.run(..., which=["artifacts"])``."""
    from . import cubes, sensitivity
    sens = sensitivity.run(class_module, inputs, which=["stats"])
    rates = cubes.sweep_rates(sens)
    total = sens["baseline_total"]
    return potential_gains(state, rates, total, stat_to_key), rates, total
