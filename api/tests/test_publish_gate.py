"""The PUBLISH GATE (engine/__init__.py): a class module that exports ``PUBLISHED = False`` is hidden from the API unless ``MSI_INCLUDE_UNPUBLISHED=1``.

Every check injects a throw-away fake class (a temporary directory appended to ``engine.classes.__path__``; nothing is written into the repo) and either runs in-process with
``monkeypatch`` or in a SUBPROCESS with a controlled environment (the way the deployed API sees it: the variable unset).  Fast (a few hundred ms per subprocess)."""
import importlib
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import engine
import engine.classes as classes_pkg
from api import registry
from api.main import create_app
from api.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
ENV_VAR = "MSI_INCLUDE_UNPUBLISHED"

FAKE_SOURCE = textwrap.dedent('''
    {published_line}
    CLASS_NAME = "Fake Gate Class"

    def schema():
        return {{"class_id": "zz_fake_gate", "name": "Fake Gate Class", "fields": [], "content_types": [], "stat_identity": {{"main": "STR", "sub": "DEX"}}}}

    def defaults(content_type=None):
        return {{}}

    def compute(inputs):
        return {{"total_dps": 1.0}}
''')


def shipped_published():
    """The shipped (real) classes whose module is published; the others (classes still under development) are hidden from the API without the variable."""
    return [c for c in engine.CLASSES if engine.is_published(importlib.import_module(f"engine.classes.{c}"))]


def shipped_unpublished():
    return [c for c in engine.CLASSES if c not in shipped_published()]


def write_fake(directory, name, published):
    """``published``: True (explicit), False (unpublished) or None (no attribute at all)."""
    line = "" if published is None else f"PUBLISHED = {published}"
    (Path(directory) / f"{name}.py").write_text(FAKE_SOURCE.format(published_line=line))


@pytest.fixture
def fake_dir(tmp_path, monkeypatch):
    """A tmp directory on ``engine.classes.__path__`` for the duration of the test; the fake modules are removed from sys.modules afterwards."""
    monkeypatch.setattr(classes_pkg, "__path__", list(classes_pkg.__path__) + [str(tmp_path)])
    importlib.invalidate_caches()
    yield tmp_path
    for name in [m for m in sys.modules if m.startswith("engine.classes.zz_fake")]:
        del sys.modules[name]
    importlib.invalidate_caches()


def served(monkeypatch, with_variable):
    if with_variable:
        monkeypatch.setenv(ENV_VAR, "1")
    else:
        monkeypatch.delenv(ENV_VAR, raising=False)
    return sorted(registry.discover())


def test_unpublished_class_is_hidden_without_the_variable_and_listed_with_it(fake_dir, monkeypatch):
    write_fake(fake_dir, "zz_fake_gate", False)
    assert "zz_fake_gate" not in served(monkeypatch, with_variable=False)
    assert "zz_fake_gate" in served(monkeypatch, with_variable=True)


def test_api_answers_404_for_an_unpublished_class_without_the_variable(fake_dir, monkeypatch):
    write_fake(fake_dir, "zz_fake_gate", False)
    monkeypatch.delenv(ENV_VAR, raising=False)
    client = TestClient(create_app(Settings(rate_limit_per_minute=0)))
    ids = [c["id"] for c in client.get("/api/classes").json()["classes"]]
    assert "zz_fake_gate" not in ids and "fp_mage" in ids
    n_hidden = client.get("/api/health").json()["classes"]
    for path in ("schema", "defaults"):
        r = client.get(f"/api/classes/zz_fake_gate/{path}")
        assert r.status_code == 404 and "unknown class" in r.text
    assert client.post("/api/classes/zz_fake_gate/compute", json={}).status_code == 404
    assert client.post("/api/classes/zz_fake_gate/sensitivity", json={}).status_code == 404
    monkeypatch.setenv(ENV_VAR, "1")
    client = TestClient(create_app(Settings(rate_limit_per_minute=0)))
    assert "zz_fake_gate" in [c["id"] for c in client.get("/api/classes").json()["classes"]]
    assert client.get("/api/health").json()["classes"] == n_hidden + len(shipped_unpublished()) + 1
    assert client.get("/api/classes/zz_fake_gate/schema").status_code == 200
    assert client.get("/api/classes/zz_fake_gate/defaults").status_code == 200


