import copy
from typing import Any
from abstralix.plugins.base.base_type import BaseTypePlugin


class DictTypePlugin(BaseTypePlugin):
    name = "dict"

    def validate(self, value: Any) -> bool:
        return isinstance(value, dict)

    def assign(self, base_val: Any, new_val: Any) -> Any:
        return copy.deepcopy(new_val)

    def append(self, base_val: Any, delta_val: Any) -> Any:
        res = dict(base_val or {})
        if isinstance(delta_val, dict):
            res.update(delta_val)
        return res

    def remove(self, base_val: Any, delta_val: Any) -> Any:
        res = dict(base_val or {})
        keys = list(delta_val.keys()) if isinstance(delta_val, dict) else (
            delta_val if isinstance(delta_val, list) else [delta_val]
        )
        for k in keys:
            res.pop(k, None)
        return res
