"""Input validation driven by a class's ``schema()``: types, enum membership, applicability and numeric ranges, with field-level messages.

``validate_inputs(schema, defaults_for, body)`` returns ``(clean_inputs, errors)``; ``errors`` is a list of ``{"field", "message"}`` (empty =
valid).  Rules:

* ``content_type`` first (enum from the schema); the rest of the defaults come from ``defaults_for(content_type)``.
* a key missing from the body takes the workbook default for that content type; ``None`` is allowed for numeric fields (reads as 0, like a
  blank cell) unless the schema's ``min`` is above 0 (level, PvP fight length); fields that do not apply to the content type are forced to ``None``; computed fields are ignored.
* unknown keys are rejected (typos must not silently do nothing); ``artifacts`` is accepted when the class models artifacts (others get a clear 422).
* ``typed_includes_artifacts`` (optional boolean, not a schema field like ``artifacts``): the typed stats already contain the equipped artifacts' effects (the values of
  the in-game preset page).  The API fills it TRUE when a request omits it; ``false`` asks for the workbooks' convention (artifacts added on top of the typed values).
* numeric ranges are the schema's own ``min`` / ``max``.
"""
import math
import re

TYPED_FLAG = "typed_includes_artifacts"       # engine.typed_artifacts.FLAG (not imported: the validation module stays engine-free)
CHAPTER_STAGE_RE = re.compile(r"^\d{1,3}(-\d{1,2})?$")
# Ranges come from the schema (``field["min"]`` / ``field["max"]``, engine/common/schema.py).  A schema snapshot without them (older engine)
# falls back to these permissive limits.
FALLBACK_RANGE = (0, 1e13)


def _range(field):
    lo, hi = field.get("min"), field.get("max")
    return (FALLBACK_RANGE[0] if lo is None else lo, FALLBACK_RANGE[1] if hi is None else hi)


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check_field(field, v):
    """(clean value, error message or None) for one non-None value."""
    typ, key = field["type"], field["key"]
    if typ == "enum":
        opts = field["options"] or []
        if not isinstance(v, str) or v not in opts:
            return None, f"must be one of: {', '.join(opts)}"
        return v, None
    if typ == "text":
        if key == "chapter_stage" and _is_number(v) and float(v).is_integer() and v >= 0:
            v = str(int(v))                            # a bare stage / chapter number may arrive as a JSON number
        if not isinstance(v, str):
            return None, "must be text"
        v = v.strip()
        if key == "chapter_stage":
            if not CHAPTER_STAGE_RE.match(v):
                return None, "use 'chapter-substage' (e.g. 28-9) or a plain number (e.g. 37)"
        elif len(v) > 64:
            return None, "too long (max 64 characters)"
        return v, None
    # numeric
    if not _is_number(v):
        return None, "must be a number"
    if isinstance(v, float) and not math.isfinite(v):
        return None, "must be a finite number"
    lo, hi = _range(field)
    if typ == "int":
        if isinstance(v, float):
            if v != int(v):
                return None, "must be a whole number"
            v = int(v)
    if v < lo or v > hi:
        return None, f"must be between {lo:g} and {hi:g}"
    return v, None


def _validate_artifacts(art_schema, value):
    """Accepted: list (<= max_slots) of ``{"key": <artifact id | display name | '(none)'>, "star": 0..5 | 'Not Unlocked' | None}``."""
    errors = []
    if not isinstance(value, list):
        return None, [("artifacts", "must be a list of {key, star} slots")]
    if len(value) > art_schema["max_slots"]:
        return None, [("artifacts", f"at most {art_schema['max_slots']} slots")]
    ids = {a["key"] for a in art_schema["artifacts"]}
    names = {a["name"] for a in art_schema["artifacts"]}
    stars = [s for s in art_schema["star_options"]]
    clean = []
    for i, slot in enumerate(value):
        name = f"artifacts[{i}]"
        if not isinstance(slot, dict):
            errors.append((name, "must be an object {key, star}"))
            continue
        extra = set(slot) - {"key", "star"}
        if extra:
            errors.append((name, f"unknown keys: {', '.join(sorted(extra))}"))
            continue
        key, star = slot.get("key"), slot.get("star")
        if key not in ids and key not in names and key not in (None, "", art_schema["none_label"]):
            errors.append((f"{name}.key", "unknown artifact"))
            continue
        if star is not None and not (star in stars and not isinstance(star, bool)):
            errors.append((f"{name}.star", "must be 0-5 or 'Not Unlocked'"))
            continue
        clean.append({"key": key, "star": star})
    return clean, errors


