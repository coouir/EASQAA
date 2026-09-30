"""Ollama client (SPEC §7.1): `/api/chat` with a JSON schema as `format`, seed and options per call.

Only the standard library is used. `FakeLLM` (tests, dry runs) has the same `chat` interface.
Defaults come from `configs/default.yaml` (`llm:`); the SPEC's defaults are think=false,
temperature=0.2, num_ctx=8192.
"""

import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from sarqa.config import load_config

SEED_MOD = 2**31


class LLMError(Exception):
    """The model server failed (connection, HTTP, timeout, bad response body)."""


def seed_for(qid: str, repeat: int) -> int:
    """`seed = hash(qid, repeat) mod 2^31`. Condition-independent, so paired conditions share it."""
    digest = hashlib.sha256(f"{qid}|{repeat}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % SEED_MOD


@dataclass
class LLMReply:
    content: str
    tokens_in: int = 0
    tokens_out: int = 0
    ms: int = 0
    raw: dict = field(default_factory=dict)


class OllamaClient:
    def __init__(self, model: str | None = None, host: str | None = None, **options):
        cfg = load_config()["llm"]
        self.model = model or cfg["model"]
        self.host = (host or cfg["host"]).rstrip("/")
        self.think = cfg["think"]
        self.keep_alive = cfg.get("keep_alive", -1)   # -1: the model stays loaded between runs
        self.options = {"temperature": cfg["temperature"], "num_ctx": cfg["num_ctx"],
                        "num_predict": cfg["num_predict"], **options}

    def _post(self, path: str, body: dict | None, timeout: float) -> dict:
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(f"{self.host}{path}", data, {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            raise LLMError(f"{type(e).__name__}: {e}") from e

    def chat(self, messages: list[dict], schema: dict, seed: int, timeout: float = 300) -> LLMReply:
        body = {"model": self.model, "messages": messages, "stream": False, "think": self.think,
                "keep_alive": self.keep_alive, "format": schema, "options": {**self.options, "seed": seed}}
        t0 = time.monotonic()
        out = self._post("/api/chat", body, timeout)
        msg = out.get("message") or {}
        if "content" not in msg:
            raise LLMError(f"response without message content: {str(out)[:200]}")
        return LLMReply(msg["content"], out.get("prompt_eval_count", 0), out.get("eval_count", 0),
                        int((time.monotonic() - t0) * 1000), {"done_reason": out.get("done_reason")})

    def info(self) -> dict:
        """Server version and model digest for the run metadata (SPEC §0-5)."""
        version = self._post("/api/version", None, 10).get("version")
        tags = self._post("/api/tags", None, 10).get("models", [])
        digest = next((m.get("digest") for m in tags if m.get("name") == self.model), None)
        return {"ollama_version": version, "model": self.model, "model_digest": digest}


class FakeLLM:
    """Scripted replies for tests: `replies` is a list of str/dict/Exception, one per `chat` call."""

    def __init__(self, replies, model: str = "fake"):
        self.replies = list(replies)
        self.calls: list[dict] = []
        self.model = model

    def chat(self, messages, schema, seed, timeout=300) -> LLMReply:
        self.calls.append({"messages": list(messages), "schema": schema, "seed": seed})
        if not self.replies:
            raise LLMError("FakeLLM has no more scripted replies")
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return LLMReply(r if isinstance(r, str) else json.dumps(r), tokens_in=10, tokens_out=5, ms=1)

    def info(self) -> dict:
        return {"ollama_version": "fake", "model": self.model, "model_digest": "fake"}
