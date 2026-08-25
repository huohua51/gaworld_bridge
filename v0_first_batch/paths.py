from __future__ import annotations

import sys
from pathlib import Path

BRIDGE_ROOT = Path(__file__).resolve().parent.parent
GAWORLD_ROOT = BRIDGE_ROOT.parent / "GAWorld"


def ensure_import_paths() -> None:
    for root in (str(GAWORLD_ROOT), str(BRIDGE_ROOT)):
        if root not in sys.path:
            sys.path.insert(0, root)
