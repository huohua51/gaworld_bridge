from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from cal_gm_change_01.contract import action_contract, parse_json_object

GenerateFn = Callable[[str], str]


def run_cell(
    *,
    task: dict[str, Any],
    variant: str,
    instance_id: str,
    out_dir: Path,
    prompt: str,
    generate_fn: GenerateFn,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_text = generate_fn(prompt) or ""
    parsed = parse_json_object(raw_text)
    action, contract_error = action_contract(parsed)
    (out_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    (out_dir / "raw.txt").write_text(raw_text, encoding="utf-8")
    (out_dir / "parsed.json").write_text(json.dumps(parsed or {}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "action.json").write_text(json.dumps(action, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "instance_id": instance_id,
        "raw_text": raw_text,
        "parsed": parsed or {},
        "action": action,
        "contract_error": contract_error,
        "contract_ok": contract_error == "ok",
        "prompt": prompt,
        "calls": 1,
        "budget_valid": True,
    }
