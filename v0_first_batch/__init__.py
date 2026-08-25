"""GAWorld first-batch Workflow-Rubric factory (2026-08-22).

Runs only tasks the current GAWorld code can actually host.
TMS / Collective Efficacy pilots stay planned, not executed.
"""

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
BRIDGE_ROOT = PACKAGE_ROOT.parent
GAWORLD_ROOT = BRIDGE_ROOT.parent / "GAWorld"
