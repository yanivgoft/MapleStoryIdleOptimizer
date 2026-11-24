"""Test-session setup for api/tests: serve the classes that are still ``PUBLISHED = False`` (the publish gate, engine/__init__.py) so they are tested like every other
class.  ``tests/run_all.py`` exports the same variable to its subprocesses; this ``setdefault`` makes a bare ``pytest api/tests`` behave identically.  The gate itself is
tested in ``test_publish_gate.py`` (subprocesses with a controlled environment)."""
import os

os.environ.setdefault("MSI_INCLUDE_UNPUBLISHED", "1")


# Tests that compare the API with a WORKBOOK-derived golden (the frozen Excel clamps skill levels at 300; the engine's production mode continues the growth curves past 300,
# engine/common/factors.py) are marked ``workbook_golden`` and run in the legacy 300-clamp mode; every other test (engine-native classes, API contract, self-consistency) runs in
# the default extended mode.
import pytest  # noqa: E402

from engine.common import factors  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "workbook_golden: compares with a workbook-derived golden: runs with the legacy 300-clamp of the skill-level growth factors")


@pytest.fixture(autouse=True)
def _legacy_clamp_for_workbook_goldens(request):
    if request.node.get_closest_marker("workbook_golden") is None:
        yield
        return
    with factors.legacy_clamp(True):
        yield
