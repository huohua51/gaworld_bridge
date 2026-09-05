"""Run one platform probe set inside that platform's isolated environment."""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path

MODULES = {
    "GAWorld": "cross_platform.native_boundary_probes_v1.gaworld_probe",
    "YuLan-OneSim": "cross_platform.native_boundary_probes_v1.yulan_probe",
    "AgentSociety2": "cross_platform.native_boundary_probes_v1.agentsociety_probe",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=tuple(MODULES), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    module = importlib.import_module(MODULES[args.platform])
    result = module.run(args.out)
    if result.get("platform") != args.platform:
        raise RuntimeError("worker returned an unexpected platform")
    print(args.out / "probe_result.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
