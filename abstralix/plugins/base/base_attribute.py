from abc import ABC
from typing import Any, List


class BaseAttributePlugin(ABC):
    """Базовый контракт для системных атрибутов (@context, @in, @use и др.)."""
    name: str
    allowed_scopes: List[str]
    allowed_types: List[str]
    inheritable: bool = True
    default: Any = None

    def normalize(self, value: Any) -> Any:
        """Автоприведение типов (синтаксический сахар)."""
        return value
