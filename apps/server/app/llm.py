from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx


@dataclass
class LLMConfig:
    host: str
    model: str
    timeout_ms: int = 120000
    temperature: float = 0.3
    top_p: float = 0.9
    repeat_penalty: float = 1.1
    num_ctx: Optional[int] = None  # let server default if None


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


def _sleep_backoff(attempt: int) -> None:
    # simple exponential backoff with jitter: 100ms, 300ms, 900ms ...
    base = 0.1 * (3 ** attempt)
    jitter = random.uniform(0, 0.1)
    time.sleep(base + jitter)


def ollama_chat(system: str, user: str, cfg: LLMConfig, retries: int = 2) -> Tuple[str, Dict[str, Any]]:
    """Call Ollama's /api/chat and return (text, meta).

    meta includes timing and token counts if available.
    """
    url = cfg.host.rstrip("/") + "/api/chat"
    payload: Dict[str, Any] = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {
            "temperature": cfg.temperature,
            "top_p": cfg.top_p,
            "repeat_penalty": cfg.repeat_penalty,
        },
        "stream": False,
    }
    if cfg.num_ctx:
        payload["options"]["num_ctx"] = cfg.num_ctx

    start = _now_ms()
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=cfg.timeout_ms / 1000.0) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                # Ollama returns {message: {content: ...}, eval_count, prompt_eval_count, total_duration, ...}
                content = data.get("message", {}).get("content", "")
                meta = {
                    "eval_count": data.get("eval_count"),
                    "prompt_eval_count": data.get("prompt_eval_count"),
                    "total_duration": data.get("total_duration"),
                }
                meta["llm_ms"] = _now_ms() - start
                return content, meta
        except Exception as e:
            last_exc = e
            if attempt < retries:
                _sleep_backoff(attempt)
                continue
            raise


_CIT_PATTERN = re.compile(r"\[CIT-(\d+)\]")


def extract_citation_indices(text: str) -> List[int]:
    """Return sorted unique citation indices found in text as integers."""
    seen = set(int(m.group(1)) for m in _CIT_PATTERN.finditer(text))
    return sorted(seen)

