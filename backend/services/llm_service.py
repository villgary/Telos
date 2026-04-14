"""
LLM Service — generates AI reports for assets and scan results.
Supports OpenAI, Anthropic Claude, Ollama (local),
MiniMax (M2/M2.5/M2.7), DeepSeek, and Zhipu (智谱GLM).
"""

import logging
from typing import Optional
from backend import encryption

logger = logging.getLogger("llm_service")


def _call_openai(api_key: str, model: str, base_url: Optional[str], system: str, user: str) -> str:
    import requests
    endpoint = (base_url or "https://api.openai.com") + "/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
    }
    resp = requests.post(endpoint, headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"OpenAI API error {resp.status_code}: {resp.text[:200]}")
    return resp.json()["choices"][0]["message"]["content"]


def _call_anthropic(api_key: str, model: str, base_url: Optional[str], system: str, user: str) -> str:
    import requests
    endpoint = (base_url or "https://api.anthropic.com") + "/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model or "claude-sonnet-4-20250514",
        "messages": [
            {"role": "user", "content": f"{system}\n\n{user}"},
        ],
        "max_tokens": 2000,
        "temperature": 0.3,
    }
    resp = requests.post(endpoint, headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Anthropic API error {resp.status_code}: {resp.text[:200]}")
    return resp.json()["content"][0]["text"]


def _call_ollama(base_url: str, model: str, system: str, user: str) -> str:
    import requests
    endpoint = f"{base_url}/api/generate"
    payload = {
        "model": model,
        "prompt": f"{system}\n\n{user}",
        "stream": False,
        "options": {"temperature": 0.3},
    }
    resp = requests.post(endpoint, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Ollama API error {resp.status_code}: {resp.text[:200]}")
    return resp.json().get("response", "")


def _call_openai_compat(
    api_key: str,
    model: str,
    endpoint: str,
    system: str,
    user: str,
) -> str:
    """Generic OpenAI-compatible chat completions caller."""
    import requests
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
    }
    resp = requests.post(endpoint, headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"API error {resp.status_code}: {resp.text[:300]}")
    return resp.json()["choices"][0]["message"]["content"]


def generate_report(
    provider: str,
    api_key_enc: Optional[str],
    base_url: Optional[str],
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """
    Call LLM API and return the generated text.
    api_key_enc must be decrypted by the caller.
    """
    api_key = encryption.decrypt(api_key_enc) if api_key_enc else None

    if provider == "openai":
        if not api_key:
            raise ValueError("OpenAI API key not configured")
        return _call_openai(api_key, model, base_url, system_prompt, user_prompt)

    elif provider == "anthropic":
        if not api_key:
            raise ValueError("Anthropic API key not configured")
        return _call_anthropic(api_key, model, base_url, system_prompt, user_prompt)

    elif provider == "ollama":
        if not base_url:
            raise ValueError("Ollama base_url not configured")
        return _call_ollama(base_url, model, system_prompt, user_prompt)

    elif provider == "minimax":
        if not api_key:
            raise ValueError("MiniMax API key not configured")
        endpoint = (base_url or "https://api.minimaxi.com/v1") + "/chat/completions"
        return _call_openai_compat(api_key, model, endpoint, system_prompt, user_prompt)

    elif provider == "deepseek":
        if not api_key:
            raise ValueError("DeepSeek API key not configured")
        endpoint = (base_url or "https://api.deepseek.com/v1") + "/chat/completions"
        return _call_openai_compat(api_key, model, endpoint, system_prompt, user_prompt)

    elif provider == "zhipu":
        if not api_key:
            raise ValueError("Zhipu AI API key not configured")
        endpoint = (base_url or "https://open.bigmodel.cn/api/paas/v4") + "/chat/completions"
        return _call_openai_compat(api_key, model, endpoint, system_prompt, user_prompt)

    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
