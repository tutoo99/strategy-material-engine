#!/opt/miniconda3/bin/python3

from __future__ import annotations

import json
import os
import re
from typing import Any


DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-pro"
DEFAULT_DEEPSEEK_THINKING = "enabled"
DEFAULT_DEEPSEEK_REASONING_EFFORT = "high"
DEEPSEEK_THINKING_VALUES = {"", "enabled", "disabled"}
DEEPSEEK_REASONING_EFFORT_VALUES = {"", "low", "medium", "high", "max", "xhigh"}


def validate_deepseek_backend(backend: str) -> None:
    normalized = str(backend or "auto").strip().lower()
    if normalized not in {"", "auto", "deepseek"}:
        raise ValueError(f"Unsupported LLM backend: {backend}. Only deepseek is supported.")


def resolve_deepseek_config(
    *,
    api_key: str = "",
    base_url: str = "",
    model: str = "",
    api_key_env: str = "DEEPSEEK_API_KEY",
    base_url_env: str = "DEEPSEEK_BASE_URL",
    model_env: str = "DEEPSEEK_MODEL",
) -> dict[str, str]:
    resolved_api_key = str(api_key or os.getenv(api_key_env, "") or os.getenv("DEEPSEEK_API_KEY", "")).strip()
    if not resolved_api_key:
        raise RuntimeError(f"Missing DeepSeek API key. Set {api_key_env} or DEEPSEEK_API_KEY.")
    return {
        "backend": "deepseek",
        "api_key": resolved_api_key,
        "base_url": str(base_url or os.getenv(base_url_env, "") or os.getenv("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL)).strip(),
        "model": str(model or os.getenv(model_env, "") or os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)).strip(),
    }


def extract_json_from_text(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("LLM response is empty")
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, flags=re.S)
    if not match:
        raise ValueError(f"Unable to parse JSON from LLM response: {raw[:200]}")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("LLM response is not a JSON object")
    return parsed


def normalize_deepseek_thinking(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in DEEPSEEK_THINKING_VALUES:
        raise ValueError(f"Unsupported DeepSeek thinking type: {value}. Use enabled or disabled.")
    return normalized


def normalize_deepseek_reasoning_effort(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in DEEPSEEK_REASONING_EFFORT_VALUES:
        raise ValueError(f"Unsupported DeepSeek reasoning_effort: {value}. Use high or max.")
    if normalized in {"low", "medium"}:
        return "high"
    if normalized == "xhigh":
        return "max"
    return normalized


def resolve_deepseek_runtime_options(
    *,
    thinking: str | None,
    reasoning_effort: str | None,
) -> tuple[str, str]:
    resolved_thinking = normalize_deepseek_thinking(
        os.getenv("DEEPSEEK_THINKING", thinking if thinking is not None else DEFAULT_DEEPSEEK_THINKING)
    )
    if resolved_thinking == "disabled":
        return resolved_thinking, ""
    default_effort = reasoning_effort if reasoning_effort is not None else DEFAULT_DEEPSEEK_REASONING_EFFORT
    resolved_effort = normalize_deepseek_reasoning_effort(os.getenv("DEEPSEEK_REASONING_EFFORT", default_effort))
    return resolved_thinking, resolved_effort


def deepseek_extra_body(*, thinking: str) -> dict[str, Any]:
    extra_body: dict[str, Any] = {}
    if thinking:
        extra_body["thinking"] = {"type": thinking}
    return extra_body


def call_deepseek_json(
    *,
    system_prompt: str,
    user_prompt: str,
    api_key: str = "",
    base_url: str = "",
    model: str = "",
    timeout: float = 120.0,
    temperature: float = 0.1,
    thinking: str | None = DEFAULT_DEEPSEEK_THINKING,
    reasoning_effort: str | None = DEFAULT_DEEPSEEK_REASONING_EFFORT,
    api_key_env: str = "DEEPSEEK_API_KEY",
    base_url_env: str = "DEEPSEEK_BASE_URL",
    model_env: str = "DEEPSEEK_MODEL",
) -> dict[str, Any]:
    from openai import OpenAI

    config = resolve_deepseek_config(
        api_key=api_key,
        base_url=base_url,
        model=model,
        api_key_env=api_key_env,
        base_url_env=base_url_env,
        model_env=model_env,
    )
    client = OpenAI(
        api_key=config["api_key"],
        base_url=config["base_url"],
        timeout=timeout,
        max_retries=1,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    resolved_thinking, resolved_effort = resolve_deepseek_runtime_options(
        thinking=thinking,
        reasoning_effort=reasoning_effort,
    )
    extra_body = deepseek_extra_body(thinking=resolved_thinking)
    last_error: Exception | None = None
    for use_response_format in (True, False):
        try:
            kwargs: dict[str, Any] = {
                "model": config["model"],
                "messages": messages,
                "stream": False,
                "extra_body": extra_body,
            }
            if resolved_effort:
                kwargs["reasoning_effort"] = resolved_effort
            if resolved_thinking != "enabled":
                kwargs["temperature"] = temperature
            if use_response_format:
                kwargs["response_format"] = {"type": "json_object"}
            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            return extract_json_from_text(content)
        except Exception as exc:
            last_error = exc
            if not use_response_format:
                break
            continue
    if last_error:
        raise last_error
    raise RuntimeError("DeepSeek JSON call did not execute")
