"""The public face every class module (``engine/classes/<class>.py``) exposes besides ``compute`` / ``model``: ``fields()``, ``schema()``,
``defaults()`` and ``artifact_schema()``.  A class module calls ``make(...)`` once with its identity and main-stat fields; the field list is the
common one (``schema.common_fields``) plus, optionally, class-specific extra fields."""
from . import companion as comp_mod
from . import content as content_mod
from . import schema as schema_mod
from .. import artifacts as art_mod
from ..data import artifacts as AD

# Night Lord / Shadower: a counterattack skill reads it (inserted right after Max Enemies In Range, the workbook's row order)
INCOMING_HIT_RATE = schema_mod.field(
    "incoming_hit_rate", "Incoming Hit Rate", "Additional bonuses", "float", "hits/s", 1,
    help="Hits per second you take (user-estimated); feeds Shadow Shifter's counterattack only.")


def artifact_schema():
    """What a UI needs for the artifact slots: dropdown names (+ '(none)'), star options, the default star by rank, per-artifact info.
    ``inputs["artifacts"]`` = ``[{"key": <id>, "star": 0..5 | None}, ...]`` (equipped slots, <= max_slots); the star is the artifact's own
    Star Level ("Not Unlocked" / None reads as star 0, as in the workbook)."""
    return dict(
        modelled=True, max_slots=art_mod.MAX_SLOTS, none_label=art_mod.NONE_LABEL, star_options=list(art_mod.STAR_OPTIONS),
        slot_options=[art_mod.NONE_LABEL] + list(AD.ARTIFACT_LABELS.values()),
        artifacts=[dict(key=k, name=label, rank=AD.ARTIFACT_RANK[k], default_star=art_mod.default_star(k),
                        effect=art_mod.effect_kind(k), no_dps_effect=k in AD.ARTIFACT_NO_DPS_EFFECT, reason=AD.ARTIFACT_NO_DPS_EFFECT.get(k))
                   for k, label in AD.ARTIFACT_LABELS.items()],
    )


def make(class_id, class_name, stat_identity, main_fields, data, extra_fields=(), hooks=None, row_order=None):
    """(fields, schema, defaults) of one class.  ``data`` = its ``engine/data/<class>.py`` (``SKILL_NAMES``, ``DPS_ROW_ORDER`` unless ``row_order``
    is given); ``extra_fields`` = fields inserted right after Max Enemies In Range; ``hooks`` = the artifact hooks the class reports (Night Lord /
    Shadower)."""
    order = data.DPS_ROW_ORDER if row_order is None else row_order

    def fields():
        out = schema_mod.common_fields(main_fields, comp_mod.COMPANION_CHOICES)
        for extra in extra_fields:
            i = next(i for i, f in enumerate(out) if f["key"] == "max_enemies_hit")      # the workbook's row order: right after Max Enemies In Range
            out.insert(i + 1, dict(extra))
        return out

    def schema():
        """Everything a UI needs to render the input form: the field list (see engine/common/schema.py) and the dropdown sources."""
        out = dict(class_id=class_id, name=class_name, stat_identity=stat_identity, content_types=list(content_mod.CONTENT_TYPES),
                   companions=list(comp_mod.COMPANIONS_ORDER), fields=fields(), dps_rows=[(k, data.SKILL_NAMES[k]) for k in order],
                   artifacts_modelled=True, artifacts=artifact_schema())
        if hooks is not None:
            out["hooks"] = dict(hooks)
        return out

    def defaults(content_type="Chapter Boss"):
        """Workbook default inputs resolved for ``content_type`` (fields that do not apply to it are None)."""
        return schema_mod.default_inputs(fields(), content_type)

    return fields, schema, defaults
