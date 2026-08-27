#!/usr/bin/env python3
"""Local H1 lab server: human execution, anonymous viewer, blind rating."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from exp_hf_h1_01.anonymize import ROLE_MAP, stimulus_id
from exp_hf_h1_01.extract_stimuli import extract, refresh_human_registry
from exp_hf_h1_01.freeze import write_manifest
from v0_first_batch.paths import BRIDGE_ROOT

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
DEFAULT_OUT = BRIDGE_ROOT / "output" / "exp_hf_h1_01_20260825"
PROTOCOLS = ROOT / "human_protocols"
TASKS = json.loads((PROTOCOLS / "tasks.json").read_text(encoding="utf-8"))
RUBRIC = json.loads((WEB / "rubric.json").read_text(encoding="utf-8"))
RUBRIC_IDS = {str(item["id"]) for item in RUBRIC}
VARIANT = {"A": "control", "B": "intervention"}
MAX_BODY_BYTES = 1_000_000
MAX_TURN_CHARS = 30_000
CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,39}$")

ACTIVE_OUT = DEFAULT_OUT
DISPLAY = ACTIVE_OUT / "stimuli" / "display"
HUMAN = ACTIVE_OUT / "stimuli" / "human"
RATINGS = ACTIVE_OUT / "ratings"
REGISTRY = ACTIVE_OUT / "STIMULUS_REGISTRY.yaml"
ALLOW_OVERWRITE = False


class SubmissionError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def configure_output(out_dir: Path, *, allow_overwrite: bool = False) -> None:
    global ACTIVE_OUT, DISPLAY, HUMAN, RATINGS, REGISTRY, ALLOW_OVERWRITE
    ACTIVE_OUT = Path(out_dir).resolve()
    DISPLAY = ACTIVE_OUT / "stimuli" / "display"
    HUMAN = ACTIVE_OUT / "stimuli" / "human"
    RATINGS = ACTIVE_OUT / "ratings"
    REGISTRY = ACTIVE_OUT / "STIMULUS_REGISTRY.yaml"
    ALLOW_OVERWRITE = allow_overwrite


def _reported_path(path: Path) -> str:
    """Prefer a repository-relative path, but support isolated pilot dirs."""

    try:
        return str(path.relative_to(BRIDGE_ROOT))
    except ValueError:
        return str(path)


def _task_spec(construct: str, task_id: str) -> dict[str, Any]:
    return next(
        (item for item in TASKS.get(construct, []) if item.get("task_id") == task_id),
        {},
    )


def _expected_turns(construct: str, code: str) -> list[tuple[str, str, str]]:
    if construct == "T3":
        return [
            ("起草人", "produce", "公开任务说明与当前草稿要求"),
            ("审核员", "decide", "草稿与本轮审核可见标准"),
            ("执行人", "apply", "草稿与审核意见"),
        ]
    if construct == "I1":
        return [
            ("观察员", "report", "两个来源的现场报告"),
            ("核验员", "verify", "原始报告 + 私有可信来源表"),
            ("调度员", "act", "已核实状态与动作规则"),
        ]
    turns = [
        ("执行者甲", "produce", "第一步材料"),
        ("执行者甲", "checkpoint", "已完成第一步"),
        ("协调员", "handoff", "检查点"),
    ]
    if code == "B":
        turns.append(("执行者甲", "unavailable", "现场状态"))
    successor = "执行者乙" if code == "B" else "执行者甲"
    turns.extend(
        [
            (successor, "resume", "检查点与接替指令"),
            (successor, "produce", "当前步骤材料"),
            (successor, "produce", "最后一步材料"),
        ]
    )
    return turns


def _validate_json_bodies(construct: str, turns: list[dict[str, Any]]) -> None:
    for index, turn in enumerate(turns):
        if construct == "T3" and turn["kind"] != "decide":
            continue
        if turn["kind"] == "unavailable":
            continue
        try:
            parsed = json.loads(turn["body"])
        except json.JSONDecodeError as exc:
            raise SubmissionError(f"turn_{index + 1}_invalid_json") from exc
        if construct == "I1" and turn["kind"] == "report":
            if not isinstance(parsed, list) or len(parsed) != 2:
                raise SubmissionError("observer_must_submit_two_signals")
        elif not isinstance(parsed, dict):
            raise SubmissionError(f"turn_{index + 1}_must_be_object")
        if (
            construct == "T3"
            and turn["kind"] == "decide"
            and parsed.get("decision") not in {"keep", "update"}
        ):
            raise SubmissionError("review_decision_invalid")
        if construct == "I1" and turn["kind"] == "verify":
            required = {"verified_state", "source_id", "state_version"}
            if set(parsed) != required or not all(
                str(parsed[key]).strip() for key in required
            ):
                raise SubmissionError("verification_contract_invalid")
        if construct == "I1" and turn["kind"] == "act":
            required = {"action", "value", "adopted_state_version"}
            if set(parsed) != required or not all(
                str(parsed[key]).strip() for key in required
            ):
                raise SubmissionError("action_contract_invalid")


def build_human_payload(body: dict[str, Any]) -> dict[str, Any]:
    """Validate one browser submission and return its server-owned trace."""

    construct = str(body.get("construct") or "")
    task_id = str(body.get("task_id") or "")
    code = str(body.get("variant_code") or "")
    variant = VARIANT.get(code)
    spec = _task_spec(construct, task_id)
    if construct not in ROLE_MAP or not spec or not variant:
        raise SubmissionError("bad_slot")
    if body.get("consent_confirmed") is not True:
        raise SubmissionError("consent_required")
    collection_mode = str(body.get("collection_mode") or "")
    if collection_mode not in {"solo_pilot", "three_person_team"}:
        raise SubmissionError("collection_mode_invalid")
    team_code = str(body.get("team_code") or "").strip()
    session_code = str(body.get("session_code") or "").strip()
    if not CODE_RE.fullmatch(team_code) or not CODE_RE.fullmatch(session_code):
        raise SubmissionError("coded_ids_required")
    expected_roles = list(ROLE_MAP[construct].values())
    role_assignments = body.get("role_assignments") or {}
    if set(role_assignments) != set(expected_roles):
        raise SubmissionError("role_assignments_incomplete")
    participant_codes = [
        str(role_assignments[role] or "").strip() for role in expected_roles
    ]
    if not all(CODE_RE.fullmatch(value) for value in participant_codes):
        raise SubmissionError("participant_codes_invalid")
    if collection_mode == "three_person_team" and len(set(participant_codes)) != 3:
        raise SubmissionError("team_mode_requires_three_unique_codes")

    expected_turns = _expected_turns(construct, code)
    received_turns = body.get("turns") or []
    if not isinstance(received_turns, list) or len(received_turns) != len(
        expected_turns
    ):
        raise SubmissionError("turn_count_invalid")
    turns = []
    for index, (received, expected) in enumerate(
        zip(received_turns, expected_turns)
    ):
        if not isinstance(received, dict):
            raise SubmissionError(f"turn_{index + 1}_invalid")
        role, kind, visible = expected
        if received.get("role") != role or received.get("kind") != kind:
            raise SubmissionError(f"turn_{index + 1}_role_or_kind_invalid")
        turn_body = str(received.get("body") or "").strip()
        if not turn_body or len(turn_body) > MAX_TURN_CHARS:
            raise SubmissionError(f"turn_{index + 1}_body_invalid")
        turns.append(
            {
                "t": index + 1,
                "role": role,
                "kind": kind,
                "body": turn_body,
                "visible_to_role": visible,
            }
        )
    _validate_json_bodies(construct, turns)
    notes = str(body.get("protocol_deviations") or "").strip()
    if len(notes) > 2_000:
        raise SubmissionError("protocol_deviations_too_long")
    duration_ms = body.get("duration_ms")
    if (
        not isinstance(duration_ms, int)
        or duration_ms < 0
        or duration_ms > 8 * 60 * 60 * 1000
    ):
        raise SubmissionError("duration_invalid")
    started_at = str(body.get("started_at") or "").strip()
    try:
        datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SubmissionError("started_at_invalid") from exc

    sid = stimulus_id(construct, task_id, variant)
    return {
        "stimulus_id": f"{sid}-human",
        "pairs_with": sid,
        "construct": construct,
        "task_id": task_id,
        "task_label": spec["label"],
        "variant": variant,
        "variant_code": code,
        "roles": expected_roles,
        "turns": turns,
        "source_kind": "human",
        "h1_role": "development_stimulus",
        "status": "collected",
        "trace_contract_valid": True,
        "collection": {
            "collection_mode": collection_mode,
            "team_code": team_code,
            "session_code": session_code,
            "role_assignments": dict(role_assignments),
            "started_at_client": started_at,
            "duration_ms": duration_ms,
            "protocol_deviations": notes,
            "consent_confirmed": True,
        },
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def validate_rating(
    body: dict[str, Any], allowed_stimuli: set[str]
) -> tuple[str, str, dict[str, int]]:
    sid = str(body.get("stimulus_id") or "")
    rater = str(body.get("rater_id") or "").strip()
    scores = body.get("scores") or {}
    if sid not in allowed_stimuli:
        raise SubmissionError("unknown_stimulus")
    if not CODE_RE.fullmatch(rater):
        raise SubmissionError("coded_rater_id_required")
    if set(scores) != RUBRIC_IDS:
        raise SubmissionError("incomplete_scores")
    normalized = {}
    for key, value in scores.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 1 <= value <= 7
        ):
            raise SubmissionError("score_out_of_range")
        normalized[str(key)] = value
    return sid, rater, normalized


def _registry_payload() -> dict[str, Any]:
    if not REGISTRY.is_file():
        return {
            "cells": [],
            "n_agent": 0,
            "n_human_collected": 0,
            "n_human_slots": 18,
        }
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or {}


def _display_index() -> dict[str, Any]:
    path = DISPLAY / "index.json"
    if not path.is_file():
        return {
            "stimuli": [],
            "n_agent": 0,
            "n_human_collected": 0,
            "n_human_slots": 18,
        }
    return json.loads(path.read_text(encoding="utf-8"))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        print(self.address_string(), fmt % args, flush=True)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/api/stimuli", "/api/status"}:
            self._send_json(_display_index())
            return
        if parsed.path == "/api/human-slots":
            registry = _registry_payload()
            self._send_json(
                {
                    "n_human_collected": int(
                        registry.get("n_human_collected") or 0
                    ),
                    "n_human_slots": int(registry.get("n_human_slots") or 18),
                    "slots": [
                        {
                            "construct": cell.get("construct"),
                            "task_id": cell.get("task_id"),
                            "variant_code": cell.get("variant_code"),
                            "human_status": cell.get("human_status"),
                        }
                        for cell in registry.get("cells") or []
                    ],
                }
            )
            return
        if parsed.path.startswith("/api/display/"):
            sid = parsed.path.rsplit("/", 1)[-1]
            allowed = set(_display_index().get("stimuli") or [])
            path = DISPLAY / f"{sid}.json"
            if sid not in allowed or not path.is_file():
                self._send_json({"error": "missing"}, 404)
                return
            self._send_json(json.loads(path.read_text(encoding="utf-8")))
            return
        if parsed.path == "/human-protocols/tasks.json":
            self._send_bytes(
                (PROTOCOLS / "tasks.json").read_bytes(),
                "application/json; charset=utf-8",
            )
            return
        protocol_match = re.fullmatch(
            r"/human-protocols/(t3|i1|l1)\.md", parsed.path
        )
        if protocol_match:
            self._send_bytes(
                (PROTOCOLS / f"{protocol_match.group(1)}.md").read_bytes(),
                "text/markdown; charset=utf-8",
            )
            return
        super().do_GET()

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._send_json({"error": "bad_content_length"}, 400)
            return
        if length <= 0 or length > MAX_BODY_BYTES:
            self._send_json({"error": "body_size_invalid"}, 413)
            return
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json({"error": "invalid_json"}, 400)
            return
        if not isinstance(body, dict):
            self._send_json({"error": "object_required"}, 400)
            return
        parsed = urlparse(self.path)
        if parsed.path == "/api/human-trace":
            self._save_human(body)
            return
        if parsed.path == "/api/rating":
            self._save_rating(body)
            return
        self._send_json({"error": "unknown"}, 404)

    def _save_human(self, body: dict[str, Any]) -> None:
        try:
            payload = build_human_payload(body)
        except SubmissionError as exc:
            self._send_json({"error": exc.code}, 400)
            return
        HUMAN.mkdir(parents=True, exist_ok=True)
        path = HUMAN / f"{payload['stimulus_id']}.json"
        if path.is_file() and not ALLOW_OVERWRITE:
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing = {}
            if existing.get("status") == "collected":
                self._send_json({"error": "slot_already_collected"}, 409)
                return
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        registry = refresh_human_registry(ACTIVE_OUT)
        self._send_json(
            {
                "ok": True,
                "path": _reported_path(path),
                "n_human_collected": registry["n_human_collected"],
                "n_human_slots": registry["n_human_slots"],
            }
        )

    def _save_rating(self, body: dict[str, Any]) -> None:
        allowed = set(_display_index().get("stimuli") or [])
        try:
            sid, rater, scores = validate_rating(body, allowed)
        except SubmissionError as exc:
            self._send_json({"error": exc.code}, 400)
            return
        RATINGS.mkdir(parents=True, exist_ok=True)
        if any(RATINGS.glob(f"{sid}_{rater}_*.json")):
            self._send_json({"error": "duplicate_rating"}, 409)
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = RATINGS / f"{sid}_{rater}_{stamp}.json"
        payload = {
            "stimulus_id": sid,
            "rater_id": rater,
            "scores": scores,
            "comment": str(body.get("comment") or "")[:2_000],
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "h1_formal_score": None,
            "pilot": True,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self._send_json({"ok": True, "path": _reported_path(path)})

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_bytes(self, raw: bytes, ctype: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--allow-overwrite", action="store_true")
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        parser.error(
            "H1 pilot server is local-only; host must be 127.0.0.1 or localhost"
        )
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    configure_output(args.out, allow_overwrite=args.allow_overwrite)
    extract(ACTIVE_OUT)
    if not (ACTIVE_OUT / "FREEZE.yaml").is_file():
        write_manifest(ACTIVE_OUT)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"EXP-HF-H1-01 http://{args.host}:{args.port}", flush=True)
    print(f"data_dir={ACTIVE_OUT}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
