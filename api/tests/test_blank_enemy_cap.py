"""A blank / 0 "Max Enemies In Range" typed by the user means "not entered" = uncapped, never "0 enemies are hit" (0 DPS / ZeroDivisionError in normal-only content).
The engine itself keeps the workbook semantics (blank = 0; the goldens pin that), so the rule lives in the API's input validation."""
import importlib

import pytest

import engine
from api.validation import validate_inputs

CLASS_IDS = [getattr(c, "ID", None) or getattr(c, "id", None) or c for c in engine.CLASSES]


def _module(c):
    return c if hasattr(c, "compute") else importlib.import_module(f"engine.classes.{c}")


@pytest.mark.parametrize("content", ["Chapter Hunt", "EXP Dungeon"])
@pytest.mark.parametrize("cls", CLASS_IDS, ids=str)
def test_blank_cap_is_uncapped(cls, content):
    mod = _module(cls)
    schema = mod.schema()
    ref_body = dict(mod.defaults(content), content_type=content)
    ref, errors = validate_inputs(schema, mod.defaults, ref_body)
    assert not errors
    ref_dps = mod.compute(ref)["total_dps"]
    assert ref_dps > 0
    for blank in (None, 0):
        clean, errors = validate_inputs(schema, mod.defaults, dict(ref_body, max_enemies_hit=blank))
        assert not errors
        assert clean["max_enemies_hit"] == ref["max_enemies_hit"]
        assert mod.compute(clean)["total_dps"] == ref_dps
