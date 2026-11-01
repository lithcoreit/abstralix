import os
import time
from typing import Any, Dict, List, Optional
import httpx

from abstralix.plugins.providers.base import BaseProviderPlugin, ProviderResponse
from abstralix.errors import RuntimeAbxError

CODE_FENCE = "`" * 3


def strip_code_fences(text: str) -> str:
    """Очищает ответ LLM от обрамляющих блоков кода, если модель их добавила."""
    cleaned = text.strip()
    if CODE_FENCE in cleaned:
        parts = cleaned.split(CODE_FENCE)
        if len(parts) >= 3:
            code_block = parts[1]
            lines = code_block.splitlines()
            if lines and lines[0].strip().isalpha():
                lines = lines[1:]
            return "\n".join(lines).strip()
    return cleaned


class OpenAICompatibleProvider(BaseProviderPlugin):
    adapter_id = "openai_compatible"

    def _resolve_api_key(self, raw_key: str) -> str:
        if raw_key.startswith("env:"):
            env_name = raw_key.split("env:", 1)[1].strip()
            val = os.environ.get(env_name, "")
            if not val:
                raise RuntimeAbxError(
                    code="RT_PROVIDER_AUTHENTICATION",
                    message=f"Environment variable '{env_name}' for API key is empty or not set",
                )
            return val
        return raw_key

    async def send_prompt(
        self,
        messages: List[Dict[str, str]],
        model: str,
        base_url: str,
        api_key: str,
        temperature: float = 0.2,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> ProviderResponse:
        resolved_key = self._resolve_api_key(api_key)
        url = f"{base_url.rstrip('/')}/chat/completions"

        headers = {"Content-Type": "application/json"}
        if resolved_key and resolved_key != "not-needed":
            headers["Authorization"] = f"Bearer {resolved_key}"

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if extra_params:
            payload.update(extra_params)

        start_t = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except httpx.RequestError as exc:
            raise RuntimeAbxError(
                code="RT_PROVIDER_UNREACHABLE",
                message=f"Could not connect to LLM provider at '{url}': {exc}",
                hint="Ensure LM Studio / Ollama server is running or check your internet connection.",
            )

        latency = (time.perf_counter() - start_t) * 1000.0

        if resp.status_code in (401, 403):
            raise RuntimeAbxError(
                code="RT_PROVIDER_AUTHENTICATION",
                message=f"Authentication failed ({resp.status_code}) at '{url}': {resp.text}",
            )

        if resp.status_code >= 400:
            raise RuntimeAbxError(
                code="RT_PROVIDER_ERROR",
                message=f"Provider returned HTTP {resp.status_code}: {resp.text}",
            )

        data = resp.json()
        raw_content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return ProviderResponse(
            content=strip_code_fences(raw_content),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_ms=round(latency, 2),
        )

    async def check_health(self, base_url: str, api_key: str) -> bool:
        url = f"{base_url.rstrip('/')}/models"
        headers = {}
        if api_key and not api_key.startswith("env:") and api_key != "not-needed":
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=headers)
                return resp.status_code < 500
        except Exception:
            return False