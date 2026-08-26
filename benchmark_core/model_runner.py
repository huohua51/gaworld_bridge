"""Budgeted, evidence-first model calls for benchmark pilots."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol


class LiveModelCallBlocked(RuntimeError):
    """Raised before a live provider call when explicit permission is absent."""


class ModelCallBudgetExceeded(RuntimeError):
    """Raised before a call that would exceed the registered global budget."""


@dataclass(frozen=True)
class ModelClientInfo:
    provider: str
    model_version: str
    live: bool


class ModelClient(Protocol):
    info: ModelClientInfo

    def generate(self, prompt: str, *, task: str, agent_id: str | None) -> str: ...


class CallableModelClient:
    """Adapt a deterministic test handler to the model-client protocol."""

    def __init__(
        self,
        handler: Callable[[str, str, str | None], str],
        *,
        provider: str = "fixture",
        model_version: str = "fixture-v1",
        live: bool = False,
    ) -> None:
        self._handler = handler
        self.info = ModelClientInfo(provider, model_version, live)

    def generate(self, prompt: str, *, task: str, agent_id: str | None) -> str:
        return str(self._handler(prompt, task, agent_id))


class GAWorldModelClient:
    """Explicit adapter around GAWorld's configured provider router."""

    def __init__(
        self,
        provider_name: str,
        *,
        temperature: float,
        max_tokens: int | None,
    ) -> None:
        from config import CONFIG
        from llm_providers import LLMRouter

        config = deepcopy(CONFIG)
        llm = config.get("llm") or {}
        providers = llm.get("providers") or {}
        if provider_name not in providers:
            raise ValueError(f"provider is not configured: {provider_name}")
        provider_config = dict(providers[provider_name])
        provider_config["temperature"] = temperature
        if max_tokens is not None:
            provider_config["max_tokens"] = int(max_tokens)
        providers[provider_name] = provider_config
        llm["providers"] = providers
        llm["routing"] = {
            "default": provider_name,
            "tasks": {},
            "agents": {},
            "fallback": [],
        }
        config["llm"] = llm
        self._router = LLMRouter(config)
        self.info = ModelClientInfo(
            provider=provider_name,
            model_version=str(provider_config.get("model") or provider_name),
            live=True,
        )

    def generate(self, prompt: str, *, task: str, agent_id: str | None) -> str:
        return str(self._router.call(prompt, task=task, agent_id=agent_id))


class ModelCallBudget:
    """Thread-safe global call and character budget shared across cells."""

    def __init__(
        self,
        max_calls: int,
        *,
        max_prompt_chars: int = 50_000,
        max_response_chars: int = 20_000,
    ) -> None:
        if max_calls <= 0:
            raise ValueError("max_calls must be positive")
        self.max_calls = int(max_calls)
        self.max_prompt_chars = int(max_prompt_chars)
        self.max_response_chars = int(max_response_chars)
        self._calls_used = 0
        self._prompt_chars = 0
        self._response_chars = 0
        self._lock = threading.RLock()

    def reserve(self, prompt_chars: int) -> int:
        with self._lock:
            if prompt_chars > self.max_prompt_chars:
                raise ModelCallBudgetExceeded(
                    f"prompt_chars={prompt_chars} exceeds per-call limit={self.max_prompt_chars}"
                )
            if self._calls_used >= self.max_calls:
                raise ModelCallBudgetExceeded(
                    f"model calls exhausted: {self._calls_used}/{self.max_calls}"
                )
            self._calls_used += 1
            self._prompt_chars += prompt_chars
            return self._calls_used

    def record_response(self, response_chars: int) -> None:
        with self._lock:
            self._response_chars += int(response_chars)

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "max_calls": self.max_calls,
                "calls_used": self._calls_used,
                "calls_remaining": self.max_calls - self._calls_used,
                "prompt_chars": self._prompt_chars,
                "response_chars": self._response_chars,
                "max_prompt_chars_per_call": self.max_prompt_chars,
                "max_response_chars_per_call": self.max_response_chars,
            }


@dataclass(frozen=True)
class StructuredModelResponse:
    call_id: str
    ok: bool
    parsed: dict[str, Any]
    raw_response: str
    error: str
    evidence_id: str


Validator = Callable[[dict[str, Any]], list[str]]


