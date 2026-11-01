import os
import time
from typing import Any, Dict, List, Optional
import httpx

from abstralix.plugins.providers.base import BaseProviderPlugin, ProviderResponse
from abstralix.errors import RuntimeAbxError


class AnthropicProvider(BaseProviderPlugin):
    adapter_id = "anthropic"

    def _resolve_api_key(self, raw_key: str) -> str:
        if raw_key.startswith("env:"):
            env_name = raw_key.split("env:", 1)[1].strip()
            val = os.environ.get(env_name, "")
            if not val:
                raise RuntimeAbxError(
                    code="RT_PROVIDER_AUTHENTICATION",
                    message=f"Environment variable '{env_name}' for Anthropic API key is empty or not set",
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
        url = f"{base_url.rstrip('/')}/v1/messages" if "/v1" not in base_url else f"{base_url.rstrip('/')}/messages"
        if not base_url or base_url == "default":
            url = "https://api.anthropic.com/v1/messages"

        headers = {
            "x-api-key": resolved_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        # Extract system prompt if present
        system_prompt = ""
        user_assistant_msgs = []
        for m in messages:
            if m["role"] == "system":
                system_prompt = m["content"]
            else:
                user_assistant_msgs.append({"role": m["role"], "content": m["content"]})

        payload: Dict[str, Any] = {
            "model": model,
            "messages": user_assistant_msgs,
            "max_tokens": 4096,
            "temperature": temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if extra_params:
            payload.update(extra_params)

        start_t = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except httpx.RequestError as exc:
            raise RuntimeAbxError(
                code="RT_PROVIDER_UNREACHABLE",
                message=f"Could not connect to Anthropic at '{url}': {exc}",
            )

        latency = (time.perf_counter() - start_t) * 1000.0

        if resp.status_code >= 400:
            raise RuntimeAbxError(
                code="RT_PROVIDER_ERROR",
                message=f"Anthropic returned HTTP {resp.status_code}: {resp.text}",
            )

        data = resp.json()
        raw_content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                raw_content += block.get("text", "")

        usage = data.get("usage", {})
        return ProviderResponse(
            content=raw_content.strip(),
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            latency_ms=round(latency, 2),
        )

    async def check_health(self, base_url: str, api_key: str) -> bool:
        if not api_key or api_key == "not-needed":
            return False
        try:
            resolved_key = self._resolve_api_key(api_key)
            return bool(resolved_key)
        except Exception:
            return False