def validate_inputs(schema, defaults_for, body):
    errors = []
    if not isinstance(body, dict):
        return None, [{"field": "", "message": "request body must be a JSON object of inputs"}]
    fields = {f["key"]: f for f in schema["fields"]}
    art_schema = schema.get("artifacts") if schema.get("artifacts_modelled") else None

    for key in body:
        if key == "artifacts" and not art_schema:
            errors.append({"field": key, "message": "artifacts are not modelled for this class yet"})
        elif key not in fields and key not in ("artifacts", TYPED_FLAG):
            errors.append({"field": key, "message": "unknown field"})
    typed_flag = body.get(TYPED_FLAG, True)
    if not isinstance(typed_flag, bool):
        errors.append({"field": TYPED_FLAG, "message": "must be true or false"})
        typed_flag = True

    ct_field = fields["content_type"]
    ct = body.get("content_type", ct_field["default"])
    ct, msg = _check_field(ct_field, ct) if ct is not None else (None, "is required")
    if msg:
        errors.append({"field": "content_type", "message": msg})
        return None, errors

    defaults = defaults_for(ct)
    clean = {}
    for key, field in fields.items():
        if field["computed"]:
            continue
        if key == "content_type":
            clean[key] = ct
            continue
        applicable = field["applicable"] is None or ct in field["applicable"]
        if not applicable:
            clean[key] = None
            continue
        raw = body.get(key, defaults.get(key))
        if key == "max_enemies_hit" and (raw is None or raw == 0):
            # blank / 0 = "not entered" = uncapped (the engine itself, like the workbook, reads 0 as "0 enemies are hit": 0 DPS in normal-only
            # content, a division by zero in Ice/Lightning Mage and Bishop)
            raw = defaults.get(key)
        if raw is None and field["type"] in ("int", "float") and _range(field)[0] > 0:
            errors.append({"field": key, "message": "is required"})   # a blank would read as 0, which is outside the allowed range
            continue
        if raw is None:
            # blank: numbers read as 0; enum / text fields fall back to the content type's default
            clean[key] = defaults.get(key) if field["type"] in ("enum", "text") else None
            continue
        value, msg = _check_field(field, raw)
        if msg:
            errors.append({"field": key, "message": msg})
        else:
            clean[key] = value

    if art_schema and "artifacts" in body:
        value, art_errors = _validate_artifacts(art_schema, body["artifacts"])
        errors.extend({"field": f, "message": m} for f, m in art_errors)
        if not art_errors:
            clean["artifacts"] = value
    clean[TYPED_FLAG] = typed_flag
    return (clean if not errors else None), errors


# ---- extra keys of POST /api/classes/{id}/sensitivity (everything else in the body is a normal compute input) ----------------------------------
SENSITIVITY_EXTRA_KEYS = ("which", "companion_comparison_level", "artifact_stars", "companion_levels", "companion_potential_lines_pct", "artifact_lines")


def split_sensitivity_body(body):
    """``(compute body without the extra keys, {extra key: raw value})``; a non-dict body is returned unchanged for the compute validator to reject."""
    if not isinstance(body, dict):
        return body, {}
    extras = {k: body[k] for k in SENSITIVITY_EXTRA_KEYS if k in body}
    return {k: v for k, v in body.items() if k not in extras}, extras


