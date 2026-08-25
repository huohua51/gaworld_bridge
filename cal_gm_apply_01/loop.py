from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from cal_gm_apply_01.inspect import parse_source
from cal_gm_apply_01.prompts import executor_prompt, rule_review

ExecutorFn = Callable[[str], str]


def run_cell(
    *,
    task: dict[str, Any],
    variant: str,
    instance_id: str,
    out_dir: Path,
    executor_fn: ExecutorFn,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    draft = str(task["draft"])
    review = rule_review(task, variant)
    prompt = executor_prompt(task, variant, draft)
    draft_path = out_dir / "draft_main.py"
    final_path = out_dir / "final_main.py"
    draft_path.write_text(draft if draft.endswith("\n") else draft + "\n", encoding="utf-8")
    (out_dir / "review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    raw_text = executor_fn(prompt) or ""
    (out_dir / "raw.txt").write_text(raw_text, encoding="utf-8")
    after = parse_source(raw_text)
    final_path.write_text(after, encoding="utf-8")
    # Re-read the file so scoring never trusts the in-memory claim.
    disk = final_path.read_text(encoding="utf-8")
    return {
        "instance_id": instance_id,
        "draft": draft,
        "after": disk,
        "raw_text": raw_text,
        "review": review,
        "prompt": prompt,
        "draft_path": str(draft_path),
        "final_path": str(final_path),
        "calls": 1,
        "budget_valid": True,
        "environment_rewrote": False,
        "reviewer_is_rule": True,
    }
