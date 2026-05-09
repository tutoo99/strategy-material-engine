#!/opt/miniconda3/bin/python3

from __future__ import annotations

import json
import os
import re
from typing import Any


DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-pro"


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


def deepseek_extra_body() -> dict[str, Any]:
    extra_body: dict[str, Any] = {}
    thinking_type = os.getenv("DEEPSEEK_THINKING", "enabled").strip()
    if thinking_type:
        extra_body["thinking"] = {"type": thinking_type}
    reasoning_effort = os.getenv("DEEPSEEK_REASONING_EFFORT", "high").strip()
    if reasoning_effort:
        extra_body["reasoning_effort"] = reasoning_effort
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
    extra_body = deepseek_extra_body()
    last_error: Exception | None = None
    for use_response_format in (True, False):
        try:
            kwargs: dict[str, Any] = {
                "model": config["model"],
                "temperature": temperature,
                "messages": messages,
                "stream": False,
                "extra_body": extra_body,
            }
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
