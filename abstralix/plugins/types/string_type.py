import copy
from typing import Any
from abstralix.plugins.base.base_type import BaseTypePlugin


class StringTypePlugin(BaseTypePlugin):
    name = "str"

    def validate(self, value: Any) -> bool:
        return isinstance(value, str) and value != "auto"

    def assign(self, base_val: Any, new_val: Any) -> Any:
        return copy.deepcopy(new_val)

    def append(self, base_val: Any, delta_val: Any) -> Any:
        if not base_val:
            return delta_val
        return f"{base_val}\n\n{delta_val}"

    def remove(self, base_val: Any, delta_val: Any) -> Any:
        if isinstance(base_val, str) and isinstance(delta_val, str):
            return base_val.replace(delta_val, "")
        return base_val
