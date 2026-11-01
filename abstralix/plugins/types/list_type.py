import copy
from typing import Any
from abstralix.plugins.base.base_type import BaseTypePlugin


class ListTypePlugin(BaseTypePlugin):
    name = "list"

    def validate(self, value: Any) -> bool:
        return isinstance(value, list)

    def assign(self, base_val: Any, new_val: Any) -> Any:
        return copy.deepcopy(new_val)

    def append(self, base_val: Any, delta_val: Any) -> Any:
        res = list(base_val or [])
        to_add = delta_val if isinstance(delta_val, list) else [delta_val]
        for item in to_add:
            if item not in res:
                res.append(item)
        return res

    def remove(self, base_val: Any, delta_val: Any) -> Any:
        res = list(base_val or [])
        to_remove = delta_val if isinstance(delta_val, list) else [delta_val]
        return [x for x in res if x not in to_remove]
