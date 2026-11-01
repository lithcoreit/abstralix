from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ProviderResponse:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0


class BaseProviderPlugin(ABC):
    adapter_id: str = "base"

    @abstractmethod
    async def send_prompt(
        self,
        messages: List[Dict[str, str]],
        model: str,
        base_url: str,
        api_key: str,
        temperature: float = 0.2,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> ProviderResponse:
        pass

    @abstractmethod
    async def check_health(self, base_url: str, api_key: str) -> bool:
        pass