class RecordedModelRunner:
    """Call a model once, validate strict JSON and persist request/response evidence."""

    def __init__(
        self,
        path: Path,
        client: ModelClient,
        budget: ModelCallBudget,
        *,
        temperature: float,
        allow_live_model: bool,
        run_id: str,
    ) -> None:
        self.path = Path(path)
        self.client = client
        self.budget = budget
        self.temperature = float(temperature)
        self.allow_live_model = bool(allow_live_model)
        self.run_id = str(run_id)
        self._seq = 0
        self._calls = 0
        self._valid = 0
        self._invalid = 0
        self._lock = threading.RLock()

    def _append(self, event: dict[str, Any]) -> None:
        with self._lock:
            self._seq += 1
            record = {"seq": self._seq, "ts": time.time(), **event}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def call_json(
        self,
        prompt: str,
        *,
        task: str,
        agent_id: str | None,
        validator: Validator,
    ) -> StructuredModelResponse:
        prompt = str(prompt)
        info = self.client.info
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if info.live and not self.allow_live_model:
            self._append(
                {
                    "event": "model_call_blocked",
                    "reason": "live_model_permission_missing",
                    "provider": info.provider,
                    "model_version": info.model_version,
                    "prompt_sha256": prompt_hash,
                }
            )
            raise LiveModelCallBlocked(
                "live model call requires explicit allow_live_model=True"
            )
        ordinal = self.budget.reserve(len(prompt))
        self._calls += 1
        call_id = f"{self.run_id}:call-{self._calls}"
        evidence_id = f"model-call:{call_id}"
        self._append(
            {
                "event": "model_request",
                "call_id": call_id,
                "global_call_ordinal": ordinal,
                "evidence_id": evidence_id,
                "provider": info.provider,
                "model_version": info.model_version,
                "temperature": self.temperature,
                "task": task,
                "agent_id": agent_id,
                "prompt": prompt,
                "prompt_sha256": prompt_hash,
                "prompt_chars": len(prompt),
            }
        )
        started = time.perf_counter()
        raw = ""
        parsed: dict[str, Any] = {}
        errors: list[str] = []
        try:
            raw = self.client.generate(prompt, task=task, agent_id=agent_id)
        except Exception as exc:  # noqa: BLE001 - provider errors become evidence
            errors.append(f"provider_error:{type(exc).__name__}:{exc}")
        latency_ms = int((time.perf_counter() - started) * 1000)
        self.budget.record_response(len(raw))
        if len(raw) > self.budget.max_response_chars:
            errors.append(
                f"response_too_long:{len(raw)}>{self.budget.max_response_chars}"
            )
        if not errors:
            try:
                payload = json.loads(raw.strip())
            except json.JSONDecodeError as exc:
                errors.append(f"json_parse_error:{exc.msg}")
            else:
                if not isinstance(payload, dict):
                    errors.append("response_must_be_json_object")
                else:
                    parsed = payload
                    errors.extend(validator(parsed))
        ok = not errors
        if ok:
            self._valid += 1
        else:
            self._invalid += 1
        self._append(
            {
                "event": "model_response",
                "call_id": call_id,
                "evidence_id": evidence_id,
                "ok": ok,
                "raw_response": raw,
                "raw_response_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                "response_chars": len(raw),
                "parsed": parsed,
                "errors": errors,
                "latency_ms": latency_ms,
            }
        )
        return StructuredModelResponse(
            call_id=call_id,
            ok=ok,
            parsed=parsed,
            raw_response=raw,
            error=",".join(errors),
            evidence_id=evidence_id,
        )

    def summary(self) -> dict[str, Any]:
        return {
            "provider": self.client.info.provider,
            "model_version": self.client.info.model_version,
            "live": self.client.info.live,
            "temperature": self.temperature,
            "calls": self._calls,
            "valid_responses": self._valid,
            "invalid_responses": self._invalid,
            "all_responses_valid": self._calls > 0 and self._invalid == 0,
            "trace_path": str(self.path),
            "budget": self.budget.snapshot(),
        }


def dataclass_payload(value: Any) -> dict[str, Any]:
    """Small public helper for evidence manifests."""

    return asdict(value)


__all__ = [
    "CallableModelClient",
    "GAWorldModelClient",
    "LiveModelCallBlocked",
    "ModelCallBudget",
    "ModelCallBudgetExceeded",
    "ModelClientInfo",
    "RecordedModelRunner",
    "StructuredModelResponse",
]
