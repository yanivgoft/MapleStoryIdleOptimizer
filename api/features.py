"""Cube optimizer, Equipment Compare and Artifact potential lines: request validation, static metadata and the (cached) pricing they share.

The engine does the maths (``engine.cubes`` / ``engine.equipment`` / ``engine.potentials``); this module only

* validates the extra body keys (``gear`` / ``only`` | ``current`` / ``new`` | ``potentials``) against the engine's own tables (slots, rarities, stat lists),
* builds ``GET .../cubes/meta`` (everything the UI needs to render the three editors without computing anything),
* prices stats once per character: ``rates_context`` (Sensitivity column H + the live crit-cap facts; used by Equipment Compare and Artifact potentials) and
  ``cubes_pricing`` (the cube optimizer's ``Pricing``, incl. the CDR curve and the summoning-time model).  Both are expensive (~1-3 s: they run the
  sensitivity module), so they are kept in small in-memory LRU+TTL caches, which is what makes "request the rows slot by slot" cheap after the first call.

Class capability = the sensitivity module's (``ClassEntry.supports_sensitivity``, ``registry.SENSITIVITY_CLASSES``): pricing comes from it.  Classes get their own
potential / equipment stat -> sweep-key maps through ``STAT_TO_KEY_BY_CLASS`` (empty = the engine's FP-Mage / INT defaults).
"""
import logging
import math
import threading

from .cache import TTLCache, cache_key

log = logging.getLogger("msi.features")

try:                                                     # a broken engine module only disables these three features (they answer 501)
    from engine import cubes, equipment, potentials
    from engine.data import artifacts as artifact_data
except Exception:                                        # noqa: BLE001
    log.exception("engine.cubes / equipment / potentials failed to import; cube features disabled")
    cubes = equipment = potentials = artifact_data = None

CUBES_UNSUPPORTED = "the cube optimizer is not modelled for this class yet"
EQUIPMENT_UNSUPPORTED = "equipment compare is not modelled for this class yet"
POTENTIALS_UNSUPPORTED = "artifact potentials are not modelled for this class yet"

# class id -> {"cubes": {...}, "equipment": {...}, "potentials": {...}, "cubes_sub_stat_pct": {...}} stat -> sweep key maps (None / missing = the engine's default tables,
# which are FP-Mage's).  The maps live in the class's Sensitivity spec (``SensSpec.stat_to_key``, engine/sens_specs/<class>.py); a class with maps is listed here.
try:
    from engine import sens_specs
    STAT_TO_KEY_BY_CLASS = {cid: sens_specs.get(cid).stat_to_key for cid in sens_specs.CLASS_IDS if sens_specs.get(cid) is not None and sens_specs.get(cid).stat_to_key}
except Exception:                                        # noqa: BLE001
    log.exception("engine.sens_specs failed to import; per-class stat maps disabled")
    STAT_TO_KEY_BY_CLASS = {}

SLOT_LABELS = {
    "head": "Head", "cape": "Cape", "chest": "Chest", "shoulders": "Shoulders", "legs": "Legs", "belt": "Belt", "gloves": "Gloves", "boots": "Boots",
    "ring": "Ring", "neck": "Necklace", "eye-accessory": "Eye accessory", "ring2": "Ring 2", "face": "Face accessory", "earrings": "Earrings", "pocket": "Pocket",
}
RARITY_LABELS = {"normal": "Normal", "rare": "Rare", "epic": "Epic", "unique": "Unique", "legendary": "Legendary", "mystic": "Mystic"}
MAX_PITY = 10000
MAX_LINE_VALUE = 1_000_000.0
MAX_ATTACK = 1e12
STAR_OPTIONS = (0, 1, 2, 3, 4, 5, "Not Unlocked")