def test_published_classes_excludes_the_unpublished_one(fake_dir):
    write_fake(fake_dir, "zz_fake_gate", False)
    write_fake(fake_dir, "zz_fake_explicit", True)
    write_fake(fake_dir, "zz_fake_missing", None)
    published = engine.published_classes()
    assert "zz_fake_gate" not in published
    assert "zz_fake_explicit" in published and "zz_fake_missing" in published          # True and "no attribute" both mean published
    assert published[:len(shipped_published())] == shipped_published()                  # the shipped published classes, in CLASSES order


def test_published_class_is_unaffected_by_the_gate(fake_dir, monkeypatch):
    write_fake(fake_dir, "zz_fake_gate", False)
    for with_var in (False, True):
        ids = served(monkeypatch, with_variable=with_var)
        assert set(shipped_published()) <= set(ids)                                     # every published shipped class is served either way
        assert (set(shipped_unpublished()) <= set(ids)) is with_var                     # classes under development only with the variable
    assert set(engine.published_classes()) >= set(shipped_published())
    assert not set(shipped_unpublished()) & set(engine.published_classes())


def test_variable_values(fake_dir, monkeypatch):
    write_fake(fake_dir, "zz_fake_gate", False)
    for value, expect in (("1", True), ("true", True), ("0", False), ("", False), ("no", False)):
        monkeypatch.setenv(ENV_VAR, value)
        assert ("zz_fake_gate" in registry.discover()) is expect, value


SUBPROCESS_SCRIPT = textwrap.dedent('''
    import json, sys
    sys.path.insert(0, {root!r})
    import engine.classes as pkg
    pkg.__path__.append(sys.argv[1])
    import engine
    from api import registry
    print(json.dumps({{"api": sorted(registry.discover()), "published": engine.published_classes()}}))
''')


def run_registry_subprocess(fake_directory, env_value):
    """Registry + published_classes in a fresh interpreter whose environment has the variable unset (None) or set to ``env_value`` (what the deployed container sees)."""
    import os
    env = {k: v for k, v in os.environ.items() if k != ENV_VAR}
    if env_value is not None:
        env[ENV_VAR] = env_value
    p = subprocess.run([sys.executable, "-c", SUBPROCESS_SCRIPT.format(root=str(ROOT)), str(fake_directory)], env=env, capture_output=True, text=True, timeout=120, cwd=ROOT)
    assert p.returncode == 0, p.stderr[-2000:]
    return json.loads(p.stdout.strip().splitlines()[-1])


def test_deployed_api_without_the_variable_never_serves_an_unpublished_class(tmp_path):
    """The Docker image ships engine/ unchanged; the variable is unset there, so an unpublished module is inert."""
    write_fake(tmp_path, "zz_fake_gate", False)
    write_fake(tmp_path, "zz_fake_missing", None)
    out = run_registry_subprocess(tmp_path, None)
    assert "zz_fake_gate" not in out["api"] and "zz_fake_gate" not in out["published"]
    assert "zz_fake_missing" in out["api"] and "zz_fake_missing" in out["published"]
    assert set(shipped_published()) <= set(out["api"]) and not set(shipped_unpublished()) & set(out["api"])
    with_var = run_registry_subprocess(tmp_path, "1")
    assert "zz_fake_gate" in with_var["api"]                                            # served only when asked for ...
    assert "zz_fake_gate" not in with_var["published"]                                  # ... and published_classes() ignores the variable
    assert sorted(set(with_var["api"]) - {"zz_fake_gate"} - set(shipped_unpublished())) == sorted(out["api"])
    assert set(shipped_unpublished()) <= set(with_var["api"])


def test_import_engine_stays_cheap():
    """``import engine`` is stdlib-only and loads no class module / no third-party package (the gate adds importlib + pkgutil only)."""
    p = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, %r); import engine; "
                        "bad = [m for m in sys.modules if m.startswith(('engine.classes', 'fastapi', 'numpy', 'openpyxl', 'formulas'))]; print(bad)" % str(ROOT)],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0 and p.stdout.strip() == "[]", p.stdout + p.stderr
