"""Players have never seen the old Excel calculators or our internals: no schema label / help / group string may use that vocabulary.

Runs over every class the API serves (published ones, plus the unpublished ones when ``MSI_INCLUDE_UNPUBLISHED=1``, which ``tests/run_all.py`` and
``api/tests/conftest.py`` set).  Case-insensitive WORD match, so "modelled" or "sheets of paper" style words that merely contain a listed word do not
trip it; a legitimate game term that collides goes into ``WHITELIST`` (a field key -> words allowed in its text) with a comment saying why."""
import re

import pytest

from api import registry as api_registry

FORBIDDEN = ["excel", "workbook", "workbooks", "sheet", "sheets", "inputs sheet", "artifactsinput", "potentialcubes", "spreadsheet", "spreadsheets",
             "engine", "model", "models", "golden", "sensitivity", "snapshot", "verify script"]
WHITELIST: dict[str, set[str]] = {}          # field key -> words allowed there (none needed today)

_PATTERN = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(re.escape(w) for w in sorted(FORBIDDEN, key=len, reverse=True)) + r")(?![A-Za-z0-9])", re.IGNORECASE)
CLASS_IDS = list(api_registry.discover())


def _strings(field):
    for part in ("label", "help", "group"):
        if isinstance(field.get(part), str):
            yield part, field[part]
    for opt in field.get("options") or []:
        if isinstance(opt, str):
            yield "option", opt


def test_there_are_classes():
    assert CLASS_IDS


def test_the_word_list_matches_what_it_should():
    assert _PATTERN.search("Like the workbook's ArtifactsInput sheet")
    assert _PATTERN.search("the MODEL averages min and max")
    assert _PATTERN.search("a Sensitivity run")
    assert not _PATTERN.search("Slots are modelled per content type")      # a longer word is not a hit
    assert not _PATTERN.search("Defense Penetration in %, 0-100")


@pytest.mark.parametrize("cid", CLASS_IDS)
def test_schema_text_has_no_spreadsheet_or_internals_vocabulary(cid):
    bad = []
    for f in api_registry.discover()[cid].schema["fields"]:
        for part, text in _strings(f):
            for m in _PATTERN.finditer(text):
                if m.group(1).lower() not in WHITELIST.get(f["key"], set()):
                    bad.append(f"{cid}/{f['key']} {part}: {m.group(1)!r} in {text!r}")
    assert not bad, "\n".join(bad)