def available():
    return cubes is not None and equipment is not None and potentials is not None


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _num(v, name, errors, lo=0.0, hi=MAX_LINE_VALUE):
    """Finite number within [lo, hi] (``None`` reads as 0, like a blank cell); appends to ``errors`` and returns 0.0 otherwise."""
    if v is None:
        return 0.0
    if not _is_number(v) or (isinstance(v, float) and not math.isfinite(v)):
        errors.append({"field": name, "message": "must be a number"})
        return 0.0
    if v < lo or v > hi:
        errors.append({"field": name, "message": f"must be between {lo:g} and {hi:g}"})
        return 0.0
    return float(v)


def split_body(body, keys):
    """``(compute body without the extra keys, {extra key: raw value})``; a non-dict body is returned unchanged for the compute validator to reject."""
    if not isinstance(body, dict):
        return body, {}
    extras = {k: body[k] for k in keys if k in body}
    return {k: v for k, v in body.items() if k not in extras}, extras


# ----------------------------------------------------------------------------------------------------------------------------------------------
# Cubes
# ----------------------------------------------------------------------------------------------------------------------------------------------
CUBES_EXTRA_KEYS = ("gear", "only")


def _validate_lines(raw, name, errors, stats, n):
    """Up to ``n`` ``{stat, value}`` lines -> ``n`` (stat, value) tuples (missing lines = "(none)", 0)."""
    out = []
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        errors.append({"field": name, "message": f"must be a list of up to {n} {{stat, value}} lines"})
        return [(cubes.NONE_STAT, 0.0)] * n
    if len(raw) > n:
        errors.append({"field": name, "message": f"at most {n} lines"})
    for i, ln in enumerate(raw[:n]):
        lname = f"{name}[{i}]"
        if not isinstance(ln, dict):
            errors.append({"field": lname, "message": "must be an object {stat, value}"})
            out.append((cubes.NONE_STAT, 0.0))
            continue
        extra = set(ln) - {"stat", "value"}
        if extra:
            errors.append({"field": lname, "message": f"unknown keys: {', '.join(sorted(extra))}"})
        stat = ln.get("stat")
        if stat is None or stat == "":
            stat = cubes.NONE_STAT
        if not isinstance(stat, str) or (stat != cubes.NONE_STAT and stat not in stats):
            errors.append({"field": f"{lname}.stat", "message": "unknown stat"})
            stat = cubes.NONE_STAT
        value = _num(ln.get("value"), f"{lname}.value", errors)
        out.append((stat, 0.0 if stat == cubes.NONE_STAT else value))
    while len(out) < n:
        out.append((cubes.NONE_STAT, 0.0))
    return out


