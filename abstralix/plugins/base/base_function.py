from abc import ABC, abstractmethod
from typing import Any, List


class BaseFunctionPlugin(ABC):
    """Базовый контракт для compile-time функций (file(), env() и др.)."""
    name: str

    @abstractmethod
    def execute(self, args: List[Any], file_path: str) -> Any:
        pass
