from typing import Any
from abstralix.plugins.base.base_type import BaseTypePlugin


class IntTypePlugin(BaseTypePlugin):
    name = "int"

    def validate(self, value: Any) -> bool:
        return isinstance(value, int) and not isinstance(value, bool)

    def assign(self, base_val: Any, new_val: Any) -> Any:
        return new_val

    def append(self, base_val: Any, delta_val: Any) -> Any:
        return (base_val or 0) + delta_val

    def remove(self, base_val: Any, delta_val: Any) -> Any:
        return (base_val or 0) - delta_val


class FloatTypePlugin(BaseTypePlugin):
    name = "float"

    def validate(self, value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    def assign(self, base_val: Any, new_val: Any) -> Any:
        return float(new_val)

    def append(self, base_val: Any, delta_val: Any) -> Any:
        return float(base_val or 0.0) + float(delta_val)

    def remove(self, base_val: Any, delta_val: Any) -> Any:
        return float(base_val or 0.0) - float(delta_val)