def validate_gear(raw):
    """``(full gear rows, errors)``.  ``raw`` = list of ``{slot, potential_type, rarity, pity, lines: [{stat, value} x <=3]}`` (every key but ``slot`` optional;
    a (slot, potential type) pair may appear once).  The result always holds all 15 slots x 2 potential types in ``cubes.default_gear()`` order: pairs the client
    did not send stay at the blank state (normal, pity 0, no lines) - the other rows' lines matter for cross-row baselines (summoning time), so the engine
    always sees the whole gear."""
    errors = []
    rows = {(r["slot"], r["potential_type"]): r for r in cubes.default_gear()}
    if raw is None:
        return list(rows.values()), errors
    if not isinstance(raw, list):
        return None, [{"field": "gear", "message": "must be a list of {slot, potential_type, rarity, pity, lines}"}]
    if len(raw) > len(rows):
        errors.append({"field": "gear", "message": f"at most {len(rows)} rows (15 slots x Potential / Bonus Potential)"})
        return None, errors
    stats = set(cubes.all_potential_stats())
    seen = set()
    for i, r in enumerate(raw):
        name = f"gear[{i}]"
        if not isinstance(r, dict):
            errors.append({"field": name, "message": "must be an object"})
            continue
        extra = set(r) - {"slot", "potential_type", "rarity", "pity", "lines"}
        if extra:
            errors.append({"field": name, "message": f"unknown keys: {', '.join(sorted(extra))}"})
        slot, ptype = r.get("slot"), r.get("potential_type", "Potential")
        if slot not in cubes.CUBE_SLOTS:
            errors.append({"field": f"{name}.slot", "message": f"must be one of: {', '.join(cubes.CUBE_SLOTS)}"})
            continue
        if ptype not in cubes.POTENTIAL_TYPES:
            errors.append({"field": f"{name}.potential_type", "message": f"must be one of: {', '.join(cubes.POTENTIAL_TYPES)}"})
            continue
        if (slot, ptype) in seen:
            errors.append({"field": name, "message": f"duplicate row for {slot} / {ptype}"})
            continue
        seen.add((slot, ptype))
        rarity = r.get("rarity", "normal")
        rarity = rarity.strip().casefold() if isinstance(rarity, str) else rarity
        if rarity not in cubes.RARITY_ORDER:
            errors.append({"field": f"{name}.rarity", "message": f"must be one of: {', '.join(cubes.RARITY_ORDER)}"})
            rarity = "normal"
        pity = r.get("pity", 0)
        if pity is None:
            pity = 0
        if not _is_number(pity) or (isinstance(pity, float) and (not math.isfinite(pity) or pity != int(pity))):
            errors.append({"field": f"{name}.pity", "message": "must be a whole number"})
            pity = 0
        elif pity < 0 or pity > MAX_PITY:
            errors.append({"field": f"{name}.pity", "message": f"must be between 0 and {MAX_PITY}"})
            pity = 0
        lines = _validate_lines(r.get("lines"), f"{name}.lines", errors, stats, 3)
        rows[(slot, ptype)] = dict(slot=slot, potential_type=ptype, rarity=rarity, pity=int(pity), lines=lines)
    return (list(rows.values()) if not errors else None), errors


def validate_only(raw, gear):
    """``(sorted row indices into ``gear``, errors)``: ``only`` = list of slot ids (both potential types) and / or ``{slot, potential_type}`` objects; absent = every row."""
    if raw is None:
        return list(range(len(gear))), []
    errors = []
    if not isinstance(raw, list) or not raw:
        return None, [{"field": "only", "message": "must be a non-empty list of slot ids or {slot, potential_type} objects"}]
    wanted = set()
    for i, o in enumerate(raw):
        slot, ptype = (o, None) if isinstance(o, str) else ((o.get("slot"), o.get("potential_type")) if isinstance(o, dict) else (None, None))
        if slot not in cubes.CUBE_SLOTS or (ptype is not None and ptype not in cubes.POTENTIAL_TYPES):
            errors.append({"field": f"only[{i}]", "message": f"must be a slot id ({', '.join(cubes.CUBE_SLOTS)}) or an object {{slot, potential_type}}"})
            continue
        wanted.update((slot, t) for t in ([ptype] if ptype else cubes.POTENTIAL_TYPES))
    if errors:
        return None, errors
    return [i for i, g in enumerate(gear) if (g["slot"], g["potential_type"]) in wanted], []


def validate_cubes_extras(extras):
    """``(gear rows, only indices, errors)`` of a cubes request's extra keys."""
    gear, errors = validate_gear(extras.get("gear"))
    if errors:
        return None, None, errors
    only, errors = validate_only(extras.get("only"), gear)
    return gear, only, errors


_META = None


