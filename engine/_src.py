"""Path shim: puts the repo's ``src/`` directory on ``sys.path`` so the engine can import the already pure-Python shared
modules (``companion_kits``, ``companion_python_model``, ``status_timeline``) from their single source of truth instead of
copying them.  Importing this module is idempotent.

Only those three modules may be imported through the shim: everything else in ``src/`` (the ``build_*`` / ``verify_*``
scripts) pulls in openpyxl / formulas and must never be imported by the engine.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
DATA_DIR = REPO_ROOT / "data"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