def validate_sensitivity_extras(schema, extras, parts):
    """``(clean extras, errors)``: ``which`` (list of ``parts`` names, canonical order, de-duplicated), ``companion_comparison_level`` (whole number
    within the companion level's own bounds), ``artifact_stars`` ({artifact id: 0..5 | 'Not Unlocked' | None}, classes that model artifacts), ``companion_levels`` ({companion name: 0..18}, 0 = not
    unlocked) and ``companion_potential_lines_pct`` (>= 0: summoning-time % of boots lines already inside the Inputs value).  ``artifact_lines`` is checked by the
    caller (``features.validate_artifact_lines``: it needs the engine's potential tables)."""
    clean, errors = {}, []
    if "which" in extras:
        w = extras["which"]
        if w is None:
            pass
        elif not isinstance(w, list) or not w or not all(isinstance(x, str) for x in w):
            errors.append({"field": "which", "message": f"must be a non-empty list of: {', '.join(parts)}"})
        else:
            bad = sorted({x for x in w if x not in parts})
            if bad:
                errors.append({"field": "which", "message": f"unknown part(s) {', '.join(map(repr, bad))}; choose from: {', '.join(parts)}"})
            else:
                clean["which"] = [p for p in parts if p in w]
    if extras.get("companion_comparison_level") is not None:
        v = extras["companion_comparison_level"]
        field = next((f for f in schema["fields"] if f["key"] == "companion_level"), None)
        lo, hi = (field.get("min") if field else None), (field.get("max") if field else None)
        lo, hi = (1 if not lo else max(1, lo)), (100 if hi is None else hi)
        if not _is_number(v) or (isinstance(v, float) and v != int(v)):
            errors.append({"field": "companion_comparison_level", "message": "must be a whole number"})
        elif not lo <= v <= hi:
            errors.append({"field": "companion_comparison_level", "message": f"must be between {lo:g} and {hi:g}"})
        else:
            clean["companion_comparison_level"] = int(v)
    if extras.get("companion_levels") is not None:
        v = extras["companion_levels"]
        names = set(schema.get("companions") or [])
        field = next((f for f in schema["fields"] if f["key"] == "companion_level"), None)
        hi = 18 if not field or field.get("max") is None else field["max"]
        if not isinstance(v, dict):
            errors.append({"field": "companion_levels", "message": "must be an object {companion name: level 0-%g}" % hi})
        else:
            levels, ok = {}, True
            for k, lv in v.items():
                if k not in names:
                    errors.append({"field": f"companion_levels.{k}", "message": "unknown companion"})
                    ok = False
                elif not _is_number(lv) or lv != int(lv) or not 0 <= lv <= hi:
                    errors.append({"field": f"companion_levels.{k}", "message": f"must be a whole number between 0 and {hi:g} (0 = not unlocked)"})
                    ok = False
                else:
                    levels[k] = int(lv)
            if ok:
                clean["companion_levels"] = levels
    if extras.get("companion_potential_lines_pct") is not None:
        v = extras["companion_potential_lines_pct"]
        field = next((f for f in schema["fields"] if f["key"] == "companion_summon_time_increase_pct"), None)
        hi = 10000 if not field or field.get("max") is None else field["max"]
        if not _is_number(v) or not 0 <= v <= hi:
            errors.append({"field": "companion_potential_lines_pct", "message": f"must be a number between 0 and {hi:g}"})
        else:
            clean["companion_potential_lines_pct"] = v
    if extras.get("artifact_stars") is not None:
        v = extras["artifact_stars"]
        art = schema.get("artifacts") if schema.get("artifacts_modelled") else None
        if not art:
            errors.append({"field": "artifact_stars", "message": "artifacts are not modelled for this class yet"})
        elif not isinstance(v, dict):
            errors.append({"field": "artifact_stars", "message": "must be an object {artifact id: star}"})
        else:
            ids = {a["key"] for a in art["artifacts"]}
            stars, ok = {}, True
            for k, s in v.items():
                if k not in ids:
                    errors.append({"field": f"artifact_stars.{k}", "message": "unknown artifact"})
                    ok = False
                elif s is not None and not (s in art["star_options"] and not isinstance(s, bool)):
                    errors.append({"field": f"artifact_stars.{k}", "message": "must be 0-5, 'Not Unlocked' or null"})
                    ok = False
                else:
                    stars[k] = s
            if ok:
                clean["artifact_stars"] = stars
    return clean, errors