def cubes_meta():
    """Static metadata of ``GET .../cubes/meta`` (computed once per process): slots, rarities, stat options per slot, pity caps, milestones, equipment and
    artifact-potential tables.  Nothing here depends on the class's inputs."""
    global _META
    if _META is None:
        rates = cubes.rarity_rates()
        table = cubes.roll_table()
        all_stats = cubes.all_potential_stats()
        by_slot = {}
        for slot in cubes.CUBE_SLOTS:
            have = {s for (sl, _r, _l), entries in table.items() if sl in ("ALL", slot) for s, _v, _w in entries}
            by_slot[slot] = sorted(have | set(cubes.EXTRA_SELECTABLE_STATS))
        _META = {
            "slots": [{"key": s, "label": SLOT_LABELS.get(s, s)} for s in cubes.CUBE_SLOTS],
            "potential_types": list(cubes.POTENTIAL_TYPES),
            "rarities": [{"key": r, "label": RARITY_LABELS.get(r, r.title())} for r in cubes.RARITY_ORDER],
            "none_stat": cubes.NONE_STAT,
            "stats": all_stats,
            "stats_by_slot": by_slot,
            "pity_caps": {t: {r: int(v["max"]) for r, v in rates[t].items()} for t in cubes.POTENTIAL_TYPES},
            "upgrade_rates": {t: {r: v["rate"] for r, v in rates[t].items()} for t in cubes.POTENTIAL_TYPES},
            "milestones": list(cubes.CUBE_MILESTONES),
            "max_cubes": cubes.MAX_CUBES,
            "csv_columns": list(cubes.CSV_COLUMNS),
            "max_rows": len(cubes.CUBE_SLOTS) * len(cubes.POTENTIAL_TYPES),
            "limits": {"max_pity": MAX_PITY, "max_line_value": MAX_LINE_VALUE},
            "equipment": {"stats": list(equipment.DROPDOWN_STATS), "lines": equipment.N_LINES, "attack_stat": equipment.ATTACK_STAT, "none_stat": equipment.NONE_STAT},
            "artifact_potentials": {
                "rarities": list(potentials.RARITIES),
                "stats": list(potentials.POTENTIAL_STATS),
                "values": {s: dict(v) for s, v in potentials.VALUES.items()},
                "line_min_star": list(potentials.LINE_MIN_STAR),
                "default_rarity": potentials.DEFAULT_RARITY,
                "none_stat": potentials.NONE_STAT,
                "star_options": list(STAR_OPTIONS),
                "artifacts": [{"key": k, "label": label, "rank": artifact_data.ARTIFACT_RANK[k], "lines": potentials.num_lines(k),
                               "default_star": potentials.default_star(k)} for k, label in artifact_data.ARTIFACT_LABELS.items()],
            },
        }
    return _META


# ----------------------------------------------------------------------------------------------------------------------------------------------
# Equipment compare
# ----------------------------------------------------------------------------------------------------------------------------------------------
EQUIPMENT_EXTRA_KEYS = ("current", "new")


def _validate_equip(raw, name, errors):
    if raw is None:
        return {"attack": 0.0, "lines": []}
    if not isinstance(raw, dict):
        errors.append({"field": name, "message": "must be an object {attack, lines: [{stat, value} x <=5]}"})
        return {"attack": 0.0, "lines": []}
    extra = set(raw) - {"attack", "lines"}
    if extra:
        errors.append({"field": name, "message": f"unknown keys: {', '.join(sorted(extra))}"})
    attack = _num(raw.get("attack"), f"{name}.attack", errors, 0.0, MAX_ATTACK)
    lines = _validate_lines(raw.get("lines"), f"{name}.lines", errors, set(equipment.DROPDOWN_STATS), equipment.N_LINES)
    return {"attack": attack, "lines": lines}


def validate_equipment_extras(extras):
    """``((current, new), errors)`` - each ``{"attack", "lines": [(stat, value) x 5]}``."""
    errors = []
    cur = _validate_equip(extras.get("current"), "current", errors)
    new = _validate_equip(extras.get("new"), "new", errors)
    return (None if errors else (cur, new)), errors


# ----------------------------------------------------------------------------------------------------------------------------------------------
# Artifact potentials
# ----------------------------------------------------------------------------------------------------------------------------------------------
POTENTIALS_EXTRA_KEYS = ("potentials",)


