from abc import ABC
from typing import List


class BaseObjectPlugin(ABC):
    """Базовый контракт для структурных объектов (folder, file, void)."""
    name: str
    allowed_parents: List[str]
    can_contain: List[str]
    is_filesystem_node: bool = True
