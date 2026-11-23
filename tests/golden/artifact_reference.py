#!/usr/bin/env python3
"""Ground truth for the artifact golden set: evaluates the FP-Mage WORKBOOK (with artifacts equipped) with the ``formulas`` package (shared body:
``artifact_reference_common.py``; one evaluation takes minutes and several GB: run them ONE AT A TIME, ``--run-all`` does).

    python3 tests/golden/artifact_reference.py --list
    python3 tests/golden/artifact_reference.py --case "G1/World Boss/blaze"            # one evaluation -> /tmp/engine_p2/results/<id>.json
    python3 tests/golden/artifact_reference.py --run-all                                # every missing case, sequential subprocesses
    python3 tests/golden/artifact_reference.py --assemble                               # results -> tests/golden/fp_mage_artifacts_golden.json

The scratch dir is /tmp/engine_p2 (scratch .xlsx files are deleted right after each run).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import artifact_reference_common as ARC  # noqa: E402

REF = ARC.ArtifactReference("fp_mage", "FP-Mage", "artifact_cases", "/tmp/engine_p2", 60, "CFGHIJKLMNOQRSUVWXY", ARC.rows_ed_mult, __file__)

if __name__ == "__main__":
    REF.main()