def validate_potentials_extras(extras):
    """``(state, errors)``: ``potentials`` = ``{artifact id: {"star": 0..5 | "Not Unlocked" | null (optional), "lines": [{rarity, stat} x <= 2 (3 for Legendary)]}}``;
    state = ``{artifact id: {"star"?: ..., "lines": [(rarity, stat)]}}`` (an absent ``star`` is kept absent: the engine's default by rank / the equip slot's star)."""
    raw = extras.get("potentials")
    if raw is None:
        return {}, []
    if not isinstance(raw, dict):
        return None, [{"field": "potentials", "message": "must be an object {artifact id: {star, lines}}"}]
    errors, state = [], {}
    stats = set(potentials.POTENTIAL_STATS)
    for art, s in raw.items():
        name = f"potentials.{art}"
        if art not in artifact_data.ARTIFACT_LABELS:
            errors.append({"field": name, "message": "unknown artifact"})
            continue
        if not isinstance(s, dict):
            errors.append({"field": name, "message": "must be an object {star, lines}"})
            continue
        extra = set(s) - {"star", "lines"}
        if extra:
            errors.append({"field": name, "message": f"unknown keys: {', '.join(sorted(extra))}"})
        entry = {}
        if "star" in s:
            star = s["star"]
            if star is not None and not (star in STAR_OPTIONS and not isinstance(star, bool)):
                errors.append({"field": f"{name}.star", "message": "must be 0-5, 'Not Unlocked' or null"})
            else:
                entry["star"] = star
        n = potentials.num_lines(art)
        raw_lines = s.get("lines")
        if raw_lines is None:
            raw_lines = []
        if not isinstance(raw_lines, list):
            errors.append({"field": f"{name}.lines", "message": f"must be a list of up to {n} {{rarity, stat}} lines"})
            raw_lines = []
        elif len(raw_lines) > n:
            errors.append({"field": f"{name}.lines", "message": f"at most {n} lines for this artifact ({artifact_data.ARTIFACT_RANK[art]})"})
        lines = []
        for i, ln in enumerate(raw_lines[:n]):
            lname = f"{name}.lines[{i}]"
            if not isinstance(ln, dict) or set(ln) - {"rarity", "stat"}:
                errors.append({"field": lname, "message": "must be an object {rarity, stat}"})
                continue
            rarity = ln.get("rarity", potentials.DEFAULT_RARITY)
            if rarity is None:
                rarity = potentials.DEFAULT_RARITY
            if rarity not in potentials.RARITIES:
                errors.append({"field": f"{lname}.rarity", "message": f"must be one of: {', '.join(potentials.RARITIES)}"})
                continue
            stat = ln.get("stat")
            if stat is None or stat == "":
                stat = potentials.NONE_STAT
            if not isinstance(stat, str) or (stat != potentials.NONE_STAT and stat not in stats):
                errors.append({"field": f"{lname}.stat", "message": "unknown stat"})
                continue
            lines.append((rarity, stat))
        entry["lines"] = lines
        state[art] = entry
    return (None if errors else state), errors


