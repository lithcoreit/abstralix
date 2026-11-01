from abc import ABC, abstractmethod
from typing import Any


class BaseTypePlugin(ABC):
    """Базовый контракт типа данных. Изолирует математику операторов =, +=, -=."""
    name: str

    @abstractmethod
    def validate(self, value: Any) -> bool:
        pass

    @abstractmethod
    def assign(self, base_val: Any, new_val: Any) -> Any:
        pass

    @abstractmethod
    def append(self, base_val: Any, delta_val: Any) -> Any:
        pass

    @abstractmethod
    def remove(self, base_val: Any, delta_val: Any) -> Any:
        pass
