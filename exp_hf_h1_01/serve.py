#!/usr/bin/env python3
"""Local H1 lab server: human execution, anonymous viewer, blind rating."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from exp_hf_h1_01.anonymize import stimulus_id
from exp_hf_h1_01.freeze import write_manifest
from v0_first_batch.paths import BRIDGE_ROOT

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
OUT = BRIDGE_ROOT / "output" / "exp_hf_h1_01_20260825"
DISPLAY = OUT / "stimuli" / "display"
HUMAN = OUT / "stimuli" / "human"
RATINGS = OUT / "ratings"
PROTOCOLS = ROOT / "human_protocols"

VARIANT = {"A": "control", "B": "intervention"}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        print(self.address_string(), fmt % args, flush=True)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/stimuli":
            path = DISPLAY / "index.json"
            self._send_json(json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"stimuli": []})
            return
        if parsed.path.startswith("/api/display/"):
            sid = parsed.path.rsplit("/", 1)[-1]
            path = DISPLAY / f"{sid}.json"
            if not path.is_file():
                self._send_json({"error": "missing"}, 404)
                return
            self._send_json(json.loads(path.read_text(encoding="utf-8")))
            return
        if parsed.path == "/human-protocols/tasks.json":
            self._send_bytes((PROTOCOLS / "tasks.json").read_bytes(), "application/json")
            return
        super().do_GET()

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        parsed = urlparse(self.path)
        if parsed.path == "/api/human-trace":
            self._save_human(body)
            return
        if parsed.path == "/api/rating":
            self._save_rating(body)
            return
        self._send_json({"error": "unknown"}, 404)

    def _save_human(self, body: dict) -> None:
        construct = body.get("construct")
        task_id = body.get("task_id")
        code = body.get("variant_code")
        variant = VARIANT.get(str(code))
        if construct not in {"T3", "I1", "L1"} or not task_id or not variant:
            self._send_json({"error": "bad_slot"}, 400)
            return
        try:
            sid = stimulus_id(construct, task_id, variant)
        except KeyError:
            self._send_json({"error": "unknown_task"}, 400)
            return
        HUMAN.mkdir(parents=True, exist_ok=True)
        path = HUMAN / f"{sid}-human.json"
        payload = {
            "stimulus_id": f"{sid}-human",
            "pairs_with": sid,
            "construct": construct,
            "task_id": task_id,
            "task_label": body.get("task_label"),
            "variant": variant,
            "variant_code": code,
            "roles": [t.get("role") for t in body.get("turns") or []],
            "turns": body.get("turns") or [],
            "source_kind": "human",
            "h1_role": "development_stimulus",
            "status": "collected",
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._send_json({"ok": True, "path": str(path.relative_to(BRIDGE_ROOT))})

    def _save_rating(self, body: dict) -> None:
        sid = str(body.get("stimulus_id") or "")
        rater = str(body.get("rater_id") or "").strip()
        scores = body.get("scores") or {}
        if not sid or not rater or len(scores) != 12:
            self._send_json({"error": "incomplete"}, 400)
            return
        RATINGS.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = RATINGS / f"{sid}_{rater}_{stamp}.json"
        payload = {
            **body,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "h1_formal_score": None,
            "pilot": True,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._send_json({"ok": True, "path": str(path.relative_to(BRIDGE_ROOT))})

    def _send_json(self, payload: dict, status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
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
    from exp_hf_h1_01.extract_stimuli import extract

    extract()
    write_manifest(OUT)
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("EXP-HF-H1-01 http://127.0.0.1:8765", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