# ----------------------------------------------------------------------------------------------------------------------------------------------
# Pricing (expensive, cached)
# ----------------------------------------------------------------------------------------------------------------------------------------------
class PricingService:
    """The shared, cached pricing of a character: ``rates_context`` (stats part) and ``cubes_pricing`` (stats + cdr + summon_time parts).  Thread-safe; one
    build at a time per kind (a second request for the same key waits for the first and then hits the cache)."""

    def __init__(self, ttl_s=600, rates_entries=32, pricing_entries=16, clock=None):
        kw = {} if clock is None else {"clock": clock}
        self.rates = TTLCache(rates_entries, ttl_s, **kw)
        self.pricing = TTLCache(pricing_entries, ttl_s, **kw)
        self._rates_lock = threading.Lock()
        self._pricing_lock = threading.Lock()
        self.rates_builds = self.pricing_builds = 0           # (tests / diagnostics)

    # -- Sensitivity column H + the crit-cap facts ---------------------------------------------------------------------------------------------
    def rates_key(self, class_id, clean):
        return cache_key("rates", class_id, clean)

    def cached_rates(self, class_id, clean):
        return self.rates.get(self.rates_key(class_id, clean))

    def rates_context(self, entry, clean):
        key = self.rates_key(entry.id, clean)
        hit = self.rates.get(key)
        if hit is not None:
            return hit
        with self._rates_lock:
            hit = self.rates.get(key)
            if hit is not None:
                return hit
            sens = entry.sensitivity(dict(clean), which=["stats"])
            ctx = {"rates": cubes.sweep_rates(sens), "total_dps": sens["baseline_total"], "content_type": sens.get("content_type")}
            ctx.update(_crit_facts(entry, clean))
            self.rates_builds += 1
            self.rates.put(key, ctx)
            return ctx

    # -- the cube optimizer's Pricing ---------------------------------------------------------------------------------------------------------
    def pricing_key(self, class_id, clean, companion_pct):
        return cache_key("pricing", class_id, clean, companion_pct)

    def cubes_pricing(self, entry, clean, companion_pct):
        key = self.pricing_key(entry.id, clean, companion_pct)
        hit = self.pricing.get(key)
        if hit is not None:
            return hit
        with self._pricing_lock:
            hit = self.pricing.get(key)
            if hit is not None:
                return hit
            inputs = dict(clean, companion_potential_lines_pct=companion_pct)    # b0 of the summoning-time model excludes exactly the gear's own boots lines
            sens = entry.sensitivity(dict(inputs), which=["stats", "cdr", "summon_time"])
            pricing = cubes.pricing_from_sensitivity(sens, dict(inputs), entry.module, stat_to_key=_map(entry.id, "cubes"),
                                                     sub_stat_pct_lines=_map(entry.id, "cubes_sub_stat_pct"))
            self.pricing_builds += 1
            self.pricing.put(key, pricing)
            return pricing


def _map(class_id, feature):
    return (STAT_TO_KEY_BY_CLASS.get(class_id) or {}).get(feature)


def _crit_facts(entry, clean):
    """Live crit-rate total (Inputs + artifact bucket) and the Ring of Cycles / Book of Ancient flags: the cap rule of Critical Rate lines (CLAUDE.md item 13)."""
    model_fn = getattr(entry.module, "model", None)
    if model_fn is None:
        return {"crit_rate_total": float(clean.get("crit_rate") or 0), "ring_of_cycles_equipped": False, "book_of_ancient_equipped": False}
    m = model_fn(dict(clean))
    eq = getattr(m, "eq", {}) or {}
    return {"crit_rate_total": float(getattr(m, "crit_rate_total", m.crit_rate)), "ring_of_cycles_equipped": "ring_of_cycles" in eq, "book_of_ancient_equipped": "book_of_ancient" in eq}


# ----------------------------------------------------------------------------------------------------------------------------------------------
# The three computations (pure given a pricing; what the endpoints run)
# ----------------------------------------------------------------------------------------------------------------------------------------------
def companion_pct(gear):
    return cubes.companion_lines_pct(gear)


def cubes_row_key(class_id, clean, gear, i):
    """Cache key of ONE gear row's result: the inputs, the gear's total summoning-time % (it moves the pricing's b0), the row's own state and the summoning time on
    the OTHER rows (the only cross-row dependency).  Rows are cached one by one, so recalculating after editing one slot hits the cache for every other slot and a
    slot-by-slot request series shares work with a full call."""
    return cache_key("cubes-row", class_id, clean, companion_pct(gear), gear[i], cubes.CubeModel.row_companion_base(gear[i], gear))


def cubes_lookup(cache, class_id, clean, gear, only):
    """``({row index: cached entry}, [row indices still to compute])``."""
    found, missing = {}, []
    for i in only:
        hit = cache.get(cubes_row_key(class_id, clean, gear, i))
        if hit is None:
            missing.append(i)
        else:
            found[i] = hit
    return found, missing


