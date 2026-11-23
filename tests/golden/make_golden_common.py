"""Shared body of ``make_golden_<class>.py``: run the original verify script (via ``run_reference_<class>.py``, in ONE subprocess, workbook-free) over a
class's case matrix and freeze its numbers as ``<class>_golden.json`` (the user's real workbook Inputs of ``<class>_real_inputs.json`` are appended when the
file exists, see ``check_<class>_fake.py``).  The golden file is the reference; the engine is tested against it."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def regenerate(class_id, cases_fn, reference=None):
    cs = cases_fn()
    extra = HERE / f"{class_id}_real_inputs.json"          # optional: the user's real workbook Inputs (see check_<class>_fake.py)
    if extra.exists():
        cs += [tuple(c) for c in json.loads(extra.read_text())]
    with tempfile.TemporaryDirectory() as tmp:
        cin, cout = Path(tmp) / "cases.json", Path(tmp) / "out.json"
        cin.write_text(json.dumps(cs))
        # PYTHONHASHSEED=0 is REQUIRED for the classes whose verify script sums trigger rates over a Python `set` / set literal (FP-Mage's Meteor Proc, Night Lord's /
        # Shadower's Toxic Venom: ulp-level noise depending on the hash seed); the engine fixes that summation order (TRIGGERS_* in engine/data/<class>.py) to the one
        # the set has under seed 0.  The other verify scripts have no float sum over a set, but the seed is pinned for all of them.
        env = dict(os.environ, PYTHONHASHSEED="0")
        subprocess.run([sys.executable, str(HERE / (reference or f"run_reference_{class_id}.py")), str(cin), str(cout)], check=True, env=env)
        golden = json.loads(cout.read_text())
    (HERE / f"{class_id}_golden.json").write_text(json.dumps(golden))
    print(f"wrote {len(golden)} golden cases to {class_id}_golden.json")
