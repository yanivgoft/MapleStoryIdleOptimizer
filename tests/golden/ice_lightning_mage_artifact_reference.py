#!/usr/bin/env python3
"""Ground truth for the artifact golden set: evaluates the Ice/Lightning Mage WORKBOOK (with artifacts equipped) with the ``formulas`` package (shared body:
``artifact_reference_common.py``; one evaluation takes minutes and several GB: run them ONE AT A TIME, ``--run-all`` does).

    python3 tests/golden/ice_lightning_mage_artifact_reference.py --list
    python3 tests/golden/ice_lightning_mage_artifact_reference.py --case "G1/World Boss/blaze"            # one evaluation -> $ARTIFACT_REF_SCRATCH/results/<id>.json
    python3 tests/golden/ice_lightning_mage_artifact_reference.py --run-all                                # every missing case, sequential subprocesses
    python3 tests/golden/ice_lightning_mage_artifact_reference.py --assemble                               # results -> tests/golden/ice_lightning_mage_artifacts_golden.json

The scratch dir is /tmp/ilm_art/engine (scratch .xlsx files are deleted right after each run).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import artifact_reference_common as ARC  # noqa: E402

REF = ARC.ArtifactReference("ice_lightning_mage", "Ice-Lightning-Mage", "ice_lightning_mage_artifact_cases", "/tmp/ilm_art/engine", 68, "CFGHIJKLMNOQRSTUVWXY", ARC.rows_summary_row, __file__)

if __name__ == "__main__":
    REF.main()