def run_cubes(service, entry, clean, gear, indices, cache=None, class_id=None):
    """Compute the gear rows ``indices`` (``engine.cubes.recommend(..., only=...)``) and, with a ``cache``, store each row's entry
    ``{"row", "baseline_total", "backend", "notes"}``.  Returns ``{row index: entry}``."""
    pct = companion_pct(gear)
    pricing = service.cubes_pricing(entry, clean, pct)
    model = cubes.CubeModel(pricing)
    rows = cubes.recommend(gear, pricing, only=set(indices), model=model, sort=False)     # gear order = ascending index
    notes = sorted(model.notes)
    out = {}
    for i, row in zip(sorted(indices), rows):
        out[i] = {"row": row, "baseline_total": pricing.baseline_dps, "backend": model.backend, "notes": notes}
        if cache is not None:
            cache.put(cubes_row_key(class_id or entry.id, clean, gear, i), out[i])
    return out


def cubes_payload(class_id, entries):
    """The response of ``POST .../cubes`` from ``{row index: entry}``: rows in the script's CSV order (Potential first, then Bonus Potential, each by smallest N)."""
    order = {"Potential": 0, "Bonus Potential": 1}
    rows = [entries[i]["row"] for i in sorted(entries)]
    rows.sort(key=lambda r: (order.get(r["potential_type"], 2), r["smallest_n"] if r["smallest_n"] is not None else float("inf")))
    first = next(iter(entries.values()))
    return {"class_id": class_id, "baseline_total": first["baseline_total"], "milestones": list(cubes.CUBE_MILESTONES), "csv_columns": list(cubes.CSV_COLUMNS),
            "backend": first["backend"], "rows": rows, "notes": sorted({n for e in entries.values() for n in e["notes"]})}


def run_equipment(service, entry, clean, current, new):
    ctx = service.rates_context(entry, clean)
    total = ctx["total_dps"]
    if not total or total <= 0:
        raise ValueError("Total DPS is 0")
    out = equipment.compare(current, new, ctx["rates"], total, ctx["crit_rate_total"], ctx["ring_of_cycles_equipped"], ctx["book_of_ancient_equipped"],
                            stat_to_key=_map(entry.id, "equipment"))
    capped = ctx["crit_rate_total"] >= 100 and not ctx["ring_of_cycles_equipped"] and not ctx["book_of_ancient_equipped"]
    rbs = equipment.stat_rates(ctx["rates"], ctx["crit_rate_total"], ctx["ring_of_cycles_equipped"], ctx["book_of_ancient_equipped"], _map(entry.id, "equipment"))
    return dict(out, class_id=entry.id, baseline_total=total, crit_rate_total=ctx["crit_rate_total"], crit_priced_as_crit_damage=capped, rate_by_stat=rbs)


def run_potentials(service, entry, clean, state):
    ctx = service.rates_context(entry, clean)
    total = ctx["total_dps"]
    if not total or total <= 0:
        raise ValueError("Total DPS is 0")
    slots = [s["key"] for s in (clean.get("artifacts") or []) if s.get("key") and s["key"] != "(none)"]
    state = {k: dict(v) for k, v in state.items()}
    for s in clean.get("artifacts") or []:                    # an equipped artifact's Star Level is its slot's (the equip slot picker carries it on the web)
        art = _artifact_id(s.get("key"))
        if art and art in state and "star" not in state[art]:
            state[art]["star"] = s.get("star")
        elif art and art not in state:
            state[art] = {"star": s.get("star"), "lines": []}
    rows = potentials.potential_table(state, ctx["rates"], total, slots, stat_to_key=_map(entry.id, "potentials"))
    return {"class_id": entry.id, "baseline_total": total, "rows": rows}


def _artifact_id(key):
    if not key:
        return None
    if key in artifact_data.ARTIFACT_LABELS:
        return key
    low = str(key).casefold()
    return next((k for k, label in artifact_data.ARTIFACT_LABELS.items() if label.casefold() == low), None)
