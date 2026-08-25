"""Run hidden pytest against a CodeAdapter artifact. Oracle stays off-agent."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def score_hidden_tests(artifact_path: str | None, oracle_path: Path) -> dict:
    if not artifact_path or not os.path.isfile(artifact_path):
        return {
            "evaluable": False,
            "passed": False,
            "pass_count": 0,
            "fail_count": 0,
            "returncode": None,
            "stdout_tail": "missing artifact",
            "first_error": "no_artifact",
        }
    tmp = tempfile.mkdtemp(prefix="w1_oracle_")
    try:
        shutil.copy(artifact_path, os.path.join(tmp, "main.py"))
        shutil.copy(str(oracle_path), os.path.join(tmp, "test_oracle.py"))
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "test_oracle.py", "-q", "--tb=line"],
            cwd=tmp,
            capture_output=True,
            text=True,
            timeout=60,
        )
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        passed = proc.returncode == 0
        # pytest -q summary like "4 passed" or "2 failed, 2 passed"
        pass_count = _count_token(out, "passed")
        fail_count = _count_token(out, "failed")
        first = "none" if passed else ("oracle_tests_failed" if "Error" in out or fail_count else "oracle_import_failed")
        if "ModuleNotFoundError" in out or "ImportError" in out or "cannot import name" in out:
            first = "oracle_import_failed"
        return {
            "evaluable": True,
            "passed": passed,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "returncode": proc.returncode,
            "stdout_tail": out[-800:],
            "first_error": first,
        }
    except subprocess.TimeoutExpired:
        return {
            "evaluable": True,
            "passed": False,
            "pass_count": 0,
            "fail_count": 0,
            "returncode": -1,
            "stdout_tail": "pytest timeout",
            "first_error": "oracle_timeout",
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _count_token(text: str, token: str) -> int:
    for part in text.replace(",", " ").split():
        pass
    # Look for patterns "4 passed" / "2 failed"
    import re

    match = re.search(rf"(\d+)\s+{token}", text)
    return int(match.group(1)) if match else 0
