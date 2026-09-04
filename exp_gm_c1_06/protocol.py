"""C1-06 deliberately reuses the frozen C1-v5 interaction protocol."""

from exp_gm_c1_05.protocol import run_cell

PROMPT_PROTOCOL = "gaworld-benchmark-c1-authoritative-current-spec-v5"

__all__ = ["PROMPT_PROTOCOL", "run_cell"]
