from typing import Any
from abstralix.plugins.base.base_type import BaseTypePlugin


class BoolTypePlugin(BaseTypePlugin):
    name = "bool"

    def validate(self, value: Any) -> bool:
        return isinstance(value, bool)

    def assign(self, base_val: Any, new_val: Any) -> Any:
        return bool(new_val)

    def append(self, base_val: Any, delta_val: Any) -> Any:
        return bool(delta_val)

    def remove(self, base_val: Any, delta_val: Any) -> Any:
        return base_val
