"""REL1-04 deliberately reuses the frozen REL1-v3 interaction protocol."""

from exp_rel1_03.protocol import run_cell

PROMPT_PROTOCOL = "gaworld-benchmark-rel1-phase-separated-v3"

__all__ = ["PROMPT_PROTOCOL", "run_cell"]
