from typing import Any, Dict, List
from abstralix.plugins.registry import REGISTRY

OBJECT_RULES = REGISTRY.objects
ATTRIBUTE_RULES = REGISTRY.attributes


def normalize_attribute_value(attr_name: str, value: Any) -> Any:
    if attr_name in REGISTRY.attributes:
        return REGISTRY.attributes[attr_name].normalize(value)
    return value


def check_value_type(value: Any, allowed_types: List[str]) -> bool:
    return REGISTRY.check_value_type(value, allowed_types)


def apply_operator(operator: str, base_val: Any, new_val: Any) -> Any:
    return REGISTRY.apply_operator(operator, base_val, new_val)
