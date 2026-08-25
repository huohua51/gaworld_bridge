"""Parse artifact SPEC_VERSION and assign a locatable first_error."""

from __future__ import annotations

import ast
import re
from pathlib import Path


def parse_artifact_spec_version(artifact_path: str | None) -> str | None:
    if not artifact_path or not Path(artifact_path).is_file():
        return None
    text = Path(artifact_path).read_text(encoding="utf-8", errors="replace")
    match = re.search(r"""^\s*SPEC_VERSION\s*=\s*['\"]([^'\"]+)['\"]""", text, re.M)
    if match:
        return match.group(1).strip()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "SPEC_VERSION":
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        return node.value.value
    return None


def first_error(
    *,
    track: str,
    variant: str,
    expected_version: str,
    revision_emitted: bool,
    revision_ok: bool,
    delivered_version: str | None,
    input_spec_version: str | None,
    artifact_spec_version: str | None,
    artifact_exists: bool,
    adapter_ok: bool,
    target_correct: bool,
    other_version_also_passes: bool,
    absorbed: bool,
    oracle_first_error: str | None,
) -> str:
    if track == "pipeline" and variant == "intervention":
        if not revision_emitted:
            return "revision_not_emitted"
        if not revision_ok:
            return "revision_not_delivered"
        if delivered_version != expected_version:
            return "revision_not_adopted"
    if input_spec_version != expected_version:
        return "stale_brief_used"
    if not artifact_exists:
        return "no_artifact"
    if not adapter_ok:
        return "adapter_failed"
    if artifact_spec_version == "v1" and expected_version == "v2":
        return "artifact_not_reworked"
    if not target_correct:
        return oracle_first_error or "artifact_not_reworked"
    if other_version_also_passes and artifact_spec_version != expected_version:
        return "stale_brief_used"
    if track == "pipeline" and not absorbed:
        return "result_not_absorbed"
    if artifact_spec_version != expected_version:
        return "revision_not_adopted" if expected_version == "v2" else "stale_brief_used"
    return "none"
