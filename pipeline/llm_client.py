"""
Central LLM client — the single place every pipeline module talks to the model.

Why this exists:
- Free-tier GitHub Models rate-limits hard. Previously each module instantiated its
  own OpenAI client and called it with zero retry/backoff, so one 429 anywhere killed
  the whole run. This wrapper adds retry-with-backoff (honouring Retry-After), a
  throttle that spaces calls apart, an explicit timeout, and an on-disk response cache
  so re-runs on the same input cost no quota.
- Raw model output was fed straight into json.loads(), which crashes on a stray
  ```json fence. chat_json() strips fences and does one corrective re-prompt before
  raising a typed error.
"""

import hashlib
import json
import threading
import time
from pathlib import Path

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from config import settings

# ── Shared client ────────────────────────────────────────────────────────────
_client = OpenAI(
    base_url=settings.llm_base_url,
    api_key=settings.github_access_token,
    timeout=settings.request_timeout,
)

class MalformedLLMJSON(ValueError):
    """Raised when the model cannot be coaxed into returning valid JSON."""


# ── Throttle + call counter ────────────────────────────────────────────────────
_throttle_lock = threading.Lock()
_last_call_ts = 0.0

# Outbound-call counter (excludes cache hits) — used by cli.py for verification/logging.
call_count = 0
cache_hit_count = 0


def _throttle() -> None:
    """Ensure at least min_seconds_between_calls between outbound requests."""
    global _last_call_ts
    with _throttle_lock:
        wait = settings.min_seconds_between_calls - (time.monotonic() - _last_call_ts)
        if wait > 0:
            time.sleep(wait)
        _last_call_ts = time.monotonic()


def _should_retry(exc: BaseException) -> bool:
    # Retry on all rate-limit/timeout/connection errors, but for generic
    # APIStatusError only retry server-side (5xx) — not 4xx client errors.
    if isinstance(exc, (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code >= 500
    return False


# ── Cache ──────────────────────────────────────────────────────────────────────
def _cache_path(key: str) -> Path:
    cache_dir = Path(settings.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{key}.txt"


def _cache_key(model: str, system: str, user: str, temperature: float) -> str:
    raw = f"{model}\x00{temperature}\x00{system}\x00{user}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@retry(
    retry=retry_if_exception(_should_retry),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    stop=stop_after_attempt(settings.max_retries),
    reraise=True,
)
def _create(messages, temperature, max_tokens, response_format, seed):
    """Single outbound request point — throttled, counted, and retried by tenacity."""
    global call_count
    _throttle()
    call_count += 1
    kwargs = {
        "model": settings.model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    if seed is not None:
        kwargs["seed"] = seed
    return _client.chat.completions.create(**kwargs)


def chat(
    system: str,
    user: str,
    *,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    seed: int | None = None,
) -> str:
    """Plain-text completion with retry/backoff/throttle. Returns the message content."""
    global cache_hit_count
    key = _cache_key(settings.model, system, user, temperature)

    if settings.cache_enabled:
        path = _cache_path(key)
        if path.exists():
            cache_hit_count += 1
            return path.read_text(encoding="utf-8")

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    response = _create(messages, temperature, max_tokens, None, seed)
    content = (response.choices[0].message.content or "").strip()

    if settings.cache_enabled:
        _cache_path(key).write_text(content, encoding="utf-8")
    return content


def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` / ``` ... ``` wrappers the model sometimes adds."""
    t = text.strip()
    if t.startswith("```"):
        # drop the opening fence line (``` or ```json) and the trailing fence
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def chat_json(
    system: str,
    user: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 2048,
    seed: int | None = None,
) -> dict:
    """
    JSON completion with fence-stripping and one corrective re-prompt on parse failure.
    Requests response_format=json_object, then defends against fenced/garbled output.
    """
    global cache_hit_count
    key = _cache_key(settings.model, system, user, temperature)

    if settings.cache_enabled:
        path = _cache_path(key)
        if path.exists():
            try:
                cached = json.loads(path.read_text(encoding="utf-8"))
                cache_hit_count += 1
                return cached
            except json.JSONDecodeError:
                pass  # corrupt cache entry — fall through and regenerate

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    response_format = {"type": "json_object"}

    response = _create(messages, temperature, max_tokens, response_format, seed)
    raw = response.choices[0].message.content or ""

    parsed = _try_parse(raw)
    if parsed is None:
        # One corrective attempt: hand the bad output back and demand clean JSON.
        correction = [
            *messages,
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": (
                    "Your previous response was not valid JSON. Return ONLY the JSON "
                    "object, with no markdown fences, comments, or prose."
                ),
            },
        ]
        response = _create(correction, temperature, max_tokens, response_format, seed)
        raw = response.choices[0].message.content or ""
        parsed = _try_parse(raw)

    if parsed is None:
        raise MalformedLLMJSON(f"Model did not return valid JSON:\n{raw[:500]}")

    if settings.cache_enabled:
        _cache_path(key).write_text(json.dumps(parsed), encoding="utf-8")
    return parsed


def _try_parse(raw: str) -> dict | None:
    for candidate in (raw, _strip_fences(raw)):
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
    return None
